# Pipeline Improvements

## Problems Fixed

### 1. Inconsistent Results

**Problem:** Sometimes returns 0, 1, or 2 suggestions inconsistently.

**Root Causes:**

- The entire 328-section index was being dumped into the triage agent prompt (too many tokens)
- Vague handoff mechanism where triage agent just "lists" section IDs in text
- Editor agent had to parse section IDs from conversation history (unreliable)
- No structured output format
- Poor error handling

**Solutions:**

- ✅ Switched to **structured output** using Pydantic models for triage results
- ✅ Limited section index in prompt to first 100 + patterns (reduced tokens)
- ✅ Separated pipeline into two explicit stages with clear data passing
- ✅ Editor agent now receives explicit list of sections to process
- ✅ Upgraded models from `gpt-4o-mini` to `gpt-4o` for better reliability
- ✅ Added comprehensive error handling and logging at each stage

### 2. "String did not match expected pattern" Error

**Problem:** Cryptic error message with no context.

**Root Causes:**

- Agent trying to parse section IDs from free-form text
- No validation of section IDs before processing
- Errors not caught or logged properly

**Solutions:**

- ✅ Structured output eliminates parsing errors
- ✅ Section IDs now passed as typed list, not parsed from text
- ✅ Try-catch blocks around each pipeline stage
- ✅ Detailed logging shows exactly where failures occur
- ✅ Better error messages returned to frontend

## New Architecture

### Before (Unreliable)

```
Triage Agent → (handoff with text) → Editor Agent
                                      ↓
                                   Parse section IDs from conversation
                                   (error-prone)
```

### After (Reliable)

```
Stage 1: Triage Agent
  Input: User query + compact section index
  Output: TriageResult { section_ids: [...], reasoning: "..." }
  ↓
Stage 2: Editor Agent
  Input: User query + explicit section list
  Output: Suggestions via submit_suggestion() tool calls
```

## Key Improvements

1. **Structured Output**
   - Triage agent returns `TriageResult` Pydantic model
   - No more parsing section IDs from free text
   - Type-safe data passing between stages

2. **Token Optimization**
   - Only show first 100 sections in prompt
   - Provide section patterns for discovery
   - Reduced prompt size by ~70%

3. **Better Models**
   - Upgraded from `gpt-4o-mini` to `gpt-4o`
   - More reliable reasoning and tool calling
   - Better at following complex instructions

4. **Error Handling**
   - Try-catch around each stage
   - Detailed logging at every step
   - Graceful degradation (returns empty list instead of crashing)
   - Helpful error messages to users

5. **Debugging Tools**
   - `test_pipeline.py` - Test queries locally
   - `refresh_docs_cache.py` - Update documentation cache
   - Detailed logs show exactly what the agents are doing

## Testing

Test the improved pipeline:

```bash
cd backend

# Test with a specific query
python3 scripts/test_pipeline.py "We removed support for agents.as_tool() method"

# Check the logs to see:
# - Which sections were identified
# - What suggestions were generated
# - Any errors that occurred
```

## Expected Behavior Now

1. **Consistent Results**: Same query should produce same suggestions
2. **Clear Logging**: See exactly what the AI is thinking
3. **Better Errors**: Helpful messages instead of cryptic failures
4. **More Suggestions**: Better at identifying all relevant sections
5. **Faster**: Reduced token usage = faster responses

## Monitoring

Check backend logs for:

- `Triage complete | identified=N sections` - How many sections found
- `Target sections: [...]` - Which sections will be processed
- `Editor complete | suggestions=N` - How many suggestions generated
- Any ERROR lines indicate failures

## Next Steps (Optional)

For production, consider:

- Vector search instead of full index in prompt
- Caching triage results for similar queries
- Parallel processing of sections
- Fine-tuned model for section identification
- User feedback loop to improve accuracy

---

## Planned Improvements

### 1. User-Driven Section Selection (High Priority)

**Problem:** The pipeline currently processes all retrieved sections automatically, which causes:
- Editor generating cosmetic/no-op suggestions on irrelevant sections
- Long processing times (25 sections × editor calls = timeouts)
- No user control over what gets processed

**Proposed Solution:**

Split the pipeline into two explicit user-triggered phases:

**Phase 1 — Discovery** (runs immediately on query submit):
```
Stage 1: Validator
Stage 2: Signal Extractor  → change_type, old_terms, affects_code
Stage 3: Retrieval         → list of affected section IDs
```
Returns the section list to the frontend instantly — no LLM editor calls yet.

**Phase 2 — Generation** (runs only on user selection):
```
User reviews section list, checks the ones they want
→ clicks "Generate Suggestions"
Stage 4: Pre-check         → filter already-applied sections
Stage 5: Editor            → generate suggestions for selected sections only
```

**Why this is better:**
- User sees what will be changed before any suggestions are generated
- No wasted API calls on irrelevant sections
- No arbitrary caps needed — user decides the scope
- Solves "current and suggested look the same" — user filters out incidental mentions upfront
- Much faster initial response

**Frontend changes needed:**
- After query submit, show a checklist of retrieved sections
- "Generate Suggestions" button triggers Phase 2 on checked sections only
- Selected sections passed as `section_ids` in the request body

### 2. Section Type Tagging (Quick Win)

**Problem:** `release` page changelog entries (e.g. `0.9.0`, `0.13.0`) are retrieved as candidates and sometimes suggested for editing — but changelog entries are historical records and should never be modified.

**Solution:** Tag sections at index time with `section_type: "content" | "changelog" | "example"` based on their `page_id`. Exclude `changelog` sections from all retrieval strategies.

### 3. Signal Extractor — Enforce Short Identifiers

**Problem:** Signal extractor sometimes returns natural language phrases as `old_terms` (e.g. `"agents as_tool"` instead of `"as_tool"`), causing exact scan to find 0 hits.

**Solution:** Add explicit rules to the signal extractor prompt:
- Always extract the bare code identifier, never surrounding words
- `"agents as_tool"` → `["as_tool", "Agent.as_tool", ".as_tool("]`
- Include all syntactic variations of the identifier

## Configuration

You can tune the pipeline behavior in `backend/app/pipeline_config.py`:

```python
from app.pipeline_config import PipelineConfig

# Custom configuration
config = PipelineConfig(
    triage_model="gpt-4o",           # Model for finding sections
    editor_model="gpt-4o",           # Model for generating edits
    max_sections_in_prompt=100,      # How many sections to show
    verbose_logging=True,            # Detailed logs
)

# Use in pipeline
suggestions = await run_pipeline(query, docs, logger, config)
```

Pre-configured options:

- `DEFAULT_CONFIG` - Balanced (gpt-4o, 100 sections)
- `FAST_CONFIG` - Cheaper (gpt-4o-mini, 50 sections)
- `PRODUCTION_CONFIG` - Most reliable (gpt-4o, 150 sections, retries)
