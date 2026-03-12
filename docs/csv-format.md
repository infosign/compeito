# CSVフォーマット仕様

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

OpenSALTのCSVインポートとの相互運用を意図した形式。ただし完全互換ではない（差異の詳細は [reference/opensalt-csv-format.md](reference/opensalt-csv-format.md) を参照）。

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
