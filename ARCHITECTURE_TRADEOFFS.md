# Pipeline Architecture Tradeoffs

This document chronicles the evolution of the documentation update pipeline — why each architecture was chosen, what problems it solved, and what new problems it introduced.

---

## v1 — Triage + Editor (Two Agent Architecture)

### How it worked
```
Query
  ↓
Triage Agent
  reads: compact section index (ID | page | title)
  outputs: list of section IDs to update
  ↓
Editor Agent
  reads: full content of each section via get_section()
  outputs: edit suggestions via submit_suggestion()
```

### Why we built it this way
Simple and intuitive — one agent to find, one agent to fix. The triage agent was given the full section index (328 entries) as a list of IDs and titles, so it could scan and decide which ones needed updating.

### Problems discovered

**Triage only sees headings, not content.**
The section index passed to triage contains `ID | page | title` — no actual content. So triage is making decisions based on section titles alone. A section titled "Running agents" gives no signal about whether it mentions `assistant` or `as_tool` inside it.

**Misses terminology and rename changes entirely.**
For queries like `"Agent.run() renamed to Agent.execute()"` or `"Rename handoff to delegation"`, triage returned 0 sections. It couldn't infer from a title like "The agent loop" that the section contains `Agent.run()` calls.

**Non-deterministic results.**
Same query could return 0, 2, or 7 sections across runs. The LLM reading 328 titles in one prompt is inconsistent.

**Inconsistent section ID parsing.**
Early versions had the triage agent output section IDs as free text, which the editor then had to parse — causing "string did not match expected pattern" errors.

### What we fixed
- Switched to structured output (`TriageResult` Pydantic model) — eliminated parsing errors
- Passed explicit section ID list to editor — no more parsing from conversation history

---

## v2 — RAG (Embeddings + Cosine Similarity)

### How it worked
```
Query
  ↓
Embed query with text-embedding-3-small
  ↓
Cosine similarity against 328 pre-computed section embeddings
  ↓
Top-K sections (K=10) passed to Editor
```

### Why we built it this way
Triage's core problem was not reading section content. RAG fixes this by embedding the full section text at index time — so retrieval is based on semantic meaning of content, not just titles.

### Problems discovered

**The full query is noisy.**
A query like `"We no longer use the term assistant, everything should be called agent"` gets embedded as one vector. Words like `"we no longer use the term"` and `"everything should be called"` dilute the signal. The actual meaningful signal is just `assistant → agent`. RAG ends up retrieving sections that are semantically similar to the instruction language, not just the affected terms.

**Retrieves topically related, not specifically affected.**
For `"Agent.run() renamed to Agent.execute()"`, RAG returned 9 sections — all about "running agents" broadly. But most didn't contain `Agent.run()` in their code. They were related to the topic but didn't need updating.

**Changelog pollution.**
The `release` page (version history entries like `0.9.0`, `0.13.0`) contains old API names by definition. RAG consistently retrieved changelog entries as candidates because they semantically match the query — but changelog entries should never be edited.

**No understanding of change type.**
RAG treats every query the same way regardless of whether it's a rename, removal, addition, or structural change. A query asking to add a new section gets the same retrieval strategy as a query asking to rename a method.

**Over-retrieval on broad terms.**
For `"assistant → agent"`, RAG retrieved 10 sections. For `"remove streaming"`, it retrieved 10 sections. The top-K cap is arbitrary and not calibrated to the scope of the change.

---

## v3 — Hybrid (Intent Extraction + RAG + Code Scan + LLM Filter)

### How it worked
```
Query
  ↓
Stage 0: Intent Extraction (LLM)
  extracts code patterns: ["as_tool", "handoff"]
  ↓
Stage 1: RAG → top 20 semantic candidates
Stage 2: Code Scan → sections whose code blocks contain the patterns
  ↓
Stage 3: Union of both → deduplicated candidates
  ↓
Stage 4: LLM Filter
  reads all candidates, keeps only sections that genuinely need updating
  ↓
Editor
```

### Why we built it this way
RAG finds semantically related sections. Code scan finds sections with exact code matches. The union should give better recall than either alone, and the LLM filter prunes false positives.

### Problems discovered

**Code scan floods the pipeline.**
The word `handoff` appears in 60 sections. `assistant` appears in 57. Any rename or removal query produces 60+ candidates from code scan alone, making the union 62–74 candidates before the filter even runs.

**LLM filter is non-deterministic at scale.**
Feeding 74 candidates (×500 chars each = ~37,000 chars) into one prompt produces inconsistent results:
```
Same query, same candidates:
  Run 1: kept=13
  Run 2: kept=7
  Run 3: kept=17
  Run 4: kept=0
```
The LLM loses coherence reading 74 sections in one shot.

**Filter returns 0 when overwhelmed.**
For many queries, the filter returned 0 — rejecting all candidates despite both RAG and code scan finding relevant sections. The filter with too many inputs defaults to aggressive pruning.

**Extreme timeout outlier.**
One query took 1447 seconds (24 minutes) — likely a retry/backoff loop triggered by a timeout on the oversized filter prompt.

**Still no understanding of change type.**
Hybrid runs all four stages for every query regardless of type. A structural reorganization query runs code scan unnecessarily. A rename query runs RAG unnecessarily.

---

## v4 — Auto (Signal Extraction + Strategy Routing)

### How it works
```
Query
  ↓
Stage 1: Validator
  rejects vague queries, prompt injection
  ↓
Stage 2: Signal Extractor (LLM)
  change_type: rename | removal | addition | behavior_change | structural
  old_terms: ["assistant"]
  new_terms: ["agent"]
  affects_code: true
  affects_prose: true
  ↓
Stage 3: Strategy Router (no LLM)
  rename/removal  → exact string scan for old_terms
  addition        → RAG semantic search
  behavior_change → RAG semantic search
  structural      → triage agent
  ↓
  (fallback: if exact scan returns 0 hits → RAG)
  (cap: if exact scan returns >15 hits → RAG)
  ↓
Stage 4: Pre-check
  filters sections where change already applied
  ↓
Stage 5: Editor
  generates suggestions for remaining sections
```

### Why this is better
- **Query-aware retrieval** — a rename query uses exact string matching, not semantic search. An addition query uses RAG. The strategy matches the nature of the change.
- **No code scan flooding** — exact scan is direct and capped, not a regex over all code blocks feeding into a batch LLM call.
- **Idempotent** — pre-check prevents duplicate suggestions on re-runs.
- **Validator kills vague queries early** — queries like "make docs clearer" are rejected before any retrieval runs.

### Problems discovered

**Signal extractor is non-deterministic.**
The same query can produce `old_terms=['as_tool']` one run and `old_terms=['agents as_tool']` the next. A phrase instead of a bare identifier causes exact scan to find 0 hits.

**Exact scan too broad for common terms.**
Terms like `assistant`, `handoff`, `tool` appear in 19–60 sections. Passing all of them to the editor causes timeouts and shallow suggestions.

**Editor overwhelmed at scale.**
Editor is an agentic loop — 2–3 tool calls per section. 25 sections = ~75 turns. The LLM loses track of which sections it has processed and starts making superficial changes to move through the list faster.

**Pre-check loses coherence at scale.**
Pre-check embeds all section contents in one prompt. 25 sections × ~800 chars = ~20,000 chars. The LLM makes inconsistent idempotency judgments at this scale.

---

## Planned Solution — User-Driven Section Selection

### Core idea
Split the pipeline into two user-triggered phases:

**Phase 1 — Discovery** (runs immediately, fast):
```
Validator → Signal Extractor → Retrieval → return section list to frontend
```

**Phase 2 — Generation** (runs only on user selection):
```
User reviews and selects sections → Pre-check → Editor
```

### Why this solves the core problems
- **No arbitrary caps** — user decides scope, not an algorithm
- **No editor overwhelm** — user selects 3–5 sections, not 25
- **No shallow suggestions** — user filters out incidental mentions before any LLM calls
- **Transparent** — user sees exactly what will be changed before committing API calls
- **Idempotency visible to user** — user can see which sections already reflect the change

### Tradeoff
Adds one interaction step — user must review and confirm before suggestions are generated. For automated pipelines this would need a different approach.

---

## Summary Table

| Version | Retrieval | Strength | Core Weakness |
|---------|-----------|----------|---------------|
| v1 Triage+Editor | LLM reads titles | Simple, structured | Blind to section content |
| v2 RAG | Embeddings + cosine | Reads content semantically | Noisy query, no change-type awareness |
| v3 Hybrid | RAG + code scan + LLM filter | Best recall | Code scan floods, filter non-deterministic at scale |
| v4 Auto | Signal extraction + routing | Query-aware strategy | Signal extractor non-deterministic, scale issues in editor |
| v5 Auto + User Selection | Same as v4 | User controls scope | Requires human in the loop |
