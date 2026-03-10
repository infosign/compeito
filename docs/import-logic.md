# インポート/エクスポート ビジネスロジック

**エラー・警告メッセージの言語:** 本ドキュメント内のエラーメッセージ・警告メッセージは**英語で統一**している（CASE API・Admin API の他のエラーメッセージと一致）。説明文（エラーの条件・動作の解説）は日本語で記載している。

## CSVインポート処理フロー

```
1. CSVファイル読み込み・フォーマット自動判定
2. メタデータ行のパース
2.5. (OpenSALT形式のみ) Is Part Of の事前スキャン
3. CFDocument の作成または更新
4. 行ごとのパース・バリデーション
5. lookup系テーブルの自動生成 (CFItemType, CFSubject, CFConcept)
6. CFItem の作成または更新 (upsert)
7. CFAssociation (isChildOf) の生成
8. depth の計算
9. 結果レポート出力
```

**トランザクション戦略:**
全ステップ（3〜8）を単一トランザクションで実行する。Step 4 のバリデーションエラーはDB書き込み前に弾くため、トランザクション内でのエラーは原則発生しない。万一 DB レベルのエラーが発生した場合はトランザクション全体をロールバックしてエラー終了する（部分コミットしない）。NFR-6.5 の「行単位スキップ」はバリデーション段階での処理であり、DB書き込み段階ではない。

**同一ドキュメントへの同時インポート防止:**
既存ドキュメント更新時（`--doc` 指定等）は、Step 3 で対象 CFDocument 行に `SELECT ... FOR UPDATE` を取得し、トランザクション終了まで保持する。これにより同一ドキュメントへの並行インポートを直列化し、isChildOf 全削除→再生成の競合（重複 association 等）を防止する。新規ドキュメント作成時はドキュメントがまだ存在しないため、ロックは不要。

### ステップ1: ファイル読み込み・フォーマット判定

**エンコーディング:** CSVファイルを UTF-8 として読み込む。BOM（`\xEF\xBB\xBF`）が先頭にある場合は自動的にスキップする（Python の `utf-8-sig` エンコーディング相当）。UTF-8 としてデコードできない場合はエラー終了する（「CSV file is not valid UTF-8」）。

**UUID の大文字/小文字:** UUID 識別子の比較（upsert マッチング、parentIdentifier 解決、`/uri/{uuid}` 検索等）は**大文字小文字を区別しない**（PostgreSQL の UUID 型はケースインセンシティブ。`D86774F2-...` と `d86774f2-...` は同一と見なす）。新規作成時は小文字で正規化して保存する。外部インポート由来の UUID は元の形式のまま保存するが、比較時にはケースインセンシティブで行う。

フォーマット自動判定ロジックは [csv-format.md](csv-format.md) を参照。

### ステップ2: メタデータパース

`#` で始まる行をキー・バリューとしてパースし、CFDocument のフィールドにマッピングする。
CLI引数が指定されている場合はCLI引数が優先。

**空文字列の扱い（全メタデータ共通）:** 全ての単一値メタデータフィールド（`#title`, `#version`, `#creator`, `#publisher`, `#description`, `#language`, `#adoption_status`, `#official_source_url`, `#license`, `#status_start_date`, `#status_end_date`）において、値が空文字列（前後空白をトリムした後に空）の場合は NULL（未指定）として扱う。新規作成時は NULL が設定され、更新時は既存値を保持する（キー自体が未記載の場合と同じ動作）。

### ステップ2.5: Is Part Of 事前スキャン（OpenSALT形式のみ）

OpenSALT形式の場合、Step 3 で CFDocument を特定するために `Is Part Of` カラムの値が必要。`Is Part Of` はデータ行のカラム値であり Step 4（行パース）より前に読み取る必要があるため、全データ行の `Is Part Of` 列を事前にスキャンする。最初の非空値を CFDocument identifier として採用し、異なる値の行があれば記録しておく（Step 4 で警告出力する: 「Row N: Is Part Of 'xxx' differs from document identifier 'yyy', ignored」）。全行が空の場合は新規ドキュメント作成として扱う。この事前スキャンでは `Is Part Of` 列のみを読み取り、他のカラムは処理しない。

### ステップ3: CFDocument 作成/更新

| 条件 | 動作 |
|------|------|
| `--doc` 未指定（独自形式・簡易形式） | 新規CFDocumentを作成。`identifier` は UUID v4 自動採番 |
| `--doc` 未指定（OpenSALT形式、`Is Part Of` 非空） | `Is Part Of` の値を CFDocument identifier として同一テナント内で検索。存在すれば更新、なければ新規作成（`identifier` は `Is Part Of` の値を使用）。`Is Part Of` がUUID形式でない場合はエラー終了（「Is Part Of value is not a valid UUID: '...'」） |
| `--doc` 未指定（OpenSALT形式、`Is Part Of` 空） | 新規CFDocumentを作成。`identifier` は UUID v4 自動採番 |
| `--doc {uuid}` 指定、同一テナント内に存在する | 既存CFDocumentを更新（下記ルールで上書き）。OpenSALT形式の `Is Part Of` は無視 |
| `--doc {uuid}` 指定、同一テナント内に存在しない | エラー終了（「Document not found: '{uuid}'」） |

**新規作成時の動作:**
- `identifier` → 条件テーブルに従い UUID v4 自動採番、または OpenSALT `Is Part Of` の値を使用
- `uri` → `{BASE_URL}/{tenant_id}/uri/{identifier}`
- `title` → `--doc-title` > `#title` の優先順。空文字列は「未指定」と同等に扱う（空文字列のタイトルは許可しない）。いずれもない場合はエラー終了（「Document title is required」）
- `version` → `--doc-version` > `#version` の優先順。空文字列は「未指定」と同等に扱う。いずれもない場合は NULL
- `language` → メタデータ `#language` の値。未指定なら NULL
- その他のフィールド → 対応するメタデータ行の値。未指定なら NULL
- `last_change_date_time` → インポート実行時のUTCタイムスタンプ

**更新時の動作:**
- メタデータ行に値がある → 対応するCFDocumentフィールドを上書き
- メタデータ行に値がない（キー自体が未記載） → 既存値を保持（NULLで上書きしない）
- `last_change_date_time` → インポート実行時のUTCタイムスタンプで上書き
- `title` → `--doc-title` > `#title` > 既存値の優先順
- `version` → `--doc-version` > `#version` > 既存値の優先順

### ステップ4: 行パース・バリデーション

各行を内部表現に変換する。エラーは行番号と共に収集し、最後にまとめてレポートする。

**バリデーションルール:**
- `fullStatement` が空または空白文字のみ → 行スキップ（警告「Row N: fullStatement is empty, skipped」）。前後の空白をトリムしてから判定する（トリム後の値が空なら空扱い）。トリム後の値をそのまま fullStatement として保存する（先頭・末尾の空白は除去される）。**簡易形式の場合**: インデント（先頭の空白）から depth を算出した後にトリムする（インデント解析 → トリム → 空判定の順）
- `Identifier` が空 → UUID v4 自動採番
- `Identifier` がUUID形式でない → エラー（行スキップ。警告「Row N: Invalid Identifier 'xxx', skipped」）
- **同一CSV内で `Identifier` が重複** → 後の行を採用（警告「Row N: Duplicate Identifier 'xxx', overwriting Row M」）
- `educationLevel` のパース → カンマ区切りで文字列配列に変換（各値の前後空白をトリムし、トリム後の空文字列はフィルタする。例: `"09, 10, 11"` → `["09", "10", "11"]`、`"09,,11"` → `["09", "11"]`）
- `conceptKeywords` のパース → カンマ区切りで文字列配列に変換（各値の前後空白をトリムし、トリム後の空文字列はフィルタする。例: `"分析, 評価"` → `["分析", "評価"]`、`"分析,,評価"` → `["分析", "評価"]`）
- `parentIdentifier` / `Is Child Of` が非空かつUUID形式でない → 警告（「Row N: parentIdentifier 'xxx' is not a valid UUID, treated as root」）。ドキュメント直下として扱う
- `sequenceNumber` → 整数に変換。変換失敗時はエラー（行スキップ。警告「Row N: Invalid sequenceNumber 'xxx', skipped」）。値が PostgreSQL INTEGER 範囲（-2147483648 ～ 2147483647）を超える場合も変換失敗として同じ扱い
- `statusStartDate` → 非空の場合、`YYYY-MM-DD` 形式の有効な日付かを検証する。形式不正または無効な日付（例: `2025-13-45`）の場合は警告を出力し（「Row N: Invalid statusStartDate 'xxx', set to null」）、該当フィールドを NULL として扱う（行スキップではない）
- `statusEndDate` → `statusStartDate` と同じバリデーションルール（警告メッセージのフィールド名は `statusEndDate`）
- `license` → CFItemType と同じ lookup パターン。Step 5 で cf_license を find or create し、`cf_item.cf_license_id` に FK を設定する。空セルなら NULL（新規作成時）、または既存値を保持（更新時）
- `language` → 非空の場合、10文字以下であることを検証する。超過の場合は警告を出力し（「Row N: language 'xxx' exceeds 10 characters, set to null」）、値を NULL として扱う（行スキップではない。DB の `VARCHAR(10)` 制約によるトランザクション全体のロールバックを防止する）

**メタデータのバリデーション:**
- `#adoption_status` → 有効値（`Draft` / `Private Draft` / `Adopted` / `Deprecated`）以外の場合は警告を出力し（「Invalid adoption_status 'xxx', storing as-is」）、値をそのまま DB に保存する（エラーにしない）。APIレスポンスでもそのまま出力される
- `#language` → 10文字以下であることを検証する。超過の場合は警告を出力し（「Metadata #language 'xxx' exceeds 10 characters, set to null」）、値を NULL として扱う
- `#status_start_date` / `#status_end_date` → 非空の場合、`YYYY-MM-DD` 形式の有効な日付かを検証する。形式不正または無効な日付の場合は警告を出力し（「Invalid #status_start_date 'xxx', set to null」）、値を NULL として扱う

### ステップ5: lookup系テーブル自動生成

CSVの `CFItemType` 列・`license` 列・メタデータ `#subject`・メタデータ `#license` の値から、lookup系テーブル（cf_item_type, cf_license, cf_subject）のレコードを自動生成する。cf_concept は CSV インポートでは生成しない（外部 CASE ソースインポートの CFDefinitions.CFConcepts でのみ作成される）。

**前処理:** lookup のキーとなる値（CFItemType 列の値、`license` 列の値、`#license` の値、`#subject` の各要素）は前後空白をトリムしてからマッチングに使用する（トリム後の値を `title` として lookup テーブルに保存する）。トリム後に空文字列となる場合は「値なし」として扱う（lookup レコードの作成・検索を行わない）。`#subject` は csv-format.md のパース段階で個々の要素がトリム済みだが、`CFItemType` と `license` / `#license` は本ステップで追加でトリムする。

**マッチングルール（全lookup共通）:**
1. 同一テナント内で `title` の**完全一致**を検索（大文字小文字を区別する）
2. 一致するレコードが1件あれば、そのレコードのIDを使用
3. 一致するレコードが**複数件**あれば（外部CASEソースインポートで同一titleの異なるidentifierが作成された場合に発生しうる）、`identifier` の辞書順で最初のレコードを使用する（決定的な選択を保証する）
4. なければ新規レコードを作成（`identifier` = UUID v4、`uri` = `{BASE_URL}/{tenant_id}/uri/{identifier}`、`last_change_date_time` = インポート実行時のUTCタイムスタンプ）

**対象テーブルと元データ:**
| lookup テーブル | CSVの列 | 備考 |
|---------------|---------|------|
| cf_item_type | CFItemType | 値が空なら: 新規作成時は cf_item.cf_item_type_id = NULL、更新時は既存の cf_item_type_id を保持する（Step 6 の空セル→既存値保持ルールと同一） |
| cf_license | `license` 列（CFItem用）/ メタデータ `#license`（CFDocument用） | CFItemType と同じ title ベースの find or create パターン。`license` 列の値が空なら: 新規作成時は cf_item.cf_license_id = NULL、更新時は既存の cf_license_id を保持する。`#license` の値が空なら: 新規作成時は cf_document.cf_license_id = NULL、更新時は既存の cf_license_id を保持する。CFItem と CFDocument が同じ license 名を参照する場合、同一の cf_license レコードを共有する |
| cf_subject | メタデータ `#subject` | カンマ区切り。cf_documentの `subject` / `subject_uri` に格納 |

**JSONB配列の構築ルール（新規作成・更新共通）:**
- `cf_document.subject`: メタデータ `#subject` の値をそのまま文字列配列として格納（例: `["国語", "地理歴史"]`）
- `cf_document.subject_uri`: 各 cf_subject レコードの `{title, identifier, uri}` から LinkURI オブジェクト配列を構築（例: `[{"title":"国語","identifier":"<cf_subject.identifier>","uri":"<cf_subject.uri>"}]`）
- `cf_item.concept_keywords`: CSVの `conceptKeywords` の値をそのまま文字列配列として格納（例: `["分析", "評価"]`）

**cf_item.cf_concept_id について:** CSV に conceptKeywordsURI に対応するカラムは存在しない。CSV インポートでは `cf_concept_id` は設定されない（新規作成時は NULL、更新時は既存値を保持）。cf_concept レコードは外部 CASE ソースインポートの CFDefinitions.CFConcepts でのみ作成される。

**更新時の連動ルール:**
- CSVの `conceptKeywords` に値がある → `concept_keywords` を新しい値で更新する（`cf_concept_id` は連動しない。既存値を保持する）
- CSVの `conceptKeywords` が空セル → `concept_keywords` の既存値を保持する
- メタデータ `#subject` に値がある（1つ以上の subject 名がある） → `subject` と `subject_uri` の両方を新しい値で再構築する
- メタデータ `#subject` が記載されているが値が空（`#subject` のみ、または `#subject,` で値なし） → `subject` と `subject_uri` の両方を空配列 `[]` にクリアする
- メタデータ `#subject` が未記載（キー自体がない） → `subject` と `subject_uri` の両方とも既存値を保持する

### ステップ6: CFItem upsert

**upsertマッチングキー（優先順）:**

1. **Identifier一致**: 同一テナント内でCSVの `Identifier` が既存CFItemの `identifier` と一致 → 更新。一致したアイテムが別ドキュメントに属する場合は `cf_document_id` を現在のドキュメントに付け替える（**副作用**: 元ドキュメントの isChildOf Association がこのアイテムを参照し続けるが、depth は再計算されない。元ドキュメントの整合性を回復するには、元ドキュメントを再インポートするか、`doc delete` で削除する必要がある。付け替えが発生した場合は警告を出力する: 「Row N: Item '{item_identifier}' moved from document '{old_doc_identifier}' to current document」。`{old_doc_identifier}` は移動元ドキュメントの `identifier`（外部CASEインポートの同等の警告と同一形式）
2. **humanCodingScheme一致**: 同一テナント・同一ドキュメント内で `human_coding_scheme` が一致 → 更新。ただし NULL 同士はマッチしない（CSVの値が空、かつ既存も NULL の場合は不一致扱い）。一致するアイテムが複数存在する場合は `identifier` の辞書順で最初のアイテムを更新対象とする（決定的な選択を保証する。lookup テーブルの複数マッチルールと同一方針）
3. **いずれも不一致** → 新規作成

**更新時の動作:**
- CSVに値がある列 → 上書き
- CSVに値がない列（空セル、またはフォーマット定義にカラム自体が存在しない場合。例: OpenSALT形式の `listEnumeration`, `license`, `statusStartDate`, `statusEndDate`） → 既存値を保持（NULLで上書きしない）。**「空セル」の判定はパース前の原値で行う**（セル値が空文字列または未存在の場合。区切り文字のみの入力（例: `educationLevel` 列が `","` ）はパース前の原値が非空のため「値がある」として扱い、パース結果の `[]` で上書きされる）
- `uri` → 既存値を保持する（再生成しない。外部CASEソースインポート由来のアイテムの外部URIを上書きしないため）
- `last_change_date_time` → インポート実行時のUTCタイムスタンプで上書き

**新規作成時の動作:**
- `identifier` → CSVの値。空なら UUID v4 自動採番
- `uri` → `{BASE_URL}/{tenant_id}/uri/{identifier}`
- `language` → CSVの値。空なら CFDocument の `language` を継承（CFDocument も NULL なら NULL）
- `last_change_date_time` → インポート実行時のUTCタイムスタンプ

### ステップ7: CFAssociation (isChildOf) 生成

親子関係を `isChildOf` タイプの CFAssociation として保存する。

**parentIdentifier の解決:**
1. 独自形式・OpenSALT形式: `parentIdentifier` / `Is Child Of` 列の UUID で親を特定。検索スコープは同一テナント・同一ドキュメント内（現在のCSVでupsertされたアイテム + DB上の既存アイテム）。別ドキュメントのアイテムは対象外。自己参照（`parentIdentifier` が自身の `Identifier` と同一）の場合は警告を出力し（「Row N: parentIdentifier references self, treated as root」）、ドキュメント直下として扱う（自己参照の isChildOf は生成しない）
2. 簡易形式: インデントから depth を計算し、直前の浅い depth のアイテムを親とする
   - depth が2段以上ジャンプした場合（例: depth 0 → depth 3）: 直前のアイテムを親とし、警告を出力する（「Row N: depth jumped from 0 to 3, treating previous item as parent」）。中間の depth は作成しない
3. 親が見つからない場合: CFDocument を親とする（ルートレベル扱い）

**生成ルール:**
- `tenant_id` = インポート対象テナントの `id`
- `cf_document_id` = インポート対象 CFDocument の `id`（内部PK）
- `association_type` = `isChildOf`
- `identifier` = UUID v4 自動採番
- `uri` = `{BASE_URL}/{tenant_id}/uri/{identifier}`
- `origin_node_identifier` = 子アイテムの `identifier`
- `origin_node_uri` = 子アイテムの `uri`
- `origin_node_title` = 子アイテムの `fullStatement`
- `origin_node_target_type` = NULL（CSV インポートでは targetType を設定しない）
- `destination_node_identifier` = 親アイテムの `identifier`（親が CFDocument の場合は CFDocument の `identifier`）
- `destination_node_uri` = 親アイテムの `uri`（親が CFDocument の場合は CFDocument の `uri`）
- `destination_node_title` = 親アイテムの `fullStatement`（親が CFDocument の場合は `title`）
- `destination_node_target_type` = NULL（CSV インポートでは targetType を設定しない）
- `sequence_number` = CSVの `sequenceNumber`。空なら**同一親ごとに独立したカウンタ**で出現順に 10, 20, 30... を自動採番（各親が初めて登場した時点でその親のカウンタを 10 から開始する。同じ親の子が CSV 内で非連続に出現する場合もカウンタは継続する）。明示値と自動採番は独立で、明示値との重複回避はしない
- `last_change_date_time` = インポート実行時のUTCタイムスタンプ

**upsert時の既存Association処理:**
- 既存ドキュメントの更新時（`--doc` 指定、または OpenSALT `Is Part Of` で既存ドキュメントにマッチした場合）: 該当ドキュメントの既存 `isChildOf` Association を**全削除**してから再生成する。CSVにデータ行が0件（全行スキップを含む）の場合も既存 isChildOf は全削除される（ツリー構造が消失する）。既存 isChildOf が 1 件以上あり、かつ処理アイテムが 0 件の場合は警告を出力する（「No items processed, but {N} existing isChildOf associations were deleted」）。既存 isChildOf が 0 件の場合は警告を出力しない（削除実績がないため）
- 新規ドキュメント作成時: そのまま生成。処理アイテムが 0 件の場合は、空のドキュメントが作成される。この場合は警告を出力する（「No items processed, empty document created」）

### ステップ8: depth計算

インポート対象ドキュメント内の全CFItemの `depth` を、同ドキュメント内の isChildOf Association から計算する。他ドキュメントのアイテムは対象外。

**アルゴリズム:**
```
1. CFDocument直下のアイテム（parentがCFDocument）を depth=0 とする
2. BFS（幅優先探索）で isChildOf を辿り、子に parent.depth + 1 を設定
3. どの親からも到達できないアイテム（孤立ノード）は depth=0 とする（警告「Orphan item '{identifier}' has no reachable parent, set to depth 0」）
4. 循環参照を検出した場合: 該当アイテムの depth=0 とし、エラーレポートに追記
```

**循環参照検出:**
BFS 中に訪問済みノード（既に depth が割り当てられたノード）に再到達した場合は、循環参照ではなく**複数親**（multi-parent、外部CASEインポートで発生しうる）として扱い、再訪問をスキップする（最初に割り当てた depth を保持する。BFS はレベル順に処理するため、最も浅い depth が割り当てられる）。
**真の循環参照**の検出: BFS 完了後、全 isChildOf の origin/destination をたどり、ルートから到達不可能なサイクル（全ノードがドキュメント直下でなく、かつ BFS で到達されなかったノード群）を検出する。サイクル内のノードは Step 3 の孤立ノードとして depth=0 が割り当てられるが、追加で循環参照として報告する（警告「Circular reference detected involving items: '{identifier1}', '{identifier2}', ..., set to depth 0」）。
**注意:** ルートから到達可能な循環（例: A→B→C→A で A がルート直下）は BFS で全ノードに depth が割り当てられるため検出されない。この場合、ツリービューで無限展開が可能になるが、HTMX の遅延ロードにより無限ループは発生しない（ユーザーが手動で展開を繰り返す必要がある）。

### ステップ9: 結果レポート

インポート完了後、結果サマリーを出力する（CLI: rich テーブル形式）。

```
Import Result:
  Document:     高等学校学習指導要領 (d86774f2-...)
  Items:        1523 created, 34 updated, 3 skipped
  Associations: 2045 created, 0 updated, 0 skipped
  ItemTypes:    5 created, 0 updated, 2 existing, 0 skipped
  Subjects:     3 created, 0 updated, 0 existing, 0 skipped
  Concepts:     0 created, 0 updated, 0 existing, 0 skipped
  Licenses:     0 created, 0 updated, 0 existing, 0 skipped
  Groupings:    0 created, 0 updated, 0 existing, 0 skipped

Warnings:
  Row 45: fullStatement is empty, skipped
  Row 102: Invalid Identifier 'abc', skipped
  Row 203: Parent 'f1a2b3c4-...' not found, treated as root
```

## 外部CASEソースインポート

外部CASE APIからCFPackageを取得してDBに保存する。

**トランザクション戦略:**
CSVインポートと同様に、全ステップ（3〜7）を単一トランザクションで実行する。途中でDBレベルのエラーが発生した場合はトランザクション全体をロールバックしてエラー終了する。個別リソースの不正（エラーハンドリング表の「CFPackage内の個別リソースが不正」）はスキップ扱いでありDBエラーではないため、トランザクションは継続する。

**同一ドキュメントへの同時インポート防止:**
CSVインポートと同様に、既存ドキュメント更新時は Step 3 で対象 CFDocument 行に `SELECT ... FOR UPDATE` を取得し、トランザクション終了まで保持する。新規ドキュメント作成時はロック不要。

### `--doc` オプションの動作

| 条件 | 動作 |
|------|------|
| `--doc` 未指定 | 外部 CFPackage の CFDocument identifier で同一テナント内の既存を検索。存在すれば更新、なければ新規作成 |
| `--doc {uuid}` 指定、同一テナント内に存在する | 既存 CFDocument を外部データで上書き更新 |
| `--doc {uuid}` 指定、同一テナント内に存在しない | エラー終了（「Document not found: '{uuid}'」） |

**更新時の動作（CFDocument / CFItem / CFAssociation / CFDefinitions 共通）:**
- 外部 CFPackage に値があるフィールド → 上書き
- 外部 CFPackage に値がないフィールド（null/未存在） → 既存値を保持
- `identifier` → 既存値を保持する（上書きしない。identifier は upsert のマッチングキーであり、変更すると UNIQUE 制約違反や既存の Association・URI 参照の整合性が破壊される。`--doc` 指定時に外部 CFDocument の identifier が異なる場合も、既存ドキュメントの identifier を維持する）
- `last_change_date_time` → 外部データの値をそのまま使用（外部データにもない場合はインポート実行時のUTCタイムスタンプ）
- 既存の CFItem / CFAssociation は**テナント内全体**で identifier 一致検索し upsert する。一致した既存アイテムが別ドキュメントに属する場合は `cf_document_id` を現在のドキュメントに付け替える（一致しないものは新規作成）。付け替えが発生した場合は警告を出力する（「Item '{identifier}' moved from document '{old_doc_identifier}' to current document」。CSVインポートの同等の警告と同一方針）
- 既存 CFDefinitions（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）は**テナント内全体**で identifier 一致検索し upsert する
- **外部ソースに含まれないリソースの扱い:** DB上に存在するが外部CFPackageに含まれないCFItem/CFAssociation/CFDefinitions（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）は削除しない（additive only）。外部ソース側でリソースが削除されても、DB上には残り続ける。完全な同期が必要な場合は、事前に `doc delete` で既存ドキュメントを削除してから再インポートする

### 処理フロー

**`--url` パラメータの形式:**
- CASE API ベースパス（バージョンパスまで含む）を指定する。例: `https://opensalt.example.com/ims/case/v1p0`、`https://case.example.com/{tenant}/ims/case/v1p1`
- または、CFPackage の直接URL を指定する。例: `https://opensalt.example.com/ims/case/v1p0/CFPackages/{uuid}`
- サーバールート（例: `https://opensalt.example.com`）は不可。下記フローで `/CFDocuments` を追加するため、CASE API パスが含まれていないと正しいエンドポイントに到達できない

```
1. URL解決・CFPackage JSON取得
   - URLパスが `/CFPackages/` を含む場合: そのURLに直接GETリクエスト
   - それ以外の場合（ベースURL）:
     a. URLの末尾スラッシュを正規化（あってもなくても動くようにする）
     b. GET {url}/CFDocuments で文書一覧を取得
     c. 文書一覧が空の場合: エラー終了（「No documents found on remote server: {url}」）
     d. 最初（または唯一）のドキュメントの identifier を使用。文書一覧が2件以上の場合は警告を出力する（「Remote server has {n} documents. Importing first document '{identifier}'」）
     e. GET {url}/CFPackages/{identifier} で取得
2. JSON をパース・バリデーション
3. CFDocument を作成/更新
4. CFDefinitions (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping) を保存（フィールドマッピング後述）
5. CFItems を一括保存
   - 全 CFItem の `cf_document_id` は Step 3 で作成/更新した CFDocument の内部PK（`id`）を設定する（既存アイテムの別ドキュメントからの付け替えも含む）
   - `CFItemTypeURI.identifier` がある場合: 同一テナント内の `cf_item_type` から `identifier` 一致で検索し、`cf_item.cf_item_type_id` に内部PK（`id`）を設定する。一致するレコードがない場合（Step 4 で保存されなかった場合）は `cf_item_type_id = NULL` とし、警告を出力する（「CFItem '{item_identifier}': CFItemType '{type_identifier}' not found, set to null」）
   - `conceptKeywordsURI.identifier` がある場合: 同一テナント内の `cf_concept` から `identifier` 一致で検索し、`cf_item.cf_concept_id` に内部PK（`id`）を設定する。一致するレコードがない場合は `cf_concept_id = NULL` とし、警告を出力する（「CFItem '{item_identifier}': CFConcept '{concept_identifier}' not found, set to null」。CFItemType FK 解決と同一パターン）
   - `educationLevel`, `conceptKeywords` → 外部データの値をそのまま JSONB として保存する（FK解決なし）
6. CFAssociations を一括保存
   - 全 CFAssociation の `cf_document_id` は Step 3 で作成/更新した CFDocument の内部PK（`id`）を設定する
   - `originNodeURI.title` / `destinationNodeURI.title` をそのまま `origin_node_title` / `destination_node_title` に保持
   - `CFAssociationGroupingURI.identifier` がある場合: 同一テナント内の `cf_association_grouping` から `identifier` 一致で検索し、`cf_association.cf_association_grouping_id` に内部PK（`id`）を設定する。一致するレコードがない場合は `cf_association_grouping_id = NULL` とし、警告を出力する（「CFAssociation '{assoc_identifier}': CFAssociationGrouping '{grouping_identifier}' not found, set to null」）
   - 既存の CFAssociation が別ドキュメントに属する場合は `cf_document_id` を現在のドキュメントに付け替える。付け替えが発生した場合は警告を出力する（「CFAssociation '{identifier}' moved from document '{old_doc_identifier}' to current document」。CFItem の付け替え警告と同一方針）
7. depth を計算（対象ドキュメント内の全 CFItem について、同ドキュメント内の全 isChildOf Association（既存保持分+新規インポート分）から再計算する。アルゴリズムは CSV インポートの Step 8 と同一）
8. 結果レポート出力（CSV インポートの Step 9 と同一フォーマット。各カテゴリのカウンタ: items/associations は created/updated/skipped の3種、definitions は created/updated/existing/skipped の4種。warnings を併せて出力する。definitions の "updated" は identifier 一致で upsert し 1 つ以上のフィールドが変更された件数。"existing" は identifier 一致で upsert したがフィールド変更がなかった件数。"skipped" は identifier/title 欠落等のバリデーション不正でスキップされた件数。CSV インポートでは definitions の "updated" と "skipped" は常に 0（find or create のため更新しない。CSV 由来の値はバリデーション済みのためスキップも発生しない）。外部 CASE インポートでは "updated" と "skipped" が非 0 になりうる）
```

### CFDocument フィールドマッピング

外部 CFPackage の CFDocument オブジェクトから DB カラムへのマッピング:
- `identifier` → `identifier`（新規作成時のみ使用。更新時は既存値を保持）
- `uri` → `uri`（新規作成時のみ使用。更新時は既存値を保持。URI保持ルール参照）
- `title` → `title`
- `creator` → `creator`
- `publisher` → `publisher`
- `description` → `description`
- `frameworkType` → `framework_type`（v1.1 new）
- `caseVersion` → `case_version`（v1.1 new。値は `"1.1"` のみ有効）
- `language` → `language`（10文字以下であることを検証する。超過の場合は NULL として保存し警告出力。CSV インポートと同一ルール）
- `version` → `version`
- `adoptionStatus` → `adoption_status`
- `statusStartDate` → `status_start_date`（`YYYY-MM-DD` 形式の文字列 → DATE 型。形式不正の場合は NULL として保存し警告出力。CFItem と同一ルール）
- `statusEndDate` → `status_end_date`（`statusStartDate` と同一ルール）
- `licenseURI` → `cf_license_id`（`licenseURI.identifier` で同一テナント内の cf_license を検索し、内部PK を設定する。一致する cf_license がない場合は `cf_license_id = NULL` とし、警告を出力する。CFItem の CFItemTypeURI FK 解決と同一パターン）
- `officialSourceURL` → `official_source_url`
- `subject` → `subject`（文字列配列 JSONB）
- `subjectURI` → `subject_uri`（LinkURI オブジェクト配列 JSONB）
- `lastChangeDateTime` → `last_change_date_time`（ISO 8601 文字列をパース。形式不正の場合はインポート実行時の UTC タイムスタンプを使用し警告出力。未存在の場合も同様。CFItem と同一ルール）
- `CFPackageURI`, `notes` 等の非保存フィールドは無視する

### CFDefinitions フィールドマッピング

外部 CASE JSON のフィールド名（camelCase）を DB カラム名（snake_case）にマッピングする。共通フィールド（`identifier`, `uri`, `title`, `description`, `lastChangeDateTime`）は全 lookup テーブルで同一。`lastChangeDateTime` は ISO 8601 文字列をパースし、形式不正の場合はインポート実行時の UTC タイムスタンプを使用し警告出力する（CFItem の `lastChangeDateTime` と同一ルール）。未存在の場合も同様。固有フィールド:
- CFItemType: `typeCode` → `type_code`、`hierarchyCode` → `hierarchy_code`
- CFSubject: `hierarchyCode` → `hierarchy_code`
- CFConcept: `keywords` → `keywords`、`hierarchyCode` → `hierarchy_code`
- CFLicense: `licenseText` → `license_text`
- CFAssociationGrouping: 固有フィールドなし

### CFItem フィールドマッピング

外部 CFPackage の CFItem オブジェクトから DB カラムへのマッピング:
- `identifier` → `identifier`（新規作成時のみ使用。更新時は既存値を保持）
- `uri` → `uri`（新規作成時のみ使用。更新時は既存値を保持。URI保持ルール参照）
- `fullStatement` → `full_statement`（前後空白トリム後に保存。空の場合はスキップ）
- `humanCodingScheme` → `human_coding_scheme`
- `abbreviatedStatement` → `abbreviated_statement`
- `listEnumeration` → `list_enumeration`
- `language` → `language`（10文字以下であることを検証する。超過の場合は NULL として保存し警告出力。CSV インポートと同一ルール）
- `licenseURI` → `cf_license_id`（`licenseURI.identifier` で同一テナント内の cf_license を検索し、内部PK を設定する。一致する cf_license がない場合は `cf_license_id = NULL` とし、警告を出力する。CFDocument の licenseURI FK 解決と同一パターン）
- `statusStartDate` → `status_start_date`（`YYYY-MM-DD` 形式の文字列 → DATE 型。形式不正の場合は NULL として保存し警告出力）
- `statusEndDate` → `status_end_date`（`statusStartDate` と同一ルール）
- `educationLevel` → `education_level`（JSONB。外部データをそのまま保存）
- `subject` → `subject`（JSONB 文字列配列。外部データをそのまま保存。v1.1 new）
- `subjectURI` → `subject_uri`（JSONB LinkURI オブジェクト配列。外部データをそのまま保存。v1.1 new）
- `conceptKeywords` → `concept_keywords`（JSONB。外部データをそのまま保存）
- `conceptKeywordsURI` → `cf_concept_id`（`conceptKeywordsURI.identifier` で同一テナント内の cf_concept を検索し、内部PK を設定する。一致する cf_concept がない場合は `cf_concept_id = NULL` とし、警告を出力する。CFItemTypeURI FK 解決と同一パターン。CASE v1.1 では `conceptKeywordsURI` は単一の LinkURIDType）
- `CFItemTypeURI.identifier` → `cf_item_type_id` の FK 解決（Step 5 参照）
- `lastChangeDateTime` → `last_change_date_time`（ISO 8601 文字列をパース。形式不正の場合はインポート実行時の UTC タイムスタンプを使用し警告出力。未存在の場合も同様）
- `CFDocumentURI`, `notes`, `alternativeLabel` 等の非保存フィールドは無視する

### CFAssociation フィールドマッピング

外部 CFPackage の CFAssociation オブジェクトから DB カラムへのマッピング:
- `identifier` → `identifier`（新規作成時のみ使用。更新時は既存値を保持）
- `uri` → `uri`（新規作成時のみ使用。更新時は既存値を保持。URI保持ルール参照）
- `associationType` → `association_type`
- `originNodeURI.identifier` → `origin_node_identifier`
- `originNodeURI.uri` → `origin_node_uri`
- `originNodeURI.title` → `origin_node_title`
- `originNodeURI.targetType` → `origin_node_target_type`（v1.1 new。値は `"CASE"` or `"ext:*"` 等。NULL/未存在の場合は NULL）
- `destinationNodeURI.identifier` → `destination_node_identifier`
- `destinationNodeURI.uri` → `destination_node_uri`
- `destinationNodeURI.title` → `destination_node_title`
- `destinationNodeURI.targetType` → `destination_node_target_type`（v1.1 new。originNodeURI.targetType と同一ルール）
- `sequenceNumber` → `sequence_number`（INTEGER。数値以外の場合は NULL として保存し警告出力。浮動小数点数の場合は整数に切り捨て。PostgreSQL INTEGER 範囲（-2147483648 ～ 2147483647）を超える場合も NULL として保存し警告出力）
- `CFAssociationGroupingURI.identifier` → `cf_association_grouping_id` の FK 解決（Step 6 参照）
- `lastChangeDateTime` → `last_change_date_time`（CFItem と同一ルール）
- `CFDocumentURI` 等の非保存フィールドは無視する

### CFItemType FK 解決の補足

CFItem の `CFItemTypeURI` がない場合（`CFItemTypeURI` が null/未存在で `CFItemType` 文字列のみの場合）: `cf_item_type_id = NULL` とする（文字列だけでは identifier ベースの FK 解決ができないため）。`CFItemType` 文字列は DB に保存されない（FK JOIN で CFItemType.title から導出する設計のため）。型情報を保持するには外部ソース側が `CFItemTypeURI` を提供する必要がある。

### 未サポートフィールド・リソースの扱い

外部 CFPackage に含まれるが DB にカラムがないフィールドは無視する（エラーにしない）:
- `notes`（CFDocument / CFItem）: CASE v1.1 の任意フィールドだが DB スキーマに含めていない。外部インポート時に値が失われる
- `alternativeLabel`（CFItem）: 同上
- `CFPackageURI`（CFDocument）: API レスポンス生成時に動的構築するフィールドであり、DB に保存しない
- その他の未知フィールド: CASE v1.1 の将来的な拡張やサーバー固有フィールドは無視する

**CFRubrics の扱い（Phase 1）:**
外部 CFPackage に `CFRubrics` 配列が含まれている場合、Phase 1 では無視する（DB スキーマは存在するがインポートロジックは Phase 2）。`CFRubrics` が存在しても警告は出力しない（CFRubrics は CASE v1.1 の標準構造であり、未対応であっても正常動作の範囲内）。Phase 2 で CFRubric インポートを実装する際にこの節を更新する。

### URI保持ルール

外部インポート時は元のURIをそのまま保持する:
- `cf_document.uri` → 外部サーバーのURI（上書きしない。既存ドキュメント更新時も既存 uri を保持する）
- `cf_item.uri` → 外部サーバーのURI（上書きしない。既存アイテム更新時も既存 uri を保持する）
- `cf_association.uri` → 外部サーバーのURI（上書きしない。既存 Association 更新時も既存 uri を保持する）
- `identifier` → 外部のidentifier をそのまま使用
- **lookup リソース（CFItemType, CFSubject 等）の uri**: 一般更新ルール（値があれば上書き）に従う。同一外部ソースからの再インポートでは通常同じ値のため実質変化しないが、異なる外部ソースから同一 identifier の lookup を再インポートすると uri が更新される

自サーバーの `/uri/{uuid}` では `identifier` で検索するため、
外部URIのリソースも自サーバー経由でアクセス可能になる。

### エラーハンドリング

| エラー | 動作 |
|--------|------|
| 外部URLに接続できない（タイムアウト含む） | エラー終了。タイムアウトは各HTTPリクエストごとに30秒（ベースURLの場合、CFDocuments取得とCFPackage取得それぞれに30秒）。HTTPリダイレクト（301/302/307/308）は最大5回まで自動追従する。リトライしない |
| HTTPステータスが2xx以外 | エラー終了（「Remote server returned HTTP {status}: {url}」） |
| レスポンスがJSONとしてパースできない | エラー終了（「Response is not valid JSON」） |
| CFDocuments一覧レスポンスが不正（`CFDocuments` キーがない、配列でない等） | エラー終了（「Invalid CFDocuments response: {url}」） |
| JSONは有効だがCFPackage構造でない（下記参照） | エラー終了（「Invalid CFPackage response: {detail}」） |
| CFPackage内の個別リソースが不正（下記参照） | 該当リソースをスキップし、警告をレポートに追記。他のリソースは処理続行 |
| SSL証明書エラー | エラー終了（「SSL certificate verification failed」） |

**CFPackage構造バリデーション（エラー終了の条件）:**
以下のいずれかに該当する場合、「Invalid CFPackage response: {detail}」としてエラー終了する:
- ルートに `CFPackage` キーが存在しない（直接URLの場合）、または `CFDocuments` キーの配列内に期待される構造がない（ベースURL経由の場合）
- `CFPackage.CFDocument` が存在しない、またはオブジェクトでない
- `CFPackage.CFDocument.identifier` が存在しない、または UUID 形式でない
- `CFPackage.CFDocument.title` が存在しない、空文字列、または空白文字のみ（前後空白をトリムした後に空。新規ドキュメント作成時に DB の NOT NULL 制約違反となるため。既存ドキュメント更新時は既存値を保持するが、構造バリデーション段階では新規/更新を区別しないため一律でチェックする）

**個別リソースの不正（スキップの条件）:**
以下に該当する個別リソースはスキップし、警告を出力する:
- CFItem: `identifier` または `fullStatement` が欠落、または `fullStatement` が空文字列もしくは空白文字のみ（前後空白をトリムした後に空）。または `identifier` が UUID 形式でない（警告「Skipped CFItem: {reason}. identifier='{identifier}'」）
- CFAssociation: `identifier`, `associationType`, `originNodeURI`, `destinationNodeURI` のいずれかが欠落。または `associationType` が CASE v1.1 列挙値（api-spec.md 参照）に含まれない。または `originNodeURI` / `destinationNodeURI` 内の必須サブフィールド（`identifier`, `uri`）が欠落（DB の NOT NULL 制約違反を防止）。または `identifier` が UUID 形式でない（DB の UUID 型カラムへの格納不可を防止）。`originNodeURI.identifier` / `destinationNodeURI.identifier` は UUID 制限なし（LinkGenURIDType: 外部参照で非UUIDの場合あり。DB カラムは VARCHAR 型）（警告「Skipped CFAssociation: {reason}. identifier='{identifier}'」）
- CFDefinitions 内のリソース: `identifier` または `title` が欠落。または `identifier` が UUID 形式でない（警告「Skipped {resource_type}: {reason}. identifier='{identifier}'」）

### v1.0 → v1.1 正規化（Phase 2）

CASE v1.0 の CFPackage レスポンスを v1.1 形式に変換する:
- フィールド名の差異を吸収
- 欠落フィールドにデフォルト値を設定
- 詳細は Phase 2 実装時に定義

## CSVエクスポート処理フロー

```
1. CFDocument + 配下の全 CFItem を取得
2. 同一ドキュメント内（`cf_association.cf_document_id` が対象ドキュメントと一致）の isChildOf Association から親子関係を解決
3. ツリー順序（depth-first）でソート
4. 指定フォーマットでCSV生成
```

### エクスポート共通ルール

- エンコーディング: UTF-8（BOM なし）
- 改行コード: LF
- CSV構文: RFC 4180 準拠（フィールド内にカンマ・改行・ダブルクォートを含む場合はダブルクォートで囲む）

### 独自形式エクスポート

- CFDocumentの非NULLかつ非空のフィールドからメタデータ行を出力する（VARCHAR 型フィールドは NULL なら出力しない。FK 参照型フィールド `cf_license_id` は NULL なら出力しない、非 NULL なら `cf_license.title` を解決して `#license` として出力する。JSONB 配列型フィールド `subject` は NULL または空配列 `[]` なら出力しない。**round-trip 制約**: `[]`（空配列）は出力されないため、新規ドキュメントとしての re-import 時に `subject` / `subject_uri` は NULL に変わる。既存ドキュメントの更新時はキー未記載→既存値保持のため問題ない）。出力順: `#title`, `#version`, `#creator`, `#publisher`, `#description`, `#language`, `#adoption_status`, `#status_start_date`, `#status_end_date`, `#license`, `#official_source_url`, `#subject`）。`#status_start_date` / `#status_end_date` は `YYYY-MM-DD` 形式で出力する。メタデータ行もCSV行として出力するため、値にカンマ・改行・ダブルクォートが含まれる場合はRFC 4180に従いダブルクォートで囲む（例: `#description,"情報I, 情報II向け"`）。`#subject` は JSONB配列の各要素を個別のCSVフィールドとして出力する（単一のクォート文字列にまとめない。例: `#subject,国語,地理歴史,公民`）。個々の subject 値にカンマ等が含まれる場合は RFC 4180 に従い個別にクォートする（例: `#subject,国語,"情報I, 情報II",地理歴史`）
- ヘッダー行を出力する（`Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType,educationLevel,conceptKeywords,abbreviatedStatement,language,listEnumeration,license,statusStartDate,statusEndDate`）
- 全列を出力（Identifier含む）
- `parentIdentifier` には親アイテムのUUIDを出力。ルートレベルアイテム（親が CFDocument）の場合は空セル。1つのアイテムが複数の `isChildOf` association を持つ場合（外部CASEソースインポート由来）は、`sequence_number` が最小の association の親を採用する（NULL は非NULLの後に配置する。`sequence_number` が同じ場合は `destination_node_identifier` の辞書順で最初のもの）。**round-trip 制約**: 複数の isChildOf 親を持つアイテムは、エクスポート時に1つの親に集約される。このCSVを再インポートすると、選択されなかった親子関係は isChildOf 全削除→再生成により失われる
- `sequenceNumber` は `parentIdentifier` の決定に使用した isChildOf association の `sequence_number` を出力する（複数 isChildOf がある場合も、選択した association の値を使用）。NULL の場合は空セル。**round-trip 制約**: 空セルの `sequenceNumber` は re-import 時に自動採番（10, 20, 30...）に変わる。エクスポート時のソート順で自動採番されるため表示順序は維持されるが、実際の値は変化する
- `CFItemType` は `cf_item_type_id` から `cf_item_type.title` を解決して出力（`cf_item_type_id` が NULL なら空セル）。**round-trip 制約**: `title` のみ出力されるため、cf_item_type の `type_code`・`hierarchy_code`・`description` は CSV に含まれない。同一テナント内の再インポートでは title 一致で既存 cf_item_type レコードを使用するためこれらのフィールドは保持されるが、別テナントへのインポートでは title のみの新規レコードが作成され、これらのフィールドは欠落する
- `educationLevel` は JSONB 配列をカンマ区切り文字列に変換して出力（例: `["09","10","11","12"]` → `"09,10,11,12"`）。NULL または空配列 `[]` なら空セル。**round-trip 制約**: `[]`（空配列）は空セルとして出力されるため、新規作成での re-import 時に NULL に変わる（API レスポンスで `[]` と `null` は異なる出力となる。既存アイテムの更新時は空セル→既存値保持のため問題ない）
- `conceptKeywords` は JSONB 配列をカンマ区切り文字列に変換して出力（例: `["分析","評価"]` → `"分析,評価"`）。NULL または空配列 `[]` なら空セル（`educationLevel` と同じ round-trip 制約あり）。**制約**: 配列要素にカンマが含まれる場合（外部CASEソースインポート由来で発生しうる）、再インポート時にカンマで分割されて値が壊れる。この制約は `educationLevel` にも適用されるが、教育段階コードにカンマが含まれることは実運用上ない
- **`cf_concept_id` の round-trip 制約**: `conceptKeywordsURI`（cf_concept への FK 参照）は CSV に出力されない。CSV インポートでは `cf_concept_id` は設定されないため、外部 CASE ソースインポートで設定された `cf_concept_id` は CSV エクスポート→再インポートで失われる（NULL になる）。同一テナント内の更新時は空セル→既存値保持のため問題ない
- **`subject_uri` の round-trip 制約**: `subject_uri` は CSV に出力されない（`#subject` は subject 名のみ出力）。再インポート時にローカル cf_subject lookup テーブルから URI を再構築するため、外部 CASE ソースインポート由来の外部 URI はローカル URI に置き換わる。同一テナント内の更新では lookup レコードの identifier が一致するため URI は維持されるが、新規テナントへのインポートでは新しい identifier・URI が採番される
- `language` は `cf_item.language` をそのまま出力（NULL なら空セル）
- `abbreviatedStatement` は `cf_item.abbreviated_statement` をそのまま出力（NULL なら空セル）
- `listEnumeration` は `cf_item.list_enumeration` をそのまま出力（NULL なら空セル）
- `license` は `cf_item.cf_license_id` から `cf_license.title` を解決して出力（`cf_license_id` が NULL なら空セル）。CFItemType と同じ FK → JOIN パターン。**round-trip 制約**: `title` のみ出力されるため、cf_license の `license_text`・`description` は CSV に含まれない。同一テナント内の再インポートでは title 一致で既存 cf_license レコードを使用するためこれらのフィールドは保持されるが、別テナントへのインポートでは title のみの新規レコードが作成され、これらのフィールドは欠落する
- `statusStartDate` は `cf_item.status_start_date` を `YYYY-MM-DD` 形式で出力（NULL なら空セル）
- `statusEndDate` は `cf_item.status_end_date` を `YYYY-MM-DD` 形式で出力（NULL なら空セル）
- **cf_association_grouping の round-trip 制約**: cf_association_grouping は CSV に一切出力されない（CSV フォーマットに対応するカラムが存在しない）。外部 CASE ソースインポートで作成された cf_association_grouping レコードは、CSV エクスポート→別テナントへの CSV インポートで完全に失われる。同一テナント内の更新ではテナント所有の lookup レコードが DB 上に残るため影響はないが、テナント間のデータ移行には CSV ではなく外部 CASE ソースインポートを使用すべきである

### OpenSALT形式エクスポート（Phase 2）

- OpenSALTのヘッダー名で出力
- `Is Child Of` に親のIdentifierを出力
- `Is Part Of` にCFDocumentのIdentifierを出力

### ソート順序

ツリーの depth-first 順でソートする:
1. ルートレベルのアイテムを `sequence_number` 昇順で並べる（isChildOf で CFDocument を parent とするアイテム）
2. 各アイテムの子を `sequence_number` 昇順で再帰的に挿入
3. isChildOf の `sequence_number` が NULL のアイテムは、同一親の子の中で最後に配置する
4. `sequence_number` が同じ場合は `human_coding_scheme` の自然順ソート（数値部分を数値として比較する。例: `"A-2"` < `"A-10"`。Python の `natsort.natsorted()` をデフォルト設定（`alg=natsort.ns.DEFAULT`）で使用する。ロケール依存のソートは使わない（`humansorted` / `os_sorted` は不使用）。NULL は非NULLの後に配置する）
5. それも同じ場合は `identifier` の辞書順
6. 孤立アイテム（isChildOf Association を持たないアイテム）は通常ルートアイテムの後に配置する。孤立アイテム間のソートは `human_coding_scheme` 自然順 → `identifier` 辞書順（ツリービューの孤立アイテム表示順と同一）
