/**
 * HTML Renderer — Converts HTML files into PdfBlocks.
 *
 * Extracts text content and structure from HTML, stripping scripts
 * and styles. For full-fidelity HTML rendering, use the Puppeteer
 * path (not implemented here — this is the lightweight text extraction).
 */

import type { PdfBlock, Renderer } from "./types.js";

/**
 * Lightweight HTML-to-blocks parser.
 * Strips tags and extracts text structure.
 * Not a full DOM parser — handles common patterns.
 */
function htmlToBlocks(source: string): PdfBlock[] {
  const blocks: PdfBlock[] = [];

  // Strip script and style blocks
  let cleaned = source.replace(/<script[\s\S]*?<\/script>/gi, "");
  cleaned = cleaned.replace(/<style[\s\S]*?<\/style>/gi, "");
  cleaned = cleaned.replace(/<!--[\s\S]*?-->/g, "");

  // Extract title
  const titleMatch = cleaned.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  if (titleMatch) {
    blocks.push({
      type: "heading",
      content: decodeEntities(titleMatch[1].trim()),
      metadata: { level: 1 },
    });
  }

  // Extract headings
  const headingRegex = /<h([1-6])[^>]*>([\s\S]*?)<\/h\1>/gi;
  let match: RegExpExecArray | null;
  while ((match = headingRegex.exec(cleaned)) !== null) {
    blocks.push({
      type: "heading",
      content: stripTags(decodeEntities(match[2])),
      metadata: { level: parseInt(match[1], 10) },
    });
  }

  // Extract paragraphs
  const paraRegex = /<p[^>]*>([\s\S]*?)<\/p>/gi;
  while ((match = paraRegex.exec(cleaned)) !== null) {
    const text = stripTags(decodeEntities(match[1])).trim();
    if (text) {
      blocks.push({ type: "text", content: text });
    }
  }

  // Extract code blocks
  const codeRegex = /<pre[^>]*><code[^>]*(?:class="[^"]*language-(\w+)")?[^>]*>([\s\S]*?)<\/code><\/pre>/gi;
  while ((match = codeRegex.exec(cleaned)) !== null) {
    blocks.push({
      type: "code",
      content: decodeEntities(match[2]),
      metadata: { lang: match[1] ?? "text" },
    });
  }

  // If no structured content found, extract all visible text
  if (blocks.length === 0) {
    // Get body content or full document
    const bodyMatch = cleaned.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    const bodyContent = bodyMatch ? bodyMatch[1] : cleaned;
    const text = stripTags(decodeEntities(bodyContent)).trim();
    if (text) {
      blocks.push({ type: "text", content: text });
    }
  }

  return blocks;
}

function stripTags(html: string): string {
  return html.replace(/<[^>]+>/g, "").replace(/\s+/g, " ");
}

function decodeEntities(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

export const htmlRenderer: Renderer = {
  name: "html",
  extensions: [".html", ".htm", ".xhtml"],

  async parse(source: string, filename: string): Promise<PdfBlock[]> {
    return htmlToBlocks(source);
  },
};
