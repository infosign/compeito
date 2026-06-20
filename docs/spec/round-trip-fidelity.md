# Round-trip Fidelity (CASE JSON vs Excel vs CSV)

Which CASE v1.1 fields survive an import → export round-trip on each interchange
path. The short version: **CASE JSON (CFPackage) is full fidelity; Excel is an
OpenSALT-compatible subset; CSV is a smaller subset.** Whether a field is kept or
lost is a property of the *format's expressiveness*, not of the tool's CASE
version — if a format has no place to put a field, even a fully v1.1-compliant
tool drops it on that path.

Related docs:
[csv-format.md](csv-format.md) (column-level CSV/Excel spec),
[import-logic.md](import-logic.md) (upsert rules),
[../guide/opencase-interop.md](../guide/opencase-interop.md) (JSON handoff),
[../dev/round_trip_status.md](../dev/round_trip_status.md) (JSON losslessness test status).

## How to read the matrices

| Mark | Meaning |
|------|---------|
| ✓ | Preserved across the round-trip |
| △ | Partially preserved (only a sub-field such as `title`, or the value is regenerated) |
| ✗ | Dropped (no column, hard-coded `None`, or not wired in import/export) |
| — | Not applicable |

CSV has three profiles. Where they differ, **Custom** and **OpenSALT** get their
own columns below; the **Simple** profile is positional (auto-assigns
`identifier`/`sequenceNumber`, keeps only the first few columns) and is covered in
[Cross-cutting behaviour](#cross-cutting-behaviour).

## TL;DR — what is JSON-only

These are preserved by CASE JSON but lost (or only partially kept) on **both**
Excel and CSV:

- **`targetType`** (CFAssociation origin/destination, v1.1) — the cross-framework marker.
- **`notes`** on CFAssociation (v1.1).
- **`extensions`** on every resource (v1.1).
- **CFDocument `frameworkType`, `caseVersion`** (v1.1).
- **CFItem `subject` / `subjectURI`** (v1.1, item-level).
- **CFConcept** (whole resource), and the non-label fields of **CFItemType /
  CFSubject / CFLicense / CFAssociationGrouping**.
- **CFRubric / CFRubricCriterion / CFRubricCriterionLevel** are absent from Excel
  entirely (CSV handles them only via the dedicated rubric CSV).

Notice the pattern: **almost everything CASE *added* in v1.1 is JSON-only.** The
flat-file formats predate those fields and have no column for them.

## CFDocument

| Field | JSON | Excel | CSV (Custom) | CSV (OpenSALT) | Notes |
|-------|:----:|:-----:|:------------:|:--------------:|-------|
| identifier | ✓ | ✓ | ✓ | ✓ | find-or-create key |
| title | ✓ | ✓ | ✓ | ✓ | |
| creator | ✓ | ✓ | ✓ | ✓ | |
| publisher | ✓ | ✓ | ✓ | ✓ | |
| description | ✓ | ✓ | ✓ | ✓ | |
| version | ✓ | ✓ | ✓ | ✓ | |
| language | ✓ | ✓ | ✓ | ✓ | |
| adoptionStatus | ✓ | ✓ | ✓ | ✓ | |
| officialSourceURL | ✓ | ✓ | ✓ | ✓ | |
| statusStartDate | ✓ | ✓ | ✓ | ✓ | |
| statusEndDate | ✓ | ✓ | ✓ | ✓ | |
| notes | ✓ | ✓ | ✓ | ✓ | |
| subject | ✓ | ✓ | ✓ | ✓ | string array (`\|`-joined in Excel) |
| subjectURI | ✓ | ✗ | △ | △ | flat formats keep only the `subject` title; identifier/uri regenerated |
| licenseURI | ✓ | △ | △ | △ | Excel: `title` + `licenseText` (text exported but **not re-imported**); CSV: `title` only |
| frameworkType | ✓ | ✗ | ✗ | ✗ | v1.1; no column |
| caseVersion | ✓ | ✗ | ✗ | ✗ | v1.1; no column |
| CFPackageURI | ✓ | ✗ | ✗ | ✗ | `.uri` kept verbatim in JSON |
| extensions | ✓ | ✗ | ✗ | ✗ | v1.1; no column |
| uri | ✓ | △ | △ | △ | JSON keeps source URI; flat formats rebuild from identifier |
| lastChangeDateTime | △ | ✗ | ✗ | ✗ | re-stamped on import (see caveats) |

## CFItem

| Field | JSON | Excel | CSV (Custom) | CSV (OpenSALT) | Notes |
|-------|:----:|:-----:|:------------:|:--------------:|-------|
| identifier | ✓ | ✓ | ✓ | ✓ | blank → new UUID |
| fullStatement | ✓ | ✓ | ✓ | ✓ | |
| humanCodingScheme | ✓ | ✓ | ✓ | ✓ | |
| abbreviatedStatement | ✓ | ✓ | ✓ | ✓ | |
| notes | ✓ | ✓ | ✓ | ✓ | |
| language | ✓ | ✓ | ✓ | ✓ | |
| conceptKeywords | ✓ | ✓ | ✓ | ✓ | string array |
| educationLevel | ✓ | ✓ | ✓ | ✓ | string array |
| CFItemType (label) | ✓ | ✓ | ✓ | ✓ | find-or-create by title |
| listEnumeration | ✓ | ✓ | ✓ | ✗ | no column in OpenSALT item sheet |
| alternativeLabel | ✓ | ✗ | ✓ | ✗ | Excel forces `""`; not in OpenSALT |
| statusStartDate | ✓ | ✗ | ✓ | ✗ | not in OpenSALT item sheet |
| statusEndDate | ✓ | ✗ | ✓ | ✗ | not in OpenSALT item sheet |
| licenseURI | ✓ | ✗ | △ | ✗ | Custom CSV: `title` only; Excel column unused; OpenSALT ignores it |
| subject | ✓ | ✗ | ✗ | ✗ | v1.1 (item-level) |
| subjectURI | ✓ | ✗ | ✗ | ✗ | v1.1 (item-level) |
| conceptKeywordsURI | ✓ | ✗ | ✗ | ✗ | only the plain `conceptKeywords` strings survive |
| CFItemTypeURI | ✓ | △ | △ | △ | only the type label survives; identifier/uri rebuilt from FK |
| extensions | ✓ | ✗ | ✗ | ✗ | v1.1; no column |
| CFDocumentURI | ✓ | ✓ | ✓ | ✓ | implicit (item belongs to the document) |
| uri | ✓ | △ | △ | △ | JSON keeps source URI; flat formats rebuild from identifier |
| lastChangeDateTime | △ | ✗ | ✗ | ✗ | re-stamped on import |

The parent/child hierarchy (`isChildOf` + `sequenceNumber`) is **not** a CFItem
field but is carried alongside items: Excel uses the `smartLevel` column, CSV
Custom uses `parentIdentifier`/`sequenceNumber`, CSV Simple uses indentation.

## CFAssociation

| Field | JSON | Excel | CSV | Notes |
|-------|:----:|:-----:|:---:|-------|
| identifier | ✓ | ✓ | ✗ | CSV regenerates a UUID each round-trip |
| associationType | ✓ (all) | ✓ (all) | ✗ | **CSV can only express `isChildOf`** (parent/child); Excel carries every type in the CF Association sheet |
| originNodeURI.uri | ✓ | ✓ | ✓ | CSV value is generated for the isChildOf link |
| originNodeURI.identifier | ✓ | ✓ | ✓ | |
| originNodeURI.title | ✓ | ✗ | △ | Excel stores uri + identifier only |
| **originNodeURI.targetType** | ✓ | ✗ | ✗ | v1.1; CSV hard-codes `None` |
| destinationNodeURI.uri | ✓ | ✓ | ✓ | |
| destinationNodeURI.identifier | ✓ | ✓ | ✓ | |
| destinationNodeURI.title | ✓ | ✗ | △ | |
| **destinationNodeURI.targetType** | ✓ | ✗ | ✗ | v1.1; CSV hard-codes `None` |
| sequenceNumber | ✓ | ✗ | ✓ | CSV: only on isChildOf rows |
| CFAssociationGroupingURI | ✓ | ✓ | ✗ | Excel carries grouping identifier + title |
| notes | ✓ | ✗ | ✗ | v1.1; no column |
| extensions | ✓ | ✗ | ✗ | v1.1; no column |
| CFDocumentURI | ✓ | ✓ | ✓ | implicit |
| uri | ✓ | ✓ | ✗ | CSV regenerates |

> **Cross-tenant / cross-framework associations** (e.g. `exactMatchOf` pointing at
> another framework) round-trip **fully in JSON**. In **Excel** the association and
> its type survive, but `targetType` and the node `title`s are lost. In **CSV** the
> association cannot be expressed at all (CSV only emits `isChildOf`). Note that
> Excel splits the work: `isChildOf` lives in the CF Item `smartLevel` column and is
> *excluded* from the CF Association sheet, which carries every other type.

## CFDefinitions (lookup resources)

Excel has three sheets (CF Doc / CF Item / CF Association) and CSV has item +
rubric layouts; neither has dedicated sheets/rows for definition resources. They
survive only as labels embedded in other rows, if at all.

| Resource | JSON | Excel | CSV | What survives on flat-file paths |
|----------|:----:|:-----:|:---:|----------------------------------|
| CFItemType | ✓ | △ | △ | `title` label only; `description` / `hierarchyCode` / `typeCode` dropped |
| CFConcept | ✓ | ✗ | ✗ | nothing (the plain `conceptKeywords` strings are a different thing) |
| CFSubject | ✓ | △ | △ | `title` only; `hierarchyCode` / `description` dropped |
| CFLicense | ✓ | △ | △ | `title` (+ `licenseText` exported-only in Excel); `identifier` / `uri` / `description` dropped |
| CFAssociationGrouping | ✓ | △ | ✗ | Excel: `identifier` + `title`; `description` / `extensions` dropped |

> A definition resource that is **not referenced** by any document/item/association
> is omitted from a CFPackage export even on the JSON path (the package only emits
> definitions reachable from the document). Fetch it via the single-resource API if
> you need the orphan.

## CFRubric / CFRubricCriterion / CFRubricCriterionLevel

Excel has **no rubric sheet** — rubrics are dropped entirely on the Excel path.
CSV handles rubrics only through the dedicated rubric CSV
(`import rubric` / `export rubric`), separate from the item CSV.

| Field | JSON | Excel | Rubric CSV | Notes |
|-------|:----:|:-----:|:----------:|-------|
| CFRubric.identifier / title / description | ✓ | ✗ | ✓ | |
| CFRubricCriterion.identifier / category / description / weight / position / rubricId | ✓ | ✗ | ✓ | |
| CFRubricCriterion.CFItemURI | ✓ | ✗ | △ | CSV keeps the linked item `identifier` only; title/uri rebuilt |
| CFRubricCriterion.rubricCriterionText | ✗ | ✗ | ✗ | **dropped on every path** — DB column exists but is not wired in import/export |
| CFRubricCriterionLevel.identifier / description / quality / score / feedback / position / rubricCriterionId | ✓ | ✗ | ✓ | |
| extensions (all rubric resources) | ✓ | ✗ | ✗ | v1.1 |
| uri (all rubric resources) | ✓ | ✗ | ✗ | CSV regenerates; levels get a synthetic `urn:csv-import:{uuid}` |

`rubricCriterionText` is the **only** CASE v1.1 field that even the JSON path does
not round-trip.

## Cross-cutting behaviour

- **`lastChangeDateTime` is re-stamped on import on every path, including JSON.**
  The DB stores it and export emits it, but import overwrites it with the current
  time, so the *original* timestamp is not preserved. The JSON losslessness test
  ignores this field by design (see
  [round_trip_status.md](../dev/round_trip_status.md)).
- **`uri`:** JSON import keeps the source `uri` verbatim (resolved gaps A/F/G in
  the losslessness work). CSV/Excel rebuild every URI from the `identifier`, so the
  stored URI string does not survive those paths.
- **`identifier`:** preserved when a column carries it (CFDocument/CFItem
  identifier on all paths; CFAssociation identifier in Excel). CSV regenerates
  CFAssociation, definition, and rubric-level UUIDs on each round-trip.
- **LinkURI sub-fields:** `title`/`identifier`/`uri` of *referenced-resource*
  LinkURIs (`CFItemTypeURI`, `conceptKeywordsURI`, `licenseURI`,
  `CFAssociationGroupingURI`, document `licenseURI`) are rebuilt from the FK target
  in JSON — so they survive if the target is in the same package, reflecting the
  target's current values. On flat-file paths usually only a label survives.
- **Association node identifiers** that are UUIDs are lower-cased on JSON import
  (value-equivalent; cosmetic only).
- **CSV Simple profile** is positional: it auto-assigns `identifier` and
  `sequenceNumber` and keeps only the leading columns, dropping most optional
  fields. Use the **Custom** profile when you need to edit and re-import safely.

## Choosing a path

- **Full fidelity / archival / cross-framework** (need `targetType`, `notes`,
  `extensions`, definition resources, rubrics): use **CASE JSON (CFPackage)**.
  This is also what the OpenCASE interop flow uses end-to-end, so OpenCASE ↔
  COMPEITO keeps everything.
- **OpenSALT interchange:** use **Excel** (3-sheet workbook) — the highest-fidelity
  flat-file path, but it still drops `targetType`, `notes`, `extensions`, and
  rubrics.
- **Quick human edits / first ingest:** use **CSV (Custom)**. Remember CSV can only
  express `isChildOf`; other association types need Excel or JSON.
- **Rubrics over a flat-file path:** only the dedicated **rubric CSV** carries them
  (there is no Excel rubric sheet).
