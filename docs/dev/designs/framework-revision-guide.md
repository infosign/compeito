# フレームワーク改訂プロトコル 運用ガイド 執筆仕様

> **ステータス: 設計レビュー済み（実装着手可・実装順未定）**
> Codex レビュー 1 ラウンド（技術的前提の実コード検証・仕様間整合・方針整合）＋指摘反映済み（2026-07）。
> 2026-08: バックログ B8-6（日付の意味の書き分け・墓標の保持方針）を本設計に畳み込んだ。ガイド執筆時に §6 の該当箇所を書くこと。
> 成果物は**コードではなく運用ガイド文書** `docs/guide/framework-revision.md`（EN/JP 併記）。
> 本仕様書は「そのガイドに何をどう書くか」の設計であり、実装変更は一切伴わない（実装ゼロ・ドキュメントのみ）。
> 執筆担当はこの仕様書だけを頼りにガイドを書き上げられることを目標とする。

## 背景（なぜこのガイドが必要か）

2026-07 の外部レビュー（ID = インストラクショナルデザイン視点）で**重大度・高**の指摘:

- compeito の更新手段は **UUID 一致の in-place upsert のみ**。「2025年度版を凍結し、2026年度版を新たに起こす。発行済み OB v3 バッジは旧版項目を参照し続ける」という教育設計の基本サイクル（年度改訂）への支援が無い。
- in-place 更新で `fullStatement` の**意味が変わる**編集をすると、その UUID を `alignment` として参照している**発行済み OB v3 バッジの意味が黙って変わる**（バッジ保持者・検証者には何の通知もない）。
- CASE v1.1 標準自体にはバージョン管理機構が無い。しかし既存要素 — `replacedBy` / `exactMatchOf` 関連、`adoptionStatus`、`statusStartDate` / `statusEndDate` — の組み合わせで「**改訂プロトコル**」を**運用手順として**文書化できる。compeito は必要な要素をすべて実装済みなので、**実装ゼロで書けるのに効果が大きい**。

## 成果物と配置

| 項目 | 内容 |
|---|---|
| 新規ファイル | `docs/guide/framework-revision.md` |
| 様式 | 既存 guide（[opencase-interop.md](../../guide/opencase-interop.md)）に従う: **英語版全文 → `---` 区切り → 日本語版全文**。EN が先。両言語とも同一構成・同一コード例 |
| トーン | opencase-interop.md と同じ「実践ガイド」調。コマンドは実行例＋期待出力を併記 |
| CLAUDE.md | 仕様ドキュメント表の guide 節に 1 行追加（例: `docs/guide/framework-revision.md | フレームワーク改訂プロトコル運用ガイド（年度改訂・凍結と新版・replacedBy 対応付け）`） |
| backlog.md | 将来の `duplicate` CLI コマンド（後述「非対象」）を **未着手** 行として [backlog.md](../backlog.md) の表に追加（例: B7。「新版複製 CLI `doc duplicate` — new UUIDs + replacedBy 自動生成。framework-revision ガイドの手作業レシピの自動化」） |
| 相互リンク | opencase-interop.md の「See also / 関連ドキュメント」に本ガイドへのリンクを追加（任意・推奨） |

すべてブランチ → PR 経由（docs/dev/conventions.md 準拠。ドキュメントのみでも直接 push 禁止）。

## 決定事項（この設計で確定させる方針）

1. **判断基準を最初に置く**: in-place 更新でよいケース／新版を起こすべきケースの二分法をガイド冒頭で示す（読者が最初に知りたいのはここ）。
2. **新版は「全 UUID 差し替えの複製」**: 変わらない項目も含め **CFItem の UUID は全て新規採番**する。理由は後述の検証済み事実（同一テナント内で同じ item UUID を別ドキュメントに import すると**既存アイテムが旧ドキュメントから引き剥がされる**）。「変わらない項目は UUID を使い回す」案は**不可**と明記する。
3. **新旧対応付けは CASE の既存 association で表現**: 意味が変わった/置き換えられた項目は `replacedBy`（origin=旧項目 → destination=新項目）、意味が変わらない項目は `exactMatchOf` を**追加で**張る。対応付け association は**旧ドキュメント側に取り込む**（origin が旧項目なので、旧 doc の CSV エクスポートにも列として現れ、往復整合が取れる）。
4. **旧版の凍結は「意味の凍結」**: `fullStatement` 等の意味内容は以後変更しないが、ライフサイクルメタデータ（`adoptionStatus=Deprecated`、`statusEndDate`、replacedBy 関連の追加）の変更は凍結違反ではない、という区別をガイドで明確に述べる。
5. **UUID 差し替えは小スクリプトで行う**（手作業のエディタ置換は禁止事項として明記）。jq より **Python 数十行**の方が「識別子収集 → 対応表生成 → 全文テキスト置換」を安全に書けるので Python 例を主、jq は言及程度。
6. **バッジへの効果は「何も起きない」ことがゴール**だと明示する: 発行済みバッジは旧 UUID → 旧 permalink を参照し続け、URL も内容も不変。新版は新 UUID で並存する。

## ガイドの章立てと各章の要点

以下の章構成で書く。EN/JP とも同一構成。章番号はガイドでは見出しレベルで表現（番号は任意）。

### 1. Why revisions need a protocol / なぜ改訂に手順が要るか

- 導入: compeito は OB v3（Open Badge Factory）や QTI（TAO）の**参照先**として動く。バッジの `alignment` はコンピテンシー項目の URI（`{BASE_URL}/{tenant}/uri/{uuid}`）を指す。
- in-place upsert（`import case` / `import csv` の再実行）は **UUID が同じ行をその場で書き換える**。`fullStatement` の意味を変える編集をすると、発行済みバッジが証明する内容が**発行後に黙って変わる**。
- CASE 標準に版管理は無いが、`adoptionStatus` / `statusStartDate` / `statusEndDate`（CFDocument のライフサイクル欄）と `replacedBy` / `exactMatchOf`（association）で改訂サイクルを表現できる。本ガイドはその運用手順（プロトコル）を定める。
- 図（テキスト図で可）: 「2025年度版（Deprecated, 凍結）←replacedBy/exactMatchOf— は張られる向きに注意 —→ 2026年度版（Adopted）」と、旧版を指し続けるバッジのイメージ。

### 2. In-place update vs. new version / in-place 更新でよいか、新版を起こすべきか

判断基準の表を中心にする。**「発行済みバッジ・作成済みテスト・外部の参照者から見て、その項目が証明/測定する意味が変わるか？」が唯一の判断軸**であることを述べる。

| in-place 更新でよい（意味が変わらない） | 新版を起こすべき（意味・構造が変わる） |
|---|---|
| 誤字脱字・表記ゆれの修正 | `fullStatement` の内容的な書き換え（要求水準・範囲の変更） |
| 翻訳・多言語表記の追加 | 項目の追加・削除・分割・統合 |
| `notes` / `abbreviatedStatement` / `conceptKeywords` 等の補助情報の追記 | 階層構造（isChildOf ツリー）の組み替え |
| メタデータ整備（`humanCodingScheme` の付与、ライセンス設定等） | ルーブリック基準（criteria/levels）の実質的変更 |
| 表示順（`sequenceNumber`）の微調整 | 年度・カリキュラム改訂に伴う全面見直し |

- 補足: グレーゾーン（例: fullStatement の語順だけ変える）では「外部参照が 1 件でもあるなら新版に倒す」を推奨。
- in-place 更新のやり方自体は既存ドキュメント（opencase-interop.md の「Updating」、csv-format.md）参照でよい。本章では深追いしない。

### 3. The revision protocol (recipe) / 新版を起こす手順（レシピ）

ガイドの中核。**具体的なコマンド列**で書く。コマンドは cli.py の実体系（下記「検証済み事実」参照）を使う。全 Docker 構成なら各コマンドに `docker compose exec app` を前置（opencase-interop.md と同様に、例は `docker compose exec app uv run python cli.py ...` 形で統一してよい。ハイブリッド構成なら `uv run python cli.py ...`）。

**Step 0 — 前提確認**

```bash
uv run python cli.py tenant list
uv run python cli.py doc list --tenant {tenant_id}
```

対象ドキュメントの UUID を控える（以下 `{old_doc_id}`）。

**Step 1 — 旧版を CASE JSON でエクスポート**

```bash
uv run python cli.py export case --tenant {tenant_id} --doc {old_doc_id} --file framework-2025.json
# 36 アイテムを framework-2025.json にエクスポートしました
```

出力は `GET /ims/case/v1p1/CFPackages/{id}` と同形（トップレベル `CFDocument` / `CFItems` / `CFAssociations` / `CFDefinitions` / `CFRubrics`）。これが**新版の原本**かつ**バックアップ**になる。

**Step 2 — 全 UUID を差し替えて新版パッケージを作る（スクリプト）**

後述「UUID 差し替えスクリプトの仕様」のとおり。`framework-2025.json` → `framework-2026.json` と、旧→新 UUID の**対応表（mapping ファイル）**を生成する。対応表は Step 5 で使う。

**Step 3 — 新版パッケージを編集**

`framework-2026.json` に対して:

- `CFDocument.title` に版が分かる表記を入れる（例: 「〜 (2026年度版)」）。`version` を更新（例: `2.0` / `2026`）。
- `CFDocument.adoptionStatus` を `Adopted`（確定済みなら）または `Draft`（作業中なら）に。`statusStartDate` を新版の適用開始日に（例: `2026-04-01`）。`statusEndDate` は消す（null に）。
- 実際の改訂（fullStatement 書き換え・項目追加/削除・構造変更）を行う。JSON 直編集でもよいし、いったん import してから CSV export → 編集 → CSV import の通常フローでもよい。
- 注意: `lastChangeDateTime` は import 時に不正なら現在時刻へフォールバックするだけなので厳密でなくてよいが、更新しておくのが行儀。

**Step 4 — 新版を import（新ドキュメントとして作成される）**

```bash
uv run python cli.py import case --tenant {tenant_id} --file framework-2026.json
```

新しい `CFDocument.identifier` なので `--doc` は不要（新規作成になる）。出力の items/associations/rubrics カウントが元と揃うことを確認。

**Step 5 — 新旧対応付け（replacedBy / exactMatchOf）を旧ドキュメントに追加**

推奨経路は **CASE JSON**: `framework-2025.json` の `CFAssociations` 配列に対応付け association を**追記**し、旧ドキュメントへ再 import する。

- 各 association の形（1 対応につき 1 オブジェクト）:
  - `identifier`: 新規 UUID v4（必須。UUID 形式でないと skip される）
  - `associationType`: 意味が変わった/置換された項目 → `replacedBy`。意味が変わらない項目 → `replacedBy` に**加えて** `exactMatchOf` も張る（forward pointer は全項目に付き、同一性は exactMatchOf が示す）
  - `originNodeURI`: `{"title": "...", "identifier": "{旧item UUID}", "uri": "{BASE_URL}/{tenant}/uri/{旧item UUID}"}`
  - `destinationNodeURI`: 同形で新 item UUID（`identifier` と `uri` のサブフィールドは両方必須。欠けると skip される）
- Step 2 の対応表からこの配列を機械生成する小スクリプトを Step 2 のスクリプトに同居させてよい（ガイドではワンセットの例として提示）。
- 再 import:

```bash
uv run python cli.py import case --tenant {tenant_id} --file framework-2025-with-links.json --doc {old_doc_id}
```

import は additive（既存 items は skipped/updated、association は created のみ増える）。**旧項目の意味内容は変わらない**。

- 代替経路（CSV）: 旧 doc を `export csv`（custom profile）→ `replacedBy` / `exactMatchOf` 列に新 UUID を記入（複数は `|` 区切り。同一テナント内なので裸の UUID でよい）→ `import csv --doc {old_doc_id}` で戻す。ただし後述「CSV 経路の注意」の document-level rebuild の罠があるため、**必ず全項目入りのフルエクスポートを編集する**こと。isChildOf も全削除→再生成されるため、凍結済みドキュメントには JSON 経路を推奨、と明記。

**Step 6 — 旧版を Deprecated にする**

最小・最安全の経路は**メタデータ行のみの CSV**（データ行 0 件の CSV は既存 items/associations を温存し CFDocument メタデータだけ更新する、という仕様が既にある）:

```csv
#adoption_status,Deprecated
#status_end_date,2026-03-31
```

```bash
uv run python cli.py import csv --tenant {tenant_id} --doc {old_doc_id} --file deprecate-2025.csv
```

- キーは**スネークケース**（`#adoption_status` / `#status_end_date`。JSON のキャメルケースと異なる点を明記）。日付は `YYYY-MM-DD`。
- 「No data rows in CSV; metadata updated, existing items and isChildOf preserved」という警告が出るが、これは**期待どおりの動作**であることを書く。
- 代替: `framework-2025-with-links.json` の `CFDocument` に `"adoptionStatus": "Deprecated"`, `"statusEndDate": "2026-03-31"` を入れて Step 5 の再 import に相乗りさせてもよい（1 回の import で済む）。CASE import の doc 更新は原則として**非 null フィールドのみ**上書きする。ただし `statusStartDate` / `statusEndDate` は例外で、`import case --allow-status-clear` を付けた場合に限り null で消せる（既定では保持）点に触れる。
- `adoptionStatus` は CASE 上は自由文字列だが、compeito の Web UI は `Adopted`（緑）/ `Deprecated`（ピンク）/ `Draft`（黄）の 3 値をバッジ色分け表示する。この 3 値に揃えることを推奨。

**Step 7 — 確認と表示順**

- Web UI: 旧版ツリーページに `Deprecated` バッジ、新版に `Adopted` バッジが出る。旧項目の詳細ペインに `replacedBy` 関連が表示され、リンク先（新項目）へ辿れる（テナント内クロスドキュメント解決は実装済み）。
- 新版を一覧の先頭に出す:

```bash
uv run python cli.py doc update --tenant {tenant_id} --doc {new_doc_id} --display-order 1
uv run python cli.py doc update --tenant {tenant_id} --doc {old_doc_id} --display-order 2
```

- API: `GET /{tenant}/ims/case/v1p1/CFDocuments` に両版が並び、`adoptionStatus` / `statusStartDate` / `statusEndDate` で機械可読にライフサイクルが分かる（`filter=adoptionStatus='Adopted'` での絞り込みも可能 — case_query_params.py がサポート済み）。

### 4. What happens to issued OB v3 badges / 発行済み OB v3 バッジへの影響

- **何も起きない — それが狙い**。バッジの alignment は旧項目の URI（permalink `{BASE_URL}/{tenant}/uri/{uuid}`）を保持しており、旧項目は旧ドキュメントに UUID・URI・fullStatement とも不変のまま残る。バッジ検証者がその URL を開けば、当時の記述がそのまま表示される。
- 加えて改善されること: permalink 先の詳細ページには `Deprecated` 状態と `replacedBy` の行き先（新版項目）が表示されるため、「このバッジは旧版基準で発行された。現行の対応項目はこれ」という文脈が**人にも機械にも**伝わる。
- 新規発行するバッジは新版項目の URI を参照させる（OBF 側でフレームワークを取得し直す）。
- してはいけないこと（再掲）: 旧項目の fullStatement を in-place で書き換えること。バッジの意味が黙って変わる。

### 5. CSV route cautions / CSV 経路での注意

- **document-level rebuild の罠**: CSV import は、ヘッダーに存在する association 列のタイプを**ドキュメント全体で削除してから再生成**する。一部項目を省いた部分 CSV を import すると、省いた項目のその種の関連も消える。編集前に必ずドキュメント全体をフルエクスポートし、それを編集して戻すこと（isChildOf も同じ全削除→再生成）。
- 列が**無い**タイプは温存される（CASE JSON 経由で入れた関連は、その列に言及しない CSV の往復では消えない）。逆に言うと、custom profile のフルエクスポートには `replacedBy` / `exactMatchOf` 列が含まれるため、**うっかりセルを空にして戻すと対応付けが消える**。
- OpenSALT profile には `Replaced By` 列はあるが `exactMatchOf` / `isTranslationOf` 列が**無い**（エクスポートで落ちる）。改訂プロトコルの運用では **custom profile（既定）** を使うこと。
- association の `identifier` / `notes` / `targetType` 等は CSV に列が無く、CASE JSON でしか往復しない（round-trip-fidelity.md 参照）。対応付けを厳密に保全したい場合も JSON 経路。
- 凍結済み旧ドキュメントへの CSV フル import は sequenceNumber の自動採番（10,20,30…への振り直し）等の副作用があるため、旧 doc に触る操作は「メタデータ行のみ CSV」（安全）か「JSON 再 import」（additive）に限るのが原則。

### 6. Edge cases / エッジケース

- **ルーブリックの改訂**: `export case` の出力には `CFRubrics`（criteria / levels 含む）が入り、UUID 差し替えスクリプトが rubric 系の identifier も新規採番するので、**ルーブリックは新版で自動的に複製される**。criteria の `CFItemURI` は item UUID の置換に追従する（全文置換方式のため）。旧版のルーブリックは旧版と共に凍結される。ルーブリック基準の実質的変更も「新版を起こす」判断基準に含める（§2 の表参照）。
- **多版並存時の表示**: テナントのフレームワーク一覧には全版が並ぶ（一覧に adoptionStatus バッジは出ない。バッジが出るのはツリーページと詳細）。`doc update --display-order` で現行版を上に。版が増えてきたら、Deprecated の古い版を一覧の下方に送る運用を書く。タイトルに年度を含める規約（例: 「◯◯コンピテンシー標準（2026年度版）」）を推奨。
- **年度サイクルとの対応**: 日本の教育機関を想定した対応例を書く — `statusStartDate=2026-04-01`（新年度開始）/ 旧版 `statusEndDate=2026-03-31`。改訂作業は前年度中に `Draft` で新版を作り、年度切替時に `Adopted` へ更新（これもメタデータ行のみ CSV で 1 コマンド）。「Draft の間も新版はテナント上に公開される（compeito はアクセス制御に adoptionStatus を使わない）」ことを注記し、非公開で準備したい場合は private テナントで作って本番テナントへ `export case` → `import case` する手を紹介。
- **後継の無い項目（廃止）**: replacedBy を張らず、item 単位の `statusEndDate` を設定する（CFItem にも列がある。custom CSV / xlsx に `statusStartDate` / `statusEndDate` 列あり）。**日付の意味は CFDocument と CFItem で異なるので、必ず書き分ける**（下記「日付の意味」）。
- **日付の意味（書き分け）**: この2つを混同すると1日ぶんずれ、UI の表示にも影響する。

  | | 意味 | 例 |
  |---|---|---|
  | `CFDocument.statusEndDate` | **有効期間の最終日**。その日までは有効 | 年度末の `2026-03-31` |
  | `CFItem.statusEndDate` | **廃止が確定した日**。その日から無効 | 改版が公表された `2022-03-14` |

  compeito の Web UI は CFItem について「`statusEndDate <= 今日` なら廃止」と判定し、既定でツリーから隠す（判定日は UTC）。未来日は「廃止予定」として生きた項目のまま表示するので、年度末日を前もって設定する運用と衝突しない。詳細は [retired-item-ui.md](./retired-item-ui.md)。
- **廃止項目（墓標）の保持**: 廃止した項目は**削除しない**。CASE には削除操作が無く、compeito のインポートも additive only である。発行済み OB v3 バッジの alignment 先を壊さないためでもある。ガイドには次を書く。
  - 廃止項目はテナントに残り続ける。UI では既定で隠れ、`?includeRetired=1` で表示できる（生きた子孫を持つ廃止項目は経路を保つため隠れず、バッジ付きで残る）
  - permalink（`/{tenant}/uri/{uuid}`）は廃止後も解決し、廃止バナーと後継リンクを表示する
  - 誤って廃止にした項目を戻すには、`statusEndDate` を明示的な `null` にした CASE パッケージを `import case --allow-status-clear` で取り込む。**CSV / xlsx では戻せない**（空セルは「未指定」の意味で、クリアを表現できない）
  - 外部の生成側と連携する場合、墓標と取り消しは**毎版すべて含める**前提で設計する（取り込む側が全ての版を順に適用するとは限らない）
- **1 項目が複数に分割された場合**: replacedBy は複数張れる（CSV では `|` 区切り、JSON では association を複数個）。統合（多→1）も同様に各旧項目から同じ新項目へ。
- **テナントをまたぐ参照**: destinationNodeURI に他テナント/外部の完全 URI も書ける（CSV では完全 URI セル、検証無しで verbatim 格納）が、本プロトコルは同一テナント内の新旧 2 ドキュメントを想定、と範囲を明示。

### 7. Future work / 将来の自動化

- `doc duplicate`（仮）CLI — 新 UUID 採番・title/version/status 更新・replacedBy 自動生成までを 1 コマンドで行う構想。**本ガイドの手作業レシピの自動化**であり未着手（backlog 参照）。ガイドでは「現時点では本ガイドの手順が正」としてリンクだけ張る。

### 8. See also / 関連ドキュメント

- opencase-interop.md（import/export の基本操作）、csv-format.md、import-logic.md、round-trip-fidelity.md、api-spec.md。

## UUID 差し替えスクリプトの仕様（ガイドに載せる例の設計）

手作業のエディタ置換は「identifier だけ替えて uri を替え忘れる」「association の originNodeURI / destinationNodeURI の追従漏れ」「置換対象の UUID が別の UUID の部分文字列になる事故は無いが、大文字小文字混在を見落とす」等で事故りやすい。ガイドには **Python 小スクリプト（30〜50 行）を全文掲載**する。仕様:

1. **入力**: `framework-2025.json`（export case の出力）。**出力**: `framework-2026.json` と `uuid-mapping.json`（`{"旧UUID": "新UUID", ...}`）。
2. **新規採番する identifier**（対応表に載せる）:
   - `CFDocument.identifier`
   - `CFItems[].identifier`（全項目。**変わらない項目も含む** — 使い回すと import 時に旧ドキュメントから項目が引き剥がされるため）
   - `CFAssociations[].identifier`
   - `CFRubrics[].identifier` とその `CFRubricCriteria[].identifier`・`CFRubricCriterionLevels[].identifier`
3. **採番しない（共有定義なので温存する）**: `CFDefinitions` 配下の CFItemType / CFSubject / CFConcept / CFLicense / CFAssociationGrouping の identifier。これらはテナントレベルの find-or-create で共有されるのが正しい。
4. **置換方式**: JSON を文字列化した全文に対して、対応表の各「旧UUID → 新UUID」を**大文字小文字を無視して**一括置換する（外部由来データは大文字 UUID が混ざり得る。association のノード identifier は import 時に小文字化されるが、エクスポート JSON 内の表記ゆれに備える）。UUID は 36 文字固定形式なので部分一致事故は起きない。この方式なら `identifier`・`uri`（`.../uri/{uuid}` 形式）・`originNodeURI`/`destinationNodeURI`・rubric の `CFItemURI` が**すべて同時に**整合して置き換わる。
5. 置換後に JSON として再パースして妥当性を確認し、整形して書き出す。
6. （オプション同梱）`uuid-mapping.json` から Step 5 用の replacedBy / exactMatchOf の `CFAssociations` 配列を生成する関数。`uri` サブフィールドは `{BASE_URL}/{tenant}/uri/{uuid}` で組み立てる（BASE_URL とテナント UUID を引数に）。どの対応を exactMatchOf 扱いにするかは、旧新の `fullStatement` 完全一致で自動判定してよい（一致 → replacedBy + exactMatchOf、不一致 → replacedBy のみ）。
- jq でも同種のことは書けるが、対応表の生成と 2 パス置換が煩雑なので、ガイドでは Python 例を正とし jq は一言触れる程度にする。

## 検証済み事実（執筆時にそのまま使ってよい・出典付き）

ガイド執筆者が再調査しなくて済むよう、コード・docs で検証済みの事実を列挙する。

1. **CLI コマンド体系**（cli.py 検証済み）: `tenant list` / `doc list --tenant` / `doc update --tenant --doc --display-order N` / `import case --tenant (--url|--file) [--doc]` / `export case --tenant --doc --file` / `import csv --tenant --file [--doc] [--profile auto|custom|opensalt|simple]` / `export csv --tenant --doc --file [--profile custom|opensalt]` / `import rubric` / `export rubric`。`export case` は CFPackages GET と同形のペイロード（整形出力）。
2. **upsert は additive**: 外部ソースに無いリソースは削除されない（import-logic.md「Resources not present in the external source」）。旧パッケージ＋追記 association の再 import で既存が壊れない根拠。
3. **item UUID 使い回しの危険**: 同一テナント内で identifier 一致した CFItem が別ドキュメントから来た場合、`cf_document_id` を**付け替える**（移動警告「Item '...' moved from document ...」）。旧ドキュメント側には dangling isChildOf が残り depth も再計算されない（import-logic.md Step 5 / CSV Step 5）。→ 全 UUID 差し替えが必須である根拠。
4. **replacedBy / exactMatchOf は正式サポート**: `VALID_ASSOCIATION_TYPES`（src/services/case_import_service.py:113 付近）に両方含まれる。CSV では `CUSTOM_ASSOC_COLUMNS`（src/services/csv_export_service.py:250 付近）により custom profile の 25 列ヘッダーに `replacedBy` / `exactMatchOf` 列がある。OpenSALT profile は `Replaced By` のみ（`exactMatchOf` 列なし）。API（CFAssociations エンドポイント・CFPackage）でも当然配信される。
5. **CSV の association セル**: 同一テナント内ターゲット → 裸 UUID、外 → 完全 URI（verbatim 格納・末尾 UUID を identifier に採用）。テナント内で見つからない UUID は警告付きで**リンク自体は作られる**（csv-format.md「Expressing associations」）。エクスポート時は in-document → UUID、document 外（同一テナント別 doc 含む）→ **完全 URI** で出る。
6. **document-level rebuild**: ヘッダーに列が存在する association タイプはドキュメント全体で削除→再生成。列が無いタイプは温存（import-logic.md Step 7.5）。
7. **adoptionStatus / statusStartDate / statusEndDate**:
   - CFDocument スキーマ・DB・API filter（`case_query_params.py` の filter フィールドに 3 つとも登録済み）でサポート。
   - CASE import: `_create_document` は 3 フィールドとも取り込み。更新時は原則として**非 null のみ上書き**だが、`statusStartDate` / `statusEndDate` は例外で、`import case --allow-status-clear` を付けた場合に限り明示的な `null` でクリアできる（既定は保持。import-logic.md「例外：ライフサイクル日付」）。`adoptionStatus` にクリア手段は無い。
   - CSV メタデータ行: `#adoption_status` / `#status_start_date` / `#status_end_date`（スネークケース。日付は `YYYY-MM-DD`。csv-format.md）。
   - **メタデータ行のみ（データ行 0 件）の CSV は items/associations を温存**して CFDocument メタデータだけ更新（csv-format.md「Empty files / no data rows」、import-logic.md:178）。→ Step 6 の根拠。
   - CFItem にも `statusStartDate` / `statusEndDate` があり custom CSV に列がある（CFItem に adoptionStatus は無い — CASE v1.1 仕様どおり）。
   - `adoptionStatus` は CASE 上 enum 無しの自由文字列（公式 Information Model 参照 — [docs/reference/README.md](../../reference/README.md)）。
8. **URI の扱い**: CASE import はソースの `uri` を verbatim 温存、無ければ `{BASE_URL}/{tenant_id}/uri/{identifier}` を生成（`_resolve_uri`、case_import_service.py:54）。compeito 発のエクスポートは常に後者の形なので、UUID 全文置換で uri も自動的に整合する。
9. **UI 表示**: ツリーページ（cftree.html:17-24）が `adoption_status` をバッジ表示（Adopted=緑 / Deprecated=ピンク / Draft=黄、その他はニュートラル）。詳細ヘッダにも表示（resource_detail.html:534）。詳細ペインの関連はタイプ注記付きで表示され、テナント内の別ドキュメントのノードも解決してリンクする（resource_detail.html の assoc_node_other_doc / cross_tenant 処理）。テナントのフレームワーク**一覧**（tenant.html）には adoptionStatus 表示は無い。
10. **association の検証**: import は `identifier`（UUID 必須）/ `associationType` / `originNodeURI`・`destinationNodeURI`（各 `identifier`+`uri` サブフィールド必須）の欠落で skip。origin/destination が実在するかは検証しない（クロスドキュメント/外部参照を許容。import-logic.md:437）。ノード identifier は UUID なら小文字化して格納。
11. **ルーブリック**: `export case` は `CFRubrics` を含み、`import case` はルーブリックを upsert（レポートに rubrics created/updated/skipped）。criteria は `CFItemURI` で item を参照。

## ガイド執筆者への追加指示（執筆時に実機検証すべき事項）

公開前に、使い捨てテナントで**レシピを一巡し、載せるコマンド出力を実物に差し替える**こと。特に:

1. Step 2 のスクリプトを実データ（例: docs/guide/initial-setup.md のサンプルフレームワーク）で実行し、`import case` 後の created 数が items/associations/rubrics とも元と一致すること。
2. Step 5 の JSON 再 import で associations created のみ増え、items が updated/skipped（意味内容不変）であること。旧項目詳細ペインに replacedBy が表示され新項目へ辿れること。
3. Step 6 のメタデータ行のみ CSV で `Deprecated` バッジ・`statusEndDate` が付き、items/isChildOf が温存されること（「No data rows」警告文言も実物を転記）。
4. `export csv --profile custom` の旧 doc 出力に `replacedBy` / `exactMatchOf` 列が値付きで現れること（document 外ターゲットが完全 URI になることも確認し、その旨ガイドに書く）。
5. 逆に「やってはいけない」検証: 旧 item UUID を残したまま新 doc として import すると移動警告が出て旧 doc から項目が消えることを確認（ガイドには警告文言を引用して危険性を示す）。
6. `GET /{tenant}/ims/case/v1p1/CFDocuments?filter=adoptionStatus='Adopted'` が新版だけ返すこと（API 例として載せる場合）。

## 非対象（今回やらないこと）

- **コード変更一切**（CLI 追加・UI 変更・スキーマ変更なし）。
- `doc duplicate` CLI（新 UUID 採番＋replacedBy 自動生成）— backlog 行の追加のみ。着手時は本仕様の§UUID 差し替えスクリプトが要件の下敷きになる。
- adoptionStatus に基づくアクセス制御・配信制御（Draft を非公開にする等）。
- OBF / TAO 側の操作手順の詳細（フレームワーク再取得への言及に留める）。
- CASE 標準外の独自バージョン管理機構（履歴テーブル・diff 表示等）。

## 残る決定事項（レビューで確認したい点）

- ~~exactMatchOf を「replacedBy に追加で張る」か「変わらない項目は exactMatchOf のみ」か~~ → **解消済み（レビューで確定）**: 決定事項 3 のとおり「replacedBy に**追加で** exactMatchOf を張る」を採用。「後継を辿る」consumers に一様な forward pointer を与えられるため。「exactMatchOf のみ」案は不採用。
- 対応付け association を旧ドキュメント側に置く方針（本設計）の確認。新ドキュメント側に置く案は、旧 doc を一切触らない利点があるが、CSV 経路で association が孤児化する（origin が doc 外だと新旧どちらの CSV エクスポートにも現れない）ため採らない。
- backlog 追加行の番号・文言（B7 想定）。
- ガイドのタイトル（案: EN "Framework Revision Guide" / JP「フレームワーク改訂ガイド」）。
