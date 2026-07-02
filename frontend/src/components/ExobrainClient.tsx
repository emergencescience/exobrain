"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import "katex/dist/katex.min.css";

// ── Types ──────────────────────────────────────────────────────────

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ExobrainState {
  messages: Message[];
  documentMarkdown: string;
  comments: Record<number, string[]>;
}

// ── Built-in i18n (no external dict dependency for standalone) ───

const STRINGS = {
  en: {
    play_title: "Exobrain",
    model_label: "LLM",
    copy_btn: "📋 Copy",
    download_btn: "⬇ .md",
    clear_btn: "🗑 Clear",
    clear_confirm: "Clear all messages and reset the document?",
    send_btn: "Send",
    input_placeholder: "Type a message... (Ctrl+Enter to send)",
    lines_label: "lines",
    chars_label: "chars",
    format_label: "Markdown + LaTeX",
    empty_title: "Exobrain",
    empty_desc: "Your AI STEM co-pilot. Chat to build your paper.",
    comment_placeholder: "Add a comment...",
    add_comment_btn: "Add",
    error_prefix: "❌ Error: ",
    error_default: "Failed to reach Exobrain. Please try again.",
    doc_updated_note: "📄 Document updated in the preview panel.",
    suggestions: [
      "Write an introduction for a paper on Riemann zeta function",
      "Derive the quadratic formula step by step",
      "Explain the Central Limit Theorem with LaTeX equations",
      "Create a proof outline for the Pythagorean theorem",
    ],
    default_document_title: "Untitled Paper",
    default_intro_heading: "Introduction",
    default_intro_text: "Start typing or chatting with Exobrain to build your paper.",
    default_eq_heading: "Equations",
  },
  zh: {
    play_title: "Exobrain 论文工坊",
    model_label: "LLM",
    copy_btn: "📋 复制",
    download_btn: "⬇ .md",
    clear_btn: "🗑 清空",
    clear_confirm: "确定清空所有对话并重置文档？",
    send_btn: "发送",
    input_placeholder: "输入消息...（Ctrl+Enter 发送）",
    lines_label: "行",
    chars_label: "字",
    format_label: "Markdown + LaTeX",
    empty_title: "Exobrain",
    empty_desc: "你的 AI STEM 协作者。用聊天构建你的论文。",
    comment_placeholder: "添加评论...",
    add_comment_btn: "添加",
    error_prefix: "❌ 错误：",
    error_default: "无法连接 Exobrain，请重试。",
    doc_updated_note: "📄 文档已在右侧预览面板更新。",
    suggestions: [
      "撰写一篇关于黎曼 zeta 函数的论文引言",
      "逐步推导二次公式",
      "用 LaTeX 方程解释中心极限定理",
      "创建毕达哥拉斯定理的证明大纲",
    ],
    default_document_title: "未命名论文",
    default_intro_heading: "引言",
    default_intro_text: "开始输入或与 Exobrain 对话来构建你的论文。",
    default_eq_heading: "方程式",
  },
};

// ── Props ───────────────────────────────────────────────────────────

interface Props {
  lang?: "en" | "zh";
  apiBaseUrl?: string; // defaults to "http://localhost:8080"
}

// ── Default document builder ────────────────────────────────────

function buildDefaultDocument(dict: typeof STRINGS.en): string {
  return `# ${dict.default_document_title}

## ${dict.default_intro_heading}

${dict.default_intro_text}

## ${dict.default_eq_heading}

Inline math: $E = mc^2$

Block math:

$$\\int_{0}^{\\infty} e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$$

`;
}

const STORAGE_KEY = "exobrain_play_state";

// ── Helpers ─────────────────────────────────────────────────────────

function stripMarkdownBlock(content: string): string {
  return content.replace(/```markdown\n[\s\S]*?\n```/g, "").trim();
}

function loadState(dict: typeof STRINGS.en): ExobrainState {
  if (typeof window === "undefined") {
    return { messages: [], documentMarkdown: buildDefaultDocument(dict), comments: {} };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        messages: parsed.messages || [],
        documentMarkdown: parsed.documentMarkdown || buildDefaultDocument(dict),
        comments: parsed.comments || {},
      };
    }
  } catch {
    // corrupted — reset
  }
  return { messages: [], documentMarkdown: buildDefaultDocument(dict), comments: {} };
}

function saveState(state: ExobrainState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // quota exceeded — silently ignore
  }
}

function splitParagraphs(md: string): { idx: number; text: string }[] {
  const raw = md.split("\n\n");
  return raw.map((text, idx) => ({ idx, text: text.trim() })).filter((p) => p.text.length > 0);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const MARKDOWN_COMPONENTS: any = {
  p: ({ children }: any) => <p className="my-1 text-sm text-white/80">{children}</p>,
  h1: ({ children }: any) => <h1 className="text-xl font-bold text-white/90 mt-4 mb-2">{children}</h1>,
  h2: ({ children }: any) => <h2 className="text-lg font-semibold text-white/80 mt-3 mb-1">{children}</h2>,
  h3: ({ children }: any) => <h3 className="text-base font-medium text-white/70 mt-2 mb-1">{children}</h3>,
  code: ({ children, className }: any) => {
    const isInline = !className;
    return isInline ? (
      <code className="bg-white/10 px-1 rounded text-xs text-cyan-300">{children}</code>
    ) : (
      <pre className="bg-white/5 border border-white/10 rounded p-3 my-2 overflow-x-auto">
        <code className="text-xs text-cyan-300">{children}</code>
      </pre>
    );
  },
  ul: ({ children }: any) => <ul className="list-disc list-inside my-1 text-sm text-white/70">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal list-inside my-1 text-sm text-white/70">{children}</ol>,
  blockquote: ({ children }: any) => (
    <blockquote className="border-l-2 border-purple-400/50 pl-3 my-1 text-sm text-white/50 italic">{children}</blockquote>
  ),
};

const remarkPlugins = [remarkMath];
const rehypePlugins = [rehypeKatex, rehypeRaw];

// ── Component ───────────────────────────────────────────────────────

export default function ExobrainClient({ lang = "en", apiBaseUrl = "http://localhost:8080" }: Props) {
  const dict = STRINGS[lang] || STRINGS.en;
  const [state, setState] = useState<ExobrainState>(() => loadState(dict));
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [hoveredPara, setHoveredPara] = useState<number | null>(null);
  const [commentingPara, setCommentingPara] = useState<number | null>(null);
  const [commentText, setCommentText] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const currentDefault = buildDefaultDocument(dict);
    setState((prev) => {
      if (prev.documentMarkdown.includes("Untitled Paper") || prev.documentMarkdown.includes("未命名论文")) {
        return { ...prev, documentMarkdown: currentDefault };
      }
      return prev;
    });
  }, [lang]);

  const { messages, documentMarkdown, comments } = state;

  const updateState = useCallback((patch: Partial<ExobrainState>) => {
    setState((prev) => {
      const next = { ...prev, ...patch };
      saveState(next);
      return next;
    });
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const paragraphs = useMemo(() => splitParagraphs(documentMarkdown), [documentMarkdown]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
  };

  const sendMessage = async (suggestionId?: string, presetText?: string) => {
    const text = presetText || input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    updateState({ messages: newMessages });
    if (!presetText) setInput("");
    setLoading(true);

    try {
      const body: Record<string, unknown> = {
        messages: newMessages.map((m) => ({ role: m.role, content: m.content })),
        document: documentMarkdown,
        comments: Object.keys(comments).length > 0 ? comments : undefined,
      };
      if (suggestionId) body.suggestion_id = suggestionId;

      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      const reply = data.reply || dict.error_default;
      let updatedDoc = data.document || undefined;
      if (!updatedDoc) {
        const mdMatch = reply.match(/```markdown\n([\s\S]*?)\n```/);
        updatedDoc = mdMatch ? mdMatch[1].trim() : undefined;
      }

      const assistantMsg: Message = { role: "assistant", content: reply };
      const patch: Partial<ExobrainState> = { messages: [...newMessages, assistantMsg] };
      if (updatedDoc) {
        patch.documentMarkdown = updatedDoc;
        patch.comments = {};
      }
      updateState(patch);
    } catch (err) {
      updateState({
        messages: [
          ...newMessages,
          { role: "assistant", content: `${dict.error_prefix}${err instanceof Error ? err.message : dict.error_default}` },
        ],
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      sendMessage();
    }
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(documentMarkdown);
    } catch {}
  };

  const downloadMarkdown = () => {
    const blob = new Blob([documentMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "paper.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  const clearSession = () => {
    if (confirm(dict.clear_confirm)) {
      const fresh = { messages: [], documentMarkdown: buildDefaultDocument(dict), comments: {} };
      setState(fresh);
      saveState(fresh);
    }
  };

  const addComment = (paraIdx: number) => {
    if (!commentText.trim()) {
      setCommentingPara(null);
      return;
    }
    const updated = { ...comments };
    if (!updated[paraIdx]) updated[paraIdx] = [];
    updated[paraIdx] = [...updated[paraIdx], commentText.trim()];
    updateState({ comments: updated });
    setCommentText("");
    setCommentingPara(null);
  };

  return (
    <div className="flex flex-col h-screen bg-black text-white overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-white/10 bg-black/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent">
            {dict.play_title}
          </span>
          <span className="text-xs text-white/40 hidden sm:inline">{dict.model_label}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSource(!showSource)}
            className={`px-3 py-1 text-xs rounded border transition-colors ${
              showSource ? "border-purple-400/50 text-purple-300 bg-purple-500/10" : "border-white/20 hover:border-purple-400/50 hover:text-purple-300"
            }`}
          >
            {showSource ? "👁 Preview" : "📄 Source"}
          </button>
          <button onClick={copyToClipboard} className="px-3 py-1 text-xs rounded border border-white/20 hover:border-purple-400/50 hover:text-purple-300 transition-colors">
            {dict.copy_btn}
          </button>
          <button onClick={downloadMarkdown} className="px-3 py-1 text-xs rounded border border-white/20 hover:border-cyan-400/50 hover:text-cyan-300 transition-colors">
            {dict.download_btn}
          </button>
          <button onClick={clearSession} className="px-3 py-1 text-xs rounded border border-white/20 hover:border-red-400/50 hover:text-red-300 transition-colors">
            {dict.clear_btn}
          </button>
        </div>
      </header>

      {/* Main Panels */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Chat (45%) */}
        <div className="w-[45%] min-w-[300px] flex flex-col border-r border-white/10">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-white/30 mt-20">
                <p className="text-4xl mb-4">🧠</p>
                <p className="text-lg font-medium text-white/50">{dict.empty_title}</p>
                <p className="text-sm mt-2">{dict.empty_desc}</p>
                <div className="mt-6 grid grid-cols-1 gap-2 max-w-xs mx-auto">
                  {dict.suggestions.map((hint, idx) => {
                    const ids = ["riemann_intro", "quadratic_derivation", "clt_explanation", "pythagorean_proof"];
                    return (
                      <button
                        key={hint}
                        onClick={() => sendMessage(ids[idx], hint)}
                        className="text-left text-xs px-3 py-2 rounded border border-white/10 hover:border-purple-400/30 text-white/40 hover:text-white/70 transition-colors truncate"
                      >
                        {hint}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {messages.map((msg, i) => {
              const displayContent = msg.role === "assistant" ? stripMarkdownBlock(msg.content) : msg.content;
              const hadDocBlock = msg.role === "assistant" && displayContent.length < msg.content.length;
              return (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-lg px-4 py-2 text-sm ${
                      msg.role === "user"
                        ? "bg-purple-600/30 text-purple-100 border border-purple-500/20"
                        : "bg-white/5 text-white/80 border border-white/10"
                    }`}
                  >
                    {msg.role === "assistant" ? (
                      <div>
                        <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>
                          {displayContent}
                        </ReactMarkdown>
                        {hadDocBlock && <p className="mt-2 text-xs text-purple-400/70 italic">{dict.doc_updated_note}</p>}
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm text-white/50">
                  <span className="inline-flex gap-1">
                    <span className="animate-bounce">●</span>
                    <span className="animate-bounce" style={{ animationDelay: "0.1s" }}>●</span>
                    <span className="animate-bounce" style={{ animationDelay: "0.2s" }}>●</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-white/10">
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={dict.input_placeholder}
                rows={1}
                disabled={loading}
                className="flex-1 bg-white/5 border border-white/20 rounded-lg px-3 py-2 text-sm text-white/90 placeholder:text-white/30 focus:outline-none focus:border-purple-400/50 resize-none disabled:opacity-50"
              />
              <button
                onClick={() => sendMessage()}
                disabled={loading || !input.trim()}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-cyan-500 text-white text-sm font-medium hover:from-purple-400 hover:to-cyan-400 disabled:opacity-30 disabled:cursor-not-allowed transition-all shrink-0"
              >
                {dict.send_btn}
              </button>
            </div>
          </div>
        </div>

        {/* Right: Preview (55%) */}
        <div className="w-[55%] flex flex-col bg-[#0a0a0a]">
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-2xl mx-auto">
              {showSource ? (
                <pre className="text-xs text-white/60 font-mono whitespace-pre-wrap leading-relaxed bg-white/[0.02] rounded p-4 border border-white/5">
                  {documentMarkdown}
                </pre>
              ) : (
                paragraphs.map((para) => {
                  const hasComments = comments[para.idx]?.length > 0;
                  const isHovered = hoveredPara === para.idx;
                  const isCommenting = commentingPara === para.idx;
                  return (
                    <div
                      key={para.idx}
                      className="relative group"
                      onMouseEnter={() => setHoveredPara(para.idx)}
                      onMouseLeave={() => { if (hoveredPara === para.idx) setHoveredPara(null); }}
                    >
                      <div
                        className={`transition-colors rounded ${isHovered ? "bg-white/[0.03]" : ""} ${hasComments ? "border-l-2 border-yellow-500/50 pl-3" : ""}`}
                      >
                        <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins} components={MARKDOWN_COMPONENTS}>
                          {para.text}
                        </ReactMarkdown>
                      </div>
                      {isHovered && (
                        <div className="absolute -right-2 top-0 translate-x-full flex gap-1 z-10">
                          <button onClick={() => setCommentingPara(para.idx)} className="px-2 py-0.5 text-[10px] rounded bg-white/10 border border-white/20 text-white/60 hover:bg-purple-500/30 hover:text-purple-200 whitespace-nowrap">
                            💬
                          </button>
                        </div>
                      )}
                      {(isCommenting || hasComments) && (
                        <div className="ml-4 my-1 pl-3 border-l border-yellow-500/30">
                          {hasComments && comments[para.idx].map((c, ci) => (
                            <div key={ci} className="text-[11px] text-yellow-300/70 py-0.5">💬 {c}</div>
                          ))}
                          {isCommenting && (
                            <div className="flex gap-1 mt-1">
                              <input
                                autoFocus
                                value={commentText}
                                onChange={(e) => setCommentText(e.target.value)}
                                onKeyDown={(e) => { if (e.key === "Enter") addComment(para.idx); if (e.key === "Escape") setCommentingPara(null); }}
                                placeholder={dict.comment_placeholder}
                                className="flex-1 bg-white/10 border border-white/20 rounded px-2 py-0.5 text-[11px] text-white/80 placeholder:text-white/30 focus:outline-none focus:border-yellow-400/50"
                              />
                              <button onClick={() => addComment(para.idx)} className="px-2 py-0.5 text-[10px] rounded bg-yellow-500/20 border border-yellow-500/30 text-yellow-300 hover:bg-yellow-500/30">
                                {dict.add_comment_btn}
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
          <div className="px-4 py-1 border-t border-white/10 text-[10px] text-white/30 flex justify-between shrink-0">
            <span>{documentMarkdown.split("\n").length} {dict.lines_label}</span>
            <span>{documentMarkdown.length} {dict.chars_label}</span>
            <span>{dict.format_label}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
