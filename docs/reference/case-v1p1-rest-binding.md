# CASE v1.1 REST/JSON Binding Reference

Source: [1EdTech CASE v1.1 REST/JSON Binding](https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html)

OpenAPI 3 Schema: `imscasev1p1_openapi3_v1p0.json` (downloaded from [1EdTech](https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/))

## Base Path

All endpoints are prefixed with: `/ims/case/v1p1`

Service Discovery: `GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json`

---

## API Endpoints

| HTTP Method | Path | operationId | Response (200) |
|-------------|------|-------------|----------------|
| GET | /CFDocuments | getAllCFDocuments | CFDocumentSetDType |
| GET | /CFDocuments/{sourcedId} | getCFDocument | CFDocumentDType |
| GET | /CFItems/{sourcedId} | getCFItem | CFItemDType |
| GET | /CFItemAssociations/{sourcedId} | getCFItemAssociations | CFAssociationSetDType |
| GET | /CFAssociations/{sourcedId} | getCFAssociation | CFAssociationDType |
| GET | /CFAssociationGroupings/{sourcedId} | getCFAssociationGrouping | CFAssociationGroupingDType |
| GET | /CFConcepts/{sourcedId} | getCFConcept | CFConceptSetDType |
| GET | /CFSubjects/{sourcedId} | getCFSubject | CFSubjectSetDType |
| GET | /CFItemTypes/{sourcedId} | getCFItemType | CFItemTypeSetDType |
| GET | /CFLicenses/{sourcedId} | getCFLicense | CFLicenseDType |
| GET | /CFPackages/{sourcedId} | getCFPackage | CFPackageDType |
| GET | /CFRubrics/{sourcedId} | getCFRubric | CFRubricDType |

**Notes:**
- `/CFItemAssociations/{sourcedId}` path (NOT `/CFItems/{sourcedId}/associations`)
- `/CFConcepts/{sourcedId}` returns CFConceptSetDType (set with hierarchy), not single object
- `/CFSubjects/{sourcedId}` returns CFSubjectSetDType (set with hierarchy), not single object
- `/CFItemTypes/{sourcedId}` returns CFItemTypeSetDType (set with hierarchy), not single object
- `/CFLicenses/{sourcedId}` returns single CFLicenseDType (not a set)
- Only `/CFDocuments` has list endpoint (getAllCFDocuments)

---

## Pagination Parameters

Only applies to `GET /CFDocuments` (getAllCFDocuments).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | integer (positive) | 100 | Maximum records per response |
| offset | integer (non-negative) | 0 | Index of first record (zero-based) |
| sort | string | - | Field name to sort by |
| orderBy | string (asc\|desc) | - | Sort direction |
| filter | string | - | Filter criteria |
| fields | array of strings | - | Select specific response fields |

---

## Response Wrapper Types

### CFDocumentSetDType

```json
{
  "CFDocuments": [ ...array of CFDocumentDType... ]
}
```
Required: `CFDocuments` (minItems: 1)

### CFAssociationSetDType

```json
{
  "CFItem": { ...CFItemDType... },
  "CFAssociations": [ ...array of CFPckgAssociationDType... ]
}
```
Required: `CFItem`, `CFAssociations` (minItems: 1)

**Note:** CFAssociationSet wraps associations with the source CFItem. Associations use CFPckgAssociationDType (no CFDocumentURI).

### CFConceptSetDType

```json
{
  "CFConcepts": [ ...array of CFConceptDType... ]
}
```
Required: `CFConcepts` (minItems: 1). First element is the requested concept, followed by child concepts per hierarchyCode.

### CFSubjectSetDType

```json
{
  "CFSubjects": [ ...array of CFSubjectDType... ]
}
```
Required: `CFSubjects` (minItems: 1). First element is the requested subject, followed by children.

### CFItemTypeSetDType

```json
{
  "CFItemTypes": [ ...array of CFItemTypeDType... ]
}
```
Required: `CFItemTypes` (minItems: 1). First element is the requested type, followed by children.

---

## Error Response Format

### imsx_StatusInfoDType

```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Human readable message",
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

**Note on field name casing:** The OpenAPI spec uses `imsx_codeMajor` (lowercase 'c'), `imsx_severity`, etc.

### HTTP Status Code Mapping

| Status | Condition | Error Response |
|--------|-----------|----------------|
| 200 | Success | Data payload (no imsx_StatusInfo) |
| 400 | Invalid selection field | imsx_StatusInfo |
| 401 | Unauthorized | imsx_StatusInfo |
| 403 | Forbidden | imsx_StatusInfo |
| 404 | Unknown object / Invalid UUID | imsx_StatusInfo |
| 429 | Server busy / Rate limit | imsx_StatusInfo |
| 500 | Internal server error | imsx_StatusInfo |

---

## Key Differences: Standalone vs. Package Types

### CFDocument vs CFPckgDocument

| Feature | CFDocumentDType | CFPckgDocumentDType |
|---------|----------------|---------------------|
| CFPackageURI | YES (required) | NO |

Both have `creator` as required. All other properties are identical.

### CFItem vs CFPckgItem

| Feature | CFItemDType | CFPckgItemDType |
|---------|-------------|-----------------|
| CFDocumentURI | YES (required) | NO |

All other properties are identical (same names, same types).

### CFAssociation vs CFPckgAssociation

| Feature | CFAssociationDType | CFPckgAssociationDType |
|---------|-------------------|------------------------|
| CFDocumentURI | YES (optional) | NO |
