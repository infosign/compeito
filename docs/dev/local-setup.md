# Local Development Setup

Two supported setups. Keep all tests passing on both.

## 1. Hybrid (recommended): DB in Docker, app on the host

The editor (and Claude Code) sees source files directly; `uv run pytest` runs fast. This is the recommended day-to-day setup.

### Requirements

- Docker Desktop (for the PostgreSQL container)
- [`uv`](https://docs.astral.sh/uv/) — `brew install uv` on macOS / Linuxbrew
- Python 3.12 is fetched automatically by `uv sync`

### Initial setup

```bash
# 1. Resolve dependencies and create the venv (Python 3.12 included)
uv sync

# 2. Prepare the env file (points DATABASE_URL at localhost)
cp .env.example .env

# 3. Start PostgreSQL via Docker
docker compose up -d db

# 4. Apply migrations
uv run alembic upgrade head
```

### Day-to-day commands

```bash
uv run pytest                                       # tests
uv run pytest tests/unit/test_xxx.py -v             # focused
uv run uvicorn src.main:app --reload                # dev server
uv run case-cli tenant list                         # CLI
uv run alembic upgrade head                         # migrations
uv run ruff check src/ tests/ cli.py                # lint
uv run ruff format src/ tests/ cli.py               # format
```

### The role of `.env`

`Settings` in `src/config.py` reads `.env` via `pydantic-settings`'s `env_file=".env"` option. Real environment variables (e.g., those provided by `docker compose`) take precedence over `.env`, so when running inside Docker `.env` is effectively ignored. `.env` is gitignored — feel free to edit it for your local setup.

## 2. Full Docker

For when you want a setup closer to production, or you don't want to install anything on the host.

```bash
docker compose up -d                                  # db + app
docker compose exec app uv run alembic upgrade head   # migrations
docker compose exec app uv run pytest                 # tests
```

The `app` service in `docker-compose.yml` receives `DATABASE_URL=postgresql+asyncpg://case:case@db:5432/case` (using the internal service name `db`) via `environment`. `.env` is ignored.

## Notes

- **PostgreSQL version**: 15. SQLite is not used because of async driver differences.
- **Test DB**: `conftest.py` `DELETE`s all tables after each test for rollback-like behavior.
- **CI**: GitHub Actions starts the DB with `docker compose up -d db` before running `uv run pytest`. The same sequence runs locally.
- **`LANG`**: the CLI switches its display language based on `LANG`. Tests assume English output, so an autouse fixture in `tests/unit/test_cli.py` forces `LANG=C`.

---

# ローカル開発セットアップ（日本語）

開発スタイルは 2 通り。どちらでも 全テスト pass する状態を維持する。

## 1. ハイブリッド（推奨）: DB だけ Docker、アプリはネイティブ

エディタや Claude Code から直接ファイルが見え、`uv run pytest` 等が高速に動く。日常開発はこちら推奨。

### 必要なもの

- Docker Desktop（PostgreSQL コンテナ用）
- [`uv`](https://docs.astral.sh/uv/) — Homebrew なら `brew install uv`
- Python 3.12 は `uv sync` 実行時に自動取得される

### 初回セットアップ

```bash
# 1. 依存解決と venv 作成（Python 3.12 含む）
uv sync

# 2. 環境変数ファイルを用意（DATABASE_URL を localhost に向ける）
cp .env.example .env

# 3. PostgreSQL を Docker で起動
docker compose up -d db

# 4. マイグレーションを当てる
uv run alembic upgrade head
```

### 日常コマンド

```bash
uv run pytest                                       # テスト実行
uv run pytest tests/unit/test_xxx.py -v             # 個別テスト
uv run uvicorn src.main:app --reload                # 開発サーバー
uv run case-cli tenant list                         # CLI
uv run alembic upgrade head                         # マイグレーション
uv run ruff check src/ tests/ cli.py                # lint
uv run ruff format src/ tests/ cli.py               # format
```

### `.env` の役割

`src/config.py` の `Settings` は `pydantic-settings` の `env_file=".env"` 機能で `.env` を読み込む。実環境変数（`docker compose` の `environment` など）は `.env` より優先されるため、Docker 実行時は `.env` の値が無視される。`.env` は `.gitignore` 済みで、各自のローカル設定に応じて編集してよい。

## 2. 全部 Docker

ローカル環境を汚さない・本番に近い構成で動かしたい場合。

```bash
docker compose up -d                                  # db + app
docker compose exec app uv run alembic upgrade head   # マイグレーション
docker compose exec app uv run pytest                 # テスト
```

`docker-compose.yml` の `app` サービスは `DATABASE_URL=postgresql+asyncpg://case:case@db:5432/case`（Docker 内部のサービス名 `db`）を環境変数で渡す。`.env` は無視される。

## 補足

- **PostgreSQL のバージョン**: 15。SQLite は async ドライバの差異があるため使わない
- **テスト DB**: `conftest.py` がテストごとに全テーブルを `DELETE` してロールバック相当の挙動を実現
- **CI**: GitHub Actions で `docker compose up -d db` してから `uv run pytest` を実行する（同じ手順がローカルでも再現できる）
- **`LANG` 環境変数**: CLI は `LANG` を見て表示言語を切り替える。テストは英語前提のため `tests/unit/test_cli.py` の autouse fixture で `LANG=C` を強制している
