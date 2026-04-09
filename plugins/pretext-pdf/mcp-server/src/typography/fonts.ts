/**
 * Font management for Pretext PDF export.
 *
 * Manages font loading, fallback chains, and variation settings
 * for the three primary variable font families:
 * - Inter (body text)
 * - Recursive (code)
 * - Fraunces (display/headings)
 */

import { existsSync } from "node:fs";
import { join } from "node:path";
import { registerVariableFont } from "./pretext-bridge.js";

export interface FontStack {
  body: FontConfig;
  code: FontConfig;
  display: FontConfig;
}

export interface FontConfig {
  family: string;
  path: string | null; // null = use system font
  variationSettings: Record<string, number>;
  fallback: string[];
}

const DEFAULT_FONT_STACK: FontStack = {
  body: {
    family: "Inter",
    path: null,
    variationSettings: {
      opsz: 16,
      wght: 400,
    },
    fallback: ["Helvetica Neue", "Arial", "sans-serif"],
  },
  code: {
    family: "Recursive",
    path: null,
    variationSettings: {
      MONO: 1,
      CASL: 0,
      slnt: 0,
      wght: 400,
    },
    fallback: ["SF Mono", "Menlo", "Consolas", "monospace"],
  },
  display: {
    family: "Fraunces",
    path: null,
    variationSettings: {
      SOFT: 50,
      WONK: 1,
      opsz: 48,
      wght: 700,
    },
    fallback: ["Georgia", "Times New Roman", "serif"],
  },
};

/**
 * Build a CSS font-variation-settings string from an axis map.
 */
export function buildVariationSettings(
  axes: Record<string, number>
): string {
  return Object.entries(axes)
    .map(([axis, value]) => `'${axis}' ${value}`)
    .join(", ");
}

/**
 * Build a complete font descriptor for Pretext measurement.
 */
export function fontDescriptor(
  config: FontConfig,
  size: number,
  weightOverride?: number
) {
  const axes = { ...config.variationSettings };
  if (weightOverride !== undefined) {
    axes.wght = weightOverride;
  }

  return {
    family: config.family,
    size,
    weight: axes.wght ?? 400,
    variationSettings: buildVariationSettings(axes),
  };
}

/**
 * Attempt to register bundled font files. If fonts aren't found,
 * fall back to system fonts (measurement may be less precise).
 */
export function loadFonts(fontDir?: string): FontStack {
  const stack = { ...DEFAULT_FONT_STACK };
  const dir = fontDir ?? join(process.cwd(), "fonts");

  if (!existsSync(dir)) {
    // No bundled fonts — use system fallbacks
    return stack;
  }

  const fontFiles: Array<{
    filename: string;
    family: string;
    key: keyof FontStack;
  }> = [
    { filename: "Inter-Variable.ttf", family: "Inter", key: "body" },
    {
      filename: "Recursive-Variable.ttf",
      family: "Recursive",
      key: "code",
    },
    {
      filename: "Fraunces-Variable.ttf",
      family: "Fraunces",
      key: "display",
    },
  ];

  for (const { filename, family, key } of fontFiles) {
    const fontPath = join(dir, filename);
    if (existsSync(fontPath)) {
      registerVariableFont(fontPath, family);
      stack[key] = { ...stack[key], path: fontPath };
    }
  }

  return stack;
}

/**
 * Get heading font descriptor at a specific heading level (1-6).
 */
export function headingFont(
  stack: FontStack,
  level: number,
  baseSize: number,
  headingScale: number[]
): ReturnType<typeof fontDescriptor> {
  const scale = headingScale[Math.min(level - 1, 5)] ?? 1;
  const size = baseSize * scale;
  const weight = level <= 2 ? 700 : level <= 4 ? 600 : 500;

  return fontDescriptor(stack.display, size, weight);
}

export { DEFAULT_FONT_STACK };
