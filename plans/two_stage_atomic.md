# structure_paper.py 修正指示: 2段階処理による Atomic Facts の品質向上

## 概要

現在の `structure_paper.py` は1回のAPIリクエストで全レイヤーを同時生成している。
これを **2段階に分割**し、Stage 1 で生成した `generated_questions` を Stage 2 の入力として渡すことで、
**各質問に回答する形の自己完結的な atomic facts** を生成する。

---

## 現状のアーキテクチャ

```
[論文データ] → [1回のAPIリクエスト] → [全レイヤー同時生成]
                                         ├── PICO
                                         ├── atomic_facts  ← 質問と無関係に生成
                                         ├── generated_questions
                                         ├── quantitative_data
                                         ├── limitations
                                         ├── mesh_terminology
                                         ├── embeddings_metadata
                                         └── cross_references
```

### 問題点
- atomic_facts が generated_questions を参照できない
- atomic_facts が「The study」等の曖昧な主語で文脈依存的になる
- 質問と回答の対応関係が保証されない

---

## 修正後のアーキテクチャ

```
[論文データ]
    │
    ▼
[Stage 1: APIリクエスト #1]
    │  生成対象:
    │  ├── metadata
    │  ├── pico_en
    │  ├── generated_questions (en)
    │  ├── mesh_terminology
    │  ├── quantitative_data
    │  ├── limitations
    │  └── cross_references
    │
    ▼
[Stage 2: APIリクエスト #2]
    │  入力: 論文データ + Stage 1 で生成した generated_questions
    │  生成対象:
    │  ├── atomic_facts_en  ← 質問に回答する形で生成
    │  └── embeddings_metadata
    │
    ▼
[2つの出力をマージ] → [最終JSON出力]
```

---

## 修正対象ファイル

`structure_paper.py`

---

## 修正手順

### Step 1: STRUCTURE_PROMPT を STAGE1_PROMPT にリネーム・修正

現在の `STRUCTURE_PROMPT`（98行目〜251行目）を `STAGE1_PROMPT` にリネームし、
**atomic_facts_en と embeddings_metadata を生成対象から除外**する。

#### Before（98行目）

```python
STRUCTURE_PROMPT = """You are a medical research expert specializing in evidence synthesis. Structure the following paper according to the 5-layer schema below.
```

#### After

```python
STAGE1_PROMPT = """You are a medical research expert specializing in evidence synthesis. Structure the following paper according to the schema below.

NOTE: Do NOT generate atomic_facts_en or embeddings_metadata in this step. They will be generated separately.
```

#### JSON テンプレート内の変更

`STAGE1_PROMPT` 内の JSON テンプレートから以下を **削除**:

```python
# 削除する部分
    "atomic_facts_en": [
      "Fact 1 with quantitative data",
      "Fact 2 with statistical significance",
      ...
    ],
```

```python
# 削除する部分
  "embeddings_metadata": {{
    "sapbert_targets": [
      "PICO combined text for medical concept embedding",
      "Key atomic facts for SapBERT"
    ],
    "multilingual_e5_targets": [
      "passage: PICO combined text with passage: prefix",
      "query: English questions"
    ]
  }},
```

#### Layer B の指示を削除

```python
# 削除する部分
**Layer B: Atomic Facts (English only)**
- Create 10-20 facts, each 1 sentence with 1 verifiable fact
- Include quantitative data and statistical significance
- Separate author claims from observed facts
```

```python
# 削除する部分
**Embeddings Metadata**
- List targets for SapBERT (medical concepts)
- List targets for multilingual-e5 (questions with query: prefix)
```

---

### Step 2: STAGE2_PROMPT を新規作成

`STAGE1_PROMPT` の直後に、以下の新しいプロンプトを追加する。

```python
STAGE2_PROMPT = """You are a medical research expert. Generate atomic facts and embeddings metadata for the following paper.

Paper Information:
Title: {title}
PMID: {pmid}
Abstract: {abstract}
Full Text: {full_text}

 The following questions have already been generated for this paper:
 
 English Questions:
 {questions_en}
 
 PICO (already extracted):
{pico_en}

YOUR TASK: Generate atomic_facts_en and embeddings_metadata.

CRITICAL RULES FOR atomic_facts_en:
1. Create 10-20 facts that collectively ANSWER the generated questions above
2. Each fact must be a SINGLE, SELF-CONTAINED sentence that is understandable WITHOUT any other context
3. NEVER use "The study", "The participants", "The trial", "The authors" as the sole subject
4. ALWAYS include in each fact: (1) the specific intervention name and dosage, (2) the condition/population, and (3) the PMID
5. Each fact must pass the "isolation test": reading ONLY that one sentence, the reader must know WHAT study, WHAT intervention, WHAT population, and WHAT was measured
6. After writing facts that answer the questions, add additional facts for important information NOT covered by any question (e.g., dropout rates, demographic details, safety data)
7. Include quantitative data (numbers, units, confidence intervals, p-values) wherever available

Examples:
- BAD:  "The mean age of participants was 56 years."
- GOOD: "In the semaglutide 2.4mg trial for obesity with knee osteoarthritis (PMID_39476339), the mean age of participants was 56 years."
- BAD:  "The reduction was statistically significant (p<0.001)."
- GOOD: "Body weight reduction with semaglutide 2.4mg vs placebo was statistically significant (p<0.001) in the 68-week RCT (PMID_39476339)."
- BAD:  "Gastrointestinal disorders were the most common reason for discontinuation."
- GOOD: "Gastrointestinal disorders were the most common reason for trial discontinuation in the semaglutide 2.4mg group in the obesity/knee osteoarthritis RCT (PMID_39476339)."

Return ONLY valid JSON in this exact format:
{{
  "atomic_facts_en": [
    "Self-contained fact 1 answering a generated question, with intervention name, condition, PMID, and quantitative data",
    "Self-contained fact 2...",
    ...
  ],
  "embeddings_metadata": {{
    "sapbert_targets": [
      "PICO combined text for SapBERT embedding (copy from PICO data above)",
      "Each atomic fact listed individually for SapBERT embedding"
    ],
    "multilingual_e5_targets": [
      "passage: PICO combined text with passage: prefix",
      "query: Each English question with query: prefix"
    ]
  }}
}}

Return ONLY the JSON object, no markdown or explanation."""
```

---

### Step 3: structure_paper 関数を2段階処理に修正

現在の `structure_paper` 関数（277行目〜）を以下の構造に修正する。

```python
def structure_paper(paper_data, max_retries=3):
    """Structure a single paper using LLM in 2 stages"""
    
    # === 前処理（既存のまま） ===
    abstract_text = paper_data.get('abstract', '')
    full_text = paper_data.get('full_text', '')
    sample_size = extract_sample_size(abstract_text)

    if full_text and len(full_text) > 5000:
        print(f"  ! Full text is {len(full_text)} chars, compressing...")
        full_text = compress_full_text_with_llm(full_text, max_length=5000)

    # source_instruction の準備（既存のまま）
    if full_text and full_text.strip():
        source_instruction = "Use the FULL TEXT for comprehensive PICO extraction, detailed atomic facts, and accurate quantitative data extraction."
    else:
        source_instruction = "Full text is NOT AVAILABLE. Use the ABSTRACT ONLY. Note that limited information may affect accuracy and completeness."

    # authors_str の準備（既存のまま）
    authors_list = paper_data.get('authors', [])
    # ... (既存の著者名変換ロジックをそのまま維持) ...

    # =============================================
    # Stage 1: PICO, Questions, Limitations 等の生成
    # =============================================
    print(f"  Stage 1: Generating PICO, questions, limitations...")
    
    stage1_prompt = STAGE1_PROMPT.format(
        title=paper_data.get('title', ''),
        authors=authors_str,
        journal=paper_data.get('journal', ''),
        year=paper_data.get('year', 0),
        doi=paper_data.get('doi', ''),
        pmid=paper_data.get('pmid', ''),
        abstract=paper_data.get('abstract', ''),
        full_text=full_text,
        source_instruction=source_instruction,
        publication_types=', '.join(paper_data.get('publication_types', [])),
        mesh_terms=', '.join(paper_data.get('mesh_terms', [])),
        sample_size_from_text=sample_size
    )

    stage1_result = None
    for attempt in range(max_retries):
        try:
            print(f"    Stage 1 attempt {attempt + 1}/{max_retries}...")
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a medical research expert. Return only valid JSON."},
                    {"role": "user", "content": stage1_prompt}
                ],
                temperature=0.1,
                max_tokens=16384
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from LLM")
            
            # JSON抽出（既存のクリーニングロジックをそのまま適用）
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            elif content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', content)
            if '<system-reminder>' in content:
                content = re.sub(r'<system-reminder>.*?</system-reminder>', '', content, flags=re.DOTALL)
                content = content.strip()
            
            stage1_result = json.loads(content)
            print(f"    ✓ Stage 1 complete")
            break
        except json.JSONDecodeError as e:
            print(f"    ✗ Stage 1 JSON error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            print(f"    ✗ Stage 1 error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    if not stage1_result:
        print(f"  ✗ Stage 1 failed after {max_retries} attempts")
        return None

    # =============================================
    # Stage 2: Atomic Facts + Embeddings Metadata 生成
    # =============================================
    print(f"  Stage 2: Generating atomic facts based on generated questions...")

    # Stage 1 の結果から質問とPICOを取得
    questions_en = stage1_result.get('multilingual_interface', {}).get('generated_questions', {}).get('en', [])
    pico_en = stage1_result.get('language_independent_core', {}).get('pico_en', {})

    stage2_prompt = STAGE2_PROMPT.format(
        title=paper_data.get('title', ''),
        pmid=paper_data.get('pmid', ''),
        abstract=paper_data.get('abstract', ''),
        full_text=full_text,
        questions_en='\n'.join(f"  - {q}" for q in questions_en),
        pico_en=json.dumps(pico_en, indent=2, ensure_ascii=False)
    )

    stage2_result = None
    for attempt in range(max_retries):
        try:
            print(f"    Stage 2 attempt {attempt + 1}/{max_retries}...")
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a medical research expert. Return only valid JSON. IMPORTANT: Every atomic_facts_en entry must be a fully self-contained sentence that includes the intervention name, condition, and PMID. Never use 'The study' or 'The participants' without specifying which study."},
                    {"role": "user", "content": stage2_prompt}
                ],
                temperature=0.1,
                max_tokens=8192
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from LLM")
            
            # JSON抽出（同じクリーニングロジック）
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            elif content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', content)
            if '<system-reminder>' in content:
                content = re.sub(r'<system-reminder>.*?</system-reminder>', '', content, flags=re.DOTALL)
                content = content.strip()
            
            stage2_result = json.loads(content)
            print(f"    ✓ Stage 2 complete")
            break
        except json.JSONDecodeError as e:
            print(f"    ✗ Stage 2 JSON error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            print(f"    ✗ Stage 2 error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    if not stage2_result:
        print(f"  ✗ Stage 2 failed after {max_retries} attempts")
        return None

    # =============================================
    # Stage 1 + Stage 2 の結果をマージ
    # =============================================
    print(f"  Merging Stage 1 + Stage 2 results...")

    # atomic_facts_en を language_independent_core に追加
    if 'language_independent_core' not in stage1_result:
        stage1_result['language_independent_core'] = {}
    stage1_result['language_independent_core']['atomic_facts_en'] = stage2_result.get('atomic_facts_en', [])

    # embeddings_metadata を追加
    stage1_result['embeddings_metadata'] = stage2_result.get('embeddings_metadata', {})

    print(f"  ✓ Successfully structured (2-stage)")
    return stage1_result
```

---

### Step 4: JSONクリーニングロジックを共通関数に抽出（リファクタリング）

Stage 1 と Stage 2 で同じJSONクリーニングコードが重複するため、共通関数にする。

```python
def clean_llm_json_response(content):
    """LLMレスポンスからJSONを抽出・クリーニング"""
    if content is None:
        raise ValueError("Empty response from LLM")
    
    content = content.strip()
    
    # Remove markdown code blocks
    if content.startswith('```json'):
        content = content[7:]
    elif content.startswith('```'):
        content = content[3:]
    if content.endswith('```'):
        content = content[:-3]
    content = content.strip()

    # Remove control characters
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', content)

    # Remove system-reminder injection
    if '<system-reminder>' in content or '</system-reminder>' in content:
        print(f"  ! Warning: system-reminder tags detected in response")
        content = re.sub(r'<system-reminder>.*?</system-reminder>', '', content, flags=re.DOTALL)
        content = content.strip()

    return json.loads(content)
```

Stage 1, Stage 2 の両方でこの関数を使用する:

```python
# Before (各Stageで重複していたコード)
content = response.choices[0].message.content
content = content.strip()
if content.startswith('```json'):
    ...
stage1_result = json.loads(content)

# After
content = response.choices[0].message.content
stage1_result = clean_llm_json_response(content)
```

---

## 修正しないファイル

- `batch_structure_papers.py` — 変更不要。`structure_paper()` の戻り値の構造は同じ

---

## APIコストへの影響

- リクエスト数: 1論文あたり 1回 → 2回（2倍）
- ただし Stage 1 は atomic_facts 分のトークンが減り、Stage 2 は軽量なので、合計トークン数の増加は約30-50%程度
- `time.sleep(1)` の rate limiting は `batch_structure_papers.py` 側で既に対応済み

---

## 検証方法

### 1. 単体テスト

```bash
python3 scripts/structure_paper.py pharmacologic glp1_receptor_agonists <任意のPMID>
```

確認項目:
- Stage 1, Stage 2 のログが順に表示されること
- 出力JSONに `atomic_facts_en` と `embeddings_metadata` が含まれること
- `atomic_facts_en` の各文が自己完結的であること（介入名、疾患名、PMID を含む）
- `atomic_facts_en` が `generated_questions` の内容をカバーしていること

### 2. 品質チェック

出力された `atomic_facts_en` に対して以下を確認:

```
✅ チェックリスト:
[ ] 各文に介入名と用量が含まれている（例: "semaglutide 2.4mg"）
[ ] 各文に対象疾患/集団が含まれている（例: "obesity with knee osteoarthritis"）
[ ] 各文にPMIDが含まれている（例: "(PMID_39476339)"）
[ ] "The study" 等の曖昧な主語で始まる文がない
[ ] generated_questions (en) の主要な質問に対応するfactが存在する
[ ] 質問でカバーされない重要情報（脱落率、人口統計等）もfactに含まれている
[ ] 定量データ（数値、単位、CI、p値）が含まれている
```

### 3. バッチ再処理

検証OKなら全論文を再処理:

```bash
python3 scripts/batch_structure_papers.py --all-domains --force
```
