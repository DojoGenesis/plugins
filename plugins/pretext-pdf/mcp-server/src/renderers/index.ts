/**
 * Renderer registry — auto-detects file type and selects the
 * appropriate renderer.
 */

import { extname } from "node:path";
import type { Renderer } from "./types.js";
import { markdownRenderer } from "./markdown.js";
import { codeRenderer } from "./code.js";
import { htmlRenderer } from "./html.js";
import { chatRenderer } from "./chat.js";
import { structuredRenderer, isStructuredFile } from "./structured.js";

const renderers: Renderer[] = [
  chatRenderer,
  htmlRenderer,
  markdownRenderer,
  codeRenderer,
  // structuredRenderer is used via explicit detection, not extension matching
];

/**
 * Select the best renderer for a file.
 *
 * Priority:
 * 1. Explicit renderer name override
 * 2. Structured file detection (content-based)
 * 3. Extension-based matching
 * 4. Fallback to code renderer (treats as plain text)
 */
export function selectRenderer(
  filename: string,
  source: string,
  explicit?: string
): Renderer {
  // Explicit override
  if (explicit && explicit !== "auto") {
    const found = renderers.find((r) => r.name === explicit);
    if (found) return found;
    if (explicit === "structured") return structuredRenderer;
    throw new Error(`Unknown renderer: ${explicit}`);
  }

  // Structured detection (must check before generic markdown)
  const ext = extname(filename).toLowerCase();
  if ((ext === ".md" || ext === ".markdown") && isStructuredFile(source, filename)) {
    return structuredRenderer;
  }

  // Chat JSON detection
  if (filename.endsWith(".chat.json") || filename.endsWith(".conversation.json")) {
    return chatRenderer;
  }

  // Extension-based matching
  for (const renderer of renderers) {
    if (renderer.extensions.includes(ext)) {
      return renderer;
    }
  }

  // Fallback: treat as code/plain text
  return codeRenderer;
}

export {
  markdownRenderer,
  codeRenderer,
  htmlRenderer,
  chatRenderer,
  structuredRenderer,
};

export type { Renderer, PdfBlock, RenderContext, PageDimensions } from "./types.js";
export { PAGE_SIZES } from "./types.js";
