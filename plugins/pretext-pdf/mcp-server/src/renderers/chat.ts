/**
 * Chat Renderer — Converts DojoChat conversation exports into PdfBlocks.
 *
 * Uses Pretext shrink-wrap for bubble sizing and supports
 * disposition-driven typography (ADA personality → font settings).
 *
 * Expected input format (JSON):
 * {
 *   "messages": [
 *     {
 *       "role": "user" | "assistant",
 *       "content": "message text",
 *       "timestamp": "ISO 8601",
 *       "disposition"?: { tone, verbosity, depth, brevity }
 *     }
 *   ],
 *   "metadata"?: { title, participants, created }
 * }
 */

import type { PdfBlock, Renderer } from "./types.js";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  disposition?: {
    tone?: "formal" | "casual" | "technical" | "warm";
    verbosity?: "terse" | "balanced" | "verbose";
    depth?: "surface" | "moderate" | "deep";
    brevity?: "minimal" | "standard" | "expansive";
  };
}

interface ChatExport {
  messages: ChatMessage[];
  metadata?: {
    title?: string;
    participants?: string[];
    created?: string;
  };
}

/**
 * Map disposition traits to typography hints.
 * The PDF generator uses these to select font variants.
 */
function dispositionToTypographyHints(
  disposition?: ChatMessage["disposition"]
): Record<string, unknown> {
  if (!disposition) return {};

  return {
    fontWeight:
      disposition.tone === "formal"
        ? 400
        : disposition.tone === "casual"
          ? 350
          : 400,
    fontSize:
      disposition.verbosity === "verbose"
        ? 10
        : disposition.verbosity === "terse"
          ? 12
          : 11,
    lineHeight:
      disposition.depth === "deep"
        ? 1.4
        : disposition.depth === "surface"
          ? 1.6
          : 1.5,
    maxBubbleWidth:
      disposition.brevity === "minimal"
        ? 300
        : disposition.brevity === "expansive"
          ? 450
          : 380,
    casualAxis: disposition.tone === "casual" ? 0.5 : 0,
  };
}

export const chatRenderer: Renderer = {
  name: "chat",
  extensions: [".chat.json", ".conversation.json"],

  async parse(source: string, filename: string): Promise<PdfBlock[]> {
    let chat: ChatExport;
    try {
      chat = JSON.parse(source) as ChatExport;
    } catch {
      throw new Error(`Invalid chat JSON in ${filename}`);
    }

    if (!chat.messages || !Array.isArray(chat.messages)) {
      throw new Error(`Chat export missing 'messages' array in ${filename}`);
    }

    const blocks: PdfBlock[] = [];

    // Conversation header
    if (chat.metadata?.title) {
      blocks.push({
        type: "heading",
        content: chat.metadata.title,
        metadata: { level: 1 },
      });
    }

    if (chat.metadata?.created) {
      blocks.push({
        type: "text",
        content: new Date(chat.metadata.created).toLocaleDateString("en-US", {
          weekday: "long",
          year: "numeric",
          month: "long",
          day: "numeric",
        }),
        metadata: { subtitle: true, muted: true },
      });
    }

    if (chat.metadata?.participants?.length) {
      blocks.push({
        type: "text",
        content: `Participants: ${chat.metadata.participants.join(", ")}`,
        metadata: { muted: true },
      });
    }

    blocks.push({ type: "rule", content: "" });

    // Messages
    for (const msg of chat.messages) {
      const typographyHints = dispositionToTypographyHints(msg.disposition);

      blocks.push({
        type: "text",
        content: msg.content,
        metadata: {
          chatBubble: true,
          role: msg.role,
          timestamp: msg.timestamp,
          alignment: msg.role === "user" ? "right" : "left",
          shrinkWrap: true,
          ...typographyHints,
        },
      });
    }

    return blocks;
  },
};
