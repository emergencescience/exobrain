import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import { AppConfig, loadConfig, getChatEndpoint, getChatHeaders, buildChatBody, parseChatResponse } from "../config";

// ── Types ──────────────────────────────────────────────────────────

interface Message { role: "user" | "assistant"; content: string }
interface ExobrainState {
  messages: Message[];
  documentMarkdown: string;
  comments: Record<number, string[]>;
}

// ── Defaults ────────────────────────────────────────────────────────

const DEFAULT_DOC = `# Untitled Paper

## Introduction

This is your mathematical paper. Start editing or chat with the AI to build it.

## Equations

Inline math: $E = mc^2$

Block math:

$$\\int_{0}^{\\infty} e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$$

`;

// ── Helpers ─────────────────────────────────────────────────────────

function stripMarkdownBlock(content: string): string {
  return content.replace(/```markdown\n[\s\S]*?\n```/g, "").trim();
}

function splitParagraphs(md: string): { idx: number; text: string }[] {
  return md.split("\n\n").map((text, idx) => ({ idx, text: text.trim() })).filter((p) => p.text.length > 0);
}

// ── Props ───────────────────────────────────────────────────────────

interface Props {
  onSettings: () => void;
}

const MARKDOWN_COMPONENTS: Record<string, React.ComponentType<any>> = {
  p: ({ children }: any) => <p style={{ margin: "4px 0", fontSize: 13, color: "rgba(255,255,255,0.8)" }}>{children}</p>,
  h1: ({ children }: any) => <h1 style={{ fontSize: 18, fontWeight: "bold", color: "rgba(255,255,255,0.9)", margin: "12px 0 6px" }}>{children}</h1>,
  h2: ({ children }: any) => <h2 style={{ fontSize: 16, fontWeight: "bold", color: "rgba(255,255,255,0.85)", margin: "10px 0 4px" }}>{children}</h2>,
  h3: ({ children }: any) => <h3 style={{ fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.7)", margin: "8px 0 2px" }}>{children}</h3>,
  code: ({ children, className }: any) => !className
    ? <code style={{ background: "rgba(255,255,255,0.1)", padding: "2px 4px", borderRadius: 3, fontSize: 12, color: "#22d3ee" }}>{children}</code>
    : <pre style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 6, padding: 8, overflow: "auto", margin: "6px 0" }}><code style={{ fontSize: 11, color: "#22d3ee" }}>{children}</code></pre>,
  blockquote: ({ children }: any) => <blockquote style={{ borderLeft: "2px solid rgba(168,85,247,0.5)", paddingLeft: 10, margin: "4px 0", fontSize: 12, color: "rgba(255,255,255,0.5)", fontStyle: "italic" }}>{children}</blockquote>,
};

export default function ExobrainEditor({ onSettings }: Props) {
  const cfgRef = useRef<AppConfig>(loadConfig());
  const [state, _setState] = useState<ExobrainState>(() => {
    try {
      const raw = localStorage.getItem("exobrain_edit_state");
      if (raw) return JSON.parse(raw);
    } catch {}
    return { messages: [], documentMarkdown: DEFAULT_DOC, comments: {} };
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Rebuild editor config byte array from panes whenever the state changes
  const setState = useCallback((v: ExobrainState | ((p: ExobrainState) => ExobrainState)) => {
    _setState((prev) => {
      const next = typeof v === "function" ? v(prev) : v;
      try { localStorage.setItem("exobrain_edit_state", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const { messages, documentMarkdown, comments } = state;

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const paragraphs = useMemo(() => splitParagraphs(documentMarkdown), [documentMarkdown]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const cfg = cfgRef.current;
    const userMsg: Message = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setState({ messages: newMessages, documentMarkdown, comments });
    setInput("");
    setLoading(true);

    try {
      const body = buildChatBody(cfg, newMessages, documentMarkdown, comments);
      const resp = await fetch(getChatEndpoint(cfg), {
        method: "POST",
        headers: getChatHeaders(cfg),
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        const errText = await resp.text().catch(() => "Unknown error");
        throw new Error(`HTTP ${resp.status}: ${errText.slice(0, 200)}`);
      }

      const data = await resp.json();
      const { reply, document: updatedDoc } = parseChatResponse(cfg, data);

      const asstMsg: Message = { role: "assistant", content: reply };
      setState((prev) => ({
        messages: [...prev.messages, asstMsg],
        documentMarkdown: updatedDoc || prev.documentMarkdown,
        comments: updatedDoc ? {} : prev.comments,
      }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, { role: "assistant", content: `❌ ${err instanceof Error ? err.message : "Unknown error"}` }],
      }));
    } finally {
      setLoading(false);
    }
  };

  const clearSession = () => {
    setState({ messages: [], documentMarkdown: DEFAULT_DOC, comments: {} });
  };

  const copyDoc = () => {
    navigator.clipboard.writeText(documentMarkdown).catch(() => {});
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#000", color: "#e0e0e0" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 12px", borderBottom: "1px solid rgba(255,255,255,0.1)",
        background: "rgba(0,0,0,0.9)", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 16, fontWeight: "bold",
            background: "linear-gradient(135deg, #a855f7, #06b6d4)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>
            Exobrain
          </span>
          <span style={{ fontSize: 10, color: "#555" }}>
            {cfgRef.current.mode === "self" ? "🔑 Self" : "☁️ SaaS"}
          </span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <button onClick={() => setShowSource(!showSource)} style={btnStyle(showSource)}>
            {showSource ? "👁" : "📄"}
          </button>
          <button onClick={copyDoc} style={btnStyle(false)}>📋</button>
          <button onClick={clearSession} style={btnStyle(false)}>🗑</button>
          <button onClick={onSettings} style={{ ...btnStyle(false), fontSize: 18 }}>⚙</button>
        </div>
      </div>

      {/* Main */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Chat (40%) */}
        <div style={{
          width: "40%", minWidth: 280, display: "flex", flexDirection: "column",
          borderRight: "1px solid rgba(255,255,255,0.1)",
        }}>
          <div style={{ flex: 1, overflow: "auto", padding: 12 }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", color: "rgba(255,255,255,0.3)", marginTop: "40%" }}>
                <div style={{ fontSize: 40, marginBottom: 12 }}>🧠</div>
                <p style={{ fontSize: 14 }}>Chat with AI to build your paper</p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                marginBottom: 8,
              }}>
                <div style={{
                  maxWidth: "90%", padding: "8px 12px", borderRadius: 12,
                  background: m.role === "user" ? "rgba(168,85,247,0.2)" : "rgba(255,255,255,0.05)",
                  border: m.role === "user" ? "1px solid rgba(168,85,247,0.3)" : "1px solid rgba(255,255,255,0.1)",
                  fontSize: 13, lineHeight: 1.5,
                }}>
                  {m.role === "assistant" ? (
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex, rehypeRaw]}>
                      {stripMarkdownBlock(m.content)}
                    </ReactMarkdown>
                  ) : (
                    <p style={{ whiteSpace: "pre-wrap" }}>{m.content}</p>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div style={{ textAlign: "center", color: "rgba(255,255,255,0.3)", fontSize: 20 }}>●●●</div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div style={{ padding: 8, borderTop: "1px solid rgba(255,255,255,0.1)" }}>
            <div style={{ display: "flex", gap: 6 }}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                placeholder="Describe your paper..."
                disabled={loading}
                style={{
                  flex: 1, padding: "10px 12px", borderRadius: 10,
                  background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.15)",
                  color: "#e0e0e0", fontSize: 14, outline: "none",
                }}
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                style={{
                  padding: "10px 16px", borderRadius: 10, border: "none",
                  background: (loading || !input.trim()) ? "#333" : "linear-gradient(135deg, #a855f7, #06b6d4)",
                  color: "#fff", fontSize: 14, fontWeight: "bold",
                  opacity: (loading || !input.trim()) ? 0.4 : 1,
                }}
              >
                →
              </button>
            </div>
          </div>
        </div>

        {/* Preview (60%) */}
        <div style={{ width: "60%", overflow: "auto", background: "#0a0a0a", padding: 16 }}>
          {showSource ? (
            <pre style={{ fontSize: 11, color: "rgba(255,255,255,0.5)", whiteSpace: "pre-wrap", fontFamily: "monospace" }}>
              {documentMarkdown}
            </pre>
          ) : (
            <div style={{ maxWidth: 640, margin: "0 auto" }}>
              {paragraphs.map((p) => (
                <div key={p.idx} style={{ marginBottom: 12 }}>
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex, rehypeRaw]}
                    components={MARKDOWN_COMPONENTS}
                  >
                    {p.text}
                  </ReactMarkdown>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function btnStyle(active: boolean): React.CSSProperties {
  return {
    padding: "4px 8px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.15)",
    background: active ? "rgba(168,85,247,0.2)" : "transparent",
    color: active ? "#a855f7" : "rgba(255,255,255,0.5)",
    fontSize: 14, cursor: "pointer",
  };
}
