import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import { AppConfig, loadConfig, getChatEndpoint, getChatHeaders, getDocumentsEndpoint, buildChatBody, parseChatResponse, DocInfo } from "../config";

// ── Types ──────────────────────────────────────────────────────────

interface Message { role: "user" | "assistant"; content: string }
interface ExobrainState {
  messages: Message[];
  documentMarkdown: string;
  comments: Record<number, string[]>;
}

// ── Helpers ─────────────────────────────────────────────────────────

function stripMarkdownBlock(content: string): string {
  return content.replace(/```markdown\n[\s\S]*?\n```/g, "").trim();
}

function splitParagraphs(md: string): { idx: number; text: string }[] {
  return md.split("\n\n").map((text, idx) => ({ idx, text: text.trim() })).filter((p) => p.text.length > 0);
}

// ── Breakpoint ──────────────────────────────────────────────────────

const MOBILE_BREAKPOINT = 768;

function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window !== "undefined") return window.innerWidth < MOBILE_BREAKPOINT;
    return false;
  });
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return isMobile;
}

// ── Props ───────────────────────────────────────────────────────────

interface Props {
  onSettings: () => void;
}

const MARKDOWN_COMPONENTS: Record<string, React.ComponentType<any>> = {
  p: ({ children }: any) => <p style={{ margin: "4px 0", fontSize: 13, color: "var(--fg)" }}>{children}</p>,
  h1: ({ children }: any) => <h1 style={{ fontSize: 18, fontWeight: "bold", color: "var(--heading-primary)", margin: "12px 0 6px" }}>{children}</h1>,
  h2: ({ children }: any) => <h2 style={{ fontSize: 16, fontWeight: "bold", color: "var(--heading-secondary)", margin: "10px 0 4px" }}>{children}</h2>,
  h3: ({ children }: any) => <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--fg-secondary)", margin: "8px 0 2px" }}>{children}</h3>,
  code: ({ children, className }: any) => !className
    ? <code style={{ background: "var(--comment-bg)", padding: "2px 4px", borderRadius: 3, fontSize: 12, color: "var(--fg-link)" }}>{children}</code>
    : <pre style={{ background: "var(--pre-bg)", border: "1px solid var(--pre-border)", borderRadius: 6, padding: 8, overflow: "auto", margin: "6px 0" }}><code style={{ fontSize: 11, color: "var(--fg-link)" }}>{children}</code></pre>,
  blockquote: ({ children }: any) => <blockquote style={{ borderLeft: "2px solid rgba(168,85,247,0.5)", paddingLeft: 10, margin: "4px 0", fontSize: 12, color: "var(--btn-text)", fontStyle: "italic" }}>{children}</blockquote>,
};

type Tab = "chat" | "preview" | "verify";

interface VerifyResult { line: number; equation: string; status: string; detail: string }

// ── i18n ──────────────────────────────────────────────────────────────

const STR = {
  en: {
    title: "Exobrain",
    chat_with_ai: "Chat with AI to build your paper",
    describe_paper: "Describe your paper...",
    hints: [
      "Write an introduction for Riemann zeta function",
      "Derive the quadratic formula step by step",
      "Explain the Central Limit Theorem",
      "Prove the Pythagorean theorem",
    ],
    tab_chat: "💬 Chat",
    tab_doc: "📄 Document",
    tab_verify: "🔬 Verify",
    no_projects: "No projects",
    new_project: "➕ New Project",
    untitled: "Untitled Paper",
    delete_confirm: "Delete this project?",
    saving: "saving...",
    default_intro: "This is your mathematical paper. Start editing or chat with the AI to build it.",
    btn_copy: "Copy",
    btn_clear: "Clear",
    btn_settings: "Settings",
  },
  zh: {
    title: "Exobrain",
    chat_with_ai: "与 AI 对话，构建你的论文",
    describe_paper: "描述你想要的论文...",
    hints: [
      "撰写黎曼 zeta 函数的论文引言",
      "逐步推导二次公式",
      "解释中心极限定理",
      "证明毕达哥拉斯定理",
    ],
    tab_chat: "💬 对话",
    tab_doc: "📄 文档",
    tab_verify: "🔬 验证",
    no_projects: "暂无项目",
    new_project: "➕ 新建项目",
    untitled: "未命名论文",
    delete_confirm: "确定删除此项目？",
    saving: "保存中...",
    default_intro: "这是你的数学论文。开始编辑或与 AI 对话来构建它。",
    btn_copy: "复制",
    btn_clear: "清空",
    btn_settings: "设置",
  },
};

const DEFAULT_DOC = `# Untitled Paper

## Introduction

This is your mathematical paper. Start editing or chat with the AI to build it.

## Equations

Inline math: $E = mc^2$

Block math:

$$\\\\int_{0}^{\\\\infty} e^{-x^2} dx = \\\\frac{\\\\sqrt{\\\\pi}}{2}$$

`;

const DEFAULT_DOC_ZH = `# 未命名论文

## 引言

这是你的数学论文。开始编辑或与 AI 对话来构建它。

## 方程式

行内公式: $E = mc^2$

块级公式:

$$\\\\int_{0}^{\\\\infty} e^{-x^2} dx = \\\\frac{\\\\sqrt{\\\\pi}}{2}$$

`;

export default function ExobrainEditor({ onSettings }: Props) {
  const [cfg, setCfg] = useState<AppConfig>(loadConfig);
  const cfgRef = useRef(cfg);
  cfgRef.current = cfg; // always latest for callbacks
  const isMobile = useIsMobile();
  const isSaaS = cfg.mode === "saas";
  const t = STR[cfg.lang] || STR.en;
  const defaultDoc = cfg.lang === "zh" ? DEFAULT_DOC_ZH : DEFAULT_DOC;
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [state, _setState] = useState<ExobrainState>(() => {
    try {
      const raw = localStorage.getItem("exobrain_edit_state");
      if (raw) return JSON.parse(raw);
    } catch {}
    return { messages: [], documentMarkdown: defaultDoc, comments: {} };
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [verifyResults, setVerifyResults] = useState<VerifyResult[] | null>(null);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // ── Project management ──────────────────────────────────────────────
  const [projects, setProjects] = useState<DocInfo[]>([]);
  const [currentDocId, setCurrentDocId] = useState<string | null>(null);
  const [docTitle, setDocTitle] = useState<string>("");
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [savingStatus, setSavingStatus] = useState<"idle" | "saving">("idle");

  // Reload config when returning from settings
  useEffect(() => {
    const fresh = loadConfig();
    setCfg(fresh);
  }, []);

  const setState = useCallback((v: ExobrainState | ((p: ExobrainState) => ExobrainState)) => {
    _setState((prev) => {
      const next = typeof v === "function" ? v(prev) : v;
      try { localStorage.setItem("exobrain_edit_state", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const { messages, documentMarkdown, comments } = state;

  // Auto-scroll to bottom — use scrollTop to avoid mobile scrollIntoView issues
  useEffect(() => {
    const el = chatContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Switch to chat when user sends a message on mobile
  const switchToChat = useCallback(() => { if (isMobile) setActiveTab("chat"); }, [isMobile]);

  const paragraphs = useMemo(() => splitParagraphs(documentMarkdown), [documentMarkdown]);

  // ── Project operations ──────────────────────────────────────────────

  const fetchProjects = useCallback(async () => {
    const cfg = cfgRef.current;
    if (cfg.mode !== "saas" || !cfg.emergenceApiKey) return;
    try {
      const resp = await fetch(getDocumentsEndpoint(cfg), {
        headers: getChatHeaders(cfg),
      });
      if (resp.ok) {
        const data = await resp.json();
        setProjects(data.documents || []);
      }
    } catch { /* offline — keep stale list */ }
  }, []);

  // Load projects on mount (SaaS only)
  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const openProject = useCallback((doc: DocInfo) => {
    setCurrentDocId(doc.id);
    setDocTitle(doc.title);
    setProjectsOpen(false);
    setState({
      messages: (doc.messages || []) as Message[],
      documentMarkdown: doc.markdown || defaultDoc,
      comments: {},
    });
  }, []);

  const createProject = useCallback(async () => {
    const cfg = cfgRef.current;
    if (!isSaaS) return;
    try {
      const resp = await fetch(getDocumentsEndpoint(cfg), {
        method: "POST",
        headers: getChatHeaders(cfg),
        body: JSON.stringify({ title: t.untitled }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const doc: DocInfo = data.document;
        setProjects(prev => [doc, ...prev]);
        openProject(doc);
      }
    } catch {}
  }, [isSaaS, openProject]);

  const deleteProject = useCallback(async (id: string) => {
    const cfg = cfgRef.current;
    if (!isSaaS) return;
    try {
      const resp = await fetch(getDocumentsEndpoint(cfg, id), {
        method: "DELETE",
        headers: getChatHeaders(cfg),
      });
      if (resp.ok) {
        setProjects(prev => prev.filter(p => p.id !== id));
        if (currentDocId === id) {
          setCurrentDocId(null);
          setDocTitle("");
          setState({ messages: [], documentMarkdown: defaultDoc, comments: {} });
        }
      }
    } catch {}
  }, [isSaaS, currentDocId]);

  // Auto-save to backend after each assistant reply (SaaS only)
  const saveToBackend = useCallback(async (msgs: Message[], md: string) => {
    const cfg = cfgRef.current;
    if (!currentDocId || !isSaaS) return;
    setSavingStatus("saving");
    try {
      await fetch(getDocumentsEndpoint(cfg, currentDocId), {
        method: "PATCH",
        headers: getChatHeaders(cfg),
        body: JSON.stringify({ markdown: md, messages: msgs }),
      });
    } catch {}
    setSavingStatus("idle");
  }, [currentDocId, isSaaS]);

  // ── Verify ───────────────────────────────────────────────────────────
  const runVerify = useCallback(async () => {
    const cfg = cfgRef.current;
    if (!isSaaS) return;
    setVerifyLoading(true);
    setVerifyResults(null);
    setActiveTab("verify");
    try {
      const resp = await fetch("https://api.emergence.science/api/play/exobrain/verify", {
        method: "POST",
        headers: getChatHeaders(cfg),
        body: JSON.stringify({ markdown: documentMarkdown }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setVerifyResults(data);
      } else {
        setVerifyResults([{ line: 0, equation: "", status: "error", detail: `HTTP ${resp.status}` }]);
      }
    } catch (err) {
      setVerifyResults([{ line: 0, equation: "", status: "error", detail: `${err}` }]);
    } finally {
      setVerifyLoading(false);
    }
  }, [isSaaS, documentMarkdown]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const cfg = cfgRef.current;
    const userMsg: Message = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setState({ messages: newMessages, documentMarkdown, comments });
    setInput("");
    setLoading(true);
    switchToChat();

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
      const finalDoc = updatedDoc || documentMarkdown;
      const finalMessages = [...newMessages, asstMsg];
      setState((prev) => ({
        messages: finalMessages,
        documentMarkdown: finalDoc,
        comments: updatedDoc ? {} : prev.comments,
      }));
      // Auto-save to backend (SaaS only)
      saveToBackend(finalMessages, finalDoc);
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
    setState({ messages: [], documentMarkdown: defaultDoc, comments: {} });
  };

  const copyDoc = () => {
    navigator.clipboard.writeText(documentMarkdown).catch(() => {});
  };

  // ── Shared styles ──────────────────────────────────────────────────

  const headerStyle: React.CSSProperties = {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "8px 12px", paddingTop: "max(8px, env(safe-area-inset-top, 0px))",
    borderBottom: "1px solid var(--divider)",
    background: "var(--header-bg)", flexShrink: 0,
    position: "sticky", top: 0, zIndex: 10,
  };

  const containerStyle: React.CSSProperties = {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
    display: "flex", flexDirection: "column",
    background: "var(--bg)", color: "var(--fg)",
  };

  // ── Chat panel (shared) ────────────────────────────────────────────

  const chatPanel = (
    <div style={{
      display: "flex", flexDirection: "column",
      flex: isMobile ? 1 : undefined,
      width: isMobile ? undefined : "40%",
      minWidth: isMobile ? undefined : 280,
      borderRight: isMobile ? undefined : "1px solid var(--divider)",
      overflow: "hidden",
    }}>
      <div ref={chatContainerRef} style={{ flex: 1, overflow: "auto", padding: 12, overscrollBehavior: "contain" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", color: "var(--fg-dim)", marginTop: isMobile ? "20%" : "40%" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🧠</div>
            <p style={{ fontSize: 14, marginBottom: 16 }}>{t.chat_with_ai}</p>
            <div style={{
              display: "flex", flexDirection: "column", gap: 8,
              maxWidth: 300, margin: "0 auto",
            }}>
              {t.hints.map((hint) => (
                <button
                  key={hint}
                  onClick={() => {
                    setInput(hint);
                    // Focus the input
                    const inp = document.querySelector('input[placeholder=\"Describe your paper...\"]') as HTMLInputElement;
                    if (inp) inp.focus();
                  }}
                  style={{
                    textAlign: "left", padding: "10px 14px", borderRadius: 10,
                    border: "1px solid var(--hint-border)",
                    background: "var(--suggestion-bg)",
                    color: "var(--fg-muted)", fontSize: 12, cursor: "pointer",
                    transition: "all 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "var(--hint-hover-border)";
                    e.currentTarget.style.color = "var(--fg-secondary)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--hint-border)";
                    e.currentTarget.style.color = "var(--fg-muted)";
                  }}
                >
                  {hint}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start",
            marginBottom: 8,
          }}>
            <div style={{
              maxWidth: "90%", padding: "8px 12px", borderRadius: 12,
              background: m.role === "user" ? "var(--chat-user-bg)" : "var(--chat-ai-bg)",
              border: m.role === "user" ? "1px solid var(--accent-purple)" : "1px solid var(--border)",
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
          <div style={{ textAlign: "center", color: "var(--fg-dim)", fontSize: 20 }}>●●●</div>
        )}
      </div>

      {/* Input */}
      <div style={{ padding: 8, borderTop: "1px solid var(--divider)", paddingBottom: "max(8px, env(safe-area-inset-bottom, 0px))" }}>
        <div style={{ display: "flex", gap: 6 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder={t.describe_paper}
            disabled={loading}
            style={{
              flex: 1, padding: "10px 12px", borderRadius: 10,
              background: "var(--input-bg)", border: "1px solid var(--border-hover)",
              color: "var(--fg)", fontSize: 14, outline: "none",
            }}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            style={{
              padding: "10px 16px", borderRadius: 10, border: "none",
              background: (loading || !input.trim()) ? "var(--btn-disabled)" : "var(--gradient-btn)",
              color: "#fff", fontSize: 14, fontWeight: "bold",
              opacity: (loading || !input.trim()) ? 0.4 : 1,
            }}
          >
            →
          </button>
        </div>
      </div>
    </div>
  );

  // ── Preview panel (shared) ─────────────────────────────────────────

  const previewPanel = (
    <div style={{
      flex: isMobile ? 1 : undefined,
      width: isMobile ? undefined : "60%",
      overflow: "auto", background: "var(--bg-secondary)", padding: 16,
      paddingBottom: isMobile ? "max(16px, env(safe-area-inset-bottom, 0px))" : 16,
    }}>
      {showSource ? (
        <pre style={{ fontSize: 11, color: "var(--btn-text)", whiteSpace: "pre-wrap", fontFamily: "monospace" }}>
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
  );

  // ── Mobile tab bar ─────────────────────────────────────────────────

  const mobileTabs = (
      <div style={{
      display: "flex", borderBottom: "1px solid var(--divider)",
      background: "var(--tab-bg)", flexShrink: 0,
    }}>
      <button
        onClick={() => setActiveTab("chat")}
        style={{
          flex: 1, padding: "10px 0", border: "none",
          background: activeTab === "chat" ? "var(--tab-active-bg)" : "transparent",
          color: activeTab === "chat" ? "var(--tab-active-fg)" : "var(--tab-inactive-fg)",
          fontSize: 13, fontWeight: activeTab === "chat" ? "bold" : "normal",
          borderBottom: activeTab === "chat" ? "2px solid #06b6d4" : "2px solid transparent",
          cursor: "pointer",
        }}
      >
        {t.tab_chat}
        {messages.length > 0 && (
          <span style={{
            marginLeft: 4, padding: "1px 6px", borderRadius: 8,
            background: "rgba(6,182,212,0.2)", fontSize: 10, color: "#06b6d4",
          }}>
            {messages.length}
          </span>
        )}
      </button>
      <button
        onClick={() => setActiveTab("preview")}
        style={{
          flex: 1, padding: "10px 0", border: "none",
          background: activeTab === "preview" ? "var(--tab-active-bg)" : "transparent",
          color: activeTab === "preview" ? "var(--tab-active-fg)" : "var(--tab-inactive-fg)",
          fontSize: 13, fontWeight: activeTab === "preview" ? "bold" : "normal",
          borderBottom: activeTab === "preview" ? "2px solid #a855f7" : "2px solid transparent",
          cursor: "pointer",
        }}
      >
        {t.tab_doc}
      </button>
      {isSaaS && (
        <button
          onClick={runVerify}
          style={{
            flex: 1, padding: "10px 0", border: "none",
            background: activeTab === "verify" ? "var(--tab-active-bg)" : "transparent",
            color: activeTab === "verify" ? "var(--tab-active-fg)" : "var(--tab-inactive-fg)",
            fontSize: 13, fontWeight: activeTab === "verify" ? "bold" : "normal",
            borderBottom: activeTab === "verify" ? "2px solid #f59e0b" : "2px solid transparent",
            cursor: "pointer",
          }}
        >
          {t.tab_verify}
        </button>
      )}
    </div>
  );

  // ── Verify panel ──────────────────────────────────────────────────

  const verifyPanel = (
    <div style={{
      flex: 1, overflow: "auto", background: "var(--bg-secondary)", padding: 16,
    }}>
      {verifyLoading ? (
        <div style={{ textAlign: "center", color: "var(--fg-dim)", marginTop: "40%", fontSize: 20 }}>●●●</div>
      ) : verifyResults === null ? (
        <div style={{ textAlign: "center", color: "var(--fg-dim)", marginTop: "40%", fontSize: 14 }}>
          <p>Tap the Verify tab to check LaTeX equations with SymPy.</p>
        </div>
      ) : verifyResults.length === 0 ? (
        <div style={{ textAlign: "center", color: "var(--fg-dim)", marginTop: "40%", fontSize: 14 }}>
          <p>✅ No equations found in document.</p>
        </div>
      ) : (
        <div style={{ maxWidth: 640, margin: "0 auto" }}>
          {verifyResults.map((r, i) => (
            <div key={i} style={{
              padding: "8px 12px", marginBottom: 8, borderRadius: 8,
              background: r.status === "verified" ? "rgba(34,197,94,0.1)" : r.status === "error" ? "rgba(239,68,68,0.1)" : "rgba(255,255,255,0.03)",
              border: `1px solid ${r.status === "verified" ? "rgba(34,197,94,0.3)" : r.status === "error" ? "rgba(239,68,68,0.3)" : "var(--border)"}`,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: "var(--fg-tertiary)" }}>Line {r.line}</span>
                <span style={{
                  fontSize: 11, fontWeight: "bold",
                  color: r.status === "verified" ? "#22c55e" : r.status === "error" ? "#ef4444" : "#f59e0b",
                }}>
                  {r.status === "verified" ? "✓" : r.status === "error" ? "✗" : "?"} {r.status}
                </span>
              </div>
              <code style={{ fontSize: 12, color: "var(--fg-link)", display: "block", marginBottom: 4 }}>{r.equation}</code>
              <p style={{ fontSize: 11, color: "var(--fg-secondary)" }}>{r.detail}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{
            display: "flex", alignItems: "center", gap: 6,
          }}>
            <div style={{
              width: 24, height: 24, borderRadius: 6,
              background: "linear-gradient(135deg, #a855f7, #06b6d4)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14, flexShrink: 0,
            }}>🧠</div>
            <span style={{
              fontSize: 16, fontWeight: "bold",
              background: "linear-gradient(135deg, #a855f7, #06b6d4)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>
              {t.title}
            </span>
          </span>
          <span style={{ fontSize: 10, color: "var(--fg-tertiary)" }}>
            {cfgRef.current.mode === "self" ? "🔑" : "☁️"}
          </span>
          {isSaaS && (
            <span style={{ position: "relative" }}>
              <button
                onClick={() => { setProjectsOpen(!projectsOpen); if (!projectsOpen) fetchProjects(); }}
                style={{
                  ...btnStyle(false), fontSize: 16, padding: "2px 6px",
                  display: "flex", alignItems: "center", gap: 4,
                }}
                title="Projects"
              >
                📁 {docTitle ? (
                  <span style={{ fontSize: 11, maxWidth: 80, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--fg-secondary)" }}>
                    {docTitle}
                  </span>
                ) : null}
                {savingStatus === "saving" && <span style={{ fontSize: 10, color: "var(--fg-dim)" }}>…</span>}
              </button>
              {projectsOpen && (
                <div style={{
                  position: "absolute", top: "100%", left: 0, zIndex: 100,
                  background: "var(--bg-tertiary)", border: "1px solid var(--border)",
                  borderRadius: 8, minWidth: 200, maxHeight: 300, overflow: "auto",
                  boxShadow: "0 4px 12px var(--shadow-dropdown)",
                }}>
                  {projects.length === 0 ? (
                    <div style={{ padding: 12, fontSize: 12, color: "var(--fg-dim)" }}>{t.no_projects}</div>
                  ) : (
                    projects.map((p) => (
                      <div key={p.id} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "8px 12px", cursor: "pointer",
                        borderBottom: "1px solid var(--border)",
                        background: currentDocId === p.id ? "var(--chat-user-bg)" : "transparent",
                      }}>
                        <div onClick={() => openProject(p)} style={{ flex: 1, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {p.title}
                          <span style={{ fontSize: 10, color: "var(--fg-tertiary)", marginLeft: 6 }}>
                            {new Date(p.updated_at).toLocaleDateString()}
                          </span>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); if (confirm(t.delete_confirm)) deleteProject(p.id); }}
                          style={{ ...btnStyle(false), fontSize: 12, padding: "1px 4px", opacity: 0.5 }}
                        >
                          🗑
                        </button>
                      </div>
                    ))
                  )}
                  <div style={{ padding: 4 }}>
                    <button
                      onClick={createProject}
                      style={{
                        width: "100%", padding: "6px", border: "none", borderRadius: 6,
                        background: "var(--suggestion-bg)", color: "var(--fg-secondary)",
                        fontSize: 12, cursor: "pointer",
                      }}
                    >
                      {t.new_project}
                    </button>
                  </div>
                </div>
              )}
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <button onClick={() => setShowSource(!showSource)} style={btnStyle(showSource)}>
            {showSource ? "👁" : "📄"}
          </button>
          <button onClick={copyDoc} style={btnStyle(false)}>{t.btn_copy}</button>
          <button onClick={clearSession} style={btnStyle(false)}>{t.btn_clear}</button>
          <button onClick={onSettings} style={btnStyle(false)}>{t.btn_settings}</button>
        </div>
      </div>

      {/* Desktop: side-by-side */}
      {!isMobile && (
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {chatPanel}
          {previewPanel}
        </div>
      )}

      {/* Mobile: tabs + single column */}
      {isMobile && (
        <>
          {mobileTabs}
          <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
            {activeTab === "chat" ? chatPanel : activeTab === "verify" ? verifyPanel : previewPanel}
          </div>
        </>
      )}
    </div>
  );
}

function btnStyle(active: boolean): React.CSSProperties {
  return {
    padding: "4px 8px", borderRadius: 6, border: "1px solid var(--border-hover)",
    background: active ? "rgba(168,85,247,0.2)" : "transparent",
    color: active ? "var(--btn-active-color)" : "var(--btn-text)",
    fontSize: 13, cursor: "pointer",
  };
}
