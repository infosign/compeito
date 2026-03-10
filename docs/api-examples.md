# APIリクエスト/レスポンス例

全レスポンスはルートレベルに直接配置する（ラッパーなし）。
テナントUUID `550e8400-e29b-41d4-a716-446655440000` を例として使用。

## CFDocuments

### GET /{tenant}/ims/case/v1p1/CFDocuments

一覧取得。ページネーション対応。

**リクエスト:**
```
GET /550e8400-e29b-41d4-a716-446655440000/ims/case/v1p1/CFDocuments?limit=10&offset=0
```

**レスポンス (200):**
```json
{
  "CFDocuments": [
    {
      "identifier": "d86774f2-1234-5678-9abc-def012345678",
      "uri": "https://case.example.com/550e8400-e29b-41d4-a716-446655440000/uri/d86774f2-1234-5678-9abc-def012345678",
      "title": "高等学校学習指導要領",
      "creator": "文部科学省",
      "publisher": "文部科学省",
      "description": "高等学校学習指導要領（平成30年告示）",
      "language": "ja",
      "version": "1.0",
      "adoptionStatus": "Adopted",
      "statusStartDate": "2018-03-30",
      "statusEndDate": null,
      "licenseURI": null,
      "officialSourceURL": "https://www.mext.go.jp/...",
      "subject": ["国語", "地理歴史", "公民"],
      "subjectURI": [
        {"title": "国語", "identifier": "aaa-...", "uri": "https://..."},
        {"title": "地理歴史", "identifier": "bbb-...", "uri": "https://..."},
        {"title": "公民", "identifier": "ccc-sub-...", "uri": "https://..."}
      ],
      "CFPackageURI": {
        "title": "高等学校学習指導要領",
        "identifier": "d86774f2-1234-5678-9abc-def012345678",
        "uri": "https://case.example.com/550e8400-.../ims/case/v1p1/CFPackages/d86774f2-1234-5678-9abc-def012345678"
      },
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    }
  ]
}
```

### GET /{tenant}/ims/case/v1p1/CFDocuments/{id}

**レスポンス (200):**
```json
{
  "CFDocument": {
    "identifier": "d86774f2-1234-5678-9abc-def012345678",
    "uri": "https://case.example.com/550e8400-.../uri/d86774f2-1234-5678-9abc-def012345678",
    "title": "高等学校学習指導要領",
    "creator": "文部科学省",
    "publisher": "文部科学省",
    "description": "高等学校学習指導要領（平成30年告示）",
    "language": "ja",
    "version": "1.0",
    "adoptionStatus": "Adopted",
    "statusStartDate": "2018-03-30",
    "statusEndDate": null,
    "licenseURI": null,
    "officialSourceURL": "https://www.mext.go.jp/...",
    "subject": ["国語", "地理歴史", "公民"],
    "subjectURI": [
      {"title": "国語", "identifier": "aaa-...", "uri": "https://..."},
      {"title": "地理歴史", "identifier": "bbb-...", "uri": "https://..."},
      {"title": "公民", "identifier": "ccc-sub-...", "uri": "https://..."}
    ],
    "CFPackageURI": {
      "title": "高等学校学習指導要領",
      "identifier": "d86774f2-1234-5678-9abc-def012345678",
      "uri": "https://case.example.com/550e8400-.../ims/case/v1p1/CFPackages/d86774f2-1234-5678-9abc-def012345678"
    },
    "lastChangeDateTime": "2025-10-08T12:00:00Z"
  }
}
```

null 許容フィールドは全てレスポンスに含める（Pydantic の `exclude_none=False`）。一覧エンドポイントと単一取得エンドポイントで同一のスキーマ・同一のフィールドセットを返す。
`CFPackageURI` は必須フィールドであり、常に含めなければならない。

## CFItems

### GET /{tenant}/ims/case/v1p1/CFItems/{id}

**レスポンス (200):**
```json
{
  "CFItem": {
    "identifier": "e97885g3-2345-6789-abcd-ef0123456789",
    "uri": "https://case.example.com/550e8400-.../uri/e97885g3-2345-6789-abcd-ef0123456789",
    "fullStatement": "実社会に必要な国語の知識や技能を身に付けるようにする。",
    "humanCodingScheme": "A-1-(1)",
    "abbreviatedStatement": null,
    "conceptKeywords": ["言葉", "国語"],
    "conceptKeywordsURI": {"title": "言語能力", "identifier": "ccc-concept-...", "uri": "https://..."},
    "educationLevel": ["10", "11", "12"],
    "subject": null,
    "subjectURI": null,
    "CFItemType": "知識及び技能",
    "CFItemTypeURI": {
      "title": "知識及び技能",
      "identifier": "fff-...",
      "uri": "https://case.example.com/550e8400-.../uri/fff-..."
    },
    "language": "ja",
    "licenseURI": null,
    "statusStartDate": null,
    "statusEndDate": null,
    "listEnumeration": "1",
    "CFDocumentURI": {
      "title": "高等学校学習指導要領",
      "identifier": "d86774f2-1234-5678-9abc-def012345678",
      "uri": "https://case.example.com/550e8400-.../uri/d86774f2-1234-5678-9abc-def012345678"
    },
    "lastChangeDateTime": "2025-10-08T12:00:00Z"
  }
}
```

## CFAssociations

### GET /{tenant}/ims/case/v1p1/CFItemAssociations/{id}

対象アイテムと、そのアイテムに関連する全Association（origin/destination両方向）を返す。
CASE v1.1 の CFAssociationSetDType 形式。CFAssociations 内の各 Association は CFDocumentURI を含まない（CFPckgAssociationDType）。

**レスポンス (200):**
```json
{
  "CFItem": {
    "identifier": "e97885g3-2345-6789-abcd-ef0123456789",
    "uri": "https://case.example.com/550e8400-.../uri/e97885g3-...",
    "fullStatement": "実社会に必要な国語の知識や技能を身に付けるようにする。",
    "humanCodingScheme": "A-1-(1)",
    "abbreviatedStatement": null,
    "conceptKeywords": ["言葉", "国語"],
    "conceptKeywordsURI": null,
    "educationLevel": ["10", "11", "12"],
    "subject": null,
    "subjectURI": null,
    "CFItemType": "知識及び技能",
    "CFItemTypeURI": {"title": "知識及び技能", "identifier": "fff-...", "uri": "https://..."},
    "language": "ja",
    "licenseURI": null,
    "statusStartDate": null,
    "statusEndDate": null,
    "listEnumeration": "1",
    "CFDocumentURI": {"title": "高等学校学習指導要領", "identifier": "d86774f2-...", "uri": "https://..."},
    "lastChangeDateTime": "2025-10-08T12:00:00Z"
  },
  "CFAssociations": [
    {
      "identifier": "aaa11111-1111-1111-1111-111111111111",
      "uri": "https://case.example.com/550e8400-.../uri/aaa11111-1111-1111-1111-111111111111",
      "associationType": "isChildOf",
      "originNodeURI": {
        "title": "実社会に必要な国語の知識や技能を...",
        "identifier": "e97885g3-2345-6789-abcd-ef0123456789",
        "uri": "https://case.example.com/550e8400-.../uri/e97885g3-..."
      },
      "destinationNodeURI": {
        "title": "言葉の特徴や使い方に関する事項",
        "identifier": "f08896h4-3456-7890-bcde-f01234567890",
        "uri": "https://case.example.com/550e8400-.../uri/f08896h4-..."
      },
      "sequenceNumber": 10,
      "CFAssociationGroupingURI": null,
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    }
  ]
}
```

### GET /{tenant}/ims/case/v1p1/CFAssociations/{id}

**レスポンス (200):**
```json
{
  "CFAssociation": {
    "identifier": "aaa11111-1111-1111-1111-111111111111",
    "uri": "https://case.example.com/550e8400-.../uri/aaa11111-1111-1111-1111-111111111111",
    "associationType": "isChildOf",
    "originNodeURI": {
      "title": "実社会に必要な国語の知識や技能を...",
      "identifier": "e97885g3-...",
      "uri": "https://..."
    },
    "destinationNodeURI": {
      "title": "言葉の特徴や使い方に関する事項",
      "identifier": "f08896h4-...",
      "uri": "https://..."
    },
    "sequenceNumber": 10,
    "CFAssociationGroupingURI": null,
    "CFDocumentURI": {
      "title": "高等学校学習指導要領",
      "identifier": "d86774f2-...",
      "uri": "https://..."
    },
    "lastChangeDateTime": "2025-10-08T12:00:00Z"
  }
}
```

**CFAssociationGroupingURI が非 null の場合:**
```json
{
  "CFAssociationGroupingURI": {
    "title": "教科間関連",
    "identifier": "ggg11111-1111-1111-1111-111111111111",
    "uri": "https://case.example.com/550e8400-.../uri/ggg11111-1111-1111-1111-111111111111"
  }
}
```

## CFPackages

### GET /{tenant}/ims/case/v1p1/CFPackages/{id}

ドキュメント配下の全リソースを一括取得。

**レスポンス (200):**
```json
{
  "CFPackage": {
    "CFDocument": {
      "identifier": "d86774f2-...",
      "uri": "https://...",
      "title": "高等学校学習指導要領",
      "creator": "文部科学省",
      "publisher": "文部科学省",
      "description": "高等学校学習指導要領（平成30年告示）",
      "language": "ja",
      "version": "1.0",
      "adoptionStatus": "Adopted",
      "statusStartDate": "2018-03-30",
      "statusEndDate": null,
      "licenseURI": null,
      "officialSourceURL": "https://www.mext.go.jp/...",
      "subject": ["国語", "地理歴史", "公民"],
      "subjectURI": [
        {"title": "国語", "identifier": "aaa-...", "uri": "https://..."},
        {"title": "地理歴史", "identifier": "bbb-...", "uri": "https://..."},
        {"title": "公民", "identifier": "ccc-sub-...", "uri": "https://..."}
      ],
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    },
    "CFItems": [
      {
        "identifier": "e97885g3-...",
        "uri": "https://case.example.com/550e8400-.../uri/e97885g3-...",
        "fullStatement": "国語",
        "humanCodingScheme": "A",
        "abbreviatedStatement": null,
        "conceptKeywords": null,
        "conceptKeywordsURI": null,
        "educationLevel": ["10", "11", "12"],
        "subject": null,
        "subjectURI": null,
        "CFItemType": "知識及び技能",
        "CFItemTypeURI": {"title": "知識及び技能", "identifier": "fff-...", "uri": "https://..."},
        "language": "ja",
        "licenseURI": null,
        "statusStartDate": null,
        "statusEndDate": null,
        "listEnumeration": null,
        "lastChangeDateTime": "2025-10-08T12:00:00Z"
      }
    ],
    "CFAssociations": [
      {
        "identifier": "aaa11111-...",
        "uri": "https://case.example.com/550e8400-.../uri/aaa11111-...",
        "associationType": "isChildOf",
        "originNodeURI": {"title": "国語", "identifier": "e97885g3-...", "uri": "https://..."},
        "destinationNodeURI": {"title": "高等学校学習指導要領", "identifier": "d86774f2-...", "uri": "https://..."},
        "sequenceNumber": 10,
        "CFAssociationGroupingURI": null,
        "lastChangeDateTime": "2025-10-08T12:00:00Z"
      }
    ],
    "CFDefinitions": {
      "CFItemTypes": [
        {
          "identifier": "fff-...",
          "uri": "https://...",
          "title": "知識及び技能",
          "description": null,
          "typeCode": null,
          "hierarchyCode": null,
          "lastChangeDateTime": "2025-10-08T12:00:00Z"
        }
      ],
      "CFSubjects": [
        {
          "identifier": "aaa-...",
          "uri": "https://...",
          "title": "国語",
          "description": null,
          "hierarchyCode": null,
          "lastChangeDateTime": "2025-10-08T12:00:00Z"
        }
      ],
      "CFLicenses": [
        {
          "identifier": "lic11111-...",
          "uri": "https://...",
          "title": "CC BY 4.0",
          "description": null,
          "licenseText": null,
          "lastChangeDateTime": "2025-10-08T12:00:00Z"
        }
      ]
    }
  }
}
```

`CFDefinitions` 内の空の配列はキーごと省略する。
例: CFConceptsが0件なら `"CFConcepts"` キー自体を含めない。

## lookup系リソース

### GET /{tenant}/ims/case/v1p1/CFItemTypes

**レスポンス (200):**
```json
{
  "CFItemTypes": [
    {
      "identifier": "fff11111-...",
      "uri": "https://case.example.com/550e8400-.../uri/fff11111-...",
      "title": "知識及び技能",
      "description": null,
      "typeCode": null,
      "hierarchyCode": null,
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    },
    {
      "identifier": "fff22222-...",
      "uri": "https://case.example.com/550e8400-.../uri/fff22222-...",
      "title": "思考力，判断力，表現力等",
      "description": null,
      "typeCode": null,
      "hierarchyCode": null,
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    }
  ]
}
```

### GET /{tenant}/ims/case/v1p1/CFItemTypes/{id}

**レスポンス (200):**
```json
{
  "CFItemType": {
    "identifier": "fff11111-...",
    "uri": "https://case.example.com/550e8400-.../uri/fff11111-...",
    "title": "知識及び技能",
    "description": null,
    "typeCode": null,
    "hierarchyCode": null,
    "lastChangeDateTime": "2025-10-08T12:00:00Z"
  }
}
```

CFSubjects, CFConcepts, CFLicenses, CFAssociationGroupings も同じ基本構造。
ルートキー名のみ異なる（`CFSubjects`/`CFSubject`, `CFConcepts`/`CFConcept` 等）。
各リソースの固有フィールド:
- **CFSubject / CFConcept**: `hierarchyCode` (string, nullable)
- **CFLicense**: `licenseText` (string, nullable)
- **CFAssociationGrouping**: 固有フィールドなし（共通フィールドのみ）

**licenseURI が非 null の場合（CFDocument / CFItem 共通）:**
```json
{
  "licenseURI": {
    "title": "CC BY 4.0",
    "identifier": "lic11111-1111-1111-1111-111111111111",
    "uri": "https://case.example.com/550e8400-.../uri/lic11111-1111-1111-1111-111111111111"
  }
}
```

## エラーレスポンス

### 400 Bad Request — UUID形式不正

```
GET /not-a-uuid/ims/case/v1p1/CFDocuments
```

```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Invalid UUID format: 'not-a-uuid'",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {
        "imsx_codeMinorFieldName": "sourcedId",
        "imsx_codeMinorFieldValue": "invalid_uuid"
      }
    ]
  }
}
```

### 404 Not Found — リソースが存在しない

```
GET /550e8400-.../ims/case/v1p1/CFItems/99999999-9999-9999-9999-999999999999
```

```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "CFItem not found: '99999999-9999-9999-9999-999999999999'",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {
        "imsx_codeMinorFieldName": "sourcedId",
        "imsx_codeMinorFieldValue": "unknownobject"
      }
    ]
  }
}
```

### 404 Not Found — テナントが存在しない

```
GET /99999999-9999-9999-9999-999999999999/ims/case/v1p1/CFDocuments
```

```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Tenant not found: '99999999-9999-9999-9999-999999999999'",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {
        "imsx_codeMinorFieldName": "sourcedId",
        "imsx_codeMinorFieldValue": "unknownobject"
      }
    ]
  }
}
```

### 404 Not Found — /CFItemAssociations/{id} でアイテムが存在しない

```
GET /550e8400-.../ims/case/v1p1/CFItemAssociations/99999999-9999-9999-9999-999999999999
```

```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "CFItem not found: '99999999-9999-9999-9999-999999999999'",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {
        "imsx_codeMinorFieldName": "sourcedId",
        "imsx_codeMinorFieldValue": "unknownobject"
      }
    ]
  }
}
```

空配列ではなく 404 を返す（api-spec.md 参照）。

### 405 Method Not Allowed — CASE API への非GETリクエスト

```
POST /550e8400-.../ims/case/v1p1/CFDocuments
```

```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Method not allowed",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {
        "imsx_codeMinorFieldName": "sourcedId",
        "imsx_codeMinorFieldValue": "invalid_selection_field"
      }
    ]
  }
}
```

`Allow: GET` レスポンスヘッダーを含める。

### 500 Internal Server Error

```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Internal server error",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {
        "imsx_codeMinorFieldName": "sourcedId",
        "imsx_codeMinorFieldValue": "internal_server_error"
      }
    ]
  }
}
```

## ページネーション例

### バリデーションエラー — limit が負数

```
GET /550e8400-.../ims/case/v1p1/CFDocuments?limit=-1
```

```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Invalid limit: must be a non-negative integer",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {
        "imsx_codeMinorFieldName": "sourcedId",
        "imsx_codeMinorFieldValue": "invalid_selection_field"
      }
    ]
  }
}
```

`offset` 不正時も同様の形式（`imsx_description` は `"Invalid offset: must be a non-negative integer"`）。
`limit` / `offset` が整数でない場合は `"Invalid limit: must be a non-negative integer"` / `"Invalid offset: must be a non-negative integer"`。

### デフォルト（limit=100, offset=0）

```
GET /550e8400-.../ims/case/v1p1/CFDocuments
```

→ 先頭100件を返す。

### 2ページ目

```
GET /550e8400-.../ims/case/v1p1/CFDocuments?limit=50&offset=50
```

→ 51件目から50件を返す。

### 最大件数

```
GET /550e8400-.../ims/case/v1p1/CFItemAssociations/xxx?limit=500&offset=0
```

→ limit の上限は500。500を超える値を指定した場合は500として扱う。

### 結果が0件の場合

```json
{
  "CFDocuments": []
}
```

空配列を返す（エラーではない）。
