"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

type RenderedMathProps = {
  source: string;
  compact?: boolean;
  className?: string;
};

/** Shared KaTeX-first rendering for Review, Proof map, and the dashboard. */
export default function RenderedMath({ source, compact = false, className = "" }: RenderedMathProps) {
  return (
    <div className={`exobrain-prose overflow-x-auto rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2 text-slate-800 ${compact ? "text-xs" : "text-sm"} ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{source}</ReactMarkdown>
    </div>
  );
}
