# Import / Export Business Logic

**Language of error / warning messages:** error and warning messages throughout this document are **standardized in English** (matching all other error messages in the CASE API and Admin API). Explanatory text (conditions and behavior) is given in both English and Japanese.

## CSV import flow

```
1. Read the CSV file; auto-detect the format
2. Parse metadata rows
2.5. (OpenSALT only) Pre-scan `Is Part Of`
3. Create or update the CFDocument
4. Parse and validate each row
5. Auto-create lookup tables (CFItemType, CFSubject, CFConcept)
6. Upsert CFItem
7. Generate isChildOf CFAssociations
8. Compute `depth`
9. Print the result report
```

**Transaction strategy:**
Steps 3–8 run in a single transaction. Step 4 validation errors are filtered out before any DB write, so in principle no error occurs inside the transaction. If a DB-level error happens nonetheless, the entire transaction is rolled back and the import fails (no partial commit). NFR-6.5's "skip per row" applies to the validation stage, not the DB-write stage.

**Preventing concurrent imports on the same document:**
On update (`--doc` etc.), Step 3 acquires `SELECT ... FOR UPDATE` on the target CFDocument row and holds it until the transaction ends. This serializes concurrent imports on the same document and prevents races between the isChildOf delete-all → regenerate sequence (e.g., duplicate associations). On create, no lock is needed (the document doesn't exist yet).

### Step 1: file read and format detection

**Encoding:** the file is read as UTF-8. A BOM (`\xEF\xBB\xBF`) at the start is silently skipped (Python's `utf-8-sig` behavior). If the file can't be decoded as UTF-8, the import fails ("CSV file is not valid UTF-8").

**UUID case sensitivity:** UUID identifiers are compared **case-insensitively** (upsert matching, `parentIdentifier` resolution, `/uri/{uuid}` lookup, etc.). PostgreSQL's UUID type is case-insensitive — `D86774F2-...` equals `d86774f2-...`. On create we normalize to lowercase when storing. UUIDs from external imports are stored as-is, and the case-insensitive rule still applies on comparison.

**compeito-local fields are never touched by import.** `display_order` (manual list ordering on `tenants` / `cf_documents`) is not a CASE field and is not part of any import format. Import only writes CASE-derived fields, so re-importing a CFPackage **preserves** an existing `display_order`. It is likewise excluded from CASE/CSV/xlsx export.

For format auto-detection rules see [csv-format.md](./csv-format.md).

### Step 2: metadata parsing

Lines starting with `#` are parsed as key/value pairs and mapped to CFDocument fields. CLI flags win over metadata when both are present.

**Empty-string handling (applies to every metadata field):** for every single-valued metadata field (`#title`, `#version`, `#creator`, `#publisher`, `#description`, `#language`, `#adoption_status`, `#official_source_url`, `#license`, `#status_start_date`, `#status_end_date`), an empty string (empty after trimming surrounding whitespace) is treated as NULL (unspecified). On create the field becomes NULL; on update the existing value is preserved (same as omitting the key entirely).

### Step 2.5: `Is Part Of` pre-scan (OpenSALT only)

For OpenSALT format, Step 3 needs the `Is Part Of` column to identify the CFDocument. Since `Is Part Of` lives on each data row and is needed before Step 4 (row parsing), we pre-scan the entire `Is Part Of` column. The first non-empty value becomes the CFDocument identifier; rows with a different value are recorded for a Step 4 warning ("Row N: Is Part Of 'xxx' differs from document identifier 'yyy', ignored"). If every row is empty, treat the import as a new document. The pre-scan only reads the `Is Part Of` column; other columns are untouched.

### Step 3: CFDocument create / update

| Condition | Behavior |
|-----------|----------|
| `--doc` omitted (custom / simple) | Create a new CFDocument; `identifier` is auto-generated UUID v4 |
| `--doc` omitted (OpenSALT, non-empty `Is Part Of`) | Use `Is Part Of` as the CFDocument identifier and look up an existing one in the tenant. Update if found; create otherwise (`identifier` = the `Is Part Of` value). If `Is Part Of` is not a valid UUID, the import fails ("Is Part Of value is not a valid UUID: '...'") |
| `--doc` omitted (OpenSALT, empty `Is Part Of`) | Create a new CFDocument; `identifier` is auto-generated UUID v4 |
| `--doc {uuid}` specified, exists in the tenant | Update the existing CFDocument (rules below). For OpenSALT, `Is Part Of` is ignored |
| `--doc {uuid}` specified, not in the tenant | Fail ("Document not found: '{uuid}'") |

**On create:**
- `identifier` → per the table above; either auto-generated UUID v4 or the OpenSALT `Is Part Of` value.
- `uri` → `{BASE_URL}/{tenant_id}/uri/{identifier}`.
- `title` → priority `--doc-title` > `#title`. Empty strings are treated as "unspecified" (empty title is not allowed). If neither is provided, the import fails ("Document title is required").
- `version` → priority `--doc-version` > `#version`. Empty strings are treated as "unspecified". If neither is provided, NULL.
- `language` → `#language` value. NULL if unspecified.
- Other fields → from the corresponding metadata row, NULL otherwise.
- `last_change_date_time` → the import-time UTC timestamp.

**On update:**
- Metadata row with a value → overwrite the corresponding CFDocument field.
- Metadata row without a value (the key itself is missing) → preserve the existing value (no NULL overwrite).
- `last_change_date_time` → overwrite with the import-time UTC timestamp.
- `title` → priority `--doc-title` > `#title` > existing value.
- `version` → priority `--doc-version` > `#version` > existing value.

### Step 4: row parsing and validation

Each row is converted to the internal representation. Errors are collected with row numbers and reported at the end.

**Validation rules:**
- `fullStatement` is empty or whitespace-only → skip the row (warning "Row N: fullStatement is empty, skipped"). Trim surrounding whitespace first (empty after trimming = empty). The trimmed value is stored (surrounding whitespace is removed). **Simple format**: compute depth from leading whitespace **before** trimming (parse indent → trim → empty check).
- `Identifier` is empty → auto-generate UUID v4.
- `Identifier` is not a UUID → error (skip the row; warning "Row N: Invalid Identifier 'xxx', skipped").
- **Duplicate `Identifier` within the same CSV** → the later row wins (warning "Row N: Duplicate Identifier 'xxx', overwriting Row M").
- Parse `educationLevel` → split on comma into a string array (trim each value; drop empties after trimming). `"09, 10, 11"` → `["09", "10", "11"]`; `"09,,11"` → `["09", "11"]`.
- Parse `conceptKeywords` → split on comma into a string array (trim each value; drop empties after trimming). `"分析, 評価"` → `["分析", "評価"]`; `"分析,,評価"` → `["分析", "評価"]`.
- `parentIdentifier` / `Is Child Of` is non-empty but not a UUID → warning ("Row N: parentIdentifier 'xxx' is not a valid UUID, treated as root"). Treat as root level.
- `sequenceNumber` → convert to integer. On failure, error (skip the row; warning "Row N: Invalid sequenceNumber 'xxx', skipped"). Values outside the PostgreSQL INTEGER range (-2147483648 .. 2147483647) are treated as conversion failure too.
- `statusStartDate` → when non-empty, validate `YYYY-MM-DD`. On invalid format or value (e.g., `2025-13-45`), emit a warning ("Row N: Invalid statusStartDate 'xxx', set to null") and treat the field as NULL (don't skip the row).
- `statusEndDate` → same rule as `statusStartDate` (warning name uses `statusEndDate`).
- `license` → same lookup pattern as CFItemType. Step 5 find-or-creates `cf_license` and sets the FK on `cf_item.cf_license_id`. Empty cell → NULL on create, keep existing on update.
- `language` → when non-empty, validate length ≤ 10. If too long, emit a warning ("Row N: language 'xxx' exceeds 10 characters, set to null") and treat as NULL (don't skip the row; prevents the `VARCHAR(10)` constraint from rolling back the whole transaction).

**Metadata validation:**
- `#adoption_status` → values outside the standard set (`Draft` / `Private Draft` / `Adopted` / `Deprecated`) emit a warning ("Invalid adoption_status 'xxx', storing as-is") and the value is stored as-is (no error). It is also returned as-is in API responses.
- `#language` → validate length ≤ 10. Too long → warning ("Metadata #language 'xxx' exceeds 10 characters, set to null"); treat as NULL.
- `#status_start_date` / `#status_end_date` → when non-empty, validate `YYYY-MM-DD`. Invalid format or value → warning ("Invalid #status_start_date 'xxx', set to null"); treat as NULL.

### Step 5: lookup table auto-creation

Auto-create lookup rows (cf_item_type, cf_license, cf_subject) from the CSV's `CFItemType` column, the `license` column, the `#subject` metadata, and the `#license` metadata. `cf_concept` is **not** created by CSV import (only by the external CASE source import via `CFDefinitions.CFConcepts`).

**Pre-processing:** lookup key values (the `CFItemType` cell, the `license` cell, the `#license` value, each element of `#subject`) are trimmed before matching (the trimmed value is stored as `title`). Values that are empty after trimming are treated as "no value" (no lookup is created or matched). `#subject` elements are already trimmed during the csv-format.md parsing step; `CFItemType`, `license`, and `#license` are trimmed again in this step.

**Matching rules (common to every lookup):**
1. Search the tenant for an **exact** `title` match (case-sensitive).
2. Exactly one row → use its ID.
3. **More than one row** (can happen when external CASE imports created multiple lookups with the same title but different identifiers) → pick the row with the lexicographically smallest `identifier` (deterministic selection).
4. None → create a new row (`identifier` = UUID v4, `uri` = `{BASE_URL}/{tenant_id}/uri/{identifier}`, `last_change_date_time` = the import-time UTC timestamp).

**Target tables and source data:**
| Lookup table | CSV source | Notes |
|--------------|-----------|-------|
| cf_item_type | `CFItemType` column | Empty → on create `cf_item.cf_item_type_id = NULL`, on update keep the existing `cf_item_type_id` (same as Step 6's empty-cell-keeps-existing rule). |
| cf_license | `license` column (CFItem) / `#license` metadata (CFDocument) | Same title-based find-or-create as CFItemType. Empty `license` column: on create `cf_item.cf_license_id = NULL`, on update keep existing. Empty `#license`: on create `cf_document.cf_license_id = NULL`, on update keep existing. CFItem and CFDocument referring to the same license name share the same cf_license row. |
| cf_subject | `#subject` metadata | Comma-separated. Stored on the document in `subject` / `subject_uri`. |

**JSONB array construction (same on create and update):**
- `cf_document.subject`: store the `#subject` values directly as a string array (e.g., `["Japanese", "Geography"]`).
- `cf_document.subject_uri`: build a LinkURI object array from each `cf_subject` row's `{title, identifier, uri}` (e.g., `[{"title":"Japanese","identifier":"<cf_subject.identifier>","uri":"<cf_subject.uri>"}]`).
- `cf_item.concept_keywords`: store the parsed `conceptKeywords` as-is as a string array (e.g., `["analysis", "evaluation"]`).

**About `cf_item.cf_concept_id`:** CSV has no column for `conceptKeywordsURI`. CSV import never sets `cf_concept_id` (on create it's NULL; on update the existing value is kept). `cf_concept` rows are created only by the external CASE source import via `CFDefinitions.CFConcepts`.

**Update interactions:**
- `conceptKeywords` non-empty → overwrite `concept_keywords` (don't touch `cf_concept_id`; keep its existing value).
- `conceptKeywords` empty cell → preserve `concept_keywords`'s existing value.
- `#subject` with at least one subject → rebuild both `subject` and `subject_uri` from the new values.
- `#subject` present but empty (`#subject` alone, or `#subject,` with no value) → clear both `subject` and `subject_uri` to empty arrays `[]`.
- `#subject` absent (the key is not present at all) → preserve both `subject` and `subject_uri`.

### Step 6: CFItem upsert

**Upsert match keys (priority order):**

1. **Identifier match**: a CFItem in the tenant whose `identifier` equals the CSV `Identifier` → update. If the matched item belongs to a different document, reattach `cf_document_id` to the current document. (**Side effect**: the previous document's isChildOf associations may still reference this item, and `depth` is not recomputed for it there. To restore the previous document's consistency, re-import it or `doc delete` it. When reattaching, emit a warning: "Row N: Item '{item_identifier}' moved from document '{old_doc_identifier}' to current document".) `{old_doc_identifier}` is the source document's `identifier` (same shape as the equivalent external-import warning).
2. **`humanCodingScheme` match** (only when CSV `Identifier` is empty): a row in the same tenant and document whose `human_coding_scheme` matches → update. If CSV `Identifier` has a value, this fallback is **not** used (Identifier-bearing rows must match by Identifier; if not, create new). Two NULLs do not match (empty CSV value with existing NULL is not a match). If multiple items match, the lexicographically smallest `identifier` wins (deterministic selection — same policy as the lookup multi-match rule).
3. **No match** → create a new row.

**On update:**
- Columns with a CSV value → overwrite.
- Columns without a CSV value (empty cell, or absent from the format definition entirely — e.g., OpenSALT's `listEnumeration`, `license`, `statusStartDate`, `statusEndDate`) → preserve the existing value (no NULL overwrite). **The "empty cell" check uses the raw pre-parse value** (an empty string or a missing cell). Delimiter-only inputs (e.g., `educationLevel` = `","`) are non-empty in the raw value, so they overwrite with the parsed `[]`.
- `uri` → preserve the existing value (do not regenerate; this preserves external URIs of items imported from CASE sources).
- `last_change_date_time` → overwrite with the import-time UTC timestamp.

**On create:**
- `identifier` → CSV value; empty → auto-generated UUID v4.
- `uri` → `{BASE_URL}/{tenant_id}/uri/{identifier}`.
- `language` → CSV value; empty → inherit `language` from the CFDocument (NULL if the document is also NULL).
- `last_change_date_time` → the import-time UTC timestamp.

### Step 7: generating CFAssociation (`isChildOf`)

Persist parent–child relationships as `isChildOf` CFAssociation rows.

**`parentIdentifier` resolution:**
1. Custom / OpenSALT: resolve the parent by the UUID in `parentIdentifier` / `Is Child Of`. Search scope: same tenant, same document (items upserted in this CSV + items already in the DB). Other documents' items are out of scope. Self-reference (`parentIdentifier` equals the row's own `Identifier`) emits a warning ("Row N: parentIdentifier references self, treated as root") and is treated as root (no self-isChildOf is created).
2. Simple format: compute depth from indent; the most recent item at a shallower depth is the parent.
   - If depth jumps by 2+ (e.g., 0 → 3): use the most recent item as the parent and emit a warning ("Row N: depth jumped from 0 to 3, treating previous item as parent"). Intermediate depths are not created.
3. Parent not found: treat as root (parent is the CFDocument).

**Generation rules:**
- `tenant_id` = the target tenant's `id`.
- `cf_document_id` = the target CFDocument's internal PK (`id`).
- `association_type` = `isChildOf`.
- `identifier` = UUID v4 (auto-generated).
- `uri` = `{BASE_URL}/{tenant_id}/uri/{identifier}`.
- `origin_node_identifier` = the child's `identifier`.
- `origin_node_uri` = the child's `uri`.
- `origin_node_title` = the child's `fullStatement`.
- `origin_node_target_type` = NULL (CSV import never sets `targetType`).
- `destination_node_identifier` = the parent's `identifier` (CFDocument's `identifier` when the parent is the document).
- `destination_node_uri` = the parent's `uri` (the document's `uri` when applicable).
- `destination_node_title` = the parent's `fullStatement` (the document's `title` when applicable).
- `destination_node_target_type` = NULL.
- `sequence_number` = CSV `sequenceNumber`. If empty, **per-parent counter** auto-numbers 10, 20, 30, … in encounter order (a parent's counter starts at 10 the first time it appears; the counter continues even when the same parent's children are interleaved with others in the CSV). Explicit values and the auto-numbering are independent; no de-duplication is performed against explicit values.
- `last_change_date_time` = the import-time UTC timestamp.

**Existing associations on upsert:**
- Updating an existing document (`--doc` specified, OpenSALT `Is Part Of` matched, or `#identifier` matched) **with at least 1 data row**: **delete all** existing `isChildOf` associations of that document, then regenerate from the current CSV.
- Updating an existing document **with 0 data rows** (metadata-only CSV): existing items and `isChildOf` associations are **preserved**; only CFDocument metadata (`#title`, `#subject`, etc.) is updated. A non-destructive warning is emitted ("No data rows in CSV; metadata updated, existing items and isChildOf preserved"). To intentionally wipe the tree, a future explicit `--clear-items` flag is the planned entry point; until then no implicit wipe path exists. This safety carve-out is especially relevant for `#identifier`, which makes triggering an update with a metadata-only CSV trivially easy.
- New document: just generate. With 0 items processed, an empty document is created and a warning is emitted ("No items processed, empty document created").

### Step 8: depth computation

Compute `depth` for every CFItem in the target document using its `isChildOf` associations (other documents' items are out of scope).

**Algorithm:**
```
1. Items directly under the CFDocument (parent = CFDocument) get depth=0.
2. BFS over isChildOf: each child gets parent.depth + 1.
3. Fallback: if any items remain unreachable after step 2, the items that have
   NO isChildOf association at all are treated as document roots (depth=0) and
   a second BFS runs from them. This handles editors (e.g., OpenCASE) that do
   not emit `isChildOf -> CFDocument` for top-level items.
4. Items still unreachable after step 3 are orphans (depth=0) with a warning
   "Orphan item '{identifier}' has no reachable parent, set to depth 0".
5. If a cycle is detected, set the affected items' depth=0 and add an entry to
   the error report.
```

**Cycle detection:**
Revisiting an already-visited node during BFS (where depth has been assigned) is **not** treated as a cycle; it is treated as **multi-parent** (can occur with external CASE imports), and the revisit is skipped (keep the first-assigned depth; BFS processes level by level, so the shallowest depth wins).
**True cycles** are detected after BFS: walk every isChildOf origin/destination and find unreachable cycles (groups of nodes that are not directly under the document and were never reached by BFS). Nodes in such a cycle are already orphans (depth=0 from Step 3); we additionally report them as a cycle (warning "Circular reference detected involving items: '{identifier1}', '{identifier2}', ..., set to depth 0").
**Caveat:** cycles reachable from the root (e.g., A → B → C → A where A is directly under the document) are not detected because BFS assigns depth to every node. The tree view can be expanded infinitely in that case, but HTMX lazy-loading prevents an infinite loop (the user must keep manually expanding).

### Step 9: result report

After import, print a summary (CLI uses a rich table).

```
Import Result:
  Document:     High School Curriculum (d86774f2-...)
  Items:        1523 created, 34 updated, 3 skipped
  Associations: 2045 created, 0 updated, 0 skipped
  ItemTypes:    5 created, 0 updated, 2 existing, 0 skipped
  Subjects:     3 created, 0 updated, 0 existing, 0 skipped
  Concepts:     0 created, 0 updated, 0 existing, 0 skipped
  Licenses:     0 created, 0 updated, 0 existing, 0 skipped
  Groupings:    0 created, 0 updated, 0 existing, 0 skipped

Warnings:
  Row 45: fullStatement is empty, skipped
  Row 102: Invalid Identifier 'abc', skipped
  Row 203: Parent 'f1a2b3c4-...' not found, treated as root
```

## External CASE source import

Fetch a CFPackage from an external CASE API and persist it to the DB.

**Transaction strategy:**
Like CSV import, run steps 3–7 in one transaction. On any DB-level error during the run, roll back everything and fail. Individual resource issues (the "invalid individual resource in CFPackage" rows in the error-handling table) are skip-level — not DB errors — so the transaction continues.

**Preventing concurrent imports on the same document:**
Same as CSV import: on update, Step 3 acquires `SELECT ... FOR UPDATE` on the target CFDocument row and holds it until the transaction ends. On create, no lock is needed.

### `--doc` semantics

| Condition | Behavior |
|-----------|----------|
| `--doc` omitted | Look up by the external CFPackage's CFDocument identifier within the tenant. Update if found; create otherwise |
| `--doc {uuid}` specified, in the tenant | Overwrite the existing CFDocument with the external data |
| `--doc {uuid}` specified, not in the tenant | Fail ("Document not found: '{uuid}'") |

**Update rules (same for CFDocument / CFItem / CFAssociation / CFDefinitions):**
- External CFPackage has a value → overwrite.
- External CFPackage lacks a value (null / missing) → preserve the existing value.
- `identifier` → preserve the existing value (no overwrite). `identifier` is the upsert match key; changing it would violate UNIQUE constraints and break association / URI references. If `--doc` specifies an external CFDocument with a different identifier, keep the existing document's identifier.
- `last_change_date_time` → use the external value as-is (fall back to the import-time UTC timestamp if missing).
- Existing CFItem / CFAssociation are upserted by **tenant-wide** identifier match. When a match belongs to a different document, reattach `cf_document_id` to the current document (no match → create new). When reattaching, emit a warning ("Item '{identifier}' moved from document '{old_doc_identifier}' to current document" — same policy as the equivalent CSV warning).
- Existing CFDefinitions (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping) are upserted by **tenant-wide** identifier match.
- **Resources not present in the external source**: CFItem / CFAssociation / CFDefinitions (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping) in the DB but not in the external CFPackage are **not deleted** (additive only). If they were deleted upstream, they remain locally. For a full sync, `doc delete` the existing document first and re-import.

### Flow

**`--url` parameter format:**
- Provide a CASE API base path (up to the version segment). Examples: `https://opensalt.example.com/ims/case/v1p0`, `https://case.example.com/{tenant}/ims/case/v1p1`.
- Or a direct CFPackage URL. Example: `https://opensalt.example.com/ims/case/v1p0/CFPackages/{uuid}`.
- A bare server root (e.g., `https://opensalt.example.com`) is not accepted. The flow below appends `/CFDocuments`, so the URL must contain the CASE API path.

```
1. Resolve the URL and fetch the CFPackage JSON
   - If the URL contains `/CFPackages/`: GET it directly
   - Otherwise (base URL):
     a. Normalize trailing slashes (with or without works)
     b. GET {url}/CFDocuments to list documents
     c. Empty list → fail ("No documents found on remote server: {url}")
     d. Use the first (or only) document's identifier. If there are 2+, warn ("Remote server has {n} documents. Importing first document '{identifier}'")
     e. GET {url}/CFPackages/{identifier}
2. Parse and validate the JSON
3. Create or update the CFDocument
4. Persist CFDefinitions (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping) (mapping below)
5. Bulk persist CFItems
   - Every CFItem's `cf_document_id` is set to the internal PK of the CFDocument created/updated in Step 3 (including items reattached from other documents)
   - When `CFItemTypeURI.identifier` is present: look up `cf_item_type` in the same tenant by `identifier` match and set `cf_item.cf_item_type_id` to the internal PK. If no match (i.e., Step 4 didn't persist it), `cf_item_type_id = NULL` with a warning ("CFItem '{item_identifier}': CFItemType '{type_identifier}' not found, set to null")
   - When `conceptKeywordsURI.identifier` is present: look up `cf_concept` in the same tenant by `identifier` match and set `cf_item.cf_concept_id` to the internal PK. If no match, `cf_concept_id = NULL` with a warning ("CFItem '{item_identifier}': CFConcept '{concept_identifier}' not found, set to null" — same pattern as CFItemType FK resolution)
   - `educationLevel`, `conceptKeywords` → store the external values as-is as JSONB (no FK resolution)
6. Bulk persist CFAssociations
   - Every CFAssociation's `cf_document_id` is set to the internal PK of the CFDocument from Step 3
   - Keep `originNodeURI.title` / `destinationNodeURI.title` as-is in `origin_node_title` / `destination_node_title`
   - When `CFAssociationGroupingURI.identifier` is present: look up `cf_association_grouping` in the same tenant by `identifier` match and set `cf_association.cf_association_grouping_id` to the internal PK. If no match, `cf_association_grouping_id = NULL` with a warning ("CFAssociation '{assoc_identifier}': CFAssociationGrouping '{grouping_identifier}' not found, set to null")
   - When an existing CFAssociation belongs to a different document, reattach `cf_document_id`. Emit a warning when reattaching ("CFAssociation '{identifier}' moved from document '{old_doc_identifier}' to current document" — same policy as the CFItem reattach warning)
6.5. Persist CFRubrics (upsert the three-level CFRubric → CFRubricCriterion → CFRubricCriterionLevel; see "CFRubrics handling")
7. Recompute depth for all CFItems in the target document from all isChildOf associations in that document (existing + newly imported). Algorithm = CSV import Step 8
8. Print the result report (same format as CSV import Step 9; the per-category counters: items/associations/rubrics use the 3-state created/updated/skipped, definitions use the 4-state created/updated/existing/skipped; warnings are also printed. For definitions, "updated" counts identifier-match upserts that changed ≥ 1 field, "existing" counts identifier-match upserts with no field changes, "skipped" counts validation failures (missing identifier/title, etc.). CSV imports always have "updated" and "skipped" = 0 for definitions (find-or-create never updates; CSV values are pre-validated so skips do not occur). External CASE imports can have non-zero "updated" and "skipped" for definitions)
```

### CFDocument field mapping

Mapping from the external CFPackage's CFDocument object to DB columns:
- `identifier` → `identifier` (used only on create; on update keep existing).
- `uri` → `uri` (FR-7.2: source URI preserved verbatim on **both** create and update via `_resolve_uri()` in `case_import_service.py`. Same rule applies to CFItem / CFAssociation / CFRubric* / lookup resources).
- `title` → `title`.
- `creator` → `creator` (required in CASE v1.1 OpenAPI but nullable here. On create, missing / null / blank emits a warning and stores NULL. On update, follow the rule "no external value → keep existing": missing / null retains existing silently; a blank string emits a warning and still retains existing (the existing `creator` is not overwritten with an empty string). `null` / key absent / empty string / whitespace-only are all treated as "missing".).
- `publisher` → `publisher`.
- `description` → `description`.
- `frameworkType` → `framework_type` (v1.1 new).
- `caseVersion` → `case_version` (v1.1 new; only `"1.1"` is valid).
- `language` → `language` (validate length ≤ 10; too long → NULL with a warning — same rule as CSV import).
- `version` → `version`.
- `adoptionStatus` → `adoption_status`.
- `statusStartDate` → `status_start_date` (`YYYY-MM-DD` string → DATE. Invalid format → NULL with a warning — same rule as CFItem).
- `statusEndDate` → `status_end_date` (same rule as `statusStartDate`).
- `licenseURI` → `cf_license_id` (resolve `licenseURI.identifier` against `cf_license` in the same tenant; set the internal PK. No match → `cf_license_id = NULL` with a warning. Same pattern as CFItem's CFItemTypeURI FK resolution).
- `officialSourceURL` → `official_source_url`.
- `subject` → `subject` (JSONB string array).
- `subjectURI` → `subject_uri` (JSONB LinkURI object array).
- `lastChangeDateTime` → `last_change_date_time` (parse ISO 8601; on invalid format or absence, use the import-time UTC timestamp with a warning — same rule as CFItem).
- `CFPackageURI.uri` → `cf_package_uri_source` (the rest of the LinkURI is rebuilt at emit time). Stored verbatim so re-export preserves the source URI without touching `BASE_URL` — required for OpenCASE / OBF round-trip (FR-7.2; see [round_trip_status.md](../dev/round_trip_status.md) cat G). On update, the field is overwritten when the new payload includes a `CFPackageURI` key (matches the existing "missing → keep existing" semantics).
- `notes` → `notes`; `extensions` → `extensions` (both persisted on create and update; absent → keep existing). Container-level `CFPackage.extensions` → `package_extensions` and `CFDefinitions.extensions` → `definitions_extensions` on the CFDocument row.

### CFDefinitions field mapping

Map camelCase external CASE fields to snake_case DB columns. The common fields (`identifier`, `uri`, `title`, `description`, `lastChangeDateTime`) are the same for every lookup table. `lastChangeDateTime` is parsed as ISO 8601; on invalid format or absence the import-time UTC timestamp is used (with a warning) — same rule as CFItem. Specific fields:
- CFItemType: `typeCode` → `type_code`; `hierarchyCode` → `hierarchy_code`.
- CFSubject: `hierarchyCode` → `hierarchy_code`.
- CFConcept: `keywords` → `keywords`; `hierarchyCode` → `hierarchy_code`.
- CFLicense: `licenseText` → `license_text`.
- CFAssociationGrouping: no specific fields.

### CFItem field mapping

Mapping from the external CFPackage's CFItem object to DB columns:
- `identifier` → `identifier` (create only; update keeps existing).
- `uri` → `uri` (FR-7.2: source URI preserved verbatim on **both** create and update — `_resolve_uri()` in `case_import_service.py`. Falls back to `{BASE_URL}/{tenant}/uri/{identifier}` only when the source omits `uri`. The same rule applies to CFDocument / CFAssociation / CFRubric* / lookup resources).
- `fullStatement` → `full_statement` (stored after trimming surrounding whitespace; empty → skip).
- `humanCodingScheme` → `human_coding_scheme`.
- `abbreviatedStatement` → `abbreviated_statement`.
- `listEnumeration` → `list_enumeration`.
- `language` → `language` (validate length ≤ 10; too long → NULL with a warning — same as CSV).
- `licenseURI` → `cf_license_id` (resolve `licenseURI.identifier` against `cf_license` in the tenant; set the internal PK; no match → NULL with a warning — same pattern as CFDocument's licenseURI).
- `statusStartDate` → `status_start_date` (`YYYY-MM-DD` → DATE; invalid → NULL with a warning).
- `statusEndDate` → `status_end_date` (same as `statusStartDate`).
- `educationLevel` → `education_level` (JSONB; stored as-is).
- `subject` → `subject` (JSONB string array; stored as-is; v1.1 new).
- `subjectURI` → `subject_uri` (JSONB LinkURI object array; stored as-is; v1.1 new).
- `conceptKeywords` → `concept_keywords` (JSONB; stored as-is).
- `conceptKeywordsURI` → `cf_concept_id` (resolve `conceptKeywordsURI.identifier` against `cf_concept` in the tenant; set the internal PK; no match → NULL with a warning — same pattern as CFItemTypeURI. In CASE v1.1, `conceptKeywordsURI` is a single LinkURIDType).
- `CFItemTypeURI.identifier` → resolve to `cf_item_type_id` (see Step 5).
- `lastChangeDateTime` → `last_change_date_time` (parse ISO 8601; invalid / absent → import-time UTC with a warning).
- `alternativeLabel` → `alternative_label`; `notes` → `notes`; `extensions` → `extensions` (all persisted on create and update; absent → keep existing).
- `CFDocumentURI` is dynamically generated by the API response — not persisted.

### CFAssociation field mapping

Mapping from the external CFPackage's CFAssociation object to DB columns:
- `identifier` → `identifier` (create only; update keeps existing).
- `uri` → `uri` (FR-7.2: source URI preserved verbatim on **both** create and update via `_resolve_uri()`. Same rule as CFDocument / CFItem).
- `associationType` → `association_type`.
- `originNodeURI.identifier` → `origin_node_identifier`.
- `originNodeURI.uri` → `origin_node_uri` (source URI preserved verbatim when present, same `_resolve_uri()` semantics).
- `originNodeURI.title` → `origin_node_title`.
- `originNodeURI.targetType` → `origin_node_target_type` (v1.1 new; values `"CASE"` / `"ext:*"`; NULL/absent → NULL).
- `destinationNodeURI.identifier` → `destination_node_identifier`.
- `destinationNodeURI.uri` → `destination_node_uri`.
- `destinationNodeURI.title` → `destination_node_title`.
- `destinationNodeURI.targetType` → `destination_node_target_type` (v1.1 new; same rule as `origin_node_target_type`).
- `sequenceNumber` → `sequence_number` (INTEGER; non-numeric → NULL with a warning; floats are truncated to integer; values outside the PostgreSQL INTEGER range → NULL with a warning).
- `CFAssociationGroupingURI.identifier` → resolve to `cf_association_grouping_id` (see Step 6).
- `lastChangeDateTime` → `last_change_date_time` (same rule as CFItem).
- `notes` → `notes`; `extensions` → `extensions` (persisted on create and update; absent → keep existing).
- `CFDocumentURI` is dynamically generated by the API response — not persisted.

### Note on CFItemType FK resolution

When CFItem has no `CFItemTypeURI` (e.g., `CFItemTypeURI` is null/absent but the `CFItemType` string is present): `cf_item_type_id = NULL` (identifier-based FK resolution can't be done from a name alone). The `CFItemType` string is **not** stored in the DB (the design derives it from `CFItemType.title` via JOIN). To preserve the type, the external source must provide `CFItemTypeURI`.

### Unsupported fields / resources

External CFPackage fields without a DB column are silently ignored (no error):
- `CFPackageURI` (CFDocument): dynamically generated by the API response — not persisted (but `CFPackageURI.uri` is preserved as `cf_package_uri_source` for round-trip; see CFDocument mapping above).
- `CFDocumentURI` (CFItem / CFAssociation): dynamically generated by the API response — not persisted.
- Other unknown fields: silently ignored to accommodate future CASE v1.1 extensions and server-specific fields.

Note: `notes` (CFDocument / CFItem / CFAssociation), `alternativeLabel` (CFItem), and `extensions` (all resources + container-level `package_extensions` / `definitions_extensions`) **are** persisted (added in v1.1 support; see the field-mapping sections above and [db-schema.md](db-schema.md)).

**CFRubrics handling:**
When the external CFPackage contains a `CFRubrics` array, Step 6.5 (after CFAssociations, before depth) upserts CFRubric / CFRubricCriterion / CFRubricCriterionLevel. If `CFRubrics` is absent, it is silently skipped (no error).

CFRubric upsert rules mirror CFItem / CFAssociation:
- CFRubric: tenant-wide `identifier` match.
- If matched, update (overwrite only non-null fields).
- If not matched, create.
- CFRubricCriterion is upserted by `identifier` **within the parent CFRubric** (`UNIQUE(cf_rubric_id, identifier)`, #187); CFRubricCriterionLevel by `identifier` **within the parent CFRubricCriterion** (`UNIQUE(cf_rubric_criterion_id, identifier)`). The same UUID can therefore recur under different parents / tenants without colliding.
- CFRubricCriterion's `CFItemURI.identifier` → resolve to the FK against `cf_item` in the same tenant (same pattern as CFItem FK resolution).
- `rubricId` / `rubricCriterionId` are kept as-is as reference UUIDs (no FK resolution).

Validation:
- CFRubric: missing `identifier` or not a UUID → skip (warning).
- CFRubricCriterion: same.
- CFRubricCriterionLevel: same.

Report counters: `rubrics_created`, `rubrics_updated`, `rubrics_skipped` (CFRubric level. Criterion/Level skips go into warnings; no counters).

### URI preservation rule (FR-7.2)

CFPackage imports preserve the source `uri` verbatim — implemented by `_resolve_uri(source, tenant_id, identifier)` in `case_import_service.py`. The helper returns `source["uri"]` when present (non-blank string), and falls back to a compeito-native `{BASE_URL}/{tenant}/uri/{identifier}` only when the source omits it.

Behavior summary:
- **CFDocument / CFItem / CFAssociation / CFRubric / CFRubricCriterion / CFRubricCriterionLevel / CFDefinitions lookups**: source `uri` overwrites the stored value on **both** create and update. A re-import with a different upstream URI updates the column.
- **CFAssociation.originNodeURI.uri / destinationNodeURI.uri**: same — preferred over the synthesized URI when the source provides it.
- **`identifier`**: always preserved as-is from the source (matches CASE round-trip semantics).
- **Denormalized LinkURI fields** (`CFDocument.CFPackageURI.uri`, `CFRubricCriterion.CFItemURI.uri`): captured verbatim into dedicated columns (`cf_documents.cf_package_uri_source`, `cf_rubric_criteria.cf_item_uri_source`) so re-export reproduces them. See [round_trip_status.md](../dev/round_trip_status.md) cat F / G.
- **CSV import**: bypasses `_resolve_uri()` and always synthesizes a compeito-native URI (CSV rows don't carry a URI column).

The `/uri/{uuid}` route on our own server searches by `identifier`, so externally-URI resources remain reachable through compeito's own host as well.

### Error handling

| Error | Behavior |
|-------|----------|
| Cannot connect to the external URL (including timeouts) | Fail. Timeout is 30s per HTTP request (for base URLs, both the CFDocuments fetch and the CFPackage fetch get 30s each). HTTP redirects (301 / 302 / 307 / 308) are followed up to 5 times. No retry |
| Non-2xx HTTP status | Fail ("Remote server returned HTTP {status}: {url}") |
| Response is not JSON | Fail ("Response is not valid JSON") |
| CFDocuments list response is malformed (no `CFDocuments` key, not an array, etc.) | Fail ("Invalid CFDocuments response: {url}") |
| JSON parses but isn't a CFPackage (see below) | Fail ("Invalid CFPackage response: {detail}") |
| An individual resource inside CFPackage is invalid (see below) | Skip the resource and add a warning. Other resources continue |
| SSL certificate error | Fail ("SSL certificate verification failed") |

**CFPackage structure validation (fail conditions):**
Any of the following yields "Invalid CFPackage response: {detail}":
- The root has no `CFPackage` key (for direct URL), or the expected structure is missing inside the `CFDocuments` array (for base-URL flow).
- `CFPackage.CFDocument` is missing or not an object.
- `CFPackage.CFDocument.identifier` is missing or not a UUID.
- `CFPackage.CFDocument.title` is missing, empty, or whitespace-only (empty after trim). The structure validation does not distinguish create vs. update, so this is checked uniformly (would violate the NOT NULL constraint on create).

**Individual resource invalidity (skip conditions):**
The following are skipped with a warning:
- CFItem: missing `identifier` or `fullStatement`, or `fullStatement` is empty or whitespace-only (empty after trim), or `identifier` is not a UUID. (Warning "Skipped CFItem: {reason}. identifier='{identifier}'".)
- CFAssociation: missing `identifier`, `associationType`, `originNodeURI`, or `destinationNodeURI`. Or `associationType` is not in the CASE v1.1 enum or extension pattern (`ext:` is valid; see api-spec.md). Or `originNodeURI` / `destinationNodeURI`'s required subfields (`identifier`, `uri`) are missing (prevents NOT NULL violations). Or `identifier` is not a UUID (prevents UUID-column insertion failure). `originNodeURI.identifier` / `destinationNodeURI.identifier` are not restricted to UUID (LinkGenURIDType supports non-UUID external references; the columns are VARCHAR). (Warning "Skipped CFAssociation: {reason}. identifier='{identifier}'".)
- Resource inside CFDefinitions: missing `identifier` or `title`, or `identifier` is not a UUID. (Warning "Skipped {resource_type}: {reason}. identifier='{identifier}'".)

### v1.0 → v1.1 normalization

For CASE v1.0 CFPackage responses, normalize to v1.1 form after fetch and before validation.

**Version detection** (positive v1.0 signals only; ambiguous payloads default to v1.1):
- URL contains `v1p0` → v1.0.
- URL contains `v1p1` → NOT v1.0 (the path is treated as authoritative; the body's `caseVersion` is not required). This avoids spurious v1.0 detection for servers like OpenCASE that ship v1.1 responses without the `caseVersion` field.
- URL has neither segment (e.g., file-based imports) → look at `CFDocument.caseVersion` (at the root, or inside the `CFPackage` wrapper). Only `"1.0"` triggers v1.0 detection. Missing / `"1.1"` / any other value → NOT v1.0. The `CFPackage` wrapper alone is NOT a v1.0 signal — `_validate_cf_package()` accepts wrapped payloads from non-conforming v1.1 sources as well.

**Normalization rules:**
- `conceptKeywordsURI`: some v1.0 implementations (e.g., OpenSALT) return an array. If it's an array, use the first element; warn if there are multiple.
- v1.1-added fields (`frameworkType`, `caseVersion`, `subject` / `subjectURI`, `targetType`, `notes`, `extensions`) are absent from v1.0 responses, but existing import logic uses `.get()` with `None` as default — no extra normalization needed.
- Structural differences (missing `CFPackage` wrapper) are already handled by `_validate_cf_package`.

**Output:**
- When v1.0 is detected, emit a warning ("Detected CASE v1.0 response, normalizing to v1.1 format").

## Rubric CSV import flow

```
1. Read the CSV file (UTF-8; BOM auto-skipped)
2. Parse and validate the header row (verify the `Type` column exists)
3. Acquire the target document (`--doc` required; `SELECT ... FOR UPDATE`)
4. Per-row parse / upsert (resolve Rubric → Criterion → Level positional context)
5. Print the result report
```

**Transaction strategy:**
Run all steps in a single transaction. On error, roll back. Per-row validation errors are treated as skips.

### Step 4: parse / upsert

**Behavior per Type:**

- **Rubric**: look up an existing CFRubric in the tenant by `identifier` and upsert. Overwrite only non-null fields (title, description). On create, set `uri` to `{BASE_URL}/{tenant_id}/uri/{identifier}`.
- **Criterion**: resolve the parent Rubric via `RubricIdentifier` or positional context (the most recent Rubric row). Look up an existing CFRubricCriterion by `identifier` **within that parent Rubric** and upsert. When `CFItemIdentifier` is set, resolve the FK against `cf_item` in the same tenant (no match → NULL with a warning).
- **Level**: resolve the parent Criterion via `CriterionIdentifier` or positional context (the most recent Criterion row). Look up an existing CFRubricCriterionLevel by `identifier` **within that parent Criterion** and upsert.

**Validation:**
- `Identifier` empty → auto-generate UUID v4.
- `Identifier` not a UUID → skip the row (warning).
- Criterion with no parent Rubric (`RubricIdentifier` empty and no preceding Rubric row) → skip (warning).
- Level with no parent Criterion → skip (warning).
- Unknown Type → skip (warning).
- `Weight` / `Score` non-numeric → store as NULL (warning).
- `Position` non-integer → store as NULL (warning).

### Step 5: result report

```
Imported into 'Document Title' (doc-uuid)
  Rubrics:   1 created, 0 updated, 0 skipped
  Criteria:  2 created, 1 updated, 0 skipped
  Levels:    4 created, 0 updated, 1 skipped
```

## Rubric CSV export flow

```
1. Fetch the target document (`--doc` required)
2. Fetch its CFRubrics along with their criteria and levels
3. Emit CSV rows in the order rubric → criterion → level
```

**Output format:**
- Encoding: UTF-8 (no BOM); line endings: LF.
- Header: `Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier`.
- Rubric order: `title` ASC → `identifier` lexicographic.
- Criterion order: `position` ASC (NULL last) → `identifier` lexicographic.
- Level order: `position` ASC (NULL last) → `identifier` lexicographic.
- CFItemIdentifier: write the linked CFItem's `identifier` (empty cell when there's no link).

## CSV export flow

```
1. Fetch the CFDocument and all its CFItems
2. Resolve parent/child relations from isChildOf in the same document (`cf_association.cf_document_id` matches the target)
3. Sort in tree (depth-first) order
4. Generate CSV in the specified format
```

### Common export rules

- Encoding: UTF-8 (no BOM).
- Line endings: LF.
- CSV syntax: RFC 4180 (quote fields containing commas, newlines, or double-quotes).

### Custom-format export

- Emit metadata rows from CFDocument's non-NULL, non-empty fields. (VARCHAR fields → omit when NULL. FK reference `cf_license_id` → omit when NULL; otherwise resolve `cf_license.title` and emit as `#license`. JSONB array `subject` → omit when NULL or `[]`. **Round-trip caveat**: `[]` is omitted, so re-importing as a new document drops `subject` / `subject_uri` to NULL; on update with omitted keys, the existing values are preserved, so there's no impact.) Output order: `#identifier` (emitted first so re-import preserves the CFDocument UUID), `#title`, `#version`, `#creator`, `#publisher`, `#description`, `#notes`, `#language`, `#adoption_status`, `#status_start_date`, `#status_end_date`, `#license`, `#official_source_url`, `#subject`. `#status_start_date` / `#status_end_date` are emitted as `YYYY-MM-DD`. Metadata rows follow RFC 4180 too (quote values containing commas, newlines, or double-quotes; e.g., `#description,"Information I, II"`). `#subject` is emitted with each JSONB element as a separate CSV field (not as one quoted string; e.g., `#subject,Japanese,Geography,Civics`). Quote individual `subject` values that contain commas, etc., per RFC 4180 (e.g., `#subject,Japanese,"Information I, II",Geography`).
- Emit the header row: `Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType,educationLevel,conceptKeywords,abbreviatedStatement,alternativeLabel,notes,language,listEnumeration,license,statusStartDate,statusEndDate` (16 columns).
- Emit every column (including Identifier).
- `parentIdentifier` is the parent's UUID; an empty cell for root-level items (parent = CFDocument). When an item has multiple `isChildOf` parents (possible via external CASE imports), pick the association with the smallest `sequence_number` (NULL last; ties broken by `destination_node_identifier` lexicographic). **Round-trip caveat**: an item with multiple isChildOf parents is collapsed to one in the export. Re-importing this CSV loses the non-selected relationships via the isChildOf delete-all → regenerate.
- `sequenceNumber` is the `sequence_number` of the isChildOf association used for `parentIdentifier` (when there are multiple isChildOfs, the selected one's value). NULL → empty cell. **Round-trip caveat**: an empty `sequenceNumber` cell auto-numbers (10, 20, 30, …) on re-import. The display order is preserved because the export sort matches the auto-numbering order, but the actual values change.
- `CFItemType` resolves `cf_item_type_id` to `cf_item_type.title` (`cf_item_type_id` NULL → empty cell). **Round-trip caveat**: only the `title` is emitted, so `cf_item_type`'s `type_code` / `hierarchy_code` / `description` aren't in the CSV. Re-importing into the same tenant matches by title and reuses the existing row (so these fields are preserved). Importing into a different tenant creates a new row with title only — those fields are lost.
- `educationLevel` converts the JSONB array to a comma-separated string (`["09","10","11","12"]` → `"09,10,11,12"`). NULL or `[]` → empty cell. **Round-trip caveat**: empty cell becomes NULL on re-import as a new document (API responses distinguish `[]` and `null`). On update, the empty cell preserves the existing value.
- `conceptKeywords` converts the JSONB array to comma-separated (`["analysis","evaluation"]` → `"analysis,evaluation"`). NULL or `[]` → empty cell (same round-trip caveat as `educationLevel`). **Caveat**: array elements containing commas (can happen with external imports) get split by the comma on re-import and are corrupted. This caveat also applies to `educationLevel`, but in practice education-level codes never contain commas.
- **`cf_concept_id` round-trip caveat**: `conceptKeywordsURI` (the FK to `cf_concept`) is not in the CSV. CSV import never sets `cf_concept_id`, so values set by external CASE imports are lost on export → re-import (becomes NULL). On update within the same tenant, the empty cell preserves the existing value — no impact.
- **`subject_uri` round-trip caveat**: `subject_uri` is not in the CSV (`#subject` only emits subject names). On re-import, the URI is rebuilt from the local `cf_subject` lookup table, so external-CASE-originated external URIs are replaced with local URIs. Within the same tenant, the lookup row's `identifier` matches and the URI is preserved; importing into a new tenant assigns new identifiers / URIs.
- **`framework_type` / `case_version` round-trip caveat**: there are no `#framework_type` / `#case_version` keys in the CSV metadata. Values set by external CASE imports are lost on export → re-import (become NULL). On update within the same tenant, the keys are absent, so the existing values are preserved.
- **CFItem `subject` / `subject_uri` round-trip caveat**: the CSV has no item-level subject column (`#subject` is document-level metadata). Item-level `subject` / `subject_uri` set by external CASE imports are lost on export → re-import (NULL on create; on update, empty cells preserve existing).
- `language` is `cf_item.language` as-is (NULL → empty cell).
- `abbreviatedStatement` is `cf_item.abbreviated_statement` as-is (NULL → empty cell).
- `listEnumeration` is `cf_item.list_enumeration` as-is (NULL → empty cell).
- `license` resolves `cf_item.cf_license_id` to `cf_license.title` (NULL → empty cell). Same FK → JOIN pattern as CFItemType. **Round-trip caveat**: only `title` is emitted, so `license_text` / `description` aren't in the CSV. Same caveats as CFItemType for re-import into another tenant.
- `statusStartDate` emits `cf_item.status_start_date` as `YYYY-MM-DD` (NULL → empty cell).
- `statusEndDate` emits `cf_item.status_end_date` as `YYYY-MM-DD` (NULL → empty cell).
- **`cf_association_grouping` round-trip caveat**: `cf_association_grouping` is not emitted at all (no CSV column). Rows created by external CASE imports are entirely lost when exporting and importing into a different tenant. Within the same tenant, the tenant-owned lookup row stays in the DB, so updates aren't affected. For cross-tenant data migration, use external CASE imports instead of CSV.

### OpenSALT-format export

> See [reference/opensalt-csv-format.md](../reference/opensalt-csv-format.md) for differences from OpenSALT's actual format.

- Metadata rows use the same rule as the custom format (`#title`, `#version`, …, `#subject` order; only non-NULL, non-empty fields).
- Header: `Identifier,Full Statement,Human Coding Scheme,Abbreviated Statement,Notes,Concept Keywords,Education Level,CF Item Type,Language,License,Is Child Of,Sequence Number,Is Part Of` (13 columns).
- Column mapping:
  - `Identifier` → `cf_item.identifier`.
  - `Full Statement` → `cf_item.full_statement`.
  - `Human Coding Scheme` → `cf_item.human_coding_scheme` (NULL → empty).
  - `Abbreviated Statement` → `cf_item.abbreviated_statement` (NULL → empty).
  - `Notes` → `cf_item.notes` (NULL → empty).
  - `Concept Keywords` → JSONB array as comma-separated (same as custom).
  - `Education Level` → JSONB array as comma-separated (same as custom).
  - `CF Item Type` → `cf_item_type.title` (NULL → empty).
  - `Language` → `cf_item.language` (NULL → empty).
  - `License` → always empty (OpenSALT manages license at the document level; the item-level cell is not used).
  - `Is Child Of` → parent's identifier (same logic as custom format `parentIdentifier`; root → empty).
  - `Sequence Number` → the isChildOf association's `sequence_number` (same logic as custom format `sequenceNumber`).
  - `Is Part Of` → the CFDocument `identifier` (same value for every row).
- Sort order: same as the custom format (depth-first; see "Sort order" below).
- Round-trip caveats: same as the custom format. The `License` column is always empty, so item-level `cf_license_id` is lost in round-trip. Document-level license is preserved via the `#license` metadata row.

### Sort order

Tree depth-first order:
1. Root-level items sorted by `sequence_number` ASC (items whose isChildOf parent is the CFDocument).
2. For each item, insert its children recursively in `sequence_number` ASC.
3. Items whose isChildOf `sequence_number` is NULL go last among the same parent's children.
4. When `sequence_number` ties, use `human_coding_scheme` natural sort (numeric parts compared numerically; e.g., `"A-2"` < `"A-10"`. Python `natsort.natsorted()` defaults — `alg=natsort.ns.DEFAULT`. No locale-dependent sort like `humansorted` / `os_sorted`. NULL last).
5. When that also ties, use `identifier` lexicographic.
6. Orphan items (no isChildOf) are placed after the normal root items. Orphans are sorted by `human_coding_scheme` natural sort → `identifier` lexicographic (same as the tree view's orphan order).

---

# インポート/エクスポート ビジネスロジック（日本語）

**エラー・警告メッセージの言語:** 本ドキュメント内のエラーメッセージ・警告メッセージは**英語で統一**している（CASE API・Admin API の他のエラーメッセージと一致）。説明文（エラーの条件・動作の解説）は日本語で記載している。

## CSVインポート処理フロー

```
1. CSVファイル読み込み・フォーマット自動判定
2. メタデータ行のパース
2.5. (OpenSALT形式のみ) Is Part Of の事前スキャン
3. CFDocument の作成または更新
4. 行ごとのパース・バリデーション
5. lookup系テーブルの自動生成 (CFItemType, CFSubject, CFConcept)
6. CFItem の作成または更新 (upsert)
7. CFAssociation (isChildOf) の生成
8. depth の計算
9. 結果レポート出力
```

**トランザクション戦略:**
全ステップ（3〜8）を単一トランザクションで実行する。Step 4 のバリデーションエラーはDB書き込み前に弾くため、トランザクション内でのエラーは原則発生しない。万一 DB レベルのエラーが発生した場合はトランザクション全体をロールバックしてエラー終了する（部分コミットしない）。NFR-6.5 の「行単位スキップ」はバリデーション段階での処理であり、DB書き込み段階ではない。

**同一ドキュメントへの同時インポート防止:**
既存ドキュメント更新時（`--doc` 指定等）は、Step 3 で対象 CFDocument 行に `SELECT ... FOR UPDATE` を取得し、トランザクション終了まで保持する。これにより同一ドキュメントへの並行インポートを直列化し、isChildOf 全削除→再生成の競合（重複 association 等）を防止する。新規ドキュメント作成時はドキュメントがまだ存在しないため、ロックは不要。

### ステップ1: ファイル読み込み・フォーマット判定

**エンコーディング:** CSVファイルを UTF-8 として読み込む。BOM（`\xEF\xBB\xBF`）が先頭にある場合は自動的にスキップする（Python の `utf-8-sig` エンコーディング相当）。UTF-8 としてデコードできない場合はエラー終了する（「CSV file is not valid UTF-8」）。

**UUID の大文字/小文字:** UUID 識別子の比較（upsert マッチング、parentIdentifier 解決、`/uri/{uuid}` 検索等）は**大文字小文字を区別しない**（PostgreSQL の UUID 型はケースインセンシティブ。`D86774F2-...` と `d86774f2-...` は同一と見なす）。新規作成時は小文字で正規化して保存する。外部インポート由来の UUID は元の形式のまま保存するが、比較時にはケースインセンシティブで行う。

フォーマット自動判定ロジックは [csv-format.md](./csv-format.md) を参照。

### ステップ2: メタデータパース

`#` で始まる行をキー・バリューとしてパースし、CFDocument のフィールドにマッピングする。
CLI引数が指定されている場合はCLI引数が優先。

**空文字列の扱い（全メタデータ共通）:** 全ての単一値メタデータフィールド（`#title`, `#version`, `#creator`, `#publisher`, `#description`, `#language`, `#adoption_status`, `#official_source_url`, `#license`, `#status_start_date`, `#status_end_date`）において、値が空文字列（前後空白をトリムした後に空）の場合は NULL（未指定）として扱う。新規作成時は NULL が設定され、更新時は既存値を保持する（キー自体が未記載の場合と同じ動作）。

### ステップ2.5: Is Part Of 事前スキャン（OpenSALT形式のみ）

OpenSALT形式の場合、Step 3 で CFDocument を特定するために `Is Part Of` カラムの値が必要。`Is Part Of` はデータ行のカラム値であり Step 4（行パース）より前に読み取る必要があるため、全データ行の `Is Part Of` 列を事前にスキャンする。最初の非空値を CFDocument identifier として採用し、異なる値の行があれば記録しておく（Step 4 で警告出力する: 「Row N: Is Part Of 'xxx' differs from document identifier 'yyy', ignored」）。全行が空の場合は新規ドキュメント作成として扱う。この事前スキャンでは `Is Part Of` 列のみを読み取り、他のカラムは処理しない。

### ステップ3: CFDocument 作成/更新

| 条件 | 動作 |
|------|------|
| `--doc` 未指定（独自形式・簡易形式） | 新規CFDocumentを作成。`identifier` は UUID v4 自動採番 |
| `--doc` 未指定（OpenSALT形式、`Is Part Of` 非空） | `Is Part Of` の値を CFDocument identifier として同一テナント内で検索。存在すれば更新、なければ新規作成（`identifier` は `Is Part Of` の値を使用）。`Is Part Of` がUUID形式でない場合はエラー終了（「Is Part Of value is not a valid UUID: '...'」） |
| `--doc` 未指定（OpenSALT形式、`Is Part Of` 空） | 新規CFDocumentを作成。`identifier` は UUID v4 自動採番 |
| `--doc {uuid}` 指定、同一テナント内に存在する | 既存CFDocumentを更新（下記ルールで上書き）。OpenSALT形式の `Is Part Of` は無視 |
| `--doc {uuid}` 指定、同一テナント内に存在しない | エラー終了（「Document not found: '{uuid}'」） |

**新規作成時の動作:**
- `identifier` → 条件テーブルに従い UUID v4 自動採番、または OpenSALT `Is Part Of` の値を使用
- `uri` → `{BASE_URL}/{tenant_id}/uri/{identifier}`
- `title` → `--doc-title` > `#title` の優先順。空文字列は「未指定」と同等に扱う（空文字列のタイトルは許可しない）。いずれもない場合はエラー終了（「Document title is required」）
- `version` → `--doc-version` > `#version` の優先順。空文字列は「未指定」と同等に扱う。いずれもない場合は NULL
- `language` → メタデータ `#language` の値。未指定なら NULL
- その他のフィールド → 対応するメタデータ行の値。未指定なら NULL
- `last_change_date_time` → インポート実行時のUTCタイムスタンプ

**更新時の動作:**
- メタデータ行に値がある → 対応するCFDocumentフィールドを上書き
- メタデータ行に値がない（キー自体が未記載） → 既存値を保持（NULLで上書きしない）
- `last_change_date_time` → インポート実行時のUTCタイムスタンプで上書き
- `title` → `--doc-title` > `#title` > 既存値の優先順
- `version` → `--doc-version` > `#version` > 既存値の優先順

### ステップ4: 行パース・バリデーション

各行を内部表現に変換する。エラーは行番号と共に収集し、最後にまとめてレポートする。

**バリデーションルール:**
- `fullStatement` が空または空白文字のみ → 行スキップ（警告「Row N: fullStatement is empty, skipped」）。前後の空白をトリムしてから判定する（トリム後の値が空なら空扱い）。トリム後の値をそのまま fullStatement として保存する（先頭・末尾の空白は除去される）。**簡易形式の場合**: インデント（先頭の空白）から depth を算出した後にトリムする（インデント解析 → トリム → 空判定の順）
- `Identifier` が空 → UUID v4 自動採番
- `Identifier` がUUID形式でない → エラー（行スキップ。警告「Row N: Invalid Identifier 'xxx', skipped」）
- **同一CSV内で `Identifier` が重複** → 後の行を採用（警告「Row N: Duplicate Identifier 'xxx', overwriting Row M」）
- `educationLevel` のパース → カンマ区切りで文字列配列に変換（各値の前後空白をトリムし、トリム後の空文字列はフィルタする。例: `"09, 10, 11"` → `["09", "10", "11"]`、`"09,,11"` → `["09", "11"]`）
- `conceptKeywords` のパース → カンマ区切りで文字列配列に変換（各値の前後空白をトリムし、トリム後の空文字列はフィルタする。例: `"分析, 評価"` → `["分析", "評価"]`、`"分析,,評価"` → `["分析", "評価"]`）
- `parentIdentifier` / `Is Child Of` が非空かつUUID形式でない → 警告（「Row N: parentIdentifier 'xxx' is not a valid UUID, treated as root」）。ドキュメント直下として扱う
- `sequenceNumber` → 整数に変換。変換失敗時はエラー（行スキップ。警告「Row N: Invalid sequenceNumber 'xxx', skipped」）。値が PostgreSQL INTEGER 範囲（-2147483648 ～ 2147483647）を超える場合も変換失敗として同じ扱い
- `statusStartDate` → 非空の場合、`YYYY-MM-DD` 形式の有効な日付かを検証する。形式不正または無効な日付（例: `2025-13-45`）の場合は警告を出力し（「Row N: Invalid statusStartDate 'xxx', set to null」）、該当フィールドを NULL として扱う（行スキップではない）
- `statusEndDate` → `statusStartDate` と同じバリデーションルール（警告メッセージのフィールド名は `statusEndDate`）
- `license` → CFItemType と同じ lookup パターン。Step 5 で cf_license を find or create し、`cf_item.cf_license_id` に FK を設定する。空セルなら NULL（新規作成時）、または既存値を保持（更新時）
- `language` → 非空の場合、10文字以下であることを検証する。超過の場合は警告を出力し（「Row N: language 'xxx' exceeds 10 characters, set to null」）、値を NULL として扱う（行スキップではない。DB の `VARCHAR(10)` 制約によるトランザクション全体のロールバックを防止する）

**メタデータのバリデーション:**
- `#adoption_status` → 有効値（`Draft` / `Private Draft` / `Adopted` / `Deprecated`）以外の場合は警告を出力し（「Invalid adoption_status 'xxx', storing as-is」）、値をそのまま DB に保存する（エラーにしない）。APIレスポンスでもそのまま出力される
- `#language` → 10文字以下であることを検証する。超過の場合は警告を出力し（「Metadata #language 'xxx' exceeds 10 characters, set to null」）、値を NULL として扱う
- `#status_start_date` / `#status_end_date` → 非空の場合、`YYYY-MM-DD` 形式の有効な日付かを検証する。形式不正または無効な日付の場合は警告を出力し（「Invalid #status_start_date 'xxx', set to null」）、値を NULL として扱う

### ステップ5: lookup系テーブル自動生成

CSVの `CFItemType` 列・`license` 列・メタデータ `#subject`・メタデータ `#license` の値から、lookup系テーブル（cf_item_type, cf_license, cf_subject）のレコードを自動生成する。cf_concept は CSV インポートでは生成しない（外部 CASE ソースインポートの CFDefinitions.CFConcepts でのみ作成される）。

**前処理:** lookup のキーとなる値（CFItemType 列の値、`license` 列の値、`#license` の値、`#subject` の各要素）は前後空白をトリムしてからマッチングに使用する（トリム後の値を `title` として lookup テーブルに保存する）。トリム後に空文字列となる場合は「値なし」として扱う（lookup レコードの作成・検索を行わない）。`#subject` は csv-format.md のパース段階で個々の要素がトリム済みだが、`CFItemType` と `license` / `#license` は本ステップで追加でトリムする。

**マッチングルール（全lookup共通）:**
1. 同一テナント内で `title` の**完全一致**を検索（大文字小文字を区別する）
2. 一致するレコードが1件あれば、そのレコードのIDを使用
3. 一致するレコードが**複数件**あれば（外部CASEソースインポートで同一titleの異なるidentifierが作成された場合に発生しうる）、`identifier` の辞書順で最初のレコードを使用する（決定的な選択を保証する）
4. なければ新規レコードを作成（`identifier` = UUID v4、`uri` = `{BASE_URL}/{tenant_id}/uri/{identifier}`、`last_change_date_time` = インポート実行時のUTCタイムスタンプ）

**対象テーブルと元データ:**
| lookup テーブル | CSVの列 | 備考 |
|---------------|---------|------|
| cf_item_type | CFItemType | 値が空なら: 新規作成時は cf_item.cf_item_type_id = NULL、更新時は既存の cf_item_type_id を保持する（Step 6 の空セル→既存値保持ルールと同一） |
| cf_license | `license` 列（CFItem用）/ メタデータ `#license`（CFDocument用） | CFItemType と同じ title ベースの find or create パターン。`license` 列の値が空なら: 新規作成時は cf_item.cf_license_id = NULL、更新時は既存の cf_license_id を保持する。`#license` の値が空なら: 新規作成時は cf_document.cf_license_id = NULL、更新時は既存の cf_license_id を保持する。CFItem と CFDocument が同じ license 名を参照する場合、同一の cf_license レコードを共有する |
| cf_subject | メタデータ `#subject` | カンマ区切り。cf_documentの `subject` / `subject_uri` に格納 |

**JSONB配列の構築ルール（新規作成・更新共通）:**
- `cf_document.subject`: メタデータ `#subject` の値をそのまま文字列配列として格納（例: `["国語", "地理歴史"]`）
- `cf_document.subject_uri`: 各 cf_subject レコードの `{title, identifier, uri}` から LinkURI オブジェクト配列を構築（例: `[{"title":"国語","identifier":"<cf_subject.identifier>","uri":"<cf_subject.uri>"}]`）
- `cf_item.concept_keywords`: CSVの `conceptKeywords` の値をそのまま文字列配列として格納（例: `["分析", "評価"]`）

**cf_item.cf_concept_id について:** CSV に conceptKeywordsURI に対応するカラムは存在しない。CSV インポートでは `cf_concept_id` は設定されない（新規作成時は NULL、更新時は既存値を保持）。cf_concept レコードは外部 CASE ソースインポートの CFDefinitions.CFConcepts でのみ作成される。

**更新時の連動ルール:**
- CSVの `conceptKeywords` に値がある → `concept_keywords` を新しい値で更新する（`cf_concept_id` は連動しない。既存値を保持する）
- CSVの `conceptKeywords` が空セル → `concept_keywords` の既存値を保持する
- メタデータ `#subject` に値がある（1つ以上の subject 名がある） → `subject` と `subject_uri` の両方を新しい値で再構築する
- メタデータ `#subject` が記載されているが値が空（`#subject` のみ、または `#subject,` で値なし） → `subject` と `subject_uri` の両方を空配列 `[]` にクリアする
- メタデータ `#subject` が未記載（キー自体がない） → `subject` と `subject_uri` の両方とも既存値を保持する

### ステップ6: CFItem upsert

**upsertマッチングキー（優先順）:**

1. **Identifier一致**: 同一テナント内でCSVの `Identifier` が既存CFItemの `identifier` と一致 → 更新。一致したアイテムが別ドキュメントに属する場合は `cf_document_id` を現在のドキュメントに付け替える（**副作用**: 元ドキュメントの isChildOf Association がこのアイテムを参照し続けるが、depth は再計算されない。元ドキュメントの整合性を回復するには、元ドキュメントを再インポートするか、`doc delete` で削除する必要がある。付け替えが発生した場合は警告を出力する: 「Row N: Item '{item_identifier}' moved from document '{old_doc_identifier}' to current document」。`{old_doc_identifier}` は移動元ドキュメントの `identifier`（外部CASEインポートの同等の警告と同一形式）
2. **humanCodingScheme一致**（CSVの `Identifier` が空の場合のみ）: 同一テナント・同一ドキュメント内で `human_coding_scheme` が一致 → 更新。CSVの `Identifier` に値がある場合はこのフォールバックを適用しない（Identifier 指定行は Identifier のみでマッチし、不一致なら新規作成）。ただし NULL 同士はマッチしない（CSVの値が空、かつ既存も NULL の場合は不一致扱い）。一致するアイテムが複数存在する場合は `identifier` の辞書順で最初のアイテムを更新対象とする（決定的な選択を保証する。lookup テーブルの複数マッチルールと同一方針）
3. **いずれも不一致** → 新規作成

**更新時の動作:**
- CSVに値がある列 → 上書き
- CSVに値がない列（空セル、またはフォーマット定義にカラム自体が存在しない場合。例: OpenSALT形式の `listEnumeration`, `license`, `statusStartDate`, `statusEndDate`） → 既存値を保持（NULLで上書きしない）。**「空セル」の判定はパース前の原値で行う**（セル値が空文字列または未存在の場合。区切り文字のみの入力（例: `educationLevel` 列が `","` ）はパース前の原値が非空のため「値がある」として扱い、パース結果の `[]` で上書きされる）
- `uri` → 既存値を保持する（再生成しない。外部CASEソースインポート由来のアイテムの外部URIを上書きしないため）
- `last_change_date_time` → インポート実行時のUTCタイムスタンプで上書き

**新規作成時の動作:**
- `identifier` → CSVの値。空なら UUID v4 自動採番
- `uri` → `{BASE_URL}/{tenant_id}/uri/{identifier}`
- `language` → CSVの値。空なら CFDocument の `language` を継承（CFDocument も NULL なら NULL）
- `last_change_date_time` → インポート実行時のUTCタイムスタンプ

### ステップ7: CFAssociation (isChildOf) 生成

親子関係を `isChildOf` タイプの CFAssociation として保存する。

**parentIdentifier の解決:**
1. 独自形式・OpenSALT形式: `parentIdentifier` / `Is Child Of` 列の UUID で親を特定。検索スコープは同一テナント・同一ドキュメント内（現在のCSVでupsertされたアイテム + DB上の既存アイテム）。別ドキュメントのアイテムは対象外。自己参照（`parentIdentifier` が自身の `Identifier` と同一）の場合は警告を出力し（「Row N: parentIdentifier references self, treated as root」）、ドキュメント直下として扱う（自己参照の isChildOf は生成しない）
2. 簡易形式: インデントから depth を計算し、直前の浅い depth のアイテムを親とする
   - depth が2段以上ジャンプした場合（例: depth 0 → depth 3）: 直前のアイテムを親とし、警告を出力する（「Row N: depth jumped from 0 to 3, treating previous item as parent」）。中間の depth は作成しない
3. 親が見つからない場合: CFDocument を親とする（ルートレベル扱い）

**生成ルール:**
- `tenant_id` = インポート対象テナントの `id`
- `cf_document_id` = インポート対象 CFDocument の `id`（内部PK）
- `association_type` = `isChildOf`
- `identifier` = UUID v4 自動採番
- `uri` = `{BASE_URL}/{tenant_id}/uri/{identifier}`
- `origin_node_identifier` = 子アイテムの `identifier`
- `origin_node_uri` = 子アイテムの `uri`
- `origin_node_title` = 子アイテムの `fullStatement`
- `origin_node_target_type` = NULL（CSV インポートでは targetType を設定しない）
- `destination_node_identifier` = 親アイテムの `identifier`（親が CFDocument の場合は CFDocument の `identifier`）
- `destination_node_uri` = 親アイテムの `uri`（親が CFDocument の場合は CFDocument の `uri`）
- `destination_node_title` = 親アイテムの `fullStatement`（親が CFDocument の場合は `title`）
- `destination_node_target_type` = NULL（CSV インポートでは targetType を設定しない）
- `sequence_number` = CSVの `sequenceNumber`。空なら**同一親ごとに独立したカウンタ**で出現順に 10, 20, 30... を自動採番（各親が初めて登場した時点でその親のカウンタを 10 から開始する。同じ親の子が CSV 内で非連続に出現する場合もカウンタは継続する）。明示値と自動採番は独立で、明示値との重複回避はしない
- `last_change_date_time` = インポート実行時のUTCタイムスタンプ

**upsert時の既存Association処理:**
- 既存ドキュメントの更新時（`--doc` 指定、OpenSALT `Is Part Of` マッチ、または `#identifier` マッチ）で**データ行が 1 件以上ある場合**: 該当ドキュメントの既存 `isChildOf` Association を**全削除**してから、現 CSV から再生成する
- 既存ドキュメントの更新時で**データ行が 0 件**（メタデータのみの CSV）の場合: 既存のアイテムと `isChildOf` Association は**保持**され、CFDocument のメタデータ（`#title` / `#subject` 等）のみが更新される。非破壊的な警告を出力する（「No data rows in CSV; metadata updated, existing items and isChildOf preserved」）。意図的にツリーを消したい場合は将来追加予定の明示フラグ `--clear-items` を入口とする。それまでは暗黙的な wipe パスを設けない。この安全策は `#identifier` が「メタデータのみの CSV で誤って update を発火させる」操作を簡単に作れるようになったことを踏まえた措置
- 新規ドキュメント作成時: そのまま生成。処理アイテムが 0 件の場合は、空のドキュメントが作成される。この場合は警告を出力する（「No items processed, empty document created」）

### ステップ8: depth計算

インポート対象ドキュメント内の全CFItemの `depth` を、同ドキュメント内の isChildOf Association から計算する。他ドキュメントのアイテムは対象外。

**アルゴリズム:**
```
1. CFDocument直下のアイテム（parentがCFDocument）を depth=0 とする
2. BFS（幅優先探索）で isChildOf を辿り、子に parent.depth + 1 を設定
3. ステップ2 で到達できなかったアイテムのうち、isChildOf を一つも持たない
   アイテムをドキュメント直下のルート（depth=0）として扱い、そこから再度
   BFS を行う。OpenCASE 等、トップレベルアイテムに `isChildOf -> CFDocument`
   を出力しないエディタからの取り込みに対応するためのフォールバック
4. ステップ3 でも到達できなかったアイテム（孤立ノード）は depth=0 とする
   （警告「Orphan item '{identifier}' has no reachable parent, set to depth 0」）
5. 循環参照を検出した場合: 該当アイテムの depth=0 とし、エラーレポートに追記
```

**循環参照検出:**
BFS 中に訪問済みノード（既に depth が割り当てられたノード）に再到達した場合は、循環参照ではなく**複数親**（multi-parent、外部CASEインポートで発生しうる）として扱い、再訪問をスキップする（最初に割り当てた depth を保持する。BFS はレベル順に処理するため、最も浅い depth が割り当てられる）。
**真の循環参照**の検出: BFS 完了後、全 isChildOf の origin/destination をたどり、ルートから到達不可能なサイクル（全ノードがドキュメント直下でなく、かつ BFS で到達されなかったノード群）を検出する。サイクル内のノードは Step 3 の孤立ノードとして depth=0 が割り当てられるが、追加で循環参照として報告する（警告「Circular reference detected involving items: '{identifier1}', '{identifier2}', ..., set to depth 0」）。
**注意:** ルートから到達可能な循環（例: A→B→C→A で A がルート直下）は BFS で全ノードに depth が割り当てられるため検出されない。この場合、ツリービューで無限展開が可能になるが、HTMX の遅延ロードにより無限ループは発生しない（ユーザーが手動で展開を繰り返す必要がある）。

### ステップ9: 結果レポート

インポート完了後、結果サマリーを出力する（CLI: rich テーブル形式）。

```
Import Result:
  Document:     高等学校学習指導要領 (d86774f2-...)
  Items:        1523 created, 34 updated, 3 skipped
  Associations: 2045 created, 0 updated, 0 skipped
  ItemTypes:    5 created, 0 updated, 2 existing, 0 skipped
  Subjects:     3 created, 0 updated, 0 existing, 0 skipped
  Concepts:     0 created, 0 updated, 0 existing, 0 skipped
  Licenses:     0 created, 0 updated, 0 existing, 0 skipped
  Groupings:    0 created, 0 updated, 0 existing, 0 skipped

Warnings:
  Row 45: fullStatement is empty, skipped
  Row 102: Invalid Identifier 'abc', skipped
  Row 203: Parent 'f1a2b3c4-...' not found, treated as root
```

## 外部CASEソースインポート

外部CASE APIからCFPackageを取得してDBに保存する。

**トランザクション戦略:**
CSVインポートと同様に、全ステップ（3〜7）を単一トランザクションで実行する。途中でDBレベルのエラーが発生した場合はトランザクション全体をロールバックしてエラー終了する。個別リソースの不正（エラーハンドリング表の「CFPackage内の個別リソースが不正」）はスキップ扱いでありDBエラーではないため、トランザクションは継続する。

**同一ドキュメントへの同時インポート防止:**
CSVインポートと同様に、既存ドキュメント更新時は Step 3 で対象 CFDocument 行に `SELECT ... FOR UPDATE` を取得し、トランザクション終了まで保持する。新規ドキュメント作成時はロック不要。

### `--doc` オプションの動作

| 条件 | 動作 |
|------|------|
| `--doc` 未指定 | 外部 CFPackage の CFDocument identifier で同一テナント内の既存を検索。存在すれば更新、なければ新規作成 |
| `--doc {uuid}` 指定、同一テナント内に存在する | 既存 CFDocument を外部データで上書き更新 |
| `--doc {uuid}` 指定、同一テナント内に存在しない | エラー終了（「Document not found: '{uuid}'」） |

**更新時の動作（CFDocument / CFItem / CFAssociation / CFDefinitions 共通）:**
- 外部 CFPackage に値があるフィールド → 上書き
- 外部 CFPackage に値がないフィールド（null/未存在） → 既存値を保持
- `identifier` → 既存値を保持する（上書きしない。identifier は upsert のマッチングキーであり、変更すると UNIQUE 制約違反や既存の Association・URI 参照の整合性が破壊される。`--doc` 指定時に外部 CFDocument の identifier が異なる場合も、既存ドキュメントの identifier を維持する）
- `last_change_date_time` → 外部データの値をそのまま使用（外部データにもない場合はインポート実行時のUTCタイムスタンプ）
- 既存の CFItem / CFAssociation は**テナント内全体**で identifier 一致検索し upsert する。一致した既存アイテムが別ドキュメントに属する場合は `cf_document_id` を現在のドキュメントに付け替える（一致しないものは新規作成）。付け替えが発生した場合は警告を出力する（「Item '{identifier}' moved from document '{old_doc_identifier}' to current document」。CSVインポートの同等の警告と同一方針）
- 既存 CFDefinitions（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）は**テナント内全体**で identifier 一致検索し upsert する
- **外部ソースに含まれないリソースの扱い:** DB上に存在するが外部CFPackageに含まれないCFItem/CFAssociation/CFDefinitions（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）は削除しない（additive only）。外部ソース側でリソースが削除されても、DB上には残り続ける。完全な同期が必要な場合は、事前に `doc delete` で既存ドキュメントを削除してから再インポートする

### 処理フロー

**`--url` パラメータの形式:**
- CASE API ベースパス（バージョンパスまで含む）を指定する。例: `https://opensalt.example.com/ims/case/v1p0`、`https://case.example.com/{tenant}/ims/case/v1p1`
- または、CFPackage の直接URL を指定する。例: `https://opensalt.example.com/ims/case/v1p0/CFPackages/{uuid}`
- サーバールート（例: `https://opensalt.example.com`）は不可。下記フローで `/CFDocuments` を追加するため、CASE API パスが含まれていないと正しいエンドポイントに到達できない

```
1. URL解決・CFPackage JSON取得
   - URLパスが `/CFPackages/` を含む場合: そのURLに直接GETリクエスト
   - それ以外の場合（ベースURL）:
     a. URLの末尾スラッシュを正規化（あってもなくても動くようにする）
     b. GET {url}/CFDocuments で文書一覧を取得
     c. 文書一覧が空の場合: エラー終了（「No documents found on remote server: {url}」）
     d. 最初（または唯一）のドキュメントの identifier を使用。文書一覧が2件以上の場合は警告を出力する（「Remote server has {n} documents. Importing first document '{identifier}'」）
     e. GET {url}/CFPackages/{identifier} で取得
2. JSON をパース・バリデーション
3. CFDocument を作成/更新
4. CFDefinitions (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping) を保存（フィールドマッピング後述）
5. CFItems を一括保存
   - 全 CFItem の `cf_document_id` は Step 3 で作成/更新した CFDocument の内部PK（`id`）を設定する（既存アイテムの別ドキュメントからの付け替えも含む）
   - `CFItemTypeURI.identifier` がある場合: 同一テナント内の `cf_item_type` から `identifier` 一致で検索し、`cf_item.cf_item_type_id` に内部PK（`id`）を設定する。一致するレコードがない場合（Step 4 で保存されなかった場合）は `cf_item_type_id = NULL` とし、警告を出力する（「CFItem '{item_identifier}': CFItemType '{type_identifier}' not found, set to null」）
   - `conceptKeywordsURI.identifier` がある場合: 同一テナント内の `cf_concept` から `identifier` 一致で検索し、`cf_item.cf_concept_id` に内部PK（`id`）を設定する。一致するレコードがない場合は `cf_concept_id = NULL` とし、警告を出力する（「CFItem '{item_identifier}': CFConcept '{concept_identifier}' not found, set to null」。CFItemType FK 解決と同一パターン）
   - `educationLevel`, `conceptKeywords` → 外部データの値をそのまま JSONB として保存する（FK解決なし）
6. CFAssociations を一括保存
   - 全 CFAssociation の `cf_document_id` は Step 3 で作成/更新した CFDocument の内部PK（`id`）を設定する
   - `originNodeURI.title` / `destinationNodeURI.title` をそのまま `origin_node_title` / `destination_node_title` に保持
   - `CFAssociationGroupingURI.identifier` がある場合: 同一テナント内の `cf_association_grouping` から `identifier` 一致で検索し、`cf_association.cf_association_grouping_id` に内部PK（`id`）を設定する。一致するレコードがない場合は `cf_association_grouping_id = NULL` とし、警告を出力する（「CFAssociation '{assoc_identifier}': CFAssociationGrouping '{grouping_identifier}' not found, set to null」）
   - 既存の CFAssociation が別ドキュメントに属する場合は `cf_document_id` を現在のドキュメントに付け替える。付け替えが発生した場合は警告を出力する（「CFAssociation '{identifier}' moved from document '{old_doc_identifier}' to current document」。CFItem の付け替え警告と同一方針）
6.5. CFRubrics を保存（CFRubric → CFRubricCriterion → CFRubricCriterionLevel の3階層を upsert。詳細は「CFRubrics の扱い」節参照）
7. depth を計算（対象ドキュメント内の全 CFItem について、同ドキュメント内の全 isChildOf Association（既存保持分+新規インポート分）から再計算する。アルゴリズムは CSV インポートの Step 8 と同一）
8. 結果レポート出力（CSV インポートの Step 9 と同一フォーマット。各カテゴリのカウンタ: items/associations/rubrics は created/updated/skipped の3種、definitions は created/updated/existing/skipped の4種。warnings を併せて出力する。definitions の "updated" は identifier 一致で upsert し 1 つ以上のフィールドが変更された件数。"existing" は identifier 一致で upsert したがフィールド変更がなかった件数。"skipped" は identifier/title 欠落等のバリデーション不正でスキップされた件数。CSV インポートでは definitions の "updated" と "skipped" は常に 0（find or create のため更新しない。CSV 由来の値はバリデーション済みのためスキップも発生しない）。外部 CASE インポートでは "updated" と "skipped" が非 0 になりうる）
```

### CFDocument フィールドマッピング

外部 CFPackage の CFDocument オブジェクトから DB カラムへのマッピング:
- `identifier` → `identifier`（新規作成時のみ使用。更新時は既存値を保持）
- `uri` → `uri`（FR-7.2: source URI を **新規・更新の両方で** verbatim 保持。CFItem 側と同じ `_resolve_uri()` で処理）
- `title` → `title`
- `creator` → `creator`（CASE v1.1 OpenAPI では required だが本システムは nullable で受け入れる。新規作成時に欠落・null・空白文字列のいずれかであれば警告を出力した上で NULL として保存する。更新時はインポート規約「外部 CFPackage に値がない → 既存値を保持」に従い、キー未存在・null は既存値を保持し警告は出さない。空白文字列のみが指定された場合は警告を出した上で既存値を保持する（既存 creator を空文字へ上書きしない）。`null` 値・キー未存在・空文字列・空白のみは「missing」として同一扱い）
- `publisher` → `publisher`
- `description` → `description`
- `frameworkType` → `framework_type`（v1.1 new）
- `caseVersion` → `case_version`（v1.1 new。値は `"1.1"` のみ有効）
- `language` → `language`（10文字以下であることを検証する。超過の場合は NULL として保存し警告出力。CSV インポートと同一ルール）
- `version` → `version`
- `adoptionStatus` → `adoption_status`
- `statusStartDate` → `status_start_date`（`YYYY-MM-DD` 形式の文字列 → DATE 型。形式不正の場合は NULL として保存し警告出力。CFItem と同一ルール）
- `statusEndDate` → `status_end_date`（`statusStartDate` と同一ルール）
- `licenseURI` → `cf_license_id`（`licenseURI.identifier` で同一テナント内の cf_license を検索し、内部PK を設定する。一致する cf_license がない場合は `cf_license_id = NULL` とし、警告を出力する。CFItem の CFItemTypeURI FK 解決と同一パターン）
- `officialSourceURL` → `official_source_url`
- `subject` → `subject`（文字列配列 JSONB）
- `subjectURI` → `subject_uri`（LinkURI オブジェクト配列 JSONB）
- `lastChangeDateTime` → `last_change_date_time`（ISO 8601 文字列をパース。形式不正の場合はインポート実行時の UTC タイムスタンプを使用し警告出力。未存在の場合も同様。CFItem と同一ルール）
- `CFPackageURI.uri` → `cf_package_uri_source`（LinkURI の残り部分は emit 時に再構築する）。source URI を verbatim 保存することで、再 export 時に `BASE_URL` で上書きせず source の URI を返せる（OpenCASE / OBF round-trip のため必要。FR-7.2、詳細は [round_trip_status.md](../dev/round_trip_status.md) の cat G）。更新時、新しいペイロードに `CFPackageURI` キーがあれば上書きする（既存の「キー未存在 → 既存値を保持」のセマンティクスに沿う）
- `notes` → `notes`、`extensions` → `extensions`（新規・更新の両方で保存。未存在 → 既存値を保持）。コンテナレベルの `CFPackage.extensions` → `package_extensions`、`CFDefinitions.extensions` → `definitions_extensions` を CFDocument 行に保存する

### CFDefinitions フィールドマッピング

外部 CASE JSON のフィールド名（camelCase）を DB カラム名（snake_case）にマッピングする。共通フィールド（`identifier`, `uri`, `title`, `description`, `lastChangeDateTime`）は全 lookup テーブルで同一。`lastChangeDateTime` は ISO 8601 文字列をパースし、形式不正の場合はインポート実行時の UTC タイムスタンプを使用し警告出力する（CFItem の `lastChangeDateTime` と同一ルール）。未存在の場合も同様。固有フィールド:
- CFItemType: `typeCode` → `type_code`、`hierarchyCode` → `hierarchy_code`
- CFSubject: `hierarchyCode` → `hierarchy_code`
- CFConcept: `keywords` → `keywords`、`hierarchyCode` → `hierarchy_code`
- CFLicense: `licenseText` → `license_text`
- CFAssociationGrouping: 固有フィールドなし

### CFItem フィールドマッピング

外部 CFPackage の CFItem オブジェクトから DB カラムへのマッピング:
- `identifier` → `identifier`（新規作成時のみ使用。更新時は既存値を保持）
- `uri` → `uri`（FR-7.2: source URI を **新規・更新の両方で** verbatim 保持 — `case_import_service.py` の `_resolve_uri()`。source に `uri` が無い場合だけ `{BASE_URL}/{tenant}/uri/{identifier}` にフォールバック。同じルールが CFDocument / CFAssociation / CFRubric* / lookup リソースに適用される）
- `fullStatement` → `full_statement`（前後空白トリム後に保存。空の場合はスキップ）
- `humanCodingScheme` → `human_coding_scheme`
- `abbreviatedStatement` → `abbreviated_statement`
- `listEnumeration` → `list_enumeration`
- `language` → `language`（10文字以下であることを検証する。超過の場合は NULL として保存し警告出力。CSV インポートと同一ルール）
- `licenseURI` → `cf_license_id`（`licenseURI.identifier` で同一テナント内の cf_license を検索し、内部PK を設定する。一致する cf_license がない場合は `cf_license_id = NULL` とし、警告を出力する。CFDocument の licenseURI FK 解決と同一パターン）
- `statusStartDate` → `status_start_date`（`YYYY-MM-DD` 形式の文字列 → DATE 型。形式不正の場合は NULL として保存し警告出力）
- `statusEndDate` → `status_end_date`（`statusStartDate` と同一ルール）
- `educationLevel` → `education_level`（JSONB。外部データをそのまま保存）
- `subject` → `subject`（JSONB 文字列配列。外部データをそのまま保存。v1.1 new）
- `subjectURI` → `subject_uri`（JSONB LinkURI オブジェクト配列。外部データをそのまま保存。v1.1 new）
- `conceptKeywords` → `concept_keywords`（JSONB。外部データをそのまま保存）
- `conceptKeywordsURI` → `cf_concept_id`（`conceptKeywordsURI.identifier` で同一テナント内の cf_concept を検索し、内部PK を設定する。一致する cf_concept がない場合は `cf_concept_id = NULL` とし、警告を出力する。CFItemTypeURI FK 解決と同一パターン。CASE v1.1 では `conceptKeywordsURI` は単一の LinkURIDType）
- `CFItemTypeURI.identifier` → `cf_item_type_id` の FK 解決（Step 5 参照）
- `lastChangeDateTime` → `last_change_date_time`（ISO 8601 文字列をパース。形式不正の場合はインポート実行時の UTC タイムスタンプを使用し警告出力。未存在の場合も同様）
- `alternativeLabel` → `alternative_label`、`notes` → `notes`、`extensions` → `extensions`（いずれも新規・更新の両方で保存。未存在 → 既存値を保持）
- `CFDocumentURI` は API レスポンス生成時に動的構築するフィールドであり、DB に保存しない

### CFAssociation フィールドマッピング

外部 CFPackage の CFAssociation オブジェクトから DB カラムへのマッピング:
- `identifier` → `identifier`（新規作成時のみ使用。更新時は既存値を保持）
- `uri` → `uri`（新規作成時のみ使用。更新時は既存値を保持。URI保持ルール参照）
- `associationType` → `association_type`
- `originNodeURI.identifier` → `origin_node_identifier`
- `originNodeURI.uri` → `origin_node_uri`
- `originNodeURI.title` → `origin_node_title`
- `originNodeURI.targetType` → `origin_node_target_type`（v1.1 new。値は `"CASE"` or `"ext:*"` 等。NULL/未存在の場合は NULL）
- `destinationNodeURI.identifier` → `destination_node_identifier`
- `destinationNodeURI.uri` → `destination_node_uri`
- `destinationNodeURI.title` → `destination_node_title`
- `destinationNodeURI.targetType` → `destination_node_target_type`（v1.1 new。originNodeURI.targetType と同一ルール）
- `sequenceNumber` → `sequence_number`（INTEGER。数値以外の場合は NULL として保存し警告出力。浮動小数点数の場合は整数に切り捨て。PostgreSQL INTEGER 範囲（-2147483648 ～ 2147483647）を超える場合も NULL として保存し警告出力）
- `CFAssociationGroupingURI.identifier` → `cf_association_grouping_id` の FK 解決（Step 6 参照）
- `lastChangeDateTime` → `last_change_date_time`（CFItem と同一ルール）
- `notes` → `notes`、`extensions` → `extensions`（新規・更新の両方で保存。未存在 → 既存値を保持）
- `CFDocumentURI` は API レスポンス生成時に動的構築するフィールドであり、DB に保存しない

### CFItemType FK 解決の補足

CFItem の `CFItemTypeURI` がない場合（`CFItemTypeURI` が null/未存在で `CFItemType` 文字列のみの場合）: `cf_item_type_id = NULL` とする（文字列だけでは identifier ベースの FK 解決ができないため）。`CFItemType` 文字列は DB に保存されない（FK JOIN で CFItemType.title から導出する設計のため）。型情報を保持するには外部ソース側が `CFItemTypeURI` を提供する必要がある。

### 未サポートフィールド・リソースの扱い

外部 CFPackage に含まれるが DB にカラムがないフィールドは無視する（エラーにしない）:
- `CFPackageURI`（CFDocument）: API レスポンス生成時に動的構築するフィールドであり、DB に保存しない（ただし `CFPackageURI.uri` は round-trip のため `cf_package_uri_source` に保持。上記 CFDocument マッピング参照）
- `CFDocumentURI`（CFItem / CFAssociation）: API レスポンス生成時に動的構築するフィールドであり、DB に保存しない
- その他の未知フィールド: CASE v1.1 の将来的な拡張やサーバー固有フィールドは無視する

注: `notes`（CFDocument / CFItem / CFAssociation）、`alternativeLabel`（CFItem）、`extensions`（全リソース + コンテナレベルの `package_extensions` / `definitions_extensions`）は**保存される**（v1.1 対応で追加。上記フィールドマッピング各節および [db-schema.md](db-schema.md) 参照）。

**CFRubrics の扱い:**
外部 CFPackage に `CFRubrics` 配列が含まれている場合、Step 6.5（CFAssociations の後、depth 計算の前）で CFRubric / CFRubricCriterion / CFRubricCriterionLevel を upsert する。`CFRubrics` が存在しない場合はスキップする（エラーにしない）。

CFRubric の upsert ルールは CFItem / CFAssociation と同様:
- CFRubric: テナント内全体で `identifier` 一致検索
- 一致する場合は更新（非 null フィールドのみ上書き）
- 一致しない場合は新規作成
- CFRubricCriterion は**親 CFRubric のスコープ内**で `identifier` 一致 upsert（`UNIQUE(cf_rubric_id, identifier)`、#187）。CFRubricCriterionLevel は**親 CFRubricCriterion のスコープ内**で `identifier` 一致 upsert（`UNIQUE(cf_rubric_criterion_id, identifier)`）。同一 UUID が別の親 / テナントで重複しても衝突しない
- CFRubricCriterion の `CFItemURI.identifier` → 同一テナント内の `cf_item` から FK 解決（CFItem の FK 解決と同一パターン）
- `rubricId` / `rubricCriterionId` は参照用の UUID 値としてそのまま保存する（FK 解決不要）

バリデーション:
- CFRubric: `identifier` が欠落または UUID 形式でない → スキップ（警告出力）
- CFRubricCriterion: `identifier` が欠落または UUID 形式でない → スキップ（警告出力）
- CFRubricCriterionLevel: `identifier` が欠落または UUID 形式でない → スキップ（警告出力）

レポートカウンタ: `rubrics_created`, `rubrics_updated`, `rubrics_skipped`（CFRubric 単位。Criterion/Level のスキップは warnings に出力するがカウンタは持たない）

### URI保持ルール (FR-7.2)

CFPackage インポートは source の `uri` を verbatim 保持する — `case_import_service.py` の `_resolve_uri(source, tenant_id, identifier)` ヘルパーで実装。source dict に `uri` キーがあれば（空白文字列以外）それを使い、無ければ `{BASE_URL}/{tenant}/uri/{identifier}` にフォールバック。

挙動まとめ:
- **CFDocument / CFItem / CFAssociation / CFRubric / CFRubricCriterion / CFRubricCriterionLevel / CFDefinitions 系 lookup**: source `uri` は **新規・更新の両方で** DB に書き込まれる。別の上流から URI が変わった状態で再インポートすればその値で更新される
- **CFAssociation.originNodeURI.uri / destinationNodeURI.uri**: 同じく、source 値があれば優先（無ければ identifier から生成）
- **`identifier`**: source の値をそのまま保持（CASE round-trip 意味論に合致）
- **denormalized LinkURI フィールド**（`CFDocument.CFPackageURI.uri`、`CFRubricCriterion.CFItemURI.uri`）: 専用列（`cf_documents.cf_package_uri_source`、`cf_rubric_criteria.cf_item_uri_source`）に verbatim 保存し、再 export で同じ値を返す。詳細は [round_trip_status.md](../dev/round_trip_status.md) cat F / G
- **CSV インポート**: `_resolve_uri()` を経由せず、常に compeito-native な URI を生成（CSV 行は URI 列を持たないため）

自サーバーの `/uri/{uuid}` は `identifier` で検索するので、外部 URI のリソースも自サーバー経由でアクセス可能。

### エラーハンドリング

| エラー | 動作 |
|--------|------|
| 外部URLに接続できない（タイムアウト含む） | エラー終了。タイムアウトは各HTTPリクエストごとに30秒（ベースURLの場合、CFDocuments取得とCFPackage取得それぞれに30秒）。HTTPリダイレクト（301/302/307/308）は最大5回まで自動追従する。リトライしない |
| HTTPステータスが2xx以外 | エラー終了（「Remote server returned HTTP {status}: {url}」） |
| レスポンスがJSONとしてパースできない | エラー終了（「Response is not valid JSON」） |
| CFDocuments一覧レスポンスが不正（`CFDocuments` キーがない、配列でない等） | エラー終了（「Invalid CFDocuments response: {url}」） |
| JSONは有効だがCFPackage構造でない（下記参照） | エラー終了（「Invalid CFPackage response: {detail}」） |
| CFPackage内の個別リソースが不正（下記参照） | 該当リソースをスキップし、警告をレポートに追記。他のリソースは処理続行 |
| SSL証明書エラー | エラー終了（「SSL certificate verification failed」） |

**CFPackage構造バリデーション（エラー終了の条件）:**
以下のいずれかに該当する場合、「Invalid CFPackage response: {detail}」としてエラー終了する:
- ルートに `CFPackage` キーが存在しない（直接URLの場合）、または `CFDocuments` キーの配列内に期待される構造がない（ベースURL経由の場合）
- `CFPackage.CFDocument` が存在しない、またはオブジェクトでない
- `CFPackage.CFDocument.identifier` が存在しない、または UUID 形式でない
- `CFPackage.CFDocument.title` が存在しない、空文字列、または空白文字のみ（前後空白をトリムした後に空。新規ドキュメント作成時に DB の NOT NULL 制約違反となるため。既存ドキュメント更新時は既存値を保持するが、構造バリデーション段階では新規/更新を区別しないため一律でチェックする）

**個別リソースの不正（スキップの条件）:**
以下に該当する個別リソースはスキップし、警告を出力する:
- CFItem: `identifier` または `fullStatement` が欠落、または `fullStatement` が空文字列もしくは空白文字のみ（前後空白をトリムした後に空）。または `identifier` が UUID 形式でない（警告「Skipped CFItem: {reason}. identifier='{identifier}'」）
- CFAssociation: `identifier`, `associationType`, `originNodeURI`, `destinationNodeURI` のいずれかが欠落。または `associationType` が CASE v1.1 列挙値および拡張パターン（api-spec.md 参照。`ext:` プレフィックス付きの値も有効）に含まれない。または `originNodeURI` / `destinationNodeURI` 内の必須サブフィールド（`identifier`, `uri`）が欠落（DB の NOT NULL 制約違反を防止）。または `identifier` が UUID 形式でない（DB の UUID 型カラムへの格納不可を防止）。`originNodeURI.identifier` / `destinationNodeURI.identifier` は UUID 制限なし（LinkGenURIDType: 外部参照で非UUIDの場合あり。DB カラムは VARCHAR 型）（警告「Skipped CFAssociation: {reason}. identifier='{identifier}'」）
- CFDefinitions 内のリソース: `identifier` または `title` が欠落。または `identifier` が UUID 形式でない（警告「Skipped {resource_type}: {reason}. identifier='{identifier}'」）

### v1.0 → v1.1 正規化

CASE v1.0 の CFPackage レスポンスをフェッチ後、バリデーション前に v1.1 互換形式に正規化する。

**バージョン検出**（positive な v1.0 signal のみを使用。曖昧なペイロードは v1.1（現行仕様）として扱う）:
- URL に `v1p0` を含む場合は v1.0 と判定
- URL に `v1p1` を含む場合は v1.0 ではないと判定（パスを権威とみなし、ボディの `caseVersion` 有無に関わらず v1.1 として扱う）。OpenCASE のように v1.1 レスポンスから `caseVersion` フィールドを落とす実装に対する誤検出を防ぐためのルール
- URL にいずれのバージョンセグメントも含まれない場合（例: ファイル経由インポート）→ `CFDocument.caseVersion`（root、または `CFPackage` ラッパー内）を見る。`"1.0"` のみ v1.0 と判定。欠落 / `"1.1"` / その他の値はすべて NOT v1.0。`CFPackage` ラッパーの有無は v1.0 signal として扱わない（非準拠の v1.1 ソースもラップ形式で送ってくることがあるため、`_validate_cf_package()` も両方受け入れる）

**正規化ルール:**
- `conceptKeywordsURI`: 一部の v1.0 実装（OpenSALT 等）が配列を返す場合がある。配列の場合は先頭要素を使用し、複数要素がある場合は警告を出力
- v1.1 で追加されたフィールド（`frameworkType`, `caseVersion`, `subject`/`subjectURI`, `targetType`, `notes`, `extensions`）は v1.0 レスポンスには存在しないが、既存のインポートロジックが `.get()` で `None` をデフォルトとして処理するため追加の正規化は不要
- 構造差異（`CFPackage` ラッパーなし）は `_validate_cf_package` で既に対応済み

**出力:**
- v1.0 検出時に警告「Detected CASE v1.0 response, normalizing to v1.1 format」を出力

## ルーブリックCSVインポート処理フロー

```
1. CSVファイル読み込み（UTF-8、BOM自動スキップ）
2. ヘッダー行のパース・バリデーション（`Type` 列の存在確認）
3. 対象ドキュメントの取得（`--doc` 必須、`SELECT ... FOR UPDATE`）
4. 行ごとのパース・upsert（Rubric → Criterion → Level の位置コンテキスト解決）
5. 結果レポート出力
```

**トランザクション戦略:**
全ステップを単一トランザクションで実行する。エラー発生時はロールバック。行単位のバリデーションエラーはスキップ扱い。

### ステップ4: 行パース・upsert

**Type ごとの処理:**

- **Rubric**: `identifier` で同一テナント内の既存 CFRubric を検索し upsert。非 null フィールド（title, description）のみ上書き。新規作成時は `uri` を `{BASE_URL}/{tenant_id}/uri/{identifier}` で生成
- **Criterion**: 親 Rubric を `RubricIdentifier` または位置コンテキスト（直前の Rubric 行）から解決。**その親 Rubric のスコープ内**で `identifier` により既存 CFRubricCriterion を検索し upsert。`CFItemIdentifier` が指定されている場合は同一テナント内の CFItem から FK 解決（見つからない場合は NULL + 警告）
- **Level**: 親 Criterion を `CriterionIdentifier` または位置コンテキスト（直前の Criterion 行）から解決。**その親 Criterion のスコープ内**で `identifier` により既存 CFRubricCriterionLevel を検索し upsert

**バリデーション:**
- `Identifier` が空 → UUID v4 自動採番
- `Identifier` が UUID 形式でない → 行スキップ（警告出力）
- Criterion に親 Rubric がない（`RubricIdentifier` 空かつ直前に Rubric 行なし）→ 行スキップ（警告出力）
- Level に親 Criterion がない → 行スキップ（警告出力）
- 未知の Type → 行スキップ（警告出力）
- `Weight`, `Score` の数値変換失敗 → NULL として保存（警告出力）
- `Position` の整数変換失敗 → NULL として保存（警告出力）

### ステップ5: 結果レポート

```
Imported into 'Document Title' (doc-uuid)
  Rubrics:   1 created, 0 updated, 0 skipped
  Criteria:  2 created, 1 updated, 0 skipped
  Levels:    4 created, 0 updated, 1 skipped
```

## ルーブリックCSVエクスポート処理フロー

```
1. 対象ドキュメントの取得（--doc 必須）
2. 配下の CFRubric をクライテリア・レベルと共に取得
3. ルーブリック→クライテリア→レベルの順でCSV行を生成
```

**出力形式:**
- エンコーディング: UTF-8（BOM なし）、改行コード: LF
- ヘッダー: `Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier`
- ルーブリック: title 昇順 → identifier 辞書順
- クライテリア: position 昇順（NULL last）→ identifier 辞書順
- レベル: position 昇順（NULL last）→ identifier 辞書順
- CFItemIdentifier: クライテリアに紐づく CFItem の identifier を出力（紐づきなしなら空セル）

## CSVエクスポート処理フロー

```
1. CFDocument + 配下の全 CFItem を取得
2. 同一ドキュメント内（`cf_association.cf_document_id` が対象ドキュメントと一致）の isChildOf Association から親子関係を解決
3. ツリー順序（depth-first）でソート
4. 指定フォーマットでCSV生成
```

### エクスポート共通ルール

- エンコーディング: UTF-8（BOM なし）
- 改行コード: LF
- CSV構文: RFC 4180 準拠（フィールド内にカンマ・改行・ダブルクォートを含む場合はダブルクォートで囲む）

### 独自形式エクスポート

- CFDocumentの非NULLかつ非空のフィールドからメタデータ行を出力する（VARCHAR 型フィールドは NULL なら出力しない。FK 参照型フィールド `cf_license_id` は NULL なら出力しない、非 NULL なら `cf_license.title` を解決して `#license` として出力する。JSONB 配列型フィールド `subject` は NULL または空配列 `[]` なら出力しない。**round-trip 制約**: `[]`（空配列）は出力されないため、新規ドキュメントとしての re-import 時に `subject` / `subject_uri` は NULL に変わる。既存ドキュメントの更新時はキー未記載→既存値保持のため問題ない）。出力順: `#identifier`（再インポート時に CFDocument UUID を保持するため先頭に出力）, `#title`, `#version`, `#creator`, `#publisher`, `#description`, `#notes`, `#language`, `#adoption_status`, `#status_start_date`, `#status_end_date`, `#license`, `#official_source_url`, `#subject`）。`#status_start_date` / `#status_end_date` は `YYYY-MM-DD` 形式で出力する。メタデータ行もCSV行として出力するため、値にカンマ・改行・ダブルクォートが含まれる場合はRFC 4180に従いダブルクォートで囲む（例: `#description,"情報I, 情報II向け"`）。`#subject` は JSONB配列の各要素を個別のCSVフィールドとして出力する（単一のクォート文字列にまとめない。例: `#subject,国語,地理歴史,公民`）。個々の subject 値にカンマ等が含まれる場合は RFC 4180 に従い個別にクォートする（例: `#subject,国語,"情報I, 情報II",地理歴史`）
- ヘッダー行を出力する（`Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType,educationLevel,conceptKeywords,abbreviatedStatement,alternativeLabel,notes,language,listEnumeration,license,statusStartDate,statusEndDate`、16列）
- 全列を出力（Identifier含む）
- `parentIdentifier` には親アイテムのUUIDを出力。ルートレベルアイテム（親が CFDocument）の場合は空セル。1つのアイテムが複数の `isChildOf` association を持つ場合（外部CASEソースインポート由来）は、`sequence_number` が最小の association の親を採用する（NULL は非NULLの後に配置する。`sequence_number` が同じ場合は `destination_node_identifier` の辞書順で最初のもの）。**round-trip 制約**: 複数の isChildOf 親を持つアイテムは、エクスポート時に1つの親に集約される。このCSVを再インポートすると、選択されなかった親子関係は isChildOf 全削除→再生成により失われる
- `sequenceNumber` は `parentIdentifier` の決定に使用した isChildOf association の `sequence_number` を出力する（複数 isChildOf がある場合も、選択した association の値を使用）。NULL の場合は空セル。**round-trip 制約**: 空セルの `sequenceNumber` は re-import 時に自動採番（10, 20, 30...）に変わる。エクスポート時のソート順で自動採番されるため表示順序は維持されるが、実際の値は変化する
- `CFItemType` は `cf_item_type_id` から `cf_item_type.title` を解決して出力（`cf_item_type_id` が NULL なら空セル）。**round-trip 制約**: `title` のみ出力されるため、cf_item_type の `type_code`・`hierarchy_code`・`description` は CSV に含まれない。同一テナント内の再インポートでは title 一致で既存 cf_item_type レコードを使用するためこれらのフィールドは保持されるが、別テナントへのインポートでは title のみの新規レコードが作成され、これらのフィールドは欠落する
- `educationLevel` は JSONB 配列をカンマ区切り文字列に変換して出力（例: `["09","10","11","12"]` → `"09,10,11,12"`）。NULL または空配列 `[]` なら空セル。**round-trip 制約**: `[]`（空配列）は空セルとして出力されるため、新規作成での re-import 時に NULL に変わる（API レスポンスで `[]` と `null` は異なる出力となる。既存アイテムの更新時は空セル→既存値保持のため問題ない）
- `conceptKeywords` は JSONB 配列をカンマ区切り文字列に変換して出力（例: `["分析","評価"]` → `"分析,評価"`）。NULL または空配列 `[]` なら空セル（`educationLevel` と同じ round-trip 制約あり）。**制約**: 配列要素にカンマが含まれる場合（外部CASEソースインポート由来で発生しうる）、再インポート時にカンマで分割されて値が壊れる。この制約は `educationLevel` にも適用されるが、教育段階コードにカンマが含まれることは実運用上ない
- **`cf_concept_id` の round-trip 制約**: `conceptKeywordsURI`（cf_concept への FK 参照）は CSV に出力されない。CSV インポートでは `cf_concept_id` は設定されないため、外部 CASE ソースインポートで設定された `cf_concept_id` は CSV エクスポート→再インポートで失われる（NULL になる）。同一テナント内の更新時は空セル→既存値保持のため問題ない
- **`subject_uri` の round-trip 制約**: `subject_uri` は CSV に出力されない（`#subject` は subject 名のみ出力）。再インポート時にローカル cf_subject lookup テーブルから URI を再構築するため、外部 CASE ソースインポート由来の外部 URI はローカル URI に置き換わる。同一テナント内の更新では lookup レコードの identifier が一致するため URI は維持されるが、新規テナントへのインポートでは新しい identifier・URI が採番される
- **`framework_type` / `case_version` の round-trip 制約**: CSV メタデータに `#framework_type` / `#case_version` キーは存在しない。外部 CASE ソースインポートで設定された `framework_type` / `case_version` は CSV エクスポート→再インポートで失われる（NULL になる）。同一テナント内の更新時はキー未記載→既存値保持のため問題ない
- **CFItem `subject` / `subject_uri` の round-trip 制約**: CSV フォーマットに CFItem レベルの subject に対応するカラムは存在しない（`#subject` は CFDocument レベルのメタデータ）。外部 CASE ソースインポートで設定された CFItem の `subject` / `subject_uri` は CSV エクスポート→再インポートで失われる（新規作成時は NULL、既存アイテム更新時は空セル→既存値保持）
- `language` は `cf_item.language` をそのまま出力（NULL なら空セル）
- `abbreviatedStatement` は `cf_item.abbreviated_statement` をそのまま出力（NULL なら空セル）
- `listEnumeration` は `cf_item.list_enumeration` をそのまま出力（NULL なら空セル）
- `license` は `cf_item.cf_license_id` から `cf_license.title` を解決して出力（`cf_license_id` が NULL なら空セル）。CFItemType と同じ FK → JOIN パターン。**round-trip 制約**: `title` のみ出力されるため、cf_license の `license_text`・`description` は CSV に含まれない。同一テナント内の再インポートでは title 一致で既存 cf_license レコードを使用するためこれらのフィールドは保持されるが、別テナントへのインポートでは title のみの新規レコードが作成され、これらのフィールドは欠落する
- `statusStartDate` は `cf_item.status_start_date` を `YYYY-MM-DD` 形式で出力（NULL なら空セル）
- `statusEndDate` は `cf_item.status_end_date` を `YYYY-MM-DD` 形式で出力（NULL なら空セル）
- **cf_association_grouping の round-trip 制約**: cf_association_grouping は CSV に一切出力されない（CSV フォーマットに対応するカラムが存在しない）。外部 CASE ソースインポートで作成された cf_association_grouping レコードは、CSV エクスポート→別テナントへの CSV インポートで完全に失われる。同一テナント内の更新ではテナント所有の lookup レコードが DB 上に残るため影響はないが、テナント間のデータ移行には CSV ではなく外部 CASE ソースインポートを使用すべきである

### OpenSALT形式エクスポート

> OpenSALT の実際のフォーマットとの差異については [reference/opensalt-csv-format.md](../reference/opensalt-csv-format.md) を参照。

- メタデータ行は独自形式と同一のルールで出力する（`#title`, `#version`, ..., `#subject` の順。非NULLかつ非空のフィールドのみ出力）
- ヘッダー行: `Identifier,Full Statement,Human Coding Scheme,Abbreviated Statement,Notes,Concept Keywords,Education Level,CF Item Type,Language,License,Is Child Of,Sequence Number,Is Part Of`（13列）
- 列の対応:
  - `Identifier` → `cf_item.identifier`
  - `Full Statement` → `cf_item.full_statement`
  - `Human Coding Scheme` → `cf_item.human_coding_scheme`（NULL なら空セル）
  - `Abbreviated Statement` → `cf_item.abbreviated_statement`（NULL なら空セル）
  - `Notes` → `cf_item.notes`（NULL なら空セル）
  - `Concept Keywords` → JSONB 配列をカンマ区切りに変換（独自形式と同一ルール）
  - `Education Level` → JSONB 配列をカンマ区切りに変換（独自形式と同一ルール）
  - `CF Item Type` → `cf_item_type.title`（`cf_item_type_id` が NULL なら空セル）
  - `Language` → `cf_item.language`（NULL なら空セル）
  - `License` → 常に空セル（OpenSALTではライセンスはドキュメントレベルで管理するため、アイテムレベルでは出力しない）
  - `Is Child Of` → 親アイテムの identifier（独自形式の `parentIdentifier` と同一ロジック。ルートレベルなら空セル）
  - `Sequence Number` → isChildOf association の `sequence_number`（独自形式の `sequenceNumber` と同一ロジック）
  - `Is Part Of` → CFDocument の `identifier`（全行で同一値）
- ソート順序は独自形式と同一（depth-first、上記「ソート順序」セクション参照）
- round-trip 制約は独自形式と同一（`License` 列が常に空のため、アイテムレベルの `cf_license_id` は round-trip で失われる。ドキュメントレベルのライセンスはメタデータ行 `#license` で保持される）

### ソート順序

ツリーの depth-first 順でソートする:
1. ルートレベルのアイテムを `sequence_number` 昇順で並べる（isChildOf で CFDocument を parent とするアイテム）
2. 各アイテムの子を `sequence_number` 昇順で再帰的に挿入
3. isChildOf の `sequence_number` が NULL のアイテムは、同一親の子の中で最後に配置する
4. `sequence_number` が同じ場合は `human_coding_scheme` の自然順ソート（数値部分を数値として比較する。例: `"A-2"` < `"A-10"`。Python の `natsort.natsorted()` をデフォルト設定（`alg=natsort.ns.DEFAULT`）で使用する。ロケール依存のソートは使わない（`humansorted` / `os_sorted` は不使用）。NULL は非NULLの後に配置する）
5. それも同じ場合は `identifier` の辞書順
6. 孤立アイテム（isChildOf Association を持たないアイテム）は通常ルートアイテムの後に配置する。孤立アイテム間のソートは `human_coding_scheme` 自然順 → `identifier` 辞書順（ツリービューの孤立アイテム表示順と同一）
