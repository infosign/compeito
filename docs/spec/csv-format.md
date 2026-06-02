# CSV Format Specification

## Format overview

Three CSV formats are supported. The format is auto-detected on import; on export it is selected via `--format`.

| Format | Import | Export | Use case |
|--------|--------|--------|----------|
| Custom | yes | yes (default) | Carries UUIDs; safe to edit and re-import (upsert) |
| OpenSALT | yes | yes (`--format opensalt`) | Migration from OpenSALT |
| Simple | yes | — | Minimal header; suitable for the first ingest |

## Auto-detection logic

The format is decided from the header row (line 1, or the first non-empty line after `#` metadata rows). Empty lines between metadata and the header are skipped by the common rule. **Column names are matched case-insensitively** across all formats:

1. **Custom**: header contains both `Identifier` and `fullStatement`.
2. **OpenSALT**: header contains `Is Child Of` or `Is Part Of`, or `Full Statement` (OpenSALT-compatible header).
3. **Simple**: anything else. The first column is treated as `fullStatement`.

**Note**: rule 3 is a catch-all, so a CSV with only part of the custom columns (e.g., `fullStatement` present but no `Identifier`) falls back to the simple format. Simple format is positional and does not map columns by name. To avoid an unintended fallback, always include the `Identifier` column in custom-format CSVs (it can be entirely empty).

**Empty files / no data rows**: when the file is empty (0 lines), or contains only metadata rows, there's no header to detect on. In that case the **simple format is used** (rule 3 fallback) and processing continues with zero data rows. The result is an empty document (on create) or all `isChildOf` associations being deleted (on update).

## Metadata rows

Lines starting with `#` may appear at the top of the file (optional). The rule applies to all formats.

```csv
#title,High School National Curriculum Standard
#version,1.0
#creator,Ministry of Education
#publisher,Ministry of Education
#description,High School National Curriculum (announced 2018)
#language,en
#adoption_status,Adopted
#official_source_url,https://www.mext.go.jp/...
#license,CC BY 4.0
#status_start_date,2018-03-30
#status_end_date,2028-03-31
#subject,Japanese,Geography & History,Civics
```

- `#title`: CFDocument title. If `--doc-title` is given on the CLI, the CLI flag wins.
- `#version`: CFDocument version. If `--doc-version` is given on the CLI, the CLI flag wins.
- `#subject`: subject(s). Multiple values can be comma-separated (e.g., `#subject,Japanese,Geography`). cf_subject lookups are auto-generated. Each value is trimmed; trimmed-empty values are filtered (e.g., `#subject,Japanese,,Geography` → `["Japanese", "Geography"]`).
- `#license`: license name (e.g., `CC BY 4.0`). A cf_license lookup is auto-generated and linked via `cf_license_id`. Same title-based lookup pattern as `CFItemType`.
- Others (`#creator`, `#publisher`, `#description`, `#language`, `#adoption_status`, `#official_source_url`, `#status_start_date`, `#status_end_date`): mapped to the corresponding CFDocument field. These are **single-value fields**: only the 2nd field (after CSV parsing) is used as the value (3rd and onward are ignored). To include commas, quote the value with `"` (e.g., `#description,"Information I, II"`). `#status_start_date` / `#status_end_date` must be in `YYYY-MM-DD` form.
- Metadata rows must appear before the header row. `#` lines after the header are treated as data rows (in the custom format they're parsed as `Identifier`, and rejected by UUID validation).
- Duplicate keys: the last value wins, and a warning is emitted ("Duplicate metadata key '#xxx', overwriting previous value"). `#subject` follows the same rule (overwrite, not merge).
- Unknown keys are ignored (a warning is emitted: "Unknown metadata key '#xxx', ignored").

## Custom format

### Columns

| Column | Required | Description |
|--------|----------|-------------|
| Identifier | — | UUID. Blank → auto-generated UUID v4 |
| fullStatement | yes | Full text of the item |
| humanCodingScheme | — | Human-readable code (e.g., "A-1-2") |
| parentIdentifier | — | Parent item's Identifier (UUID). Blank → directly under the document |
| sequenceNumber | — | Display order within the same parent. Blank → auto-assigned 10, 20, 30, … in encounter order |
| CFItemType | — | Item type name (e.g., "Knowledge & Skills"). Lookup is auto-generated |
| educationLevel | — | Education levels, comma-separated (e.g., "09,10,11,12") |
| conceptKeywords | — | Keywords, comma-separated (e.g., "analysis,evaluation") |
| abbreviatedStatement | — | Abbreviated form |
| language | — | Language code (e.g., "en"). Blank → inherits the document's language |
| listEnumeration | — | Enumeration text |
| license | — | License name (e.g., "CC BY 4.0"). Lookup is auto-generated |
| statusStartDate | — | Status start date (YYYY-MM-DD) |
| statusEndDate | — | Status end date (YYYY-MM-DD) |

### Example

```csv
#title,High School National Curriculum
#language,en
Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType,educationLevel,conceptKeywords
,Japanese,,,,Subject,,
,Modern Japanese,,,10,Course,,
,Items on the characteristics and use of language,A-1,,10,Knowledge & Skills,"10,11,12",language
a1b2c3d4-...,Acquire the Japanese knowledge and skills needed in society.,A-1-(1),<parent UUID>,10,,,
```

### Expressing hierarchy

The `parentIdentifier` column makes parent–child relationships explicit:
- Blank (or unspecified) → directly under the document (root level, depth=0).
- A UUID → child of the item with that Identifier.
- Forward and backward references are both allowed (resolved in two passes).
- A non-existent UUID → warning emitted; the row is treated as a root-level item.

## OpenSALT format

A format intended for interoperability with OpenSALT CSV imports. It is not fully compatible (see [reference/opensalt-csv-format.md](../reference/opensalt-csv-format.md) for differences).

### Columns

| Header | Internal field |
|--------|----------------|
| Identifier | Identifier |
| Full Statement | fullStatement |
| Human Coding Scheme | humanCodingScheme |
| Abbreviated Statement | abbreviatedStatement |
| Concept Keywords | conceptKeywords (comma-separated) |
| Education Level | educationLevel (comma-separated) |
| CF Item Type | CFItemType |
| Language | language |
| License | (ignored; managed at the CFDocument level) |
| Is Child Of | parentIdentifier (the parent's Identifier) |
| Sequence Number | sequenceNumber |
| Is Part Of | CFDocument identifier (see notes below) |

### Example

```csv
Identifier,Full Statement,Human Coding Scheme,Abbreviated Statement,Concept Keywords,Education Level,CF Item Type,Language,License,Is Child Of,Sequence Number,Is Part Of
d86774f2-...,Japanese,,,,,Subject,en,,,,a1b2c3d4-...
e97885g3-...,Modern Japanese,,,,,Course,en,,d86774f2-...,10,a1b2c3d4-...
```

### Notes on the OpenSALT format

- Handling of `Is Part Of`:
  - With `--doc`: the `Is Part Of` value is **ignored** and rows are bound to the specified document.
  - Without `--doc`, when `Is Part Of` is non-empty: that value is used as a CFDocument identifier searched within the tenant; if found, that document is updated; if not, a new CFDocument is created using this value as its `identifier`.
  - Without `--doc`, when `Is Part Of` is empty: a new document is created using the `#title` metadata or the `--doc-title` CLI flag.
  - When `Is Part Of` varies row-by-row in one CSV: the first non-empty value is used as the document identifier; rows with different values produce a warning (all rows still bind to that single document).
- In OpenSALT CSVs, `Is Child Of` carries the parent item's Identifier (the same role as `parentIdentifier` in the custom format).
- Header names are case-insensitive (`Full Statement` = `full statement` = `FULL STATEMENT`).

## Simple format

A minimal-header (or no-header) format for easy first imports.
The first non-metadata line used for format detection is **not** treated as a header — it is processed as the first data row (the custom and OpenSALT formats consume their header rows; the simple format does not).

### Column interpretation (positional)

| Column | Interpretation |
|--------|---------------|
| 1 | fullStatement |
| 2 (optional) | humanCodingScheme |
| 3 (optional) | CFItemType |
| 4 (optional) | educationLevel (comma-separated) |

### Hierarchy

Depth is decided from the leading indentation of `fullStatement`:
- No indent → depth 0 (root).
- 2 spaces or 1 tab → depth 1.
- 4 spaces or 2 tabs → depth 2.
- And so on.
- **Mixed tabs and spaces**: per-row, by leading whitespace. Tabs expand to 2 spaces before depth is computed (e.g., `\t  ` = depth 2). Mixed tab and space lines in the same file are accepted.

```csv
Japanese
  Modern Japanese
    Items on the characteristics and use of language
    Items on speaking and listening
  Language Culture
    Items on our country's language culture
Geography & History
  Geography (general)
```

### Indent and storage of `fullStatement`

Indentation (leading whitespace) in the simple format is used **only for hierarchy** and is **not stored** in `fullStatement`. Processing order: parse indent (compute depth) → trim leading/trailing whitespace → store the trimmed value. Example: `"  Modern Japanese"` → depth=1, fullStatement=`"Modern Japanese"`.

### Constraints

- Identifiers are always auto-generated.
- `parentIdentifier` cannot be specified (the hierarchy is implicit from indent).
- A `#title` metadata row, or `--doc-title` on the CLI, is required (otherwise an error). On update with `--doc`, this can be omitted (the existing title is kept).
- **Upsert limitation**: because Identifiers are auto-generated, re-importing with `--doc` cannot upsert by Identifier match. If column 2 (`humanCodingScheme`) is populated, rows match existing items by `humanCodingScheme` within the document. With neither, every import creates new items (no way to bind to existing ones).

## Rubric CSV format

A CSV dedicated to rubrics (CFRubric / CFRubricCriterion / CFRubricCriterionLevel). Independent of the item CSV; used by the `import csv-rubric` / `export csv-rubric` commands.

### Columns

| Header | Description |
|--------|-------------|
| Type | Row type: `Rubric`, `Criterion`, or `Level` (case-insensitive) |
| Identifier | UUID. Blank → auto-generated UUID v4 |
| RubricIdentifier | On a Criterion row, specifies the parent rubric. Blank → uses the most recent Rubric row |
| CriterionIdentifier | On a Level row, specifies the parent criterion. Blank → uses the most recent Criterion row |
| Title | Rubric title (Rubric rows only) |
| Description | Description text |
| Category | Criterion category (Criterion rows only) |
| Weight | Criterion weight, float (Criterion rows only) |
| Position | Display order (integer) |
| Quality | Level quality label (Level rows only) |
| Score | Level score, float (Level rows only) |
| Feedback | Level feedback text (Level rows only) |
| CFItemIdentifier | UUID of the CFItem associated with the criterion (Criterion rows only) |

### Example

```csv
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,aabbcc01-0000-0000-0000-000000000001,,,Writing Rubric,Evaluates writing skills,,,,,,,
Criterion,aabbcc02-0000-0000-0000-000000000001,aabbcc01-0000-0000-0000-000000000001,,,,Organization,0.3,1,,,,aabbcc05-0000-0000-0000-000000000001
Level,aabbcc03-0000-0000-0000-000000000001,,aabbcc02-0000-0000-0000-000000000001,,Well organized,,,,1,Excellent,4.0,Great structure,
Level,aabbcc04-0000-0000-0000-000000000001,,aabbcc02-0000-0000-0000-000000000001,,Mostly organized,,,,2,Good,3.0,Room for improvement,
```

### Row type vs. column applicability

| Column | Rubric | Criterion | Level |
|--------|--------|-----------|-------|
| Type | yes | yes | yes |
| Identifier | yes | yes | yes |
| RubricIdentifier | — | yes (parent) | — |
| CriterionIdentifier | — | — | yes (parent) |
| Title | yes | — | — |
| Description | yes | yes | yes |
| Category | — | yes | — |
| Weight | — | yes | — |
| Position | — | yes | yes |
| Quality | — | — | yes |
| Score | — | — | yes |
| Feedback | — | — | yes |
| CFItemIdentifier | — | yes | — |

### Positional context (implicit parent resolution)

Rows are processed top-down. When a Criterion row has an empty `RubricIdentifier`, the most recently processed Rubric row's Identifier is used as the parent. When a Level row has an empty `CriterionIdentifier`, the most recently processed Criterion row's Identifier is used. This lets you list multiple criteria under one rubric and multiple levels under one criterion without repeating parent IDs.

## Common rules

### Encoding
- UTF-8 (with or without BOM).
- Line endings: CR+LF and LF both accepted.

### CSV syntax
- Delimiter: comma `,`.
- Quote: double-quote `"` (required when a field contains a comma or newline).
- RFC 4180 compliant.

### Unknown columns
- Header columns not defined in the format are silently ignored (no warning).
- In the simple format, columns 5+ are ignored. Rows with fewer than 4 columns treat the missing columns as empty (e.g., a single-column row sets only `fullStatement`; `humanCodingScheme` / `CFItemType` / `educationLevel` are empty).

### Empty lines / whitespace
- Empty lines are skipped.
- Rows where all columns are empty are skipped.
- Rows where `fullStatement` is empty are skipped (a warning is logged).
- Whitespace-only `fullStatement` is also treated as empty (trim first). **Simple format**: depth is computed from leading whitespace **before** trimming (parse indent → trim → empty check; trimming first would lose the indent).

---

# CSVフォーマット仕様（日本語）

## フォーマット概要

3種類のCSVフォーマットをサポートする。インポート時は自動判定、エクスポート時は `--format` で選択。

| フォーマット | インポート | エクスポート | 用途 |
|-------------|-----------|------------|------|
| 独自形式 | ○ | ○ (デフォルト) | UUID付き。編集後のre-importでupsert可能 |
| OpenSALT形式 | ○ | ○ (`--format opensalt`) | OpenSALTからの移行 |
| 簡易形式 | ○ | - | ヘッダー最小。初回インポート向け |

## フォーマット自動判定ロジック

ヘッダー行（1行目、または `#` メタデータ行の直後の非空行）の列名で判定する。メタデータ行とヘッダー行の間に空行がある場合は共通ルールの空行スキップが適用される。**列名の大文字小文字は区別しない**（全フォーマット共通）:

1. **独自形式**: ヘッダーに `Identifier` と `fullStatement` の両方が存在
2. **OpenSALT形式**: ヘッダーに `Is Child Of` または `Is Part Of` が存在、もしくは `Full Statement` が存在（OpenSALT互換ヘッダー）
3. **簡易形式**: 上記に該当しない場合。先頭列を `fullStatement` として扱う

**注意**: ルール3は全ての残りケースをキャッチするため、独自形式の列名を一部のみ含むCSV（例: `fullStatement` はあるが `Identifier` がない）も簡易形式にフォールバックする。簡易形式はポジションベースのため、名前ベースの列マッピングは行われない。意図しないフォーマット判定を避けるため、独自形式では `Identifier` 列を必ず含めること（全行空でもよい）。

**空ファイル・データ行なしの扱い**: ファイルが空（0行）、またはメタデータ行のみでデータ行がない場合は、フォーマット判定に必要なヘッダー行が存在しない。この場合は**簡易形式として扱い**（ルール3のフォールバック）、データ行 0 件として処理を続行する。結果として空のドキュメントが作成される（新規作成時）、または既存ドキュメントの isChildOf が全削除される（更新時）。

## メタデータ行

CSVファイルの先頭に `#` で始まるメタデータ行を配置できる（任意）。全フォーマット共通。

```csv
#title,高等学校学習指導要領
#version,1.0
#creator,文部科学省
#publisher,文部科学省
#description,高等学校学習指導要領（平成30年告示）
#language,ja
#adoption_status,Adopted
#official_source_url,https://www.mext.go.jp/...
#license,CC BY 4.0
#status_start_date,2018-03-30
#status_end_date,2028-03-31
#subject,国語,地理歴史,公民
```

- `#title`: CFDocumentのタイトル。CLI `--doc-title` が指定されている場合はCLI引数を優先
- `#version`: CFDocumentのバージョン。CLI `--doc-version` が指定されている場合はCLI引数を優先
- `#subject`: 教科・科目。カンマ区切りで複数指定可（例: `#subject,国語,地理歴史`）。cf_subject lookup を自動生成。各値の前後空白をトリムし、トリム後の空文字列はフィルタする（例: `#subject,国語,,地理歴史` → `["国語", "地理歴史"]`）
- `#license`: ライセンス名（例: `CC BY 4.0`）。cf_license lookup を自動生成し、CFDocument の `cf_license_id` に FK で紐づける。CFItemType と同じ title ベースの lookup パターン
- その他 (`#creator`, `#publisher`, `#description`, `#language`, `#adoption_status`, `#official_source_url`, `#status_start_date`, `#status_end_date`): 対応するCFDocumentフィールドにマッピング。これらは**単一値フィールド**であり、CSVパース後の2番目のフィールドのみを値として使用する（3番目以降のフィールドは無視）。値にカンマを含める場合はダブルクォートで囲むこと（例: `#description,"情報I, 情報II向け"`）。`#status_start_date` / `#status_end_date` は `YYYY-MM-DD` 形式
- メタデータ行はヘッダー行より前に配置すること。ヘッダー行の後に `#` で始まる行があっても、メタデータとしては処理されずデータ行として扱われる（独自形式の場合、先頭列 `Identifier` として解釈されるため UUID バリデーションで行スキップとなる）
- 同一キーが複数回出現した場合: 最後の行の値で上書きする（警告ログを出力する: 「Duplicate metadata key '#xxx', overwriting previous value」）。`#subject` も同様（結合ではなく上書き）
- 未知のキーは無視（警告「Unknown metadata key '#xxx', ignored」を出力）

## 独自形式

### 列定義

| 列名 | 必須 | 説明 |
|------|------|------|
| Identifier | - | UUID。空の場合はUUID v4を自動採番 |
| fullStatement | ○ | 項目の全文テキスト |
| humanCodingScheme | - | 人間可読なコード（例: "A-1-2"） |
| parentIdentifier | - | 親アイテムのIdentifier (UUID)。空 = ドキュメント直下 |
| sequenceNumber | - | 同一親内の表示順序。空 = 出現順に自動採番 (10, 20, 30...) |
| CFItemType | - | アイテム種別の名前（例: "知識及び技能"）。lookup自動生成 |
| educationLevel | - | 教育段階。カンマ区切り（例: "09,10,11,12"） |
| conceptKeywords | - | キーワード。カンマ区切り（例: "分析,評価"） |
| abbreviatedStatement | - | 短縮表記 |
| language | - | 言語コード（例: "ja"）。空 = ドキュメントのlanguageを継承 |
| listEnumeration | - | 列挙番号テキスト |
| license | - | ライセンス名（例: "CC BY 4.0"）。lookup自動生成 |
| statusStartDate | - | ステータス開始日（YYYY-MM-DD形式） |
| statusEndDate | - | ステータス終了日（YYYY-MM-DD形式） |

### 例

```csv
#title,高等学校学習指導要領
#language,ja
Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType,educationLevel,conceptKeywords
,国語,,,,教科,,
,現代の国語,,,10,科目,,
,言葉の特徴や使い方に関する事項,A-1,,10,知識及び技能,"10,11,12",言葉
a1b2c3d4-...,実社会に必要な国語の知識や技能を身に付けるようにする。,A-1-(1),<親のUUID>,10,,,
```

### 階層構造の表現

`parentIdentifier` 列で親子関係を明示する:
- 空（または未指定） → ドキュメント直下（ルートレベル、depth=0）
- UUIDを指定 → そのIdentifierを持つアイテムの子
- 同一CSV内の前方参照・後方参照いずれも可能（2パスで解決する）
- 存在しないUUID → 警告を出力し、ドキュメント直下として扱う

## OpenSALT形式

OpenSALTのCSVインポートとの相互運用を意図した形式。ただし完全互換ではない（差異の詳細は [reference/opensalt-csv-format.md](../reference/opensalt-csv-format.md) を参照）。

### 列定義

| 列名 | 対応する内部フィールド |
|------|---------------------|
| Identifier | Identifier |
| Full Statement | fullStatement |
| Human Coding Scheme | humanCodingScheme |
| Abbreviated Statement | abbreviatedStatement |
| Concept Keywords | conceptKeywords（カンマ区切り） |
| Education Level | educationLevel（カンマ区切り） |
| CF Item Type | CFItemType |
| Language | language |
| License | （無視。CFDocumentレベルで管理） |
| Is Child Of | parentIdentifier（親のIdentifier） |
| Sequence Number | sequenceNumber |
| Is Part Of | CFDocument identifier（下記注意事項参照） |

### 例

```csv
Identifier,Full Statement,Human Coding Scheme,Abbreviated Statement,Concept Keywords,Education Level,CF Item Type,Language,License,Is Child Of,Sequence Number,Is Part Of
d86774f2-...,国語,,,,,教科,ja,,,,a1b2c3d4-...
e97885g3-...,現代の国語,,,,,科目,ja,,d86774f2-...,10,a1b2c3d4-...
```

### OpenSALT形式の注意事項

- `Is Part Of` 列の処理:
  - `--doc` が指定されている場合: `Is Part Of` の値は**無視**し、`--doc` で指定されたドキュメントに紐づける
  - `--doc` が未指定かつ `Is Part Of` が非空の場合: その値を CFDocument identifier として同一テナント内で検索し、存在すればそのドキュメントを更新対象とする。存在しなければ新規 CFDocument を作成し、その `identifier` として使用する
  - `--doc` が未指定かつ `Is Part Of` が空の場合: メタデータの `#title` または CLI `--doc-title` で新規ドキュメントを作成する
  - CSV内で行ごとに `Is Part Of` が異なる場合: 最初の非空値をドキュメント identifier として採用し、異なる値の行は警告を出力する（全行を同一ドキュメントに紐づける）
- OpenSALTのCSVは `Is Child Of` に親アイテムのIdentifierが入る（独自形式の `parentIdentifier` と同義）
- ヘッダー名の大文字小文字は区別しない（`Full Statement` = `full statement` = `FULL STATEMENT`）

## 簡易形式

ヘッダーなし or 最小ヘッダーでの簡易インポート。初回データ投入を簡単にするための形式。
フォーマット判定に使った最初の非メタデータ行はヘッダーとして**スキップせず、そのまま最初のデータ行として処理する**（独自形式・OpenSALT形式ではヘッダー行をスキップするが、簡易形式ではスキップしない）。

### 列の解釈（位置ベース）

| 列位置 | 解釈 |
|--------|------|
| 1列目 | fullStatement |
| 2列目（任意） | humanCodingScheme |
| 3列目（任意） | CFItemType |
| 4列目（任意） | educationLevel（カンマ区切り） |

### 階層の表現

fullStatement の先頭のインデントで階層を判定する:
- インデントなし → depth 0（ルート直下）
- 半角スペース2つ or タブ1つ → depth 1
- 半角スペース4つ or タブ2つ → depth 2
- 以降同様
- **タブとスペースの混在**: 行ごとに先頭の空白文字で判定する。タブはスペース2つに展開してから depth を計算する（例: タブ1つ+スペース2つ = depth 2）。ファイル内でタブ行とスペース行が混在しても許容する

```csv
国語
  現代の国語
    言葉の特徴や使い方に関する事項
    話すこと・聞くことに関する事項
  言語文化
    我が国の言語文化に関する事項
地理歴史
  地理総合
```

### インデントと fullStatement の保存

簡易形式のインデント（先頭の空白）は階層判定のみに使用し、fullStatement には**含めずに保存する**。処理順序: インデント解析（depth 算出）→ 先頭・末尾の空白をトリム → トリム後の値を fullStatement として保存。例: `"  現代の国語"` → depth=1, fullStatement=`"現代の国語"`。

### 簡易形式の制約

- Identifier は全て自動採番
- parentIdentifier は指定不可（インデントで暗黙的に決定）
- `#title` メタデータ行、または CLI `--doc-title` が必須（なければエラー）。ただし `--doc` 指定の更新時は省略可（既存タイトルを保持）
- **upsert の制約**: Identifier が自動採番のため、`--doc` 指定で再インポートしても Identifier 一致による更新はできない。2列目（humanCodingScheme）が指定されていれば同一ドキュメント内の humanCodingScheme 一致で更新される。humanCodingScheme も空の場合は毎回新規作成となる（既存アイテムとの紐づけ手段がないため）

## ルーブリックCSV形式

ルーブリック（CFRubric / CFRubricCriterion / CFRubricCriterionLevel）専用のCSV形式。アイテムCSVとは独立したフォーマットであり、`import csv-rubric` / `export csv-rubric` コマンドで使用する。

### 列定義

| 列名 | 説明 |
|------|------|
| Type | 行タイプ: `Rubric`, `Criterion`, `Level` のいずれか（大文字小文字不問） |
| Identifier | UUID。空の場合は UUID v4 を自動採番 |
| RubricIdentifier | Criterion行で親ルーブリックを指定。空の場合は直前のRubric行を使用 |
| CriterionIdentifier | Level行で親クライテリアを指定。空の場合は直前のCriterion行を使用 |
| Title | ルーブリックのタイトル（Rubric行のみ） |
| Description | 説明文 |
| Category | クライテリアのカテゴリ（Criterion行のみ） |
| Weight | クライテリアの重み（浮動小数点、Criterion行のみ） |
| Position | 表示順序（整数） |
| Quality | レベルの品質ラベル（Level行のみ） |
| Score | レベルのスコア（浮動小数点、Level行のみ） |
| Feedback | レベルのフィードバック文（Level行のみ） |
| CFItemIdentifier | クライテリアに紐づくCFItemのUUID（Criterion行のみ） |

### 例

```csv
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,aabbcc01-0000-0000-0000-000000000001,,,Writing Rubric,Evaluates writing skills,,,,,,,
Criterion,aabbcc02-0000-0000-0000-000000000001,aabbcc01-0000-0000-0000-000000000001,,,,Organization,0.3,1,,,,aabbcc05-0000-0000-0000-000000000001
Level,aabbcc03-0000-0000-0000-000000000001,,aabbcc02-0000-0000-0000-000000000001,,Well organized,,,,1,Excellent,4.0,Great structure,
Level,aabbcc04-0000-0000-0000-000000000001,,aabbcc02-0000-0000-0000-000000000001,,Mostly organized,,,,2,Good,3.0,Room for improvement,
```

### 行タイプと列の使い分け

| 列 | Rubric | Criterion | Level |
|----|--------|-----------|-------|
| Type | ○ | ○ | ○ |
| Identifier | ○ | ○ | ○ |
| RubricIdentifier | - | ○（親指定） | - |
| CriterionIdentifier | - | - | ○（親指定） |
| Title | ○ | - | - |
| Description | ○ | ○ | ○ |
| Category | - | ○ | - |
| Weight | - | ○ | - |
| Position | - | ○ | ○ |
| Quality | - | - | ○ |
| Score | - | - | ○ |
| Feedback | - | - | ○ |
| CFItemIdentifier | - | ○ | - |

### 位置コンテキスト（暗黙の親解決）

CSV行は上から順に処理される。Criterion行で `RubricIdentifier` が空の場合、直前に処理されたRubric行のIdentifierを親として使用する。Level行で `CriterionIdentifier` が空の場合、直前に処理されたCriterion行のIdentifierを親として使用する。これにより、同一ルーブリック配下の複数クライテリア、同一クライテリア配下の複数レベルを、親IDを省略して記述できる。

## 共通ルール

### エンコーディング
- UTF-8（BOM付き・BOM無し両対応）
- 改行コード: CR+LF / LF 両対応

### CSV構文
- 区切り文字: カンマ `,`
- 引用符: ダブルクォート `"`（フィールド内にカンマ・改行を含む場合は必須）
- RFC 4180 準拠

### 未知の列
- 定義されていない列名（ヘッダーに存在するが、各フォーマットの列定義にない列）は無視する（警告なし）
- 簡易形式では5列目以降は無視する。行の列数が4列未満の場合、不足する列は空として扱う（例: 1列のみの行は fullStatement のみ、humanCodingScheme・CFItemType・educationLevel は空）

### 空行・空白
- 空行はスキップ
- 全列が空の行はスキップ
- `fullStatement` が空の行はスキップ（警告ログ出力）
- `fullStatement` が空白文字のみの行も空として扱う（前後の空白をトリムしてから判定する）。**簡易形式の場合**: インデント（先頭の空白）から depth を算出した後にトリムする（インデント解析 → トリム → 空判定の順。トリムを先に行うとインデント情報が失われるため）
