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

Added `translate_query()` function in `scripts/medgemma_query.py`:

```python
def translate_query(query):
    """Translate JP query to EN"""
    if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', query):
        return query

    # 翻訳プロンプトを少し強化（余計な解説を出させないようにする）
    prompt = f"""Task: Translate this Japanese medical question to English.
Rules: Output ONLY the English translation text. No explanations.

Japanese: {query}
English:"""
    
    # 翻訳時は余計なことを言わないよう短めに制限
    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': "medgemma",
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_predict': 128, 
                    'temperature': 0.0
                }
            },
            timeout=30
        )
        text = response.json().get('response', '').strip()
        # "The question is..." などの余計な枕詞がついた場合、改行で区切って最初の行だけ取るなど簡易クリーニング
        if "\n" in text:
            text = text.split("\n")[0]
        # Explanationなどが残っていたら削除する正規表現処理などを入れても良いが、まずはシンプルに
        return text
    except:
        return query
```

### RAG Query Flow

Modified `run_map_reduce_query()` to translate Japanese queries before searching:

```python
def run_map_reduce_query(query, verbose=False):
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import search_qdrant

    print(f"Query (RAG Mode): {query}")

    # 1. 翻訳 & 検索
    search_query = translate_query(query)
    # 翻訳が長文解説を含んでしまった場合のクリーニング (ログを見て簡易対策)
    if "Explanation:" in search_query:
        search_query = search_query.split("Explanation:")[0].strip()
    if "The translation is:" in search_query:
        search_query = search_query.split("The translation is:")[-1].strip()

    if verbose: print(f"Translated: {search_query}")
    
    print("1. Searching papers...")
    search_results = search_qdrant.search_medical_papers(search_query, top_k=3)
    papers = search_results['papers']
    
    if not papers:
        return "関連する論文が見つかりませんでした。"

    # 2. Atomic Facts検索
    print("2. Searching atomic facts...")
    paper_ids = [p.get('paper_id') for p in papers]
    all_facts = search_qdrant.search_atomic_facts(search_query, limit=10, paper_ids=paper_ids)
    
    facts_by_paper = {str(pid): [] for pid in paper_ids}
    for fact in all_facts:
        pid = str(fact.get('paper_id'))
        if pid in facts_by_paper:
            facts_by_paper[pid].append(fact)

    # 3. Mapフェーズ
    print("3. Analyzing each paper (Map phase)...")
    valid_findings = []
    for paper in papers:
        pid = str(paper.get('paper_id'))
        related_facts = facts_by_paper.get(pid, [])
        result = analyze_single_paper(paper, related_facts, search_query, verbose)
        if result:
            valid_findings.append(result)

    # 4. Reduceフェーズ
    print(f"4. Synthesizing {len(valid_findings)} findings (Reduce phase)...")
    final_answer = synthesize_findings(valid_findings, query)

    return final_answer
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
Query (RAG Mode): glp1受容体作動薬は変形性膝関節症に有効ですか?
Translated: Are GLP-1 receptor agonists effective for osteoarthritis?
1. Searching papers...
2. Searching atomic facts...
3. Analyzing each paper (Map phase)...
   > Analyzing: Semaglutide for osteoarthritis... (3 facts)
     -> Extracted: - Drug Name: Semaglutide
- Result: Weight reduction: -14.9% (95% CI: -16.4 to -13.4)
   > Analyzing: Effect of GLP-1 agonists on joint pain... (2 facts)
     -> Extracted: - Drug Name: Tirzepatide
- Result: Pain score improvement: -25.3 points (p<0.001)
4. Synthesizing 2 findings (Reduce phase)...

Answer:
はい、関連する研究によると、glp1受容体作動薬は変形性膝関節症に有効である可能性が示唆されています。セマグルチドは肥満のある変形性膝関節症の成人において14.9%の体重減少（95% CI: -16.4 to -13.4）を示しました。また、Tirzepatideは痛みスコアを25.3ポイント改善しました（p<0.001）。
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
  - Added `translate_query()` function for Japanese-to-English translation
  - Modified `run_map_reduce_query()` to translate Japanese queries before search
  - Implemented Map-Reduce RAG architecture (analyze_single_paper, synthesize_findings)

## Related Documentation

- [japanese-query-reranking.md](./japanese-query-reranking.md) - Previous keyword mapping approach (deprecated)
- [search-flow.md](./search-flow.md) - Overall search flow documentation
