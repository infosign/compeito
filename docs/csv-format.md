# CSVフォーマット仕様

## フォーマット概要

3種類のCSVフォーマットをサポートする。インポート時は自動判定、エクスポート時は `--format` で選択。

| フォーマット | インポート | エクスポート | 用途 |
|-------------|-----------|------------|------|
| 独自形式 | ○ | ○ (デフォルト) | UUID付き。編集後のre-importでupsert可能 |
| OpenSALT形式 | ○ | ○ (`--format opensalt`, Phase 2) | OpenSALTからの移行 |
| 簡易形式 | ○ | - | ヘッダー最小。初回インポート向け |

## フォーマット自動判定ロジック

ヘッダー行（1行目、または `#` メタデータ行の直後の行）の列名で判定する:

1. **独自形式**: ヘッダーに `Identifier` と `fullStatement` の両方が存在
2. **OpenSALT形式**: ヘッダーに `CASE Item Identifier` または `Full Statement` が存在（OpenSALTのCSV出力ヘッダー）
3. **簡易形式**: 上記に該当しない場合。先頭列を `fullStatement` として扱う

判定不能な場合はエラー終了（「CSVフォーマットを自動判定できません」）。

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
#subject,国語,地理歴史,公民
```

- `#title`: CFDocumentのタイトル。CLI `--doc-title` が指定されている場合はCLI引数を優先
- `#version`: CFDocumentのバージョン。CLI `--doc-version` が指定されている場合はCLI引数を優先
- `#subject`: 教科・科目。カンマ区切りで複数指定可（例: `#subject,国語,地理歴史`）。cf_subject lookup を自動生成
- その他 (`#creator`, `#publisher`, `#description`, `#language`, `#adoption_status`, `#official_source_url`): 対応するCFDocumentフィールドにマッピング
- メタデータ行はヘッダー行より前に配置すること
- 未知のキーは無視（警告ログを出力）

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

OpenSALTのCSVエクスポートと互換性を持つ形式。

### 列定義

| 列名 | 対応する内部フィールド |
|------|---------------------|
| CASE Item Identifier | Identifier |
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
| Is Part Of | （無視。CFDocument identifierが入る） |

### 例

```csv
CASE Item Identifier,Full Statement,Human Coding Scheme,Abbreviated Statement,Concept Keywords,Education Level,CF Item Type,Language,License,Is Child Of,Sequence Number,Is Part Of
d86774f2-...,国語,,,,,教科,ja,,,,a1b2c3d4-...
e97885g3-...,現代の国語,,,,,科目,ja,,d86774f2-...,10,a1b2c3d4-...
```

### OpenSALT形式の注意事項

- `Is Part Of` 列の値はCFDocument identifierとして扱い、空の場合はCLI引数の `--doc` またはメタデータの `#title` で指定されたドキュメントに紐づける
- OpenSALTのCSVは `Is Child Of` に親アイテムのIdentifierが入る（独自形式の `parentIdentifier` と同義）
- ヘッダー名の大文字小文字は区別しない（`Full Statement` = `full statement` = `FULL STATEMENT`）

## 簡易形式

ヘッダーなし or 最小ヘッダーでの簡易インポート。初回データ投入を簡単にするための形式。

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

### 簡易形式の制約

- Identifier は全て自動採番
- parentIdentifier は指定不可（インデントで暗黙的に決定）
- `#title` メタデータ行、または CLI `--doc-title` が必須（なければエラー）

## 共通ルール

### エンコーディング
- UTF-8（BOM付き・BOM無し両対応）
- 改行コード: CR+LF / LF 両対応

### CSV構文
- 区切り文字: カンマ `,`
- 引用符: ダブルクォート `"`（フィールド内にカンマ・改行を含む場合は必須）
- RFC 4180 準拠

### 空行・空白
- 空行はスキップ
- 全列が空の行はスキップ
- `fullStatement` が空の行はスキップ（警告ログ出力）
