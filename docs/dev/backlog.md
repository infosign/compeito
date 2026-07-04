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
| B4 | **Web UI キーワード検索** — ツリービューに検索ボックス（ILIKE 部分一致、HTMX＋no-JS フォールバック）。B2（意味検索）の前段で、実装後は UI を B2 と共有 | 設計中（レビュー中） | [designs/web-ui-keyword-search.md](./designs/web-ui-keyword-search.md) |
| B5 | **フレームワーク改訂プロトコル運用ガイド** — 新版複製（全 UUID 新規採番）＋ `replacedBy`/`exactMatchOf` ＋ 旧版 Deprecated 化の手順書（docs/guide/framework-revision.md、実装なし）。発行済み OB v3 バッジを壊さない年度改訂サイクルを支援 | 設計中（レビュー中） | [designs/framework-revision-guide.md](./designs/framework-revision-guide.md) |
| B6 | **インポート dry-run/確認ガード ＋ AI 変換ガイド** — import 系 CLI に `--dry-run`・破壊的変更の確認プロンプト・構造化 validation report（strict 出力 C3 対応(a)を兼ねる）。AI による Excel→CASE 変換の利用ガイド（docs/guide/ai-conversion.md）も含む | 設計中（レビュー中） | [designs/import-dry-run-and-ai-guide.md](./designs/import-dry-run-and-ai-guide.md) |
| B7 | **新版複製 CLI `doc duplicate`** — new UUIDs 採番＋ `replacedBy` 自動生成。B5 ガイドの手作業レシピの自動化 | 未着手 | — |

## 参考: 別ファイルで管理する将来要望（要件未確定）

- **Moodle 内でコンピテンシーとコースをバッチで結びつける仕組み** — B1（Moodle エクスポート）の先にある発展要望。実行場所（Moodle プラグイン/スクリプト/compeito 側）・入力形式・粒度とも未定。着手前に要件を詰める。
