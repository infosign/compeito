# CASE v1.1 API Specification

API path: `/{tenant}/ims/case/v1p1/` (required for conformance) + `/{tenant}/ims/case/v1p0/` (backward compatibility).

**Meaning of the `{id}` path parameter:** in every endpoint, `{id}` is the CASE identifier (the DB `identifier` column), not the internal PK (`id`).

## Endpoint list

12 CASE v1.1 compliant endpoints:

| Path | Response root key | Description | CASE v1.1 |
|------|-------------------|-------------|-----------|
| GET /{tenant}/ims/case/v1p1/CFPackages/{id} | `{"CFDocument": {...}, "CFItems": [...], ...}` | Get a package (top-level CFPackageDType, no wrapper) | ✓ |
| GET /{tenant}/ims/case/v1p1/CFDocuments | `{"CFDocuments": [...]}` | List documents | ✓ |
| GET /{tenant}/ims/case/v1p1/CFDocuments/{id} | `{"CFDocument": {...}}` | Get a document | ✓ |
| GET /{tenant}/ims/case/v1p1/CFItems/{id} | `{"CFItem": {...}}` | Get an item | ✓ |
| GET /{tenant}/ims/case/v1p1/CFItemAssociations/{id} | `{"CFItem": {...}, "CFAssociations": [...]}` | Item + its associations | ✓ |
| GET /{tenant}/ims/case/v1p1/CFAssociations/{id} | `{"CFAssociation": {...}}` | Get an association | ✓ |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id} | `{"CFAssociationGrouping": {...}}` | Get an association grouping | ✓ |
| GET /{tenant}/ims/case/v1p1/CFConcepts/{id} | `{"CFConcepts": [...]}` | Get concept set | ✓ |
| GET /{tenant}/ims/case/v1p1/CFItemTypes/{id} | `{"CFItemTypes": [...]}` | Get item-type set | ✓ |
| GET /{tenant}/ims/case/v1p1/CFLicenses/{id} | `{"CFLicense": {...}}` | Get a license | ✓ |
| GET /{tenant}/ims/case/v1p1/CFSubjects/{id} | `{"CFSubjects": [...]}` | Get subject set | ✓ |
| GET /{tenant}/ims/case/v1p1/CFRubrics/{id} | `{"CFRubric": {...}}` | Get a rubric | ✓ |

**Custom listing endpoints** (outside the CASE v1.1 spec; provided for convenience to list all resources within a tenant):

| Path | Response root key | Description |
|------|-------------------|-------------|
| GET /{tenant}/ims/case/v1p1/CFItemTypes | `{"CFItemTypes": [...]}` | List item types |
| GET /{tenant}/ims/case/v1p1/CFSubjects | `{"CFSubjects": [...]}` | List subjects |
| GET /{tenant}/ims/case/v1p1/CFConcepts | `{"CFConcepts": [...]}` | List concepts |
| GET /{tenant}/ims/case/v1p1/CFLicenses | `{"CFLicenses": [...]}` | List licenses |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings | `{"CFAssociationGroupings": [...]}` | List association groupings |
| GET /{tenant}/ims/case/v1p1/CFRubrics?doc={id} | `{"CFRubrics": [...]}` | List rubrics (`doc` is required) |

**Why CFRubrics requires `doc`:** unlike CFDefinitions (e.g., CFItemType), a CFRubric belongs to a specific CFDocument. The CASE v1.1 `CFRubricDType` has no field indicating its owning document, so listing across the tenant would not tell you which document each rubric belongs to. The `doc` query parameter (CFDocument identifier, a UUID) is therefore **required**. Missing `doc` → 400; invalid UUID → 400; document not found → 404.

**Set-type endpoints (`/CFConcepts/{id}`, `/CFSubjects/{id}`, `/CFItemTypes/{id}`)**: per CASE v1.1, these return Set types (`CFConceptSetDType`, `CFSubjectSetDType`, `CFItemTypeSetDType`). The first array element is the requested resource; subsequent elements are descendants in the `hierarchyCode` hierarchy. Descendants are determined by string match: if the target's `hierarchyCode` is `<root>`, records whose `hierarchyCode` starts with `<root>.` are included (e.g., for `<root>` = `"1"`: `"1.1"`, `"1.2.3"`, etc.). Descendants are ordered ascending by `hierarchyCode` (ties broken by ascending `identifier`). When the requested resource's `hierarchyCode` is NULL, or it has no descendants, only the requested resource is returned. `/CFLicenses/{id}` returns a single object `CFLicenseDType` (not a Set).

**Compliance note for required lookup fields (Phase 2):**
CASE v1.1 OpenAPI marks some lookup fields as required (non-nullable):
- CFItemType: `description`, `hierarchyCode`
- CFSubject: `hierarchyCode`
- CFConcept: `hierarchyCode`
- CFLicense: `licenseText`

In Phase 1 these are stored as nullable; if missing, `null` is returned (auto-generated lookups from CSV imports always leave these NULL). Phase 2 will revisit this for Conformance compliance: either return an empty string `""` or treat the schema as nullable.

## CFPackage response shape

The response IS a `CFPackageDType` (no wrapper key). This matches CASE v1.1 and OpenSALT — clients read `CFDocument` / `CFItems` directly from the top level.

```json
{
  "CFDocument": {...},
  "CFItems": [...],
  "CFAssociations": [...],
  "CFDefinitions": {
    "CFItemTypes": [...],
    "CFSubjects": [...],
    "CFConcepts": [...],
    "CFLicenses": [...],
    "CFAssociationGroupings": [...]
  },
  "CFRubrics": [...]
}
```
- `CFItems` and `CFAssociations` are always included as arrays, empty if no data. (CASE v1.1 OpenAPI lists `CFItems` / `CFAssociations` as optional, but we include them unconditionally for client convenience.) Both are filtered by `cf_document_id` (resources owned by this document only; associations from other documents that reference this document's items are not included).
- `CFDefinitions` is omitted entirely when empty. Each inner key is also omitted when empty (an exception to the global `exclude_none=False` policy). Empty-array keys inside CFDefinitions are excluded rather than emitted as `null`. Use a Pydantic custom serializer (e.g., `model_serializer`) to drop empty arrays; `exclude_none=True` only drops `None` values, not `[]`.
- Scope of `CFDefinitions`: only definitions referenced from this document's resources (not all tenant definitions). Specifically: CFItemTypes referenced by `cf_item_type_id` from the document's items; CFSubjects referenced via `subject_uri` from the CFDocument or its items; CFConcepts referenced by `cf_concept_id` from the document's items; CFLicenses referenced by `cf_license_id` from the CFDocument or its items; CFAssociationGroupings referenced by `cf_association_grouping_id` from the document's associations.
- `CFRubrics` is always included as an array, empty if no data (like `CFItems` / `CFAssociations`; `CFRubrics` is an array type and the CFDefinitions object-type omission rule does not apply).
- **Sort order within CFPackage**: every array in CFItems / CFAssociations / CFDefinitions is sorted by `identifier ASC` (consistent with the listing endpoints' default; guarantees deterministic output).
- **CFPckg* schemas inside CFPackage**: CASE v1.1 uses CFPckg-specific schemas inside CFPackage:
  - `CFPckgDocument`: standalone `CFDocument` minus `CFPackageURI` (redundant since the CFPackage already wraps this document).
  - `CFPckgItem`: standalone `CFItem` minus `CFDocumentURI` (the document is unambiguous from the CFPackage context).
  - `CFPckgAssociation`: standalone `CFAssociation` minus `CFDocumentURI` (same rationale).
  - Each CFDefinitions resource (CFItemType, CFSubject, etc.) uses the same schema as the standalone form.
  - Define CFPckg-specific derived schemas in Pydantic that exclude `CFPackageURI` / `CFDocumentURI`.

Do **not** add custom wrappers (`{"data": ...}` etc.) to the response.
**Null fields**: include nullable fields in the response (Pydantic `exclude_none=False`). The policy is consistent across every endpoint for consistency.
On error, return `{"imsx_codeMajor": "failure", ...}` directly at the root (see the error format section).

## CFItemAssociations response shape

The CASE v1.1 `CFAssociationSetDType`. Returns the target CFItem and every association related to it:
```json
{
  "CFItem": {...},
  "CFAssociations": [...]
}
```
- `CFItem`: the target item in its standalone shape (identical to `GET /CFItems/{id}`, with `CFDocumentURI`).
- `CFAssociations`: every association related to the target item. Each association does **not** include `CFDocumentURI` (the CASE v1.1 `CFPckgAssociationDType`; same schema as CFAssociations inside CFPackage).
- `CFAssociations` is always returned as an array, empty if no data. (CASE v1.1 OpenAPI defines `CFAssociations` as required with `minItems: 1`, but we allow the empty array because an item without associations is operationally normal.)

## Validation (common to all endpoints)

**Tenant UUID:**
- `{tenant-uuid}` is not a UUID → **400** (`imsx_codeMinorFieldValue: invalid_uuid`). (CASE v1.1 specifies 404 even for invalid UUIDs in some cases, but we split invalid format from "not found" for clarity.)
- Valid UUID but the tenant does not exist → **404** (`imsx_codeMinorFieldValue: unknownobject`).

**Resource ID:**
- All resource fetches are tenant-scoped (within the tenant specified by `{tenant-uuid}`).
- `{id}` (in `/CFItems/{id}`, `/CFDocuments/{id}`, etc.) is not a UUID → **400** (`imsx_codeMinorFieldValue: invalid_uuid`).
- Valid UUID but the resource is not found inside the tenant → **404** (`imsx_codeMinorFieldValue: unknownobject`).
- `GET /CFItemAssociations/{id}` when the item does not exist → **404** (`imsx_codeMinorFieldValue: unknownobject`) — not an empty array.
- `GET /CFItemAssociations/{id}` search scope: returns associations whose `origin_node_identifier = {id}` OR `destination_node_identifier = {id}` across all documents in the tenant (not just the document the item lives in).

**Scope:**
- `/uri/{uuid}` is tenant-scoped. UUIDs that belong to another tenant return **404**.
- `/uri/{uuid}` search order: cf_document → cf_item → cf_association → cf_item_type → cf_subject → cf_concept → cf_license → cf_association_grouping (stops at the first match). If the same UUID exists in multiple tables (theoretically possible since there's no cross-table UNIQUE), the first match in this order wins.

## Pagination

CASE v1.1 compliant. All listing endpoints accept `limit` (default 100, max 500) and `offset` (default 0).
Applies to: `CFDocuments`, `CFItemAssociations/{id}`, `CFItemTypes`, `CFSubjects`, `CFConcepts`, `CFLicenses`, `CFAssociationGroupings` (every endpoint that returns an array). CASE v1.1 OpenAPI defines pagination only for `GET /CFDocuments`; we extend it to every listing endpoint for convenience.
`CFPackages/{id}` is not paginated. Per spec, the CFItems / CFAssociations / CFDefinitions inside CFPackage are returned in full. **Note**: the API Gateway payload limit is 10MB. Large documents (10,000+ items) may exceed it; API Gateway returns 502 in that case. If needed, consider going through the Lambda Function URL (Phase 2+).
`sort` / `orderBy` / `filter` / `fields` parameters are not implemented in Phase 1 (silently ignored).
Total count is not included in the response. CASE v1.1 OpenAPI defines `X-Total-Count` and `links` (next, last, first, prev) for `GET /CFDocuments`; we do not implement them in Phase 1 (Phase 2 will revisit).
Default sort order: every listing endpoint sorts by `identifier ASC` to guarantee deterministic ordering and avoid duplicates / gaps across pages.
Scope: every listing endpoint returns all tenant rows (no document filtering). `CFDocuments` returns every document in the tenant. `CFItemTypes` / `CFSubjects` / `CFConcepts` / `CFLicenses` / `CFAssociationGroupings` return every lookup in the tenant. `CFItems/{id}/associations` searches all documents in the tenant (see the validation section). CFDefinitions inside CFPackage is narrowed to definitions referenced from the document, but listing endpoints are not narrowed.

**Validation:**
- `limit` = 0 → return an empty array (treated as a valid request; CASE v1.1 OpenAPI defines `minimum: 1`, but `limit=0` is a sensible "empty result" request).
- `limit` < 0 → 400 (`invalid_selection_field`).
- `limit` > 500 → treat as 500 (no error).
- `limit` is not an integer → 400 (`invalid_selection_field`).
- `offset` < 0 → 400 (`invalid_selection_field`).
- `offset` is not an integer → 400 (`invalid_selection_field`).
- `offset` > 100000 → treat as 100000 (PostgreSQL OFFSET cap, mirroring the `limit` cap).
- `offset` ≥ total row count → return an empty array (no error).

## Response headers (Cache-Control)

**Successful responses (200):** every CASE API endpoint sets `Cache-Control: public, max-age=3600` (the same for public and private tenants).

**Error responses (4xx / 5xx):** no `Cache-Control`. Falls back to CloudFront's Error Caching Minimum TTL (default 10s). A 404 may be cached briefly right after an import; it expires quickly.

**Exceptions:**
- Health check (`GET /health`): `Cache-Control: no-store` (see below).
- v1p0 redirect (301): no `Cache-Control` (301 is cacheable by default per HTTP).

## Health check

```
GET /health
```
Response (200):
```json
{"status": "ok"}
```
- No auth, no tenant path.
- `Content-Type: application/json`.
- `Cache-Control: no-store` (don't let CloudFront cache it).
- No DB connection check (prioritize Lambda cold-start speed).

## v1p0 backward compatibility

`/ims/case/v1p0/` paths are 301-redirected to `/ims/case/v1p1/`.
Since the CASE API is GET-only, a 301 is safe (no risk of method change as with POST).
Don't double-implement routers — `src/main.py` has a single middleware that handles the swap.
The target replaces `v1p0` with `v1p1` in the path (query parameters are preserved).
No `Cache-Control` (HTTP defaults make 301 cacheable; CloudFront / browsers cache it. This is permanent so the default behavior is fine).

```python
# Middleware example in src/main.py
@app.middleware("http")
async def redirect_v1p0(request, call_next):
    if "/ims/case/v1p0/" in request.url.path:
        new_path = request.url.path.replace("/ims/case/v1p0/", "/ims/case/v1p1/")
        new_url = str(request.url).replace(request.url.path, new_path)
        return RedirectResponse(url=new_url, status_code=301)
    return await call_next(request)
```

## Date / timestamp formats

- **TIMESTAMP fields** (`lastChangeDateTime`): ISO 8601 UTC with a trailing `Z` (e.g., `"2025-10-08T12:00:00Z"`). No milliseconds. Standardize via Pydantic serialization settings.
- **DATE fields** (`statusStartDate`, `statusEndDate`): `YYYY-MM-DD` (e.g., `"2018-03-30"`). Per CASE v1.1, `xsd:date`.

## LinkURI types

`CFPackageURI`, `CFDocumentURI`, `CFOriginNodeURI`, `CFDestinationNodeURI`, `CFItemTypeURI`, etc. are composite objects, not strings:
```json
{"title": "Document title", "identifier": "uuid", "uri": "https://..."}
```
Define a shared `LinkURIType` Pydantic class in `src/schemas/common.py`.
The DB stores `_uri` (VARCHAR) and `_identifier` (UUID); `title` is resolved via JOIN or in the application layer.
To accommodate external references that can't be resolved by JOIN, `cf_association.origin_node_uri` / `destination_node_uri` also keep a `_title` column.

**Constructing `CFPackageURI`:**
`CFPackageURI` is not persisted to the DB; it is constructed when generating the API response:
- `title` = CFDocument.title
- `identifier` = CFDocument.identifier
- `uri` = `{BASE_URL}/{tenant}/ims/case/v1p1/CFPackages/{CFDocument.identifier}`

Even for externally imported documents, `CFPackageURI.uri` points at our own API endpoint (CFDocument.uri keeps the external URI, but CFPackageURI.uri indicates "where to retrieve this package", which must be our own server).

**Constructing `CFDocumentURI` (inside CFItem / CFAssociation):**
JOIN on `cf_document_id` and use the CFDocument's `{title, identifier, uri}`. CASE v1.1 OpenAPI lists CFDocumentURI as **required** for CFItemDType and **optional** for CFAssociationDType, but since `cf_document_id` is NOT NULL here it's always present — we include `CFDocumentURI` in both cases.

**Constructing `CFItemTypeURI` (inside CFItem):**
JOIN on `cf_item_type_id` and use the CFItemType's `{title, identifier, uri}`. When `cf_item_type_id` is NULL, `CFItemTypeURI` is null too (included as JSON `null` since `exclude_none=False`). The string field `CFItemType` uses the joined CFItemType's `title`; when `cf_item_type_id` is NULL, `CFItemType` is also null.

**Constructing `licenseURI` (inside CFDocument / CFItem):**
JOIN on `cf_license_id` and use the CFLicense's `{title, identifier, uri}`. When `cf_license_id` is NULL, `licenseURI` is null (included as JSON `null`). Same FK → JOIN pattern as CFItemTypeURI.

**Constructing `CFAssociationGroupingURI` (inside CFAssociation):**
JOIN on `cf_association_grouping_id` and use the CFAssociationGrouping's `{title, identifier, uri}`. When `cf_association_grouping_id` is NULL, it's null (included as JSON `null`).

**Constructing `originNodeURI` / `destinationNodeURI` (inside CFAssociation):**
Built directly from the DB columns `origin_node_identifier`, `origin_node_uri`, `origin_node_title`, `origin_node_target_type` (no JOIN). To support external references, the stored values are used as-is. CASE v1.1 uses `LinkGenURIDType`: `identifier` is not restricted to UUID, and `targetType` is a new field. When `targetType` is NULL, we still emit `null` in the response. (CASE v1.1 OpenAPI defines `targetType` as `anyOf` (`"CASE"` enum / `ext:` pattern) and does not permit null, but in practice unset targetType is common, so we include `null`. Strict conformance with `exclude_none` is on the Phase 2 list.)

**Constructing `subject` / `subjectURI` (inside CFDocument / CFItem):**
The DB columns `subject` (JSONB string array) and `subject_uri` (JSONB LinkURI object array) are emitted as-is. When NULL, the value is null (included as JSON `null`). CASE v1.1 defines both fields on CFDocument and CFItem.

**Constructing `conceptKeywordsURI` (inside CFItem):**
JOIN on `cf_concept_id` and use the CFConcept's `{title, identifier, uri}`. When `cf_concept_id` is NULL, the value is null (included as JSON `null`). CASE v1.1 defines `conceptKeywordsURI` as a single LinkURIDType (not an array). Same FK → JOIN pattern as CFItemTypeURI.

**Internal fields hidden from API responses:**
`cf_item.depth` is internal (used to render the tree view) and does not exist in CASE v1.1, so it is excluded from every API response (CFItem standalone and within CFPackage). Exclude it in the Pydantic schemas.

**CASE v1.1 fields omitted in Phase 1:**
`notes` (CFDocument / CFItem / CFAssociation), `alternativeLabel` (CFItem), and `extensions` (common, v1.1 new) are not persisted (see db-schema.md). These fields are **not** included in the Pydantic schemas (no API output — they are outside the `exclude_none=False` policy). They are optional in CASE v1.1, so omitting them does not affect compliance. Phase 2 will add the columns and the Pydantic fields (returning `null` when empty).

## Error response format

The CASE v1.1 `imsx_StatusInfo` shape. Fields are at the root (no wrapper):
```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Not found",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {"imsx_codeMinorFieldName": "sourcedId", "imsx_codeMinorFieldValue": "unknownobject"}
    ]
  }
}
```
- Field names start with lowercase (`imsx_codeMajor` ✓, `imsx_CodeMajor` ✗).
- `imsx_codeMajor`: `success` / `processing` / `failure` / `unsupported`.
- `imsx_severity`: `status` / `warning` / `error`.
- `imsx_description`: human-readable message (optional).
- `imsx_codeMinor`: optional. A nested object (not a string). `imsx_codeMinorFieldName` is always `"sourcedId"` for every error (per CASE v1.1 imsx convention).
- `imsx_codeMinorFieldValue`: `fullsuccess` / `invalid_sort_field` / `invalid_selection_field` / `forbidden` / `unauthorised_request` / `internal_server_error` / `unknownobject` / `server_busy` / `invalid_uuid`.
- HTTP status mapping: 400 → `failure/error`; 404 → `failure/error` + `unknownobject`; 405 → `failure/error` + `invalid_selection_field`; 429 → `failure/error` + `server_busy`; 500 → `failure/error` + `internal_server_error`.
- **429 (Server Busy):** defined for every endpoint in the CASE v1.1 OpenAPI. We do not implement rate limiting in Phase 1 explicitly, but API Gateway / Lambda throttling may yield 429. In that case we return the `server_busy` imsx_StatusInfo shape.
- We do not use FastAPI's default 422 Validation Error; a custom exception handler converts `RequestValidationError` into a **400** `invalid_selection_field` imsx_StatusInfo response.
- Requests to undefined sub-paths under `/{tenant}/ims/case/v1p1/...` return **404** (`unknownobject`) in the imsx_StatusInfo shape. FastAPI/Starlette's default 404 isn't in imsx form, so a catch-all route or a custom handler for the CASE API path translates it.

## Unsupported HTTP methods

The CASE API is read-only (GET). POST / PUT / DELETE / PATCH on CASE API paths return **405 Method Not Allowed**:
```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Method not allowed",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {"imsx_codeMinorFieldName": "sourcedId", "imsx_codeMinorFieldValue": "invalid_selection_field"}
    ]
  }
}
```
The response includes an `Allow: GET` header.

## `associationType` values

Valid values per CASE v1.1:
- `isChildOf` / `isPeerOf` / `isPartOf` / `exactMatchOf` / `precedes` / `isRelatedTo` / `replacedBy` / `exemplar` / `hasSkillLevel` / `isTranslationOf`.
- Extension pattern: values prefixed with `ext:` (regex: `(ext:)[a-zA-Z0-9\.\-_]+`) are also valid per CASE v1.1.

When importing from an external CASE source, validate against this enum plus the extension pattern; any value matching neither causes the association to be skipped with a warning. `ext:`-prefixed values are accepted.

## `adoptionStatus` values

Standard values per the CASE v1.1 information model:
- `Draft` / `Private Draft` / `Adopted` / `Deprecated`.

**Note:** CASE v1.1 OpenAPI types `adoptionStatus` as `string` (no enum constraint), so other values are technically valid. We recommend the standard values, but imports with non-standard values are not rejected (a warning is emitted and the value is stored as-is).

## Intentional differences from CASE v1.1

Notable design choices that diverge from the CASE v1.1 OpenAPI schema:

1. **Response wrapper structure:** strictly per the OpenAPI schema, single-resource fetches (`GET /CFDocuments/{id}`, etc.) return the DType at the root (no wrapper). We wrap with a root key — `{"CFDocument": {...}}` — to match the convention used by OpenSALT and other CASE implementations. **Exception:** `GET /CFPackages/{id}` returns the `CFPackageDType` at the top level (no wrapper) so that CASE clients reading `CFDocument` / `CFItems` from the root can interpret the framework. OpenSALT does the same.
2. **Empty arrays allowed:** `CFDocumentSetDType` (`minItems: 1`) and `CFAssociationSetDType` (`minItems: 1`) are documented as non-empty in the spec, but we return empty arrays when the result is 0 (see relevant sections).
3. **Invalid UUID → 400:** CASE v1.1 lumps invalid UUIDs into 404; we split into 400 (see validation section).
4. **`limit=0` accepted:** OpenAPI says `minimum: 1`, but we accept it and return an empty array (see pagination section).
5. **Pagination extended:** OpenAPI defines `limit` / `offset` etc. only on `GET /CFDocuments`; we extend them to every listing endpoint.
6. **`X-Total-Count` / `links` headers omitted:** not implemented in Phase 1 (see pagination section).
7. **Emitting `targetType: null`:** OpenAPI's anyOf does not permit null, but we include it for practical reasons (see LinkURI section).
8. **Tenant prefix:** `/{tenant}/ims/case/v1p1/` is an extension to support multi-tenancy (not in the CASE v1.1 spec).
9. **Service Discovery endpoint:** CASE v1.1 defines `GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json`. Not implemented in Phase 1; Phase 2 will revisit during Conformance work.
10. **405 Method Not Allowed:** not defined in CASE v1.1 OpenAPI, but reasonable for a GET-only API; we add it.
11. **401 / 403 not implemented:** defined for every endpoint in CASE v1.1 OpenAPI, but our CASE API is public (no auth) so they're irrelevant.
12. **CFDocument `creator` nullable:** required in CASE v1.1 OpenAPI (in the CFDocumentDType required list), but nullable in our DB to accommodate CSV imports that omit it. The API response can return `null`. External CFPackage import behavior: on create, missing / null / blank `creator` emits a warning and stores `null`; on update, missing / null retains the existing value silently, and a blank string emits a warning while still retaining the existing value (the existing `creator` is not overwritten with an empty string). Phase 2 will consider an empty-string default for Conformance.
13. **Required lookup fields nullable:** `description` / `hierarchyCode` on CFItemType, `hierarchyCode` on CFSubject and CFConcept, and `licenseText` on CFLicense are treated as nullable (see "Compliance note for required lookup fields" above).

## Content negotiation

- Web UI: `/`, `/{tenant}/`, `/{tenant}/cftree/doc/*` → always HTML (`Content-Type: text/html; charset=utf-8`). HTMX fragments (`/children/*`, `/detail/*`) are HTML too.
- `/{tenant}/uri/{uuid}` → Accept-based negotiation (see below).
- CASE API: `/{tenant}/ims/case/v1p1/CFItems/{uuid}` → always JSON (`Content-Type: application/json`).
- Admin API: → always JSON (`Content-Type: application/json`).

### `/{tenant}/uri/{uuid}` content negotiation

`/{tenant}/uri/{uuid}` is the canonical URI returned in `LinkURIDType.uri`. CASE clients (e.g., Open Badge Factory) fetch it to obtain JSON, while browsers expect a human-readable page. The handler inspects the `Accept` request header:

- Contains `application/json` or `application/ld+json` AND does NOT contain `text/html` → **303 See Other** redirect to the matching CASE API endpoint (e.g., CFItem → `/{tenant}/ims/case/v1p1/CFItems/{uuid}`).
- Otherwise (browsers, `*/*`, or absent Accept) → HTML detail page.

Resource types without an individual CASE API endpoint (`CFRubricCriterion`, `CFRubricCriterionLevel`) always serve HTML.

When `Accept`-based variants matter for caches, the response should also vary on `Accept`. CloudFront currently ignores `Accept` for cache key lookups, so deployments behind a shared cache must whitelist `Accept` (or split the URIs by path suffix) before relying on the negotiated response.

---

# CASE v1.1 API 仕様（日本語）

APIパス: `/{tenant}/ims/case/v1p1/` (conformance必須) + `/{tenant}/ims/case/v1p0/` (後方互換)

**パスパラメータ `{id}` の意味:** 全エンドポイントの `{id}` は CASE 識別子（DB の `identifier` カラム）を指す。内部PK（`id` カラム）ではない。

## エンドポイント一覧

CASE v1.1 準拠の 12 エンドポイント:

| Path | レスポンスルートキー | 説明 | CASE v1.1 |
|------|---------------------|------|-----------|
| GET /{tenant}/ims/case/v1p1/CFPackages/{id} | `{"CFDocument": {...}, "CFItems": [...], ...}` | パッケージ取得（CFPackageDType をトップレベルで返す、ラッパーなし） | ○ |
| GET /{tenant}/ims/case/v1p1/CFDocuments | `{"CFDocuments": [...]}` | 文書一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFDocuments/{id} | `{"CFDocument": {...}}` | 文書取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItems/{id} | `{"CFItem": {...}}` | 項目取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItemAssociations/{id} | `{"CFItem": {...}, "CFAssociations": [...]}` | 項目の関連一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociations/{id} | `{"CFAssociation": {...}}` | 関連取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id} | `{"CFAssociationGrouping": {...}}` | 関連グループ取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFConcepts/{id} | `{"CFConcepts": [...]}` | コンセプト取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItemTypes/{id} | `{"CFItemTypes": [...]}` | 項目種別取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFLicenses/{id} | `{"CFLicense": {...}}` | ライセンス取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFSubjects/{id} | `{"CFSubjects": [...]}` | 教科取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFRubrics/{id} | `{"CFRubric": {...}}` | ルーブリック取得 | ○ |

**独自拡張エンドポイント**（CASE v1.1 仕様外。テナント内の全リソースを一覧取得。利便性のため提供）:

| Path | レスポンスルートキー | 説明 |
|------|---------------------|------|
| GET /{tenant}/ims/case/v1p1/CFItemTypes | `{"CFItemTypes": [...]}` | 項目種別一覧 |
| GET /{tenant}/ims/case/v1p1/CFSubjects | `{"CFSubjects": [...]}` | 教科一覧 |
| GET /{tenant}/ims/case/v1p1/CFConcepts | `{"CFConcepts": [...]}` | コンセプト一覧 |
| GET /{tenant}/ims/case/v1p1/CFLicenses | `{"CFLicenses": [...]}` | ライセンス一覧 |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings | `{"CFAssociationGroupings": [...]}` | 関連グループ一覧 |
| GET /{tenant}/ims/case/v1p1/CFRubrics?doc={id} | `{"CFRubrics": [...]}` | ルーブリック一覧（`doc` 必須） |

**CFRubrics 一覧の `doc` パラメータについて:** CFRubric は CFDefinitions 系（CFItemType 等）と異なり、特定の CFDocument に所属する。CASE v1.1 の CFRubricDType には所属 Document を示すフィールドがないため、テナント全体で返すとどの Document のルーブリックか判別できない。そのため `doc` クエリパラメータ（CFDocument の identifier, UUID）を**必須**とする。`doc` 未指定は 400、不正な UUID は 400、Document が存在しない場合は 404 を返す。

**Set 型エンドポイント（`/CFConcepts/{id}`, `/CFSubjects/{id}`, `/CFItemTypes/{id}`）**: CASE v1.1 仕様に従い、それぞれ Set 型（`CFConceptSetDType`, `CFSubjectSetDType`, `CFItemTypeSetDType`）を返す。配列の先頭は要求されたリソース、後続は `hierarchyCode` の階層下に位置する子孫リソースとなる。子孫の判定は文字列マッチで行い、対象の `hierarchyCode` を `<root>` とすると `<root>.` で始まる `hierarchyCode` を持つレコードを子孫として含める（例: `<root>` が `"1"` の場合、`"1.1"`, `"1.2.3"` 等が該当）。子孫の並び順は `hierarchyCode` の昇順（同値時は `identifier` 昇順）。要求されたリソースの `hierarchyCode` が NULL の場合、または該当する子孫が存在しない場合は、要求されたリソース 1 件のみを返す。`/CFLicenses/{id}` は単一オブジェクト `CFLicenseDType` を返す（Set 型ではない）。

**lookup リソースの必須フィールドに関する準拠性（Phase 2 対応）:**
CASE v1.1 OpenAPI 仕様では、lookup リソースの一部フィールドが "required"（non-nullable）として定義されている:
- CFItemType: `description`, `hierarchyCode`
- CFSubject: `hierarchyCode`
- CFConcept: `hierarchyCode`
- CFLicense: `licenseText`

Phase 1 ではこれらのフィールドを DB 上 nullable として扱い、値がない場合は `null` を返す（CSV インポートで自動生成された lookup レコードではこれらのフィールドは常に NULL）。Phase 2 の 1EdTech Conformance テスト対応で、`null` の代わりに空文字列 `""` を返すか、スキーマ上 nullable として扱うかを検討する。

## CFPackage レスポンス構造

レスポンス自体が `CFPackageDType` で、ラッパーキーは付けない。CASE v1.1 仕様および OpenSALT と同形式 — クライアントはトップレベルから `CFDocument` / `CFItems` を直接読む。

```json
{
  "CFDocument": {...},
  "CFItems": [...],
  "CFAssociations": [...],
  "CFDefinitions": {
    "CFItemTypes": [...],
    "CFSubjects": [...],
    "CFConcepts": [...],
    "CFLicenses": [...],
    "CFAssociationGroupings": [...]
  },
  "CFRubrics": [...]
}
```
- `CFItems` と `CFAssociations` はデータがなくても空配列 `[]` として常に含める（CASE v1.1 OpenAPI では `CFItems` / `CFAssociations` は required ではなく省略可能だが、クライアントの利便性のため常に含める）。いずれも `cf_document_id` でフィルタする（このドキュメントに属するリソースのみ。他ドキュメントからこのドキュメントのアイテムを参照する Association は含まない）
- `CFDefinitions` はデータがなければオブジェクトごと省略する。内部の各キーもデータがなければ省略する（`exclude_none=False` グローバルポリシーの例外。CFDefinitions 内の空配列キーは `null` として含めるのではなく、キー自体を省略する。Pydantic のカスタムシリアライザ（`model_serializer` 等）で空配列のキーを除外する。`exclude_none=True` は `None` 値のみ除外し空配列 `[]` は除外しないため、それだけでは不十分）
- `CFDefinitions` に含めるスコープ: このドキュメントのリソースから参照されている定義のみ（テナント内の全定義ではない）。具体的には: CFItemTypes = ドキュメント配下の CFItem が `cf_item_type_id` で参照するもの、CFSubjects = CFDocument および配下の CFItem の `subject_uri` から参照されるもの、CFConcepts = ドキュメント配下の CFItem が `cf_concept_id` で参照するもの、CFLicenses = CFDocument または配下の CFItem が `cf_license_id` で参照するもの、CFAssociationGroupings = ドキュメント配下の CFAssociation が `cf_association_grouping_id` で参照するもの
- `CFRubrics` は `CFItems` / `CFAssociations` と同様に空配列 `[]` として常に含める（`CFRubrics` は配列型であり、CFDefinitions のオブジェクト型省略ルールとは異なる）
- **CFPackage 内のソート順**: CFItems・CFAssociations・CFDefinitions 内の各配列は `identifier ASC` で並べる（一覧エンドポイントのデフォルトソート順と統一し、決定的な出力を保証する）
- **CFPackage 内のリソーススキーマ（CFPckg* 型）**: CASE v1.1 では CFPackage 内のリソースはスタンドアロン型とは異なる CFPckg* 型を使用する:
  - `CFPckgDocument`: スタンドアロン `CFDocument` から `CFPackageURI` を**除外**（CFPackage 自体がこのドキュメントを包含しているため冗長）
  - `CFPckgItem`: スタンドアロン `CFItem` から `CFDocumentURI` を**除外**（CFPackage のコンテキストからドキュメントが明確なため冗長）
  - `CFPckgAssociation`: スタンドアロン `CFAssociation` から `CFDocumentURI` を**除外**（同上）
  - CFDefinitions 内の各リソース（CFItemType, CFSubject 等）はスタンドアロンと同一スキーマ
  - Pydantic で CFPckg* 用の派生スキーマを定義し、`CFPackageURI` / `CFDocumentURI` フィールドを除外する

レスポンスにカスタムラッパー (`{"data": ...}` 等) を**追加してはならない**。
**null フィールドの扱い:** null 許容フィールドはレスポンスに含める方針とする（Pydantic の `exclude_none=False`）。全エンドポイントで同一の方針を適用し、一貫性を優先する。
エラー時は `{"imsx_codeMajor": "failure", ...}` をルートレベルに直接返す（エラー形式参照）。

## CFItemAssociations レスポンス構造

CASE v1.1 の `CFAssociationSetDType` 形式。対象 CFItem と、そのアイテムに関連する全 Association を返す:
```json
{
  "CFItem": {...},
  "CFAssociations": [...]
}
```
- `CFItem`: 対象アイテムのスタンドアロンスキーマ（`GET /CFItems/{id}` と同一。`CFDocumentURI` を含む）
- `CFAssociations`: 対象アイテムに関連する全 Association の配列。各 Association は `CFDocumentURI` を**含まない**（CASE v1.1 の `CFPckgAssociationDType`。CFPackage 内の CFAssociation と同じスキーマ）
- `CFAssociations` はデータがなくても空配列 `[]` として常に含める（CASE v1.1 OpenAPI の CFAssociationSetDType は `CFAssociations` を required + `minItems: 1` と定義しているが、Association がないアイテムに対して空配列を返すのは実運用上必要なため、空配列を許容する）

## バリデーション（全エンドポイント共通）

**テナントUUID:**
- `{tenant-uuid}` が UUID 形式でない → **400** (`imsx_codeMinorFieldValue: invalid_uuid`)（CASE v1.1 仕様では invalid UUID を 404 で返す定義もあるが、本システムでは UUID 形式不正と リソース未存在を区別するため 400 を返す）
- UUID 形式だがテナントが存在しない → **404** (`imsx_codeMinorFieldValue: unknownobject`)

**リソースID:**
- 全リソース取得エンドポイントはテナントスコープ内で検索する（パスの `{tenant-uuid}` で指定されたテナント内のみ）
- `{id}`（`/CFItems/{id}`, `/CFDocuments/{id}` 等）が UUID 形式でない → **400** (`imsx_codeMinorFieldValue: invalid_uuid`)
- UUID 形式だがテナント内にリソースが存在しない → **404** (`imsx_codeMinorFieldValue: unknownobject`)
- `GET /CFItemAssociations/{id}` で `{id}` のアイテムが存在しない → **404** (`imsx_codeMinorFieldValue: unknownobject`)（空配列ではなく404を返す）
- `GET /CFItemAssociations/{id}` の検索スコープ: テナント内の全ドキュメントから `origin_node_identifier = {id}` OR `destination_node_identifier = {id}` の Association を返す（アイテムが属するドキュメントに限定しない）

**スコープ:**
- `/uri/{uuid}` はテナントスコープ内で検索する。別テナントの UUID を指定した場合は **404**
- `/uri/{uuid}` の検索順序: cf_document → cf_item → cf_association → cf_item_type → cf_subject → cf_concept → cf_license → cf_association_grouping（最初にヒットした時点で検索を打ち切る）。同一 UUID が複数テーブルに存在する場合（テーブル間の UNIQUE 制約はないため理論上可能）、この順序で最初にマッチしたリソースを返す

## ページネーション

CASE v1.1準拠。全一覧エンドポイントに `limit`(デフォルト100, 最大500) / `offset`(デフォルト0) を実装。
対象: `CFDocuments`, `CFItemAssociations/{id}`, `CFItemTypes`, `CFSubjects`, `CFConcepts`, `CFLicenses`, `CFAssociationGroupings`（レスポンスが配列の全エンドポイント）。CASE v1.1 OpenAPI ではページネーションパラメータは `GET /CFDocuments` のみに定義されているが、本システムでは利便性のため全一覧エンドポイントに拡張適用する。
`CFPackages/{id}` はページネーション対象外。CASE v1.1 仕様に従い、CFPackage 内の CFItems・CFAssociations・CFDefinitions は全件を返す。**注意**: API Gateway のレスポンスペイロード上限は 10MB。大規模ドキュメント（10,000+ アイテム）ではこの制限に達する可能性がある。制限超過時は API Gateway が 502 を返す。必要に応じて Lambda Function URL 経由での直接アクセスを検討する（Phase 2 以降）。
`sort` / `orderBy` / `filter` / `fields` パラメータは Phase 1 では実装しない（無視する）。
レスポンスに総件数は含めない。CASE v1.1 OpenAPI スキーマでは `GET /CFDocuments` に `X-Total-Count` レスポンスヘッダーと `links`（next, last, first, prev）が定義されているが、本システムでは Phase 1 では実装しない（Phase 2 で検討）。
デフォルトソート順: 全一覧エンドポイントは `identifier ASC` で並べる（決定的な順序を保証し、ページ間の重複・欠落を防ぐ）。
スコープ: 全一覧エンドポイントはテナント内の全件を返す（ドキュメントでフィルタリングしない）。`CFDocuments` はテナント内の全ドキュメント、`CFItemTypes` / `CFSubjects` / `CFConcepts` / `CFLicenses` / `CFAssociationGroupings` はテナント内の全 lookup リソースを返す。`CFItems/{id}/associations` はテナント内の全ドキュメントを横断して検索する（api-spec.md バリデーション節参照）。CFPackage 内の CFDefinitions はドキュメントから参照されている定義のみに絞り込むが、一覧APIは絞り込まない。

**バリデーション:**
- `limit` = 0 → 空配列を返す（有効なリクエストとして扱う。CASE v1.1 OpenAPI は `minimum: 1` を定義しているが、実用上 `limit=0` は空結果を返す有効なリクエストとして扱う）
- `limit` < 0 → 400 (`invalid_selection_field`)
- `limit` > 500 → 500 として扱う（エラーにしない）
- `limit` が整数でない → 400 (`invalid_selection_field`)
- `offset` < 0 → 400 (`invalid_selection_field`)
- `offset` が整数でない → 400 (`invalid_selection_field`)
- `offset` > 100000 → 100000 として扱う（`limit` の cap と同様。PostgreSQL の OFFSET に渡す上限を設ける）
- `offset` が総件数以上 → 空配列を返す（エラーではない）

## レスポンスヘッダー（Cache-Control）

**正常レスポンス（200）:** 全 CASE API エンドポイントに `Cache-Control: public, max-age=3600` を設定する（public/private テナント共通）。

**エラーレスポンス（4xx/5xx）:** `Cache-Control` を設定しない。CloudFront のデフォルト Error Caching Minimum TTL（デフォルト10秒）に委ねる。インポート直後に一部リソースの 404 キャッシュが残る可能性があるが、短時間で失効する。

**例外:**
- ヘルスチェック（`GET /health`）: `Cache-Control: no-store`（下記参照）
- v1p0 リダイレクト（301）: `Cache-Control` を設定しない（HTTP 仕様上、301 はデフォルトでキャッシュ可能）

## ヘルスチェック

```
GET /health
```
レスポンス (200):
```json
{"status": "ok"}
```
- 認証不要、テナントパス不要
- `Content-Type: application/json` で返す
- `Cache-Control: no-store` を設定する（CloudFront でキャッシュさせない）
- DB接続確認は行わない（Lambda コールドスタートの高速化を優先）

## v1p0 後方互換

`/ims/case/v1p0/` パスへのリクエストは `/ims/case/v1p1/` に 301リダイレクト。
CASE API は GET のみのため 301 で問題ない（POST でメソッドが変わるリスクなし）。
ルーターを二重に実装しない。`src/main.py` にミドルウェアを1つ追加して一括処理する。
リダイレクト先はパスの `v1p0` を `v1p1` に置換したもの（クエリパラメータはそのまま引き継ぐ）。
`Cache-Control` は設定しない（301 は HTTP 仕様上デフォルトでキャッシュ可能であり、CloudFront・ブラウザがデフォルト挙動でキャッシュする。恒久的なリダイレクトなのでこの挙動で問題ない）。

```python
# src/main.py のミドルウェア例
@app.middleware("http")
async def redirect_v1p0(request, call_next):
    if "/ims/case/v1p0/" in request.url.path:
        new_path = request.url.path.replace("/ims/case/v1p0/", "/ims/case/v1p1/")
        new_url = str(request.url).replace(request.url.path, new_path)
        return RedirectResponse(url=new_url, status_code=301)
    return await call_next(request)
```

## 日付・タイムスタンプ形式

- **TIMESTAMP 型フィールド**（`lastChangeDateTime`）: ISO 8601 UTC（末尾 `Z`）で出力する（例: `"2025-10-08T12:00:00Z"`）。ミリ秒は含めない。Pydantic のシリアライズ設定で統一する
- **DATE 型フィールド**（`statusStartDate`, `statusEndDate`）: `YYYY-MM-DD` 形式で出力する（例: `"2018-03-30"`）。CASE v1.1 仕様の `xsd:date` 型に準拠

## LinkURI型

`CFPackageURI`, `CFDocumentURI`, `CFOriginNodeURI`, `CFDestinationNodeURI`, `CFItemTypeURI` 等は
文字列ではなく複合オブジェクト:
```json
{"title": "文書タイトル", "identifier": "uuid", "uri": "https://..."}
```
Pydantic で `LinkURIType` クラスを定義して共有する (`src/schemas/common.py`)。
DBには `_uri` (VARCHAR) と `_identifier` (UUID) カラムを持ち、`title` はJOINまたはアプリ層で解決する。
JOINで解決できない外部参照に備え、cf_association の originNodeURI / destinationNodeURI は `_title` カラムも保持する。

**CFPackageURI の構築:**
`CFPackageURI` はDBに保存せず、APIレスポンス生成時にアプリ層で構築する:
- `title` = CFDocument.title
- `identifier` = CFDocument.identifier
- `uri` = `{BASE_URL}/{tenant}/ims/case/v1p1/CFPackages/{CFDocument.identifier}`

外部インポートしたドキュメントでも、CFPackageURI.uri は**自サーバーのAPIエンドポイント**を指す（CFDocument.uri は外部URIを保持するが、CFPackageURI.uri は「このパッケージをどこで取得できるか」を示すため自サーバーを指す）。

**CFDocumentURI の構築（CFItem / CFAssociation 内）:**
`cf_document_id` FK で JOIN し、CFDocument の `{title, identifier, uri}` を使用する。CASE v1.1 OpenAPI では CFDocumentURI は CFItemDType では **required**、CFAssociationDType では **optional** だが、本システムでは `cf_document_id` が NOT NULL のため常に値があり、両方のケースで CFDocumentURI を含める。

**CFItemTypeURI の構築（CFItem 内）:**
`cf_item_type_id` FK で JOIN し、CFItemType の `{title, identifier, uri}` を使用する。`cf_item_type_id` が NULL の場合は `CFItemTypeURI` も null（`exclude_none=False` のため JSON に `null` として含まれる）。`CFItemType`（文字列フィールド）は同じ JOIN で CFItemType の `title` を使用する。`cf_item_type_id` が NULL の場合は `CFItemType` も null。

**licenseURI の構築（CFDocument / CFItem 内）:**
`cf_license_id` FK で JOIN し、CFLicense の `{title, identifier, uri}` を使用する。`cf_license_id` が NULL の場合は `licenseURI` も null（`exclude_none=False` のため JSON に `null` として含まれる）。CFItemTypeURI と同じ FK → JOIN パターン。

**CFAssociationGroupingURI の構築（CFAssociation 内）:**
`cf_association_grouping_id` FK で JOIN し、CFAssociationGrouping の `{title, identifier, uri}` を使用する。`cf_association_grouping_id` が NULL の場合は null（`exclude_none=False` のため JSON に `null` として含まれる）。

**originNodeURI / destinationNodeURI の構築（CFAssociation 内）:**
DBの `origin_node_identifier`, `origin_node_uri`, `origin_node_title`, `origin_node_target_type` カラムから直接構築する（JOINしない）。外部参照のリソースに対応するため、保存時点の値をそのまま使用する。CASE v1.1 では `LinkGenURIDType` を使用し、`identifier` は UUID 制限なし、`targetType` フィールドが追加されている。`targetType` は NULL の場合レスポンスに null として含める（CASE v1.1 OpenAPI では `targetType` は anyOf（`"CASE"` enum / `ext:` パターン）で null を許容しない定義だが、実運用上 targetType が未設定のケースは一般的であるため null を含める方針とする。strict な準拠が必要な場合は `exclude_none` で省略する対応を Phase 2 で検討する）。

**subject / subjectURI の構築（CFDocument / CFItem 内）:**
DB の `subject` JSONB カラム（文字列配列）と `subject_uri` JSONB カラム（LinkURI オブジェクト配列）をそのまま出力する。NULL の場合は null（`exclude_none=False` のため JSON に `null` として含まれる）。CASE v1.1 では `subject` と `subjectURI` は CFDocument と CFItem の両方に定義されている。

**conceptKeywordsURI の構築（CFItem 内）:**
`cf_concept_id` FK で JOIN し、CFConcept の `{title, identifier, uri}` を使用する。`cf_concept_id` が NULL の場合は null（`exclude_none=False` のため JSON に `null` として含まれる）。CASE v1.1 仕様では `conceptKeywordsURI` は単一の LinkURIDType（配列ではない）。CFItemTypeURI と同じ FK → JOIN パターン。

**API レスポンスに含めない内部フィールド:**
`cf_item.depth` は内部用フィールド（ツリービューの描画用）であり、CASE v1.1 仕様に存在しないため、全 API レスポンス（CFItem, CFPackage 内の CFItems）に含めない。Pydantic スキーマで除外すること。

**Phase 1 で省略する CASE v1.1 フィールド:**
`notes`（CFDocument / CFItem / CFAssociation）、`alternativeLabel`（CFItem）、`extensions`（全リソース共通、v1.1 新規）は DB に保存しない（db-schema.md 参照）。これらのフィールドは Pydantic スキーマに**含めない**（API レスポンスに一切出力しない。`exclude_none=False` ポリシーの対象外）。CASE v1.1 ではこれらは任意フィールドであり、省略しても準拠性に影響しない。Phase 2 でカラム追加時に Pydantic スキーマにも追加し、`null` として出力されるようにする。

## エラーレスポンス形式

CASE v1.1 の imsx_StatusInfo 形式。ルートレベルに直接フィールドを配置する（ラッパーオブジェクトなし）:
```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Not found",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {"imsx_codeMinorFieldName": "sourcedId", "imsx_codeMinorFieldValue": "unknownobject"}
    ]
  }
}
```
- フィールド名は全て小文字始まり（`imsx_codeMajor` ○、`imsx_CodeMajor` ✗）
- `imsx_codeMajor`: `success` / `processing` / `failure` / `unsupported`
- `imsx_severity`: `status` / `warning` / `error`
- `imsx_description`: 人間向けの説明文字列（任意）
- `imsx_codeMinor`: 任意。ネストされたオブジェクト（文字列ではない）。`imsx_codeMinorFieldName` は全エラーで `"sourcedId"` 固定（CASE v1.1 imsx 標準の慣例に従う）
- `imsx_codeMinorFieldValue`: `fullsuccess` / `invalid_sort_field` / `invalid_selection_field` / `forbidden` / `unauthorised_request` / `internal_server_error` / `unknownobject` / `server_busy` / `invalid_uuid`
- HTTPステータスコード対応: 400→`failure/error`, 404→`failure/error`+`unknownobject`, 405→`failure/error`+`invalid_selection_field`, 429→`failure/error`+`server_busy`, 500→`failure/error`+`internal_server_error`
- **429 (Server Busy):** CASE v1.1 OpenAPI で全エンドポイントに定義されている。Phase 1 では明示的なレート制限を実装しないが、API Gateway / Lambda のスロットリングにより 429 が返される可能性がある。その場合は imsx_StatusInfo 形式で `server_busy` を返す
- FastAPI のデフォルト 422 Validation Error レスポンスは使用せず、imsx_StatusInfo 形式の **400**（`invalid_selection_field`）に変換する。カスタム例外ハンドラで RequestValidationError をキャッチし、imsx_StatusInfo 形式で返す
- CASE API パス配下（`/{tenant}/ims/case/v1p1/...`）の未定義サブパスへのアクセスには **404**（`unknownobject`）を imsx_StatusInfo 形式で返す。FastAPI/Starlette のデフォルト 404 レスポンスは imsx_StatusInfo 形式ではないため、CASE API パス配下の catch-all ルートまたはカスタム例外ハンドラで変換する

## 非対応HTTPメソッド

CASE API は読み取り専用（GET のみ）。POST / PUT / DELETE / PATCH を CASE API パスに送信した場合は **405 Method Not Allowed** を返す:
```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Method not allowed",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {"imsx_codeMinorFieldName": "sourcedId", "imsx_codeMinorFieldValue": "invalid_selection_field"}
    ]
  }
}
```
`Allow: GET` レスポンスヘッダーを含める。

## associationType 列挙値

CASE v1.1 で定義されている有効値:
- `isChildOf` / `isPeerOf` / `isPartOf` / `exactMatchOf` / `precedes` / `isRelatedTo` / `replacedBy` / `exemplar` / `hasSkillLevel` / `isTranslationOf`
- 拡張パターン: `ext:` プレフィックス付きの値（正規表現: `(ext:)[a-zA-Z0-9\.\-_]+`）も CASE v1.1 で有効として定義されている

外部CASEソースインポート時にこの列挙値および拡張パターンを検証し、いずれにも該当しない値の場合は該当 Association をスキップして警告を出力する。`ext:` プレフィックス付きの値は有効な associationType として受け入れる。

## adoptionStatus 列挙値

CASE v1.1 情報モデルで定義されている標準値:
- `Draft` / `Private Draft` / `Adopted` / `Deprecated`

**注意:** CASE v1.1 OpenAPI スキーマでは `adoptionStatus` の型は `string`（enum 制約なし）のため、上記以外の値も技術的には有効。本システムでは上記の値を推奨するが、インポート時に上記以外の値が指定されてもエラーにしない（警告のみ出力し、値をそのまま保存する）。

## CASE v1.1 公式仕様との意図的差異

以下は CASE v1.1 OpenAPI スキーマとの差異のうち、意図的な設計判断として本システムで採用しているもの:

1. **レスポンスラッパー構造:** OpenAPI スキーマの strict な読み方では、単一リソース取得（`GET /CFDocuments/{id}` 等）は DType をルートに直接返す（ラッパーなし）。本システムでは `{"CFDocument": {...}}` のようにルートキーでラップする。これは OpenSALT 等の既存 CASE 実装の慣行に合わせた設計。**例外:** `GET /CFPackages/{id}` は `CFPackageDType` をトップレベルで返す（ラッパーなし）。これは CASE クライアントがトップレベルから `CFDocument` / `CFItems` を読めるようにするため。OpenSALT も同じ形式
2. **空配列の許容:** `CFDocumentSetDType` (`minItems: 1`) や `CFAssociationSetDType` (`minItems: 1`) に対して、0 件時に空配列を返す（上記各セクション参照）
3. **invalid UUID → 400:** CASE v1.1 では invalid UUID も 404 に含むが、本システムでは 400 に分離（上記バリデーション節参照）
4. **`limit=0` の許容:** OpenAPI は `minimum: 1` だが、本システムでは空配列を返す有効リクエストとして扱う（上記ページネーション節参照）
5. **ページネーション拡張:** OpenAPI では `limit`/`offset` 等は `GET /CFDocuments` のみに定義。本システムでは全一覧エンドポイントに適用する独自拡張
6. **`X-Total-Count` / `links` ヘッダー省略:** Phase 1 では実装しない（上記ページネーション節参照）
7. **`targetType: null` の出力:** OpenAPI の anyOf 定義上 null は有効値でないが、実運用上必要なため null を含める（上記 LinkURI 型節参照）
8. **テナントプレフィックス:** `/{tenant}/ims/case/v1p1/` パスは CASE v1.1 仕様にない独自拡張（マルチテナント対応）
9. **Service Discovery エンドポイント:** CASE v1.1 では `GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json` が定義されている。Phase 1 では未実装。Phase 2 の Conformance テスト対応で実装を検討する
10. **405 Method Not Allowed:** CASE v1.1 OpenAPI に定義はないが、GET only の API として合理的なため追加
11. **401/403 未実装:** CASE v1.1 OpenAPI で全エンドポイントに定義されているが、CASE API は public（認証不要）のため不要
12. **CFDocument `creator` の nullable 化:** CASE v1.1 OpenAPI では `creator` は required（CFDocumentDType の required リストに含まれる）だが、CSV インポートで未指定のケースに対応するため DB では nullable。API レスポンスで `null` が返る可能性がある。外部 CASE CFPackage インポート時の挙動: 新規作成時に `creator` が欠落・null・空白文字列であれば警告を出力した上で `null` で保存する。更新時は欠落・null は既存値を保持（無警告）、空白文字列の場合は警告を出した上で既存値を保持する（既存 creator を空文字に上書きしない）。Phase 2 の Conformance テスト対応で空文字列デフォルト化を検討する
13. **lookup リソースの required フィールドの nullable 化:** CFItemType の `description`/`hierarchyCode`、CFSubject の `hierarchyCode`、CFConcept の `hierarchyCode`、CFLicense の `licenseText` を nullable として扱う（上記「lookup リソースの必須フィールドに関する準拠性」節参照）

## コンテントネゴシエーション

- Web UI: `/`, `/{tenant}/`, `/{tenant}/cftree/doc/*` → 常に HTML（`Content-Type: text/html; charset=utf-8`）。HTMX フラグメント（`/children/*`, `/detail/*`）も HTML
- `/{tenant}/uri/{uuid}` → Accept ヘッダによるネゴシエーション（下記参照）
- CASE API: `/{tenant}/ims/case/v1p1/CFItems/{uuid}` → 常に JSON（`Content-Type: application/json`）
- Admin API: → 常に JSON（`Content-Type: application/json`）

### `/{tenant}/uri/{uuid}` のコンテントネゴシエーション

`/{tenant}/uri/{uuid}` は `LinkURIDType.uri` で返される正規 URI であり、CASE クライアント（Open Badge Factory 等）は JSON 取得のためこの URI を直接 fetch する。一方、ブラウザは人間向けページを期待する。そのためハンドラは `Accept` リクエストヘッダを参照する:

- `application/json` または `application/ld+json` を含み、かつ `text/html` を含まない → 該当する CASE API エンドポイント（例: CFItem → `/{tenant}/ims/case/v1p1/CFItems/{uuid}`）へ **303 See Other** リダイレクト
- それ以外（ブラウザ、`*/*`、Accept 未指定）→ HTML 詳細ページ

CASE API エンドポイントを持たないリソース種別（`CFRubricCriterion`、`CFRubricCriterionLevel`）は常に HTML を返す。

Accept 別レスポンスをキャッシュ層に正しく反映させたい場合は、レスポンスを `Accept` でバリエーション分けする必要がある。CloudFront は現状 `Accept` をキャッシュキーに含めないため、共有キャッシュ配下で本ネゴシエーション結果に依存する場合は `Accept` ホワイトリスト化、または別パス分割を事前に検討すること。
