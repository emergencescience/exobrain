# Proof Fragments & Dependency Graphs

> **Status:** Product and implementation reference for Exobrain.
>
> **Audience:** Researchers, scientific-computing users, reviewers, and contributors.
> **Last updated:** 2026-08-14.

## Purpose

Exobrain helps researchers inspect how a bounded part of a derivation is supported. It does **not** claim that every Markdown or LaTeX paper is automatically transformed into a complete machine-checked proof.

The primary user-facing structure is a **proof dependency graph**. It shows a small set of **proof steps**, their declared assumptions, their local deterministic checks, and the **proof obligations** that remain unresolved. A graph may cover one theorem, one derivation subsection, or another local **proof fragment**. It is deliberately smaller and more auditable than a full-paper syntax tree.

## Canonical vocabulary

| Term | Meaning in Exobrain | Why this term is used | Do not confuse it with |
|---|---|---|---|
| **Proof fragment** | A bounded, source-addressable portion of a derivation that Exobrain can parse and review as a unit. | It accurately signals a local scope rather than a claim to formalize a whole paper. | A complete formal proof or full-document AST. |
| **Proof step** | One reviewable unit in a fragment: an assumption, definition, statement, derivation step, theorem application, or conclusion. | StepProof uses stepwise verification of natural-language proof sentences / sub-propositions; proof assistants also organise interaction around local goals and steps.[1] [2] | A line of LaTeX. One step can span text, equations, or several source lines. |
| **Proof dependency graph** | A directed graph showing which proof steps, definitions, and assumptions a later step uses. | ProofFlow calls this a DAG of logical dependencies between proof steps; KnowTeX uses dependency graphs for definitions, results, and proofs.[3] [4] | Proof that every edge is already valid. The graph exposes obligations; it does not discharge them automatically. |
| **Assumption** | A hypothesis, domain restriction, theorem precondition, modelling choice, or external fact accepted for the fragment. | Standard mathematical and formal-methods vocabulary. Assumptions must remain visible at the point of use. | Deterministically verified evidence. |
| **Intermediate result** | A derived statement that can support one or more later proof steps. | Matches normal mathematical writing and ProofFlow’s intermediate-lemma structure.[3] | A final conclusion. |
| **Theorem application** | A proof step that invokes a named theorem or rule, such as Tonelli, Fubini, a change-of-variables theorem, or a chain rule. | Separates “the formula is syntactically plausible” from “the theorem’s hypotheses hold.” | A purely algebraic rewrite. |
| **Proof obligation** | A specific local proposition or dependency edge that needs to be discharged by a defined validation rule, evidence artifact, or reviewer decision. | `Proof obligation` and `goal` are standard formal-verification terms; Why3 uses them for statements to be proved.[5] | A vague TODO or an assertion already established. |
| **Evidence artifact** | A reproducible record supporting a local step: a bounded symbolic check, numerical computation, code run, citation, or reviewer-approved observation. | Makes the source, method, scope, and result inspectable. | A model explanation or unsupported chat response. |

### Terms intentionally not used as the main UI label

| Term | Use in Exobrain | Reason |
|---|---|---|
| **Claim AST** | Technical route name and possible internal parser representation only. | “AST” is an implementation term and suggests a total syntactic parse of the paper, which Exobrain does not promise. |
| **Proof tree** | A special case of the dependency graph when every node has one downstream path. | Research derivations commonly reuse definitions and intermediate results, so the realistic structure is a directed acyclic graph (DAG), not always a tree. |
| **Formal proof** | Reserved for a proof checked by a formal kernel or equivalent specified proof checker. | Exobrain’s bounded symbolic and evidence checks are valuable without claiming Lean/Coq/Isabelle-level formalization. |
| **Argument graph** | Used only in research-assurance or evidence-report contexts. | In structured assurance, claims, arguments, context, and evidence form a broader confidence case; that is not synonymous with a deductive mathematical proof.[6] |

## Data model

A persisted review records a versioned proof dependency graph alongside the immutable verification snapshot. The graph is an auditable **candidate structure**: its nodes and edges retain source ranges and status separately.

```text
ProofDependencyGraph
├── proof fragment: “Assumptions”
│   └── proof step: assumption
├── proof fragment: “Derivation”
│   ├── proof step: definition
│   ├── proof step: theorem application
│   ├── proof step: derivation step
│   └── proof step: conclusion
└── dependencies (directed edges)
    ├── requires_assumption
    └── derives
```

Each proof step has a stable identifier, exact Markdown source range, kind, source text, and **local check status**. Each dependency has a source step, target step, relation kind, a separate **edge status**, and a concise reason. The separation is essential:

> A locally verified equation does **not** automatically verify the dependency edge that says why the transformation is permitted.

For example, a symbolic engine may validate a radial integral calculation. It cannot thereby establish that Tonelli’s theorem applies, that a coordinate transformation has the right domain and Jacobian, or that all omitted boundary conditions are harmless.

## Status semantics

| Status | Applies to | Meaning |
|---|---|---|
| `locally_verified` | Proof step | A supported deterministic rule verified the limited mathematical expression or computation in the step. |
| `partially_checked` | Proof step | Some contained expressions were checked, but the whole step was not established. |
| `not_checked` | Proof step or dependency | Exobrain has parsed the item but has no validator or evidence for it yet. |
| `declared` | Dependency | An explicit prerequisite / assumption was connected to a step; its sufficiency remains unproved. |
| `verified_under_assumptions` | Future dependency status | A rule-specific validator established the inference conditional on visible, declared assumptions. |
| `requires_evidence` | Future dependency status | A computation, citation, domain condition, reviewer decision, or stronger formalization is required. |
| `failed` | Proof step or dependency | A defined check found an inconsistency, counterexample, invalid precondition, or incompatible evidence. |
| `inconclusive` | Proof step or dependency | The available bounded methods cannot decide the item. |

Exobrain must label only the precise object established by a check. A green local status on one proof step cannot make a whole fragment or final conclusion green unless every necessary incoming dependency is established under an explicit status policy.

## Local-first workflow

The recommended author and reviewer workflow is incremental.

| Stage | Researcher action | Exobrain responsibility |
|---|---|---|
| Scope | Select a claim, derivation subsection, or calculation block. | Create a source-addressable proof fragment and immutable verification snapshot. |
| Structure | Review the candidate proof steps and dependencies. | Keep parsing decisions visible and editable; never hide ambiguity. |
| Assumptions | Confirm domain restrictions, named theorems, and modelling assumptions. | Attach them as explicit prerequisites rather than silently treating them as facts. |
| Discharge | Run a supported symbolic rule, attach evidence, add a citation, or mark a reviewer-approved hold. | Record the validator, inputs, outputs, source hash, and scope. |
| Review | Inspect which edges remain open or stale after edits. | Propagate stale / blocked status and preserve the evidence trail. |

This follows the interaction philosophy of stepwise proof verification: retain already reviewed steps, localise errors, and allow a researcher to hold an unresolved step provisionally rather than pretending it is verified.[1] It also follows the dependency-graph approach of preserving the logical structure of a human-written argument before attempting formalization.[3]

## Example: Gaussian integral

For the standard first-quadrant Gaussian integral derivation, a useful initial proof fragment contains the following steps.

| Step | Kind | Incoming dependencies | Expected evidence status |
|---|---|---|---|
| The integrand is nonnegative; the integral has the stated interpretation. | Assumption | — | `declared` unless independently established. |
| Define \(I = \int_0^\infty e^{-x^2}dx\). | Definition | — | `not_checked` or syntactically parsed. |
| Rewrite \(I^2\) as a product integral. | Derivation step | Definition of \(I\). | A bounded algebraic / definitional rule may support it. |
| Convert the product integral to a double integral. | Theorem application | Tonelli/nonnegativity assumption. | `verified_under_assumptions` only when the rule and visible preconditions match. |
| Apply polar coordinates and the Jacobian \(r\). | Theorem application | Coordinate-change assumptions and region bounds. | `requires_evidence` or conditional verification. |
| Evaluate the radial and angular integrals. | Derivation step | The transformed integral. | Local symbolic / limit checks where supported. |
| Select the positive square root. | Derivation step | \(I^2=\pi/4\) and positivity. | Conditional on the positivity premise. |
| State \(I=\sqrt{\pi}/2\). | Conclusion | All necessary prior steps. | Never stronger than the weakest required edge. |

The useful outcome is not thirty independent equation cards. It is a reviewable explanation of **which inference is valid, under which assumptions, and which link still needs evidence**.

## Author annotations and future compatibility

The initial parser extracts candidate structure from headings, paragraphs, displayed mathematics, and conservative lexical cues. It should not rely on inference alone forever. Mathematical dependency tooling such as KnowTeX and Lean Blueprint demonstrates the value of author-declared relationships.[4]

A future Exobrain document syntax may support optional, human-editable annotations such as:

```markdown
<!-- exobrain: step=tonelli-application uses=nonnegative-integrand -->
<!-- exobrain: requires=tonelli-nonnegative -->
```

These annotations would be an authoring convenience, not an escape hatch from evidence: a declared relation remains a proof obligation until a defined rule, evidence artifact, or reviewer decision addresses it.

## Product boundary

Exobrain is an **evidence and verification workspace**, not a replacement for Lean, Rocq/Coq, Isabelle, or a domain theorem-proving kernel. Its near-term value lies in making informal scientific derivations structurally legible, locally checkable, reproducible, and reviewable. When a claim needs stronger assurance, Exobrain should surface that gap and provide a path to an appropriate formal or external tool rather than overclaiming certainty.

## References

[1] Hu, Xiaolin; Zhou, Qinghua; Grechuk, Bogdan; Tyukin, Ivan. [*StepProof: Step-by-step verification of natural language mathematical proofs*](https://arxiv.org/html/2506.10558v2). arXiv:2506.10558v2, 2025.

[2] Avigad, Jeremy; de Moura, Leonardo; Kong, Soonho; Ullrich, Sebastian, et al. [*Theorem Proving in Lean 4*](https://lean-lang.org/theorem_proving_in_lean4/). Lean Community documentation, accessed 2026-08-14.

[3] Cabral, Rafael; Manh, Tuan; Yu, Xuejun; Tai, Wai Ming; Feng, Zijin; Xin, Shen. [*ProofFlow: A Dependency Graph Approach to Faithful Proof Autoformalization*](https://proceedings.iclr.cc/paper_files/paper/2026/hash/5fce5198dbf92d5ff45f74504431e2ff-Abstract-Conference.html). ICLR 2026.

[4] Uskuplu, Elif; Moss, Lawrence S.; de Paiva, Valeria. [*KnowTeX: Visualizing Mathematical Dependencies*](https://arxiv.org/html/2601.15294v1). arXiv:2601.15294v1, 2026.

[5] Why3 developers. [*Interactive Proof Assistants*](https://why3.org/doc/itp.html). Why3 1.8.2 documentation, accessed 2026-08-14.

[6] Information Commissioner’s Office. [*Argument-based assurance cases*](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/explaining-decisions-made-with-artificial-intelligence/annexe-5-argument-based-assurance-cases/). UK ICO guidance, accessed 2026-08-14.
