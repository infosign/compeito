# DBスキーマ設計

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
creator: VARCHAR
publisher: VARCHAR
description: TEXT
framework_type: VARCHAR      -- v1.1 new. 例: "CourseCodes"
case_version: VARCHAR        -- v1.1 new. 値は "1.1" のみ
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
category: VARCHAR
description: TEXT
weight: FLOAT
position: INTEGER
rubric_criterion_text_plain: TEXT   -- cf_item.fullStatement に相当
last_change_date_time: TIMESTAMP NOT NULL
INDEX(cf_rubric_id), INDEX(identifier)
```

### cf_rubric_criterion_level
```
id: UUID PK
cf_rubric_criterion_id: UUID FK(cf_rubric_criterion.id) NOT NULL
identifier: UUID UNIQUE NOT NULL       -- tenant_idを持たないため単独UNIQUE。Phase 2で詳細設計（cf_rubric_criterion と同一リスク）
uri: VARCHAR NOT NULL
description: TEXT
quality: VARCHAR
score: FLOAT
position: INTEGER
last_change_date_time: TIMESTAMP NOT NULL
INDEX(cf_rubric_criterion_id), INDEX(identifier)
```

### Phase 1 で省略する CASE v1.1 フィールド
以下のフィールドは CASE v1.1 仕様に存在するが、実運用での使用頻度が低いため Phase 1 では省略する。
Phase 2 以降で必要に応じてカラムを追加する。
- `notes: TEXT` — CFDocument / CFItem 共通。自由記述メモ
- `alternativeLabel: VARCHAR` — CFItem のみ。代替ラベル
