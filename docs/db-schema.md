# DBスキーマ設計

## 設計方針

**FK削除ポリシー:**
所有関係の FK は `ON DELETE CASCADE`、参照関係の nullable FK は `ON DELETE SET NULL` を使い分ける。

CASCADE（所有関係）:
- `tenant_id` → tenant削除で cf_document, cf_item, cf_association, lookup系テーブル全て自動削除
- `cf_document_id` → cf_document削除で配下のcf_item, cf_association自動削除
- `cf_rubric_id` → cf_rubric削除で配下のcf_rubric_criterion自動削除
- `cf_rubric_criterion_id` → cf_rubric_criterion削除で配下のcf_rubric_criterion_level自動削除

SET NULL（参照関係）:
- `cf_item.cf_item_type_id` → CFItemType削除時、アイテムのtype参照をNULLにする（アイテム自体は残す）
- `cf_association.cf_association_grouping_id` → CFAssociationGrouping削除時、関連のgrouping参照をNULLにする（関連自体は残す）

**`id` と `identifier` を分離する理由:**
`identifier` は CASE 仕様上のリソース識別子（外部からのインポート時に既存UUIDを保持する）。
`id` は内部PK（外部キーの参照先に使用）。外部インポートで `identifier` が変更されても
内部のFK関係が壊れないための防御設計。

## テーブル定義

### tenant
```
id: UUID PK  ← 公開URL /{tenant-uuid}/ に使われるUUID
name: VARCHAR
is_private: BOOLEAN DEFAULT false
created_at: TIMESTAMP
```

### cf_document
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
identifier: UUID UNIQUE NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR NOT NULL
creator: VARCHAR
publisher: VARCHAR
description: TEXT
language: VARCHAR(10)
version: VARCHAR
adoption_status: VARCHAR
status_start_date: DATE
status_end_date: DATE
license_uri: VARCHAR
official_source_url: VARCHAR
subject: JSONB           -- 文字列配列 ["数学", "理科"]
subject_uri: JSONB       -- URI配列 (CFSubjectへの参照)
last_change_date_time: TIMESTAMP NOT NULL
INDEX(tenant_id), INDEX(identifier)
```

### cf_item
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
cf_item_type_id: UUID FK(cf_item_type.id) NULLABLE
identifier: UUID UNIQUE NOT NULL
uri: VARCHAR NOT NULL
full_statement: TEXT NOT NULL
human_coding_scheme: VARCHAR
list_enumeration: VARCHAR
abbreviated_statement: TEXT
concept_keywords: JSONB    -- 文字列配列 ["分析", "評価"]
concept_keywords_uri: JSONB -- URI配列 (CFConceptへの参照)
education_level: JSONB     -- 文字列配列 ["09", "10", "11", "12"]
language: VARCHAR(10)
adoption_status: VARCHAR
status_start_date: DATE
status_end_date: DATE
depth: INTEGER NOT NULL DEFAULT 0  -- ツリーの深さ (0=ルート直下)。インポート時にisChildOfを再帰的にたどって計算
                                   -- 孤立ノード(isChildOfの参照先が未解決)は depth=0 とする
                                   -- 循環参照を検出した場合はインポートエラー（該当行をスキップしてレポート）
last_change_date_time: TIMESTAMP NOT NULL
INDEX(tenant_id), INDEX(cf_document_id), INDEX(identifier)
INDEX(tenant_id, cf_document_id, human_coding_scheme)  -- upsertマッチング用
INDEX(cf_document_id, depth)  -- ツリービューLevel判定用
```

### cf_association
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
identifier: UUID UNIQUE NOT NULL
uri: VARCHAR NOT NULL
association_type: VARCHAR NOT NULL
origin_node_uri: VARCHAR NOT NULL
origin_node_identifier: UUID NOT NULL
destination_node_uri: VARCHAR NOT NULL
destination_node_identifier: UUID NOT NULL
sequence_number: INTEGER
cf_association_grouping_id: UUID FK(cf_association_grouping.id) NULLABLE
last_change_date_time: TIMESTAMP NOT NULL
INDEX(tenant_id), INDEX(identifier), INDEX(origin_node_identifier), INDEX(destination_node_identifier)
```

### uuid横断検索用（/uri/{uuid}）
`identifier` は全テーブルでUNIQUEインデックスを持つ。
検索順序: cf_document → cf_item → cf_association → その他

### lookup系テーブル共通カラム

全 lookup テーブルは以下の共通カラムを持つ:
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
identifier: UUID UNIQUE NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR NOT NULL
description: TEXT
last_change_date_time: TIMESTAMP NOT NULL
INDEX(tenant_id), INDEX(identifier)
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
hierarchy_code: VARCHAR    -- CASE v1.1 hierarchyCode
```

### cf_license（追加カラム）
```
license_text: TEXT         -- ライセンス本文
```

### cf_association_grouping
共通カラムのみ（追加カラムなし）。

### lookup テーブルの運用ルール

CSVインポート時に**同一テナント内で** `title` の完全一致でupsertして自動生成する（大文字小文字を区別する）。
テナント横断の共有はしない。一致するものがなければ新規UUID採番して作成する。
CFSubject/CFConceptはCFDocument/CFItemの `*_uri` JSONB配列からURIで参照される。
固有カラム（typeCode等）はCSVインポートでは設定されない。外部CASEソースインポート時にのみ値が入る。

### cf_rubric（Phase 2、DBスキーマは Phase 1 で作成）
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
identifier: UUID UNIQUE NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR
description: TEXT
last_change_date_time: TIMESTAMP NOT NULL
INDEX(tenant_id), INDEX(identifier)
```

### cf_rubric_criterion
```
id: UUID PK
cf_rubric_id: UUID FK(cf_rubric.id) NOT NULL
identifier: UUID UNIQUE NOT NULL
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
identifier: UUID UNIQUE NOT NULL
uri: VARCHAR NOT NULL
description: TEXT
quality: VARCHAR
score: FLOAT
position: INTEGER
last_change_date_time: TIMESTAMP NOT NULL
INDEX(cf_rubric_criterion_id), INDEX(identifier)
```

### `notes` フィールドについて
CASE v1.1 仕様の CFDocument / CFItem には `notes` フィールドが存在するが、
実運用での使用頻度が低いため Phase 1 では省略する。
Phase 2 以降で必要に応じて `notes: TEXT` カラムを追加する。
