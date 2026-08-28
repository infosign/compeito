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
| B4 | **Web UI キーワード検索** — ツリービューに検索ボックス（ILIKE 部分一致、HTMX＋no-JS フォールバック）。B2（意味検索）の前段で、実装後は UI を B2 と共有 | 設計済み（実装順未定） | [designs/web-ui-keyword-search.md](./designs/web-ui-keyword-search.md) |
| B5 | **フレームワーク改訂プロトコル運用ガイド** — 新版複製（全 UUID 新規採番）＋ `replacedBy`/`exactMatchOf` ＋ 旧版 Deprecated 化の手順書（docs/guide/framework-revision.md、実装なし）。発行済み OB v3 バッジを壊さない年度改訂サイクルを支援 | 設計済み（実装順未定） | [designs/framework-revision-guide.md](./designs/framework-revision-guide.md) |
| B6 | **インポート dry-run/確認ガード ＋ AI 変換ガイド** — import 系 CLI に `--dry-run`・破壊的変更の確認プロンプト・構造化 validation report（strict 出力 C3 対応(a)を兼ねる）。AI による Excel→CASE 変換の利用ガイド（docs/guide/ai-conversion.md）も含む | 設計済み（実装順未定） | [designs/import-dry-run-and-ai-guide.md](./designs/import-dry-run-and-ai-guide.md) |
| B7 | **新版複製 CLI `doc duplicate`** — new UUIDs 採番＋ `replacedBy` 自動生成。B5 ガイドの手作業レシピの自動化 | 未着手 | — |
| B8 | **廃止項目（墓標）の扱い** — 元データから消えた項目を `statusEndDate` ＋ `replacedBy` の墓標として受け入れ、配信では全件返しつつ UI/検索で既定除外する。to-case（学習指導要領コード表の変換）との合意事項（[infosign/to-case#9](https://github.com/infosign/to-case/issues/9)）。内訳は下記 | 実装中 | — |

## 参考: 別ファイルで管理する将来要望（要件未確定）

- **Moodle 内でコンピテンシーとコースをバッチで結びつける仕組み** — B1（Moodle エクスポート）の先にある発展要望。実行場所（Moodle プラグイン/スクリプト/compeito 側）・入力形式・粒度とも未定。着手前に要件を詰める。

## B8 の内訳（廃止項目の扱い）

to-case との合意（[infosign/to-case#9](https://github.com/infosign/to-case/issues/9)）にもとづく compeito 側の作業。
合意の要点は、削除も prune もせず、廃止を `statusEndDate` と `replacedBy` の**状態**として表現すること。
外部から参照されている項目（発行済み OB v3 バッジの alignment 先）を壊さないための選択である。

初回公開までに入れるもの:

| # | 項目 | 状態 |
|---|------|:--:|
| B8-1 | `statusStartDate` / `statusEndDate` のクリア判定の修正。CASE JSON の明示的な `null` で既存値をクリアできるようにする（従来は不正な日付文字列でのみ消え、`null` は無視されていた） | 実装中 |
| B8-2 | xlsx エクスポートの CFItem 行に `statusStartDate` / `statusEndDate` 列を追加。現状 CFDocument 側にしか列が無く、xlsx 往復で墓標が「生きた項目」に戻る | 未着手 |
| B8-3 | CFItem の廃止表示。詳細ページの廃止バナー（`statusEndDate` を明示）と `replacedBy` の後継リンク（1 ホップ）、ツリー上の区別 | 未着手 |
| B8-4 | ツリーの非表示規則。サブツリー全体が廃止のときのみ既定非表示とし、生きた子孫がいる場合は区別表示で残す（単純フィルタでは生きた子孫まで消える） | 未着手 |

改版の取り込みまでに間に合えばよいもの:

| # | 項目 | 状態 |
|---|------|:--:|
| B8-5 | キーワード検索（B4）・意味検索（B2）の設計に、廃止項目の既定除外と `includeRetired` 相当の切り替えを追記 | 未着手 |
| B8-6 | 改訂プロトコル運用ガイド（B5）に、日付定義の書き分け（CFItem = 廃止が確定した版の公表日／CFDocument = 有効期間の最終日）と墓標の保持方針を追記 | 未着手 |

関連する設計上の不変条件（to-case と共有）: **任意の一版のパッケージを単独で取り込んだだけで正しい状態になること**。
テナントが全ての版を順に取り込むとは限らないため、墓標も墓標の取り消しも `replacedBy` の連鎖も、毎版すべて出力される前提で扱う。
