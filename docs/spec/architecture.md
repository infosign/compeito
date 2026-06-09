# Architecture

## System overview

```
Docker (FastAPI + uvicorn) → PostgreSQL
```

- **Multi-tenant**: tenants are isolated under `/{tenant}/ims/case/v1p1/` (v1p0 is kept as a backward-compatible redirect). `{tenant}` is either the tenant UUID (canonical) or, if set, a URL-friendly `slug` alias (e.g., `ikenohata-u`). CASE API response bodies always carry the canonical UUID; slugs appear only in Web UI navigation. See [cli.md](./cli.md#tenant-slug-rules) for the slug format and [web-ui.md](./web-ui.md#uuid-vs-slug--which-one-appears-where) for which URL form is used where.
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
| Web UI | Jinja2 + HTMX (self-hosted) + Tailwind CSS (self-hosted; built at image-build time, CDN fallback in native dev) |

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

The 1EdTech CASE ecosystem has several active open-source implementations:

- **[OpenCASE](https://github.com/1EdTech/OpenCASE)** — the 1EdTech reference implementation. A full platform combining a visual framework editor, Keycloak-based multi-tenant authentication, immutable version history, and a certified publishing server. A good fit for organizations that want a single integrated stack covering editing through publishing.
- **[OpenSALT](https://github.com/opensalt/opensalt)** — the long-standing community implementation by PCG Education. The latest stable release (3.2.0, September 2023) targets CASE v1.0; v1.1 work is underway on the `develop` branch. A full-featured framework editor with a large existing user base, especially around US K-12 standards.
- **COMPEITO** — a lightweight, distribution-focused server developed in Japan. CASE v1.1 conformance shipping today, with English/Japanese bilingual UI / CLI / docs, custom-and-OpenSALT CSV import paths, and an emphasis on being easy to embed in existing stacks.

These projects are designed to **interoperate via the CASE standard**. COMPEITO can import CFPackages published by OpenSALT or OpenCASE, and frameworks published by COMPEITO can be consumed by any CASE-conformant client (e.g., Open Badge Factory). COMPEITO's specific niche is: a small focused publishing component to pair with an external editor, or a Japanese-language CASE endpoint for use with Open Badge Factory, QTI Testing, and similar reference clients.

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

- **マルチテナント**: `/{tenant}/ims/case/v1p1/` でテナント分離（v1p0も後方互換で維持）。`{tenant}` はテナント UUID（canonical）または設定済みの URL 別名 `slug`（例: `ikenohata-u`）のいずれか。CASE API レスポンス本文では常に canonical な UUID を返し、slug は Web UI のナビゲーションのみで使う。slug のフォーマット仕様は [cli.md](./cli.md#テナント-slug-の制約)、Web UI 上の使い分けは [web-ui.md](./web-ui.md#uuid-と-slug-の使い分け) を参照
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
| Web UI | Jinja2 + HTMX (self-hosted) + Tailwind CSS (self-hosted; built at image-build time, CDN fallback in native dev) |

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

1EdTech CASE のエコシステムには複数の OSS 実装が存在する:

- **[OpenCASE](https://github.com/1EdTech/OpenCASE)** — 1EdTech 公式のリファレンス実装。ビジュアルなフレームワークエディタ、Keycloak ベースのマルチテナント認証、不変なバージョン履歴、認定済み配信サーバーを一体で提供するフルプラットフォーム。編集から配信までを一つのスタックで完結させたい組織に向いている。
- **[OpenSALT](https://github.com/opensalt/opensalt)** — 長年コミュニティで使われてきた PCG Education 開発の実装。安定リリース 3.2.0 (2023 年 9 月) は CASE v1.0 対応、v1.1 対応は `develop` ブランチで作業中。フル機能のエディタで、米国の K-12 標準など大きな既存ユーザーベースを持つ。
- **COMPEITO** — 日本で開発される軽量・配信特化サーバー。CASE v1.1 を正式リリースで提供し、英日両対応の UI / CLI / ドキュメント、独自 CSV と OpenSALT 互換 CSV のインポート、既存スタックへの組み込みやすさを重視している。

これらは **CASE 標準を介して相互運用すること** を前提に設計されている。COMPEITO は OpenSALT や OpenCASE が公開する CFPackage を取り込むことができ、COMPEITO が公開するフレームワークは CASE 準拠の任意のクライアント（例: Open Badge Factory）から参照可能。COMPEITO の独自の立ち位置は、既存エディタと組み合わせて配信を担当する軽量コンポーネントとして、または Open Badge Factory / QTI Testing 等の参照クライアントと繋ぐ日本語環境向けの CASE エンドポイントとして機能することにある。

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
