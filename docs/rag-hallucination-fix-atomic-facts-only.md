# RAG ハルシネーション対策：数値抽出をAtomic Factsに限定する

## 背景と問題

「GLP-1受容体作動薬は変形性膝関節症の症状緩和に有効ですか？」という質問に対し、
RAGパイプラインが膝OAとは無関係な **ASCVD（心血管イベント）データ（HR 0.80、CV event 20%減少）**
を回答に含めてしまう現象が確認された。

## 根本原因

### 検索は正しかった

PMID_40789597（CMAJ 2025肥満ガイドライン）は膝OAについても言及しており、
検索ステージで正当に取得されていた。問題は検索精度ではなく、その後の **数値抽出ステップ** にあった。

### なぜ誤った数値が混入したか

`analyze_single_paper()` はペーパーのコンテキストとして `pico_en.outcome` フィールドを渡す。
このフィールドはそのガイドラインが扱う **すべての疾患のアウトカム** をまとめて記述しており、
ASCVDの数値（`HR 0.80, 95% CI 0.72–0.90`）も含まれていた。

プロンプトが「Outcome または Facts から数値を抽出せよ」と指示していたため、
LLMはクエリと無関係なASCVD数値も忠実に抽出し、回答に混入させた。

```
# 修正前のプロンプト指示（問題箇所）
- Result: [Specific numbers from Outcome or Facts]
```

一方、**Atomic Facts** はベクトル検索でクエリに対してセマンティックにマッチしたものだけが
返されるため、膝OAクエリに対してはWOMACスコアや体重減少など膝OA試験の数値のみが含まれる。

### 対比まとめ

| フィールド | フィルタリング | 膝OAクエリでの内容 |
|---|---|---|
| `pico_en.outcome` | なし（論文全体を記述） | ASCVD、膝OA、その他すべてのアウトカム |
| Atomic Facts | セマンティック検索で絞り込み済み | 膝OA関連の数値のみ |

## 修正内容

### Fix 1 — `analyze_single_paper()` のプロンプト

数値の抽出元を **Atomic Facts のみ** に限定。`Outcome (Summary)` は関連性の判断にのみ使用し、
数値ソースとしては禁止した。また Key Facts が空または質問と無関係な場合は
`IRRELEVANT` を出力するよう明示した。

```python
# 修正後
IMPORTANT: Extract numbers ONLY from the "Key Facts from Text" section.
Use "Outcome (Summary)" to judge relevance only — never as a source of specific numbers.
If "Key Facts from Text" is empty, or its facts do not answer the question, output "IRRELEVANT".

Output Format:
- Drug Name: [Name]
- Result: [Numbers from Key Facts only]
```

### Fix 2 — `synthesize_findings()` のプロンプト

Reduceフェーズでも、抽出された Findings に含まれない情報を LLM が自前の知識で補わないよう
グラウンディング指示を追加した。

```python
# 修正後
2. List ONLY the specific evidence (Drug names and Numbers) that appear in the Extracted Findings above.
3. Do NOT add information from your own knowledge. If a finding does not address the user's question, omit it.
```

## 修正のポイント

この修正が効果的な理由は、**情報の信頼性の非対称性** を活用している点にある。

- `pico_en.outcome` はインデクシング時に生成された「論文全体の要約」であり、クエリを知らない。
- Atomic Facts はクエリに対してベクトル類似度でフィルタされた「クエリ関連の証拠」である。

Map フェーズでの数値抽出源を後者に限定することで、検索精度を下げることなくハルシネーションを防ぐ。
`Outcome (Summary)` は「この論文がそもそも関係しているか」の判断材料として引き続き活用する。

## 検証コマンド

```bash
# テスト1: 膝OAクエリ — ASCVD・HR・心血管イベントが含まれないこと
python3 scripts/medgemma_query.py "GLP1受容体作動薬は、変形性膝関節症の症状緩和に有効ですか？" --mode rag

# テスト2: 回帰テスト — 肥満/体重減少クエリで正しい数値が出ること
python3 scripts/medgemma_query.py "GLP1受容体作動薬は肥満の体重減少に有効ですか？" --mode rag
```

**期待結果（テスト1）:** WOMACスコアや膝OA試験の体重減少数値を含む Yes/No 回答。
ASCVD、HR、心血管イベントへの言及なし。

## 修正ファイル

- `scripts/medgemma_query.py` — `analyze_single_paper()` と `synthesize_findings()` のプロンプトのみ変更
