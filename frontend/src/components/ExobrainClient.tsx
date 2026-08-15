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
import RenderedMath from "@/components/RenderedMath";

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
  | "partially_checked"
  | "inconclusive"
  | "insufficient_information"
  | "reasoned"
  | "semantically_reviewed"
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

interface VerificationScope {
  kind: "document" | "block" | "claim";
  start_line?: number;
  end_line?: number;
  claim_id?: string | null;
}

interface ProofStep {
  id: string;
  kind: "assumption" | "definition" | "statement" | "derivation_step" | "theorem_application" | "conclusion";
  text: string;
  source: { start_line: number; end_line: number };
  local_status: "locally_verified" | "partially_checked" | "semantically_reviewed" | "inconclusive" | "failed" | "not_checked" | "not_required";
  fragment_id: string;
  is_formula?: boolean;
  semantic_role?: "definition" | "hypothesis" | "lemma" | "deduction" | "conclusion";
  verification_target?: "none" | "sympy" | "rule";
  semantic_rule_id?: string;
  semantic_rationale?: string;
}
interface ProofDependency {
  id: string;
  from_step_id: string;
  to_step_id: string;
  kind: "derives" | "requires_assumption" | "formula_transform" | "uses_definition" | "justifies" | "substitutes_result";
  edge_status: "not_checked" | "declared" | "semantically_reviewed" | "verified" | "verified_under_assumptions" | "failed";
  reason: string;
  review_visible?: boolean;
  validator?: {
    id: string;
    label: string;
    status: "verified" | "verified_under_assumptions";
    method: string;
    evidence: Record<string, string | string[]>;
  };
}
interface ProofFragment {
  id: string;
  title: string;
  kind: "assumptions" | "claim" | "derivation" | "context";
  source: { start_line: number; end_line: number };
  steps: ProofStep[];
}
interface ProofGraph {
  schema_version: string;
  fragments: ProofFragment[];
  dependencies: ProofDependency[];
  limitations?: string[];
  semantic_proposal?: {
    status: "proposed" | "unavailable";
    reason?: string;
    notice?: string;
    model?: string;
  };
}
interface VerificationSnapshot {
  id: string;
  document_id?: string;
  markdown?: string;
  content_hash: string;
  verification_results?: VerifyResult[];
  verification_scope?: VerificationScope;
  proof_graph?: ProofGraph;
  created_at: string;
}

interface EvidenceLink {
  id: string;
  claim_id: string;
  artifact_id: string;
  code_hash: string;
  stdout: string;
  stderr: string;
  exit_code: number;
  created_at: string;
}

type SourceScope = Required<Pick<VerificationScope, "start_line" | "end_line">> &
  Pick<VerificationScope, "claim_id"> & { kind: "block" | "claim" };

interface Props {
  lang?: "en" | "zh";
  apiBaseUrl?: string;
}

type WorkspaceTab = "edit" | "preview" | "label" | "review";
type MobilePane = "project" | "document" | "assistant";

const COPY = {
  en: {
    product: "Exobrain",
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
    label: "Label",
    document: "Document",
    sourceHint: "Markdown and LaTeX source",
    previewHint: "Rendered scientific document",
    reviewHint: "Claims, evidence and verification scope",
    labelHint: "Rendered document with source-anchored verification markers",
    labelEmpty: "Run verification to add claim markers to the rendered document.",
    labelLegend: "Claim markers",
    openEvidence: "Open verification result",
    closeEvidence: "Close result",
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
    partiallyChecked: "Partially checked",
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
    label: "标注",
    document: "文档",
    sourceHint: "Markdown 与 LaTeX 源码",
    previewHint: "渲染后的科学文档",
    reviewHint: "主张、证据与验证范围",
    labelHint: "与正文同步的验证标注阅读层",
    labelEmpty: "运行验证后，正文会显示可点击的主张标记。",
    labelLegend: "主张标记",
    openEvidence: "打开验证结果",
    closeEvidence: "关闭结果",
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
    partiallyChecked: "已部分验证",
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
    partially_checked: { label: copy.partiallyChecked, className: `${shared} border-amber-200 bg-amber-50 text-amber-800`, dot: "bg-amber-500" },
    inconclusive: { label: copy.inconclusive, className: `${shared} border-amber-200 bg-amber-50 text-amber-800`, dot: "bg-amber-500" },
    insufficient_information: { label: copy.insufficient_information, className: `${shared} border-slate-200 bg-slate-50 text-slate-700`, dot: "bg-slate-400" },
    reasoned: { label: copy.reasoned, className: `${shared} border-sky-200 bg-sky-50 text-sky-800`, dot: "bg-sky-500" },
    semantically_reviewed: { label: copy.reasoned, className: `${shared} border-sky-200 bg-sky-50 text-sky-800`, dot: "bg-sky-500" },
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

function sourceLineAtOffset(markdown: string, offset: number) {
  return markdown.slice(0, Math.max(0, offset)).split("\n").length;
}

function scopeLabel(scope: VerificationScope | undefined, lang: "en" | "zh") {
  if (!scope || scope.kind === "document") return lang === "zh" ? "整篇文档" : "Whole document";
  const range = `L${scope.start_line}–${scope.end_line}`;
  if (scope.kind === "claim") return lang === "zh" ? `主张 · ${range}` : `Claim · ${range}`;
  return lang === "zh" ? `选中区块 · ${range}` : `Selected block · ${range}`;
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
  const [labelFocusLine, setLabelFocusLine] = useState<number | null>(null);
  const [mobilePane, setMobilePane] = useState<MobilePane>("document");
  const [verifyResults, setVerifyResults] = useState<VerifyResult[]>([]);
  const [verificationSnapshot, setVerificationSnapshot] = useState<VerificationSnapshot | null>(null);
  const [verificationSnapshots, setVerificationSnapshots] = useState<VerificationSnapshot[]>([]);
  const [evidenceLinks, setEvidenceLinks] = useState<EvidenceLink[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<SourceScope | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [verifiedMarkdown, setVerifiedMarkdown] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [saveState, setSaveState] = useState<"saved" | "saving" | "unsaved">("saved");
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [projectMenuId, setProjectMenuId] = useState<string | null>(null);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const conversationRef = useRef<HTMLDivElement>(null);

  const markdownPlugins = useMemo(() => [remarkMath], []);
  const htmlPlugins = useMemo(() => [rehypeKatex], []);
  const stale = Boolean(verificationSnapshot && verifiedMarkdown !== markdown);
  const verifiedCount = verifyResults.filter((result) => result.status === "verified").length;
  const reviewCount = verifyResults.filter((result) => result.status !== "verified").length;

  const loadEvidence = useCallback(async (documentId: string, snapshotId: string) => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/evidence/${snapshotId}?document_id=${documentId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setEvidenceLinks(data.evidence || []);
    } catch {
      setEvidenceLinks([]);
    }
  }, [apiBaseUrl]);

  const activateSnapshot = useCallback(async (documentId: string, snapshot: VerificationSnapshot) => {
    setVerificationSnapshot(snapshot);
    setVerifyResults(snapshot.verification_results || []);
    setVerifiedMarkdown(snapshot.markdown || null);
    setSelectedClaimId(snapshot.verification_results?.find((item) => item.claim_type !== "assumption")?.claim_id || null);
    await loadEvidence(documentId, snapshot.id);
  }, [loadEvidence]);

  const loadReviewContext = useCallback(async (documentId: string, preferredSnapshotId?: string) => {
    setSnapshotLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}/snapshots`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const snapshots = (data.snapshots || []) as VerificationSnapshot[];
      setVerificationSnapshots(snapshots);
      const active = snapshots.find((item) => item.id === preferredSnapshotId) || snapshots[0];
      if (active) await activateSnapshot(documentId, active);
      else {
        setVerificationSnapshot(null);
        setVerifyResults([]);
        setEvidenceLinks([]);
        setVerifiedMarkdown(null);
      }
    } catch {
      setVerificationSnapshots([]);
      setEvidenceLinks([]);
    } finally {
      setSnapshotLoading(false);
    }
  }, [activateSnapshot, apiBaseUrl]);

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
    setVerificationSnapshots([]);
    setEvidenceLinks([]);
    setSelectedClaimId(null);
    setSelectedBlock(null);
    setVerifiedMarkdown(null);
    setSaveState("saved");
    void loadReviewContext(project.id);
    setWorkspaceError(null);
    setMobilePane("document");
    try {
      localStorage.setItem(CURRENT_PROJECT_KEY, JSON.stringify({ id: project.id }));
    } catch {
      // Best-effort convenience only.
    }
  }, [copy, loadReviewContext]);

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

  const startRenameProject = useCallback((project: DocumentRecord) => {
    setRenamingProjectId(project.id);
    setRenameTitle(project.title || copy.documentTitle);
    setProjectMenuId(null);
  }, [copy.documentTitle]);
  const commitRenameProject = useCallback(async (project: DocumentRecord) => {
    const title = renameTitle.trim() || copy.documentTitle;
    setRenamingProjectId(null);
    if (title === project.title) return;
    try {
      const response = await fetch(`${apiBaseUrl}/api/documents/${project.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const updated = data.document as DocumentRecord;
      setProjects((previous) => previous.map((item) => (item.id === updated.id ? updated : item)));
      if (currentDocId === updated.id) setDocumentTitle(updated.title);
    } catch {
      setWorkspaceError(copy.apiError);
    }
  }, [apiBaseUrl, copy.apiError, copy.documentTitle, currentDocId, renameTitle]);
  const duplicateProject = useCallback(async (project: DocumentRecord) => {
    try {
      const title = lang === "zh" ? `${project.title || copy.documentTitle} 副本` : `${project.title || copy.documentTitle} copy`;
      const createdResponse = await fetch(`${apiBaseUrl}/api/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!createdResponse.ok) throw new Error(`HTTP ${createdResponse.status}`);
      const created = (await createdResponse.json()).document as DocumentRecord;
      const copiedResponse = await fetch(`${apiBaseUrl}/api/documents/${created.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown: project.markdown, messages: project.messages, title }),
      });
      if (!copiedResponse.ok) throw new Error(`HTTP ${copiedResponse.status}`);
      const duplicated = (await copiedResponse.json()).document as DocumentRecord;
      setProjects((previous) => [duplicated, ...previous]);
      setProjectMenuId(null);
      openProject(duplicated);
    } catch {
      setWorkspaceError(copy.apiError);
    }
  }, [apiBaseUrl, copy.apiError, copy.documentTitle, lang, openProject]);
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
        setVerificationSnapshots([]);
        setEvidenceLinks([]);
        setSelectedClaimId(null);
        setSelectedBlock(null);
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
    setLabelFocusLine(line);
    setWorkspaceTab("label");
  };

  const captureSourceSelection = () => {
    const editor = editorRef.current;
    if (!editor || editor.selectionStart === editor.selectionEnd) {
      setSelectedBlock(null);
      return;
    }
    const startLine = sourceLineAtOffset(markdown, editor.selectionStart);
    const endLine = sourceLineAtOffset(markdown, Math.max(editor.selectionStart, editor.selectionEnd - 1));
    setSelectedBlock({ kind: "block", start_line: startLine, end_line: endLine });
  };

  const verifyDocument = async (scope?: SourceScope) => {
    setVerifying(true);
    setWorkspaceError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: currentDocId || undefined, markdown, locale: lang, scope, semantic_parse: true }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const snapshot = data.snapshot as VerificationSnapshot | null;
      const responseResults = (snapshot?.verification_results || data.results || []) as VerifyResult[];
      setVerifyResults(responseResults);
      setVerificationSnapshot(snapshot);
      setVerifiedMarkdown(markdown);
      setSelectedClaimId(scope?.claim_id || responseResults.find((item) => item.claim_type !== "assumption")?.claim_id || null);
      if (snapshot && currentDocId) await loadReviewContext(currentDocId, snapshot.id);
      else {
        setEvidenceLinks([]);
        setVerificationSnapshots(snapshot ? [snapshot] : []);
      }
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

  const downloadProject = useCallback((project: DocumentRecord) => {
    const isCurrentDocument = project.id === currentDocId;
    const content = isCurrentDocument ? markdown : project.markdown;
    const title = isCurrentDocument ? (documentTitle || copy.documentTitle) : (project.title || copy.documentTitle);
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title.replace(/[^a-z0-9-_]+/gi, "-").toLowerCase()}.md`;
    link.click();
    URL.revokeObjectURL(url);
    setProjectMenuId(null);
  }, [copy.documentTitle, currentDocId, documentTitle, markdown]);


  const currentProject = projects.find((project) => project.id === currentDocId) || null;
  const showWorkspace = Boolean(currentDocId || currentProject);

  return (
    <main className="min-h-screen bg-[#f7f8fa] text-slate-900 selection:bg-indigo-100">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/95 px-3 backdrop-blur lg:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-indigo-600 text-sm font-semibold text-white">S</div>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-semibold tracking-tight text-slate-950">{copy.product}</p>
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
          <a href="/dashboard" className="hidden rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 sm:block">
            {lang === "zh" ? "验证仪表板" : "Verification dashboard"}
          </a>
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
                  const renaming = project.id === renamingProjectId;
                  const menuOpen = project.id === projectMenuId;
                  const menuLabels = lang === "zh"
                    ? { actions: "文档操作", download: "下载", rename: "重命名", duplicate: "创建副本", delete: "删除" }
                    : { actions: "Actions", download: "Download", rename: "Rename", duplicate: "Duplicate", delete: "Delete" };
                  return (
                    <div key={project.id} onContextMenu={(event) => { event.preventDefault(); setProjectMenuId(menuOpen ? null : project.id); }} onKeyDown={(event) => { if (active && event.key === "F2") { event.preventDefault(); startRenameProject(project); } }} className={`group relative flex items-center gap-2 rounded-md border px-2 py-2 transition ${active ? "border-indigo-200 bg-indigo-50" : "border-transparent hover:bg-slate-100"}`}>
                      {renaming ? (
                        <input autoFocus value={renameTitle} onChange={(event) => setRenameTitle(event.target.value)} onBlur={() => void commitRenameProject(project)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); void commitRenameProject(project); } if (event.key === "Escape") { setRenamingProjectId(null); } }} aria-label={menuLabels.rename} className="min-w-0 flex-1 rounded border border-indigo-300 bg-white px-1.5 py-1 text-xs font-medium text-slate-800 outline-none ring-2 ring-indigo-100" />
                      ) : (
                        <button onClick={() => openProject(project)} className="min-w-0 flex-1 text-left">
                          <p className={`truncate text-xs font-medium ${active ? "text-indigo-900" : "text-slate-700"}`}>{project.title || copy.documentTitle}</p>
                          <p className="mt-0.5 truncate text-[10px] text-slate-400">{formatDate(project.updated_at, lang)}</p>
                        </button>
                      )}
                      {!renaming && <button type="button" onClick={(event) => { event.stopPropagation(); setProjectMenuId(menuOpen ? null : project.id); }} aria-label={menuLabels.actions} aria-haspopup="menu" aria-expanded={menuOpen} className="rounded p-1 text-slate-400 transition hover:bg-white hover:text-indigo-700 group-hover:block focus:block">•••</button>}
                      {menuOpen && <div role="menu" className="absolute right-1 top-9 z-30 w-40 rounded-lg border border-slate-200 bg-white p-1 shadow-lg ring-1 ring-slate-950/5">
                        <button role="menuitem" onClick={() => downloadProject(project)} className="block w-full rounded px-2 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-50">{menuLabels.download}</button>
                        <button role="menuitem" onClick={() => startRenameProject(project)} className="block w-full rounded px-2 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-50">{menuLabels.rename}</button>
                        <button role="menuitem" onClick={() => void duplicateProject(project)} className="block w-full rounded px-2 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-50">{menuLabels.duplicate}</button>
                        <button role="menuitem" onClick={() => { setProjectMenuId(null); void deleteProject(project); }} className="block w-full rounded px-2 py-1.5 text-left text-xs text-rose-700 hover:bg-rose-50">{menuLabels.delete}</button>
                      </div>}
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
              <div className="border-b border-slate-200 bg-white px-4 pt-2 lg:px-5">
                <div className="flex items-center gap-4">
                  {([
                    ["edit", copy.edit],
                    ["preview", copy.preview],
                    ["label", copy.label],
                    ["review", copy.review],
                  ] as [WorkspaceTab, string][]).map(([tab, label]) => (
                    <button key={tab} onClick={() => setWorkspaceTab(tab)} className={`border-b-2 px-0.5 pb-2 text-xs font-semibold transition ${workspaceTab === tab ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{label}</button>
                  ))}
                  <span className="ml-auto pb-2 text-[11px] text-slate-400">{markdown.split("\n").length} {copy.lines} · {markdown.length.toLocaleString()} {copy.chars}</span>
                </div>
              </div>

              {workspaceTab === "edit" && (
                <div className="flex min-h-0 flex-1 flex-col">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-2 lg:px-5">
                    <span className="text-[11px] font-medium text-slate-500">{copy.current}</span>
                    <div className="flex items-center gap-2">
                      {selectedBlock && <button onClick={() => void verifyDocument(selectedBlock)} className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-100">{lang === "zh" ? `验证选中区块 L${selectedBlock.start_line}–${selectedBlock.end_line}` : `Verify selection L${selectedBlock.start_line}–${selectedBlock.end_line}`}</button>}
                      <span className="text-[11px] text-slate-400">Markdown · LaTeX</span>
                    </div>
                  </div>
                  <textarea ref={editorRef} value={markdown} onChange={(event) => changeMarkdown(event.target.value)} onSelect={captureSourceSelection} onKeyUp={captureSourceSelection} onBlur={() => { captureSourceSelection(); void saveDocument(); }} spellCheck={false} placeholder={copy.editorPlaceholder} className="min-h-[480px] flex-1 resize-none border-0 bg-[#fcfcfd] px-5 py-5 font-mono text-[13px] leading-6 text-slate-700 outline-none placeholder:text-slate-300 lg:px-7" />
                </div>
              )}

              {workspaceTab === "preview" && (
                <div className="min-h-0 flex-1 overflow-y-auto bg-[#fcfcfd] px-5 py-7 lg:px-10">
                  <article className="exobrain-prose mx-auto max-w-3xl">
                    <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>{markdown}</ReactMarkdown>
                  </article>
                </div>
              )}

              {workspaceTab === "label" && (
                <LabelDocument
                  markdown={markdown}
                  results={verifyResults}
                  stale={stale}
                  copy={copy}
                  markdownPlugins={markdownPlugins}
                  htmlPlugins={htmlPlugins}
                  focusLine={labelFocusLine}
                  onFocused={() => setLabelFocusLine(null)}
                />
              )}

              {workspaceTab === "review" && (
                <ReviewPanel copy={copy} lang={lang} results={verifyResults} snapshots={verificationSnapshots} snapshot={verificationSnapshot} proofGraph={verificationSnapshot?.proof_graph} evidenceLinks={evidenceLinks} stale={stale} verifying={verifying} loadingSnapshots={snapshotLoading} selectedClaimId={selectedClaimId} selectedBlock={selectedBlock} onVerify={() => void verifyDocument()} onVerifyClaim={(claim) => void verifyDocument({ kind: "claim", start_line: claim.line, end_line: claim.end_line, claim_id: claim.claim_id })} onVerifyBlock={() => selectedBlock && void verifyDocument(selectedBlock)} onSelectClaim={setSelectedClaimId} onFocusSource={focusSourceLine} onSelectSnapshot={(snapshot) => currentDocId && void activateSnapshot(currentDocId, snapshot)} />
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

function markerMeta(status: VerificationStatus) {
  if (status === "verified") return { glyph: "✓", tone: "border-emerald-300 bg-emerald-50 text-emerald-700 shadow-emerald-100", ring: "ring-emerald-200" };
  if (status === "failed" || status === "error") return { glyph: "×", tone: "border-rose-300 bg-rose-50 text-rose-700 shadow-rose-100", ring: "ring-rose-200" };
  return { glyph: "!", tone: "border-amber-300 bg-amber-50 text-amber-700 shadow-amber-100", ring: "ring-amber-200" };
}

type LabelSegment = { key: string; markdown: string; results?: VerifyResult[]; startLine: number; endLine: number };
function expandToMarkdownBlock(lines: string[], startLine: number, endLine: number) {
  let openDisplayMath: number | null = null;
  for (let index = 0; index < lines.length; index += 1) {
    const trimmed = lines[index].trim();
    if (!trimmed.startsWith("$$")) continue;
    const lineNumber = index + 1;
    const closingDelimiter = trimmed.lastIndexOf("$$");
    if (closingDelimiter > 0) {
      if (lineNumber <= endLine && lineNumber >= startLine) return { startLine: lineNumber, endLine: lineNumber };
      continue;
    }
    if (openDisplayMath === null) {
      openDisplayMath = lineNumber;
      continue;
    }
    if (openDisplayMath <= endLine && lineNumber >= startLine) {
      return { startLine: openDisplayMath, endLine: lineNumber };
    }
    openDisplayMath = null;
  }
  return { startLine, endLine };
}
function aggregateLabelStatus(results: VerifyResult[]): VerificationStatus {
  if (results.some((result) => result.status === "failed" || result.status === "error")) return "failed";
  if (results.every((result) => result.status === "verified")) return "verified";
  if (results.some((result) => result.status === "verified" || result.status === "partially_checked")) return "partially_checked";
  return "inconclusive";
}
function labelSegments(markdown: string, results: VerifyResult[]): LabelSegment[] {
  const lines = markdown.split("\n");
  const grouped = new Map<string, { startLine: number; endLine: number; results: VerifyResult[] }>();
  for (const result of [...results]
    .filter((item) => item.line >= 1 && item.line <= lines.length)
    .sort((left, right) => left.line - right.line || left.end_line - right.end_line)) {
    const sourceRange = expandToMarkdownBlock(lines, result.line, Math.max(result.line, result.end_line || result.line));
    const key = `${sourceRange.startLine}-${sourceRange.endLine}`;
    const existing = grouped.get(key);
    if (existing) existing.results.push(result);
    else grouped.set(key, { ...sourceRange, results: [result] });
  }
  const groupedRanges = [...grouped.values()].sort((left, right) => left.startLine - right.startLine || left.endLine - right.endLine);
  const segments: LabelSegment[] = [];
  let cursor = 1;
  for (const item of groupedRanges) {
    const start = Math.max(cursor, item.startLine);
    const end = Math.min(lines.length, Math.max(start, item.endLine));
    if (start > cursor) {
      segments.push({ key: `plain-${cursor}`, markdown: lines.slice(cursor - 1, start - 1).join("\n"), startLine: cursor, endLine: start - 1 });
    }
    segments.push({ key: `claims-${item.startLine}-${item.endLine}`, markdown: lines.slice(start - 1, end).join("\n"), results: item.results, startLine: start, endLine: end });
    cursor = end + 1;
  }
  if (cursor <= lines.length) {
    segments.push({ key: `plain-${cursor}`, markdown: lines.slice(cursor - 1).join("\n"), startLine: cursor, endLine: lines.length });
  }
  return segments.filter((segment) => segment.markdown.trim());
}
function LabelDocument({
  markdown,
  results,
  stale,
  copy,
  markdownPlugins,
  htmlPlugins,
  focusLine,
  onFocused,
}: {
  markdown: string;
  results: VerifyResult[];
  stale: boolean;
  copy: Copy;
  markdownPlugins: typeof remarkMath[];
  htmlPlugins: typeof rehypeKatex[];
  focusLine: number | null;
  onFocused: () => void;
}) {
  const [openClaimId, setOpenClaimId] = useState<string | null>(null);
  const segments = useMemo(() => labelSegments(markdown, results), [markdown, results]);

  useEffect(() => {
    if (focusLine === null) return;
    const target = document.getElementById(`label-source-${focusLine}`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    onFocused();
  }, [focusLine, onFocused]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-[#fcfcfd] px-5 py-7 lg:px-10">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div>
            <p className="text-xs font-semibold text-slate-800">{copy.labelLegend}</p>
            <p className="mt-0.5 text-[11px] leading-4 text-slate-500">{results.length ? copy.labelHint : copy.labelEmpty}</p>
          </div>
          <div className="flex items-center gap-2 text-[10px] font-medium text-slate-500" aria-label={copy.labelLegend}>
            <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-emerald-500" />{copy.verified}</span>
            <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-amber-500" />{copy.issueCount}</span>
            <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-rose-500" />{copy.failed}</span>
          </div>
        </div>
        {stale && <p className="mb-5 inline-flex rounded-md bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-800">{copy.stale}</p>}
        <article className="exobrain-prose mx-auto max-w-3xl">
          {segments.map((segment) => {
            const segmentResults = segment.results || [];
            const status = segmentResults.length ? aggregateLabelStatus(segmentResults) : null;
            const marker = status ? markerMeta(status) : null;
            const selected = segment.key === openClaimId;
            return (
              <section key={segment.key} id={`label-source-${segment.startLine}`} className={`relative scroll-mt-20 pr-12 ${selected ? "rounded-lg bg-indigo-50/50 px-3 py-1 -mx-3" : ""}`}>
                <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>{segment.markdown}</ReactMarkdown>
                {status && marker && (
                  <div className="absolute right-0 top-2 z-10">
                    <button
                      type="button"
                      onClick={() => setOpenClaimId(selected ? null : segment.key)}
                      aria-expanded={selected}
                      aria-label={`${copy.openEvidence}: ${statusMeta(status, copy).label}`}
                      className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs font-bold shadow-sm transition hover:scale-110 focus:outline-none focus:ring-2 ${marker.tone} ${marker.ring}`}
                    >
                      {marker.glyph}
                    </button>
                    {selected && (
                      <div role="dialog" aria-label={copy.openEvidence} className="absolute right-0 top-8 z-30 w-80 rounded-xl border border-slate-200 bg-white p-3 text-left shadow-xl ring-1 ring-slate-950/5">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">{copy.claim} · L{segment.startLine}–{segment.endLine}</p>
                            <span className={`mt-1 inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-semibold ${statusMeta(status, copy).className}`}><i className={`h-1.5 w-1.5 rounded-full ${statusMeta(status, copy).dot}`} />{statusMeta(status, copy).label}</span>
                          </div>
                          <button type="button" onClick={() => setOpenClaimId(null)} aria-label={copy.closeEvidence} className="rounded p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700">×</button>
                        </div>
                        <div className="mt-3 space-y-3">
                          {segmentResults.map((result, index) => <div key={result.claim_id} className={index ? "border-t border-slate-100 pt-3" : ""}>
                            <p className="whitespace-pre-wrap font-mono text-[11px] leading-5 text-slate-700">{displayEquation(result.equation)}</p>
                            <p className="mt-2 text-xs leading-5 text-slate-600">{result.detail}</p>
                          </div>)}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </section>
            );
          })}
        </article>
      </div>
    </div>
  );
}

const PrettyFormula = RenderedMath;

function ReviewPanel({
  copy,
  lang,
  results,
  snapshots,
  snapshot,
  proofGraph,
  evidenceLinks,
  stale,
  verifying,
  loadingSnapshots,
  selectedClaimId,
  selectedBlock,
  onVerify,
  onVerifyClaim,
  onVerifyBlock,
  onSelectClaim,
  onFocusSource,
  onSelectSnapshot,
}: {
  copy: Copy;
  lang: "en" | "zh";
  results: VerifyResult[];
  snapshots: VerificationSnapshot[];
  snapshot: VerificationSnapshot | null;
  proofGraph?: ProofGraph;
  evidenceLinks: EvidenceLink[];
  stale: boolean;
  verifying: boolean;
  loadingSnapshots: boolean;
  selectedClaimId: string | null;
  selectedBlock: SourceScope | null;
  onVerify: () => void;
  onVerifyClaim: (claim: VerifyResult) => void;
  onVerifyBlock: () => void;
  onSelectClaim: (claimId: string) => void;
  onFocusSource: (line: number) => void;
  onSelectSnapshot: (snapshot: VerificationSnapshot) => void;
}) {
  const [view, setView] = useState<"map" | "edges" | "graph" | "evidence">("map");
  const allSteps = proofGraph?.fragments.flatMap((fragment) => fragment.steps) || [];
  const stepById = new Map(allSteps.map((step) => [step.id, step]));
  const proofEdges = [...(proofGraph?.dependencies || [])
    .filter((edge) => (edge.review_visible === true || Boolean(edge.validator)) && stepById.has(edge.from_step_id) && stepById.has(edge.to_step_id))
    .reduce((selected, edge) => {
      const key = `${edge.from_step_id}:${edge.to_step_id}`;
      const priority = (candidate: ProofGraph["dependencies"][number]) => {
        if (candidate.edge_status === "verified" || candidate.edge_status === "verified_under_assumptions") return 100;
        return ({ justifies: 50, requires_assumption: 45, uses_definition: 40, formula_transform: 30, substitutes_result: 20, derives: 10 } as Record<string, number>)[candidate.kind] || 0;
      };
      const previous = selected.get(key);
      if (!previous || priority(edge) > priority(previous)) selected.set(key, edge);
      return selected;
    }, new Map<string, ProofGraph["dependencies"][number]>())
    .values()];
  const verifiedEdges = proofEdges.filter((edge) => edge.edge_status === "verified" || edge.edge_status === "verified_under_assumptions").length;
  const reviewedEdges = proofEdges.filter((edge) => edge.edge_status === "semantically_reviewed").length;
  const openEdges = proofEdges.length - verifiedEdges - reviewedEdges;
  const edgeStatusMeta = (status: string) => {
    if (status === "verified") return { label: copy.verified, className: "border-emerald-200 bg-emerald-50 text-emerald-800", dot: "bg-emerald-500" };
    if (status === "semantically_reviewed") return { label: lang === "zh" ? "结构审阅通过" : "Structurally reviewed", className: "border-violet-200 bg-violet-50 text-violet-800", dot: "bg-violet-500" };
    if (status === "verified_under_assumptions") return { label: lang === "zh" ? "在显式前提下成立" : "Verified under assumptions", className: "border-sky-200 bg-sky-50 text-sky-800", dot: "bg-sky-500" };
    if (status === "failed") return { label: copy.failed, className: "border-rose-200 bg-rose-50 text-rose-800", dot: "bg-rose-500" };
    if (status === "declared") return { label: lang === "zh" ? "已声明前提" : "Declared premise", className: "border-slate-200 bg-slate-50 text-slate-700", dot: "bg-slate-400" };
    return { label: lang === "zh" ? "待验证边" : "Open proof obligation", className: "border-amber-200 bg-amber-50 text-amber-800", dot: "bg-amber-500" };
  };
  const labels = lang === "zh"
    ? { map: "证明地图", edges: "推导关系", graph: "图谱细节", evidence: "执行证据", history: "快照历史", scope: "验证范围", source: "在源码中查看", block: "验证选中区块", noEvidence: "这个快照中还没有关联的执行证据。", noGraph: "尚未提取可显示的证明依赖。", execution: "执行结果", sourceLatex: "查看源码 LaTeX", edgeSummary: "边是验证对象；节点只提供上下文。", upstream: "前提/输入", downstream: "结论/输出", ruleEvidence: "确定性证据", openEdges: "待验证关系" }
    : { map: "Proof map", edges: "Proof edges", graph: "Graph detail", evidence: "Execution evidence", history: "Snapshot history", scope: "Verification scope", source: "View source", block: "Verify selected block", noEvidence: "No execution evidence is linked to this snapshot yet.", noGraph: "No proof dependencies were extracted for this snapshot.", execution: "Execution result", sourceLatex: "View source LaTeX", edgeSummary: "Edges are the verification objects; nodes provide context only.", upstream: "Premise / input", downstream: "Conclusion / output", ruleEvidence: "Deterministic evidence", openEdges: "Open proof obligations" };
  const selectedClaim = results.find((item) => item.claim_id === selectedClaimId) || null;
  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-[#fcfcfd] p-4 lg:p-5">
      <div className="mx-auto max-w-4xl">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-800">{copy.reviewSummary}</p>
              <p className="mt-1 text-xs text-slate-500">{snapshot ? `${copy.snapshot} · ${formatDate(snapshot.created_at, lang)}` : copy.noVerification}</p>
              {stale && <p className="mt-2 inline-flex rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">{copy.stale}</p>}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {selectedBlock && <button onClick={onVerifyBlock} disabled={verifying} className="rounded-md border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-50">{labels.block}</button>}
              <button onClick={onVerify} disabled={verifying} className="rounded-md bg-indigo-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50">{verifying ? copy.working : snapshot ? copy.rerunVerification : copy.runVerification}</button>
            </div>
          </div>
          <div className="mt-4 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <label className="block text-[11px] font-medium text-slate-500">{labels.history}
              <select value={snapshot?.id || ""} onChange={(event) => { const next = snapshots.find((item) => item.id === event.target.value); if (next) onSelectSnapshot(next); }} disabled={loadingSnapshots || snapshots.length === 0} className="mt-1.5 block w-full rounded-md border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-700 outline-none focus:border-indigo-300">
                {!snapshots.length && <option value="">{loadingSnapshots ? copy.loading : copy.noVerification}</option>}
                {snapshots.map((item) => <option key={item.id} value={item.id}>{formatDate(item.created_at, lang)} · {scopeLabel(item.verification_scope, lang)} · {item.proof_graph?.dependencies?.length || 0} {lang === "zh" ? "边" : "edges"}</option>)}
              </select>
            </label>
            <div className="text-[11px] font-medium text-slate-500">{labels.scope}<p className="mt-1.5 rounded-md border border-slate-100 bg-slate-50 px-2.5 py-2 text-xs font-normal text-slate-700">{snapshot ? scopeLabel(snapshot.verification_scope, lang) : scopeLabel(undefined, lang)}</p></div>
          </div>
        </div>
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-1.5 shadow-sm">
          <div className="grid grid-cols-4 gap-1" role="tablist" aria-label={copy.review}>
            {([["map", labels.map], ["edges", labels.edges], ["graph", labels.graph], ["evidence", labels.evidence]] as const).map(([id, label]) => <button key={id} role="tab" aria-selected={view === id} onClick={() => setView(id)} className={`rounded-md px-3 py-2 text-xs font-semibold transition ${view === id ? "bg-indigo-50 text-indigo-700 shadow-sm" : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"}`}>{label}</button>)}
          </div>
          {!snapshot ? <div className="p-8 text-center"><p className="text-sm font-semibold text-slate-700">{copy.noVerification}</p><p className="mx-auto mt-2 max-w-md text-xs leading-5 text-slate-500">{copy.noVerificationDescription}</p></div> : <>
            {view === "edges" && <div className="mt-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-xs text-indigo-900"><span>{labels.edgeSummary}</span><span className="font-semibold">{verifiedEdges} {copy.verified} · {reviewedEdges} {lang === "zh" ? "结构审阅" : "structurally reviewed"} · {openEdges} {labels.openEdges}</span></div>
              {!proofEdges.length ? <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-xs leading-5 text-slate-500">{labels.noGraph}</div> : proofEdges.map((edge) => {
                const source = stepById.get(edge.from_step_id)!;
                const target = stepById.get(edge.to_step_id)!;
                const meta = edgeStatusMeta(edge.edge_status);
                const validator = edge.validator as { id?: string; label?: string; method?: string; evidence?: Record<string, unknown> } | undefined;
                const focusLine = Math.min(source.source.start_line, target.source.start_line);
                return <article key={edge.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex flex-wrap items-center gap-2"><span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[10px] font-semibold ${meta.className}`}><i className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />{meta.label}</span><span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{edge.kind.replaceAll("_", " ")}</span></div><button onClick={() => onFocusSource(focusLine)} className="rounded-md border border-slate-200 px-2.5 py-1.5 text-[10px] font-semibold text-indigo-700 transition hover:border-indigo-200 hover:bg-indigo-50">{labels.source} · L{source.source.start_line}–{target.source.end_line}</button></div>
                  <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] lg:items-center"><div><p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">{labels.upstream}</p><PrettyFormula source={source.text} compact /></div><div className="hidden text-center text-lg text-indigo-400 lg:block">→</div><div><p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">{labels.downstream}</p><PrettyFormula source={target.text} compact /></div></div>
                  <p className="mt-3 text-xs leading-5 text-slate-600">{edge.reason}</p>
                  {validator && <details className="mt-3 rounded-lg border border-slate-100 bg-slate-50 p-3"><summary className="cursor-pointer text-xs font-semibold text-slate-700">{labels.ruleEvidence}{validator.label ? ` · ${validator.label}` : ""}</summary><p className="mt-2 text-xs leading-5 text-slate-600">{validator.method}</p>{validator.evidence && <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-2 text-[10px] leading-4 text-slate-100">{JSON.stringify(validator.evidence, null, 2)}</pre>}</details>}
                </article>;
              })}
            </div>}
            {view === "map" && <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">{proofGraph?.fragments?.length ? <ProofMap graph={proofGraph} lang={lang} onFocusSource={onFocusSource} /> : <p className="text-xs leading-5 text-slate-500">{labels.noGraph}</p>}</div>}
            {view === "graph" && <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">{proofGraph?.fragments?.length ? <ProofDependencyGraph graph={proofGraph} lang={lang} onFocusSource={onFocusSource} /> : <p className="text-xs leading-5 text-slate-500">{labels.noGraph}</p>}</div>}
            {view === "evidence" && <div className="mt-4 space-y-3">{!evidenceLinks.length ? <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-xs leading-5 text-slate-500">{labels.noEvidence}</div> : evidenceLinks.map((evidence) => { const claim = results.find((item) => item.claim_id === evidence.claim_id); return <article key={evidence.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold text-slate-700">{labels.execution}</p><p className="mt-1 text-[10px] text-slate-500">{claim ? `${copy.claim} · L${claim.line}` : evidence.claim_id} · {formatDate(evidence.created_at, lang)}</p></div><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${evidence.exit_code === 0 ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800"}`}>{evidence.exit_code === 0 ? copy.verified : copy.error}</span></div><p className="mt-3 break-all font-mono text-[10px] text-slate-400">SHA-256 {evidence.code_hash}</p>{evidence.stdout && <pre className="mt-3 max-h-44 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">{evidence.stdout}</pre>}{evidence.stderr && <pre className="mt-3 max-h-44 overflow-auto rounded-lg bg-rose-50 p-3 text-xs text-rose-900">{evidence.stderr}</pre>}{claim && <button onClick={() => { onSelectClaim(claim.claim_id); onFocusSource(claim.line); }} className="mt-3 text-xs font-semibold text-indigo-600">{labels.source}</button>}</article>; })}</div>}
          </>}
        </div>
        {selectedClaim && <div className="mt-4 rounded-lg border border-indigo-100 bg-indigo-50/50 px-3 py-2 text-xs text-indigo-800">{lang === "zh" ? "当前选中主张：" : "Selected claim: "}<span className="font-mono">{selectedClaim.claim_id}</span></div>}
      </div>
    </div>
  );
}
function ProofMap({ graph, lang, onFocusSource }: { graph: ProofGraph; lang: "en" | "zh"; onFocusSource: (line: number) => void }) {
  const labels = lang === "zh"
    ? { assumptions: "前提", claim: "命题", derivation: "推导", context: "上下文", verified: "已有确定性证据", review: "仍有证明义务", premise: "引用前提/引理", structure: "结构上下文", formulas: "公式步骤", source: "定位源码", edge: "关系边" }
    : { assumptions: "Assumptions", claim: "Claim", derivation: "Derivation", context: "Context", verified: "Deterministic evidence present", review: "Proof obligations remain", premise: "Cited premise or lemma", structure: "Structural context", formulas: "Formula steps", source: "View source", edge: "Dependency" };
  const fragmentLabel: Record<ProofFragment["kind"], string> = { assumptions: labels.assumptions, claim: labels.claim, derivation: labels.derivation, context: labels.context };
  const stepById = new Map(graph.fragments.flatMap((fragment) => fragment.steps).map((step) => [step.id, step]));
  return <div className="mx-auto max-w-3xl">
    <div className="mb-4 rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-xs leading-5 text-indigo-900">{lang === "zh" ? "按原文顺序展示局部 proof fragments。颜色仅概括已存在的确定性证据；灰色关系边仍是待验证的 proof obligation。" : "Local proof fragments follow source order. Color summarizes existing deterministic evidence only; gray dependency edges remain open proof obligations."}</div>
    <div className="space-y-0">
      {graph.fragments.map((fragment, index) => {
        const formulaSteps = fragment.steps.filter((step) => step.is_formula);
        const formulaIds = new Set(formulaSteps.map((step) => step.id));
        const incidentEdges = graph.dependencies.filter((edge) => fragment.steps.some((step) => step.id === edge.from_step_id || step.id === edge.to_step_id));
        const hasVerifiedEdge = incidentEdges.some((edge) => edge.edge_status === "verified" || edge.edge_status === "verified_under_assumptions");
        const hasOpenFormula = formulaSteps.some((step) => step.local_status === "inconclusive" || step.local_status === "partially_checked" || step.local_status === "not_checked");
        const allFormulaPremises = formulaSteps.length > 0 && formulaSteps.every((step) => step.local_status === "not_required");
        const status = formulaSteps.length === 0 ? "structure" : allFormulaPremises ? "premise" : hasVerifiedEdge && !hasOpenFormula ? "verified" : "review";
        const tone = status === "verified" ? "border-emerald-200 bg-emerald-50/70" : status === "review" ? "border-amber-200 bg-amber-50/60" : status === "premise" ? "border-violet-200 bg-violet-50/70" : "border-slate-200 bg-white";
        const statusText = status === "verified" ? labels.verified : status === "review" ? labels.review : status === "premise" ? labels.premise : labels.structure;
        const statusTextTone = status === "verified" ? "text-emerald-800" : status === "review" ? "text-amber-800" : status === "premise" ? "text-violet-800" : "text-slate-600";
        return <div key={fragment.id} className="relative">
          {index > 0 && <div aria-hidden className="mx-auto h-6 w-px bg-slate-300"><span className="relative -left-1.5 top-4 block h-0 w-0 border-x-[3px] border-t-[5px] border-x-transparent border-t-slate-300" /></div>}
          <section className={`rounded-xl border p-4 shadow-sm ${tone}`}>
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{fragmentLabel[fragment.kind]}</p><h3 className="mt-1 text-sm font-semibold text-slate-800">{fragment.title}</h3><p className={`mt-1 text-[11px] font-medium ${statusTextTone}`}>{statusText}</p></div><button onClick={() => onFocusSource(fragment.source.start_line)} className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold text-indigo-700 transition hover:border-indigo-200 hover:bg-indigo-50">{labels.source} · L{fragment.source.start_line}–{fragment.source.end_line}</button></div>
            {formulaSteps.length > 0 ? <div className="mt-3 space-y-2">{formulaSteps.map((step) => <button key={step.id} type="button" onClick={() => onFocusSource(step.source.start_line)} className="block w-full rounded-lg border border-white/80 bg-white p-3 text-left shadow-sm transition hover:border-indigo-200 hover:ring-2 hover:ring-indigo-100"><div className="flex items-center justify-between gap-3"><span className="text-[10px] font-medium text-slate-400">{labels.formulas}</span><span className="text-[10px] font-semibold text-indigo-600">L{step.source.start_line}–{step.source.end_line}</span></div><div className="pointer-events-none mt-2"><PrettyFormula source={step.text} compact /></div></button>)}</div> : <p className="mt-3 rounded-lg border border-dashed border-slate-200 bg-white/80 px-3 py-2 text-xs leading-5 text-slate-500">{lang === "zh" ? "该 fragment 保留了证明结构与来源上下文；它本身不是独立可执行的公式义务。" : "This fragment retains proof structure and source context; it is not an independently executable formula obligation."}</p>}
            {incidentEdges.length > 0 && <details className="mt-3 border-t border-slate-200/70 pt-3"><summary className="cursor-pointer text-xs font-semibold text-slate-700">{labels.edge} · {incidentEdges.length}</summary><div className="mt-2 space-y-1.5">{incidentEdges.slice(0, 6).map((edge) => { const source = stepById.get(edge.from_step_id); const target = stepById.get(edge.to_step_id); return <button key={edge.id} type="button" onClick={() => onFocusSource((target || source)?.source.start_line || fragment.source.start_line)} className={`block w-full rounded-md border px-2.5 py-2 text-left text-[10px] leading-4 ${edge.edge_status === "verified" ? "border-emerald-100 bg-emerald-50 text-emerald-900" : edge.edge_status === "verified_under_assumptions" ? "border-sky-100 bg-sky-50 text-sky-900" : "border-slate-100 bg-white/80 text-slate-600"}`}><span className="font-semibold">{edge.kind.replaceAll("_", " ")} · {edge.edge_status.replaceAll("_", " ")}</span><span className="block opacity-80">{edge.reason}</span></button>; })}</div></details>}
          </section>
        </div>;
      })}
    </div>
  </div>;
}

function ProofDependencyGraph({ graph, lang, onFocusSource }: { graph: ProofGraph; lang: "en" | "zh"; onFocusSource: (line: number) => void }) {
  const allSteps = graph.fragments.flatMap((fragment) => fragment.steps);
  const byId = new Map(allSteps.map((step) => [step.id, step]));
  const labels = lang === "zh"
    ? { local: "局部检查", declared: "已声明前提", unchecked: "边尚未验证", verified: "规则已验证", conditional: "在显式前提下成立", assumptions: "假设", definition: "定义", statement: "命题", derivation: "推导步骤", theorem: "定理应用", conclusion: "结论", docs: "阅读术语说明", limitations: "证据边界", deterministicEvidence: "确定性规则证据" }
    : { local: "Local check", declared: "Declared prerequisite", unchecked: "Edge not checked", verified: "Rule verified", conditional: "Verified under explicit assumptions", assumptions: "Assumption", definition: "Definition", statement: "Statement", derivation: "Derivation step", theorem: "Theorem application", conclusion: "Conclusion", docs: "Read terminology", limitations: "Evidence boundary", deterministicEvidence: "Deterministic rule evidence" };
  const kindLabel: Record<ProofStep["kind"], string> = {
    assumption: labels.assumptions,
    definition: labels.definition,
    statement: labels.statement,
    derivation_step: labels.derivation,
    theorem_application: labels.theorem,
    conclusion: labels.conclusion,
  };
  const relationLabel: Record<string, string> = lang === "zh"
    ? { derives: "推导", requires_assumption: "需要前提", formula_transform: "公式变换", uses_definition: "使用定义", justifies: "论证", substitutes_result: "代入结果" }
    : { derives: "derives", requires_assumption: "requires assumption", formula_transform: "formula transformation", uses_definition: "uses definition", justifies: "justifies", substitutes_result: "substitutes result" };
  const statusTone: Record<ProofStep["local_status"], string> = {
    locally_verified: "bg-emerald-50 text-emerald-800",
    partially_checked: "bg-sky-50 text-sky-800",
    semantically_reviewed: "bg-sky-50 text-sky-800",
    inconclusive: "bg-amber-50 text-amber-800",
    failed: "bg-rose-50 text-rose-800",
    not_checked: "bg-slate-100 text-slate-600",
    not_required: "bg-violet-50 text-violet-800",
  };
  const statusLabel: Record<ProofStep["local_status"], string> = {
    locally_verified: lang === "zh" ? "局部已验证" : "Locally verified",
    partially_checked: lang === "zh" ? "部分已检查" : "Partially checked",
    semantically_reviewed: lang === "zh" ? "结构审阅通过" : "Structurally reviewed",
    inconclusive: lang === "zh" ? "不确定" : "Inconclusive",
    failed: lang === "zh" ? "失败" : "Failed",
    not_checked: lang === "zh" ? "未检查" : "Not checked",
    not_required: lang === "zh" ? "前提/引理" : "Cited premise",
  };

  return <div>
    {graph.semantic_proposal?.status === "unavailable" && <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"><span className="font-semibold">{lang === "zh" ? "语义解析未运行：" : "Semantic parsing unavailable: "}</span>{graph.semantic_proposal.notice || (lang === "zh" ? "当前显示启发式结构。" : "heuristic structure is shown.")}</div>}
    {graph.semantic_proposal?.status === "proposed" && <div className="mb-3 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs leading-5 text-violet-900"><span className="font-semibold">{lang === "zh" ? "LLM 结构提案：" : "LLM structure proposal: "}</span>{lang === "zh" ? "角色与关系已绑定原文；绿色仍仅表示确定性证据。" : "roles and relations are source-bound; green still requires deterministic evidence."}</div>}
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-3">
      <div><p className="text-sm font-semibold text-slate-800">{lang === "zh" ? "局部证明片段" : "Local proof fragments"}</p><p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">{lang === "zh" ? "每个节点是一个可审阅的证明步骤；边代表待验证的依赖，而非仅由文档顺序推断出的真理。" : "Each node is a reviewable proof step. Edges are proof dependencies awaiting their own verification, not truth inferred from document order."}</p></div>
      <a href="/docs/proof-dependency-graph" className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-indigo-700 transition hover:border-indigo-200 hover:bg-indigo-50">{labels.docs}</a>
    </div>
    <div className="mt-4 space-y-5">
      {graph.fragments.map((fragment) => <section key={fragment.id} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
        <div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold text-slate-700">{fragment.title}</p><button onClick={() => onFocusSource(fragment.source.start_line)} className="text-[10px] font-medium text-indigo-600">L{fragment.source.start_line}–{fragment.source.end_line}</button></div>
        <div className="mt-3 space-y-2">{fragment.steps.map((step) => {
          const inbound = graph.dependencies.filter((edge) => edge.to_step_id === step.id);
          return <article key={step.id} className="rounded-md border border-slate-200 bg-white p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex flex-wrap items-center gap-2"><span className="rounded bg-indigo-50 px-1.5 py-1 text-[10px] font-semibold text-indigo-700">{kindLabel[step.kind]}</span><span className={`rounded px-1.5 py-1 text-[10px] font-medium ${statusTone[step.local_status]}`}>{statusLabel[step.local_status]}</span></div><button onClick={() => onFocusSource(step.source.start_line)} className="text-[10px] font-medium text-indigo-600">L{step.source.start_line}–{step.source.end_line}</button></div><PrettyFormula source={step.text} compact /><details className="mt-2 text-[10px] text-slate-500"><summary className="cursor-pointer font-medium hover:text-indigo-700">{lang === "zh" ? "查看源码 LaTeX" : "View source LaTeX"}</summary><pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-2 text-[9px] leading-4 text-slate-100">{step.text}</pre></details>{inbound.length > 0 && <div className="mt-3 space-y-2 border-t border-slate-100 pt-2">{inbound.map((edge) => { const source = byId.get(edge.from_step_id); const edgeLabel = edge.edge_status === "verified" ? labels.verified : edge.edge_status === "verified_under_assumptions" ? labels.conditional : edge.edge_status === "declared" ? labels.declared : labels.unchecked; const edgeTone = edge.edge_status === "verified" ? "border-emerald-100 bg-emerald-50/60 text-emerald-900" : edge.edge_status === "verified_under_assumptions" ? "border-sky-100 bg-sky-50/60 text-sky-900" : edge.edge_status === "declared" ? "border-amber-100 bg-amber-50/60 text-amber-900" : "border-slate-100 bg-slate-50 text-slate-600"; return <div key={edge.id} className={`rounded-md border px-2.5 py-2 text-[10px] leading-4 ${edgeTone}`}><p className="font-semibold">{edgeLabel}: {relationLabel[edge.kind] ?? edge.kind} · {source ? `${kindLabel[source.kind]} · L${source.source.start_line}` : edge.from_step_id}</p><p className="mt-1 opacity-80">{edge.reason}</p>{edge.validator && <details className="mt-2"><summary className="cursor-pointer font-semibold">{labels.deterministicEvidence} · {edge.validator.label}</summary><p className="mt-1 opacity-80">{edge.validator.method}</p><pre className="mt-2 overflow-auto rounded bg-white/70 p-2 text-[9px] text-slate-700">{JSON.stringify(edge.validator.evidence, null, 2)}</pre></details>}</div>; })}</div>}</article>;
        })}</div>
      </section>)}
    </div>
    {graph.limitations?.length ? <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50/60 p-3"><p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-amber-800">{labels.limitations}</p><div className="mt-2 space-y-1 text-xs leading-5 text-amber-900">{graph.limitations.map((limitation) => <p key={limitation}>{limitation}</p>)}</div></div> : null}
  </div>;
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
