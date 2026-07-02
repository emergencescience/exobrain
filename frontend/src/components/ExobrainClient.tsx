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

interface Document {
  id: string;
  title: string;
  markdown: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
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
    settings_btn: "⚙️",
    projects_btn: "📁 Projects",
    settings_title: "Settings",
    theme_label: "Theme",
    theme_dark: "Dark",
    theme_light: "Light",
    lang_label: "Language",
    llm_provider_label: "LLM Provider",
    llm_base_url_label: "Base URL",
    llm_api_key_label: "API Key",
    llm_model_label: "Model",
    llm_base_url_placeholder: "https://api.openai.com/v1",
    llm_api_key_placeholder: "sk-...",
    llm_model_placeholder: "gpt-4o",
    close_btn: "Close",
    reveal_btn: "👁",
    hide_btn: "🙈",
    projects_header: "Projects",
    new_project_btn: "➕ New Project",
    delete_confirm: "Delete this project?",
    delete_btn: "🗑",
    back_dashboard: "📁 Projects",
    saving: "Saving...",
    saved: "Saved",
    no_projects: "No projects yet. Create one to get started!",
    tab_chat: "💬 Chat",
    tab_source: "📝 Source",
    tab_preview: "👁 Preview",
    tab_verify: "🔬 Verify",
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
    settings_btn: "⚙️",
    projects_btn: "📁 项目",
    settings_title: "设置",
    theme_label: "主题",
    theme_dark: "深色",
    theme_light: "浅色",
    lang_label: "语言",
    llm_provider_label: "LLM 提供商",
    llm_base_url_label: "Base URL",
    llm_api_key_label: "API Key",
    llm_model_label: "模型",
    llm_base_url_placeholder: "https://api.openai.com/v1",
    llm_api_key_placeholder: "sk-...",
    llm_model_placeholder: "gpt-4o",
    close_btn: "关闭",
    reveal_btn: "👁",
    hide_btn: "🙈",
    projects_header: "项目",
    new_project_btn: "➕ 新建项目",
    delete_confirm: "确定删除这个项目？",
    delete_btn: "🗑",
    back_dashboard: "📁 项目",
    saving: "保存中...",
    saved: "已保存",
    no_projects: "暂无项目，创建一个开始吧！",
    tab_chat: "💬 对话",
    tab_source: "📝 源码",
    tab_preview: "👁 预览",
    tab_verify: "🔬 验证",
  },
};

const TAB_LABELS: Record<string, string> = {
  chat: "💬 Chat", source: "📝 Source", preview: "👁 Preview", verify: "🔬 Verify",
};

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

// ── Settings helpers ──────────────────────────────────────────────

function loadSettings() {
  if (typeof window === "undefined") return { theme: "dark", lang: "en", llmBaseUrl: "", llmApiKey: "", llmModel: "" };
  return {
    theme: localStorage.getItem("exobrain_theme") || "dark",
    lang: (localStorage.getItem("exobrain_lang") || "en") as "en" | "zh",
    llmBaseUrl: localStorage.getItem("exobrain_llm_base_url") || "",
    llmApiKey: localStorage.getItem("exobrain_llm_api_key") || "",
    llmModel: localStorage.getItem("exobrain_llm_model") || "",
  };
}

function loadCurrentProject(): { docId: string; title: string } | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("exobrain_current_project");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveCurrentProject(docId: string, title: string) {
  try {
    localStorage.setItem("exobrain_current_project", JSON.stringify({ docId, title }));
  } catch {}
}

function clearCurrentProject() {
  try {
    localStorage.removeItem("exobrain_current_project");
  } catch {}
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
  const [mobileTab, setMobileTab] = useState<"chat" | "source" | "preview" | "verify">("chat");
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ── Settings & Project state ──────────────────────────────────
  const [settings, setSettings] = useState(loadSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [projects, setProjects] = useState<Document[]>([]);
  const [currentDocId, setCurrentDocId] = useState<string | null>(() => loadCurrentProject()?.docId || null);
  const [docTitle, setDocTitle] = useState<string>(() => loadCurrentProject()?.title || "");
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [savingStatus, setSavingStatus] = useState<"idle" | "saving" | "saved">("idle");

  // Theme effect
  useEffect(() => {
    localStorage.setItem("exobrain_theme", settings.theme);
  }, [settings.theme]);

  // Language effect
  useEffect(() => {
    localStorage.setItem("exobrain_lang", settings.lang);
  }, [settings.lang]);

  useEffect(() => {
    const currentDefault = buildDefaultDocument(dict);
    setState((prev) => {
      if (prev.documentMarkdown.includes("Untitled Paper") || prev.documentMarkdown.includes("未命名论文")) {
        return { ...prev, documentMarkdown: currentDefault };
      }
      return prev;
    });
  }, [lang]);

  // Fetch projects
  const fetchProjects = useCallback(async () => {
    setProjectsLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/documents`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data.documents || []);
      }
    } catch {
      // offline — use empty list
    } finally {
      setProjectsLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Open a project
  const openProject = useCallback(async (doc: Document) => {
    setCurrentDocId(doc.id);
    setDocTitle(doc.title);
    saveCurrentProject(doc.id, doc.title);
    setState({
      messages: doc.messages || [],
      documentMarkdown: doc.markdown || buildDefaultDocument(dict),
      comments: {},
    });
  }, [dict]);

  // Go back to dashboard
  const goToDashboard = useCallback(() => {
    setCurrentDocId(null);
    setDocTitle("");
    clearCurrentProject();
    setState({ messages: [], documentMarkdown: buildDefaultDocument(dict), comments: {} });
    fetchProjects();
  }, [dict, fetchProjects]);

  // Delete project
  const deleteProject = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/documents/${id}`, { method: "DELETE" });
      if (res.ok) {
        setProjects((prev) => prev.filter((p) => p.id !== id));
        if (currentDocId === id) {
          goToDashboard();
        }
      }
    } catch {}
  }, [apiBaseUrl, currentDocId, goToDashboard]);

  // Create new project
  const createProject = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: dict.default_document_title }),
      });
      if (res.ok) {
        const data = await res.json();
        const doc: Document = data.document;
        setProjects((prev) => [doc, ...prev]);
        openProject(doc);
      }
    } catch {}
  }, [apiBaseUrl, dict, openProject]);

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
      if (currentDocId) body.doc_id = currentDocId;

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

      // PATCH the document if we have a doc_id
      if (currentDocId) {
        setSavingStatus("saving");
        try {
          const finalDoc = updatedDoc || documentMarkdown;
          const finalMessages = [...newMessages, assistantMsg];
          await fetch(`${apiBaseUrl}/api/documents/${currentDocId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ markdown: finalDoc, messages: finalMessages }),
          });
          setSavingStatus("saved");
          setTimeout(() => setSavingStatus("idle"), 2000);
        } catch {
          setSavingStatus("idle");
        }
      }
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
            {currentDocId ? docTitle : dict.play_title}
          </span>
          {currentDocId && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full ${
              savingStatus === "saving" ? "bg-yellow-500/20 text-yellow-400" :
              savingStatus === "saved" ? "bg-green-500/20 text-green-400" : "hidden"
            }`}>
              {savingStatus === "saving" ? dict.saving : savingStatus === "saved" ? dict.saved : ""}
            </span>
          )}
          <span className="text-xs text-white/40 hidden sm:inline">{dict.model_label}</span>
        </div>
        <div className="flex items-center gap-2">
          {currentDocId && (
            <button onClick={goToDashboard} className="px-3 py-1 text-xs rounded border border-white/20 hover:border-purple-400/50 hover:text-purple-300 transition-colors">
              {dict.back_dashboard}
            </button>
          )}
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
          <button onClick={() => setSettingsOpen(true)} className="px-2 py-1 text-sm rounded border border-white/20 hover:border-purple-400/50 hover:text-purple-300 transition-colors" title={dict.settings_title}>
            {dict.settings_btn}
          </button>
        </div>
      </header>

      {/* Project Dashboard (when no project is open) */}
      {!currentDocId ? (
        <ProjectDashboard
          dict={dict}
          projects={projects}
          loading={projectsLoading}
          onOpen={openProject}
          onDelete={deleteProject}
          onCreate={createProject}
        />
      ) : (
      /* Main Panels */
      <div className="flex flex-1 overflow-hidden">
        {/* ── Mobile Tab Bar (visible < 768px) ── */}
        <div className="md:hidden flex flex-col flex-1 overflow-hidden">
          <div className="flex border-b border-white/10 shrink-0">
            {(["chat","source","preview","verify"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setMobileTab(tab)}
                className={`flex-1 py-2 text-xs font-medium transition-colors ${
                  mobileTab === tab
                    ? "text-purple-400 border-b-2 border-purple-400 bg-purple-500/5"
                    : "text-white/40 hover:text-white/60 border-b-2 border-transparent"
                }`}
              >
                {TAB_LABELS[tab] || tab}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-hidden">
            {/* Mobile Chat Panel */}
            {mobileTab === "chat" && (
              <div className="flex flex-col h-full">
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                  {messages.length === 0 && (
                    <div className="text-center text-white/30 mt-10">
                      <p className="text-3xl mb-3">🧠</p>
                      <p className="text-sm font-medium text-white/50">{dict.empty_title}</p>
                      <p className="text-xs mt-1">{dict.empty_desc}</p>
                      <div className="mt-4 grid grid-cols-1 gap-1.5 max-w-xs mx-auto">
                        {dict.suggestions.map((hint, idx) => {
                          const ids = ["riemann_intro","quadratic_derivation","clt_explanation","pythagorean_proof"];
                          return (
                            <button key={hint} onClick={() => sendMessage(ids[idx], hint)}
                              className="text-left text-[11px] px-2.5 py-1.5 rounded border border-white/10 hover:border-purple-400/30 text-white/40 hover:text-white/70 transition-colors">
                              {hint}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {messages.map((msg, i) => {
                    const displayContent = msg.role === "assistant" ? stripMarkdownBlock(msg.content) : msg.content;
                    return (
                      <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[90%] rounded-lg px-3 py-2 text-xs ${
                          msg.role === "user" ? "bg-purple-600/30 text-purple-100 border border-purple-500/20"
                            : "bg-white/5 text-white/80 border border-white/10"}`}>
                          {msg.role === "assistant" ? (
                            <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>{displayContent}</ReactMarkdown>
                          ) : (
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  {loading && (
                    <div className="flex justify-start">
                      <div className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white/50">
                        <span className="inline-flex gap-1"><span className="animate-bounce">●</span><span className="animate-bounce" style={{animationDelay:"0.1s"}}>●</span><span className="animate-bounce" style={{animationDelay:"0.2s"}}>●</span></span>
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
                <div className="p-2 border-t border-white/10">
                  <div className="flex gap-1.5">
                    <textarea value={input} onChange={handleInputChange} onKeyDown={handleKeyDown} placeholder={dict.input_placeholder}
                      rows={1} disabled={loading}
                      className="flex-1 bg-white/5 border border-white/20 rounded-lg px-2.5 py-1.5 text-xs text-white/90 placeholder:text-white/30 focus:outline-none focus:border-purple-400/50 resize-none disabled:opacity-50" />
                    <button onClick={() => sendMessage()} disabled={loading || !input.trim()}
                      className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-500 to-cyan-500 text-white text-xs font-medium hover:from-purple-400 hover:to-cyan-400 disabled:opacity-30 disabled:cursor-not-allowed transition-all shrink-0">
                      {dict.send_btn}
                    </button>
                  </div>
                </div>
              </div>
            )}
            {/* Mobile Source Panel */}
            {mobileTab === "source" && (
              <div className="h-full overflow-y-auto p-3">
                <pre className="text-[11px] text-white/60 font-mono whitespace-pre-wrap leading-relaxed bg-white/[0.02] rounded p-3 border border-white/5 h-full">
                  {documentMarkdown}
                </pre>
              </div>
            )}
            {/* Mobile Preview Panel */}
            {mobileTab === "preview" && (
              <div className="flex flex-col h-full">
                <div className="flex-1 overflow-y-auto p-3">
                  {paragraphs.map((para) => {
                    const hasComments = comments[para.idx]?.length > 0;
                    return (
                      <div key={para.idx} className={`${hasComments ? "border-l-2 border-yellow-500/50 pl-2" : ""} mb-2`}>
                        <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins} components={MARKDOWN_COMPONENTS}>
                          {para.text}
                        </ReactMarkdown>
                      </div>
                    );
                  })}
                </div>
                <div className="px-3 py-1 border-t border-white/10 text-[9px] text-white/30 flex justify-between shrink-0">
                  <span>{documentMarkdown.split("\n").length} {dict.lines_label}</span>
                  <span>{documentMarkdown.length} {dict.chars_label}</span>
                  <span>{dict.format_label}</span>
                </div>
              </div>
            )}
            {/* Mobile Verify Panel (SymPy — coming soon) */}
            {mobileTab === "verify" && (
              <div className="h-full flex items-center justify-center">
                <div className="text-center text-white/30 p-6">
                  <p className="text-4xl mb-3">🔬</p>
                  <p className="text-sm">Formal verification coming soon.</p>
                  <p className="text-xs mt-1 text-white/20">SymPy &bull; Lean 4</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Desktop Layout (≥ 768px, original side-by-side) ── */}
        {/* Left: Chat (45%) */}
        <div className="hidden md:flex w-[45%] min-w-[300px] flex-col border-r border-white/10">
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
                      <button key={hint} onClick={() => sendMessage(ids[idx], hint)}
                        className="text-left text-xs px-3 py-2 rounded border border-white/10 hover:border-purple-400/30 text-white/40 hover:text-white/70 transition-colors truncate">
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
                  <div className={`max-w-[85%] rounded-lg px-4 py-2 text-sm ${
                    msg.role === "user" ? "bg-purple-600/30 text-purple-100 border border-purple-500/20"
                      : "bg-white/5 text-white/80 border border-white/10"}`}>
                    {msg.role === "assistant" ? (
                      <div>
                        <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>{displayContent}</ReactMarkdown>
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
                  <span className="inline-flex gap-1"><span className="animate-bounce">●</span><span className="animate-bounce" style={{animationDelay:"0.1s"}}>●</span><span className="animate-bounce" style={{animationDelay:"0.2s"}}>●</span></span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="p-3 border-t border-white/10">
            <div className="flex gap-2">
              <textarea value={input} onChange={handleInputChange} onKeyDown={handleKeyDown} placeholder={dict.input_placeholder}
                rows={1} disabled={loading}
                className="flex-1 bg-white/5 border border-white/20 rounded-lg px-3 py-2 text-sm text-white/90 placeholder:text-white/30 focus:outline-none focus:border-purple-400/50 resize-none disabled:opacity-50" />
              <button onClick={() => sendMessage()} disabled={loading || !input.trim()}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-cyan-500 text-white text-sm font-medium hover:from-purple-400 hover:to-cyan-400 disabled:opacity-30 disabled:cursor-not-allowed transition-all shrink-0">
                {dict.send_btn}
              </button>
            </div>
          </div>
        </div>

        {/* Right: Preview (55%) */}
        <div className="hidden md:flex w-[55%] flex-col bg-[#0a0a0a]">
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
                    <div key={para.idx} className="relative group" onMouseEnter={() => setHoveredPara(para.idx)} onMouseLeave={() => { if (hoveredPara === para.idx) setHoveredPara(null); }}>
                      <div className={`transition-colors rounded ${isHovered ? "bg-white/[0.03]" : ""} ${hasComments ? "border-l-2 border-yellow-500/50 pl-3" : ""}`}>
                        <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins} components={MARKDOWN_COMPONENTS}>
                          {para.text}
                        </ReactMarkdown>
                      </div>
                      {isHovered && (
                        <div className="absolute -right-2 top-0 translate-x-full flex gap-1 z-10">
                          <button onClick={() => setCommentingPara(para.idx)} className="px-2 py-0.5 text-[10px] rounded bg-white/10 border border-white/20 text-white/60 hover:bg-purple-500/30 hover:text-purple-200 whitespace-nowrap">💬</button>
                        </div>
                      )}
                      {(isCommenting || hasComments) && (
                        <div className="ml-4 my-1 pl-3 border-l border-yellow-500/30">
                          {hasComments && comments[para.idx].map((c, ci) => (
                            <div key={ci} className="text-[11px] text-yellow-300/70 py-0.5">💬 {c}</div>
                          ))}
                          {isCommenting && (
                            <div className="flex gap-1 mt-1">
                              <input autoFocus value={commentText} onChange={(e) => setCommentText(e.target.value)}
                                onKeyDown={(e) => { if (e.key === "Enter") addComment(para.idx); if (e.key === "Escape") setCommentingPara(null); }}
                                placeholder={dict.comment_placeholder}
                                className="flex-1 bg-white/10 border border-white/20 rounded px-2 py-0.5 text-[11px] text-white/80 placeholder:text-white/30 focus:outline-none focus:border-yellow-400/50" />
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
      )}

      {/* Settings Modal */}
      {settingsOpen && (
        <SettingsModal
          dict={dict}
          settings={settings}
          showApiKey={showApiKey}
          onClose={() => setSettingsOpen(false)}
          onToggleApiKey={() => setShowApiKey(!showApiKey)}
          onSettingChange={(key: string, value: string) => {
            setSettings((prev) => {
              const next = { ...prev, [key]: value };
              if (key === "llmBaseUrl") localStorage.setItem("exobrain_llm_base_url", value);
              if (key === "llmApiKey") localStorage.setItem("exobrain_llm_api_key", value);
              if (key === "llmModel") localStorage.setItem("exobrain_llm_model", value);
              return next;
            });
          }}
        />
      )}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────

function ProjectDashboard({
  dict,
  projects,
  loading,
  onOpen,
  onDelete,
  onCreate,
}: {
  dict: typeof STRINGS.en;
  projects: Document[];
  loading: boolean;
  onOpen: (doc: Document) => void;
  onDelete: (id: string) => void;
  onCreate: () => void;
}) {
  const handleDelete = (id: string) => {
    if (confirm(dict.delete_confirm)) {
      onDelete(id);
    }
  };

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white/90">{dict.projects_header}</h2>
          <button
            onClick={onCreate}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-cyan-500 text-white text-sm font-medium hover:from-purple-400 hover:to-cyan-400 transition-all"
          >
            {dict.new_project_btn}
          </button>
        </div>

        {loading ? (
          <div className="text-center text-white/40 py-12">
            <span className="inline-flex gap-1">
              <span className="animate-bounce">●</span>
              <span className="animate-bounce" style={{ animationDelay: "0.1s" }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: "0.2s" }}>●</span>
            </span>
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center text-white/30 py-16">
            <p className="text-4xl mb-4">📂</p>
            <p className="text-lg">{dict.no_projects}</p>
            <button
              onClick={onCreate}
              className="mt-4 px-4 py-2 rounded-lg bg-purple-500/20 border border-purple-500/30 text-purple-300 text-sm hover:bg-purple-500/30 transition-colors"
            >
              {dict.new_project_btn}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {projects.map((project) => (
              <div
                key={project.id}
                className="group flex items-start gap-3 p-4 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] hover:border-purple-400/30 transition-all cursor-pointer"
                onClick={() => onOpen(project)}
              >
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-white/80 truncate">{project.title || "Untitled"}</h3>
                  <p className="text-[11px] text-white/30 mt-1">
                    {formatTime(project.updated_at || project.created_at)}
                  </p>
                  <p className="text-xs text-white/40 mt-1.5 line-clamp-2">
                    {(project.markdown || "").substring(0, 80)}{(project.markdown || "").length > 80 ? "..." : ""}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(project.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 px-2 py-1 text-xs rounded border border-red-400/30 text-red-400 hover:bg-red-500/10 transition-all shrink-0"
                  title={dict.delete_btn}
                >
                  {dict.delete_btn}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SettingsModal({
  dict,
  settings,
  showApiKey,
  onClose,
  onToggleApiKey,
  onSettingChange,
}: {
  dict: typeof STRINGS.en;
  settings: { theme: string; lang: string; llmBaseUrl: string; llmApiKey: string; llmModel: string };
  showApiKey: boolean;
  onClose: () => void;
  onToggleApiKey: () => void;
  onSettingChange: (key: string, value: string) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className={`w-full max-w-md mx-4 rounded-xl border ${settings.theme === "light" ? "border-gray-200 bg-white" : "border-white/10 bg-[#111]"} shadow-2xl`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`flex items-center justify-between px-6 py-4 border-b ${settings.theme === "light" ? "border-gray-200" : "border-white/10"}`}>
          <h2 className={`text-lg font-bold ${settings.theme === "light" ? "text-gray-900" : "text-white"}`}>
            {dict.settings_title}
          </h2>
          <button
            onClick={onClose}
            className={`px-2 py-1 text-sm rounded hover:bg-white/10 transition-colors ${settings.theme === "light" ? "text-gray-500 hover:text-gray-700" : "text-white/50 hover:text-white/80"}`}
          >
            ✕
          </button>
        </div>

        <div className="px-6 py-4 space-y-5">
          {/* Theme */}
          <div>
            <label className={`block text-xs font-medium mb-2 ${settings.theme === "light" ? "text-gray-600" : "text-white/50"}`}>
              {dict.theme_label}
            </label>
            <div className="flex gap-2">
              {["dark", "light"].map((t) => (
                <button
                  key={t}
                  onClick={() => onSettingChange("theme", t)}
                  className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-all ${
                    settings.theme === t
                      ? "border-purple-400/50 bg-purple-500/10 text-purple-300"
                      : settings.theme === "light" ? "border-gray-200 text-gray-600 hover:border-gray-400" : "border-white/10 text-white/50 hover:border-white/30"
                  }`}
                >
                  {t === "dark" ? dict.theme_dark : dict.theme_light}
                </button>
              ))}
            </div>
          </div>

          {/* Language */}
          <div>
            <label className={`block text-xs font-medium mb-2 ${settings.theme === "light" ? "text-gray-600" : "text-white/50"}`}>
              {dict.lang_label}
            </label>
            <div className="flex gap-2">
              {[
                { key: "en", label: "English" },
                { key: "zh", label: "中文" },
              ].map((l) => (
                <button
                  key={l.key}
                  onClick={() => onSettingChange("lang", l.key)}
                  className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-all ${
                    settings.lang === l.key
                      ? "border-purple-400/50 bg-purple-500/10 text-purple-300"
                      : settings.theme === "light" ? "border-gray-200 text-gray-600 hover:border-gray-400" : "border-white/10 text-white/50 hover:border-white/30"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* LLM Provider */}
          <div>
            <label className={`block text-xs font-medium mb-3 ${settings.theme === "light" ? "text-gray-600" : "text-white/50"}`}>
              {dict.llm_provider_label}
            </label>

            {/* Base URL */}
            <div className="mb-3">
              <label className={`block text-[10px] mb-1 ${settings.theme === "light" ? "text-gray-500" : "text-white/30"}`}>
                {dict.llm_base_url_label}
              </label>
              <input
                type="text"
                value={settings.llmBaseUrl}
                onChange={(e) => onSettingChange("llmBaseUrl", e.target.value)}
                placeholder={dict.llm_base_url_placeholder}
                className={`w-full px-3 py-2 text-sm rounded-lg border focus:outline-none focus:border-purple-400/50 ${
                  settings.theme === "light"
                    ? "bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-400"
                    : "bg-white/5 border-white/20 text-white/90 placeholder:text-white/30"
                }`}
              />
            </div>

            {/* API Key */}
            <div className="mb-3">
              <label className={`block text-[10px] mb-1 ${settings.theme === "light" ? "text-gray-500" : "text-white/30"}`}>
                {dict.llm_api_key_label}
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={settings.llmApiKey}
                  onChange={(e) => onSettingChange("llmApiKey", e.target.value)}
                  placeholder={dict.llm_api_key_placeholder}
                  className={`w-full px-3 py-2 pr-10 text-sm rounded-lg border focus:outline-none focus:border-purple-400/50 ${
                    settings.theme === "light"
                      ? "bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-400"
                      : "bg-white/5 border-white/20 text-white/90 placeholder:text-white/30"
                  }`}
                />
                <button
                  onClick={onToggleApiKey}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 text-sm ${settings.theme === "light" ? "text-gray-400 hover:text-gray-600" : "text-white/40 hover:text-white/70"}`}
                >
                  {showApiKey ? dict.hide_btn : dict.reveal_btn}
                </button>
              </div>
            </div>

            {/* Model */}
            <div>
              <label className={`block text-[10px] mb-1 ${settings.theme === "light" ? "text-gray-500" : "text-white/30"}`}>
                {dict.llm_model_label}
              </label>
              <input
                type="text"
                value={settings.llmModel}
                onChange={(e) => onSettingChange("llmModel", e.target.value)}
                placeholder={dict.llm_model_placeholder}
                className={`w-full px-3 py-2 text-sm rounded-lg border focus:outline-none focus:border-purple-400/50 ${
                  settings.theme === "light"
                    ? "bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-400"
                    : "bg-white/5 border-white/20 text-white/90 placeholder:text-white/30"
                }`}
              />
            </div>
          </div>
        </div>

        <div className={`px-6 py-4 border-t ${settings.theme === "light" ? "border-gray-200" : "border-white/10"}`}>
          <button
            onClick={onClose}
            className={`w-full px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              settings.theme === "light"
                ? "bg-gray-100 text-gray-700 hover:bg-gray-200"
                : "bg-white/5 text-white/70 hover:bg-white/10 border border-white/10"
            }`}
          >
            {dict.close_btn}
          </button>
        </div>
      </div>
    </div>
  );
}
