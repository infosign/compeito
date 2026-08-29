# Feature backlog

未着手・未完了の**機能/相互運用**項目のバックログ。各項目は設計が固まったら `docs/dev/designs/<slug>.md` に個別の設計ドキュメントを持つ（設計未着手の項目はリンク無し）。

関連する別管理のバックログ:
- **CASE v1.1 厳密適合**のギャップ（wrapper、パッケージ内 URI、Link ヘッダー等）は [case-v1p1-conformance-backlog.md](./case-v1p1-conformance-backlog.md) で管理。
- 完了済みの項目は [requirements/phases.md](../requirements/phases.md)（ロードマップ）に履歴として残る。

> ステータス凡例 — **完了**: main にマージ済み / **実装中**: ブランチで作業中 / **設計済み**: レビュー済みで実装着手可 / **設計中**: 設計検討中 / **未着手**: アイデアのみ。

| # | 項目 | ステータス | 設計 |
|---|------|:--:|------|
| B1 | **Moodle コンピテンシー CSV エクスポート**（`export csv --profile moodle`） — CFDocument を Moodle の `tool_lpimportcsv`（サイト管理 > コンピテンシー > コンピテンシーフレームワークのインポート）が取り込める CSV として出力する一方通行・lossy なエクスポート | 設計済み（実装順未定） | [designs/moodle-competency-export.md](./designs/moodle-competency-export.md) |
| B2 | **コンピテンシーの意味検索**（ベクトル埋め込み） — ローカル埋め込みモデル同梱（オフライン）＋ pgvector ＋検索 API。CFItem を意味の近さで検索 | 設計済み（実装順未定） | [designs/semantic-search.md](./designs/semantic-search.md) |
| B3 | **フレームワーク間自動マッピング提案** | 未着手 | — |
| B4 | **Web UI キーワード検索** — ツリービューに検索ボックス（ILIKE 部分一致、HTMX＋no-JS フォールバック）。B2（意味検索）の前段で、実装後は UI を B2 と共有 | 設計済み（実装順未定） | [designs/web-ui-keyword-search.md](./designs/web-ui-keyword-search.md) |
| B5 | **フレームワーク改訂プロトコル運用ガイド** — 新版複製（全 UUID 新規採番）＋ `replacedBy`/`exactMatchOf` ＋ 旧版 Deprecated 化の手順書（docs/guide/framework-revision.md、実装なし）。発行済み OB v3 バッジを壊さない年度改訂サイクルを支援 | 設計済み（実装順未定） | [designs/framework-revision-guide.md](./designs/framework-revision-guide.md) |
| B6 | **インポート dry-run/確認ガード ＋ AI 変換ガイド** — import 系 CLI に `--dry-run`・破壊的変更の確認プロンプト・構造化 validation report（strict 出力 C3 対応(a)を兼ねる）。AI による Excel→CASE 変換の利用ガイド（docs/guide/ai-conversion.md）も含む | 設計済み（実装順未定） | [designs/import-dry-run-and-ai-guide.md](./designs/import-dry-run-and-ai-guide.md) |
| B7 | **新版複製 CLI `doc duplicate`** — new UUIDs 採番＋ `replacedBy` 自動生成。B5 ガイドの手作業レシピの自動化 | 未着手 | — |
| B8 | **廃止項目（墓標）の受け入れ** — 元ソースから消えた CFItem を、削除せず `statusEndDate` ＋ `replacedBy` の**状態**として受け入れる。配信では全件返し、UI と検索で既定除外する。発行済み OB v3 バッジの alignment 先を壊さないための方針。内訳は下記 | 実装中（初回公開に必要な4項目は完了） | — |
| B9 | **自ホスト URI のテナント不一致を警告** — インポート時、保存しようとしている `uri` が自分の `BASE_URL` を指しているのに、テナントセグメントが取り込み先テナントの UUID と一致しない場合に警告する。現状は無検査。slug 入りや別テナントの URI が入ると、slug のリネームやテナント移動で保存済み URI が解決しなくなる（インポートは `uri` を verbatim 保存する仕様のため、後から直らない） | 完了 | — |

## B8 の内訳（廃止項目の受け入れ）

CASE には項目の廃止を表す削除操作が無く、compeito のインポートも additive only である。
元ソースから消えた項目を削除せず、`statusEndDate`（廃止の日付）と `replacedBy`（後継への関連）で**状態**として表す。
外部から参照されている項目（発行済み OB v3 バッジの alignment 先）を壊さないための選択であり、prune モードや削除 API は設けない。

前提とする不変条件: **任意の一版のパッケージを単独で取り込んだだけで正しい状態になること**。
テナントが全ての版を順に取り込むとは限らないので、墓標も後継関連も、毎版すべて含まれる前提で扱う。
ただしこの不変条件はリソースのフィールド値に限る。association は additive only のため、一度張られた `replacedBy` はパッケージ側から取り消せない（B8-7）。

初回公開に必要なものは B8-1〜B8-4 で、すべて完了している。

優先度の高いもの:

| # | 項目 | 状態 |
|---|------|:--:|
| B8-1 | `statusStartDate` / `statusEndDate` のクリア手段。既定では null / 欠落とも既存値を保持し、`import case --allow-status-clear` のときだけクリアする（OpenCASE や compeito 自身のエクスポートは null を出力するため、既定でクリアすると再インポートで墓標が消える） | 完了 |
| B8-2 | xlsx の CFItem シートに `statusStartDate` / `statusEndDate` 列（compeito 拡張、ヘッダ名で探索）を追加。列が無いと xlsx 往復で墓標が「生きた項目」に戻る | 完了 |
| B8-3 | CFItem の廃止表示。詳細ページの廃止バナー（`statusEndDate` を明示）と `replacedBy` の後継リンク（1 ホップ）、ツリー上の区別 | 完了 → [designs/retired-item-ui.md](./designs/retired-item-ui.md) |
| B8-4 | ツリーの非表示規則。サブツリー全体が廃止のときのみ既定非表示とし、生きた子孫がいる場合は区別表示で残す（単純フィルタでは生きた子孫まで消える） | 完了 → [designs/retired-item-ui.md](./designs/retired-item-ui.md) |

後続:

| # | 項目 | 状態 |
|---|------|:--:|
| B8-5 | キーワード検索（B4）・意味検索（B2）の設計に、廃止項目の既定除外と `includeRetired` 相当の切り替えを追記 | 未着手 |
| B8-6 | 改訂プロトコル運用ガイド（B5）に、日付の意味の書き分け（CFItem = 廃止が確定した日／CFDocument = 有効期間の最終日）と墓標の保持方針を追記 | 完了（B5 の設計に畳み込み。ガイド本体は B5 の実装時に書かれる） |
| B8-7 | 誤って張られた `replacedBy` の取り消し手段。association は additive only なので、パッケージの再インポートでは消せない | 未着手 |

B6（インポート dry-run / validation report）へ引き継ぐ3点:

- ライフサイクル日付の保持・クリアの件数はレポートで集約している（リソースごとに1行ではない）。B6 で識別子のサンプルを出す場合は、そこで想定しているサンプル上限に合流させる。
- 公式スキーマに `nullable` は無く、`"statusEndDate": null` は厳密には型違反である。ただし `--allow-status-clear` と組み合わせたときは意味を持つ入力なので、単なる型違反として潰さない。
- 日付フィールドに数値（例: `20210401`）が入ったパッケージは、`_parse_date` の `strptime` が `TypeError` を投げてインポート全体が中断する。B8-1 以前からの挙動で今回の範囲外だが、「インポートは寛容に」という方針とは合わない。なお `0` は falsy のため例外にならず、非ゼロの数値と挙動が分かれる。

外部の変換ツールとの取り決めの経緯は [infosign/to-case#9](https://github.com/infosign/to-case/issues/9)。

## B9 の補足（自ホスト URI のテナント不一致）

compeito の CASE インポートは、外部ソースの `uri` をそのまま保存する（FR-7.2。外部クライアントが保存済みの URI を壊さないため）。
この挙動は正しいが、投入時に誤った URI が入っても検知できない。

想定する事故は、テナントセグメントに UUID ではなく slug を入れた URI を投入する経路である。
compeito は slug を「UI 上の別名」と位置づけ、CASE API のレスポンスには UUID しか出さず、slug の変更で保存済み URI を書き換えない（[web-ui.md](../spec/web-ui.md)）。
そのため slug 入りの URI が保存されると、slug をリネームした時点で解決しなくなり、compeito 側では回復できない。

**警告に留める理由**: 外部の CASE サーバーから取り込んだパッケージが他ホストの URI を持つのは正常であり、拒否はできない。
検査対象は「`uri` が自分の `BASE_URL` を指しているのに、テナントセグメントが取り込み先テナントの UUID と一致しない」場合に限る。

**優先度**: 高くない。個々の投入ツール側で `--base` を検証する対処が実際に行われており（[infosign/to-case#17](https://github.com/infosign/to-case/pull/17)）、現実的に踏む経路は減っている。
ただし投入側の検証はその投入側にしか効かないので、手書き JSON や他のエディタからの取り込みには compeito 側の検査が要る。
B6（インポート dry-run / validation report）の検査項目として実装するのが自然。

## 参考: 別ファイルで管理する将来要望（要件未確定）

- **Moodle 内でコンピテンシーとコースをバッチで結びつける仕組み** — B1（Moodle エクスポート）の先にある発展要望。実行場所（Moodle プラグイン/スクリプト/compeito 側）・入力形式・粒度とも未定。着手前に要件を詰める。
