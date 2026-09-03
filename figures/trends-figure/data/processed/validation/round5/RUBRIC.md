# Round five rubric — `agentic_ai`

**Written before the sample was drawn and before any abstract was read.**
Pre-registering matters more here than in any previous round: the central
question is definitional, not lexical, and a rubric written after seeing the
papers is a rubric fitted to them.

Status when this was written: config on disk is **themes v10**; the data under
`data/processed/` is stamped **themes v9**. No draw until the v10 re-run lands
and the header says v10.

---

## The author's definition, verbatim

> "exploring using an AI agent to do pathology or radiomics research, or
> clinical application"

## The question this leaves open

Does the row mean papers that **build** agentic systems, or papers **about**
agentic AI? "Exploring using an AI agent to do X" reads wider than "building
one" — a review that examines how agents could do pathology is exploring
exactly that — but narrower than "any paper that says the word".

The project has two precedents and they point in opposite directions, so
neither settles it:

- `digital_twins` was ruled **inclusive**: the row "tracks trends of interest in
  the literature, not successful construction". A review naming twins among
  future directions counts.
- `virtual_staining` was ruled to **exclude** its adjacent class: biomarker
  status prediction is not virtual staining, even though the row's name invites
  it.

**Therefore this round scores both readings and reports both.** The author's
ruling can then be applied without anyone re-reading 35 abstracts. This is the
same device that worked for round four's five label-free-source papers.

## Labels, applied to every paper

Each paper gets exactly one **kind**:

| Kind | Meaning |
|---|---|
| `builds` | Develops, implements or evaluates an agentic system: one that plans, decomposes a task, selects or invokes tools, or acts over multiple steps toward a goal. |
| `about` | Substantively about agentic AI — a review or perspective in which agentic AI is a subject, given more than a sentence. |
| `mention` | Agentic wording appears, but the paper is neither of the above. A single clause in a list of future directions. |
| `rl_agent` | "Agent" in the reinforcement-learning or multi-agent-architecture sense: an RL policy, or "multi-agent collaboration" as a metaphor for network components. |
| `misnomer` | The authors call an ordinary, non-agentic model an "AI agent". |

Two derived verdicts:

- **strict** = `builds`
- **inclusive** = `builds` + `about`

`rl_agent` and `misnomer` are out under both readings. They are recorded apart
rather than merged into `mention`, because they have different remedies: a
`misnomer` is unfixable by any regex, while `rl_agent` is a vocabulary decision
the owner deliberately deferred.

## Two blinding rules, both load-bearing

1. **The reading sheet carries title and abstract only** — no firing pattern, no
   year, no rule label. Withholding the pattern prevents anchoring on the
   matching phrase, as in round four.
2. **The year is withheld specifically.** Precision is reported to be strongly
   time-dependent (89% from 2025 on, 12% before). If the labeler can see the
   year, that correlation is partly manufactured. The split is applied *after*
   labelling, never during it.

A census cannot be blind to membership — every paper in the row is
rule-positive by construction — and that limitation applies here as it did to
digital twins and virtual staining. The residual bias runs toward generosity.

## Reporting

- Precision under both readings, with Wilson intervals.
- **Pre-2024 and 2024-onward reported separately, never pooled.** The author has
  drawn the figure's line at 2024 because "agent" acquired its current sense
  around then; a pooled number would describe neither era.
- Counts by kind, so the size of each error class is visible.
- Per-pattern precision, as in round four, to show whether any single pattern
  carries the error.

## The prior being tested

The classification agent estimates from titles and firing excerpts that 14–17 of
35 build an agentic system and about 3 more are reviews squarely about it. It
offered this as a prior, not a measurement. This round is a full read of every
abstract and **confirms or refutes it**; it does not reproduce it. No per-paper
judgment from that estimate was consulted.
