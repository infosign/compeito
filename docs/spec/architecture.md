# Architecture

## System overview

```
Docker (FastAPI + uvicorn) → PostgreSQL
```

- **Multi-tenant**: tenants are isolated under `/{tenant-uuid}/ims/case/v1p1/` (v1p0 is kept as a backward-compatible redirect).
- **Visibility control**: a public/private flag. Private tenants are hidden from the top list, but reachable via direct URL.
- **Data updates**: CLI only (no Web UI for editing). Data is imported from CSV or from an external CASE source.

## Tech stack

| Layer | Technology |
|-------|-----------|
| API | Python 3.12 + FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| DB | PostgreSQL (Docker) |
| Local dev | Docker + docker-compose |
| Tests | pytest + pytest-asyncio |
| Package management | uv |
| CLI rendering | rich (tables, progress bars, colored output) |
| Web UI | Jinja2 + HTMX + Tailwind CSS (CDN) |

## Alembic migration strategy

Alembic uses the asyncpg driver directly; a sync driver (e.g., psycopg2) is not needed. `env.py` uses the `run_async_migrations()` pattern, connecting via `connectable = create_async_engine(...)`.

```bash
docker compose exec app alembic upgrade head
```

## CLI execution environment

The CLI connects directly to PostgreSQL using `DATABASE_URL` (env var or `.env` file). See [docs/spec/cli.md](./cli.md) for details.

## Version compatibility policy

| Operation | v1.0 | v1.1 |
|-----------|------|------|
| Import (CSV / external CASE source) | yes (normalized and stored as v1.1; Phase 2) | yes |
| API serving | no | yes (v1.1 only) |

## Background and differentiation

The current de facto CASE implementation is **OpenSALT** (an OSS project by PCG Education). Its latest stable release (3.2.0, September 2023) targets CASE v1.0; CASE v1.1 work is in progress on the `develop` branch but is not yet released as of mid-2026. OpenSALT is a full-featured framework editor.

COMPEITO takes a complementary role: a lightweight Python / FastAPI **API distribution server** that ships CASE v1.1 conformance today, with multi-tenancy and bilingual (English / Japanese) UI, CLI, and docs. It is intended as a competency reference endpoint for systems such as Open Badge Factory and QTI Testing. Importing frameworks published in OpenSALT instances is a first-class capability.

## Referenced specifications

### CASE v1.1 (1EdTech Competency and Academic Standards Exchange)
- Spec home: https://www.imsglobal.org/spec/case/v1p1
- Information Model: https://www.imsglobal.org/sites/default/files/spec/case/v1p1/information_model/caseservicev1p1_infomodelv1p0.html
  - §5 Data Model: definitions for CFDocument, CFItem, CFAssociation, etc.
  - Local reference: [docs/reference/case-v1p1-info-model.md](../reference/case-v1p1-info-model.md)
- REST/JSON Binding: https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html
  - §4 REST API: endpoints, request/response shape
  - §6 UML to JSON Mappings: all DTypes and enumerated values
  - §7 Conformance: required endpoints and compliance requirements
  - Appendix B: OpenAPI definitions (YAML/JSON) — requires 1EdTech member login
  - Appendix C: JSON Schema — requires 1EdTech member login
  - Local reference: [docs/reference/case-v1p1-rest-binding.md](../reference/case-v1p1-rest-binding.md)
- OpenAPI 3 schema (authoritative): [docs/reference/imscasev1p1_openapi3_v1p0.json](../reference/imscasev1p1_openapi3_v1p0.json)
  - Official source: https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/imscasev1p1_openapi3_v1p0.json
- Response format: plain JSON (no JSON-LD `@context` / `@type` for the REST API)
- `imsx_StatusInfo` error shape: REST Binding §4.4

### Related specifications
- Open Badges v3: https://www.imsglobal.org/spec/ob/v3p0
- QTI v3.0: https://www.imsglobal.org/spec/qti/v3p0
- OpenSALT (existing CASE implementation): https://github.com/opensalt/opensalt

---

# アーキテクチャ（日本語）

## システム構成

```
Docker (FastAPI + uvicorn) → PostgreSQL
```

- **マルチテナント**: `/{tenant-uuid}/ims/case/v1p1/` でテナント分離（v1p0も後方互換で維持）
- **公開制御**: public/private フラグ。privateはトップ一覧に非表示、URL直接アクセスは可能
- **データ更新**: CLI経由のみ（Web UIなし）。CSV または外部CASEソースからインポート

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| API | Python 3.12 + FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| マイグレーション | Alembic |
| DB | PostgreSQL (Docker) |
| ローカル開発 | Docker + docker-compose |
| テスト | pytest + pytest-asyncio |
| パッケージ管理 | uv |
| CLI表示 | rich (テーブル・プログレスバー・カラー出力) |
| Web UI | Jinja2 + HTMX + Tailwind CSS (CDN) |

## Alembicマイグレーション実行戦略

Alembic は asyncpg（async ドライバ）をそのまま使用する。同期ドライバ（psycopg2）は不要。
`env.py` で `run_async_migrations()` パターンを使い、`connectable = create_async_engine(...)` で接続する。

```bash
docker compose exec app alembic upgrade head
```

## CLI実行環境

CLIは `DATABASE_URL`（環境変数または `.env` ファイル）で PostgreSQL に直接接続。詳細は [docs/spec/cli.md](./cli.md) を参照。

## バージョン対応方針

| 操作 | v1.0 | v1.1 |
|------|------|------|
| インポート (CSV / 外部CASEソース) | ○ (v1.1に正規化して保存、Phase 2) | ○ |
| API配信 | なし | ○ (v1.1のみ) |

## 背景・差別化

CASE 実装のデファクトスタンダードは **OpenSALT** (PCG Education 製 OSS)。現行の安定リリース (3.2.0、2023 年 9 月) は CASE v1.0 対応で、`develop` ブランチで CASE v1.1 対応の作業が進行中（2026 年中盤時点で未リリース）。OpenSALT はフレームワーク編集機能を備えたフル機能ツール。

本プロジェクトは補完的な役割を担う: 軽量な Python / FastAPI ベースの **API 配信サーバー**として CASE v1.1 を正式リリースで提供し、マルチテナント・英日両対応の UI / CLI / ドキュメントを備える。Open Badge Factory や QTI Testing 等のコンピテンシー参照先として連携することを目指す。OpenSALT インスタンスで公開されたフレームワークをインポートできることも重要な価値。

## 参照仕様

### CASE v1.1 (1EdTech Competency and Academic Standards Exchange)
- 仕様トップ: https://www.imsglobal.org/spec/case/v1p1
- Information Model: https://www.imsglobal.org/sites/default/files/spec/case/v1p1/information_model/caseservicev1p1_infomodelv1p0.html
  - §5 Data Model: CFDocument, CFItem, CFAssociation 等のフィールド定義
  - ローカル参照: [docs/reference/case-v1p1-info-model.md](../reference/case-v1p1-info-model.md)
- REST/JSON Binding: https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html
  - §4 REST API: エンドポイント一覧、リクエスト/レスポンス形式
  - §6 UML to JSON Mappings: 全DType・列挙値の定義
  - §7 Conformance: 必須エンドポイントと準拠要件
  - 付録B: OpenAPI定義 (YAML/JSON) — 1EdTechメンバーログイン要
  - 付録C: JSON Schema — 1EdTechメンバーログイン要
  - ローカル参照: [docs/reference/case-v1p1-rest-binding.md](../reference/case-v1p1-rest-binding.md)
- OpenAPI 3 スキーマ（権威的ソース）: [docs/reference/imscasev1p1_openapi3_v1p0.json](../reference/imscasev1p1_openapi3_v1p0.json)
  - 公式配布元: https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/imscasev1p1_openapi3_v1p0.json
- レスポンス形式: 標準JSON（JSON-LDの `@context` / `@type` はREST APIに含めない）
- imsx_StatusInfo エラー形式: REST Binding §4.4

### 関連仕様
- Open Badges v3: https://www.imsglobal.org/spec/ob/v3p0
- QTI v3.0: https://www.imsglobal.org/spec/qti/v3p0
- OpenSALT (既存CASE実装): https://github.com/opensalt/opensalt
