# Japanese Query Translation Implementation

## Overview

This document describes the Japanese-to-English translation approach for improving search accuracy when users submit Japanese queries to the clinical evidence agent.

## Problem Statement

When querying in Japanese (e.g., "glp1受容体作動薬は変形性膝関節症に有効ですか?"), the system failed to retrieve relevant atomic facts from the correct papers:

| Issue | Description |
|-------|-------------|
| Root Cause | SapBERT (PubMedBERT-based) is trained on English text |
| Japanese Similarity | Japanese terms like "変形性膝関節症" have low similarity scores |
| Result | Incorrect papers' atomic facts ranked higher |

## Solution: Query Translation

### Architecture

```
Japanese Query: "glp1受容体作動薬は変形性膝関節症に有効ですか?"
        ↓
MedGemma Translation (~3 seconds)
        ↓
English Query: "Are GLP-1 receptor agonists effective for osteoarthritis?"
        ↓
SapBERT Search (high-precision matching)
        ↓
PMID_39476339's atomic facts ranked correctly
```

### Implementation

Added `translate_query_to_english()` function in `scripts/medgemma_query.py`:

```python
def translate_query_to_english(query, model="medgemma", timeout=30):
    """
    Translate Japanese medical query to English using MedGemma
    """
    prompt = f"""Translate this Japanese medical question to English. Output ONLY the English translation, no explanations or additional text.

Japanese: {query}
English:"""
    
    result = query_ollama(
        prompt=prompt,
        model=model,
        temperature=0.1,
        timeout=timeout
    )
    
    if result['error']:
        return {
            'original': query,
            'translation': query,  # Fallback to original
            'duration_ms': result['duration_ms'],
            'error': result['error']
        }
    
    translation = result['response'].strip()
    
    # Clean up: Remove extra explanations
    translation = translation.replace('English:', '').strip()
    translation = translation.replace('The English translation is:', '').strip()
    translation = translation.replace('The translation is:', '').strip()
    translation = translation.replace('"', '').strip()
    translation = translation.replace("'", '').strip()
    
    # Use first valid line
    lines = translation.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('Japanese:') and not line.startswith('The '):
            clean_lines.append(line)
    
    if clean_lines:
        translation = clean_lines[0]
    
    # Complete sentence if needed
    if translation and not translation.endswith('?') and not translation.endswith('.'):
        translation += '?'
    
    return {
        'original': query,
        'translation': translation,
        'duration_ms': result['duration_ms'],
        'error': None
    }
```

### RAG Query Flow

Modified `run_rag_query()` to translate Japanese queries before searching:

```python
def run_rag_query(query, verbose=False):
    import re
    
    # Detect language
    is_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query))
    language = 'ja' if is_japanese else 'en'
    
    # Translate Japanese to English for search
    search_query = query
    if is_japanese:
        print("0. 日本語クエリを英語に翻訳...")
        translation_result = translate_query_to_english(query)
        if translation_result.get('error'):
            print(f"   ✗ 翻訳エラー: {translation_result['error']}")
            print(f"   ⚠ 元のクエリで検索を続行")
        else:
            search_query = translation_result['translation']
    
    # Search with English query (high precision)
    search_results = search_qdrant.search_medical_papers(search_query, top_k=5)
    
    # Generate answer in original language (Japanese query = Japanese answer)
    return ask_medgemma_with_qdrant(papers, atomic_facts, query, language=language)
```

## Test Results

### Before (Japanese query without translation)

| Metric | Value |
|--------|-------|
| Query Language | Japanese (multilingual-e5) |
| Top Paper | PMID_39476339 ranked low |
| Result | 120 second timeout |

### After (Japanese query with translation)

| Metric | Value |
|--------|-------|
| Translation Time | ~3 seconds |
| Query Language | English (SapBERT) |
| Top Paper | PMID_39476339 ranked #1 |
| Total Time | 19 seconds |
| Answer Quality | Correct (WOMAC pain score improvement mentioned) |

### Sample Output

**Input:**
```
glp1受容体作動薬は変形性膝関節症に有効ですか?
```

**Output:**
```
はい、関連する研究によると、glp1受容体作動薬は変形性膝関節症に有効である可能性が示唆されています。
Paper 1では、セマグルチドは肥満のある変形性膝関節症の成人における体重減少、痛みスコアの改善、身体機能スコアの改善に有効であることが示されました。
```

## Advantages Over Keyword Mapping

| Approach | Maintainability | Accuracy | Flexibility |
|----------|-----------------|----------|-------------|
| Keyword Mapping | Manual updates required | Limited to mapped terms | Static |
| Query Translation | Automatic | Handles any medical term | Dynamic |

### Why Keyword Mapping is No Longer Needed

1. **Query is translated to English** - All downstream processing uses English
2. **PICO data is English** - Direct keyword matching works
3. **No manual maintenance** - New medical terms handled automatically
4. **Consistent results** - Same pipeline for all queries

## Files Modified

- `scripts/medgemma_query.py`
  - Added `translate_query_to_english()` function
  - Modified `run_rag_query()` to translate Japanese queries

## Related Documentation

- [japanese-query-reranking.md](./japanese-query-reranking.md) - Previous keyword mapping approach (deprecated)
- [search-flow.md](./search-flow.md) - Overall search flow documentation
