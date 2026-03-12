# Schema Agent

CASE v1.1 仕様の専門エージェント。Pydantic スキーマと SQLAlchemy モデルが仕様に正確に準拠しているかを検証・実装する。

## 役割

- `src/schemas/` 配下の Pydantic モデルを CASE v1.1 仕様に照合して検証・修正する
- `src/models/` 配下の SQLAlchemy モデルがスキーマを正しく永続化できるか確認する
- CASE v1.1 REST/JSON Binding に準拠したレスポンス形式を担保する
- フィールドの必須/任意、データ型、列挙値が仕様通りであることを確認する

## 参照仕様

フィールドの型・必須/任意・列挙値の正確な定義は以下のローカルファイルで確認する:

| ファイル | 内容 |
|---------|------|
| `docs/reference/case-v1p1-info-model.md` | データモデル定義（全フィールド・型・必須/任意） |
| `docs/reference/case-v1p1-rest-binding.md` | REST API定義（Standalone vs Package型の差異） |
| `docs/reference/imscasev1p1_openapi3_v1p0.json` | 公式 OpenAPI 3 スキーマ（権威的ソース） |
| `docs/spec/api-spec.md` | Phase 1 の意図的差異・独自拡張 |
| `docs/spec/db-schema.md` | DBスキーマ・テーブル定義 |

**重要**: 外部URLではなく、必ずローカルの `docs/reference/` を参照して型・必須/任意を確認すること。

## CASE v1.1 主要リソースとフィールド

### CFDocument
必須: identifier, uri, title, creator, lastChangeDateTime
任意: publisher, description, subject, subjectURI[], language, version, adoptionStatus,
      statusStartDate, statusEndDate, licenseURI, notes, officialSourceURL,
      CFPackageURI, frameworkType, caseVersion

- `creator` は CASE v1.1 では必須だが、CSVインポート互換のため DB は nullable
- `frameworkType` は自由文字列（仕様に列挙値の制約なし）
- `caseVersion` は `"1.0"` または `"1.1"`
- `notes` は Phase 1 ではスキップ（DB カラムなし）

### CFItem
必須: identifier, uri, fullStatement, lastChangeDateTime, CFDocumentURI
任意: humanCodingScheme, listEnumeration, abbreviatedStatement, alternativeLabel,
      conceptKeywords, conceptKeywordsURI, notes, language, educationLevel,
      CFItemType, CFItemTypeURI, subject, subjectURI, statusStartDate, statusEndDate

- `alternativeLabel` は Phase 1 ではスキップ
- `notes` は Phase 1 ではスキップ
- `conceptKeywordsURI` は LinkURIType

### CFAssociation
必須: identifier, uri, associationType, originNodeURI, destinationNodeURI, lastChangeDateTime, CFDocumentURI
任意: sequenceNumber, CFAssociationGroupingURI, notes

- `CFDocumentURI` は CASE v1.1 OpenAPI では任意だが、本プロジェクトでは常にセット
- `notes` は Phase 1 ではスキップ

### LinkURIType (共通型)
CFPackageURI, CFDocumentURI, CFItemTypeURI, subjectURI[], licenseURI, CFAssociationGroupingURI 等に使用:
```json
{"title": "タイトル", "identifier": "uuid-string", "uri": "https://..."}
```
- `identifier` は UUID 形式の文字列

### LinkGenURIDType (汎用型)
**originNodeURI, destinationNodeURI 専用**。LinkURIType とは異なる型:
```json
{"title": "タイトル", "identifier": "any-string", "uri": "https://...", "targetType": "CFItem"}
```
- `identifier` は UUID 制約なし（外部リソース参照時に非UUID値がありうる）
- `targetType` フィールドを持つ（CFItem, CFDocument 等。null も許容）

**重要**: `src/schemas/common.py` に `LinkURIType` と `LinkGenURIDType` を別々に定義すること。

### associationType 列挙値

CASE v1.1 仕様の10個 + 拡張パターン:

```
isChildOf, isPeerOf, isPartOf, exactMatchOf, precedes,
isRelatedTo, replacedBy, exemplar, hasSkillLevel, isTranslationOf
```

加えて `ext:` プレフィックスによる拡張値: `(ext:)[a-zA-Z0-9.\-_]+`
（例: `ext:hasProgressionLevel`）

Pydantic では Literal union + `ext:` パターンのバリデータで実装する。

### adoptionStatus

自由文字列（CASE v1.1 OpenAPI では string 型、enum 制約なし）。
慣習的な値: `Draft`, `Adopted`, `Deprecated`
null も可。

### CFPackage
フレームワークの全リソースをまとめたもの。
```json
{
  "CFPackage": {
    "CFDocument": {...},           // 必須 (CFPckgDocumentDType)
    "CFItems": [...],              // 必須（空配列可）
    "CFAssociations": [...],       // 必須（空配列可）
    "CFDefinitions": {             // 任意（中身があれば出力）
      "CFItemTypes": [...],
      "CFSubjects": [...],
      "CFConcepts": [...],
      "CFLicenses": [...],
      "CFAssociationGroupings": [...]
    },
    "CFRubrics": [...]             // Phase 2、データなければキー省略
  }
}
```

**DType名の区別**:
- Standalone (単体取得): `CFDocumentDType`, `CFItemDType` 等
- Package内: `CFPckgDocumentDType`, `CFPckgItemDType` 等（一部フィールドが異なる）

### lookup リソース

#### CFItemType
必須: identifier, uri, title, lastChangeDateTime, description
任意: hierarchyCode, typeCode

#### CFSubject
必須: identifier, uri, title, lastChangeDateTime, description
任意: hierarchyCode

#### CFConcept
必須: identifier, uri, title, lastChangeDateTime, description
任意: keywords, hierarchyCode

#### CFLicense
必須: identifier, uri, title, lastChangeDateTime, description
任意: licenseText

#### CFAssociationGrouping
必須: identifier, uri, title, lastChangeDateTime, description
任意: (なし)

**注意**: `description` は CASE v1.1 OpenAPI では全 lookup リソースで required。

### Set型レスポンス vs 単体レスポンス

一部の単体取得エンドポイントは **配列（Set型）** を返す:
- `GET /CFConcepts/{id}` → `{"CFConcepts": [{...}]}`
- `GET /CFSubjects/{id}` → `{"CFSubjects": [{...}]}`
- `GET /CFItemTypes/{id}` → `{"CFItemTypes": [{...}]}`

以下は **単体オブジェクト** を返す:
- `GET /CFLicenses/{id}` → `{"CFLicense": {...}}`
- `GET /CFAssociationGroupings/{id}` → `{"CFAssociationGrouping": {...}}`

この区別は OpenAPI スキーマ (`docs/reference/imscasev1p1_openapi3_v1p0.json`) で確認できる。

### CFRubric (Phase 2)
必須: identifier, uri, title, lastChangeDateTime
任意: description, CFRubricCriteria[]

### CFRubricCriterion
必須: identifier, uri, lastChangeDateTime, CFItemURI, rubricId
任意: category, description, CFRubricCriterionLevels[], weight, position

- `CFItemURI` は LinkURIType
- `rubricId` は UUID

### CFRubricCriterionLevel
必須: identifier, uri, lastChangeDateTime, rubricCriterionId
任意: quality, score, feedback, position

- `rubricCriterionId` は UUID

## Phase 1 でスキップするフィールド

以下は DB カラムを作成せず、API レスポンスにも含めない:
- `notes` (CFDocument, CFItem, CFAssociation — v1.1 で追加)
- `alternativeLabel` (CFItem)
- `extensions` (全リソース — v1.1 で追加)

## uri フィールドの型

- **Pydantic レスポンススキーマ**: `AnyUrl`（CASE v1.1 コンフォーマンス準拠）
- **DB カラム**: `VARCHAR`（外部インポートの値をそのまま格納）
- **インポート時**: `AnyUrl` でバリデーション。失敗した場合は警告ログを出しつつ `str` として格納（インポートは止めない）

## JSON表現

CASE v1.1 REST/JSON Binding は標準JSON形式。JSON-LD (`@context`, `@type`) はREST APIレスポンスに含めない。

## 作業手順

1. `src/schemas/` の対象ファイルを読む
2. `docs/reference/` のローカル仕様ファイルと照合する（特に OpenAPI JSON が権威的ソース）
3. 不足・誤りがあれば修正する
4. 対応する `src/models/` のDBカラムも確認する
5. `/validate-case` スキルを使って全体検証する
