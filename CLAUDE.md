# CASE Server — Claude Code Instructions

## プロジェクト概要

1EdTech CASE v1.1 準拠のWebサービス。コンピテンシーフレームワークをAPIで配信する。
Open Badge Factory (OB v3) と TAO Testing (QTI v3.0) の参照先として機能する。
インフォザインが開発・運用。Apache License 2.0 でOSS公開。

## アーキテクチャ

```
Public:  CloudFront → API Gateway → Lambda (FastAPI + Mangum) → Aurora Serverless v2 (PostgreSQL)
Admin:   CLI → Lambda Function URL (HTTPS + Bearer token) → Lambda → Aurora
```

- **Lambda**: 単一の Lambda 関数。タイムアウト 300s。アクセス経路が2つ（API Gateway / Function URL）
- **Public API**: API Gateway 経由。API Gateway の統合タイムアウト (29s) で自然に制限される
- **Admin API**: Lambda Function URL 経由。API Gateway を通さないため 300s の長時間処理が可能

- **マルチテナント**: `/{tenant-uuid}/ims/case/v1p1/` でテナント分離（v1p0も後方互換で維持）
- **公開制御**: public/private フラグ。privateはトップ一覧に非表示、URL直接アクセスは可能
- **キャッシュ**: CloudFront が主キャッシュ。CLIインポート時にinvalidate
- **データ更新**: CLI経由のみ（Web UIなし）。CSV または外部CASEソースからインポート

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| API | Python 3.12 + FastAPI + Mangum |
| ORM | SQLAlchemy 2.x (async) |
| マイグレーション | Alembic |
| DB | PostgreSQL (Aurora Serverless v2 / ローカルはDocker) |
| キャッシュ | CloudFront (HTTP Cache-Control headers) |
| インフラ | AWS CDK (Python) |
| ローカル開発 | Docker + docker-compose |
| テスト | pytest + pytest-asyncio |
| パッケージ管理 | uv |
| CLI表示 | rich (テーブル・プログレスバー・カラー出力) |
| Web UI | Jinja2 + HTMX + Tailwind CSS (CDN) |

## ディレクトリ構成

```
case-server/
├── src/
│   ├── main.py                  # FastAPI app エントリーポイント + Mangum handler
│   ├── config.py                # 設定 (Pydantic Settings)
│   ├── database.py              # DB接続 (async SQLAlchemy)
│   ├── models/                  # SQLAlchemy ORM モデル
│   │   ├── tenant.py
│   │   ├── cf_document.py
│   │   ├── cf_item.py
│   │   ├── cf_association.py
│   │   ├── cf_association_grouping.py
│   │   ├── cf_item_type.py
│   │   ├── cf_concept.py
│   │   ├── cf_subject.py
│   │   ├── cf_license.py
│   │   ├── cf_rubric.py              # Phase 2 (APIは後回し、DBは初期から)
│   │   ├── cf_rubric_criterion.py
│   │   └── cf_rubric_criterion_level.py
│   ├── schemas/                 # Pydantic スキーマ (CASE v1.1 準拠)
│   │   ├── common.py            # LinkURIType, imsx_StatusInfo 等の共通型
│   │   ├── cf_document.py
│   │   ├── cf_item.py
│   │   ├── cf_association.py
│   │   ├── cf_association_grouping.py
│   │   ├── cf_item_type.py
│   │   ├── cf_concept.py
│   │   ├── cf_subject.py
│   │   ├── cf_license.py
│   │   ├── cf_package.py
│   │   └── cf_rubric.py              # Phase 2
│   ├── routers/                 # FastAPI ルーター
│   │   ├── admin.py             # POST /admin/* (管理API、Bearer token認証)
│   │   ├── index.py             # GET / テナント一覧
│   │   ├── cf_documents.py
│   │   ├── cf_items.py
│   │   ├── cf_associations.py
│   │   ├── cf_association_groupings.py
│   │   ├── cf_item_types.py
│   │   ├── cf_concepts.py
│   │   ├── cf_subjects.py
│   │   ├── cf_licenses.py
│   │   ├── cf_packages.py
│   │   └── cf_rubrics.py             # Phase 2
│   ├── templates/               # Jinja2 HTMLテンプレート
│   │   ├── base.html            # 共通レイアウト
│   │   ├── index.html           # テナント一覧
│   │   ├── tenant.html          # フレームワーク一覧
│   │   ├── cftree.html          # ツリービュー
│   │   └── uri.html             # アイテム詳細
│   ├── services/                # ビジネスロジック (router → service → repository)
│   │   ├── tenant_service.py
│   │   ├── cf_view_service.py       # ツリービュー・アイテム詳細・CFPackage構築
│   │   ├── csv_import_service.py
│   │   ├── csv_export_service.py
│   │   └── case_import_service.py
│   └── repositories/            # DBアクセス層
│       ├── tenant_repository.py
│       ├── cf_document_repository.py
│       ├── cf_item_repository.py
│       ├── cf_association_repository.py
│       ├── cf_association_grouping_repository.py
│       ├── cf_item_type_repository.py
│       ├── cf_concept_repository.py
│       ├── cf_subject_repository.py
│       └── cf_license_repository.py
├── cli.py                       # CLI エントリーポイント
├── migrations/                  # Alembic マイグレーション
├── tests/
│   ├── unit/
│   └── integration/
├── infra/
│   └── cdk/                     # AWS CDK (Python)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .claude/
    ├── agents/                  # Claude Code サブエージェント定義
    └── skills/                  # Claude Code スキル定義
```

## URLパス設計

### Web UI (HTML)
| Path | 説明 |
|------|------|
| GET / | 公開テナント一覧: テナント名の一覧（privateは非表示） |
| GET /{tenant-uuid}/ | フレームワーク一覧: CFDocumentのtitle, lastChangeDateTime, アイテム数 |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid} | ツリービュー (Level 1-2をSSR、Level 3+はHTMX遅延ロード) |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/children/{item-uuid} | 子アイテムHTMLフラグメント (HTMX用) |
| GET /{tenant-uuid}/uri/{uuid} | リソース詳細ページ (HTML固定、下記参照) |

**ツリービュー (`/cftree/doc/{doc-uuid}`) のレイアウト:**
OpenSALT のツリービューを参考にした 2 ペイン構成。見た目は Tailwind CSS のデフォルトスタイルでモダンに仕上げる（OpenSALT の見た目をコピーしない）。

```
┌─────────────────────────────────────────────────────┐
│ ヘッダー: CFDocument title + adoptionStatus バッジ    │
├──────────────────────┬──────────────────────────────┤
│ 左ペイン（ツリー）     │ 右ペイン（詳細）              │
│                      │                              │
│ ▼ 国語               │ fullStatement                │
│   ▼ 現代の国語        │ humanCodingScheme            │
│     【知識及び技能】   │ identifier                   │
│     ● 言葉の特徴や... │ CFItemType                   │
│     ● 言葉には...     │ educationLevel               │
│   ▶ 言語文化          │ 「詳細」リンク → /uri/{uuid}  │
│ ▶ 地理歴史            │                              │
│ ▶ 公民                │                              │
└──────────────────────┴──────────────────────────────┘
```

- **左ペイン**: ツリー構造。クリックで展開/折りたたみ（▶/▼）。アイテムクリックで右ペインに詳細表示
- **右ペイン**: 選択アイテムの主要フィールドを表示。`/uri/{uuid}` への「詳細」リンク
- **レスポンシブ**: モバイルではツリーのみ表示、アイテムタップで詳細ページ (`/uri/`) に遷移

**`/uri/{uuid}` 詳細ページの表示内容:**
Open Badge Factory 等の外部システムからリンクされる公開ページ。
OpenSALT の `/uri/{uuid}` ページ（例: opensalt.net/uri/0ce49f58-... ）を参考にしつつ、
デザインは Tailwind CSS のデフォルトスタイルでモダンに仕上げる。
値がないフィールドは非表示（行ごと省略）。

CFItem の場合:
| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID |
| uri | 必須 | URL（リンク） |
| CFDocumentURI | 必須 | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| fullStatement | 必須 | テキスト |
| lastChangeDateTime | 必須 | ISO 8601 |
| humanCodingScheme | 任意 | テキスト |
| abbreviatedStatement | 任意 | テキスト |
| CFItemType | 任意 | CFItemTypeURI のネスト表示（title, identifier, uri） |
| educationLevel | 任意 | 配列をカンマ区切りで表示 |
| conceptKeywords | 任意 | 配列をカンマ区切りで表示 |
| language | 任意 | 言語コード |
| listEnumeration | 任意 | テキスト |
| 「ツリーで表示」リンク | - | ツリービューの該当アイテム位置へ遷移 |

CFDocument の場合:
| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID |
| uri | 必須 | URL（リンク） |
| title | 必須 | テキスト |
| lastChangeDateTime | 必須 | ISO 8601 |
| creator | 任意 | テキスト |
| publisher | 任意 | テキスト |
| description | 任意 | テキスト |
| language | 任意 | 言語コード |
| version | 任意 | テキスト |
| adoptionStatus | 任意 | バッジ表示（Draft / Adopted / Deprecated） |
| officialSourceURL | 任意 | URL（リンク） |
| subject | 任意 | 配列をカンマ区切りで表示 |
| CFPackageURI | 任意 | ネスト表示（title, identifier, uri） |
| 「ツリーで表示」リンク | - | ツリービュートップへ遷移 |

childrenパスに `{doc-uuid}` を含めることで、CloudFrontのワイルドカード
`/{tenant}/cftree/doc/{doc-uuid}*` で一括invalidation可能。

**ツリーのLevel判定**: `cf_item.depth` カラムに格納（インポート時に `isChildOf` を
再帰的にたどって計算）。Level 1-2 = depth 0-1 をSSRで返し、depth 2+ はHTMX遅延ロード。

**子アイテム取得** (`/children/{item-uuid}`): `isChildOf` association で
`origin_node_identifier = item-uuid` のアイテムを取得し、`sequence_number` 昇順でソートする。

CASEリソースの `uri` フィールドは `/uri/{uuid}` を指す (OpenSALTと同じパターン):
`https://example.com/{tenant-uuid}/uri/{resource-uuid}`

**URI生成ルール:**
- `config.py` に `BASE_URL` 設定を持つ（例: `https://case.example.com`）
- Docker環境のデフォルト: `http://localhost:8000`
- 環境変数 `BASE_URL` で上書き可能
- 新規作成時: `uri = f"{BASE_URL}/{tenant_id}/uri/{identifier}"`
- **外部インポート時**: 元の `uri` をそのまま DB に保持する（上書きしない）。
  外部URIのリソースを自サーバーの `/uri/{uuid}` でもアクセス可能にするため、
  `identifier` での検索を `/uri/{uuid}` ルーターが行う（DB の `uri` カラムとは別）

**コンテントネゴシエーションは使わない。** CloudFrontがAcceptヘッダーを無視して
キャッシュするため、HTML/JSONが混在するリスクがある。
- Web UI: `/{tenant}/uri/{uuid}` → 常にHTML
- CASE API: `/{tenant}/ims/case/v1p1/CFItems/{uuid}` → 常にJSON

**テナントバリデーション（全エンドポイント共通）:**
- `{tenant-uuid}` が UUID 形式でない → **400** (`imsx_codeMinorFieldValue: invalid_uuid`)
- UUID 形式だがテナントが存在しない → **404** (`imsx_codeMinorFieldValue: unknownobject`)
- `/uri/{uuid}` はテナントスコープ内で検索する。別テナントの UUID を指定した場合は **404**

### CASE v1.1 API (JSON)

APIパス: `/ims/case/v1p1/` (conformance必須) + `/ims/case/v1p0/` (後方互換)

| Path | レスポンスルートキー | 説明 | 必須 |
|------|---------------------|------|------|
| GET /{tenant}/ims/case/v1p1/CFPackages/{id} | `{"CFPackage": {...}}` | パッケージ取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFDocuments | `{"CFDocuments": [...]}` | 文書一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFDocuments/{id} | `{"CFDocument": {...}}` | 文書取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItems/{id} | `{"CFItem": {...}}` | 項目取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItems/{id}/associations | `{"CFAssociations": [...]}` | 項目の関連一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociations/{id} | `{"CFAssociation": {...}}` | 関連取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings | `{"CFAssociationGroupings": [...]}` | 関連グループ一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id} | `{"CFAssociationGrouping": {...}}` | 関連グループ取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFConcepts | `{"CFConcepts": [...]}` | コンセプト一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFConcepts/{id} | `{"CFConcept": {...}}` | コンセプト取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItemTypes | `{"CFItemTypes": [...]}` | 項目種別一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItemTypes/{id} | `{"CFItemType": {...}}` | 項目種別取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFLicenses | `{"CFLicenses": [...]}` | ライセンス一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFLicenses/{id} | `{"CFLicense": {...}}` | ライセンス取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFSubjects | `{"CFSubjects": [...]}` | 教科一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFSubjects/{id} | `{"CFSubject": {...}}` | 教科取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFRubrics/{id} | `{"CFRubric": {...}}` | ルーブリック取得 | Phase 2 |

**CFPackage レスポンス構造:**
```json
{
  "CFPackage": {
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
}
```
- `CFDefinitions` 内の各キーはデータがなければ省略する
- `CFRubrics` は Phase 2。データがなければキー自体を省略する

レスポンスにカスタムラッパー (`{"data": ...}` 等) を**追加してはならない**。
エラー時は `{"imsx_codeMajor": "failure", ...}` をルートレベルに直接返す（コーディング規約のエラー項参照）。

## 管理用APIエンドポイント (/admin/*)

AWS環境でCLIが叩く内部エンドポイント。Lambda Function URL 経由でアクセスする。
アプリ層（FastAPIミドルウェア）で `Authorization: Bearer <shared-secret>` を検証。
Docker環境では認証なし（ローカル開発用）。
エラーレスポンスは標準JSON形式（`{"error": "...", "detail": "..."}`）。CASE API の imsx_StatusInfo 形式は使わない。

| Path | リクエスト | レスポンス | 説明 |
|------|-----------|-----------|------|
| POST /admin/tenants | JSON body (name, is_private?) | JSON (tenant) | テナント作成 |
| GET  /admin/tenants | query: with_docs=bool | JSON (tenant[]) | テナント一覧（private含む全件） |
| DELETE /admin/tenants/{id} | - | JSON | テナント削除（CASCADE: 下記参照） |
| GET  /admin/tenants/{id}/documents | - | JSON (document[]) | フレームワーク一覧 |
| DELETE /admin/tenants/{id}/documents/{doc-uuid} | - | JSON | フレームワーク削除 |
| POST /admin/tenants/{id}/import/csv | JSON body (s3_key, doc_title, doc_uuid?) | JSON (job結果) | CSVインポート |
| POST /admin/tenants/{id}/import/case-url | JSON body (url, doc_uuid?) | JSON (job結果) | 外部CASEインポート |
| POST /admin/tenants/{id}/documents/{doc-uuid}/export/csv | JSON body (format?) | JSON (s3_presigned_url) | CSVエクスポート |
| POST /admin/cache/invalidate | JSON body (tenant_id, doc_id?) | JSON | CloudFront invalidation |
| POST /admin/migrate | - | JSON | Alembicマイグレーション実行 |
| GET  /admin/upload-url | query: tenant_id, filename | JSON (s3_key, presigned_url) | CSVアップロード用presigned URL取得 |

`src/routers/admin.py` に実装する。

### 大規模ファイルのS3経由転送

Lambda API Gatewayの6MBリクエスト/レスポンス制限を回避するため、
CSVのインポート/エクスポートはS3経由で行う。

**インポートフロー:**
```
1. CLI: GET /admin/upload-url → S3 presigned upload URL取得
2. CLI: CSVファイルをS3に直接PUT（CLIがAWS署名なしでアップロード可能）
3. CLI: POST /admin/import/csv { s3_key: "..." } → LambdaがS3からCSVを読み込んでDB投入
```

**エクスポートフロー:**
```
1. CLI: POST /admin/export/csv → LambdaがCSV生成してS3にアップロード
2. Lambda: S3 presigned download URLを返す
3. CLI: presigned URLからCSVをダウンロード
```

S3バケットはCDKでprivateとして作成。presigned URLの有効期限は15分。

## Alembicマイグレーション実行戦略

Alembic は asyncpg（async ドライバ）をそのまま使用する。同期ドライバ（psycopg2）は不要。
`env.py` で `run_async_migrations()` パターンを使い、`connectable = create_async_engine(...)` で接続する。

**ローカル/Docker環境:**
```bash
docker-compose exec app alembic upgrade head
```

**AWS環境:**
CLIから管理APIを叩いてLambda内でマイグレーションを実行する。
```bash
python cli.py db migrate   # POST /admin/migrate → Lambda内でalembic upgrade head
```
Lambda起動時の自動マイグレーションは行わない（並列実行時の競合リスクのため）。

## DBスキーマ設計

### 主要カラム・インデックス

**カスケード削除:**
全FKに `ON DELETE CASCADE` を設定する（DB側で自動削除）。アプリ層での明示的な削除は不要。
- tenant削除 → cf_document, cf_item, cf_association, lookup系テーブル全て自動削除
- cf_document削除 → 配下のcf_item, cf_association自動削除

**`id` と `identifier` を分離する理由:**
`identifier` は CASE 仕様上のリソース識別子（外部からのインポート時に既存UUIDを保持する）。
`id` は内部PK（外部キーの参照先に使用）。外部インポートで `identifier` が変更されても
内部のFK関係が壊れないための防御設計。

**tenant**
```
id: UUID PK  ← 公開URL /{tenant-uuid}/ に使われるUUID
name: VARCHAR
is_private: BOOLEAN DEFAULT false
created_at: TIMESTAMP
```

**cf_document**
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

**cf_item**
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

**cf_association**
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
cf_document_id: UUID FK(cf_document.id) NOT NULL
identifier: UUID UNIQUE NOT NULL
association_type: VARCHAR NOT NULL
origin_node_uri: VARCHAR NOT NULL
origin_node_identifier: UUID NOT NULL
destination_node_uri: VARCHAR NOT NULL
destination_node_identifier: UUID NOT NULL
sequence_number: INTEGER
cf_association_grouping_id: UUID FK(cf_association_grouping.id) NULLABLE
last_change_date_time: TIMESTAMP NOT NULL
INDEX(tenant_id), INDEX(origin_node_identifier), INDEX(destination_node_identifier)
```

**uuid横断検索用（/uri/{uuid}）**
`identifier` は全テーブルでUNIQUEインデックスを持つ。
検索順序: cf_document → cf_item → cf_association → その他

### lookup系テーブル（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）
```
id: UUID PK
tenant_id: UUID FK(tenant.id) NOT NULL
identifier: UUID UNIQUE NOT NULL
uri: VARCHAR NOT NULL
title: VARCHAR NOT NULL
description: TEXT          -- CFAssociationGrouping, CFLicense等で使用
last_change_date_time: TIMESTAMP NOT NULL
INDEX(tenant_id), INDEX(identifier)
```
CSVインポート時に**同一テナント内で** `title` の完全一致でupsertして自動生成する（大文字小文字を区別する）。
テナント横断の共有はしない。一致するものがなければ新規UUID採番して作成する。
CFSubject/CFConceptはCFDocument/CFItemの `*_uri` JSONB配列からURIで参照される。

## コーディング規約

- **レイヤー構成**: router → service → repository（DBアクセスはrepositoryに集約）
- **非同期**: 全DB操作は async/await (SQLAlchemy async session)
- **Lambda判定**: `AWS_LAMBDA_FUNCTION_NAME` 環境変数の有無で判定
  ```python
  # config.py
  is_lambda: bool = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
  base_url: str = os.environ.get("BASE_URL", "http://localhost:8000")  # URI生成に使用
  ```
- **接続プール**: Lambda環境では `NullPool` を使用（コネクション枯渇防止）
  ```python
  if settings.is_lambda:
      engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
  else:
      engine = create_async_engine(DATABASE_URL, pool_size=5)
  ```
- **CloudFront Distribution ID**: SSM Parameter Store `/case-server/cloudfront-distribution-id` に保存。Lambda起動時に読み込む。CDKデプロイ時に自動登録。
- **`POST /admin/migrate` の並行実行対策**: このエンドポイントのみLambda予約同時実行数=1に設定（CDKで定義）。
- **スキーマ**: CASEフィールド名はキャメルケース (仕様に準拠)、内部はスネークケース
- **Cache-Control**:
  - 全テナント (public/private共通): `Cache-Control: public, max-age=3600`
    privateテナントの「非公開」はURL自体の秘匿性で実現。CloudFrontキャッシュは有効にする（コスト削減）。
  - HTMXフラグメント (`/cftree/doc/*/children/*`): `Cache-Control: public, max-age=86400`
  - `/admin/*`: Lambda Function URL経由のためCache-Controlは不要
- **v1p0 後方互換**: `/ims/case/v1p0/` パスへのリクエストは `/ims/case/v1p1/` に 301リダイレクト。
  CASE API は GET のみのため 301 で問題ない（POST でメソッドが変わるリスクなし）。
  ルーターを二重に実装しない。`src/main.py` にミドルウェアを1つ追加して一括処理する。
  リダイレクト先はパスの `v1p0` を `v1p1` に置換したもの（クエリパラメータはそのまま引き継ぐ）。
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
- **ページネーション**: CASE v1.1準拠。全一覧エンドポイントに `limit`(デフォルト100, 最大500) / `offset`(デフォルト0) を実装。
  `sort` / `orderBy` / `filter` / `fields` パラメータは Phase 1 では実装しない（無視する）。
  レスポンスに総件数は含めない（CASE v1.1仕様に総件数フィールドはない）。
- **LinkURI型**: `CFPackageURI`, `CFDocumentURI`, `CFOriginNodeURI`, `CFDestinationNodeURI`, `CFItemTypeURI` 等は
  文字列ではなく複合オブジェクト:
  ```json
  {"title": "文書タイトル", "identifier": "uuid", "uri": "https://..."}
  ```
  Pydantic で `LinkURIType` クラスを定義して共有する (`src/schemas/common.py`)。
  DBには `_uri` (VARCHAR) と `_identifier` (UUID) カラムを持ち、`title` はJOINまたはアプリ層で解決する。
- **UUID**: テナント・全CASEリソースのidentifierはUUID v4
- **エラー**: CASE v1.1 の imsx_StatusInfo 形式でエラーレスポンスを返す。
  ルートレベルに直接フィールドを配置する（ラッパーオブジェクトなし）:
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
  - `imsx_codeMinor`: 任意。ネストされたオブジェクト（文字列ではない）
  - `imsx_codeMinorFieldValue`: `fullsuccess` / `invalid_sort_field` / `invalid_selection_field` / `forbidden` / `unauthorised_request` / `internal_server_error` / `unknownobject` / `server_busy` / `invalid_uuid`
  - HTTPステータスコード対応: 400→`failure/error`, 404→`failure/error`+`unknownobject`, 500→`failure/error`+`internal_server_error`

## CLIコマンド

```bash
# テナント管理
python cli.py tenant create --name "Company Name" [--private]
python cli.py tenant list
# UUID                                  NAME        VISIBILITY  CREATED
# 550e8400-...                          大学A        public      2025-01-01
# 6ba7b810-...                          企業B        private     2025-02-15

python cli.py tenant list --with-docs
# 550e8400-...  大学A  public
#   ├─ d86774f2-...  高等学校学習指導要領  (1557 items)
#   └─ a3f9c201-...  工学部コンピテンシー  (42 items)

# フレームワーク(CFDocument)管理
python cli.py doc list --tenant {tenant-uuid}
# UUID                                  TITLE                     ITEMS  UPDATED
# d86774f2-...                          高等学校学習指導要領        1557   2025-10-08

# 削除（確認プロンプトあり、--force でスキップ）
python cli.py tenant delete --tenant {tenant-uuid} [--force]
python cli.py doc delete --tenant {tenant-uuid} --doc {doc-uuid} [--force]

# CSVインポート (新規: --doc省略、更新: --doc指定でupsert)
# --doc-title: CFDocumentタイトル（フォーマット3の#title行があれば省略可、なければ必須）
# --doc-version: バージョン（任意、デフォルト ""）
python cli.py import csv --tenant {uuid} --file framework.csv
python cli.py import csv --tenant {uuid} --file framework.csv --doc-title "名称" --doc-version "1.0"
python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework.csv

# 外部CASEソースインポート (v1.0/v1.1対応、upsert)
python cli.py import case-url --tenant {uuid} --url https://...
python cli.py import case-url --tenant {uuid} --doc {doc-uuid} --url https://...

# エクスポート (UUID付き独自形式 → 編集後にimportでupsert可能)
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv --format opensalt

# DBマイグレーション
python cli.py db migrate
# Docker環境: alembic upgrade head を直接実行
# AWS環境:    POST /admin/migrate を呼び出す

# キャッシュ無効化 (CloudFront、AWS環境のみ有効)
python cli.py cache invalidate --tenant {uuid}
python cli.py cache invalidate --tenant {uuid} --doc {doc-uuid}
# Docker環境で実行した場合: "This command requires AWS environment" と表示して終了
```

## ローカル開発

```bash
docker-compose up -d          # PostgreSQL + アプリ起動
docker-compose exec app alembic upgrade head   # マイグレーション実行
docker-compose exec app pytest                 # テスト実行
```

開発時はアプリもDockerで実行する（Fargate等へのポータビリティ確保）。
ホットリロードは docker-compose.yml の volumes マウント + uvicorn `--reload` で対応。

### テスト環境
- DB: `pytest-asyncio` + `asyncpg` + Docker PostgreSQL（SQLiteは非同期ドライバの差異があるため使わない）
- `conftest.py` でテスト用DBを起動・ロールバック
- CI: GitHub Actions で `docker-compose up -d db` してからテスト実行

### CSVインポートのデフォルト動作
- `--doc-title` 省略かつCSVに `#title` 行なし → エラー終了（必須）
- `--doc-version` 省略 → `""` （任意）
- `Identifier` 空 → UUID v4 を自動採番

## フェーズ定義

### Phase 1（初期リリース）
- Docker環境でのローカル開発・実行
- 全CASEリソースのDBスキーマ（CFRubric含む）
- CASE v1.1 必須APIエンドポイント11種（CFRubric除く）
- v1p0 → v1p1 リダイレクト
- CSVインポート（独自形式 + OpenSALT 2形式の自動判定）
- 外部CASEソースインポート（v1.1のみ）
- CSVエクスポート（独自形式のみ）
- CLIツール（tenant/doc管理, import/export, db migrate）
- Web UI: トップ一覧, テナント一覧, ツリービュー, アイテム詳細
- ページネーション
- pytest による unit/integration テスト
- docker-compose.yml, Dockerfile
- pyproject.toml, README.md

### Phase 2
- CSVエクスポートのOpenSALT互換形式 (`--format opensalt`)
- 外部CASEソースインポートの v1.0 対応（v1.1に正規化）
- CFRubric API エンドポイント + CSVインポート/エクスポート
- AWS CDK インフラ構築
- Admin API エンドポイント（S3転送含む）
- CloudFront invalidation
- 1EdTech Conformance テスト通過

### Phase 3（将来）
- isChildOf 以外の CFAssociation の CSV インポート/エクスポート対応（isPeerOf, exactMatchOf 等）
- OAuth 2.0 Bearer Token 認証（オプション）
- コンピテンシーの意味検索（ベクトル埋め込み）
- フレームワーク間自動マッピング提案

## 背景・差別化

現在のデファクトCASE実装は **OpenSALT** (PCG Education製OSS) だが CASE v1.0 止まり。
本プロジェクトは CASE v1.1 対応の現代的な実装として差別化する。
OpenSALT で公開されているフレームワークをインポートできることも重要な価値。

## CloudFront Invalidation戦略

ワイルドカードを使い常に無料枠（月1000パス）内に収める。
importコマンド完了時に自動でinvalidationを実行する。

| 操作 | invalidationパス | カウント |
|------|----------------|---------|
| テナント全体 | `/{tenant-uuid}/*` | 1 |
| ドキュメント更新 | `/{tenant-uuid}/cftree/doc/{doc-uuid}*` / `/{tenant-uuid}/ims/case/v1p1/CFPackages/{doc-uuid}` / `/{tenant-uuid}/ims/case/v1p1/CFDocuments*` | 3 |

```bash
# import実行時は自動でinvalidation（手動実行も可能）
python cli.py cache invalidate --tenant {uuid}
python cli.py cache invalidate --tenant {uuid} --doc {doc-uuid}
```

## CLI実行環境と認証

### Docker環境（ローカル開発）
CLIは `DATABASE_URL` 環境変数で PostgreSQL に直接接続。
Admin APIに認証なし（ローカル開発用）。

### AWS環境
CLIは Lambda Function URL 経由で Lambda を呼び出す。
Lambda がVPC内でAuroraに接続する。

```
CLI → HTTPS + Bearer token → Lambda Function URL (/admin/*) → Lambda → Aurora
```

**認証:**
- Lambda Function URL: `auth_type=NONE`（インフラ層の認証なし）
- アプリ層: FastAPIミドルウェアで `Authorization: Bearer <shared-secret>` を検証
- CDKデプロイ時にシークレットを生成し、Secrets Manager に保存。CDK Outputs に Function URL を出力
- オペレーター側: `.env` ファイル（ローカル）、Repository Secrets（CI/CD）

```bash
# .env (gitignoreに追加)
CASE_ADMIN_URL=https://xxxxxxxx.lambda-url.ap-northeast-1.on.aws
CASE_ADMIN_KEY=xxxxxxxxxxxxxxxxxxxx
```

CLIは環境変数で接続先を自動判定:
- `DATABASE_URL` あり → 直接DB接続（Docker環境）
- `CASE_ADMIN_URL` + `CASE_ADMIN_KEY` あり → 管理API経由（AWS環境）
- 両方設定されている場合 → `DATABASE_URL` を優先（直接DB接続）。ログに警告を出す。
- どちらもない場合 → エラー終了（「DATABASE_URL or CASE_ADMIN_URL+CASE_ADMIN_KEY を設定してください」）

## バージョン対応方針

| 操作 | v1.0 | v1.1 |
|------|------|------|
| インポート (CSV / 外部CASEソース) | ○ (v1.1に正規化して保存) | ○ |
| API配信 | なし | ○ (v1.1のみ) |

## 参照仕様

### CASE v1.1 (1EdTech Competency and Academic Standards Exchange)
- 仕様トップ: https://www.imsglobal.org/spec/case/v1p1
- Information Model: https://www.imsglobal.org/sites/default/files/spec/case/v1p1/information_model/caseservicev1p1_infomodelv1p0.html
  - §5 Data Model: CFDocument, CFItem, CFAssociation 等のフィールド定義
- REST/JSON Binding: https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html
  - §4 REST API: エンドポイント一覧、リクエスト/レスポンス形式
  - §6 UML to JSON Mappings: 全DType・列挙値の定義
  - §7 Conformance: 必須エンドポイントと準拠要件
  - 付録B: OpenAPI定義 (YAML/JSON) — 1EdTechメンバーログイン要
  - 付録C: JSON Schema — 1EdTechメンバーログイン要
- レスポンス形式: 標準JSON（JSON-LDの `@context` / `@type` はREST APIに含めない）
- imsx_StatusInfo エラー形式: REST Binding §4.4

### 関連仕様
- Open Badges v3: https://www.imsglobal.org/spec/ob/v3p0
- QTI v3.0: https://www.imsglobal.org/spec/qti/v3p0
- OpenSALT (既存CASE実装): https://github.com/opensalt/opensalt
