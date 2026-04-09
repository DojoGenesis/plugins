/**
 * Markdown Renderer — Parses Markdown into PdfBlocks.
 *
 * Uses `marked` for parsing, extracts structure into blocks
 * that the PDF generator can lay out with Pretext typography.
 */

import { marked, type Token, type Tokens } from "marked";
import type { PdfBlock, Renderer } from "./types.js";

function extractFrontmatter(source: string): {
  frontmatter: Record<string, string> | null;
  body: string;
} {
  const match = source.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { frontmatter: null, body: source };

  const pairs: Record<string, string> = {};
  for (const line of match[1].split("\n")) {
    const colonIdx = line.indexOf(":");
    if (colonIdx > 0) {
      pairs[line.slice(0, colonIdx).trim()] = line.slice(colonIdx + 1).trim();
    }
  }
  return { frontmatter: pairs, body: match[2] };
}

function tokensToBlocks(tokens: Token[]): PdfBlock[] {
  const blocks: PdfBlock[] = [];

  for (const token of tokens) {
    switch (token.type) {
      case "heading": {
        const t = token as Tokens.Heading;
        blocks.push({
          type: "heading",
          content: t.text,
          metadata: { level: t.depth },
        });
        break;
      }

      case "paragraph": {
        const t = token as Tokens.Paragraph;
        blocks.push({ type: "text", content: t.text });
        break;
      }

      case "code": {
        const t = token as Tokens.Code;
        blocks.push({
          type: "code",
          content: t.text,
          metadata: { lang: t.lang ?? "text" },
        });
        break;
      }

      case "hr": {
        blocks.push({ type: "rule", content: "" });
        break;
      }

      case "table": {
        const t = token as Tokens.Table;
        const header = t.header.map((cell) => cell.text);
        const rows = t.rows.map((row) => row.map((cell) => cell.text));
        blocks.push({
          type: "table",
          content: "",
          metadata: { header, rows },
        });
        break;
      }

      case "list": {
        const t = token as Tokens.List;
        const items = t.items.map((item) => item.text);
        const prefix = t.ordered ? "ol" : "ul";
        blocks.push({
          type: "text",
          content: items
            .map((text, i) =>
              prefix === "ol" ? `${i + 1}. ${text}` : `  - ${text}`
            )
            .join("\n"),
          metadata: { listType: prefix },
        });
        break;
      }

      case "blockquote": {
        const t = token as Tokens.Blockquote;
        const inner = tokensToBlocks(t.tokens);
        for (const block of inner) {
          blocks.push({
            ...block,
            metadata: { ...block.metadata, blockquote: true },
          });
        }
        break;
      }

      case "space":
        // Skip whitespace tokens
        break;

      default:
        // Catch-all: render as text
        if ("text" in token) {
          blocks.push({
            type: "text",
            content: (token as any).text ?? "",
          });
        }
    }
  }

  return blocks;
}

export const markdownRenderer: Renderer = {
  name: "markdown",
  extensions: [".md", ".markdown", ".mdx"],

  async parse(source: string, filename: string): Promise<PdfBlock[]> {
    const { frontmatter, body } = extractFrontmatter(source);
    const blocks: PdfBlock[] = [];

    // Add frontmatter as metadata header if present
    if (frontmatter) {
      const name = frontmatter.name ?? frontmatter.title;
      if (name) {
        blocks.push({
          type: "heading",
          content: name,
          metadata: { level: 1, fromFrontmatter: true },
        });
      }
      if (frontmatter.description) {
        blocks.push({
          type: "text",
          content: frontmatter.description,
          metadata: { subtitle: true },
        });
      }
    }

    // Parse markdown body
    const tokens = marked.lexer(body);
    blocks.push(...tokensToBlocks(tokens));

    return blocks;
  },
};
