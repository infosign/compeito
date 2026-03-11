# COMPEITO

**Comp**etency **E**xchange & **I**nteroperability **To**ol

A modern [1EdTech CASE v1.1](https://www.imsglobal.org/spec/case/v1p1) compliant server for publishing competency frameworks via REST API. Designed to work with [Open Badge Factory (OB v3)](https://www.imsglobal.org/spec/ob/v3p0) and [TAO Testing (QTI v3.0)](https://www.imsglobal.org/spec/qti/v3p0) as a competency reference endpoint.

> "compeito" is also the Japanese word for [konpeitō](https://en.wikipedia.org/wiki/Konpeit%C5%8D) (金平糖), a traditional Japanese sugar candy.

## Features

- **CASE v1.1 compliant** — All required REST API endpoints (CFPackages, CFDocuments, CFItems, CFAssociations, and more)
- **Multi-tenant** — Serve multiple organizations from a single instance, each with their own UUID namespace
- **Tree view UI** — Browse competency frameworks with an interactive HTMX-powered tree view
- **CSV import/export** — Import from custom CSV or OpenSALT-compatible formats; export for editing and re-import with UUID-based upsert
- **External CASE import** — Import frameworks directly from OpenSALT or any CASE-compliant server
- **Serverless-ready** — Runs on AWS Lambda + Aurora Serverless v2 via API Gateway and CloudFront, or locally with Docker

## Architecture

```
Public:  CloudFront -> API Gateway -> Lambda (FastAPI + Mangum) -> Aurora Serverless v2
Admin:   CLI -> Lambda Function URL -> Lambda -> Aurora
Local:   Docker (FastAPI + uvicorn) -> PostgreSQL
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | Python 3.12, FastAPI, Mangum |
| ORM | SQLAlchemy 2.x (async) |
| Migration | Alembic |
| Database | PostgreSQL (Aurora Serverless v2 / Docker) |
| Cache | CloudFront (HTTP Cache-Control) |
| Infrastructure | AWS CDK (Python) |
| Web UI | Jinja2, HTMX, Tailwind CSS |
| CLI | Click, Rich |
| Package Manager | uv |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/kentalow/compeito.git
cd compeito

# Start with Docker
docker-compose up -d

# Run database migrations
docker-compose exec app alembic upgrade head
```

## CLI Usage

```bash
# Tenant management
python cli.py tenant create --name "University A"
python cli.py tenant list --with-docs

# Import a framework from CSV
python cli.py import csv --tenant {uuid} --file framework.csv

# Import from an external CASE server (e.g., OpenSALT)
python cli.py import case-url --tenant {uuid} --url https://opensalt.net/ims/case/v1p0/CFPackages/{id}

# Export for editing
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
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

- **Phase 1** — Local development with Docker, all CASE v1.1 API endpoints, CSV/CASE import & export, Web UI, CLI
- **Phase 2** — AWS CDK infrastructure, OpenSALT CSV export format, CASE v1.0 import support, CFRubric API, 1EdTech Conformance
- **Phase 3** — Non-tree association management, OAuth 2.0, semantic search, cross-framework mapping

## License

[Elastic License 2.0 (ELv2)](LICENSE)

## Developed by

[INFOSIGN Inc.](https://www.infosign.co.jp/) (インフォザイン)
