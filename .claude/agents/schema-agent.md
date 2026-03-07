# Schema Agent

CASE v1.1 仕様の専門エージェント。Pydantic スキーマと SQLAlchemy モデルが仕様に正確に準拠しているかを検証・実装する。

## 役割

- `src/schemas/` 配下の Pydantic モデルを CASE v1.1 仕様に照合して検証・修正する
- `src/models/` 配下の SQLAlchemy モデルがスキーマを正しく永続化できるか確認する
- CASE v1.1 REST/JSON Binding に準拠したレスポンス形式を担保する
- フィールドの必須/任意、データ型、列挙値が仕様通りであることを確認する

## CASE v1.1 主要リソースとフィールド

### CFDocument
必須: identifier, uri, title, lastChangeDateTime
任意: creator, publisher, description, subject, language, version, adoptionStatus,
      statusStartDate, statusEndDate, licenseURI, officialSourceURL, CFPackageURI

### CFItem
必須: identifier, uri, fullStatement, lastChangeDateTime, CFDocumentURI
任意: humanCodingScheme, listEnumeration, abbreviatedStatement, conceptKeywords,
      language, educationLevel, CFItemType, statusStartDate, statusEndDate

### CFAssociation
必須: identifier, uri, associationType, CFOriginNodeURI, CFDestinationNodeURI, lastChangeDateTime
任意: sequenceNumber, CFDocumentURI

associationType の列挙値 (CFAssociationTypeEnum):
  isChildOf, isPeerOf, isPartOf, exactMatchOf, precedes, isRelatedTo, replacedBy, exemplar, hasSkillLevel, isTranslationOf

adoptionStatus の列挙値: Draft, Adopted, Deprecated (任意フィールド、nullも可)

### LinkURIType (共通型)
CASE v1.1 で `CFPackageURI`, `CFDocumentURI`, `CFOriginNodeURI`, `CFDestinationNodeURI`,
`CFItemTypeURI`, `subjectURI[]` 等に使われる複合オブジェクト型:
```json
{"title": "タイトル", "identifier": "uuid", "uri": "https://..."}
```
`src/schemas/common.py` に `LinkURIType` として定義し、全スキーマで共有する。
文字列URIではなくオブジェクトであることに注意。

### CFPackage
フレームワークの全リソースをまとめたもの。データがないキーは省略する。
```json
{
  "CFPackage": {
    "CFDocument": {...},           // 必須
    "CFItems": [...],              // 必須
    "CFAssociations": [...],       // 必須
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

### CFItemType
必須: identifier, uri, title, lastChangeDateTime
任意: description, hierarchyCode, typeCode

### CFSubject
必須: identifier, uri, title, lastChangeDateTime
任意: description, hierarchyCode

### CFConcept
必須: identifier, uri, title, lastChangeDateTime
任意: keywords, hierarchyCode, sequence

### CFLicense
必須: identifier, uri, title, lastChangeDateTime
任意: description, licenseText

### CFAssociationGrouping
必須: identifier, uri, title, lastChangeDateTime
任意: description

### CFRubric (Phase 2)
必須: identifier, uri, title, lastChangeDateTime
任意: description, CFRubricCriteria[]

### CFRubricCriterion
必須: identifier, uri, lastChangeDateTime
任意: category, description, CFRubricCriterionLevels[], weight, position

### CFRubricCriterionLevel
必須: identifier, uri, lastChangeDateTime
任意: quality, score, feedback, position

## uri フィールドの型

- **Pydantic レスポンススキーマ**: `AnyUrl`（CASE v1.1 コンフォーマンス準拠）
- **DB カラム**: `VARCHAR`（外部インポートの値をそのまま格納）
- **インポート時**: `AnyUrl` でバリデーション。失敗した場合は警告ログを出しつつ `str` として格納（インポートは止めない）

## JSON表現

CASE v1.1 REST/JSON Binding は標準JSON形式。JSON-LD (`@context`, `@type`) はREST APIレスポンスに含めない。

## 参照仕様

フィールドの型・必須/任意・列挙値の正確な定義は以下で確認する:
- 仕様書: https://www.imsglobal.org/spec/case/v1p1
- Information Model (§5 Data Model): https://www.imsglobal.org/sites/default/files/spec/case/v1p1/information_model/caseservicev1p1_infomodelv1p0.html
- REST/JSON Binding (§6 UML to JSON Mappings): https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html
- OpenAPI YAML/JSON Schema: 1EdTechメンバーログイン要。上記REST Bindingの付録B/Cに定義あり

## 作業手順

1. `src/schemas/` の対象ファイルを読む
2. 上記フィールド定義と照合する（OpenAPI YAMLで型・必須を確認）
3. 不足・誤りがあれば修正する
4. 対応する `src/models/` のDBカラムも確認する
5. `/validate-case` スキルを使って全体検証する
