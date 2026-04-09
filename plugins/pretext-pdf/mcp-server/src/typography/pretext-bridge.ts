/**
 * Pretext Bridge — Connects @chenglou/pretext to node-canvas for
 * server-side text measurement and layout computation.
 *
 * Pretext expects a Canvas 2D context for text measurement.
 * In Node.js, we provide this via the `canvas` package (Cairo-backed).
 *
 * IMPORTANT: Never use `system-ui` as a font family.
 * Canvas and DOM resolve it differently on macOS, causing measurement drift.
 */

import { createCanvas, registerFont, type Canvas } from "canvas";

// Pretext types (the library is lightweight, these are the core interfaces)
interface PretextModule {
  prepare(text: string, font: FontDescriptor): PreparedText;
  layout(
    prepared: PreparedText,
    maxWidth: number,
    lineHeight: number
  ): LayoutResult;
}

interface FontDescriptor {
  family: string;
  size: number;
  weight?: number;
  style?: string;
  variationSettings?: string;
}

interface PreparedText {
  // Opaque handle — Pretext's internal representation
  _brand: "PreparedText";
}

interface LayoutResult {
  width: number;
  height: number;
  lines: Array<{
    text: string;
    width: number;
    y: number;
  }>;
}

export interface TypographyConfig {
  fontFamily: string;
  codeFontFamily: string;
  fontSize: number;
  codeFontSize: number;
  lineHeight: number;
  codeLineHeight: number;
  headingScale: number[];
  maxWidth: number; // in points
}

const DEFAULT_CONFIG: TypographyConfig = {
  fontFamily: "Inter",
  codeFontFamily: "Recursive",
  fontSize: 11,
  codeFontSize: 9.5,
  lineHeight: 1.5,
  codeLineHeight: 1.35,
  headingScale: [2.0, 1.5, 1.25, 1.1, 1.0, 0.875], // h1-h6 relative to body
  maxWidth: 468, // 6.5 inches at 72 dpi
};

let pretextModule: PretextModule | null = null;
let measureCanvas: Canvas | null = null;

/**
 * Lazy-load Pretext module. The library is browser-oriented so we
 * need the canvas package to provide the Canvas API it expects.
 */
async function ensurePretext(): Promise<PretextModule> {
  if (pretextModule) return pretextModule;

  // Create a measurement canvas (never rendered, just for text metrics)
  measureCanvas = createCanvas(1, 1);

  // Pretext uses globalThis.document.createElement('canvas') internally.
  // We patch the global to return our node-canvas instance.
  const origCreateElement = (globalThis as any).document?.createElement;
  (globalThis as any).document = {
    ...(globalThis as any).document,
    createElement(tag: string) {
      if (tag === "canvas") return createCanvas(1, 1);
      return origCreateElement?.call(document, tag);
    },
  };

  try {
    // Dynamic import — Pretext is ESM
    const mod = await import("@chenglou/pretext");
    pretextModule = mod.default ?? mod;
    return pretextModule!;
  } catch (error) {
    throw new Error(
      `Failed to load @chenglou/pretext. Ensure it is installed: ${error}`
    );
  }
}

/**
 * Measure text using Pretext's Canvas-based engine.
 * Returns exact layout dimensions for PDF placement.
 */
export async function measureText(
  text: string,
  font: FontDescriptor,
  maxWidth: number,
  lineHeight: number
): Promise<LayoutResult> {
  const pretext = await ensurePretext();
  const prepared = pretext.prepare(text, font);
  return pretext.layout(prepared, maxWidth, lineHeight);
}

/**
 * Compute shrink-wrapped width for a text block.
 * Binary search for the minimum width that preserves line count.
 * Used for chat bubble sizing.
 */
export async function shrinkWrap(
  text: string,
  font: FontDescriptor,
  maxWidth: number,
  lineHeight: number
): Promise<{ width: number; height: number; lines: number }> {
  const pretext = await ensurePretext();
  const prepared = pretext.prepare(text, font);

  // Get reference layout at max width
  const reference = pretext.layout(prepared, maxWidth, lineHeight);
  const targetLines = reference.lines.length;

  if (targetLines <= 1) {
    return {
      width: reference.width,
      height: reference.height,
      lines: 1,
    };
  }

  // Binary search for minimum width that keeps same line count
  let lo = reference.width * 0.5;
  let hi = maxWidth;

  while (hi - lo > 1) {
    const mid = (lo + hi) / 2;
    const attempt = pretext.layout(prepared, mid, lineHeight);
    if (attempt.lines.length <= targetLines) {
      hi = mid;
    } else {
      lo = mid;
    }
  }

  const final = pretext.layout(prepared, hi, lineHeight);
  return {
    width: Math.ceil(final.width),
    height: final.height,
    lines: final.lines.length,
  };
}

/**
 * Register a variable font file for use in Canvas text measurement.
 */
export function registerVariableFont(
  path: string,
  family: string,
  weight?: string,
  style?: string
): void {
  registerFont(path, {
    family,
    weight: weight ?? "normal",
    style: style ?? "normal",
  });
}

export function createConfig(
  overrides?: Partial<TypographyConfig>
): TypographyConfig {
  return { ...DEFAULT_CONFIG, ...overrides };
}

export { type FontDescriptor, type LayoutResult, type PreparedText };
export { DEFAULT_CONFIG };
