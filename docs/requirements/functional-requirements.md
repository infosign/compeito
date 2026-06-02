# Functional Requirements

## FR-1: Multi-tenant

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-1.1 | Tenants are identified by UUID v4 and isolated under the URL path `/{tenant-uuid}/` | 1 |
| FR-1.2 | Tenants have an `is_private` flag; private tenants are hidden from the top list (`/`) | 1 |
| FR-1.3 | Private tenants remain reachable via direct URL (URL secrecy as the control) | 1 |
| FR-1.4 | Deleting a tenant CASCADE-deletes all owned resources (CFDocument, CFItem, CFAssociation, lookups) | 1 |

## FR-2: CASE v1.1 API

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-2.1 | Provide the 11 CASE v1.1 endpoints (excluding CFRubric) plus 5 custom listing endpoints under `/{tenant}/ims/case/v1p1/` | 1 |
| FR-2.2 | The CFPackage endpoint returns CFDocument, CFItems, CFAssociations, and CFDefinitions in one response | 1 |
| FR-2.3 | CFPackage always includes CFItems / CFAssociations as arrays (empty if no data). CFDefinitions is omitted entirely when empty | 1 |
| FR-2.4 | All listing endpoints support pagination via `limit` (default 100, max 500) and `offset` (default 0, max 100000) | 1 |
| FR-2.5 | `sort` / `orderBy` / `filter` / `fields` parameters are ignored (no error) | 1 |
| FR-2.6 | Error responses use the CASE v1.1 `imsx_StatusInfo` shape | 1 |
| FR-2.7 | LinkURI types (CFPackageURI, CFDocumentURI, etc.) are returned as composite objects `{title, identifier, uri}` | 1 |
| FR-2.8 | Requests to `/ims/case/v1p0/` are 301-redirected to `/ims/case/v1p1/` | 1 |
| FR-2.9 | Non-GET requests (POST/PUT/DELETE/PATCH) on CASE API paths return 405 Method Not Allowed | 1 |
| FR-2.10 | Nullable fields are included in responses as `null` (`exclude_none=False`). CASE v1.1 allows either inclusion or omission; we always include for consistency | 1 |
| FR-2.11 | Provide CFRubric API endpoints | 2 |

## FR-3: Validation

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-3.1 | `{tenant-uuid}` not in UUID form → 400 (`invalid_uuid`) | 1 |
| FR-3.2 | UUID form but tenant not found → 404 (`unknownobject`) | 1 |
| FR-3.3 | `/uri/{uuid}` is searched within the tenant scope; resources of other tenants return 404 | 1 |
| FR-3.4 | Resource `{id}` (e.g., in `/CFItems/{id}`) not in UUID form → 400 (`invalid_uuid`) | 1 |
| FR-3.5 | UUID form but the resource is not found → 404 (`unknownobject`) | 1 |
| FR-3.6 | `GET /CFItemAssociations/{id}` returns 404 (not an empty array) when the item does not exist | 1 |

## FR-4: Health check

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-4.1 | `GET /health` returns `{"status": "ok"}` (no auth, no tenant path) | 1 |
| FR-4.2 | No DB connection check (prioritize cold-start speed) | 1 |

## FR-6: CSV import

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-6.1 | Auto-detect between custom format, OpenSALT format, and simple format from the header row | 1 |
| FR-6.2 | Metadata rows starting with `#` populate CFDocument fields | 1 |
| FR-6.3 | When `--doc` is omitted, create a new CFDocument; when specified, update the existing one | 1 |
| FR-6.4 | CFItem upsert is performed in this priority: Identifier match → humanCodingScheme match | 1 |
| FR-6.5 | Lookup tables (CFItemType, CFSubject, CFLicense) are auto-created by exact `title` match within the tenant. CFConcept is created only by the external CASE source import | 1 |
| FR-6.6 | `isChildOf` CFAssociations are auto-generated from parent–child rows | 1 |
| FR-6.7 | When updating an existing document (`--doc` specified, or OpenSALT `Is Part Of` matched an existing document), delete all of its existing `isChildOf` associations and regenerate | 1 |
| FR-6.8 | When `sequenceNumber` is blank, auto-assign 10, 20, 30, … in encounter order within each parent (counter per parent) | 1 |
| FR-6.9 | Simple format uses indentation (2 spaces or 1 tab = one level) to express hierarchy | 1 |
| FR-6.10 | URIs for newly created resources are generated as `{BASE_URL}/{tenant_id}/uri/{identifier}` | 1 |
| FR-6.11 | When an Identifier is duplicated within a single CSV, the later row wins and a warning is emitted | 1 |
| FR-6.12 | Compute `depth` via BFS over `isChildOf` and detect cycles | 1 |
| FR-6.13 | Output a report of import results (created/updated/skipped/warnings) | 1 |
| FR-6.14 | Accept UTF-8 (with or without BOM) and both CR+LF / LF line endings | 1 |

## FR-7: External CASE source import

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-7.1 | Fetch CFPackage JSON from a CASE v1.1 API and persist it | 1 |
| FR-7.2 | Preserve external URIs and identifiers as-is (do not overwrite with own server URIs) | 1 |
| FR-7.3 | Also persist CFDefinitions (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping) | 1 |
| FR-7.4 | Distinguish connection / HTTP / JSON-parse / SSL-certificate errors and exit with the appropriate diagnostic | 1 |
| FR-7.5 | Invalid resources inside the CFPackage are skipped with a warning; the rest of the import continues | 1 |
| FR-7.6 | When `--doc` is omitted, look up by the external CFDocument identifier — create if missing, update if present. With `--doc`, overwrite the specified document | 1 |
| FR-7.7 | Normalize CASE v1.0 responses to v1.1 format on save | 2 |

## FR-8: CSV export

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-8.1 | Export in the custom format (including Identifier, parentIdentifier, sequenceNumber) | 1 |
| FR-8.2 | Sort rows in tree depth-first order (sequence_number → human_coding_scheme → identifier) | 1 |
| FR-8.3 | Emit metadata rows (`#title`, `#version`, etc.) | 1 |
| FR-8.4 | Export in OpenSALT-compatible format (`--format opensalt`) | 2 |

## FR-9: Web UI

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-9.1 | `GET /` lists public tenants (private tenants are hidden) | 1 |
| FR-9.2 | `GET /{tenant}/` lists frameworks (CFDocument title, lastChangeDateTime, item count) | 1 |
| FR-9.3 | `GET /{tenant}/cftree/doc/{doc}` renders a two-pane tree view (tree on the left, detail on the right) | 1 |
| FR-9.4 | The tree view SSR-renders levels 1–2; levels 3+ are lazy-loaded via HTMX | 1 |
| FR-9.5 | `GET /{tenant}/uri/{uuid}` renders a resource detail page (CFItem, CFDocument, lookup, CFAssociation) | 1 |
| FR-9.6 | `/uri/{uuid}` pages function as the public destination linked from external systems (e.g., Open Badge Factory) | 1 |
| FR-9.7 | On mobile, only the tree is shown; tapping an item navigates to `/uri/` | 1 |
| FR-9.8 | User-friendly error pages (404 / 400 / 500) | 1 |
| FR-9.9 | The tree view supports deep linking via `?item={uuid}` (returns the expand path from root via SSR) | 1 |

## FR-10: CLI

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-10.1 | Tenant management commands: create, list, update, delete | 1 |
| FR-10.2 | Framework management commands: list, delete | 1 |
| FR-10.3 | CSV import command (`import csv`) | 1 |
| FR-10.4 | External CASE source import command (`import case-url`) | 1 |
| FR-10.5 | CSV export command (`export csv`) | 1 |
| FR-10.6 | DB migration command (`db migrate`) | 1 |
| FR-10.7 | Connect directly to the DB via `DATABASE_URL` env var or `.env` file | 1 |
| FR-10.9 | Delete commands prompt for confirmation; `--force` skips the prompt | 1 |
| FR-10.10 | CLI uses the `rich` library for tables, progress bars, and colored output | 1 |

## FR-11: Content negotiation

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-11.1 | No content negotiation (avoids conflicts with CloudFront caching) | 1 |
| FR-11.2 | Web UI paths (`/`, `/{tenant}/`, `/cftree/`, `/uri/{uuid}`) always return HTML | 1 |
| FR-11.3 | CASE API paths (`/ims/case/v1p1/`) always return JSON | 1 |

## FR-12: Phase 3 features (future)

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-12.1 | CSV import / export for CFAssociation types other than `isChildOf` (`isPeerOf`, `exactMatchOf`, etc.) | 3 |
| FR-12.2 | Semantic search over competencies using vector embeddings | 3 |
| FR-12.3 | Automatic cross-framework mapping suggestions | 3 |

---

# 機能要件（日本語）

## FR-1: マルチテナント

| ID | 要件 | Phase |
|----|------|-------|
| FR-1.1 | テナントをUUID v4で識別し、URLパス `/{tenant-uuid}/` で分離する | 1 |
| FR-1.2 | テナントに `is_private` フラグを持ち、private テナントはトップ一覧（`/`）に表示しない | 1 |
| FR-1.3 | private テナントもURL直接アクセスでは閲覧可能とする（URLの秘匿性で制御） | 1 |
| FR-1.4 | テナント削除時、配下の全リソース（CFDocument, CFItem, CFAssociation, lookup系）をCASCADE削除する | 1 |

## FR-2: CASE v1.1 API

| ID | 要件 | Phase |
|----|------|-------|
| FR-2.1 | CASE v1.1 準拠の 11 エンドポイント（CFRubric 除く）+ 独自拡張の一覧エンドポイント 5 つを `/{tenant}/ims/case/v1p1/` パスで提供する | 1 |
| FR-2.2 | CFPackage エンドポイントで、CFDocument・CFItems・CFAssociations・CFDefinitions を一括返却する | 1 |
| FR-2.3 | CFPackage の CFItems・CFAssociations はデータがなくても空配列として常に含める。CFDefinitions はデータがなければ省略する | 1 |
| FR-2.4 | 全一覧エンドポイントに `limit`（デフォルト100, 最大500）/ `offset`（デフォルト0, 最大100000）のページネーションを実装する | 1 |
| FR-2.5 | `sort` / `orderBy` / `filter` / `fields` パラメータは無視する（エラーにしない） | 1 |
| FR-2.6 | エラーレスポンスは CASE v1.1 の imsx_StatusInfo 形式で返す | 1 |
| FR-2.7 | LinkURI型（CFPackageURI, CFDocumentURI 等）は `{title, identifier, uri}` の複合オブジェクトで返す | 1 |
| FR-2.8 | `/ims/case/v1p0/` パスへのリクエストを `/ims/case/v1p1/` に301リダイレクトする | 1 |
| FR-2.9 | CASE API パスへの非GETリクエスト（POST/PUT/DELETE/PATCH）には 405 Method Not Allowed を返す | 1 |
| FR-2.10 | null 許容フィールドはレスポンスに `null` として含める（`exclude_none=False`）。CASE v1.1 仕様は含めるか省略するかを許容するが、本システムでは一貫性のため常に含める方針とする | 1 |
| FR-2.11 | CFRubric API エンドポイントを提供する | 2 |

## FR-3: バリデーション

| ID | 要件 | Phase |
|----|------|-------|
| FR-3.1 | `{tenant-uuid}` がUUID形式でない場合、400エラー（`invalid_uuid`）を返す | 1 |
| FR-3.2 | UUID形式だがテナントが存在しない場合、404エラー（`unknownobject`）を返す | 1 |
| FR-3.3 | `/uri/{uuid}` はテナントスコープ内で検索し、別テナントのリソースには404を返す | 1 |
| FR-3.4 | リソースID（`/CFItems/{id}` 等の `{id}`）がUUID形式でない場合、400エラー（`invalid_uuid`）を返す | 1 |
| FR-3.5 | リソースIDがUUID形式だがリソースが存在しない場合、404エラー（`unknownobject`）を返す | 1 |
| FR-3.6 | `GET /CFItemAssociations/{id}` でアイテムが存在しない場合、空配列ではなく404エラーを返す | 1 |

## FR-4: ヘルスチェック

| ID | 要件 | Phase |
|----|------|-------|
| FR-4.1 | `GET /health` で `{"status": "ok"}` を返す（認証不要、テナントパス不要） | 1 |
| FR-4.2 | DB接続確認は行わない（コールドスタート高速化を優先） | 1 |

## FR-6: CSVインポート

| ID | 要件 | Phase |
|----|------|-------|
| FR-6.1 | 独自形式・OpenSALT形式・簡易形式の3種類をヘッダー行から自動判定する | 1 |
| FR-6.2 | `#` で始まるメタデータ行からCFDocumentフィールドを設定する | 1 |
| FR-6.3 | `--doc` 未指定時は新規CFDocumentを作成、指定時は既存を更新する | 1 |
| FR-6.4 | CFItem の upsert を Identifier一致 → humanCodingScheme一致 の優先順で行う | 1 |
| FR-6.5 | lookup テーブル（CFItemType, CFSubject, CFLicense）を同一テナント内 `title` 完全一致で自動生成する（CFConcept は外部 CASE ソースインポートでのみ作成） | 1 |
| FR-6.6 | isChildOf の CFAssociation を親子関係から自動生成する | 1 |
| FR-6.7 | 既存ドキュメントの更新時（`--doc` 指定、または OpenSALT `Is Part Of` で既存ドキュメントにマッチした場合）、該当ドキュメントの既存 isChildOf Association を全削除してから再生成する | 1 |
| FR-6.8 | sequenceNumber が空の場合、同一親内で出現順に 10, 20, 30... で自動採番する（各親ごとに独立したカウンタ） | 1 |
| FR-6.9 | 簡易形式ではインデント（スペース2つ or タブ1つ = 1段）で階層を判定する | 1 |
| FR-6.10 | 新規作成リソースの URI を `{BASE_URL}/{tenant_id}/uri/{identifier}` で生成する | 1 |
| FR-6.11 | 同一CSV内で Identifier が重複した場合、後の行を採用し警告を出力する | 1 |
| FR-6.12 | depth を isChildOf から BFS で計算し、循環参照を検出する | 1 |
| FR-6.13 | インポート結果（created/updated/skipped/warnings）をレポート出力する | 1 |
| FR-6.14 | UTF-8（BOM付き/無し）、CR+LF/LF の両方に対応する | 1 |

## FR-7: 外部CASEソースインポート

| ID | 要件 | Phase |
|----|------|-------|
| FR-7.1 | CASE v1.1 API から CFPackage JSON を取得し、DB に保存する | 1 |
| FR-7.2 | 外部リソースの URI と identifier をそのまま保持する（自サーバーの URI で上書きしない） | 1 |
| FR-7.3 | CFDefinitions（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）も保存する | 1 |
| FR-7.4 | 接続エラー・HTTPエラー・JSONパースエラー・SSL証明書エラーを区別してエラー終了する | 1 |
| FR-7.5 | CFPackage内の個別リソース不正は警告付きでスキップし、他は処理を続行する | 1 |
| FR-7.6 | `--doc` 未指定時は外部CFDocumentのidentifierで既存を検索し、存在すれば更新、なければ新規作成する。`--doc` 指定時は既存を上書き更新する | 1 |
| FR-7.7 | CASE v1.0 のレスポンスを v1.1 形式に正規化して保存する | 2 |

## FR-8: CSVエクスポート

| ID | 要件 | Phase |
|----|------|-------|
| FR-8.1 | 独自形式でエクスポートする（Identifier・parentIdentifier・sequenceNumber を含む） | 1 |
| FR-8.2 | ツリーの depth-first 順にソートする（sequence_number → human_coding_scheme → identifier） | 1 |
| FR-8.3 | メタデータ行（`#title`, `#version` 等）を出力する | 1 |
| FR-8.4 | OpenSALT互換形式でエクスポートする（`--format opensalt`） | 2 |

## FR-9: Web UI

| ID | 要件 | Phase |
|----|------|-------|
| FR-9.1 | `GET /` で公開テナント一覧を表示する（private テナントは非表示） | 1 |
| FR-9.2 | `GET /{tenant}/` でフレームワーク一覧（CFDocument の title, lastChangeDateTime, アイテム数）を表示する | 1 |
| FR-9.3 | `GET /{tenant}/cftree/doc/{doc}` で2ペインのツリービューを表示する（左: ツリー、右: 詳細） | 1 |
| FR-9.4 | ツリービューは Level 1-2 を SSR、Level 3+ を HTMX 遅延ロードで返す | 1 |
| FR-9.5 | `GET /{tenant}/uri/{uuid}` でリソース詳細ページを表示する（CFItem, CFDocument, lookup, CFAssociation 対応） | 1 |
| FR-9.6 | `/uri/{uuid}` ページは Open Badge Factory 等の外部システムからリンクされる公開ページとして機能する | 1 |
| FR-9.7 | モバイルではツリーのみ表示し、アイテムタップで `/uri/` に遷移する | 1 |
| FR-9.8 | エラーページ（404/400/500）をユーザーフレンドリーに表示する | 1 |
| FR-9.9 | ツリービューの `?item={uuid}` パラメータでアイテムへのディープリンクをサポートする（ルートから該当アイテムまでの展開パスをSSRで返す） | 1 |

## FR-10: CLI

| ID | 要件 | Phase |
|----|------|-------|
| FR-10.1 | テナント管理（create, list, update, delete）コマンドを提供する | 1 |
| FR-10.2 | フレームワーク管理（list, delete）コマンドを提供する | 1 |
| FR-10.3 | CSVインポート（`import csv`）コマンドを提供する | 1 |
| FR-10.4 | 外部CASEソースインポート（`import case-url`）コマンドを提供する | 1 |
| FR-10.5 | CSVエクスポート（`export csv`）コマンドを提供する | 1 |
| FR-10.6 | DBマイグレーション（`db migrate`）コマンドを提供する | 1 |
| FR-10.7 | `DATABASE_URL` 環境変数または `.env` ファイルから直接DB接続する | 1 |
| FR-10.9 | 削除コマンドは確認プロンプトを表示し、`--force` でスキップ可能とする | 1 |
| FR-10.10 | rich ライブラリでテーブル・プログレスバー・カラー出力を行う | 1 |

## FR-11: コンテントネゴシエーション

| ID | 要件 | Phase |
|----|------|-------|
| FR-11.1 | コンテントネゴシエーションは使わない（CloudFront キャッシュとの競合回避） | 1 |
| FR-11.2 | Web UI パス（`/`, `/{tenant}/`, `/cftree/`, `/uri/{uuid}`）は常にHTMLを返す | 1 |
| FR-11.3 | CASE API パス（`/ims/case/v1p1/`）は常にJSONを返す | 1 |

## FR-12: Phase 3 機能（将来）

| ID | 要件 | Phase |
|----|------|-------|
| FR-12.1 | isChildOf 以外の CFAssociation（isPeerOf, exactMatchOf 等）の CSV インポート/エクスポートに対応する | 3 |
| FR-12.2 | コンピテンシーの意味検索をベクトル埋め込みで提供する | 3 |
| FR-12.3 | フレームワーク間の自動マッピング提案機能を提供する | 3 |
