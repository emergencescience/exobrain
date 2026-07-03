/// <reference types="vite/client" />

/** Persistent config — saved to localStorage on mobile. */

export interface AppConfig {
  /** "self" = user's own API key, "saas" = emergence.science API */
  mode: "self" | "saas";
  /** Only used in self-hosted mode */
  apiKey: string;
  /** LLM base URL (defaults to DeepSeek) */
  baseUrl: string;
  /** Model name */
  model: string;
  /** Emergence API key (for SaaS mode) */
  emergenceApiKey: string;
  /** Theme: dark or light */
  theme: "dark" | "light";
  /** Whether setup is complete */
  setupDone: boolean;
}

const DEFAULTS: AppConfig = {
  mode: "self",
  apiKey: "",
  emergenceApiKey: "",
  baseUrl: "https://api.deepseek.com",
  model: "deepseek-v4-flash",
  theme: "dark",
  setupDone: false,
};

const STORE_KEY = "exobrain_config";

export function loadConfig(): AppConfig {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {}
  return { ...DEFAULTS };
}

export function saveConfig(cfg: AppConfig): void {
  localStorage.setItem(STORE_KEY, JSON.stringify(cfg));
}

/** Build chat completion URL based on mode. */
export function getChatEndpoint(cfg: AppConfig): string {
  if (cfg.mode === "saas") {
    return "https://api.emergence.science/api/play/exobrain/chat";
  }
  return `${cfg.baseUrl}/v1/chat/completions`;
}

/** Build headers for API calls. */
export function getChatHeaders(cfg: AppConfig): Record<string, string> {
  if (cfg.mode === "saas") {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (cfg.emergenceApiKey) {
      headers["Authorization"] = `Bearer ${cfg.emergenceApiKey}`;
    }
    return headers;
  }
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${cfg.apiKey}`,
  };
}

/** Build chat request body. */
export function buildChatBody(
  cfg: AppConfig,
  messages: { role: string; content: string }[],
  document?: string,
  comments?: Record<number, string[]>
) {
  if (cfg.mode === "saas") {
    const body: Record<string, unknown> = {
      messages,
      model: cfg.model,
      document,
      comments: comments && Object.keys(comments).length > 0 ? comments : undefined,
    };
    return body;
  }
  // Self-hosted: standard OpenAI-compatible format
  const systemMsg: { role: string; content: string } = {
    role: "system",
    content:
      "You are Exobrain, a formal mathematics co-pilot. " +
      "Help the user draft, verify, and refine mathematical documents. " +
      "Output in clean Markdown with LaTeX math using $...$ for inline and $$...$$ for blocks. " +
      "When the user asks you to update the document, output the full updated document in a " +
      "```markdown\n...\n``` code block at the end of your response. " +
      "Be precise about mathematical notation — use proper LaTeX syntax. " +
      "Reply in the same language as the user's last message.",
  };

  const withSystem = [systemMsg, ...messages];

  // Append document context
  const allMessages = [...withSystem];
  if (document) {
    let ctx = `Current document:\n\`\`\`markdown\n${document}\n\`\`\``;
    if (comments && Object.keys(comments).length > 0) {
      const lines: string[] = [];
      for (const [idx, cmts] of Object.entries(comments)) {
        for (const c of cmts) lines.push(`- Line ${idx}: ${c}`);
      }
      ctx += "\n\nActive comments:\n" + lines.join("\n");
    }
    allMessages.push({ role: "user", content: ctx });
  }

  return {
    model: cfg.model,
    messages: allMessages,
    temperature: 0.7,
    max_tokens: 8192,
  };
}

/** Parse response based on mode. */
export function parseChatResponse(
  cfg: AppConfig,
  data: Record<string, unknown>
): { reply: string; document?: string } {
  if (cfg.mode === "saas") {
    return {
      reply: (data.reply as string) || "",
      document: data.document as string | undefined,
    };
  }
  // OpenAI-compatible format
  const choices = data.choices as Array<{ message: { content: string } }>;
  const reply = choices?.[0]?.message?.content?.trim() || "";
  const mdMatch = reply.match(/```markdown\n([\s\S]*?)\n```/);
  return {
    reply,
    document: mdMatch ? mdMatch[1].trim() : undefined,
  };
}
