# Contributing to COMPEITO

Thanks for your interest in contributing! This document covers how to set up a development environment, the workflow we follow, and what to expect when you open an issue or pull request.

By participating in this project, you agree to abide by our [Code of Conduct](./CODE_OF_CONDUCT.md).

## Quick links

| Topic | Where |
|-------|-------|
| Local dev setup (Docker only / hybrid) | [docs/dev/local-setup.md](docs/dev/local-setup.md) |
| Commit message / PR / release note style | [docs/dev/conventions.md](docs/dev/conventions.md) |
| Architecture, API spec, DB schema, etc. | [docs/](docs/) |
| Security disclosures | [SECURITY.md](./SECURITY.md) |

## Development setup (TL;DR)

```bash
git clone https://github.com/infosign/compeito.git
cd compeito
brew install uv                 # macOS / Linuxbrew. See uv docs for other platforms.
uv sync
cp .env.example .env
docker compose up -d db
uv run alembic upgrade head
uv run pytest                   # 452 tests should pass
```

The fully-Docker workflow (`docker compose up -d` + `docker compose exec app ...`) also works. See [docs/dev/local-setup.md](docs/dev/local-setup.md) for both.

## Reporting bugs / requesting features

- Open a GitHub Issue using the templates under `.github/ISSUE_TEMPLATE/`.
- For security vulnerabilities, do NOT open a public issue. Follow [SECURITY.md](./SECURITY.md).

## Submitting a pull request

1. Fork the repository (or create a branch if you have write access).
2. Create a topic branch off `main`. Branch names follow `<type>/<short-description>` (e.g., `fix/csv-import-bom`).
3. Write code + tests. New behavior should ship with tests.
4. Run the checks locally before pushing:
   ```bash
   uv run pytest
   uv run ruff check src/ tests/ cli.py
   uv run ruff format --check src/ tests/ cli.py
   ```
5. Commit messages and PR titles follow [docs/dev/conventions.md](docs/dev/conventions.md) — prefixes like `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`, etc., with a concise summary in Japanese or English.
6. Open a PR against `main`. Fill in the PR template (Summary + Test plan).
7. Wait for CI (`lint` + `test`) to pass.
8. A maintainer will review. We may suggest changes; please push additional commits to the branch (we squash on merge).

## Coding style

- **Python**: 3.12, formatted by `ruff format`, linted by `ruff check` (config in `pyproject.toml`).
- **Layered architecture**: router → service → repository. DB access stays inside `src/repositories/`.
- **Async everywhere**: all DB I/O uses `async`/`await` with SQLAlchemy's async session.
- **Schemas**: CASE v1.1 schemas use camelCase field names (per spec). Internal Python identifiers use snake_case.

See [CLAUDE.md](./CLAUDE.md) for the full house style.

---

# COMPEITO への貢献ガイド（日本語）

COMPEITO への貢献を検討いただきありがとうございます。本ドキュメントは開発環境のセットアップ、ワークフロー、Issue / PR を出すときの流れをまとめたものです。

本プロジェクトへの参加にあたっては [行動規範](./CODE_OF_CONDUCT.md) を遵守ください。

## クイックリンク

| トピック | 参照先 |
|---------|--------|
| ローカル開発セットアップ（全 Docker / ハイブリッド） | [docs/dev/local-setup.md](docs/dev/local-setup.md) |
| コミットメッセージ・PR・リリースノートの書き方 | [docs/dev/conventions.md](docs/dev/conventions.md) |
| アーキテクチャ、API 仕様、DB スキーマ等 | [docs/](docs/) |
| セキュリティ脆弱性の報告 | [SECURITY.md](./SECURITY.md) |

## 開発環境セットアップ（最短手順）

```bash
git clone https://github.com/infosign/compeito.git
cd compeito
brew install uv                 # macOS / Linuxbrew の場合。他環境は uv のドキュメント参照
uv sync
cp .env.example .env
docker compose up -d db
uv run alembic upgrade head
uv run pytest                   # 452 件 pass する想定
```

全 Docker 構成（`docker compose up -d` + `docker compose exec app ...`）でも動きます。詳細は [docs/dev/local-setup.md](docs/dev/local-setup.md) を参照。

## バグ報告 / 機能要望

- GitHub Issue を `.github/ISSUE_TEMPLATE/` のテンプレートに沿って作成してください。
- セキュリティ脆弱性は公開 Issue で報告しないでください。[SECURITY.md](./SECURITY.md) の手順に従ってください。

## プルリクエストの送り方

1. リポジトリを fork する（write 権限がある場合はブランチ作成）。
2. `main` から topic ブランチを切る。ブランチ名は `<type>/<短い説明>`（例: `fix/csv-import-bom`）。
3. コードとテストを追加する。新しい挙動には必ずテストを付ける。
4. push する前にローカルでチェック:
   ```bash
   uv run pytest
   uv run ruff check src/ tests/ cli.py
   uv run ruff format --check src/ tests/ cli.py
   ```
5. コミットメッセージと PR タイトルは [docs/dev/conventions.md](docs/dev/conventions.md) に従う（`feat:` / `fix:` / `docs:` / `chore:` / `test:` / `refactor:` 等のプレフィックス＋日本語または英語の簡潔な要約）。
6. `main` 向けに PR を作成。PR テンプレート（Summary + Test plan）を埋める。
7. CI（`lint` + `test`）の通過を待つ。
8. メンテナがレビューします。修正提案があれば追加コミットを push してください（マージ時に squash します）。

## コーディングスタイル

- **Python**: 3.12、`ruff format` で整形、`ruff check` で lint（設定は `pyproject.toml`）。
- **レイヤード構成**: router → service → repository。DB アクセスは `src/repositories/` 配下に集約。
- **非同期で統一**: DB I/O はすべて SQLAlchemy async session を用いた `async`/`await`。
- **スキーマ**: CASE v1.1 のスキーマフィールドはキャメルケース（仕様準拠）、Python 内部識別子はスネークケース。

詳細は [CLAUDE.md](./CLAUDE.md) を参照。
