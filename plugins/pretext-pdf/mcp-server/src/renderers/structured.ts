/**
 * Structured Renderer — Handles Dojo ecosystem files:
 * SKILL.md, ADR-*.md, STATUS.md, handoff packages.
 *
 * These files have predictable section structures that benefit
 * from specialized layout treatment (section headers, checklists,
 * metadata tables, cross-reference formatting).
 */

import type { PdfBlock, Renderer } from "./types.js";
import { markdownRenderer } from "./markdown.js";

/**
 * Detect if a Markdown file is a structured Dojo ecosystem file.
 */
export function isStructuredFile(source: string, filename: string): boolean {
  const name = filename.toLowerCase();

  // Explicit structured file patterns
  if (name.endsWith("skill.md")) return true;
  if (name.includes("adr-") || name.includes("/decisions/")) return true;
  if (name.endsWith("status.md")) return true;
  if (name.includes("/handoffs/")) return true;

  // Check for YAML frontmatter with known Dojo fields
  if (source.startsWith("---")) {
    const frontmatterEnd = source.indexOf("---", 3);
    if (frontmatterEnd > 0) {
      const fm = source.slice(3, frontmatterEnd).toLowerCase();
      if (
        fm.includes("name:") &&
        fm.includes("description:") &&
        (fm.includes("skill") || fm.includes("seed"))
      ) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Add structured enhancements on top of standard Markdown parsing:
 * - Section numbering for roman-numeral headers (I, II, III...)
 * - Checklist detection and formatting
 * - Cross-reference formatting for skill/seed mentions
 * - Metadata badge for frontmatter fields
 */
async function enhanceBlocks(
  blocks: PdfBlock[],
  source: string,
  filename: string
): Promise<PdfBlock[]> {
  const enhanced: PdfBlock[] = [];
  let sectionCounter = 0;

  // Add document type badge
  const docType = detectDocType(filename);
  if (docType) {
    enhanced.push({
      type: "text",
      content: docType.toUpperCase(),
      metadata: { badge: true, badgeColor: docTypeColor(docType) },
    });
  }

  for (const block of blocks) {
    if (block.type === "heading") {
      const level = (block.metadata?.level as number) ?? 2;

      // Detect roman numeral section headers in skills
      if (level === 2 && /^[IVX]+\.\s/.test(block.content)) {
        sectionCounter++;
        enhanced.push({
          ...block,
          metadata: {
            ...block.metadata,
            sectionNumber: sectionCounter,
            structured: true,
          },
        });
        continue;
      }
    }

    if (block.type === "text") {
      // Detect checklist items
      if (
        block.content.includes("[ ]") ||
        block.content.includes("[x]") ||
        block.content.includes("[X]")
      ) {
        enhanced.push({
          ...block,
          metadata: { ...block.metadata, checklist: true },
        });
        continue;
      }
    }

    enhanced.push(block);
  }

  return enhanced;
}

function detectDocType(filename: string): string | null {
  const name = filename.toLowerCase();
  if (name.endsWith("skill.md")) return "skill";
  if (name.includes("adr-") || name.includes("/decisions/")) return "decision";
  if (name.endsWith("status.md")) return "status";
  if (name.includes("/handoffs/")) return "handoff";
  if (name.includes("/scouts/")) return "scout";
  if (name.includes("/specs/")) return "specification";
  return null;
}

function docTypeColor(type: string): string {
  const colors: Record<string, string> = {
    skill: "#4A90D9",
    decision: "#D94A4A",
    status: "#4AD94A",
    handoff: "#D9A84A",
    scout: "#9B4AD9",
    specification: "#4AD9D9",
  };
  return colors[type] ?? "#888888";
}

export const structuredRenderer: Renderer = {
  name: "structured",
  extensions: [], // Detection is content-based, not extension-based

  async parse(source: string, filename: string): Promise<PdfBlock[]> {
    // Start with standard Markdown parsing
    const baseBlocks = await markdownRenderer.parse(source, filename);

    // Enhance with structured formatting
    return enhanceBlocks(baseBlocks, source, filename);
  },
};
