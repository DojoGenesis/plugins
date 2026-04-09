#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { exportToPdf } from "./tools/export-pdf.js";

const server = new McpServer({
  name: "pretext-pdf",
  version: "0.1.0",
});

// --- Tools ---

server.tool(
  "export",
  "Export one or more files to a Pretext-typeset PDF. Supports code (syntax-highlighted), Markdown, HTML, chat conversations, and structured Dojo files.",
  {
    files: z
      .array(z.string())
      .describe("Absolute file paths to export"),
    output: z
      .string()
      .optional()
      .describe("Output PDF path. Defaults to ./exports/<filename>.pdf"),
    bundle: z
      .boolean()
      .optional()
      .default(false)
      .describe("Combine multiple files into a single PDF"),
    renderer: z
      .enum(["auto", "code", "markdown", "html", "chat", "structured"])
      .optional()
      .default("auto")
      .describe("Force a specific renderer. Default: auto-detect from extension"),
    theme: z
      .enum(["light", "dark"])
      .optional()
      .default("light")
      .describe("Color theme for syntax highlighting"),
    fontSize: z
      .number()
      .min(6)
      .max(24)
      .optional()
      .default(11)
      .describe("Body font size in points"),
    lineHeight: z
      .number()
      .min(1.0)
      .max(3.0)
      .optional()
      .default(1.5)
      .describe("Line height multiplier"),
    pageSize: z
      .enum(["letter", "a4", "legal"])
      .optional()
      .default("letter")
      .describe("Page dimensions"),
    lineNumbers: z
      .boolean()
      .optional()
      .default(false)
      .describe("Show line numbers in code exports"),
    toc: z
      .boolean()
      .optional()
      .default(false)
      .describe("Generate table of contents"),
    dispositionTypography: z
      .boolean()
      .optional()
      .default(false)
      .describe("Use ADA disposition mapping for chat exports"),
  },
  async (params) => {
    try {
      const result = await exportToPdf(params);
      return {
        content: [
          {
            type: "text" as const,
            text: result.summary,
          },
        ],
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: "text" as const,
            text: `PDF export failed: ${message}`,
          },
        ],
        isError: true,
      };
    }
  }
);

server.tool(
  "configure-typography",
  "Get or set typography configuration for PDF export. Returns current config if no parameters provided.",
  {
    fontFamily: z
      .enum(["inter", "recursive", "fraunces"])
      .optional()
      .describe("Primary body font family"),
    codeFontFamily: z
      .enum(["recursive-mono", "recursive-casual"])
      .optional()
      .describe("Code font family variant"),
    fontSize: z.number().min(6).max(24).optional(),
    lineHeight: z.number().min(1.0).max(3.0).optional(),
    pageSize: z.enum(["letter", "a4", "legal"]).optional(),
    margins: z
      .object({
        top: z.number().optional(),
        right: z.number().optional(),
        bottom: z.number().optional(),
        left: z.number().optional(),
      })
      .optional()
      .describe("Page margins in points"),
  },
  async (params) => {
    // Returns current config merged with any overrides
    const config = {
      fontFamily: params.fontFamily ?? "inter",
      codeFontFamily: params.codeFontFamily ?? "recursive-mono",
      fontSize: params.fontSize ?? 11,
      lineHeight: params.lineHeight ?? 1.5,
      pageSize: params.pageSize ?? "letter",
      margins: {
        top: params.margins?.top ?? 72,
        right: params.margins?.right ?? 72,
        bottom: params.margins?.bottom ?? 72,
        left: params.margins?.left ?? 72,
      },
    };

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(config, null, 2),
        },
      ],
    };
  }
);

// --- Start ---

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error("Fatal:", error);
  process.exit(1);
});
