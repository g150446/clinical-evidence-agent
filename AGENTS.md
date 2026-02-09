# AGENTS.md - 開発ガイドライン

## プロジェクト概要

MedGemma 4Bを用いた医療エビデンス検索システムの構築プロジェクトです。

## 重要: JSONデータ作成時の注意事項

**必ず読む:** [JSON Parse Error 対処ガイド](./JSON_ERROR_HANDLING.md)

JSONファイルを作成する際は、上記ガイドに従って以下の点に注意してください:

1. **Pythonのjsonモジュールを使用する** - 手動でJSON文字列を作成しない
2. **ensure_ascii=Falseを指定** - 日本語を正しく保存
3. **書き込み後は必ず検証** - 読み込みテストを実施
4. **ヒアドキュメントを避ける** - 別ファイルのPythonスクリプトとして実行
5. **一時ファイル方式を使用** - 安全な書き込みパターンを採用

## データ収集ワークフロー

### フェーズ1: 論文検索
- PubMed検索クエリの実行
- PMIDリストの取得
- 重複チェック

### フェーズ2: データ構造化（5レイヤー）
1. **PICO構造化** - 手動抽出
2. **アトミック・ファクト** - 高精度モデル使用
3. **想定質問生成** - 日本語・英語両方
4. **矛盾・限界の明示化** - 研究限界を記録
5. **クロスリファレンス** - 論文間関係性

### フェーズ3: JSON生成
- 構造化データのJSON変換
- スキーマ検証
- ファイル保存

### フェーズ4: 品質検証
- ランダムサンプリング検証
- PICO完全性確認
- データ品質チェック

## ディレクトリ構造

```
data/obesity/
├── pharmacologic/     # 薬物療法
│   ├── glp1_receptor_agonists/
│   │   ├── papers.json      # 簡単形式（pmid, title, abstract, journal, year）
│   │   └── papers/           # 5レイヤー構造化JSON（PMID_XXX.json）
│   ├── guidelines_and_reviews/
│   └── novel_agents/
├── surgical/          # 外科的治療
│   ├── procedures_and_outcomes/
│   ├── metabolic_effects/
│   └── complications_safety/
└── lifestyle/         # ライフスタイル介入
    ├── dietary_interventions/
    ├── physical_activity/
    └── behavioral_therapy/
```

**ファイル形式:**
- `papers.json`: ダウンロードした論文の簡易データ
- `papers/PMID_XXX.json`: 5レイヤー構造化されたデータ（PICO、アトミック・ファクト、質問、限界など）
```
data/
├── obesity/
│   ├── pharmacologic/     # 薬物療法
│   ├── surgical/          # 外科的治療
│   └── lifestyle/         # ライフスタイル介入
└── search_results.json    # 検索結果

scripts/
├── search_pubmed.py       # PubMed検索
├── check_duplicates.py    # 重複チェック
├── fetch_paper_details.py # 論文詳細取得
└── ...
```

## コーディング規約

- すべてのJSONファイルはUTF-8エンコーディング
- PythonスクリプトはPEP8準拠
- ファイル書き込みは検証付きで実施
- エラーハンドリングを適切に実装

## 関連ドキュメント

- [prepare.md](./prepare.md) - システム設計仕様
- [plan_obesity.md](./plan_obesity.md) - 肥満治療データ収集プラン
- [JSON_ERROR_HANDLING.md](./JSON_ERROR_HANDLING.md) - JSONエラー対処ガイド
