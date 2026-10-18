---
layout: ../../layouts/Article.astro
title: "Chasing the ambidextrous moving sofa — post-mortem"
---

<p class="meta">A project post-mortem · written 2026-10-18 · <a href="https://github.com/ElVec1o/moving-sofa-local-max" target="_blank">GitHub Repo</a> · <a href="../">← Maths</a></p>

# Chasing the ambidextrous moving sofa: how we attacked it, and how we were beaten

## TL;DR

We tried to prove that Romik's ambidextrous sofa, with area `A_R*` = 1.6449552…, is the largest-area sofa that can turn a corner in a width-1 hallway in both directions. We did not finish. On 2026-10-11, before we were done, another team posted a Lean 4 formalisation that claims to prove exactly this, including uniqueness. That proof is AI-assisted. Its authors say no human has reviewed it, and it depends on Baek's recent proof of Gerver's conjecture, which is itself an unrefereed preprint.

We read their repository and paper through web summaries only. We did not build it or run it. We found no flaw. If their claims hold, the headline result is theirs.

Along the way we proved several things by hand that may be of independent interest. They are listed in the section "What we actually proved". Some are our own computations and not formal proofs, and the text says which is which.

This post is also an honest account of the process: what worked, what fooled us, and where we think we lost.

## 1. The problem

A moving sofa is a planar region that can be pushed around an L-shaped corner of a hallway of width 1. The Hammersley sofa (about 2.2074) gave the first lower bound. Gerver's sofa (about 2.2195) improved it, and Baek recently posted a proof that Gerver's sofa is optimal.

The ambidextrous variant asks for one shape that can turn the corner to the left and to the right. Romik's ambidextrous sofa has area `A_R*` = 1.6449552184254408. It was conjectured optimal. We worked on proving that conjecture.

Conventions we used. Both hands share the horizontal starting strip. The two motions are reflections of each other in the line `y = 1/2` and begin with the same orientation. We fix the starting rotation to be zero. The external repository's definition has the same shared-start-rotation condition.

## 2. How we attacked it

We worked with an orchestrator and a rotating cast of AI "seats" (Sonnet agents, one at a time, to keep the machine safe), plus our own hand arguments and Rust programs. Python was banned after a memory accident. Everything is logged in a research log, an atom table of the remaining gaps, and a list of retired routes.

### 2.1 The relaxation

We reduced the sofa to a convex set. For any anchored sofa `T`, the convex hull `K` satisfies `T ⊂ I(K)`, where `I(K)` is the part of `K` that survives both rotations. We called the area of `I(K)` by the name `Φ(K)`. Then proving the conjecture amounts to proving

`(G*)  Φ(K) ≤ A_R*  for every convex K in the strip.`

A survival criterion makes this concrete (we called it F3): a point `P` survives exactly when the set of directions in which `K` pokes out of the unit disc around `P` contains no oriented orthogonal pair.

We also found a four-term formula for `Φ` as an integral of a minimum of four terms, and a Klein-group symmetry that includes the reflection `(x, y) → (−x, y)`.

### 2.2 Splitting the problem

We split the proof in two:

- **Local half.** Near Romik's sofa `Σ`, show a quantitative second-variation inequality. This became a long list of atoms (`N1` to `N10`), including an end term (`N8`) that took many rounds, a set of interval-arithmetic certificates, and a series of lemmas about thin spikes.
- **Global half.** Away from `Σ`, show `Φ` stays below `A_R*`. This is where we spent the last stretch and where we did not close the gap.

### 2.3 The global half: what worked

- **Tip bound.** The set of points near a one-ended tip has area at most `π/4` by the isodiametric inequality. This gave a clean bound on the "tip" contribution.
- **Theorem 1.** `Φ ≤ (π/2) sec² g` for hull length `L ≥ 5.7331`.
- **Theorem 2.** `Φ ≤ π/2 + E(L)` for `L ≥ 3.4789`, using a function `E(L)` that comes out of a kite-shaped zone lemma.
- **Theorem 3.** `Φ ≤ F3(L)` for `L ≥ 3.08`, using a column-pair inequality and Brunn–Minkowski on symmetrised columns. The reduction was reviewed; the last comparison with `A_R*` is numerical.
- **Existence.** A maximiser of `(G*)` exists on the compact range of lengths. We checked this by hand (upper semicontinuity, a saturation argument, a tube lemma).
- **Small L.** For `L ≤ 1.645` the bound is trivial.

### 2.4 The global half: what did not

- **Lane regime.** For hull length between 1.645 and roughly 2.7 to 3, we had a pair-LP bound that was numerical only. In the last run a float LP with extra "window cuts" reached `L ≳ 2.70`, with `Σ` itself not a tight point.
- **Shell.** Between the local radius (about .003) and the far field (about .12) we had no proof.
- **26+ routes died.** Finite relaxation plus a local theorem needed a certification we could not afford. Whole-body symmetrisation failed on explicit counterexamples. Concavity of the area functional on the whole space fails. A "far plateau" of competing bodies near 1.58 turned out to be an artefact of the parameter basis we hunted with.

### 2.5 Mistakes we caught (and some we only caught late)

- A claimed decay rate in one estimate was wrong (exponent 3, not 5).
- Some thresholds were off in the last digit (3.4789 and 5.7331, not 3.4788 and 5.733).
- A statement that "Theorem 2 was reviewed twice" was inexact: one review covered it, another covered the reduction.
- An early conclusion that "nobody else is working on this" was wrong. We searched the literature twice and missed the external repository. We found it only through a pull-request comment.

## 3. What we actually proved

Honest labels: **hand** means a written proof reviewed by a second agent; **numeric** means a computer check without an interval certificate; **computer-assisted** means interval arithmetic that no one has independently re-checked.

| Result | Status |
|---|---|
| Reduction: an anchored sofa lies inside `I(conv T)`, and F3 survival criterion | hand, reviewed |
| Tip set: area ≤ `π/4` (isodiametric) | hand |
| Zone lemma, end zones (`L ≥ 2√2`) | hand |
| `Φ ≤ A_R*` for `L ≥ 3.4789` (Theorem 2) | hand, reviewed once |
| `Φ ≤ A_R*` for `L ≥ 3.08` (Theorem 3) | hand reduction, last comparison numeric |
| Existence of a maximiser of `(G*)` | hand, reviewed |
| Local atoms of `N8` (end term, thin spikes, tails of one integral) | partly computer-assisted, reviews incomplete |
| Pair-LP for lane regime, reaching `L ≳ 2.70` | numeric only, float |
| Lane lemmas `L1`, `C2`, `P2`, `T6` | hand, not yet hostile-reviewed |

We want to be plain: `(G*)` itself is **not proved** for hull lengths below about 3.08 (by hand) or about 2.70 (numerically). The local second variation is not fully assembled.

## 4. How we were beaten

On 2026-10-11 a pull-request comment on the formal-conjectures repository pointed to [vltanh/lean4-ambidextrous-sofa](https://github.com/vltanh/lean4-ambidextrous-sofa). The repository claims a complete Lean 4 proof that Romik's sofa is the unique maximum, with the same shared-start definition we used.

We read it only through a web tool that returns summaries. We did not clone, build or run it. Here is what the proof does, in our words:

1. It normalises the hull into the strip. If the area is at most `√2` it is done. Otherwise each hallway has an effective angle strictly above `π/4`.
2. The hull is the intersection of two "downward caps", one per hallway.
3. A cap score `P` is defined for each cap: the roof area over the outer quarters minus the barrier area over the middle half. It is a one-corner quantity.
4. A fibre identity: `|S| ≤ P(U) + P(V)`, with a nonnegative defect term. We re-derived this by hand (through the agent's reading) and found it valid for every fibre with no extra hypotheses.
5. The cap theorem: `P ≤ M/2`, with equality only for Romik's cap, where `M = 1 + 4Y² + arctan Y` and `Y` solves `4Y³ + 3Y = 1`. This is the hard step. It is proved by a global quadratic calibration in the space of support functions, with a Dirichlet-type coercivity condition `1 − 3L²/8 > 0`, plus case analyses with fitted constants (37/50, 8/5, 3/8, 11/15), plus two exclusions that use Baek's area bound 2.2199.
6. Equality forces both caps to be Romik's, and closedness plus equal area gives `S = Σ`.

The key structural difference from our approach is step 5. We believed the two-corner coupling in `Φ = F₊ + F₋ − |K|` blocked any upper bound by one-corner pieces. The sum-of-scores inequality is valid, so it does not. All of the difficulty moves into the single cap theorem, which they attack with a global calibration instead of our local second variation.

### What we checked about their proof

We ran six read-only reviews (all through web summaries):

- The fibre identity and the effective-angle lemma: no flaw found.
- The cap theorem chain: stated in Lean with no extra hypotheses; no `sorry`, axiom, `native_decide` or `opaque` seen in the files read.
- The dependence on Baek: Baek's theorem is included as a Lean copy in the repository, not assumed as an axiom. A bridge lemma connects it to the ambidextrous setting, with the start-angle normalisation handled by a proved step. The Gerver area constant is proved by interval arithmetic in Lean.
- Definitions: width 1, continuous motions, shared start rotation, Lebesgue area. Standard. The class of sofas allowed is slightly larger than the usual one, which only makes the bound stronger.
- CI runs `lake build` and an audit that allows only the three standard axioms.

### Caveats we cannot remove

- We read summaries, not the files, and we did not build anything. About 1,000 files were never opened.
- The authors say no human has reviewed the proof. Their own review notes call some constants "fitted".
- The proof depends on Baek's theorem, which is an unrefereed preprint, and on a Lean copy of it whose fidelity we did not check.
- Red flags that deserve mention: a long proof of an open problem produced in a few days, hundreds of AI-repaired proofs along the way, and a formal-conjectures entry that still listed the problem as open when we looked.

If their claims hold, the headline result belongs to them. We have no priority claim: they posted on 2026-10-11.

## 5. Why we lost

- **We chose the harder relaxation and believed it was necessary.** Keeping both corners coupled made every upper bound look hard. A valid one-corner split was available and we had ruled it out in our heads.
- **Local-plus-global patching needs a shell.** Our plan required a quantitative local theorem, a far-field theorem, and a proof that nothing interesting lives in between. The middle never closed.
- **Hand proofs against industrial formalisation.** They used AI-assisted Lean at large scale. We had put Lean on hold for disk and memory reasons and relied on hand proofs and computer-assisted pieces.
- **We trusted hunts.** Numerical searches over a finite basis gave us "plateaus" and "far competitors" that were basis artefacts. Several claims had to be retracted.
- **Our literature search missed the one thing that mattered.** Two sweeps said we were alone. We were not.

## 6. What is still mathematically open

Even if their proof is fully correct, some questions remain:

- A proof that does not use Baek's theorem. Our route never needed it.
- A quantitative stability statement: how much area must be lost as a sofa moves away from `Σ`. They state this as open. We conjectured `A_R* − Φ ≥ 2.5·min(d, .13)²` and have local evidence.
- A human-readable proof. Theirs is 109 pages and Lean.
- Independent verification of the fitted-constant case analyses.

## 7. Takeaways

- Before a long campaign, search the code and discussion hubs, not just papers. Pull requests and formal-conjecture trackers are where this kind of work shows up.
- When a relaxation looks "blocked", test the blocking claim on a toy case before building a programme on it.
- Tie every numerical claim to a statistic that was fixed before the run, and report every trajectory, not the best one.
- A pause on formalisation saves memory but costs you the tool the competition used.

## Reproducibility

Our code is Rust only. The code, paper sources and formal material are in the public repository: [ElVec1o/moving-sofa-local-max](https://github.com/ElVec1o/moving-sofa-local-max). The research log, atom table, retired-route list and hazard list sit in the private folder of the project. Key figures: `A_R*` = 1.6449552184254408; thresholds 3.4789 (Theorem 2), 3.08 (Theorem 3), 5.7331 (Theorem 1). Reviews are noted in the table above.

Everything about the external repository comes from web-tool summaries read on 2026-10-18. Please check the repository yourself before relying on it.
