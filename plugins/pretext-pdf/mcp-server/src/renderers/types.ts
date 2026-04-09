/**
 * Shared types for all renderers.
 */

import type { TypographyConfig } from "../typography/pretext-bridge.js";
import type { FontStack } from "../typography/fonts.js";

export interface RenderContext {
  typography: TypographyConfig;
  fonts: FontStack;
  theme: "light" | "dark";
  lineNumbers: boolean;
  pageSize: PageDimensions;
}

export interface PageDimensions {
  width: number; // points
  height: number; // points
  margins: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
}

export const PAGE_SIZES: Record<string, Omit<PageDimensions, "margins">> = {
  letter: { width: 612, height: 792 },
  a4: { width: 595.28, height: 841.89 },
  legal: { width: 612, height: 1008 },
};

export interface PdfBlock {
  type: "text" | "code" | "heading" | "rule" | "table" | "image" | "pagebreak";
  content: string;
  metadata?: Record<string, unknown>;
}

export interface RenderedPage {
  blocks: PdfBlock[];
}

export interface Renderer {
  name: string;
  /** File extensions this renderer handles (e.g., ['.md', '.markdown']) */
  extensions: string[];
  /** Parse source content into renderable blocks */
  parse(source: string, filename: string): Promise<PdfBlock[]>;
}
