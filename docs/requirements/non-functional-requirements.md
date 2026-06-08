# Non-Functional Requirements

## NFR-1: Performance

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-1.1 | A single CASE API resource fetch responds within p95 500ms | |
| NFR-1.2 | CFPackage fetch responds within p95 3s for 5,000-item frameworks | |
| NFR-1.3 | Tree view initial render (SSR portion) responds within p95 1s | Levels 1–2 SSR. Access with `?item=` (expand-path computation + additional SSR scope) is out of scope. |
| NFR-1.4 | HTMX child item fragment fetch responds within p95 300ms | |
| NFR-1.5 | CSV import processes a 10,000-row CSV within 60s | |
| NFR-1.6 | External CASE source import uses 30s HTTP timeout per request | No retry. Up to 5 redirects followed. |

## NFR-2: Scalability

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-2.1 | A single tenant can hold 100,000 items | Sum across multiple frameworks |

## NFR-3: Health check

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-3.1 | `GET /health` responds immediately without touching the DB | |

## NFR-4: Security

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-4.1 | CASE API is exposed without authentication | Per CASE v1.1 (read-only) |
| NFR-4.2 | Private-tenant non-disclosure relies on URL secrecy | UUID unguessability |
| NFR-4.3 | compeito itself does not provide authentication on the CASE Provider API | Out of scope (see NG-2 in functional-requirements.md / phases.md). Authenticated admin access, when needed, lives in a separate deployment/management layer |

## NFR-5: Caching

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-5.1 | All CASE API and Web UI (including the top `/`) responses set `Cache-Control: public, max-age=3600` | Public/private tenants alike. Exceptions: error responses (4xx/5xx) have no Cache-Control; v1p0→v1p1 redirects (301) also have none (per HTTP, 301 is cacheable by default; see api-spec.md). |
| NFR-5.2 | HTMX fragments set `Cache-Control: public, max-age=86400` | `/cftree/doc/*/children/*` and `/cftree/doc/*/detail/*` |
| NFR-5.3 | Health check sets `Cache-Control: no-store` | Prevent caching |

## NFR-6: Data integrity

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-6.1 | Every CASE resource's `identifier` is UNIQUE within a tenant (`UNIQUE(tenant_id, identifier)`) | Multiple tenants can import the same external framework |
| NFR-6.2 | FK delete policies use CASCADE for ownership and SET NULL for references | Details in db-schema.md |
| NFR-6.3 | Internal PK (`id`) and CASE identifier (`identifier`) are separate so external imports don't break FKs | |
| NFR-6.4 | CSV import detects cycles and reports affected items | During depth calculation |
| NFR-6.5 | CSV import validation errors skip the offending row and continue with the rest | Skip happens before DB writes. DB-write errors roll back the whole transaction (see import-logic.md) |
| NFR-6.6 | Concurrent imports against the same document are serialized via `SELECT ... FOR UPDATE` | Prevents the isChildOf delete-all → regenerate race (see import-logic.md) |

## NFR-7: Operations / observability

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-7.1 | Standard logs are emitted to stdout/stderr via the container log driver | Collected by whatever the deployment uses (e.g., `docker logs`, or a hosted log sink) |
| NFR-7.2 | Import results (created/updated/skipped/warnings) are logged | CLI: rich tables; API: JSON |
| NFR-7.3 | CSV import warnings include row numbers | |
| NFR-7.4 | CLI uses the `rich` library for tables, progress bars, and colored output | UX |

## NFR-8: Deployment / infrastructure

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-8.1 | Development and runtime environments are built with Docker + Docker Compose | |

## NFR-9: Testing

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-9.1 | Unit and integration tests use pytest + pytest-asyncio | |
| NFR-9.2 | Test DB is Docker PostgreSQL (not SQLite) | Avoids async driver differences |
| NFR-9.3 | `conftest.py` handles test DB setup and rollback | |
| NFR-9.4 | CI (GitHub Actions) runs `docker compose up -d db` before tests | Phase 2 |

## NFR-10: Compatibility / compliance

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-10.1 | Complies with CASE v1.1 REST/JSON Binding | Endpoints and response shape |
| NFR-10.2 | Imports OpenSALT CSV formats | Migration path |
| NFR-10.3 | Compatible with OpenSALT's `/uri/{uuid}` URL pattern | Preserves external links |
| NFR-10.4 | Acts as a reference target for Open Badge v3 / QTI v3.0 | Competency framework distribution |
| NFR-10.5 | Responses are plain JSON (no JSON-LD `@context` / `@type`) | Per CASE v1.1 REST Binding |

## NFR-11: Maintainability

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-11.1 | Layered architecture: router → service → repository | Separation of concerns |
| NFR-11.2 | All DB operations are async/await (SQLAlchemy async session) | |
| NFR-11.3 | CASE field names use camelCase (per spec); internal code uses snake_case | |
| NFR-11.4 | DB schema is version-controlled via Alembic | Direct asyncpg driver |
| NFR-11.5 | Python 3.12 | |
| NFR-11.6 | `uv` is used as the package manager | |

---

# 非機能要件（日本語）

## NFR-1: パフォーマンス

| ID | 要件 | 備考 |
|----|------|------|
| NFR-1.1 | CASE API の単一リソース取得は p95 で 500ms 以内に応答する | |
| NFR-1.2 | CFPackage 取得は 5,000 アイテム規模で p95 3秒以内に応答する | |
| NFR-1.3 | ツリービュー初期表示（SSR部分）は p95 で 1秒以内に応答する | Level 1-2 の SSR 部分。`?item=` パラメータ付きアクセス（展開パス計算 + 追加SSR対象）はこの目標の対象外 |
| NFR-1.4 | HTMX 子アイテムフラグメント取得は p95 で 300ms 以内に応答する | |
| NFR-1.5 | CSVインポートは 10,000 行のCSVを 60秒以内に処理する | |
| NFR-1.6 | 外部CASEソースインポートのHTTPタイムアウトは各リクエストごとに 30秒とする | リトライしない。リダイレクトは最大5回追従 |

## NFR-2: スケーラビリティ

| ID | 要件 | 備考 |
|----|------|------|
| NFR-2.1 | 1テナントあたり 100,000 アイテムを保持できる | 複数フレームワーク合計 |

## NFR-3: ヘルスチェック

| ID | 要件 | 備考 |
|----|------|------|
| NFR-3.1 | ヘルスチェック（`GET /health`）はDB接続を行わず即座に応答する | |

## NFR-4: セキュリティ

| ID | 要件 | 備考 |
|----|------|------|
| NFR-4.1 | CASE API は認証なしで公開する | CASE v1.1 仕様上、読み取り専用 |
| NFR-4.2 | private テナントの非公開はURL自体の秘匿性で実現する | UUIDの推測困難性に依拠 |
| NFR-4.3 | compeito 自身は CASE Provider API に認証を提供しない | スコープ外（functional-requirements.md / phases.md の NG-2 参照）。認証付きの管理アクセスが必要な場合は、別途のデプロイ/管理レイヤーが担う |

## NFR-5: キャッシュ

| ID | 要件 | 備考 |
|----|------|------|
| NFR-5.1 | 全 CASE API・Web UI（トップページ `/` 含む）に `Cache-Control: public, max-age=3600` を設定する | public/private テナント共通。例外: エラーレスポンス（4xx/5xx）には Cache-Control を設定しない。v1p0→v1p1 リダイレクト（301）にも Cache-Control を設定しない（HTTP 仕様上 301 はデフォルトでキャッシュ可能。api-spec.md 参照） |
| NFR-5.2 | HTMX フラグメントに `Cache-Control: public, max-age=86400` を設定する | `/cftree/doc/*/children/*` および `/cftree/doc/*/detail/*` |
| NFR-5.3 | ヘルスチェックに `Cache-Control: no-store` を設定する | キャッシュ防止 |

## NFR-6: データ整合性

| ID | 要件 | 備考 |
|----|------|------|
| NFR-6.1 | 全CASEリソースの `identifier` はテナント内で UNIQUE とする（`UNIQUE(tenant_id, identifier)`） | 複数テナントが同じ外部フレームワークをインポート可能 |
| NFR-6.2 | FK 削除ポリシーを所有関係（CASCADE）と参照関係（SET NULL）で使い分ける | 詳細は db-schema.md |
| NFR-6.3 | 内部PK（`id`）と CASE 識別子（`identifier`）を分離し、外部インポートでFKが壊れないようにする | |
| NFR-6.4 | CSVインポートの循環参照を検出し、該当アイテムをエラーレポートに出力する | depth 計算時 |
| NFR-6.5 | CSVインポートのバリデーションエラーは行単位でスキップし、他の行は処理を続行する | バリデーション段階（DB書き込み前）でのスキップ。DB書き込み段階のエラーはトランザクション全体をロールバックする（詳細は import-logic.md） |
| NFR-6.6 | 同一ドキュメントへの並行インポートを `SELECT ... FOR UPDATE` で直列化する | isChildOf 全削除→再生成の競合防止（詳細は import-logic.md） |

## NFR-7: 運用・可観測性

| ID | 要件 | 備考 |
|----|------|------|
| NFR-7.1 | 標準ログを stdout/stderr にコンテナログドライバ経由で出力する | デプロイ環境のログ基盤（`docker logs` やホスト型ログ収集等）で収集する |
| NFR-7.2 | インポート結果（created/updated/skipped/warnings）をログに出力する | CLI: rich テーブル、API: JSON |
| NFR-7.3 | CSVインポートの警告は行番号付きで出力する | |
| NFR-7.4 | CLI は rich ライブラリでテーブル・プログレスバー・カラー出力する | UX向上 |

## NFR-8: デプロイ・インフラ

| ID | 要件 | 備考 |
|----|------|------|
| NFR-8.1 | Docker + Docker Compose で開発・実行環境を構築する | |

## NFR-9: テスト

| ID | 要件 | 備考 |
|----|------|------|
| NFR-9.1 | pytest + pytest-asyncio で unit/integration テストを実装する | |
| NFR-9.2 | テスト DB は Docker PostgreSQL を使用する（SQLite 不使用） | 非同期ドライバの差異回避 |
| NFR-9.3 | `conftest.py` でテスト用 DB のセットアップ・ロールバックを行う | |
| NFR-9.4 | CI（GitHub Actions）で `docker compose up -d db` してからテスト実行する | Phase 2 |

## NFR-10: 互換性・準拠

| ID | 要件 | 備考 |
|----|------|------|
| NFR-10.1 | CASE v1.1 REST/JSON Binding に準拠する | エンドポイント・レスポンス形式 |
| NFR-10.2 | OpenSALT の CSV フォーマットをインポート可能とする | 移行パス |
| NFR-10.3 | OpenSALT の `/uri/{uuid}` URL パターンと互換にする | 外部リンク維持 |
| NFR-10.4 | Open Badge v3 / QTI v3.0 の参照先として機能する | コンピテンシーフレームワーク配信 |
| NFR-10.5 | レスポンスは標準 JSON とする（JSON-LD の `@context` / `@type` は含めない） | CASE v1.1 REST Binding 準拠 |

## NFR-11: 保守性

| ID | 要件 | 備考 |
|----|------|------|
| NFR-11.1 | レイヤー構成を router → service → repository で統一する | 関心の分離 |
| NFR-11.2 | 全 DB 操作は async/await（SQLAlchemy async session）で統一する | |
| NFR-11.3 | CASE フィールド名はキャメルケース（仕様準拠）、内部はスネークケースとする | |
| NFR-11.4 | Alembic マイグレーションで DB スキーマをバージョン管理する | asyncpg ドライバ直接使用 |
| NFR-11.5 | Python 3.12 を使用する | |
| NFR-11.6 | パッケージ管理に uv を使用する | |
