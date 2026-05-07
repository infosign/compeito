# COMPEITO

**Comp**etency **E**xchange & **I**nteroperability **To**ol

A modern [1EdTech CASE v1.1](https://www.imsglobal.org/spec/case/v1p1) compatible server for publishing competency frameworks via REST API. Aiming to serve as a competency reference endpoint for platforms such as [Open Badge Factory (OB v3)](https://www.imsglobal.org/spec/ob/v3p0) and [TAO Testing (QTI v3.0)](https://www.imsglobal.org/spec/qti/v3p0) in the future.

> "compeito" is also the Japanese word for [konpeitō](https://en.wikipedia.org/wiki/Konpeit%C5%8D) (金平糖), a traditional Japanese sugar candy.

## Features

- **CASE v1.1 compatible** — All required REST API endpoints (CFPackages, CFDocuments, CFItems, CFAssociations, and more)
- **Multi-tenant** — Serve multiple organizations from a single instance, each with their own UUID namespace
- **Tree view UI** — Browse competency frameworks with an interactive HTMX-powered tree view
- **CSV import/export** — Import from custom CSV or OpenSALT-compatible formats; export for editing and re-import with UUID-based upsert
- **External CASE import** — Import frameworks directly from OpenSALT or any CASE-compatible server
- **Docker-ready** — Run locally or deploy anywhere with Docker and PostgreSQL

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | Python 3.12, FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| Migration | Alembic |
| Database | PostgreSQL |
| Web UI | Jinja2, HTMX, Tailwind CSS |
| CLI | Click, Rich |
| Package Manager | uv |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/kentalow/compeito.git
cd compeito

# Start with Docker
docker compose up -d

# Run database migrations
docker compose exec app alembic upgrade head
```

For local development without running the app inside Docker (e.g., DB in Docker + app on the host with `uv`), see [docs/dev/local-setup.md](docs/dev/local-setup.md).

## CLI Usage

```bash
# Tenant management
docker compose exec app uv run python cli.py tenant create --name "University A"
docker compose exec app uv run python cli.py tenant list --with-docs

# Import a framework from CSV
docker compose exec app uv run python cli.py import csv --tenant {uuid} --file framework.csv

# Import from an external CASE server (e.g., OpenSALT)
docker compose exec app uv run python cli.py import case-url --tenant {uuid} --url https://opensalt.net/ims/case/v1p0/CFPackages/{id}

# Export for editing
docker compose exec app uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
```

## API Endpoints

All endpoints follow the CASE v1.1 REST/JSON Binding specification.

```
GET /{tenant}/ims/case/v1p1/CFPackages/{id}
GET /{tenant}/ims/case/v1p1/CFDocuments
GET /{tenant}/ims/case/v1p1/CFDocuments/{id}
GET /{tenant}/ims/case/v1p1/CFItems/{id}
GET /{tenant}/ims/case/v1p1/CFItems/{id}/associations
GET /{tenant}/ims/case/v1p1/CFAssociations/{id}
GET /{tenant}/ims/case/v1p1/CFAssociationGroupings
GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id}
GET /{tenant}/ims/case/v1p1/CFConcepts
GET /{tenant}/ims/case/v1p1/CFConcepts/{id}
GET /{tenant}/ims/case/v1p1/CFItemTypes
GET /{tenant}/ims/case/v1p1/CFItemTypes/{id}
GET /{tenant}/ims/case/v1p1/CFLicenses
GET /{tenant}/ims/case/v1p1/CFLicenses/{id}
GET /{tenant}/ims/case/v1p1/CFSubjects
GET /{tenant}/ims/case/v1p1/CFSubjects/{id}
```

Legacy `/ims/case/v1p0/` paths are redirected (301) to `/ims/case/v1p1/`.

## Background

The current de facto CASE implementation is [OpenSALT](https://github.com/opensalt/opensalt) (by PCG Education), but it only supports CASE v1.0. COMPEITO provides a modern CASE v1.1 implementation with the ability to import frameworks from existing OpenSALT instances.

## Roadmap

- **Phase 1** (Done) — Docker development, all CASE v1.1 API endpoints, CSV/CASE import & export, Web UI, CLI, i18n
- **Phase 2** (Done) — OpenSALT CSV export format, CASE v1.0 import support, CFRubric API, CI
- **Phase 3** — Non-tree association management, OAuth 2.0, semantic search, cross-framework mapping

## License

[Apache License 2.0](LICENSE)

## Developed by

[Infosign, Inc.](https://www.infosign.co.jp/) (株式会社インフォザイン)

---

# COMPEITO（日本語）

**Comp**etency **E**xchange & **I**nteroperability **To**ol

[1EdTech CASE v1.1](https://www.imsglobal.org/spec/case/v1p1) 対応のコンピテンシーフレームワーク配信サーバーです。将来的に [Open Badge Factory (OB v3)](https://www.imsglobal.org/spec/ob/v3p0) や [TAO Testing (QTI v3.0)](https://www.imsglobal.org/spec/qti/v3p0) のコンピテンシー参照先として連携することを目指しています。

> "compeito" は日本語の「[金平糖](https://ja.wikipedia.org/wiki/%E9%87%91%E5%B9%B3%E7%B3%96)（こんぺいとう）」にも由来しています。

## 特徴

- **CASE v1.1 対応** — 必須の REST API エンドポイントをすべて実装（CFPackages, CFDocuments, CFItems, CFAssociations 等）
- **マルチテナント** — 1つのインスタンスで複数の組織をホスト。各テナントは独自の UUID 名前空間を持つ
- **ツリービュー UI** — HTMX によるインタラクティブなツリービューでコンピテンシーフレームワークを閲覧
- **CSV インポート/エクスポート** — 独自CSV・OpenSALT互換形式に対応。エクスポートして編集後、UUID ベースの upsert で再インポート可能
- **外部 CASE インポート** — OpenSALT 等の CASE 対応サーバーからフレームワークを直接インポート
- **Docker 対応** — Docker と PostgreSQL でローカル実行、またはどこにでもデプロイ可能

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| API | Python 3.12, FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| マイグレーション | Alembic |
| データベース | PostgreSQL |
| Web UI | Jinja2, HTMX, Tailwind CSS |
| CLI | Click, Rich |
| パッケージマネージャ | uv |

## クイックスタート

```bash
# リポジトリをクローン
git clone https://github.com/kentalow/compeito.git
cd compeito

# Docker で起動
docker compose up -d

# データベースマイグレーションを実行
docker compose exec app alembic upgrade head
```

アプリ自体を Docker の外（ホスト上で `uv` で直接）走らせるハイブリッド構成については [docs/dev/local-setup.md](docs/dev/local-setup.md) を参照してください。

## CLI の使い方

```bash
# テナント管理
docker compose exec app uv run python cli.py tenant create --name "大学A"
docker compose exec app uv run python cli.py tenant list --with-docs

# CSV からフレームワークをインポート
docker compose exec app uv run python cli.py import csv --tenant {uuid} --file framework.csv

# 外部 CASE サーバー（OpenSALT 等）からインポート
docker compose exec app uv run python cli.py import case-url --tenant {uuid} --url https://opensalt.net/ims/case/v1p0/CFPackages/{id}

# 編集用にエクスポート
docker compose exec app uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
```

## API エンドポイント

すべてのエンドポイントは CASE v1.1 REST/JSON Binding 仕様に基づいています。

```
GET /{tenant}/ims/case/v1p1/CFPackages/{id}
GET /{tenant}/ims/case/v1p1/CFDocuments
GET /{tenant}/ims/case/v1p1/CFDocuments/{id}
GET /{tenant}/ims/case/v1p1/CFItems/{id}
GET /{tenant}/ims/case/v1p1/CFItems/{id}/associations
GET /{tenant}/ims/case/v1p1/CFAssociations/{id}
GET /{tenant}/ims/case/v1p1/CFAssociationGroupings
GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id}
GET /{tenant}/ims/case/v1p1/CFConcepts
GET /{tenant}/ims/case/v1p1/CFConcepts/{id}
GET /{tenant}/ims/case/v1p1/CFItemTypes
GET /{tenant}/ims/case/v1p1/CFItemTypes/{id}
GET /{tenant}/ims/case/v1p1/CFLicenses
GET /{tenant}/ims/case/v1p1/CFLicenses/{id}
GET /{tenant}/ims/case/v1p1/CFSubjects
GET /{tenant}/ims/case/v1p1/CFSubjects/{id}
```

レガシーパス `/ims/case/v1p0/` は `/ims/case/v1p1/` にリダイレクト（301）されます。

## 背景

現在の CASE 実装のデファクトスタンダードは [OpenSALT](https://github.com/opensalt/opensalt)（PCG Education 開発）ですが、CASE v1.0 のみ対応しています。COMPEITO は CASE v1.1 のモダンな実装を提供し、既存の OpenSALT インスタンスからのフレームワークインポートにも対応しています。

## ロードマップ

- **Phase 1**（完了）— Docker によるローカル開発、CASE v1.1 API 全エンドポイント、CSV/CASE インポート＆エクスポート、Web UI、CLI、i18n
- **Phase 2**（完了）— OpenSALT CSV エクスポート形式、CASE v1.0 インポート対応、CFRubric API、CI
- **Phase 3** — ツリー外アソシエーション管理、OAuth 2.0、セマンティック検索、フレームワーク間マッピング

## ライセンス

[Apache License 2.0](LICENSE)

## 開発

[株式会社インフォザイン](https://www.infosign.co.jp/) (Infosign, Inc.)
