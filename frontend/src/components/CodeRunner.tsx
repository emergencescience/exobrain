"use client";

import { useMemo, useState } from "react";

export interface ExecutionArtifact {
  artifact_id?: string;
  stdout: string;
  stderr: string;
  exit_code: number;
  running: boolean;
}

interface Props {
  apiBaseUrl: string;
  documentId: string;
  messages: Array<{ role: string; content: string }>;
  onArtifact: (artifact: ExecutionArtifact) => void;
}

function snippetsFromMessages(messages: Props["messages"]): string[] {
  return messages.flatMap(({ content }) =>
    [...content.matchAll(/```python\s*\n([\s\S]*?)```/gi)].map((match) => match[1].trim()),
  );
}

export default function CodeRunner({ apiBaseUrl, documentId, messages, onArtifact }: Props) {
  const snippets = useMemo(() => snippetsFromMessages(messages), [messages]);
  const [outputs, setOutputs] = useState<Record<number, ExecutionArtifact>>({});

  const run = async (index: number, code: string) => {
    setOutputs((previous) => ({
      ...previous,
      [index]: { stdout: "", stderr: "", exit_code: 0, running: true },
    }));
    try {
      const response = await fetch(`${apiBaseUrl}/api/play/exobrain/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, document_id: documentId, timeout: 30 }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      const artifact: ExecutionArtifact = {
        artifact_id: result.artifact_id,
        stdout: result.stdout || "",
        stderr: result.stderr || "",
        exit_code: result.exit_code ?? -1,
        running: false,
      };
      setOutputs((previous) => ({ ...previous, [index]: artifact }));
      onArtifact(artifact);
    } catch (error) {
      setOutputs((previous) => ({
        ...previous,
        [index]: {
          stdout: "",
          stderr: error instanceof Error ? error.message : "Execution failed",
          exit_code: -1,
          running: false,
        },
      }));
    }
  };

  if (snippets.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500 shadow-sm">
        Ask Exobrain to produce a <code>```python</code> block, then run it here.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {snippets.map((code, index) => {
        const output = outputs[index];
        return (
          <section key={`${index}-${code.slice(0, 32)}`} className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-3 py-2">
              <span className="font-mono text-xs text-slate-500">Python {index + 1}</span>
              <button
                onClick={() => run(index, code)}
                disabled={output?.running}
                className="rounded-md bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {output?.running ? "Running…" : "Run"}
              </button>
            </div>
            <pre className="max-h-64 overflow-auto bg-slate-950 p-3 text-xs text-slate-100">{code}</pre>
            {output && !output.running && (
              <pre className={`max-h-48 overflow-auto whitespace-pre-wrap p-3 text-xs ${output.exit_code === 0 ? "bg-emerald-50 text-emerald-950" : "bg-rose-50 text-rose-950"}`}>
                {output.stdout || output.stderr || "(no output)"}
              </pre>
            )}
          </section>
        );
      })}
    </div>
  );
}
