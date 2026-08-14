// Copyright (c) 2026 Symbol Science. All rights reserved.

const sources = [
  { label: "StepProof — step-by-step verification of natural language mathematical proofs", href: "https://arxiv.org/html/2506.10558v2" },
  { label: "ProofFlow — a dependency graph approach to faithful proof autoformalization", href: "https://proceedings.iclr.cc/paper_files/paper/2026/hash/5fce5198dbf92d5ff45f74504431e2ff-Abstract-Conference.html" },
  { label: "Theorem Proving in Lean 4", href: "https://lean-lang.org/theorem_proving_in_lean4/" },
];

export default function ClaimAstDocsPage() {
  return <main className="min-h-screen bg-[#fcfcfd] text-slate-800">
    <div className="mx-auto max-w-5xl px-5 py-12 sm:px-8 lg:py-16">
      <a href="/" className="text-sm font-semibold text-indigo-700 hover:text-indigo-800">← Exobrain workspace</a>
      <header className="mt-8 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">Symbol Science · Exobrain documentation</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">Proof fragments &amp; dependency graphs</h1>
        <p className="mt-5 text-lg leading-8 text-slate-600">Exobrain reviews a bounded fragment of a derivation as proof steps and explicit dependencies. It does not claim to turn an entire paper into a complete formal proof.</p>
      </header>

      <section className="mt-12 grid gap-4 md:grid-cols-3">
        {[['Proof step', 'A local, reviewable statement, definition, transformation, theorem application, or conclusion.'], ['Proof dependency', 'A declared relation showing which earlier step or assumption a later step relies on.'], ['Proof obligation', 'The specific relation that needs evidence before an edge can be treated as established.']].map(([title, text]) => <article key={title} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-base font-semibold text-slate-900">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{text}</p></article>)}
      </section>

      <section className="mt-12 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Why a local fragment instead of a whole-paper AST?</h2>
        <p className="mt-4 leading-7 text-slate-600">Research prose mixes definitions, citations, informal intuition, theorem invocations, calculations, and conclusions. A complete automatic abstract syntax tree for every statement in a paper would overstate what a bounded verifier can reliably infer. Exobrain therefore starts with a small fragment, retains its exact source range, and makes every unverified dependency visible to the researcher.</p>
        <blockquote className="mt-5 border-l-2 border-indigo-400 pl-4 text-sm leading-6 text-slate-700">A formula that is locally equivalent to another formula does not, by itself, verify the reason the transformation is allowed.</blockquote>
      </section>

      <section className="mt-12">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Statuses and evidence boundary</h2>
        <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm"><table className="w-full min-w-[640px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-[0.1em] text-slate-500"><tr><th className="px-5 py-3">Status</th><th className="px-5 py-3">Meaning</th></tr></thead><tbody className="divide-y divide-slate-100"><tr><td className="px-5 py-4 font-medium text-emerald-800">Locally verified</td><td className="px-5 py-4 text-slate-600">A supported deterministic check established a local expression or calculation.</td></tr><tr><td className="px-5 py-4 font-medium text-amber-800">Declared prerequisite</td><td className="px-5 py-4 text-slate-600">The researcher supplied an assumption required by a later theorem application; Exobrain has not proved that the assumption is sufficient.</td></tr><tr><td className="px-5 py-4 font-medium text-slate-700">Dependency not checked</td><td className="px-5 py-4 text-slate-600">A candidate relation has been extracted but requires a rule-specific validator, evidence artifact, or researcher confirmation.</td></tr></tbody></table></div>
      </section>

      <section className="mt-12 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-6 sm:p-8">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Example: Gaussian integral</h2>
        <p className="mt-4 leading-7 text-slate-600">The Tonelli and polar-coordinate steps become theorem-application proof steps with explicit prerequisite edges. The radial integral is a local calculation step. The final square-root step depends on positivity. Review can then show which edge has deterministic support and which remains conditional on an explicit hypothesis.</p>
      </section>

      <section className="mt-12 border-t border-slate-200 pt-8"><h2 className="text-lg font-semibold text-slate-900">Related work and vocabulary</h2><p className="mt-3 leading-7 text-slate-600">The terminology follows established interactive theorem-proving and proof-autoformalization usage: StepProof describes verifiable sub-propositions accumulated on a proof stack, while ProofFlow explicitly constructs a directed acyclic graph of logical dependencies between proof steps. Lean provides the adjacent vocabulary of propositions, proofs, tactics, hypotheses, goals, and proof states.</p><ul className="mt-4 space-y-2 text-sm">{sources.map((source) => <li key={source.href}><a className="font-medium text-indigo-700 hover:underline" href={source.href}>{source.label}</a></li>)}</ul></section>
    </div>
  </main>;
}
