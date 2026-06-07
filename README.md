# COMPEITO

**Comp**etency **E**xchange & **I**nteroperability **To**ol

A modern [1EdTech CASE v1.1](https://www.imsglobal.org/spec/case/v1p1) compatible server for publishing competency frameworks via REST API. Aiming to serve as a competency reference endpoint for platforms such as [Open Badge Factory (OB v3)](https://www.imsglobal.org/spec/ob/v3p0) and [TAO Testing (QTI v3.0)](https://www.imsglobal.org/spec/qti/v3p0) in the future.

> "compeito" is also the Japanese word for [konpeitō](https://en.wikipedia.org/wiki/Konpeit%C5%8D) (金平糖), a traditional Japanese sugar candy.

## Try it now — [playground.compeito.org](https://playground.compeito.org/)

A live demo with a sample competency framework preloaded. Browse the tree view, hit the CASE v1.1 API directly, or register the URL as a CASE source in Open Badge Factory — no setup required.

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
git clone https://github.com/infosign/compeito.git
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
docker compose exec app uv run python cli.py import case --tenant {uuid} --url https://opensalt.net/ims/case/v1p0/CFPackages/{id}

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

The 1EdTech CASE ecosystem has several active open-source implementations, each addressing a different slice of the workflow:

- **[OpenCASE](https://github.com/1EdTech/OpenCASE)** — the 1EdTech reference implementation. A full platform combining a visual framework editor, Keycloak-based multi-tenant authentication, immutable version history, and a certified publishing server. A good fit for organizations that want a single integrated stack covering editing through publishing.

- **[OpenSALT](https://github.com/opensalt/opensalt)** — the long-standing community implementation (by PCG Education). The latest stable release (3.2.0, September 2023) targets CASE v1.0; v1.1 work is underway on the `develop` branch. A full-featured framework editor with a large existing user base, especially around US K-12 standards.

- **COMPEITO** — a lightweight, distribution-focused server developed in Japan. CASE v1.1 conformance shipping today, with English/Japanese bilingual UI / CLI / docs, custom-and-OpenSALT CSV import paths, and an emphasis on being easy to embed in existing stacks. A good fit when you already have an editor (OpenCASE, OpenSALT, or any CASE-conformant tool) and want a small, focused publishing component — or when you need a Japanese-language deployment of a CASE endpoint.

These projects are designed to **interoperate via the CASE standard**. COMPEITO can import CFPackages published by OpenSALT or OpenCASE, and frameworks published by COMPEITO can be consumed by any CASE-conformant client (e.g., Open Badge Factory). Importing competency frameworks from external CASE sources is a first-class capability.

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

## すぐ試す — [playground.compeito.org](https://playground.compeito.org/)

サンプルのコンピテンシーフレームワークを投入済みの公開デモサイトです。ツリービューでの閲覧、CASE v1.1 API の確認、Open Badge Factory への CASE ソースとしての登録など、セットアップ不要でそのまま試せます。

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
git clone https://github.com/infosign/compeito.git
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
docker compose exec app uv run python cli.py import case --tenant {uuid} --url https://opensalt.net/ims/case/v1p0/CFPackages/{id}

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

1EdTech CASE のエコシステムには複数の OSS 実装が存在し、それぞれワークフローの異なる部分を担っています:

- **[OpenCASE](https://github.com/1EdTech/OpenCASE)** — 1EdTech 公式のリファレンス実装。ビジュアルなフレームワークエディタ、Keycloak ベースのマルチテナント認証、不変なバージョン履歴、認定済み配信サーバーを一体で提供するフルプラットフォームです。編集から配信までを一つのスタックで完結させたい組織に向いています。

- **[OpenSALT](https://github.com/opensalt/opensalt)** — 長年コミュニティで使われてきた実装（PCG Education 開発）。安定リリース 3.2.0 (2023 年 9 月) は CASE v1.0 対応で、v1.1 対応は `develop` ブランチで作業中です。フル機能のエディタで、米国の K-12 標準など大きな既存ユーザーベースを持ちます。

- **COMPEITO** — 日本で開発される軽量・配信特化のサーバーです。CASE v1.1 を正式リリースで提供し、英日両対応の UI / CLI / ドキュメント、独自 CSV と OpenSALT 互換 CSV のインポート、既存スタックへの組み込みやすさを重視しています。既存のエディタ（OpenCASE、OpenSALT、その他 CASE 準拠ツール）と組み合わせて配信を担当させたい場合や、日本語環境に CASE エンドポイントを設けたい場合に向いています。

これらは **CASE 標準を介して相互運用すること** を前提に設計されています。COMPEITO は OpenSALT や OpenCASE が公開する CFPackage を取り込むことができ、また COMPEITO が公開するフレームワークは CASE 準拠の任意のクライアント（例: Open Badge Factory）から参照可能です。外部 CASE ソースからのインポートは中核機能の一つです。

## ロードマップ

- **Phase 1**（完了）— Docker によるローカル開発、CASE v1.1 API 全エンドポイント、CSV/CASE インポート＆エクスポート、Web UI、CLI、i18n
- **Phase 2**（完了）— OpenSALT CSV エクスポート形式、CASE v1.0 インポート対応、CFRubric API、CI
- **Phase 3** — ツリー外アソシエーション管理、OAuth 2.0、セマンティック検索、フレームワーク間マッピング

## ライセンス

[Apache License 2.0](LICENSE)

## 開発

[株式会社インフォザイン](https://www.infosign.co.jp/) (Infosign, Inc.)
