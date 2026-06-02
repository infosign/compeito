# API Request / Response Examples

Every response uses the CASE v1.1 DType name as the root key (no custom wrappers such as `{"data": ...}`).
The tenant UUID `550e8400-e29b-41d4-a716-446655440000` is used as an example throughout.

## CFDocuments

### GET /{tenant}/ims/case/v1p1/CFDocuments

List documents. Pagination is supported.

**Request:**
```
GET /550e8400-e29b-41d4-a716-446655440000/ims/case/v1p1/CFDocuments?limit=10&offset=0
```

**Response (200):**
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
      "frameworkType": null,
      "caseVersion": null,
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

**Response (200):**
```json
{
  "CFDocument": {
    "identifier": "d86774f2-1234-5678-9abc-def012345678",
    "uri": "https://case.example.com/550e8400-.../uri/d86774f2-1234-5678-9abc-def012345678",
    "title": "高等学校学習指導要領",
    "creator": "文部科学省",
    "publisher": "文部科学省",
    "description": "高等学校学習指導要領（平成30年告示）",
    "frameworkType": null,
    "caseVersion": null,
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

Nullable fields are always included in the response (Pydantic `exclude_none=False`). The list and single-resource endpoints share the same schema and the same field set.
`CFPackageURI` is required and must always be included.

## CFItems

### GET /{tenant}/ims/case/v1p1/CFItems/{id}

**Response (200):**
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

Returns the target item and all associations related to it (both origin and destination directions).
This is the CASE v1.1 `CFAssociationSetDType`. Each association inside `CFAssociations` does **not** include `CFDocumentURI` (this is `CFPckgAssociationDType`).

**Response (200):**
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
        "uri": "https://case.example.com/550e8400-.../uri/e97885g3-...",
        "targetType": null
      },
      "destinationNodeURI": {
        "title": "言葉の特徴や使い方に関する事項",
        "identifier": "f08896h4-3456-7890-bcde-f01234567890",
        "uri": "https://case.example.com/550e8400-.../uri/f08896h4-...",
        "targetType": null
      },
      "sequenceNumber": 10,
      "CFAssociationGroupingURI": null,
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    }
  ]
}
```

### GET /{tenant}/ims/case/v1p1/CFAssociations/{id}

**Response (200):**
```json
{
  "CFAssociation": {
    "identifier": "aaa11111-1111-1111-1111-111111111111",
    "uri": "https://case.example.com/550e8400-.../uri/aaa11111-1111-1111-1111-111111111111",
    "associationType": "isChildOf",
    "originNodeURI": {
      "title": "実社会に必要な国語の知識や技能を...",
      "identifier": "e97885g3-...",
      "uri": "https://...",
      "targetType": null
    },
    "destinationNodeURI": {
      "title": "言葉の特徴や使い方に関する事項",
      "identifier": "f08896h4-...",
      "uri": "https://...",
      "targetType": null
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

**When `CFAssociationGroupingURI` is non-null:**
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

Fetches every resource under a document in one shot.

**Response (200):**
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
      "frameworkType": null,
      "caseVersion": null,
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
        "originNodeURI": {"title": "国語", "identifier": "e97885g3-...", "uri": "https://...", "targetType": null},
        "destinationNodeURI": {"title": "高等学校学習指導要領", "identifier": "d86774f2-...", "uri": "https://...", "targetType": null},
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

Empty arrays inside `CFDefinitions` are omitted as a key.
Example: if `CFConcepts` has 0 elements, the `"CFConcepts"` key is not included at all.

## Lookup resources

### Custom listing endpoints (outside the CASE v1.1 spec)

`GET /CFItemTypes`, `GET /CFSubjects`, `GET /CFConcepts`, `GET /CFLicenses`, and `GET /CFAssociationGroupings` return every resource within the tenant as an array, with pagination. The response shape matches the CASE v1.1 Set-type endpoints (plural root key + array).

### GET /{tenant}/ims/case/v1p1/CFItemTypes

**Response (200):**
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

CASE v1.1 returns a Set type (`CFItemTypeSetDType`). The first array element is the requested CFItemType; subsequent elements are descendants in the `hierarchyCode` hierarchy (records whose `hierarchyCode` starts with `<root>.`). When the requested resource's `hierarchyCode` is NULL or it has no descendants, only the requested resource is returned (see api-spec.md).

**Response (200):**
```json
{
  "CFItemTypes": [
    {
      "identifier": "fff11111-...",
      "uri": "https://case.example.com/550e8400-.../uri/fff11111-...",
      "title": "知識及び技能",
      "description": null,
      "typeCode": null,
      "hierarchyCode": "1",
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    },
    {
      "identifier": "fff11112-...",
      "uri": "https://case.example.com/550e8400-.../uri/fff11112-...",
      "title": "知識",
      "description": null,
      "typeCode": null,
      "hierarchyCode": "1.1",
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    }
  ]
}
```

**Set-type endpoints** (`/CFConcepts/{id}`, `/CFSubjects/{id}`, `/CFItemTypes/{id}`) use plural root keys with arrays (`{"CFConcepts": [...]}`, `{"CFSubjects": [...]}`, `{"CFItemTypes": [...]}`).
**Single-object endpoints** (`/CFLicenses/{id}`, `/CFAssociationGroupings/{id}`) use singular root keys with a single object (`{"CFLicense": {...}}`, `{"CFAssociationGrouping": {...}}`).
CFLicenses and CFAssociationGroupings share the same structure (singular key, single object).
Common fields across all lookup resources: `identifier`, `uri`, `title`, `description` (nullable), `lastChangeDateTime`.
Resource-specific fields:
- **CFItemType**: `typeCode` (string, nullable), `hierarchyCode` (string, nullable)
- **CFSubject**: `hierarchyCode` (string, nullable)
- **CFConcept**: `keywords` (string, nullable, pipe-delimited), `hierarchyCode` (string, nullable)
- **CFLicense**: `licenseText` (string, nullable)
- **CFAssociationGrouping**: no specific fields (common fields only)

**Note**: in CASE v1.1, `description` (CFItemType), `hierarchyCode` (CFItemType / CFSubject / CFConcept), and `licenseText` (CFLicense) are defined as required (non-nullable). In Phase 1, the DB allows NULL and we emit `null` (as in the examples above). Phase 2 will revisit this for Conformance (see api-spec.md).

### GET /{tenant}/ims/case/v1p1/CFConcepts/{id}

CASE v1.1 returns a Set type (`CFConceptSetDType`). The first array element is the requested CFConcept; subsequent elements are descendants in the `hierarchyCode` hierarchy (see api-spec.md).

**Response (200):**
```json
{
  "CFConcepts": [
    {
      "identifier": "ccc-concept-1111-...",
      "uri": "https://case.example.com/550e8400-.../uri/ccc-concept-1111-...",
      "title": "言語能力",
      "description": null,
      "keywords": "言葉|表現|理解",
      "hierarchyCode": null,
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    }
  ]
}
```

### GET /{tenant}/ims/case/v1p1/CFSubjects/{id}

CASE v1.1 returns a Set type (`CFSubjectSetDType`). The first array element is the requested CFSubject; subsequent elements are descendants in the `hierarchyCode` hierarchy (see api-spec.md).

**Response (200):**
```json
{
  "CFSubjects": [
    {
      "identifier": "aaa-subject-1111-...",
      "uri": "https://case.example.com/550e8400-.../uri/aaa-subject-1111-...",
      "title": "国語",
      "description": null,
      "hierarchyCode": null,
      "lastChangeDateTime": "2025-10-08T12:00:00Z"
    }
  ]
}
```

### GET /{tenant}/ims/case/v1p1/CFLicenses/{id}

Single object (`CFLicenseDType`).

**Response (200):**
```json
{
  "CFLicense": {
    "identifier": "lic11111-1111-1111-1111-111111111111",
    "uri": "https://case.example.com/550e8400-.../uri/lic11111-...",
    "title": "CC BY 4.0",
    "description": "Creative Commons Attribution 4.0 International",
    "licenseText": null,
    "lastChangeDateTime": "2025-10-08T12:00:00Z"
  }
}
```

### GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id}

Single object (`CFAssociationGroupingDType`).

**Response (200):**
```json
{
  "CFAssociationGrouping": {
    "identifier": "ggg11111-1111-1111-1111-111111111111",
    "uri": "https://case.example.com/550e8400-.../uri/ggg11111-...",
    "title": "教科間関連",
    "description": null,
    "lastChangeDateTime": "2025-10-08T12:00:00Z"
  }
}
```

**When `licenseURI` is non-null (common to CFDocument / CFItem):**
```json
{
  "licenseURI": {
    "title": "CC BY 4.0",
    "identifier": "lic11111-1111-1111-1111-111111111111",
    "uri": "https://case.example.com/550e8400-.../uri/lic11111-1111-1111-1111-111111111111"
  }
}
```

## CFRubrics

### GET /{tenant}/ims/case/v1p1/CFRubrics?doc={document-identifier} (custom extension)

List rubrics belonging to a specific CFDocument. The `doc` parameter is required.

**Request:**
```
GET /550e8400-e29b-41d4-a716-446655440000/ims/case/v1p1/CFRubrics?doc=d86774f2-1234-5678-9abc-def012345678&limit=10&offset=0
```

**Response (200):**
```json
{
  "CFRubrics": [
    {
      "identifier": "rub11111-1111-1111-1111-111111111111",
      "uri": "https://case.example.com/550e8400-.../uri/rub11111-1111-1111-1111-111111111111",
      "title": "評価ルーブリック",
      "description": "学習成果の評価基準",
      "lastChangeDateTime": "2025-04-01T00:00:00+09:00",
      "CFRubricCriteria": [
        {
          "identifier": "cri11111-1111-1111-1111-111111111111",
          "uri": "https://case.example.com/550e8400-.../uri/cri11111-1111-1111-1111-111111111111",
          "category": "知識・理解",
          "description": "基本概念の理解度",
          "CFItemURI": {
            "title": "基本概念を理解している",
            "identifier": "itm11111-1111-1111-1111-111111111111",
            "uri": "https://case.example.com/550e8400-.../uri/itm11111-1111-1111-1111-111111111111"
          },
          "weight": 1.0,
          "position": 1,
          "rubricId": "rub11111-1111-1111-1111-111111111111",
          "lastChangeDateTime": "2025-04-01T00:00:00+09:00",
          "CFRubricCriterionLevels": [
            {
              "identifier": "lvl11111-1111-1111-1111-111111111111",
              "uri": "https://case.example.com/550e8400-.../uri/lvl11111-1111-1111-1111-111111111111",
              "description": "十分に理解している",
              "quality": "A",
              "score": 5.0,
              "feedback": "優れた理解を示しています",
              "position": 1,
              "rubricCriterionId": "cri11111-1111-1111-1111-111111111111",
              "lastChangeDateTime": "2025-04-01T00:00:00+09:00"
            }
          ]
        }
      ]
    }
  ]
}
```

**Response (200) — no rubrics:**
```json
{
  "CFRubrics": []
}
```

**Error — `doc` not specified (400):**
```
GET /550e8400-.../ims/case/v1p1/CFRubrics
```
```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Validation error",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {
        "imsx_codeMinorFieldName": "ims.case.v1p1",
        "imsx_codeMinorFieldValue": "invalid_selection_field"
      }
    ]
  }
}
```

**Error — `doc` is not a valid UUID (400):**
```
GET /550e8400-.../ims/case/v1p1/CFRubrics?doc=not-a-uuid
```
→ 400 `invalid_uuid`

**Error — `doc` CFDocument does not exist (404):**
```
GET /550e8400-.../ims/case/v1p1/CFRubrics?doc=00000000-0000-0000-0000-000000000000
```
→ 404 `unknownobject`

### GET /{tenant}/ims/case/v1p1/CFRubrics/{id}

Single fetch (CASE v1.1 compliant). The response shape matches an element inside the CFRubrics array of CFPackage.

```
GET /550e8400-.../ims/case/v1p1/CFRubrics/rub11111-1111-1111-1111-111111111111
```

**Response (200):**
```json
{
  "CFRubric": {
    "identifier": "rub11111-1111-1111-1111-111111111111",
    "uri": "https://case.example.com/550e8400-.../uri/rub11111-1111-1111-1111-111111111111",
    "title": "評価ルーブリック",
    "description": "学習成果の評価基準",
    "lastChangeDateTime": "2025-04-01T00:00:00+09:00",
    "CFRubricCriteria": [...]
  }
}
```

## Error responses

### 400 Bad Request — invalid UUID format

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

### 404 Not Found — resource does not exist

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

### 404 Not Found — tenant does not exist

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

### 404 Not Found — `/CFItemAssociations/{id}` with a missing item

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

Returns 404, not an empty array (see api-spec.md).

### 405 Method Not Allowed — non-GET request to the CASE API

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

The response includes an `Allow: GET` header.

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

## Pagination examples

### Validation error — negative `limit`

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

An invalid `offset` uses the same shape (`imsx_description` becomes `"Invalid offset: must be a non-negative integer"`).
Non-integer `limit` / `offset` → `"Invalid limit: must be a non-negative integer"` / `"Invalid offset: must be a non-negative integer"`.

### Default (limit=100, offset=0)

```
GET /550e8400-.../ims/case/v1p1/CFDocuments
```

→ Returns the first 100 rows.

### Page 2

```
GET /550e8400-.../ims/case/v1p1/CFDocuments?limit=50&offset=50
```

→ Returns 50 rows starting at row 51.

### Maximum limit

```
GET /550e8400-.../ims/case/v1p1/CFItemAssociations/xxx?limit=500&offset=0
```

→ The limit caps at 500; values above 500 are treated as 500.

### Empty result

```json
{
  "CFDocuments": []
}
```

An empty array is returned (this is not an error).

---

# APIリクエスト/レスポンス例（日本語）

全レスポンスは CASE v1.1 の DType 名をルートキーとして配置する（`{"data": ...}` 等のカスタムラッパーは追加しない）。
テナントUUID `550e8400-e29b-41d4-a716-446655440000` を例として使用。

## CFDocuments

### GET /{tenant}/ims/case/v1p1/CFDocuments

一覧取得。ページネーション対応。

**リクエスト:**
```
GET /550e8400-e29b-41d4-a716-446655440000/ims/case/v1p1/CFDocuments?limit=10&offset=0
```

**レスポンス (200):** 上記の英語版と同一の JSON。

### GET /{tenant}/ims/case/v1p1/CFDocuments/{id}

**レスポンス (200):** 上記の英語版と同一の JSON。

null 許容フィールドは全てレスポンスに含める（Pydantic の `exclude_none=False`）。一覧エンドポイントと単一取得エンドポイントで同一のスキーマ・同一のフィールドセットを返す。
`CFPackageURI` は必須フィールドであり、常に含めなければならない。

## CFItems

### GET /{tenant}/ims/case/v1p1/CFItems/{id}

**レスポンス (200):** 上記の英語版と同一の JSON。

## CFAssociations

### GET /{tenant}/ims/case/v1p1/CFItemAssociations/{id}

対象アイテムと、そのアイテムに関連する全Association（origin/destination両方向）を返す。
CASE v1.1 の CFAssociationSetDType 形式。CFAssociations 内の各 Association は CFDocumentURI を含まない（CFPckgAssociationDType）。

**レスポンス (200):** 上記の英語版と同一の JSON。

### GET /{tenant}/ims/case/v1p1/CFAssociations/{id}

**レスポンス (200):** 上記の英語版と同一の JSON。

**CFAssociationGroupingURI が非 null の場合:** 上記の英語版と同一の JSON。

## CFPackages

### GET /{tenant}/ims/case/v1p1/CFPackages/{id}

ドキュメント配下の全リソースを一括取得。

**レスポンス (200):** 上記の英語版と同一の JSON。

`CFDefinitions` 内の空の配列はキーごと省略する。
例: CFConceptsが0件なら `"CFConcepts"` キー自体を含めない。

## lookup系リソース

### 独自拡張一覧エンドポイント（CASE v1.1 仕様外）

`GET /CFItemTypes`, `GET /CFSubjects`, `GET /CFConcepts`, `GET /CFLicenses`, `GET /CFAssociationGroupings` はテナント内の全リソースを配列で返す。ページネーション対応。レスポンス構造は CASE v1.1 準拠の Set 型エンドポイントと同一（複数形ルートキー + 配列）。

### GET /{tenant}/ims/case/v1p1/CFItemTypes

**レスポンス (200):** 上記の英語版と同一の JSON。

### GET /{tenant}/ims/case/v1p1/CFItemTypes/{id}

CASE v1.1 では Set 型（`CFItemTypeSetDType`）を返す。配列の先頭は要求された CFItemType、後続は `hierarchyCode` の階層下に位置する子孫リソース（`<root>.` で始まる `hierarchyCode` を持つもの）。要求されたリソースの `hierarchyCode` が NULL の場合や該当する子孫がない場合は要求されたリソース 1 件のみを返す（詳細は api-spec.md 参照）。

**レスポンス (200):** 上記の英語版と同一の JSON。

**Set 型エンドポイント**（`/CFConcepts/{id}`, `/CFSubjects/{id}`, `/CFItemTypes/{id}`）は複数形ルートキーで配列を返す（`{"CFConcepts": [...]}`, `{"CFSubjects": [...]}`, `{"CFItemTypes": [...]}`）。
**単一オブジェクト型エンドポイント**（`/CFLicenses/{id}`, `/CFAssociationGroupings/{id}`）は単数形ルートキーで単一オブジェクトを返す（`{"CFLicense": {...}}`, `{"CFAssociationGrouping": {...}}`）。
CFLicenses, CFAssociationGroupings も同じ基本構造（単数キー、単一オブジェクト）。
全 lookup リソース共通フィールド: `identifier`, `uri`, `title`, `description` (nullable), `lastChangeDateTime`。
各リソースの固有フィールド:
- **CFItemType**: `typeCode` (string, nullable), `hierarchyCode` (string, nullable)
- **CFSubject**: `hierarchyCode` (string, nullable)
- **CFConcept**: `keywords` (string, nullable, パイプ区切り), `hierarchyCode` (string, nullable)
- **CFLicense**: `licenseText` (string, nullable)
- **CFAssociationGrouping**: 固有フィールドなし（共通フィールドのみ）

**注意**: CASE v1.1 仕様では `description`（CFItemType）、`hierarchyCode`（CFItemType/CFSubject/CFConcept）、`licenseText`（CFLicense）は required（non-nullable）として定義されている。Phase 1 では DB 上 nullable のため `null` を返す（上記例の通り）。Phase 2 の Conformance テスト対応で修正予定（api-spec.md 参照）。

### GET /{tenant}/ims/case/v1p1/CFConcepts/{id}

CASE v1.1 では Set 型（`CFConceptSetDType`）を返す。配列の先頭は要求された CFConcept、後続は `hierarchyCode` の階層下に位置する子孫リソース（詳細は api-spec.md 参照）。

**レスポンス (200):** 上記の英語版と同一の JSON。

### GET /{tenant}/ims/case/v1p1/CFSubjects/{id}

CASE v1.1 では Set 型（`CFSubjectSetDType`）を返す。配列の先頭は要求された CFSubject、後続は `hierarchyCode` の階層下に位置する子孫リソース（詳細は api-spec.md 参照）。

**レスポンス (200):** 上記の英語版と同一の JSON。

### GET /{tenant}/ims/case/v1p1/CFLicenses/{id}

単一オブジェクト型（`CFLicenseDType`）を返す。

**レスポンス (200):** 上記の英語版と同一の JSON。

### GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id}

単一オブジェクト型（`CFAssociationGroupingDType`）を返す。

**レスポンス (200):** 上記の英語版と同一の JSON。

**licenseURI が非 null の場合（CFDocument / CFItem 共通）:** 上記の英語版と同一の JSON。

## CFRubrics

### GET /{tenant}/ims/case/v1p1/CFRubrics?doc={document-identifier}（独自拡張）

指定した CFDocument に属するルーブリック一覧を取得。`doc` パラメータは必須。

**リクエスト:**
```
GET /550e8400-e29b-41d4-a716-446655440000/ims/case/v1p1/CFRubrics?doc=d86774f2-1234-5678-9abc-def012345678&limit=10&offset=0
```

**レスポンス (200) / レスポンス (200) — ルーブリックなし / エラー — `doc` パラメータ未指定 (400) / エラー — `doc` が不正な UUID (400) / エラー — `doc` の CFDocument が存在しない (404):** 上記の英語版と同一の JSON。

### GET /{tenant}/ims/case/v1p1/CFRubrics/{id}

個別取得は CASE v1.1 準拠。レスポンス例は CFPackages セクションの CFRubrics 配列内の要素と同じ構造。

```
GET /550e8400-.../ims/case/v1p1/CFRubrics/rub11111-1111-1111-1111-111111111111
```

**レスポンス (200):** 上記の英語版と同一の JSON。

## エラーレスポンス

### 400 Bad Request — UUID形式不正

上記の英語版「400 Bad Request — invalid UUID format」と同一の JSON。

### 404 Not Found — リソースが存在しない

上記の英語版「404 Not Found — resource does not exist」と同一の JSON。

### 404 Not Found — テナントが存在しない

上記の英語版「404 Not Found — tenant does not exist」と同一の JSON。

### 404 Not Found — /CFItemAssociations/{id} でアイテムが存在しない

上記の英語版「404 Not Found — `/CFItemAssociations/{id}` with a missing item」と同一の JSON。

空配列ではなく 404 を返す（api-spec.md 参照）。

### 405 Method Not Allowed — CASE API への非GETリクエスト

上記の英語版「405 Method Not Allowed — non-GET request to the CASE API」と同一の JSON。

`Allow: GET` レスポンスヘッダーを含める。

### 500 Internal Server Error

上記の英語版と同一の JSON。

## ページネーション例

### バリデーションエラー — limit が負数

上記の英語版「Validation error — negative `limit`」と同一の JSON。

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
