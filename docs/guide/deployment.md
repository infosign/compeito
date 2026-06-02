# Production Deployment Guide

How to run COMPEITO on a Linux server with Docker and expose it to the internet.

## Prerequisites

- A Linux server (e.g., Ubuntu 22.04 / 24.04)
- Docker Engine + Docker Compose installed
- A registered domain name (e.g., `compeito.example.com`)
- A DNS A record pointing to the server's IP address

## 1. Create the production `docker-compose.yml`

Base it on the dev `docker-compose.yml` and adjust for production:

```yaml
# docker-compose.prod.yml
services:
  db:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: case
      POSTGRES_PASSWORD: <change to a strong password>
      POSTGRES_DB: case
    # Do NOT publish the port (accessed only from the app container)
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U case"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build: .
    restart: always
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://case:<same password as above>@db:5432/case
      BASE_URL: https://compeito.example.com
    depends_on:
      db:
        condition: service_healthy
    # In production: no --reload, no source mount

volumes:
  pgdata:
```

### Key differences from dev

| Item | Dev | Production |
|------|-----|------------|
| `POSTGRES_PASSWORD` | `case` | a strong password |
| `BASE_URL` | `http://localhost:8000` | `https://compeito.example.com` |
| DB port | `5432:5432` (exposed to host) | not exposed |
| Source mount | `- .:/app` | none (uses the image's baked-in code) |
| `--reload` | yes | no |
| `restart` | none | `always` |

## 2. Configure BASE_URL

`BASE_URL` is used to generate the CASE API resource URIs (`identifier` and `uri` fields).

```
# With BASE_URL=https://compeito.example.com
{
  "uri": "https://compeito.example.com/{tenant}/ims/case/v1p1/CFPackages/{id}",
  ...
}
```

**Always set this to your public hostname.** Leaving it at `http://localhost:8000` makes resources unreachable from external systems (e.g., Open Badge Factory).

## 3. Set up a reverse proxy (Nginx)

In production, put Nginx in front to terminate HTTPS and serve static files.

### Install Nginx (Ubuntu)

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Nginx config

```nginx
# /etc/nginx/sites-available/compeito
server {
    listen 80;
    server_name compeito.example.com;

    # certbot will automatically add HTTPS redirect
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/compeito /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Obtain an SSL certificate (Let's Encrypt)

```bash
sudo certbot --nginx -d compeito.example.com
```

certbot updates the Nginx config to enable HTTPS redirect and auto-renewal.

## 4. Start the stack and run initial setup

```bash
# Start
docker compose -f docker-compose.prod.yml up -d

# Migrate
docker compose -f docker-compose.prod.yml exec app alembic upgrade head

# Create a tenant
docker compose -f docker-compose.prod.yml exec app uv run python cli.py tenant create --name "University A"
```

## 5. Data persistence

### Docker volumes

PostgreSQL data is persisted in a Docker **named volume** (`pgdata`).

```bash
# Inspect the volume
docker volume ls | grep pgdata
```

- `docker compose down` → **data persists** (only containers are removed)
- `docker compose down -v` → **data is deleted** (`-v` also removes volumes)
- Server reboot → auto-restart via `restart: always`, **data persists**

**Caution:** `docker compose down -v` is for dev resets. **Never use `-v` in production.**

## 6. Database backups

### Manual backup

```bash
# Take a SQL dump
docker compose -f docker-compose.prod.yml exec db pg_dump -U case case > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore (if needed)
docker compose -f docker-compose.prod.yml exec -T db psql -U case case < backup_20260312_120000.sql
```

### Automated backup (cron)

Daily 3 AM backup retained for 30 days:

```bash
# /etc/cron.d/compeito-backup
0 3 * * * root cd /path/to/compeito && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U case case | gzip > /var/backups/compeito/backup_$(date +\%Y\%m\%d).sql.gz && find /var/backups/compeito -name "*.sql.gz" -mtime +30 -delete
```

```bash
# Create the backup directory
sudo mkdir -p /var/backups/compeito
```

## 7. Logs

### Application logs

uvicorn's access and error logs are emitted via the Docker log driver.

```bash
# Tail in real time
docker compose -f docker-compose.prod.yml logs -f app

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail 100 app

# DB logs
docker compose -f docker-compose.prod.yml logs -f db
```

### Log rotation

Docker's default `json-file` driver grows unbounded. Cap it in production:

```yaml
# Add to each service in docker-compose.prod.yml
services:
  app:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
  db:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```

### Nginx logs

```bash
# Access log
sudo tail -f /var/log/nginx/access.log

# Error log
sudo tail -f /var/log/nginx/error.log
```

Nginx log rotation is configured automatically by `logrotate` (Ubuntu default).

## 8. Updates

```bash
cd /path/to/compeito

# Pull the latest code
git pull

# Rebuild the image and restart
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations if any
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

## 9. Server migration (with hostname change)

Restoring a backup carries the data over. If the public hostname changes, you must bulk-replace URIs stored in the DB.

### Procedure

```bash
# 1. Start and migrate on the new server
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec app alembic upgrade head

# 2. Restore the backup
docker compose -f docker-compose.prod.yml exec -T db psql -U case case < backup.sql

# 3. Bulk-replace URIs in the DB
docker compose -f docker-compose.prod.yml exec db psql -U case case
```

```sql
-- Replace old hostname with new hostname
-- uri columns in every table
UPDATE cf_documents SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_items SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_associations SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_item_types SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_subjects SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_concepts SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_licenses SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_association_groupings SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_rubrics SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_rubric_criteria SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_rubric_criterion_levels SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');

-- Reference URIs in cf_associations
UPDATE cf_associations SET origin_node_uri = REPLACE(origin_node_uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_associations SET destination_node_uri = REPLACE(destination_node_uri, 'https://old.example.com', 'https://new.example.com');
```

### Caution: external URIs

Data imported via `import case-url` retains the original server's URIs (e.g., `https://opensalt.net/uri/...`). REPLACE only your **own** old hostname. The SQL above does that explicitly, so external URIs are unaffected.

### When the hostname does not change

If only the server IP changes, restoring the backup is enough.

## 10. Security checklist

- [ ] Changed `POSTGRES_PASSWORD` from the default (`case`)
- [ ] Did NOT expose the DB port (5432) to the host
- [ ] Set `BASE_URL` to the public hostname (HTTPS)
- [ ] Configured HTTPS via Nginx (e.g., Let's Encrypt)
- [ ] Closed unnecessary firewall ports (everything except 80/443)
- [ ] Set up a cron job for DB backups
- [ ] Configured Docker log rotation

---

# 本番デプロイガイド（日本語）

Linux マシンで COMPEITO を Docker で動かし、インターネットに公開するための手順と運用方法。

## 前提条件

- Linux サーバー（Ubuntu 22.04/24.04 等）
- Docker Engine + Docker Compose がインストール済み
- ドメイン名を取得済み（例: `compeito.example.com`）
- DNS の A レコードがサーバーの IP アドレスに設定済み

## 1. 本番用 docker-compose.yml の作成

開発用の `docker-compose.yml` をベースに、本番用の設定ファイルを作成する。

```yaml
# docker-compose.prod.yml
services:
  db:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: case
      POSTGRES_PASSWORD: <強力なパスワードに変更>
      POSTGRES_DB: case
    # ports は公開しない（app コンテナからのみアクセス）
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U case"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build: .
    restart: always
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://case:<上と同じパスワード>@db:5432/case
      BASE_URL: https://compeito.example.com
    depends_on:
      db:
        condition: service_healthy
    # 本番では --reload なし、ソースのマウントなし

volumes:
  pgdata:
```

### 開発版との主な違い

| 項目 | 開発版 | 本番版 |
|------|--------|--------|
| `POSTGRES_PASSWORD` | `case` | 強力なパスワード |
| `BASE_URL` | `http://localhost:8000` | `https://compeito.example.com` |
| DB ポート | `5432:5432`（ホストに公開） | 公開しない |
| ソースマウント | `- .:/app` | なし（イメージに含むコードを使用） |
| `--reload` | あり | なし |
| `restart` | なし | `always` |

## 2. BASE_URL の設定

`BASE_URL` は CASE API のリソース URI（`identifier` や `uri` フィールド）の生成に使われる。

```
# 例: BASE_URL=https://compeito.example.com の場合
{
  "uri": "https://compeito.example.com/{tenant}/ims/case/v1p1/CFPackages/{id}",
  ...
}
```

**必ず公開ホスト名に変更すること。** `http://localhost:8000` のままだと、API を利用する外部システム（Open Badge Factory 等）がリソースにアクセスできない。

## 3. リバースプロキシ（Nginx）の設定

本番環境では Nginx をリバースプロキシとして前段に置き、HTTPS の終端と静的ファイルの配信を行う。

### Nginx のインストール（Ubuntu）

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Nginx 設定ファイル

```nginx
# /etc/nginx/sites-available/compeito
server {
    listen 80;
    server_name compeito.example.com;

    # certbot が自動的に HTTPS リダイレクトを追加する
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/compeito /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL 証明書の取得（Let's Encrypt）

```bash
sudo certbot --nginx -d compeito.example.com
```

certbot が Nginx 設定を自動更新し、HTTPS リダイレクトと証明書の自動更新を設定する。

## 4. 起動と初期セットアップ

```bash
# 起動
docker compose -f docker-compose.prod.yml up -d

# マイグレーション
docker compose -f docker-compose.prod.yml exec app alembic upgrade head

# テナント作成
docker compose -f docker-compose.prod.yml exec app uv run python cli.py tenant create --name "大学A"
```

## 5. データの永続性

### Docker ボリューム

PostgreSQL のデータは Docker の **名前付きボリューム** (`pgdata`) に保存される。

```bash
# ボリュームの確認
docker volume ls | grep pgdata
```

- `docker compose down` → **データは残る**（コンテナのみ削除）
- `docker compose down -v` → **データも削除される**（`-v` はボリュームも削除する）
- サーバー再起動 → `restart: always` により自動起動、**データは残る**

**注意:** `docker compose down -v` は開発時のリセット用。本番では絶対に `-v` を付けないこと。

## 6. データベースのバックアップ

### 手動バックアップ

```bash
# SQL ダンプを取得
docker compose -f docker-compose.prod.yml exec db pg_dump -U case case > backup_$(date +%Y%m%d_%H%M%S).sql

# リストア（必要な場合）
docker compose -f docker-compose.prod.yml exec -T db psql -U case case < backup_20260312_120000.sql
```

### 自動バックアップ（cron）

毎日 3:00 にバックアップを取り、30日分保持する例:

```bash
# /etc/cron.d/compeito-backup
0 3 * * * root cd /path/to/compeito && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U case case | gzip > /var/backups/compeito/backup_$(date +\%Y\%m\%d).sql.gz && find /var/backups/compeito -name "*.sql.gz" -mtime +30 -delete
```

```bash
# バックアップディレクトリを作成
sudo mkdir -p /var/backups/compeito
```

## 7. ログ

### アプリケーションログ

uvicorn のアクセスログとエラーログは Docker のログドライバ経由で出力される。

```bash
# リアルタイムで確認
docker compose -f docker-compose.prod.yml logs -f app

# 直近100行
docker compose -f docker-compose.prod.yml logs --tail 100 app

# DB のログ
docker compose -f docker-compose.prod.yml logs -f db
```

### ログローテーション

Docker のデフォルトでは `json-file` ログドライバが使われ、ログが無制限に増加する。本番ではサイズ制限を設定する:

```yaml
# docker-compose.prod.yml の各サービスに追加
services:
  app:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
  db:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```

### Nginx のログ

```bash
# アクセスログ
sudo tail -f /var/log/nginx/access.log

# エラーログ
sudo tail -f /var/log/nginx/error.log
```

Nginx のログローテーションは `logrotate` により自動設定される（Ubuntu のデフォルト）。

## 8. アップデート

```bash
cd /path/to/compeito

# 最新のコードを取得
git pull

# イメージを再ビルドして再起動
docker compose -f docker-compose.prod.yml up -d --build

# マイグレーションがあれば実行
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

## 9. サーバー引越し（ホスト名変更あり）

バックアップをリストアすればデータはそのまま引き継げる。ただし、公開ホスト名が変わる場合は DB 内の URI を一括置換する必要がある。

### 手順

```bash
# 1. 新サーバーで起動・マイグレーション
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec app alembic upgrade head

# 2. バックアップをリストア
docker compose -f docker-compose.prod.yml exec -T db psql -U case case < backup.sql

# 3. DB 内の URI を一括置換
docker compose -f docker-compose.prod.yml exec db psql -U case case
```

```sql
-- 旧ホスト名 → 新ホスト名に置換
-- 全テーブルの uri カラム
UPDATE cf_documents SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_items SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_associations SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_item_types SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_subjects SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_concepts SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_licenses SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_association_groupings SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_rubrics SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_rubric_criteria SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_rubric_criterion_levels SET uri = REPLACE(uri, 'https://old.example.com', 'https://new.example.com');

-- cf_associations の参照 URI
UPDATE cf_associations SET origin_node_uri = REPLACE(origin_node_uri, 'https://old.example.com', 'https://new.example.com');
UPDATE cf_associations SET destination_node_uri = REPLACE(destination_node_uri, 'https://old.example.com', 'https://new.example.com');
```

### 注意: 外部サーバーの URI

CASE API インポート（`import case-url`）で取り込んだデータには、元のサーバーの URI（例: `https://opensalt.net/uri/...`）がそのまま保存されている。REPLACE の対象は自サーバーの旧ホスト名のみにすること。上記の SQL は旧ホスト名を明示的に指定しているので、外部 URI に影響はない。

### ホスト名が変わらない場合

サーバーの IP だけ変わる場合は、バックアップのリストアのみで完了する。

## 10. セキュリティチェックリスト

- [ ] `POSTGRES_PASSWORD` をデフォルト (`case`) から変更した
- [ ] DB ポート (5432) をホストに公開していない
- [ ] `BASE_URL` を公開ホスト名 (HTTPS) に設定した
- [ ] Nginx で HTTPS を設定した（Let's Encrypt 等）
- [ ] ファイアウォールで 80/443 以外の不要なポートを閉じた
- [ ] DB バックアップの cron を設定した
- [ ] Docker のログローテーションを設定した
