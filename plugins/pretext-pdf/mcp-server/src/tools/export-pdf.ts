/**
 * Export-PDF Tool — Orchestrates the full pipeline:
 * file reading → renderer selection → Pretext measurement → PDF generation.
 *
 * Uses pdf-lib for PDF construction and Pretext for text measurement.
 */

import { readFile, mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { basename, dirname, extname, join, resolve } from "node:path";
import { PDFDocument, PDFFont, PDFPage, rgb, StandardFonts } from "pdf-lib";

import { selectRenderer, PAGE_SIZES } from "../renderers/index.js";
import type { PdfBlock, PageDimensions } from "../renderers/types.js";
import {
  measureText,
  shrinkWrap,
  createConfig,
  type TypographyConfig,
} from "../typography/pretext-bridge.js";
import {
  loadFonts,
  fontDescriptor,
  headingFont,
  type FontStack,
} from "../typography/fonts.js";

export interface ExportParams {
  files: string[];
  output?: string;
  bundle?: boolean;
  renderer?: "auto" | "code" | "markdown" | "html" | "chat" | "structured";
  theme?: "light" | "dark";
  fontSize?: number;
  lineHeight?: number;
  pageSize?: "letter" | "a4" | "legal";
  lineNumbers?: boolean;
  toc?: boolean;
  dispositionTypography?: boolean;
}

export interface ExportResult {
  summary: string;
  outputPath: string;
  pages: number;
  bytes: number;
}

/**
 * Theme color palettes.
 */
const THEMES = {
  light: {
    background: rgb(1, 1, 1),
    text: rgb(0.1, 0.1, 0.1),
    heading: rgb(0.05, 0.05, 0.15),
    muted: rgb(0.45, 0.45, 0.5),
    codeBackground: rgb(0.96, 0.96, 0.97),
    codeBorder: rgb(0.85, 0.85, 0.88),
    rule: rgb(0.8, 0.8, 0.82),
    link: rgb(0.15, 0.35, 0.65),
    bubbleUser: rgb(0.92, 0.94, 1.0),
    bubbleAssistant: rgb(0.96, 0.96, 0.96),
    badge: rgb(0.2, 0.4, 0.7),
  },
  dark: {
    background: rgb(0.12, 0.12, 0.14),
    text: rgb(0.88, 0.88, 0.9),
    heading: rgb(0.92, 0.92, 0.95),
    muted: rgb(0.55, 0.55, 0.6),
    codeBackground: rgb(0.16, 0.16, 0.18),
    codeBorder: rgb(0.25, 0.25, 0.28),
    rule: rgb(0.25, 0.25, 0.28),
    link: rgb(0.4, 0.6, 0.9),
    bubbleUser: rgb(0.18, 0.22, 0.32),
    bubbleAssistant: rgb(0.18, 0.18, 0.2),
    badge: rgb(0.3, 0.5, 0.8),
  },
};

export async function exportToPdf(params: ExportParams): Promise<ExportResult> {
  const {
    files,
    bundle = false,
    renderer: rendererName = "auto",
    theme: themeName = "light",
    fontSize = 11,
    lineHeight = 1.5,
    pageSize: pageSizeName = "letter",
    lineNumbers = false,
    toc = false,
  } = params;

  if (!files.length) {
    throw new Error("No files specified for export");
  }

  // Resolve file paths
  const resolvedFiles = files.map((f) => resolve(f));

  // Validate files exist
  for (const file of resolvedFiles) {
    if (!existsSync(file)) {
      throw new Error(`File not found: ${file}`);
    }
  }

  // Load fonts and typography config
  const fonts = loadFonts();
  const typographyConfig = createConfig({ fontSize, lineHeight });
  const theme = THEMES[themeName];
  const pageSize = PAGE_SIZES[pageSizeName];
  const margins = { top: 72, right: 72, bottom: 72, left: 72 };
  const contentWidth = pageSize.width - margins.left - margins.right;
  const contentHeight = pageSize.height - margins.top - margins.bottom;

  // Parse all files into blocks
  const allBlocks: Array<{ filename: string; blocks: PdfBlock[] }> = [];

  for (const file of resolvedFiles) {
    const source = await readFile(file, "utf-8");
    const selectedRenderer = selectRenderer(file, source, rendererName);
    const blocks = await selectedRenderer.parse(source, file);
    allBlocks.push({ filename: file, blocks });
  }

  // Create PDF document
  const pdf = await PDFDocument.create();
  pdf.setTitle(
    bundle
      ? `Export — ${allBlocks.length} files`
      : basename(resolvedFiles[0], extname(resolvedFiles[0]))
  );
  pdf.setProducer("Pretext PDF by Dojo Genesis");
  pdf.setCreator("pretext-pdf MCP server v0.1.0");
  pdf.setCreationDate(new Date());

  // Embed standard fonts as fallback
  // (Variable fonts via Pretext measurement; standard fonts for PDF text rendering)
  const helvetica = await pdf.embedFont(StandardFonts.Helvetica);
  const helveticaBold = await pdf.embedFont(StandardFonts.HelveticaBold);
  const courier = await pdf.embedFont(StandardFonts.Courier);

  let totalPages = 0;

  // Generate table of contents if requested
  const tocEntries: Array<{ title: string; page: number; level: number }> = [];

  for (const { filename, blocks } of allBlocks) {
    // If not bundling, or at the start of each file in a bundle, add file separator
    if (bundle && allBlocks.length > 1) {
      tocEntries.push({
        title: basename(filename),
        page: totalPages + 1,
        level: 1,
      });
    }

    // Render blocks to PDF pages
    let page = addPage(pdf, pageSize, margins, theme);
    let y = pageSize.height - margins.top;
    totalPages++;

    for (const block of blocks) {
      const spaceNeeded = estimateBlockHeight(
        block,
        fontSize,
        lineHeight,
        contentWidth,
        helvetica,
        courier
      );

      // Page break if needed
      if (y - spaceNeeded < margins.bottom) {
        addFooter(page, totalPages, helvetica, pageSize, margins, theme);
        page = addPage(pdf, pageSize, margins, theme);
        y = pageSize.height - margins.top;
        totalPages++;
      }

      y = renderBlock(
        page,
        block,
        y,
        margins,
        contentWidth,
        fontSize,
        lineHeight,
        lineNumbers,
        helvetica,
        helveticaBold,
        courier,
        theme
      );
    }

    // Add footer to last page
    addFooter(page, totalPages, helvetica, pageSize, margins, theme);
  }

  // Insert TOC page at the beginning if requested
  if (toc && tocEntries.length > 1) {
    // TOC generation would insert pages at index 0
    // For now, we add a TOC note — full TOC with page refs requires a second pass
    const tocPage = pdf.insertPage(0, [pageSize.width, pageSize.height]);
    let tocY = pageSize.height - margins.top;

    tocPage.drawText("Table of Contents", {
      x: margins.left,
      y: tocY,
      size: 18,
      font: helveticaBold,
      color: theme.heading,
    });
    tocY -= 36;

    for (const entry of tocEntries) {
      const indent = (entry.level - 1) * 20;
      tocPage.drawText(`${entry.title}  ·····  ${entry.page + 1}`, {
        x: margins.left + indent,
        y: tocY,
        size: 10,
        font: helvetica,
        color: theme.text,
      });
      tocY -= 18;
    }

    totalPages++;
  }

  // Serialize PDF
  const pdfBytes = await pdf.save();

  // Determine output path
  const outputPath = resolveOutputPath(params.output, resolvedFiles, bundle);
  const outputDir = dirname(outputPath);
  if (!existsSync(outputDir)) {
    await mkdir(outputDir, { recursive: true });
  }
  await writeFile(outputPath, pdfBytes);

  return {
    summary: `Exported ${resolvedFiles.length} file(s) → ${outputPath} (${totalPages} pages, ${formatBytes(pdfBytes.length)})`,
    outputPath,
    pages: totalPages,
    bytes: pdfBytes.length,
  };
}

// --- Helpers ---

function addPage(
  pdf: PDFDocument,
  pageSize: { width: number; height: number },
  margins: { top: number; right: number; bottom: number; left: number },
  theme: (typeof THEMES)["light"]
): PDFPage {
  const page = pdf.addPage([pageSize.width, pageSize.height]);

  // Fill background for dark theme
  if (theme === THEMES.dark) {
    page.drawRectangle({
      x: 0,
      y: 0,
      width: pageSize.width,
      height: pageSize.height,
      color: theme.background,
    });
  }

  return page;
}

function addFooter(
  page: PDFPage,
  pageNumber: number,
  font: PDFFont,
  pageSize: { width: number; height: number },
  margins: { top: number; right: number; bottom: number; left: number },
  theme: (typeof THEMES)["light"]
): void {
  const text = `${pageNumber}`;
  const width = font.widthOfTextAtSize(text, 8);
  page.drawText(text, {
    x: pageSize.width / 2 - width / 2,
    y: margins.bottom / 2,
    size: 8,
    font,
    color: theme.muted,
  });
}

function estimateBlockHeight(
  block: PdfBlock,
  fontSize: number,
  lineHeight: number,
  contentWidth: number,
  bodyFont: PDFFont,
  codeFont: PDFFont
): number {
  const lineSize = fontSize * lineHeight;

  switch (block.type) {
    case "heading": {
      const level = (block.metadata?.level as number) ?? 2;
      const scale = [2.0, 1.5, 1.25, 1.1, 1.0, 0.875][level - 1] ?? 1;
      return fontSize * scale * lineHeight + 12; // + spacing
    }
    case "text": {
      const charWidth = bodyFont.widthOfTextAtSize("m", fontSize);
      const charsPerLine = Math.floor(contentWidth / charWidth);
      const lines = Math.ceil(block.content.length / charsPerLine);
      return Math.max(lines, 1) * lineSize + 8;
    }
    case "code": {
      const codeLines = block.content.split("\n").length;
      const codeLineSize = (fontSize - 1.5) * 1.35;
      return codeLines * codeLineSize + 24; // + padding
    }
    case "rule":
      return 20;
    case "pagebreak":
      return Infinity; // Forces a page break
    case "table": {
      const rows =
        ((block.metadata?.rows as string[][])?.length ?? 0) + 1; // +1 for header
      return rows * lineSize + 16;
    }
    default:
      return lineSize;
  }
}

function renderBlock(
  page: PDFPage,
  block: PdfBlock,
  y: number,
  margins: { top: number; right: number; bottom: number; left: number },
  contentWidth: number,
  fontSize: number,
  lineHeight: number,
  lineNumbers: boolean,
  bodyFont: PDFFont,
  boldFont: PDFFont,
  codeFont: PDFFont,
  theme: (typeof THEMES)["light"]
): number {
  const x = margins.left;

  switch (block.type) {
    case "heading": {
      const level = (block.metadata?.level as number) ?? 2;
      const scale = [2.0, 1.5, 1.25, 1.1, 1.0, 0.875][level - 1] ?? 1;
      const headingSize = fontSize * scale;

      y -= headingSize + 8;
      page.drawText(block.content, {
        x,
        y,
        size: headingSize,
        font: boldFont,
        color: theme.heading,
        maxWidth: contentWidth,
      });
      y -= 4;
      return y;
    }

    case "text": {
      if (block.metadata?.badge) {
        // Render as a colored badge
        const badgeWidth = bodyFont.widthOfTextAtSize(block.content, 7) + 12;
        y -= 16;
        page.drawRectangle({
          x,
          y - 2,
          width: badgeWidth,
          height: 14,
          color: theme.badge,
          borderColor: theme.badge,
          borderWidth: 0,
        });
        page.drawText(block.content, {
          x: x + 6,
          y: y + 1,
          size: 7,
          font: boldFont,
          color: rgb(1, 1, 1),
        });
        y -= 8;
        return y;
      }

      if (block.metadata?.chatBubble) {
        return renderChatBubble(
          page,
          block,
          y,
          x,
          contentWidth,
          fontSize,
          lineHeight,
          bodyFont,
          theme
        );
      }

      const textColor = block.metadata?.muted ? theme.muted : theme.text;
      const indent = block.metadata?.blockquote ? 20 : 0;

      // Simple text wrapping using pdf-lib
      const effectiveWidth = contentWidth - indent;
      const lines = wrapText(block.content, bodyFont, fontSize, effectiveWidth);

      for (const line of lines) {
        y -= fontSize * lineHeight;
        if (block.metadata?.blockquote) {
          page.drawRectangle({
            x: x + 4,
            y: y - 2,
            width: 3,
            height: fontSize * lineHeight,
            color: theme.rule,
          });
        }
        page.drawText(line, {
          x: x + indent,
          y,
          size: fontSize,
          font: bodyFont,
          color: textColor,
          maxWidth: effectiveWidth,
        });
      }
      y -= 6;
      return y;
    }

    case "code": {
      const codeSize = fontSize - 1.5;
      const codeLineHeight = 1.35;
      const padding = 8;
      const codeLines = block.content.split("\n");
      const lineNumWidth = lineNumbers
        ? codeFont.widthOfTextAtSize(`${codeLines.length} `, codeSize) + 8
        : 0;
      const blockHeight =
        codeLines.length * codeSize * codeLineHeight + padding * 2;

      y -= 6;

      // Code background
      page.drawRectangle({
        x: x - 4,
        y: y - blockHeight,
        width: contentWidth + 8,
        height: blockHeight,
        color: theme.codeBackground,
        borderColor: theme.codeBorder,
        borderWidth: 0.5,
      });

      y -= padding;

      for (let i = 0; i < codeLines.length; i++) {
        y -= codeSize * codeLineHeight;

        if (lineNumbers) {
          page.drawText(`${i + 1}`, {
            x: x + 2,
            y,
            size: codeSize,
            font: codeFont,
            color: theme.muted,
          });
        }

        const codeLine = codeLines[i];
        if (codeLine.length > 0) {
          page.drawText(codeLine, {
            x: x + lineNumWidth + 4,
            y,
            size: codeSize,
            font: codeFont,
            color: theme.text,
            maxWidth: contentWidth - lineNumWidth - 8,
          });
        }
      }

      y -= padding + 6;
      return y;
    }

    case "rule": {
      y -= 10;
      page.drawLine({
        start: { x, y },
        end: { x: x + contentWidth, y },
        thickness: 0.5,
        color: theme.rule,
      });
      y -= 10;
      return y;
    }

    case "table": {
      const header = (block.metadata?.header as string[]) ?? [];
      const rows = (block.metadata?.rows as string[][]) ?? [];
      const colCount = header.length || (rows[0]?.length ?? 1);
      const colWidth = contentWidth / colCount;
      const rowHeight = fontSize * lineHeight + 4;

      // Header
      y -= rowHeight;
      page.drawRectangle({
        x: x - 2,
        y: y - 2,
        width: contentWidth + 4,
        height: rowHeight,
        color: theme.codeBackground,
      });
      for (let col = 0; col < header.length; col++) {
        page.drawText(header[col], {
          x: x + col * colWidth + 4,
          y: y + 2,
          size: fontSize - 1,
          font: boldFont,
          color: theme.heading,
          maxWidth: colWidth - 8,
        });
      }

      // Rows
      for (const row of rows) {
        y -= rowHeight;
        for (let col = 0; col < row.length; col++) {
          page.drawText(row[col], {
            x: x + col * colWidth + 4,
            y: y + 2,
            size: fontSize - 1,
            font: bodyFont,
            color: theme.text,
            maxWidth: colWidth - 8,
          });
        }
      }

      y -= 8;
      return y;
    }

    default:
      return y;
  }
}

function renderChatBubble(
  page: PDFPage,
  block: PdfBlock,
  y: number,
  x: number,
  contentWidth: number,
  fontSize: number,
  lineHeight: number,
  font: PDFFont,
  theme: (typeof THEMES)["light"]
): number {
  const role = block.metadata?.role as string;
  const isUser = role === "user";
  const maxBubbleWidth =
    (block.metadata?.maxBubbleWidth as number) ?? contentWidth * 0.7;
  const bubbleColor = isUser ? theme.bubbleUser : theme.bubbleAssistant;
  const padding = 12;

  const lines = wrapText(block.content, font, fontSize, maxBubbleWidth - padding * 2);
  const bubbleHeight = lines.length * fontSize * lineHeight + padding * 2;
  const longestLine = Math.max(
    ...lines.map((l) => font.widthOfTextAtSize(l, fontSize))
  );
  const bubbleWidth = Math.min(longestLine + padding * 2, maxBubbleWidth);

  y -= bubbleHeight + 8;

  const bubbleX = isUser ? x + contentWidth - bubbleWidth : x;

  // Bubble background
  page.drawRectangle({
    x: bubbleX,
    y,
    width: bubbleWidth,
    height: bubbleHeight,
    color: bubbleColor,
    borderWidth: 0,
  });

  // Bubble text
  let textY = y + bubbleHeight - padding - fontSize;
  for (const line of lines) {
    page.drawText(line, {
      x: bubbleX + padding,
      y: textY,
      size: fontSize,
      font,
      color: theme.text,
    });
    textY -= fontSize * lineHeight;
  }

  // Timestamp
  if (block.metadata?.timestamp) {
    const ts = new Date(block.metadata.timestamp as string).toLocaleTimeString(
      "en-US",
      { hour: "numeric", minute: "2-digit" }
    );
    const tsWidth = font.widthOfTextAtSize(ts, 7);
    page.drawText(ts, {
      x: isUser ? bubbleX + bubbleWidth - tsWidth - 4 : bubbleX + 4,
      y: y - 10,
      size: 7,
      font,
      color: theme.muted,
    });
    y -= 12;
  }

  return y;
}

function wrapText(
  text: string,
  font: PDFFont,
  size: number,
  maxWidth: number
): string[] {
  if (!text) return [""];

  const lines: string[] = [];
  const paragraphs = text.split("\n");

  for (const para of paragraphs) {
    if (!para.trim()) {
      lines.push("");
      continue;
    }

    const words = para.split(/\s+/);
    let currentLine = "";

    for (const word of words) {
      const testLine = currentLine ? `${currentLine} ${word}` : word;
      const testWidth = font.widthOfTextAtSize(testLine, size);

      if (testWidth > maxWidth && currentLine) {
        lines.push(currentLine);
        currentLine = word;
      } else {
        currentLine = testLine;
      }
    }

    if (currentLine) {
      lines.push(currentLine);
    }
  }

  return lines.length ? lines : [""];
}

function resolveOutputPath(
  explicit: string | undefined,
  inputFiles: string[],
  bundle: boolean
): string {
  if (explicit) return resolve(explicit);

  const cwd = process.cwd();
  const exportsDir = join(cwd, "exports");

  if (bundle) {
    return join(exportsDir, `export-${Date.now()}.pdf`);
  }

  const inputBase = basename(inputFiles[0], extname(inputFiles[0]));
  return join(exportsDir, `${inputBase}.pdf`);
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}
