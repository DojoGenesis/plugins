/**
 * Code Renderer — Converts source code files into PdfBlocks
 * with syntax highlighting via Shiki.
 *
 * Outputs a single code block per file with language detection
 * and optional line numbers.
 */

import { extname } from "node:path";
import type { PdfBlock, Renderer } from "./types.js";

/**
 * Map file extensions to Shiki language identifiers.
 */
const EXTENSION_TO_LANG: Record<string, string> = {
  ".ts": "typescript",
  ".tsx": "tsx",
  ".js": "javascript",
  ".jsx": "jsx",
  ".go": "go",
  ".py": "python",
  ".rs": "rust",
  ".rb": "ruby",
  ".java": "java",
  ".kt": "kotlin",
  ".swift": "swift",
  ".c": "c",
  ".cpp": "cpp",
  ".h": "c",
  ".hpp": "cpp",
  ".cs": "csharp",
  ".php": "php",
  ".sh": "bash",
  ".bash": "bash",
  ".zsh": "bash",
  ".fish": "fish",
  ".sql": "sql",
  ".html": "html",
  ".css": "css",
  ".scss": "scss",
  ".less": "less",
  ".json": "json",
  ".yaml": "yaml",
  ".yml": "yaml",
  ".toml": "toml",
  ".xml": "xml",
  ".svg": "xml",
  ".graphql": "graphql",
  ".gql": "graphql",
  ".proto": "proto",
  ".dockerfile": "dockerfile",
  ".lua": "lua",
  ".vim": "vim",
  ".zig": "zig",
  ".wasm": "wasm",
  ".r": "r",
  ".m": "matlab",
  ".ex": "elixir",
  ".exs": "elixir",
  ".erl": "erlang",
  ".hs": "haskell",
  ".ml": "ocaml",
  ".clj": "clojure",
  ".lisp": "lisp",
  ".el": "lisp",
};

function detectLanguage(filename: string): string {
  const ext = extname(filename).toLowerCase();
  return EXTENSION_TO_LANG[ext] ?? "text";
}

export const codeRenderer: Renderer = {
  name: "code",
  extensions: Object.keys(EXTENSION_TO_LANG),

  async parse(source: string, filename: string): Promise<PdfBlock[]> {
    const lang = detectLanguage(filename);
    const blocks: PdfBlock[] = [];

    // File header
    blocks.push({
      type: "heading",
      content: filename.split("/").pop() ?? filename,
      metadata: { level: 2, fileHeader: true },
    });

    // Language and line count metadata
    blocks.push({
      type: "text",
      content: `${lang} | ${source.split("\n").length} lines`,
      metadata: { subtitle: true, muted: true },
    });

    blocks.push({ type: "rule", content: "" });

    // The code block itself — syntax highlighting happens at PDF generation time
    // where we have access to Shiki and the theme configuration
    blocks.push({
      type: "code",
      content: source,
      metadata: {
        lang,
        filename,
        lineCount: source.split("\n").length,
      },
    });

    return blocks;
  },
};
