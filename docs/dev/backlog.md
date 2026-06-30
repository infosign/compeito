# Feature backlog

未着手・未完了の**機能/相互運用**項目のバックログ。各項目は設計が固まったら `docs/dev/designs/<slug>.md` に個別の設計ドキュメントを持つ（設計未着手の項目はリンク無し）。

関連する別管理のバックログ:
- **CASE v1.1 厳密適合**のギャップ（wrapper、パッケージ内 URI、Link ヘッダー等）は [case-v1p1-conformance-backlog.md](./case-v1p1-conformance-backlog.md) で管理。
- 完了済みの項目は [requirements/phases.md](../requirements/phases.md)（ロードマップ）に履歴として残る。

> ステータス凡例 — **設計済み**: レビュー済みで実装着手可 / **設計中**: 設計検討中 / **未着手**: アイデアのみ。

| # | 項目 | ステータス | 設計 |
|---|------|:--:|------|
| B1 | **Moodle コンピテンシー CSV エクスポート**（`export csv --profile moodle`） — CFDocument を Moodle の `tool_lpimportcsv`（サイト管理 > コンピテンシー > コンピテンシーフレームワークのインポート）が取り込める CSV として出力する一方通行・lossy なエクスポート | 設計済み（実装順未定） | [designs/moodle-competency-export.md](./designs/moodle-competency-export.md) |
| B2 | **コンピテンシーの意味検索**（ベクトル埋め込み） — ローカル埋め込みモデル同梱（オフライン）＋ pgvector ＋検索 API。CFItem を意味の近さで検索 | 設計済み（実装順未定） | [designs/semantic-search.md](./designs/semantic-search.md) |
| B3 | **フレームワーク間自動マッピング提案** | 未着手 | — |

## 参考: 別ファイルで管理する将来要望（要件未確定）

- **Moodle 内でコンピテンシーとコースをバッチで結びつける仕組み** — B1（Moodle エクスポート）の先にある発展要望。実行場所（Moodle プラグイン/スクリプト/compeito 側）・入力形式・粒度とも未定。着手前に要件を詰める。
