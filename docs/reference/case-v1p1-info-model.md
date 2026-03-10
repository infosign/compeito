# CASE v1.1 Information Model Reference

Source: [1EdTech CASE v1.1 Information Model](https://www.imsglobal.org/sites/default/files/spec/case/v1p1/information_model/caseservicev1p1_infomodelv1p0.html)

OpenAPI 3 Schema: `imscasev1p1_openapi3_v1p0.json` (downloaded from [1EdTech](https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/))

## Link Types

### LinkURIDType

Complex object for referencing CASE resources. Used for licenseURI, subjectURI, CFItemTypeURI, CFPackageURI, CFDocumentURI, CFAssociationGroupingURI, conceptKeywordsURI, CFItemURI (in rubric criterion).

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| title | string (NormalizedString) | YES | Human-readable label |
| identifier | string (UUID pattern) | YES | Globally unique identifier |
| uri | string (AnyURI) | YES | Network-resolvable URI |

### LinkGenURIDType

Extended link type used ONLY for originNodeURI and destinationNodeURI in CFAssociation. Adds targetType for cross-framework references.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| title | string (NormalizedString) | YES | Human-readable label |
| identifier | string (any format) | YES | Identifier (may or may not be UUID) |
| uri | string (AnyURI) | YES | Network-resolvable URI |
| targetType | string (enum or ext:pattern) | NO | v1.1 new. Type of referenced node. Enum: `CASE`, or `ext:` prefix pattern |

**Key difference from LinkURIDType:** identifier is NOT restricted to UUID pattern (external references may use non-UUID identifiers). Has additional targetType field.

---

## Data Model Definitions

### CFDocument (CFDocumentDType)

Context: standalone (in `GET /CFDocuments/{id}` response).

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| frameworkType | string | NO | v1.1 new. e.g. "CourseCodes" |
| caseVersion | string (enum: "1.1") | NO | v1.1 new. If present, MUST be "1.1" |
| creator | string | YES | |
| title | string | YES | |
| lastChangeDateTime | string (date-time) | YES | |
| officialSourceURL | string (URI) | NO | |
| publisher | string | NO | |
| description | string | NO | Changed from NormalizedString in v1.1 |
| subject | array of strings | NO | |
| subjectURI | array of LinkURIDType | NO | |
| language | string | NO | |
| version | string | NO | |
| adoptionStatus | string | NO | |
| statusStartDate | string (date) | NO | |
| statusEndDate | string (date) | NO | |
| **licenseURI** | **LinkURIDType** | **NO** | **COMPLEX OBJECT, not simple URI** |
| notes | string | NO | |
| CFPackageURI | LinkURIDType | YES (standalone only) | NOT present in CFPckgDocument |
| extensions | object | NO | v1.1 new |

### CFPckgDocument (CFPckgDocumentDType)

Context: within CFPackage. Same as CFDocument EXCEPT:
- **NO** `CFPackageURI` property
- Required: `identifier`, `uri`, `creator`, `title`, `lastChangeDateTime`

### CFItem (CFItemDType)

Context: standalone (in `GET /CFItems/{id}` response).

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| fullStatement | string | YES | Changed from NormalizedString in v1.1 |
| alternativeLabel | string | NO | |
| CFItemType | string | NO | Textual label (NOT LinkURIDType) |
| uri | string (URI) | YES | |
| humanCodingScheme | string | NO | |
| listEnumeration | string | NO | |
| abbreviatedStatement | string | NO | |
| conceptKeywords | array of strings | NO | |
| conceptKeywordsURI | LinkURIDType | NO | Single object, NOT array |
| notes | string | NO | |
| subject | array of strings | NO | v1.1 new |
| subjectURI | array of LinkURIDType | NO | v1.1 new |
| language | string | NO | |
| educationLevel | array of strings | NO | |
| CFItemTypeURI | LinkURIDType | NO | |
| **licenseURI** | **LinkURIDType** | **NO** | **COMPLEX OBJECT, not simple URI** |
| statusStartDate | string (date) | NO | |
| statusEndDate | string (date) | NO | |
| lastChangeDateTime | string (date-time) | YES | |
| CFDocumentURI | LinkURIDType | YES (standalone only) | NOT present in CFPckgItem |
| extensions | object | NO | v1.1 new |

### CFPckgItem (CFPckgItemDType)

Context: within CFPackage. Same as CFItem EXCEPT:
- **NO** `CFDocumentURI` property
- Only required: `identifier`, `fullStatement`, `uri`, `lastChangeDateTime`

All other properties (including `licenseURI`, `CFItemTypeURI`, etc.) are identical to CFItemDType.

### CFAssociation (CFAssociationDType)

Context: standalone (in `GET /CFAssociations/{id}` response).

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| associationType | string (enum or ext:) | YES | See enum below |
| sequenceNumber | integer (int32) | NO | |
| uri | string (URI) | YES | |
| originNodeURI | **LinkGenURIDType** | YES | Note: LinkGen, not LinkURI |
| destinationNodeURI | **LinkGenURIDType** | YES | Note: LinkGen, not LinkURI |
| CFAssociationGroupingURI | LinkURIDType | NO | |
| lastChangeDateTime | string (date-time) | YES | |
| notes | string | NO | v1.1 new |
| CFDocumentURI | LinkURIDType | NO | Present in standalone only |
| extensions | object | NO | v1.1 new |

### CFPckgAssociation (CFPckgAssociationDType)

Context: within CFPackage. Same as CFAssociation EXCEPT:
- **NO** `CFDocumentURI` property
- Required: `identifier`, `associationType`, `uri`, `originNodeURI`, `destinationNodeURI`, `lastChangeDateTime`

### CFAssociationGrouping (CFAssociationGroupingDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| title | string | YES | |
| description | string | NO | |
| lastChangeDateTime | string (date-time) | YES | |
| extensions | object | NO | v1.1 new |

### CFItemType (CFItemTypeDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| title | string | YES | |
| description | string | YES | **Required** per OpenAPI spec |
| hierarchyCode | string | YES | **Required** per OpenAPI spec |
| typeCode | string | NO | |
| lastChangeDateTime | string (date-time) | YES | |
| extensions | object | NO | v1.1 new |

### CFConcept (CFConceptDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| title | string | YES | |
| keywords | string | NO | Pipe-delimited keywords |
| hierarchyCode | string | YES | **Required** per OpenAPI spec |
| description | string | NO | |
| lastChangeDateTime | string (date-time) | YES | |
| extensions | object | NO | v1.1 new |

### CFSubject (CFSubjectDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| title | string | YES | |
| hierarchyCode | string | YES | **Required** per OpenAPI spec |
| description | string | NO | |
| lastChangeDateTime | string (date-time) | YES | |
| extensions | object | NO | v1.1 new |

### CFLicense (CFLicenseDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| title | string | YES | |
| description | string | NO | |
| licenseText | string | YES | **Required** per OpenAPI spec |
| lastChangeDateTime | string (date-time) | YES | |
| extensions | object | NO | v1.1 new |

### CFRubric (CFRubricDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| title | string | NO | |
| description | string | NO | Changed from NormalizedString in v1.1 |
| lastChangeDateTime | string (date-time) | YES | |
| CFRubricCriteria | array of CFRubricCriterionDType | NO | |
| extensions | object | NO | v1.1 new |

### CFRubricCriterion (CFRubricCriterionDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| category | string | NO | |
| description | string | NO | |
| CFItemURI | LinkURIDType | NO | Reference to associated CFItem |
| weight | number (float) | NO | |
| position | integer (int32) | NO | |
| rubricId | string (UUID) | NO | Parent rubric reference |
| lastChangeDateTime | string (date-time) | YES | |
| CFRubricCriterionLevels | array of CFRubricCriterionLevelDType | NO | |
| extensions | object | NO | v1.1 new |

### CFRubricCriterionLevel (CFRubricCriterionLevelDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| identifier | string (UUID) | YES | |
| uri | string (URI) | YES | |
| description | string | NO | |
| quality | string | NO | |
| score | number (float) | NO | |
| feedback | string | NO | |
| position | integer (int32) | NO | |
| rubricCriterionId | string (UUID) | NO | Parent criterion reference |
| lastChangeDateTime | string (date-time) | YES | |
| extensions | array of objects | NO | v1.1 new (note: array, not single object) |

---

## Structural Types

### CFPackage (CFPackageDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| CFDocument | CFPckgDocumentDType | YES | |
| CFItems | array of CFPckgItemDType | NO | |
| CFAssociations | array of CFPckgAssociationDType | NO | |
| CFDefinitions | CFDefinitionDType | NO | |
| CFRubrics | array of CFRubricDType | NO | |
| extensions | object | NO | v1.1 new |

### CFDefinition (CFDefinitionDType)

| Property | JSON Type | Required | Notes |
|----------|-----------|----------|-------|
| CFConcepts | array of CFConceptDType | NO | |
| CFSubjects | array of CFSubjectDType | NO | |
| CFLicenses | array of CFLicenseDType | NO | |
| CFItemTypes | array of CFItemTypeDType | NO | |
| CFAssociationGroupings | array of CFAssociationGroupingDType | NO | |
| extensions | object | NO | v1.1 new |

---

## Enumeration Types

### associationType (CFAssociationType)

Extensible enumeration. Standard values:
- `isChildOf`
- `isPeerOf`
- `isPartOf`
- `exactMatchOf`
- `precedes`
- `isRelatedTo`
- `replacedBy`
- `exemplar`
- `hasSkillLevel`
- `isTranslationOf` (v1.1 new)

Extension pattern: `ext:` prefix followed by alphanumeric/dot/hyphen/underscore characters.

### imsx_codeMajor

- `failure`
- `processing`
- `success`
- `unsupported`

### imsx_severity

- `error`
- `status`
- `warning`

### imsx_codeMinorFieldValue

- `forbidden`
- `fullsuccess`
- `internal_server_error`
- `invalid_selection_field`
- `invalid_sort_field`
- `invalid_uuid`
- `server_busy`
- `unauthorised_request`
- `unknownobject`

### caseVersion

- `1.1` (only valid value)

### targetType (in LinkGenURIDType)

Standard value: `CASE`
Extension pattern: `ext:` prefix.

---

## v1.1 Changes from v1.0

1. `frameworkType` added to CFDocument
2. `caseVersion` added to CFDocument
3. `subject` and `subjectURI` added to CFItem
4. `notes` added to CFAssociation
5. `targetType` added to LinkGenURIDType
6. `isTranslationOf` added to associationType enumeration
7. `fullStatement` (CFItem) and `description` (CFDocument/CFRubric) changed from NormalizedString to String
8. `extensions` added to all classes
9. Base path changed to `/ims/case/v1p1`
