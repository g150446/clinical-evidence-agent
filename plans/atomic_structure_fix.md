# structure_paper.py 修正指示: Atomic Facts の自己完結化

## 問題

現在の `structure_paper.py` が生成する `atomic_facts_en` は、各文が文脈に依存しており、単独で読んだとき **何の研究の何のデータか分からない**。

### 現状の問題例（PMID_39476339 の出力より）

```
❌ "The study was a 68-week, double-blind, randomized, placebo-controlled trial conducted at 61 sites in 11 countries."
❌ "The mean age of participants was 56 years."
❌ "The difference in mean body weight change between semaglutide and placebo was statistically significant (P<0.001)."
```

- 「The study」「The participants」が何を指すか、この文だけでは不明
- ベクトル検索で個別にヒットした際、ユーザーに提示できない品質

### あるべき姿

```
✅ "The semaglutide 2.4mg trial for obesity with knee osteoarthritis (PMID_39476339) was a 68-week, double-blind, randomized, placebo-controlled trial conducted at 61 sites in 11 countries."
✅ "In the semaglutide 2.4mg vs placebo trial for obesity with knee osteoarthritis (PMID_39476339), the mean age of participants was 56 years."
✅ "Body weight reduction with semaglutide 2.4mg vs placebo was statistically significant (P<0.001) in the 68-week RCT (PMID_39476339)."
```

---

## 修正対象ファイル

`structure_paper.py`

---

## 修正箇所 1: STRUCTURE_PROMPT 内の Layer B 指示（226〜231行目付近）

### Before

```python
**Layer B: Atomic Facts (English only)**
- Create 10-20 facts, each 1 sentence with 1 verifiable fact
- Include quantitative data and statistical significance
- Separate author claims from observed facts
```

### After

```python
**Layer B: Atomic Facts (English only)**
- Create 10-20 facts, each 1 sentence with 1 verifiable fact
- CRITICAL: Each fact must be SELF-CONTAINED and understandable WITHOUT any other context
  - NEVER start with "The study", "The participants", "The trial", "The authors" as the sole subject
  - ALWAYS include: (1) the specific intervention name and dosage, (2) the condition/population, and (3) the PMID
  - Each fact must pass the "isolation test": reading ONLY that one sentence, the reader must know WHAT study, WHAT intervention, WHAT population, and WHAT was measured
- Examples:
  - BAD:  "The mean age of participants was 56 years."
  - GOOD: "In the semaglutide 2.4mg trial for obesity with knee osteoarthritis (PMID_39476339), the mean age of participants was 56 years."
  - BAD:  "The reduction was statistically significant (p<0.001)."
  - GOOD: "The body weight reduction with semaglutide 2.4mg vs placebo was statistically significant (p<0.001) in the 68-week RCT (PMID_39476339)."
  - BAD:  "Gastrointestinal disorders were the most common reason for discontinuation."
  - GOOD: "Gastrointestinal disorders were the most common reason for discontinuation in the semaglutide 2.4mg group in the obesity/knee osteoarthritis trial (PMID_39476339)."
- Include quantitative data and statistical significance
- Separate author claims from observed facts
```

---

## 修正箇所 2: STRUCTURE_PROMPT 内の JSON テンプレート（145〜149行目付近）

### Before

```python
    "atomic_facts_en": [
      "Fact 1 with quantitative data",
      "Fact 2 with statistical significance",
      ...
    ],
```

### After

```python
    "atomic_facts_en": [
      "Self-contained fact 1: must include intervention name, condition, PMID, and quantitative data (e.g., 'Semaglutide 2.4mg reduced body weight by 13.7% vs 3.2% with placebo in adults with obesity and knee osteoarthritis (PMID_39476339).')",
      "Self-contained fact 2: each fact independently understandable without reading other facts",
      ...
    ],
```

---

## 修正箇所 3: system メッセージの強化（338〜341行目付近）

### Before

```python
messages=[
    {"role": "system", "content": "You are a medical research expert. Return only valid JSON."},
    {"role": "user", "content": prompt}
],
```

### After

```python
messages=[
    {"role": "system", "content": "You are a medical research expert. Return only valid JSON. IMPORTANT: Every atomic_facts_en entry must be a fully self-contained sentence that includes the intervention name, condition, and PMID. Never use 'The study' or 'The participants' without specifying which study."},
    {"role": "user", "content": prompt}
],
```

---

## 修正の適用範囲

- 上記3箇所の修正のみで対応可能
- `batch_structure_papers.py` の修正は不要
- 既に構造化済みの論文を再処理する場合は `--force` フラグを使用:

```bash
python3 scripts/batch_structure_papers.py --all-domains --force
```

---

## 検証方法

修正後、1本の論文で動作確認:

```bash
python3 scripts/structure_paper.py pharmacologic glp1_receptor_agonists <任意のPMID>
```

出力された JSON の `atomic_facts_en` の各文が以下を満たすか確認:

1. **介入名と用量が明記されている**（例: "semaglutide 2.4mg"）
2. **対象疾患/集団が明記されている**（例: "obesity with knee osteoarthritis"）
3. **PMIDが含まれている**（例: "(PMID_39476339)"）
4. **"The study" 等の曖昧な主語で始まっていない**
