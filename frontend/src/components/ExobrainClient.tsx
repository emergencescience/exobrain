"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface Message {
  role: "user" | "assistant";
  content: string;
  artifacts?: ComputationArtifact[];
}

interface ComputationArtifact {
  id: string;
  kind: string;
  status: VerificationStatus;
  title: string;
  summary: string;
  result?: Record<string, unknown>;
  provenance?: { engine?: string; operation?: string };
}

interface DocumentRecord {
  id: string;
  title: string;
  markdown: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

type VerificationStatus =
  | "verified"
  | "failed"
  | "candidate"
  | "inconclusive"
  | "insufficient_information"
  | "reasoned"
  | "error";

interface VerifyResult {
  claim_id: string;
  line: number;
  end_line: number;
  equation: string;
  status: VerificationStatus;
  detail: string;
  claim_type?: string;
  parent_claim_id?: string | null;
  edge_type?: string | null;
  assumption_claim_ids?: string[];
  crosses_paragraph?: boolean;
}

interface VerificationSnapshot {
  id: string;
  document_id?: string;
  content_hash: string;
  created_at: string;
}

interface Props {
  lang?: "en" | "zh";
  apiBaseUrl?: string;
}

type WorkspaceTab = "edit" | "preview" | "review";
type MobilePane = "project" | "document" | "assistant";

const COPY = {
  en: {
    product: "Exobrain",
    productKicker: "Symbol Science workspace",
    project: "Project",
    projects: "Projects",
    newDocument: "New document",
    newProject: "New project",
    noProjects: "No research documents yet",
    startProject: "Create a research note",
    documents: "Documents",
    researchTools: "Research tools",
    verificationRuns: "Verification runs",
    evidenceReports: "Evidence reports",
    activeDocument: "Active document",
    saved: "Saved",
    saving: "Saving",
    unsaved: "Unsaved changes",
    edit: "Edit",
    preview: "Preview",
    review: "Review",
    document: "Document",
    sourceHint: "Markdown and LaTeX source",
    previewHint: "Rendered scientific document",
    reviewHint: "Claims, evidence and verification scope",
    runVerification: "Run verification",
    rerunVerification: "Re-run verification",
    stale: "Source changed after this verification",
    current: "Current source",
    snapshot: "Verification snapshot",
    noVerification: "No verification run yet",
    noVerificationDescription:
      "Select a claim or run a bounded document verification. Results are anchored to the source and never rely on chat text alone.",
    verified: "Verified",
    failed: "Failed",
    candidate: "Candidate",
    inconclusive: "Inconclusive",
    insufficient_information: "Needs information",
    reasoned: "Reasoned",
    error: "Error",
    sourceRange: "Source",
    claim: "Claim",
    assumptions: "assumptions",
    evidence: "Evidence",
    assistant: "Exobrain assistant",
    assistantDescription:
      "Context-aware drafting and scientific reasoning. Deterministic checks remain the source of truth.",
    conversation: "Conversation",
    clearConversation: "Clear conversation",
    emptyConversation: "Start from your research question",
    emptyConversationDescription:
      "Ask for a derivation, refine the current draft, or request a bounded calculation. Your document remains the working source.",
    composePlaceholder: "Ask about this document or a scientific calculation…",
    send: "Send",
    working: "Working…",
    contextAttached: "Current document attached as context",
    exampleOne: "Draft a derivation with assumptions",
    exampleTwo: "Check the matrix result in this note",
    exampleThree: "Explain the limits of this conclusion",
    exampleFour: "Turn this result into a reviewable claim",
    status: "Status",
    noDocument: "Open or create a document to begin",
    noDocumentDescription:
      "A document is the primary research object. Chat helps you draft and review it; verification preserves evidence against an immutable snapshot.",
    createDocument: "Create document",
    delete: "Delete",
    download: "Export Markdown",
    copy: "Copy",
    copied: "Copied",
    documentTitle: "Untitled research note",
    draft: "Draft",
    reviewSummary: "Verification summary",
    claims: "claims",
    verifiedCount: "verified",
    issueCount: "need review",
    loading: "Loading workspace…",
    apiError: "The workspace could not reach Exobrain. Your local draft is still preserved.",
    chars: "characters",
    lines: "lines",
    editorPlaceholder: "Write a scientific claim, a derivation, or a Markdown / LaTeX research note…",
    assistantNotice: "The assistant can explain and propose. Only visible evidence can verify.",
    computation: "Deterministic computation",
    provenance: "Provenance",
  },
  zh: {
    product: "Exobrain",
    productKicker: "Symbol Science 工作区",
    project: "项目",
    projects: "项目",
    newDocument: "新建文档",
    newProject: "新建项目",
    noProjects: "还没有研究文档",
    startProject: "创建研究笔记",
    documents: "文档",
    researchTools: "研究工具",
    verificationRuns: "验证记录",
    evidenceReports: "证据报告",
    activeDocument: "当前文档",
    saved: "已保存",
    saving: "保存中",
    unsaved: "未保存更改",
    edit: "编辑",
    preview: "预览",
    review: "评审",
    document: "文档",
    sourceHint: "Markdown 与 LaTeX 源码",
    previewHint: "渲染后的科学文档",
    reviewHint: "主张、证据与验证范围",
    runVerification: "运行验证",
    rerunVerification: "重新验证",
    stale: "此后源文档已被修改",
    current: "当前源码",
    snapshot: "验证快照",
    noVerification: "尚未运行验证",
    noVerificationDescription:
      "选择一个主张，或运行受限的文档验证。结果锚定到源文档，绝不只依赖对话文本。",
    verified: "已验证",
    failed: "验证失败",
    candidate: "候选结果",
    inconclusive: "无法判定",
    insufficient_information: "信息不足",
    reasoned: "推理结果",
    error: "错误",
    sourceRange: "源码位置",
    claim: "主张",
    assumptions: "项假设",
    evidence: "证据",
    assistant: "Exobrain 助手",
    assistantDescription: "理解当前文档，用于起草与科学推理；确定性检查仍然是唯一事实来源。",
    conversation: "对话历史",
    clearConversation: "清空对话",
    emptyConversation: "从你的研究问题开始",
    emptyConversationDescription:
      "你可以请求推导、修改当前草稿，或发起受限计算。文档始终是工作中的源文件。",
    composePlaceholder: "针对当前文档或科学计算提出问题…",
    send: "发送",
    working: "处理中…",
    contextAttached: "当前文档会作为上下文附加",
    exampleOne: "起草包含假设的推导",
    exampleTwo: "检查笔记中的矩阵结果",
    exampleThree: "说明此结论的适用边界",
    exampleFour: "把结果整理为可评审主张",
    status: "状态",
    noDocument: "打开或创建一个文档以开始",
    noDocumentDescription:
      "文档是核心研究对象。对话帮助你起草和审阅；验证则把证据固定在不可变快照上。",
    createDocument: "创建文档",
    delete: "删除",
    download: "导出 Markdown",
    copy: "复制",
    copied: "已复制",
    documentTitle: "未命名研究笔记",
    draft: "草稿",
    reviewSummary: "验证摘要",
    claims: "条主张",
    verifiedCount: "已验证",
    issueCount: "需审阅",
    loading: "正在加载工作区…",
    apiError: "无法连接 Exobrain。你的本地草稿仍会被保留。",
    chars: "字符",
    lines: "行",
    editorPlaceholder: "撰写一条科学主张、推导，或 Markdown / LaTeX 研究笔记…",
    assistantNotice: "助手可以解释和提议；只有可见证据可以验证。",
    computation: "确定性计算",
    provenance: "溯源信息",
  },
} as const;

type Copy = { [Key in keyof typeof COPY.en]: string };

const DRAFT_STORAGE_KEY = "exobrain_workspace_draft_v2";
const CURRENT_PROJECT_KEY = "exobrain_current_project";

function defaultDocument(copy: Copy): string {
  return `# ${copy.documentTitle}\n\n## ${copy.claim}\n\nState the result you want to inspect. Keep assumptions, domains, units, and intermediate transformations explicit.\n\n## ${copy.evidence}\n\n$$\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$$\n\nAssumption: $x$ is real.\n`;
}

function readDraft(copy: Copy): { markdown: string; messages: Message[] } {
  if (typeof window === "undefined") return { markdown: defaultDocument(copy), messages: [] };
  try {
    const stored = localStorage.getItem(DRAFT_STORAGE_KEY);
    if (!stored) return { markdown: defaultDocument(copy), messages: [] };
    const parsed = JSON.parse(stored);
    return {
      markdown: typeof parsed.markdown === "string" ? parsed.markdown : defaultDocument(copy),
      messages: Array.isArray(parsed.messages) ? parsed.messages : [],
    };
  } catch {
    return { markdown: defaultDocument(copy), messages: [] };
  }
}

function statusMeta(status: VerificationStatus, copy: Copy) {
  const shared = "border";
  const values: Record<VerificationStatus, { label: string; className: string; dot: string }> = {
    verified: { label: copy.verified, className: `${shared} border-emerald-200 bg-emerald-50 text-emerald-800`, dot: "bg-emerald-500" },
    failed: { label: copy.failed, className: `${shared} border-rose-200 bg-rose-50 text-rose-800`, dot: "bg-rose-500" },
    candidate: { label: copy.candidate, className: `${shared} border-amber-200 bg-amber-50 text-amber-800`, dot: "bg-amber-500" },
    inconclusive: { label: copy.inconclusive, className: `${shared} border-amber-200 bg-amber-50 text-amber-800`, dot: "bg-amber-500" },
    insufficient_information: { label: copy.insufficient_information, className: `${shared} border-slate-200 bg-slate-50 text-slate-700`, dot: "bg-slate-400" },
    reasoned: { label: copy.reasoned, className: `${shared} border-sky-200 bg-sky-50 text-sky-800`, dot: "bg-sky-500" },
    error: { label: copy.error, className: `${shared} border-rose-200 bg-rose-50 text-rose-800`, dot: "bg-rose-500" },
  };
  return values[status] || values.error;
}

function displayEquation(equation: string) {
  return equation.replace(/^\$\$?\s?/, "").replace(/\s?\$\$?$/, "");
}

function markdownDocumentFromReply(reply: string): string | undefined {
  const match = reply.match(/```markdown\s*\n([\s\S]*?)\n```/i);
  return match?.[1]?.trim();
}

function formatDate(value?: string, locale = "en") {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function editorSelectionStart(markdown: string, line: number) {
  const lines = markdown.split("\n");
  return lines.slice(0, Math.max(0, line - 1)).reduce((total, item) => total + item.length + 1, 0);
}

export default function ExobrainClient({
  lang = "en",
  apiBaseUrl = process.env.NEXT_PUBLIC_EXOBRAIN_API_URL || "http://localhost:8080",
}: Props) {
  const copy: Copy = COPY[lang];
  const initialDraft = useMemo(() => readDraft(copy), [copy]);
  const [projects, setProjects] = useState<DocumentRecord[]>([]);
  const [currentDocId, setCurrentDocId] = useState<string | null>(null);
  const [documentTitle, setDocumentTitle] = useState<string>(copy.documentTitle);
  const [markdown, setMarkdown] = useState(initialDraft.markdown);
  const [messages, setMessages] = useState<Message[]>(initialDraft.messages);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("edit");
  const [mobilePane, setMobilePane] = useState<MobilePane>("document");
  const [verifyResults, setVerifyResults] = useState<VerifyResult[]>([]);
  const [verificationSnapshot, setVerificationSnapshot] = useState<VerificationSnapshot | null>(null);
  const [verifiedMarkdown, setVerifiedMarkdown] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [saveState, setSaveState] = useState<"saved" | "saving" | "unsaved">("saved");
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const conversationRef = useRef<HTMLDivElement>(null);

  const markdownPlugins = useMemo(() => [remarkMath], []);
  const htmlPlugins = useMemo(() => [rehypeKatex], []);
  const stale = Boolean(verificationSnapshot && verifiedMarkdown !== markdown);
  const verifiedCount = verifyResults.filter((result) => result.status === "verified").length;
  const reviewCount = verifyResults.filter((result) => result.status !== "verified").length;

  const persistDraft = useCallback((nextMarkdown: string, nextMessages: Message[]) => {
    try {
      localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify({ markdown: nextMarkdown, messages: nextMessages }));
    } catch {
      // Draft persistence is intentionally best effort.
    }
  }, []);

  const fetchProjects = useCallback(async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/documents`);
      if (!response.ok) return;
      const data = await response.json();
      setProjects(data.documents || []);
    } catch {
      // Local drafts remain available when the backend is offline.
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    persistDraft(markdown, messages);
  }, [markdown, messages, persistDraft]);

  useEffect(() => {
    conversationRef.current?.scrollTo({ top: conversationRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const openProject = useCallback((project: DocumentRecord) => {
    setCurrentDocId(project.id);
    setDocumentTitle(project.title || copy.documentTitle);
    setMarkdown(project.markdown || defaultDocument(copy));
    setMessages(project.messages || []);
    setVerifyResults([]);
    setVerificationSnapshot(null);
    setVerifiedMarkdown(null);
    setSaveState("saved");
    setWorkspaceError(null);
    setMobilePane("document");
    try {
      localStorage.setItem(CURRENT_PROJECT_KEY, JSON.stringify({ id: project.id }));
    } catch {
      // Best-effort convenience only.
    }
  }, [copy]);

  const createProject = useCallback(async () => {
    setWorkspaceError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: copy.documentTitle }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const project = data.document as DocumentRecord;
      setProjects((previous) => [project, ...previous]);
      openProject(project);
    } catch {
      setWorkspaceError(copy.apiError);
    }
  }, [apiBaseUrl, copy, openProject]);

  const deleteProject = useCallback(async (project: DocumentRecord) => {
    if (!window.confirm(`${copy.delete}: ${project.title}?`)) return;
    try {
      const response = await fetch(`${apiBaseUrl}/api/documents/${project.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setProjects((previous) => previous.filter((item) => item.id !== project.id));
      if (currentDocId === project.id) {
        setCurrentDocId(null);
        setDocumentTitle(copy.documentTitle);
        setMarkdown(defaultDocument(copy));
        setMessages([]);
        setVerifyResults([]);
        setVerificationSnapshot(null);
        setVerifiedMarkdown(null);
      }
    } catch {
      setWorkspaceError(copy.apiError);
    }
  }, [apiBaseUrl, copy, currentDocId]);

  const saveDocument = useCallback(async () => {
    if (!currentDocId) return;
    setSaveState("saving");
    try {
      const response = await fetch(`${apiBaseUrl}/api/documents/${currentDocId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown, messages, title: documentTitle || copy.documentTitle }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const updated = data.document as DocumentRecord;
      setProjects((previous) => previous.map((item) => (item.id === updated.id ? updated : item)));
      setSaveState("saved");
    } catch {
      setSaveState("unsaved");
      setWorkspaceError(copy.apiError);
    }
  }, [apiBaseUrl, copy.documentTitle, currentDocId, documentTitle, markdown, messages]);

  useEffect(() => {
    if (!currentDocId || saveState !== "unsaved") return;
    const timer = window.setTimeout(() => void saveDocument(), 900);
    return () => window.clearTimeout(timer);
  }, [currentDocId, markdown, messages, documentTitle, saveDocument, saveState]);

  const changeMarkdown = (nextMarkdown: string) => {
    setMarkdown(nextMarkdown);
    setSaveState(currentDocId ? "unsaved" : "saved");
  };

  const focusSourceLine = (line: number) => {
    setWorkspaceTab("edit");
    window.setTimeout(() => {
      const editor = editorRef.current;
      if (!editor) return;
      const start = editorSelectionStart(markdown, line);
      const end = markdown.indexOf("\n", start);
      editor.focus();
      editor.setSelectionRange(start, end === -1 ? markdown.length : end);
      editor.scrollTop = Math.max(0, (line - 3) * 24);
    }, 0);
  };

  const verifyDocument = async () => {
    setVerifying(true);
    setWorkspaceError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: currentDocId || undefined, markdown, locale: lang }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setVerifyResults(data.results || []);
      setVerificationSnapshot(data.snapshot || null);
      setVerifiedMarkdown(markdown);
      setWorkspaceTab("review");
      setMobilePane("document");
    } catch {
      setWorkspaceError(copy.apiError);
    } finally {
      setVerifying(false);
    }
  };

  const sendMessage = async (preset?: string) => {
    const text = (preset || input).trim();
    if (!text || loading) return;
    const nextMessages: Message[] = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    setWorkspaceError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: nextMessages.map(({ role, content }) => ({ role, content })),
          document: markdown,
          doc_id: currentDocId || undefined,
          locale: lang,
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const reply = data.reply || copy.apiError;
      const updatedDocument = data.document || markdownDocumentFromReply(reply);
      const assistantMessage: Message = {
        role: "assistant",
        content: reply,
        artifacts: Array.isArray(data.artifacts) ? data.artifacts : [],
      };
      const finalMessages = [...nextMessages, assistantMessage];
      setMessages(finalMessages);
      if (updatedDocument) changeMarkdown(updatedDocument);
      else setSaveState(currentDocId ? "unsaved" : "saved");
    } catch {
      setMessages([...nextMessages, { role: "assistant", content: copy.apiError }]);
      setWorkspaceError(copy.apiError);
    } finally {
      setLoading(false);
    }
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void sendMessage();
    }
  };

  const exportMarkdown = () => {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(documentTitle || copy.documentTitle).replace(/[^a-z0-9-_]+/gi, "-").toLowerCase()}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const copyMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1300);
    } catch {
      setWorkspaceError(copy.apiError);
    }
  };

  const currentProject = projects.find((project) => project.id === currentDocId) || null;
  const showWorkspace = Boolean(currentDocId || currentProject);

  return (
    <main className="min-h-screen bg-[#f7f8fa] text-slate-900 selection:bg-indigo-100">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/95 px-3 backdrop-blur lg:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-600 text-sm font-semibold text-white">S</div>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-semibold tracking-tight text-slate-950">{copy.product}</p>
            <p className="hidden text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400 sm:block">{copy.productKicker}</p>
          </div>
          {showWorkspace && (
            <>
              <span className="hidden text-slate-300 md:block">/</span>
              <span className="hidden max-w-[260px] truncate text-sm text-slate-600 md:block">{documentTitle || copy.documentTitle}</span>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          {showWorkspace && (
            <span className={`hidden items-center gap-1.5 text-xs sm:flex ${saveState === "saved" ? "text-slate-500" : saveState === "saving" ? "text-indigo-600" : "text-amber-700"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${saveState === "saved" ? "bg-emerald-500" : saveState === "saving" ? "bg-indigo-500" : "bg-amber-500"}`} />
              {saveState === "saved" ? copy.saved : saveState === "saving" ? copy.saving : copy.unsaved}
            </span>
          )}
          <button onClick={exportMarkdown} disabled={!showWorkspace} className="hidden rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-40 sm:block">
            {copy.download}
          </button>
          <button onClick={() => void createProject()} className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-500">
            {copy.newDocument}
          </button>
        </div>
      </header>

      <div className="border-b border-slate-200 bg-white px-3 py-1.5 lg:hidden">
        <div className="grid grid-cols-3 rounded-md bg-slate-100 p-0.5">
          {(["project", "document", "assistant"] as MobilePane[]).map((pane) => (
            <button key={pane} onClick={() => setMobilePane(pane)} className={`rounded px-2 py-1.5 text-xs font-medium transition ${mobilePane === pane ? "bg-white text-slate-950 shadow-sm" : "text-slate-500"}`}>
              {pane === "project" ? copy.projects : pane === "document" ? copy.document : copy.assistant}
            </button>
          ))}
        </div>
      </div>

      {workspaceError && (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
          {workspaceError}
          <button className="ml-3 font-semibold underline" onClick={() => setWorkspaceError(null)}>×</button>
        </div>
      )}

      <div className="lg:grid lg:h-[calc(100vh-56px)] lg:grid-cols-[248px_minmax(0,1fr)_360px] lg:overflow-hidden">
        <aside className={`${mobilePane === "project" ? "flex" : "hidden"} min-h-[calc(100vh-102px)] flex-col border-r border-slate-200 bg-[#fbfcfd] lg:flex lg:min-h-0`}>
          <div className="flex items-center justify-between border-b border-slate-200 px-3 py-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{copy.project}</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-800">{copy.projects}</p>
            </div>
            <button onClick={() => void createProject()} aria-label={copy.newProject} className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-lg font-light text-slate-600 transition hover:border-indigo-200 hover:text-indigo-700">+</button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 py-3">
            <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{copy.documents}</p>
            {projects.length === 0 ? (
              <button onClick={() => void createProject()} className="w-full rounded-lg border border-dashed border-slate-300 bg-white px-3 py-5 text-left transition hover:border-indigo-300 hover:bg-indigo-50/40">
                <p className="text-xs font-semibold text-slate-700">{copy.noProjects}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{copy.startProject}</p>
              </button>
            ) : (
              <div className="space-y-1">
                {projects.map((project) => {
                  const active = project.id === currentDocId;
                  return (
                    <div key={project.id} className={`group flex items-center gap-2 rounded-md border px-2 py-2 transition ${active ? "border-indigo-200 bg-indigo-50" : "border-transparent hover:bg-slate-100"}`}>
                      <button onClick={() => openProject(project)} className="min-w-0 flex-1 text-left">
                        <p className={`truncate text-xs font-medium ${active ? "text-indigo-900" : "text-slate-700"}`}>{project.title || copy.documentTitle}</p>
                        <p className="mt-0.5 truncate text-[10px] text-slate-400">{formatDate(project.updated_at, lang)}</p>
                      </button>
                      <button onClick={() => void deleteProject(project)} aria-label={`${copy.delete} ${project.title}`} className="hidden rounded p-1 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 group-hover:block">×</button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="border-t border-slate-200 px-3 py-3">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{copy.researchTools}</p>
            <div className="space-y-1 text-xs text-slate-600">
              <div className="flex items-center justify-between rounded-md px-2 py-1.5"><span>{copy.verificationRuns}</span><span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{verificationSnapshot ? "1" : "0"}</span></div>
              <div className="flex items-center justify-between rounded-md px-2 py-1.5"><span>{copy.evidenceReports}</span><span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{verifyResults.length}</span></div>
            </div>
          </div>
        </aside>

        <section className={`${mobilePane === "document" ? "flex" : "hidden"} min-h-[calc(100vh-102px)] min-w-0 flex-col bg-white lg:flex lg:min-h-0`}>
          {!showWorkspace ? (
            <EmptyDocumentState copy={copy} onCreate={() => void createProject()} />
          ) : (
            <>
              <div className="border-b border-slate-200 bg-white px-4 pt-3 lg:px-5">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <input value={documentTitle} onChange={(event) => { setDocumentTitle(event.target.value); setSaveState("unsaved"); }} onBlur={() => void saveDocument()} aria-label={copy.activeDocument} className="w-full truncate border-0 bg-transparent px-0 text-base font-semibold text-slate-900 outline-none placeholder:text-slate-400" placeholder={copy.documentTitle} />
                    <p className="mt-0.5 text-xs text-slate-400">{workspaceTab === "edit" ? copy.sourceHint : workspaceTab === "preview" ? copy.previewHint : copy.reviewHint}</p>
                  </div>
                  <button onClick={copyMarkdown} className="rounded-md border border-slate-200 px-2 py-1 text-[11px] font-medium text-slate-600 transition hover:bg-slate-50">{copied ? copy.copied : copy.copy}</button>
                </div>
                <div className="mt-4 flex items-center gap-4">
                  {([
                    ["edit", copy.edit],
                    ["preview", copy.preview],
                    ["review", copy.review],
                  ] as [WorkspaceTab, string][]).map(([tab, label]) => (
                    <button key={tab} onClick={() => setWorkspaceTab(tab)} className={`border-b-2 px-0.5 pb-2 text-xs font-semibold transition ${workspaceTab === tab ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{label}</button>
                  ))}
                  <span className="ml-auto pb-2 text-[11px] text-slate-400">{markdown.split("\n").length} {copy.lines} · {markdown.length.toLocaleString()} {copy.chars}</span>
                </div>
              </div>

              {workspaceTab === "edit" && (
                <div className="flex min-h-0 flex-1 flex-col">
                  <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2 lg:px-5">
                    <span className="text-[11px] font-medium text-slate-500">{copy.current}</span>
                    <span className="text-[11px] text-slate-400">Markdown · LaTeX</span>
                  </div>
                  <textarea ref={editorRef} value={markdown} onChange={(event) => changeMarkdown(event.target.value)} onBlur={() => void saveDocument()} spellCheck={false} placeholder={copy.editorPlaceholder} className="min-h-[480px] flex-1 resize-none border-0 bg-[#fcfcfd] px-5 py-5 font-mono text-[13px] leading-6 text-slate-700 outline-none placeholder:text-slate-300 lg:px-7" />
                </div>
              )}

              {workspaceTab === "preview" && (
                <div className="min-h-0 flex-1 overflow-y-auto bg-[#fcfcfd] px-5 py-7 lg:px-10">
                  <article className="exobrain-prose mx-auto max-w-3xl">
                    <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>{markdown}</ReactMarkdown>
                  </article>
                </div>
              )}

              {workspaceTab === "review" && (
                <ReviewPanel copy={copy} results={verifyResults} snapshot={verificationSnapshot} stale={stale} verifying={verifying} onVerify={() => void verifyDocument()} onFocusSource={focusSourceLine} />
              )}
            </>
          )}
        </section>

        <aside className={`${mobilePane === "assistant" ? "flex" : "hidden"} min-h-[calc(100vh-102px)] flex-col border-l border-slate-200 bg-[#fbfcfd] lg:flex lg:min-h-0`}>
          <div className="border-b border-slate-200 bg-white px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-100 text-xs font-semibold text-indigo-700">E</span>
                <div>
                  <p className="text-sm font-semibold text-slate-800">{copy.assistant}</p>
                  <p className="text-[10px] font-medium text-emerald-600">{copy.contextAttached}</p>
                </div>
              </div>
              <button onClick={() => { setMessages([]); setSaveState(currentDocId ? "unsaved" : "saved"); }} className="text-[11px] font-medium text-slate-400 transition hover:text-slate-700">{copy.clearConversation}</button>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-500">{copy.assistantDescription}</p>
          </div>

          <div ref={conversationRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {messages.length === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-800">{copy.emptyConversation}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{copy.emptyConversationDescription}</p>
                <div className="mt-4 space-y-2">
                  {[copy.exampleOne, copy.exampleTwo, copy.exampleThree, copy.exampleFour].map((example) => (
                    <button key={example} onClick={() => void sendMessage(example)} className="block w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-800">{example}</button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => <ChatMessage key={`${message.role}-${index}`} message={message} copy={copy} markdownPlugins={markdownPlugins} htmlPlugins={htmlPlugins} />)
            )}
            {loading && (
              <div className="flex items-center gap-2 text-xs text-slate-500"><span className="flex gap-1"><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400" /><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:120ms]" /><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:240ms]" /></span>{copy.working}</div>
            )}
          </div>

          <div className="border-t border-slate-200 bg-white p-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-2 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100">
              <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={handleComposerKeyDown} rows={3} placeholder={copy.composePlaceholder} className="w-full resize-none border-0 bg-transparent px-1 py-1 text-xs leading-5 text-slate-700 outline-none placeholder:text-slate-400" />
              <div className="mt-1 flex items-center justify-between gap-2 px-1">
                <span className="text-[10px] text-slate-400">⌘ / Ctrl + Enter</span>
                <button onClick={() => void sendMessage()} disabled={!input.trim() || loading} className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40">{copy.send}</button>
              </div>
            </div>
            <p className="mt-2 text-[10px] leading-4 text-slate-400">{copy.assistantNotice}</p>
          </div>
        </aside>
      </div>
    </main>
  );
}

function EmptyDocumentState({ copy, onCreate }: { copy: Copy; onCreate: () => void }) {
  return (
    <div className="flex flex-1 items-center justify-center bg-[#fcfcfd] p-6">
      <div className="max-w-md text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-100 text-lg font-semibold text-indigo-700">E</div>
        <h1 className="mt-5 text-xl font-semibold tracking-tight text-slate-900">{copy.noDocument}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">{copy.noDocumentDescription}</p>
        <button onClick={onCreate} className="mt-6 rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500">{copy.createDocument}</button>
      </div>
    </div>
  );
}

function ReviewPanel({
  copy,
  results,
  snapshot,
  stale,
  verifying,
  onVerify,
  onFocusSource,
}: {
  copy: Copy;
  results: VerifyResult[];
  snapshot: VerificationSnapshot | null;
  stale: boolean;
  verifying: boolean;
  onVerify: () => void;
  onFocusSource: (line: number) => void;
}) {
  const verified = results.filter((result) => result.status === "verified").length;
  const needsReview = results.length - verified;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-[#fcfcfd] p-4 lg:p-5">
      <div className="mx-auto max-w-4xl">
        <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div>
            <p className="text-sm font-semibold text-slate-800">{copy.reviewSummary}</p>
            {snapshot ? <p className="mt-1 text-xs text-slate-500">{copy.snapshot} · {formatDate(snapshot.created_at)}</p> : <p className="mt-1 text-xs text-slate-500">{copy.noVerification}</p>}
            {stale && <p className="mt-2 inline-flex rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">{copy.stale}</p>}
          </div>
          <button onClick={onVerify} disabled={verifying} className="rounded-md bg-indigo-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50">
            {verifying ? copy.working : snapshot ? copy.rerunVerification : copy.runVerification}
          </button>
        </div>

        {results.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-white p-7 text-center">
            <p className="text-sm font-semibold text-slate-700">{copy.noVerification}</p>
            <p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-slate-500">{copy.noVerificationDescription}</p>
          </div>
        ) : (
          <>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <SummaryCard label={copy.claims} value={String(results.length)} detail={copy.reviewSummary} />
              <SummaryCard label={copy.verifiedCount} value={String(verified)} detail={`${Math.round((verified / Math.max(results.length, 1)) * 100)}%`} tone="emerald" />
              <SummaryCard label={copy.issueCount} value={String(needsReview)} detail={stale ? copy.stale : copy.current} tone={needsReview ? "amber" : "slate"} />
            </div>
            <div className="mt-4 space-y-3">
              {results.map((result) => {
                const meta = statusMeta(result.status, copy);
                return (
                  <article key={result.claim_id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[10px] font-semibold ${meta.className}`}><span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />{meta.label}</span>
                          <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">{result.claim_type || copy.claim}</span>
                        </div>
                        <div className="mt-3 overflow-x-auto rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700"><span className="text-slate-400">{copy.claim}: </span>{displayEquation(result.equation)}</div>
                        <p className="mt-3 text-xs leading-5 text-slate-600">{result.detail}</p>
                        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-400">
                          <span>{copy.sourceRange} L{result.line}{result.end_line !== result.line ? `–${result.end_line}` : ""}</span>
                          {result.assumption_claim_ids?.length ? <span>{result.assumption_claim_ids.length} {copy.assumptions}</span> : null}
                          {result.parent_claim_id ? <span>{copy.provenance}</span> : null}
                        </div>
                      </div>
                      <button onClick={() => onFocusSource(result.line)} className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700">{copy.sourceRange}</button>
                    </div>
                  </article>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ label, value, detail, tone = "slate" }: { label: string; value: string; detail: string; tone?: "slate" | "emerald" | "amber" }) {
  const colors = {
    slate: "border-slate-200 bg-white text-slate-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
  };
  return <div className={`rounded-lg border p-3 ${colors[tone]}`}><p className="text-[10px] font-semibold uppercase tracking-[0.11em] opacity-60">{label}</p><div className="mt-1 flex items-end justify-between gap-2"><p className="text-xl font-semibold tracking-tight">{value}</p><p className="pb-0.5 text-[10px] opacity-60">{detail}</p></div></div>;
}

function ChatMessage({
  message,
  copy,
  markdownPlugins,
  htmlPlugins,
}: {
  message: Message;
  copy: Copy;
  markdownPlugins: typeof remarkMath[];
  htmlPlugins: typeof rehypeKatex[];
}) {
  const user = message.role === "user";
  return (
    <article className={`flex ${user ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[94%] rounded-xl px-3 py-2.5 text-xs leading-5 shadow-sm ${user ? "bg-indigo-600 text-white" : "border border-slate-200 bg-white text-slate-700"}`}>
        {!user && <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-indigo-600">{copy.product}</p>}
        {user ? <p className="whitespace-pre-wrap">{message.content}</p> : <div className="exobrain-chat-prose"><ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>{message.content.replace(/```markdown\s*\n[\s\S]*?\n```/i, "")}</ReactMarkdown></div>}
        {message.artifacts?.map((artifact) => {
          const meta = statusMeta(artifact.status, copy);
          return (
            <div key={artifact.id} className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-slate-700">
              <div className="flex items-center justify-between gap-2"><p className="text-[11px] font-semibold">{artifact.title || copy.computation}</p><span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${meta.className}`}><span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />{meta.label}</span></div>
              <p className="mt-1 text-[11px] leading-4 text-slate-500">{artifact.summary}</p>
              {artifact.provenance?.engine && <p className="mt-2 text-[9px] font-medium uppercase tracking-[0.1em] text-slate-400">{artifact.provenance.engine} · {artifact.provenance.operation}</p>}
            </div>
          );
        })}
      </div>
    </article>
  );
}
