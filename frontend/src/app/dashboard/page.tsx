// Copyright (c) 2026 Symbol Science. All rights reserved.
"use client";

import { useEffect, useMemo, useState } from "react";
import RenderedMath from "@/components/RenderedMath";

type LocalStatus = "locally_verified" | "partially_checked" | "inconclusive" | "failed" | "not_checked" | "not_required";
type Fragment = {
  id: string;
  title: string;
  kind: string;
  source: { start_line?: number; end_line?: number };
  formula_count: number;
  local_status_counts: Record<string, number>;
  formula_steps: { id: string; text: string; local_status: LocalStatus; semantic_role?: string; verification_target?: string; semantic_rationale?: string; source: { start_line?: number; end_line?: number } }[];
};
type VerificationRun = {
  snapshot_id: string;
  document_id: string;
  document_title: string;
  created_at: string;
  verification_scope: { kind?: string };
  run_status: "verified" | "mixed" | "needs_review" | "failed";
  claim_count: number;
  status_counts: Record<string, number>;
  fragments: Fragment[];
  edge_count: number;
  verified_edge_count: number;
};
type DashboardData = {
  summary: { run_count: number; verified_runs: number; mixed_runs: number; needs_review_runs: number; failed_runs: number; deterministic_edges: number };
  runs: VerificationRun[];
};

const API_BASE = process.env.NEXT_PUBLIC_EXOBRAIN_API_URL || "http://localhost:8080";
const statusMeta: Record<VerificationRun["run_status"], { label: string; tone: string }> = {
  verified: { label: "Deterministic evidence", tone: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  mixed: { label: "Mixed evidence", tone: "bg-sky-50 text-sky-800 ring-sky-200" },
  needs_review: { label: "Proof obligations", tone: "bg-amber-50 text-amber-800 ring-amber-200" },
  failed: { label: "Failed evidence", tone: "bg-rose-50 text-rose-800 ring-rose-200" },
};
const localTone: Record<LocalStatus, string> = {
  locally_verified: "bg-emerald-50 text-emerald-800",
  partially_checked: "bg-sky-50 text-sky-800",
  inconclusive: "bg-amber-50 text-amber-800",
  failed: "bg-rose-50 text-rose-800",
  not_checked: "bg-slate-100 text-slate-600",
  not_required: "bg-violet-50 text-violet-800",
};

function Formula({ source }: { source: string }) {
  return <RenderedMath source={source} className="verification-formula pointer-events-none" />;
}

export default function VerificationDashboardPage() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | VerificationRun["run_status"]>("all");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ q: query, status });
        const response = await fetch(`${API_BASE}/api/dashboard?${params}`, { signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const next = await response.json() as DashboardData;
        setData(next);
        setSelectedId((current) => current && next.runs.some((run) => run.snapshot_id === current) ? current : next.runs[0]?.snapshot_id || null);
      } catch (cause) {
        if ((cause as Error).name !== "AbortError") setError("The dashboard could not load persisted verification snapshots.");
      } finally {
        setLoading(false);
      }
    }, 180);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [query, status]);

  const selected = useMemo(() => data?.runs.find((run) => run.snapshot_id === selectedId) || null, [data, selectedId]);
  const cards = data ? [
    ["Verification runs", data.summary.run_count, "immutable snapshots"],
    ["Deterministic edges", data.summary.deterministic_edges, "replayable evidence"],
    ["Proof obligations", data.summary.needs_review_runs + data.summary.mixed_runs, "runs needing review"],
  ] : [];

  return <main className="min-h-screen bg-[#f7f8fa] text-slate-900 selection:bg-indigo-100">
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur lg:px-6">
      <a href="/" className="flex items-center gap-3"><span className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-600 text-sm font-semibold text-white">S</span><span><span className="block text-sm font-semibold tracking-tight text-slate-950">Exobrain</span><span className="block text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">Symbol Science workspace</span></span></a>
      <a href="/" className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700">Open workspace</a>
    </header>
    <section className="border-b border-slate-200 bg-white px-4 py-8 lg:px-8"><div className="mx-auto max-w-7xl"><p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-indigo-600">Evidence workspace</p><div className="mt-2 flex flex-wrap items-end justify-between gap-5"><div><h1 className="text-2xl font-semibold tracking-tight text-slate-950">Verification dashboard</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Search immutable verification snapshots, inspect local proof fragments, and distinguish replayable evidence from proof obligations.</p></div><p className="max-w-xs rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2 text-xs leading-5 text-indigo-900">LLM structure proposals are never evidence. Green indicators require a deterministic validator or explicit replayable execution record.</p></div></div></section>
    <section className="mx-auto max-w-7xl px-4 py-6 lg:px-8"><div className="grid gap-3 md:grid-cols-3">{cards.map(([label, value, detail]) => <article key={String(label)} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p><div className="mt-2 flex items-end justify-between gap-3"><p className="text-2xl font-semibold tracking-tight text-slate-900">{value}</p><p className="pb-1 text-[10px] text-slate-500">{detail}</p></div></article>)}</div>
      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.65fr)]"><aside className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><label className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Search evidence</label><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Equation, fragment, document…" className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none transition focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-100" />
        <div className="mt-3 flex flex-wrap gap-1.5">{(["all", "verified", "mixed", "needs_review", "failed"] as const).map((item) => <button key={item} type="button" onClick={() => setStatus(item)} className={`rounded-full px-2.5 py-1 text-[10px] font-semibold transition ${status === item ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{item === "all" ? "All" : statusMeta[item].label}</button>)}</div>
        <div className="mt-5 space-y-2">{loading && <p className="py-6 text-center text-xs text-slate-500">Loading snapshots…</p>}{error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-800">{error}</p>}{!loading && !error && data?.runs.length === 0 && <p className="rounded-lg border border-dashed border-slate-300 px-3 py-6 text-center text-xs leading-5 text-slate-500">No persisted verification snapshots match this search.</p>}{data?.runs.map((run) => { const meta = statusMeta[run.run_status]; const selectedRun = run.snapshot_id === selectedId; return <button key={run.snapshot_id} type="button" onClick={() => setSelectedId(run.snapshot_id)} className={`block w-full rounded-lg border p-3 text-left transition ${selectedRun ? "border-indigo-300 bg-indigo-50 ring-2 ring-indigo-100" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"}`}><div className="flex gap-3"><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-800">{run.document_title}</p><p className="mt-1 text-[10px] text-slate-500">{new Date(run.created_at).toLocaleString()} · {run.claim_count} claims · {run.fragments.length} fragments</p></div><span className={`h-fit shrink-0 rounded-full px-2 py-1 text-[9px] font-semibold ring-1 ${meta.tone}`}>{meta.label}</span></div></button>; })}</div></aside>
        <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">{selected ? <><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Snapshot evidence</p><h2 className="mt-1 text-lg font-semibold text-slate-900">{selected.document_title}</h2><p className="mt-1 text-xs text-slate-500">{selected.fragments.length} proof fragments · {selected.edge_count} graph edges · {selected.verified_edge_count} deterministic edges</p></div><span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ring-1 ${statusMeta[selected.run_status].tone}`}>{statusMeta[selected.run_status].label}</span></div><div className="mt-5 space-y-4">{selected.fragments.map((fragment) => <article key={fragment.id} className="rounded-xl border border-slate-200 bg-slate-50/50 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{fragment.kind}</p><h3 className="mt-1 text-sm font-semibold text-slate-800">{fragment.title}</h3></div><span className="rounded bg-white px-2 py-1 text-[10px] font-medium text-indigo-700 ring-1 ring-slate-200">L{fragment.source.start_line}–{fragment.source.end_line}</span></div>{fragment.formula_steps.length ? <div className="mt-3 space-y-3">{fragment.formula_steps.map((step) => <div key={step.id} className="rounded-lg border border-slate-200 bg-white p-3"><div className="mb-2 flex items-center justify-between gap-3"><span className={`rounded px-2 py-1 text-[9px] font-semibold ${localTone[step.local_status]}`}>{step.local_status.replaceAll("_", " ")}</span><span className="text-[10px] font-medium text-slate-400">{step.semantic_role ? `${step.semantic_role} · ` : ""}L{step.source.start_line}–{step.source.end_line}</span></div><Formula source={step.text} /></div>)}</div> : <p className="mt-3 rounded-lg border border-dashed border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-500">Structural context only. It does not represent an independently executable formula obligation.</p>}</article>)}</div></> : <div className="flex min-h-80 items-center justify-center text-center text-sm text-slate-500">Select a persisted verification run to inspect its evidence map.</div>}</section></div></section>
  </main>;
}
