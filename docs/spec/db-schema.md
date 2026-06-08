# DB Schema Design

## Design principles

**FK delete policy:**
Use `ON DELETE CASCADE` for ownership FKs and `ON DELETE SET NULL` for nullable reference FKs.

CASCADE (ownership):
- `tenant_id` → deleting a tenant cascades to cf_document, cf_item, cf_association, cf_rubric, and every lookup table.
- `cf_document_id` → deleting a document cascades to its cf_item, cf_association, and cf_rubric. Lookup tables (cf_item_type, cf_subject, cf_concept, cf_license, cf_association_grouping) are owned by the **tenant**, so they survive. Lookup records no longer referenced from any document become orphans inside the tenant (still returned by CASE API listing endpoints; we do not auto-clean them). **Cross-document references**: if another document's CFAssociation references items in the deleted document via `origin_node_identifier` / `destination_node_identifier`, those references become dangling. Those columns are VARCHAR without an FK constraint, so neither CASCADE nor SET NULL fires. The associations remain and continue to be returned by the API (their referenced `/uri/{uuid}` returns 404).
- `cf_rubric_id` → deleting a rubric cascades to its cf_rubric_criterion rows.
- `cf_rubric_criterion_id` → deleting a criterion cascades to its cf_rubric_criterion_level rows.

SET NULL (references):
- `cf_document.cf_license_id` → on CFLicense delete, set the document's license reference to NULL (keep the document).
- `cf_item.cf_item_type_id` → on CFItemType delete, set the item's type reference to NULL (keep the item).
- `cf_item.cf_license_id` → on CFLicense delete, set the item's license reference to NULL (keep the item).
- `cf_item.cf_concept_id` → on CFConcept delete, set the item's concept reference to NULL (keep the item).
- `cf_association.cf_association_grouping_id` → on CFAssociationGrouping delete, set the association's grouping reference to NULL (keep the association).

**Why `id` and `identifier` are separate:**
`identifier` is the CASE-spec-level resource identifier (preserved as-is on import from external sources). `id` is the internal PK (used by foreign keys). This separation prevents internal FK relationships from breaking when an external `identifier` changes.

**UNIQUE scope of `identifier`:**
`identifier` carries a composite uniqueness constraint `UNIQUE(tenant_id, identifier)` (tenant-scoped). CASE specifies UUIDs as globally unique, but in a multi-tenant deployment several tenants may import the same external framework (e.g., a national curriculum standard), so we relax uniqueness to per-tenant. `/uri/{uuid}` lookups are tenant-scoped, so there's no functional impact.

**TIMESTAMP type:**
All `TIMESTAMP` columns are `TIMESTAMPTZ` (`TIMESTAMP WITH TIME ZONE`). PostgreSQL stores TIMESTAMPTZ internally in UTC. API responses emit ISO 8601 UTC with a trailing `Z`.

## Tables

### tenant
```
id: UUID PK  ← the UUID used in the public URL /{tenant-uuid}/
name: VARCHAR NOT NULL
is_private: BOOLEAN NOT NULL DEFAULT false
created_at: TIMESTAMP NOT NULL DEFAULT now()
```

### cf_document
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_license_id: UUID FK(cf_license.id) NULLABLE
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR NOT NULL
creator: VARCHAR                 -- Required in CASE v1.1 but nullable here to accommodate CSV imports that omit it. Phase 2 will consider defaulting to an empty string.
publisher: VARCHAR
description: TEXT
framework_type: VARCHAR      -- v1.1 new. Standard value "CourseCodes" (free-form string per OpenAPI).
case_version: VARCHAR        -- v1.1 new. OpenAPI enum: ["1.1"]. Only "1.1" is valid.
language: VARCHAR(10)
version: VARCHAR
adoption_status: VARCHAR
status_start_date: DATE
status_end_date: DATE
official_source_url: VARCHAR
subject: JSONB           -- string array, e.g., ["Math", "Science"]
subject_uri: JSONB       -- LinkURI object array, e.g., [{"title":"Math","identifier":"uuid","uri":"https://..."}]
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
```

**Note**: `UNIQUE(tenant_id, identifier)` automatically creates a composite B-tree index, so a standalone `INDEX(tenant_id)` is unnecessary (covered by the leading column of the UNIQUE). A standalone `INDEX(identifier)` is also unnecessary (all queries are tenant-scoped and use `UNIQUE(tenant_id, identifier)`). The same applies to the tables below.

### cf_item
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
cf_item_type_id: UUID FK(cf_item_type.id) NULLABLE
cf_license_id: UUID FK(cf_license.id) NULLABLE
cf_concept_id: UUID FK(cf_concept.id) NULLABLE
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
full_statement: TEXT NOT NULL
human_coding_scheme: VARCHAR
list_enumeration: VARCHAR
abbreviated_statement: TEXT
concept_keywords: JSONB    -- string array, e.g., ["analysis", "evaluation"]
education_level: JSONB     -- string array, e.g., ["09", "10", "11", "12"]
subject: JSONB             -- string array, e.g., ["Math"]. v1.1 new. Same shape as CFDocument.
subject_uri: JSONB         -- LinkURI object array. v1.1 new. Same shape as CFDocument.
language: VARCHAR(10)
status_start_date: DATE
status_end_date: DATE
depth: INTEGER NOT NULL DEFAULT 0  -- Tree depth (0 = directly under the document). Computed by recursively following isChildOf on import.
                                   -- Orphan nodes (unresolved isChildOf target) get depth=0.
                                   -- When a cycle is detected, depth=0 is used and an entry is added to the error report (the item itself is still stored).
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
INDEX(tenant_id, cf_document_id, human_coding_scheme)  -- for upsert matching
INDEX(cf_document_id, depth)  -- for the tree view's level detection (also covers `INDEX(cf_document_id)` alone)
```

### cf_association
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
association_type: VARCHAR NOT NULL  -- CASE v1.1 enum: isChildOf, isPeerOf, isPartOf, exactMatchOf, precedes, isRelatedTo, replacedBy, exemplar, hasSkillLevel, isTranslationOf
origin_node_uri: VARCHAR NOT NULL
origin_node_identifier: VARCHAR NOT NULL  -- LinkGenURIDType: not restricted to UUID (external refs may not be UUIDs)
origin_node_title: VARCHAR               -- LinkGenURIDType.title; kept for external refs that can't be resolved via JOIN
origin_node_target_type: VARCHAR         -- LinkGenURIDType.targetType. v1.1 new. "CASE" or "ext:*"
destination_node_uri: VARCHAR NOT NULL
destination_node_identifier: VARCHAR NOT NULL  -- LinkGenURIDType: not restricted to UUID
destination_node_title: VARCHAR               -- LinkGenURIDType.title; kept for external refs that can't be resolved via JOIN
destination_node_target_type: VARCHAR         -- LinkGenURIDType.targetType. v1.1 new. "CASE" or "ext:*"
sequence_number: INTEGER
cf_association_grouping_id: UUID FK(cf_association_grouping.id) NULLABLE
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
INDEX(origin_node_identifier), INDEX(destination_node_identifier)
INDEX(cf_document_id, destination_node_identifier)  -- for tree children queries (also covers `INDEX(cf_document_id)` alone)
```

### Cross-table UUID lookup (`/uri/{uuid}`)
`identifier` carries a composite UNIQUE `UNIQUE(tenant_id, identifier)` across every table. The `/{tenant}/uri/{uuid}` router searches within the tenant scope, in this order: cf_document → cf_item → cf_association → cf_item_type → cf_subject → cf_concept → cf_license → cf_association_grouping (stops at the first hit).

### Common columns for lookup tables

Every lookup table shares these columns:
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR NOT NULL
description: TEXT
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
INDEX(tenant_id, title)  -- for the CSV import find-or-create pattern
```

### cf_item_type (additional columns)
```
type_code: VARCHAR         -- CASE v1.1 typeCode (e.g., "knowledge-and-skills")
hierarchy_code: VARCHAR    -- CASE v1.1 hierarchyCode (e.g., "1")
```

### cf_subject (additional columns)
```
hierarchy_code: VARCHAR    -- CASE v1.1 hierarchyCode
```

### cf_concept (additional columns)
```
keywords: VARCHAR          -- CASE v1.1 keywords (pipe-delimited string, e.g., "analysis|evaluation")
hierarchy_code: VARCHAR    -- CASE v1.1 hierarchyCode
```

### cf_license (additional columns)
```
license_text: TEXT         -- License body text
```

### cf_association_grouping
Common columns only (no additional columns).

### Lookup table operation rules

On CSV import, lookups are performed **within the tenant** by exact `title` match; if none, a new record is auto-generated (find-or-create). Title matching is case-sensitive. When a match is found, the record is reused as-is and its fields are not updated.
Lookups are not shared across tenants. If nothing matches, a new UUID is allocated and the row is created.
CFSubject is referenced by URI from CFDocument's `subject_uri` JSONB array. CFConcept is referenced by `cf_concept_id` FK from CFItem (CSV import does **not** generate cf_concept rows; only the external CASE source import creates them).
Lookup-specific columns (typeCode, etc.) are not set by CSV imports; they only receive values from the external CASE source import.

### cf_rubric (Phase 2; schema created in Phase 1)
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR
description: TEXT
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
INDEX(cf_document_id)  -- for retrieving rubrics under a document in CFPackage responses
```

### cf_rubric_criterion
```
id: UUID PK
cf_rubric_id: UUID FK(cf_rubric.id) NOT NULL
identifier: UUID UNIQUE NOT NULL       -- standalone UNIQUE since this table has no tenant_id (Phase 2 will refine)
                                       -- **Design risk**: a global UNIQUE causes a constraint violation if multiple tenants import the same external source (same UUID). Phase 2 will consider adding tenant_id.
uri: VARCHAR NOT NULL
cf_item_id: UUID FK(cf_item.id) NULLABLE  -- CASE v1.1 CFItemURI; FK to the related CFItem
rubric_id: UUID                          -- CASE v1.1 rubricId; the parent CFRubric's identifier (could also be resolved via JOIN on cf_rubric.identifier)
category: VARCHAR
description: TEXT
weight: FLOAT
position: INTEGER
rubric_criterion_text_plain: TEXT   -- Custom column (no corresponding field in CASE v1.1). Display text analogous to cf_item.fullStatement.
last_change_date_time: TIMESTAMP NOT NULL
INDEX(cf_rubric_id), INDEX(identifier)
```

### cf_rubric_criterion_level
```
id: UUID PK
cf_rubric_criterion_id: UUID FK(cf_rubric_criterion.id) NOT NULL
rubric_criterion_id: UUID                -- CASE v1.1 rubricCriterionId; the parent CFRubricCriterion's identifier
identifier: UUID UNIQUE NOT NULL       -- standalone UNIQUE since this table has no tenant_id (Phase 2 will refine; same risk as cf_rubric_criterion)
uri: VARCHAR NOT NULL
description: TEXT
quality: VARCHAR
score: FLOAT
feedback: TEXT                           -- CASE v1.1 feedback (optional)
position: INTEGER
last_change_date_time: TIMESTAMP NOT NULL
INDEX(cf_rubric_criterion_id), INDEX(identifier)
```

### CASE v1.1 standard fields (notes / alternativeLabel / extensions)
These CASE v1.1 fields are stored and round-trip through CASE JSON import/export and the API:
- `notes: TEXT` — on `cf_documents`, `cf_items`, `cf_associations` (CFAssociation's `notes` is new in v1.1). Also carried by the OpenSALT CSV/xlsx formats (CFItem / CFDocument).
- `alternative_label: TEXT` (`alternativeLabel`) — `cf_items` only.
- `extensions: JSONB` — on **all** entity tables (v1.1 "added to all classes"). Free-form extension object (array on CFRubricCriterionLevel). Carried in CASE JSON only (no column in the CSV/xlsx formats).

---

# DBスキーマ設計（日本語）

## 設計方針

**FK削除ポリシー:**
所有関係の FK は `ON DELETE CASCADE`、参照関係の nullable FK は `ON DELETE SET NULL` を使い分ける。

CASCADE（所有関係）:
- `tenant_id` → tenant削除で cf_document, cf_item, cf_association, cf_rubric, lookup系テーブル全て自動削除
- `cf_document_id` → cf_document削除で配下のcf_item, cf_association, cf_rubric自動削除。ただし lookup 系テーブル（cf_item_type, cf_subject, cf_concept, cf_license, cf_association_grouping）はテナント所有のため削除されない。ドキュメント削除後、他ドキュメントから参照されていない lookup レコードは orphan としてテナント内に残る（CASE API 一覧で返却される。自動クリーンアップは行わない）。**クロスドキュメント参照への影響**: 他ドキュメントの CFAssociation が削除されたドキュメントのアイテムを `origin_node_identifier` / `destination_node_identifier` で参照している場合、参照先が存在しなくなる（dangling reference）。`origin_node_identifier` / `destination_node_identifier` は VARCHAR 型であり FK 制約がないため、CASCADE や SET NULL は発生しない。dangling reference の association はそのまま残り、API レスポンスでも返却される（参照先の `/uri/{uuid}` は 404 となる）
- `cf_rubric_id` → cf_rubric削除で配下のcf_rubric_criterion自動削除
- `cf_rubric_criterion_id` → cf_rubric_criterion削除で配下のcf_rubric_criterion_level自動削除

SET NULL（参照関係）:
- `cf_document.cf_license_id` → CFLicense削除時、ドキュメントのlicense参照をNULLにする（ドキュメント自体は残す）
- `cf_item.cf_item_type_id` → CFItemType削除時、アイテムのtype参照をNULLにする（アイテム自体は残す）
- `cf_item.cf_license_id` → CFLicense削除時、アイテムのlicense参照をNULLにする（アイテム自体は残す）
- `cf_item.cf_concept_id` → CFConcept削除時、アイテムのconcept参照をNULLにする（アイテム自体は残す）
- `cf_association.cf_association_grouping_id` → CFAssociationGrouping削除時、関連のgrouping参照をNULLにする（関連自体は残す）

**`id` と `identifier` を分離する理由:**
`identifier` は CASE 仕様上のリソース識別子（外部からのインポート時に既存UUIDを保持する）。
`id` は内部PK（外部キーの参照先に使用）。外部インポートで `identifier` が変更されても
内部のFK関係が壊れないための防御設計。

**`identifier` のUNIQUEスコープ:**
`identifier` は `UNIQUE(tenant_id, identifier)` の複合ユニーク制約とする（テナントスコープ）。
CASE仕様上UUIDはグローバルに一意だが、マルチテナント環境では複数テナントが同じ外部フレームワーク
（学習指導要領等）をインポートするユースケースがあるため、テナント単位のユニークに緩和する。
`/uri/{uuid}` 検索はテナントスコープで行うため、動作上の影響はない。

**TIMESTAMP型:**
全 `TIMESTAMP` カラムは `TIMESTAMPTZ`（`TIMESTAMP WITH TIME ZONE`）を使用する。
PostgreSQL は TIMESTAMPTZ を内部的に UTC で保存する。APIレスポンスでは ISO 8601 UTC（末尾 `Z`）で出力する。

## テーブル定義

### tenant
```
id: UUID PK  ← 公開URL /{tenant-uuid}/ に使われるUUID
name: VARCHAR NOT NULL
is_private: BOOLEAN NOT NULL DEFAULT false
created_at: TIMESTAMP NOT NULL DEFAULT now()
```

### cf_document
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_license_id: UUID FK(cf_license.id) NULLABLE
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR NOT NULL
creator: VARCHAR                 -- CASE v1.1 では required だが、CSV インポートで未指定のケースに対応するため nullable。Phase 2 で空文字列デフォルト化を検討
publisher: VARCHAR
description: TEXT
framework_type: VARCHAR      -- v1.1 new. 標準値は "CourseCodes"（OpenAPI 上は自由文字列）
case_version: VARCHAR        -- v1.1 new. OpenAPI では enum: ["1.1"]。値は "1.1" のみ有効
language: VARCHAR(10)
version: VARCHAR
adoption_status: VARCHAR
status_start_date: DATE
status_end_date: DATE
official_source_url: VARCHAR
subject: JSONB           -- 文字列配列 ["数学", "理科"]
subject_uri: JSONB       -- LinkURIオブジェクト配列 [{"title":"数学","identifier":"uuid","uri":"https://..."}]
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
```

**注意**: `UNIQUE(tenant_id, identifier)` が B-tree 複合インデックスを自動作成するため、`INDEX(tenant_id)` 単独インデックスは不要（UNIQUE の先頭カラムでカバーされる）。`INDEX(identifier)` 単独インデックスも不要（全クエリがテナントスコープで `UNIQUE(tenant_id, identifier)` を使用する）。以下のテーブル定義でも同様。

### cf_item
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
cf_item_type_id: UUID FK(cf_item_type.id) NULLABLE
cf_license_id: UUID FK(cf_license.id) NULLABLE
cf_concept_id: UUID FK(cf_concept.id) NULLABLE
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
full_statement: TEXT NOT NULL
human_coding_scheme: VARCHAR
list_enumeration: VARCHAR
abbreviated_statement: TEXT
concept_keywords: JSONB    -- 文字列配列 ["分析", "評価"]
education_level: JSONB     -- 文字列配列 ["09", "10", "11", "12"]
subject: JSONB             -- 文字列配列 ["数学"]. v1.1 new. CFDocument と同じ形式
subject_uri: JSONB         -- LinkURIオブジェクト配列. v1.1 new. CFDocument と同じ形式
language: VARCHAR(10)
status_start_date: DATE
status_end_date: DATE
depth: INTEGER NOT NULL DEFAULT 0  -- ツリーの深さ (0=ルート直下)。インポート時にisChildOfを再帰的にたどって計算
                                   -- 孤立ノード(isChildOfの参照先が未解決)は depth=0 とする
                                   -- 循環参照を検出した場合は depth=0 とし、エラーレポートに追記（アイテム自体は保存される）
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
INDEX(tenant_id, cf_document_id, human_coding_scheme)  -- upsertマッチング用
INDEX(cf_document_id, depth)  -- ツリービューLevel判定用（INDEX(cf_document_id) 単独の用途もカバー）
```

### cf_association
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
association_type: VARCHAR NOT NULL  -- CASE v1.1列挙値: isChildOf, isPeerOf, isPartOf, exactMatchOf, precedes, isRelatedTo, replacedBy, exemplar, hasSkillLevel, isTranslationOf
origin_node_uri: VARCHAR NOT NULL
origin_node_identifier: VARCHAR NOT NULL  -- LinkGenURIDType: UUID制限なし（外部参照で非UUIDの場合あり）
origin_node_title: VARCHAR               -- LinkGenURIDType.title。JOINで解決できない外部参照用に保持
origin_node_target_type: VARCHAR         -- LinkGenURIDType.targetType。v1.1 new。"CASE" or "ext:*"
destination_node_uri: VARCHAR NOT NULL
destination_node_identifier: VARCHAR NOT NULL  -- LinkGenURIDType: UUID制限なし（外部参照で非UUIDの場合あり）
destination_node_title: VARCHAR               -- LinkGenURIDType.title。JOINで解決できない外部参照用に保持
destination_node_target_type: VARCHAR         -- LinkGenURIDType.targetType。v1.1 new。"CASE" or "ext:*"
sequence_number: INTEGER
cf_association_grouping_id: UUID FK(cf_association_grouping.id) NULLABLE
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
INDEX(origin_node_identifier), INDEX(destination_node_identifier)
INDEX(cf_document_id, destination_node_identifier)  -- ツリー子アイテム取得用（children クエリ最適化。INDEX(cf_document_id) 単独の用途もカバー）
```

### uuid横断検索用（/uri/{uuid}）
`identifier` は全テーブルで `UNIQUE(tenant_id, identifier)` の複合ユニーク制約を持つ。
`/{tenant}/uri/{uuid}` ルーターはテナントスコープ内で検索する。
検索順序: cf_document → cf_item → cf_association → cf_item_type → cf_subject → cf_concept → cf_license → cf_association_grouping（最初にヒットした時点で検索を打ち切る）

### lookup系テーブル共通カラム

全 lookup テーブルは以下の共通カラムを持つ:
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR NOT NULL
description: TEXT
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
INDEX(tenant_id, title)  -- CSVインポートの find or create パターン用
```

### cf_item_type（追加カラム）
```
type_code: VARCHAR         -- CASE v1.1 typeCode（例: "knowledge-and-skills"）
hierarchy_code: VARCHAR    -- CASE v1.1 hierarchyCode（例: "1"）
```

### cf_subject（追加カラム）
```
hierarchy_code: VARCHAR    -- CASE v1.1 hierarchyCode
```

### cf_concept（追加カラム）
```
keywords: VARCHAR          -- CASE v1.1 keywords（パイプ区切り文字列。例: "analysis|evaluation"）
hierarchy_code: VARCHAR    -- CASE v1.1 hierarchyCode
```

### cf_license（追加カラム）
```
license_text: TEXT         -- ライセンス本文
```

### cf_association_grouping
共通カラムのみ（追加カラムなし）。

### lookup テーブルの運用ルール

CSVインポート時に**同一テナント内で** `title` の完全一致で検索し、一致するレコードがなければ自動生成する（find or create。大文字小文字を区別する）。既存レコードに一致した場合はそのまま再利用し、フィールドの更新は行わない。
テナント横断の共有はしない。一致するものがなければ新規UUID採番して作成する。
CFSubject は CFDocument の `subject_uri` JSONB 配列から URI で参照される。CFConcept は CFItem の `cf_concept_id` FK で参照される（CSV インポートでは cf_concept は生成されない。外部 CASE ソースインポートでのみ作成される）。
固有カラム（typeCode等）はCSVインポートでは設定されない。外部CASEソースインポート時にのみ値が入る。

### cf_rubric（Phase 2、DBスキーマは Phase 1 で作成）
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
identifier: UUID NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR
description: TEXT
last_change_date_time: TIMESTAMP NOT NULL
UNIQUE(tenant_id, identifier)
INDEX(cf_document_id)  -- CFPackage レスポンスでドキュメント配下の CFRubric 取得用
```

### cf_rubric_criterion
```
id: UUID PK
cf_rubric_id: UUID FK(cf_rubric.id) NOT NULL
identifier: UUID UNIQUE NOT NULL       -- tenant_idを持たないため単独UNIQUE。Phase 2で詳細設計
                                       -- **設計リスク**: グローバルUNIQUEのため、複数テナントが同じ外部ソース（同一UUID）を
                                       -- インポートするとUNIQUE制約違反が発生する。Phase 2 で tenant_id 追加を検討する
uri: VARCHAR NOT NULL
cf_item_id: UUID FK(cf_item.id) NULLABLE  -- CASE v1.1 CFItemURI。関連する CFItem への FK 参照
rubric_id: UUID                          -- CASE v1.1 rubricId。親 CFRubric の identifier（cf_rubric.identifier を JOIN で解決しても可）
category: VARCHAR
description: TEXT
weight: FLOAT
position: INTEGER
rubric_criterion_text_plain: TEXT   -- 独自カラム（CASE v1.1 に対応するフィールドなし）。cf_item.fullStatement に相当する表示用テキスト
last_change_date_time: TIMESTAMP NOT NULL
INDEX(cf_rubric_id), INDEX(identifier)
```

### cf_rubric_criterion_level
```
id: UUID PK
cf_rubric_criterion_id: UUID FK(cf_rubric_criterion.id) NOT NULL
rubric_criterion_id: UUID                -- CASE v1.1 rubricCriterionId。親 CFRubricCriterion の identifier
identifier: UUID UNIQUE NOT NULL       -- tenant_idを持たないため単独UNIQUE。Phase 2で詳細設計（cf_rubric_criterion と同一リスク）
uri: VARCHAR NOT NULL
description: TEXT
quality: VARCHAR
score: FLOAT
feedback: TEXT                           -- CASE v1.1 feedback（任意）
position: INTEGER
last_change_date_time: TIMESTAMP NOT NULL
INDEX(cf_rubric_criterion_id), INDEX(identifier)
```

### CASE v1.1 標準フィールド（notes / alternativeLabel / extensions）
以下の CASE v1.1 フィールドは保存され、CASE JSON の import/export・API で往復する:
- `notes: TEXT` — `cf_documents` / `cf_items` / `cf_associations`（CFAssociation の notes は v1.1 新規）。OpenSALT の CSV/xlsx 形式でも CFItem / CFDocument が保持する
- `alternative_label: TEXT`（`alternativeLabel`） — `cf_items` のみ
- `extensions: JSONB` — **全**エンティティテーブル（v1.1 で全クラスに追加）。自由形式の拡張オブジェクト（CFRubricCriterionLevel のみ配列）。CASE JSON でのみ往復（CSV/xlsx には列が無い）
