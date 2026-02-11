# Japanese Query Reranking Implementation

> **⚠️ DEPRECATED**: This document describes the previous keyword mapping approach. The current implementation uses **query translation** instead. See [japanese-query-translation.md](./japanese-query-translation.md) for the current approach.

## Overview (Historical)

This document describes the **deprecated** implementation of a 2-stage search algorithm and Japanese-English keyword mapping to improve search ranking.

## Why This Approach Was Replaced

| Issue | Keyword Mapping | Query Translation |
|-------|-----------------|-------------------|
| Maintainability | Manual updates for each new term | Automatic |
| Accuracy | Limited to mapped terms | Handles any term |
| Complexity | High (multiple dictionaries) | Low (single function) |

## Original Implementation (Deprecated)

### 2-Stage Search Algorithm (Still Active)

The 2-stage reranking algorithm is still used for **English queries**:

#### Stage 1: Vector Similarity Search
- Retrieve top 30 candidates using vector cosine similarity
- Uses multilingual-e5 embeddings (1024-dim)

#### Stage 2: Keyword-Based Reranking
- Extract medical keywords from query
- Calculate bonus scores based on keyword importance
- Add bonus to base similarity score
- Re-sort and return top N results

### Japanese-English Keyword Mapping (Removed)

The `JP_TO_EN_KEYWORDS` dictionary was used to map Japanese terms to English equivalents:

```python
# REMOVED - No longer needed with query translation
JP_TO_EN_KEYWORDS = {
    '変形性膝関節症': ['osteoarthritis', 'knee'],
    '膝': ['knee'],
    '糖尿病': ['diabetes'],
    # ... etc
}
```

**This has been removed** because:
1. Japanese queries are now translated to English before search
2. All downstream keyword matching works directly on English text
3. No manual maintenance required

## Current Approach

For the current implementation, see:
- **[japanese-query-translation.md](./japanese-query-translation.md)** - Query translation using MedGemma

## Migration Guide

If you have code that relied on `JP_TO_EN_KEYWORDS`:

1. **Before**: Japanese query → Keyword mapping → English matching
2. **After**: Japanese query → MedGemma translation → English search

No code changes needed in calling code - the translation is handled internally in `run_rag_query()`.

## Files

- `scripts/medgemma_query.py` - Contains `translate_query_to_english()` (current approach)
- `scripts/search_qdrant.py` - Contains English-only keyword reranking

## Related Documentation

- [japanese-query-translation.md](./japanese-query-translation.md) - Current approach (recommended)
- [search-flow.md](./search-flow.md) - Overall search flow documentation
