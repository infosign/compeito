# CLI Command Specification

## Runtime environment

The CLI connects directly to PostgreSQL. Specify the connection URL via either of:

1. The `DATABASE_URL` environment variable (the container's `environment` in Docker mode, or `export DATABASE_URL=...` for native execution).
2. A `DATABASE_URL=...` line in the `.env` file at the repository root (auto-loaded by Pydantic Settings).

If neither is set, the CLI exits with code 1. When both are set, the environment variable wins.

## Command reference

```bash
# Tenant management
uv run python cli.py tenant create --name "Company Name" [--private]
uv run python cli.py tenant list
# UUID                                  NAME        VISIBILITY  CREATED
# 550e8400-...                          University A  public      2025-01-01
# 6ba7b810-...                          Company B     private     2025-02-15

uv run python cli.py tenant list --with-docs
# 550e8400-...  University A  public
#   ├─ d86774f2-...  National Curriculum  (1557 items)
#   └─ a3f9c201-...  Engineering Competencies  (42 items)

# Framework (CFDocument) management
uv run python cli.py doc list --tenant {tenant-uuid}
# UUID                                  TITLE                     ITEMS  UPDATED
# d86774f2-...                          National Curriculum       1557   2025-10-08

# Tenant update
# --private / --public are mutually exclusive (combining them is an error).
uv run python cli.py tenant update --tenant {tenant-uuid} --name "New Name"
uv run python cli.py tenant update --tenant {tenant-uuid} --private
uv run python cli.py tenant update --tenant {tenant-uuid} --public

# Delete (confirmation prompt; --force skips it)
uv run python cli.py tenant delete --tenant {tenant-uuid} [--force]
uv run python cli.py doc delete --tenant {tenant-uuid} --doc {doc-uuid} [--force]

# CSV import (new: omit --doc; update: with --doc → upsert)
# --doc-title: CFDocument title. On create, can be omitted if the CSV has a #title row, otherwise required. On update, optional (existing value retained).
# --doc-version: version (optional; on update existing value retained; default is NULL on create).
uv run python cli.py import csv --tenant {uuid} --file framework.csv
uv run python cli.py import csv --tenant {uuid} --file framework.csv --doc-title "Name" --doc-version "1.0"
uv run python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework.csv

# External CASE source import (v1.1 supported; v1.0 Phase 2; upsert)
# --url: CASE API base path or a direct CFPackage URL (see import-logic.md).
uv run python cli.py import case-url --tenant {uuid} --url https://case.example.com/{tenant}/ims/case/v1p1
uv run python cli.py import case-url --tenant {uuid} --doc {doc-uuid} --url https://server/ims/case/v1p1/CFPackages/{uuid}

# Local CFPackage JSON import (no network fetch; same persistence path as case-url)
# Useful when the source CASE server is private / not reachable from this host.
uv run python cli.py import case-file --tenant {uuid} --file framework.json
uv run python cli.py import case-file --tenant {uuid} --doc {doc-uuid} --file framework.json

# Export (custom format with UUIDs; editing + re-importing upserts)
# --file: output path. Overwrites without confirmation if the file exists.
uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv --format opensalt
# --format: "custom" (default) / "opensalt"
#           Invalid → error exit ("Invalid format: '{value}'. Valid values: custom, opensalt")

# CASE CFPackage JSON export (output is byte-for-byte identical to GET /CFPackages/{id})
# Re-importable via `import case-file`, or feed-able to any CASE-conformant editor.
uv run python cli.py export case --tenant {uuid} --doc {doc-uuid} --file output.json

# Rubric CSV import (--doc selects the target document; upsert)
uv run python cli.py import csv-rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

# Rubric CSV export
uv run python cli.py export csv-rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

# DB migration
uv run python cli.py db migrate
```

## Command output

### Create / update / delete

```bash
# tenant create → prints the created tenant
uv run python cli.py tenant create --name "University A"
# Created tenant: 550e8400-... (University A, public)

# tenant update → prints the updated tenant
uv run python cli.py tenant update --tenant {uuid} --name "New Name"
# Updated tenant: 550e8400-... (New Name, public)

# tenant delete → confirmation prompt → success message
uv run python cli.py tenant delete --tenant {uuid}
# Delete tenant 'University A' (550e8400-...)? This will delete all documents and items. [y/N]: y
# Deleted tenant: 550e8400-... (University A)

# doc delete → confirmation prompt → success message
uv run python cli.py doc delete --tenant {uuid} --doc {doc-uuid}
# Delete document 'National Curriculum' (d86774f2-..., 1557 items)? [y/N]: y
# Deleted document: d86774f2-... (National Curriculum)
```

### Delete side effects

- **Tenant delete**: every document, item, association, and lookup resource owned by the tenant is CASCADE-deleted.
- **Document delete**: the document's items and associations are CASCADE-deleted. Lookup resources (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping) are owned by the tenant and survive; records not referenced from any remaining document become orphans inside the tenant (still returned by CASE API listing endpoints). If another document's CFAssociation references items in the deleted document via `originNodeURI` / `destinationNodeURI`, those become dangling references (the association remains, but the referenced `/uri/{uuid}` is 404).

### Delete confirmation prompt

- The prompt describes the operation, the target resource name, UUID, and the impact (see examples above).
- Input: `y` or `yes` (case-insensitive) to proceed; anything else (including just Enter) cancels. The default is No (`[y/N]`).
- With `--force`: no prompt; execute immediately.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (also 0 when warnings were emitted) |
| 1 | Error (validation, connection, file not found, etc.) |
| 2 | User-cancelled (No at the delete confirmation prompt) |

## Common error cases

- `--tenant` value is not a UUID → exit ("Invalid UUID format: '{value}'", code 1)
- `--tenant` UUID does not exist → exit ("Tenant not found: '{uuid}'", code 1)
- `--doc` value is not a UUID → exit ("Invalid UUID format: '{value}'", code 1)
- `--doc` UUID is not found within the specified tenant → exit ("Document not found: '{uuid}'", code 1)
- `--file` path does not exist → exit ("File not found: '{filepath}'", code 1)
- `--file` is not readable (permissions, etc.) → exit ("Cannot read file: '{filepath}'", code 1)
- `--file` output path is not writable (directory missing, permissions) → exit ("Cannot write file: '{filepath}'", code 1)
- CSV import: file is not valid UTF-8 → exit ("CSV file is not valid UTF-8", code 1)
- `tenant update` with none of `--name` / `--private` / `--public` → exit ("At least one of --name, --private, or --public is required", code 1)

## CSV import defaults

- `--doc-title` omitted and no `#title` row in the CSV → on create, exit (required); on update (with `--doc`), keep the existing title.
- `--doc-version` omitted → on create, NULL (or the `#version` value from the CSV if present); on update, keep the existing value.
- `Identifier` blank → auto-generate a UUID v4.

## CSV export output

On success, prints:
```
Exported 1523 items to output.csv
```
The file is written to the path given by `--file`.

---

# CLIコマンド仕様（日本語）

## 実行環境

CLI は PostgreSQL に直接接続する。接続先の URL は以下のいずれかで指定する:

1. `DATABASE_URL` 環境変数（Docker 構成ではコンテナの environment、ネイティブ実行では `export DATABASE_URL=...`）
2. リポジトリ直下の `.env` ファイル内の `DATABASE_URL=...` 行（Pydantic Settings が自動で読み込む）

どちらも指定がない場合はエラー終了する（終了コード 1）。env var と `.env` が両方ある場合は env var が優先される。

## コマンド一覧

```bash
# テナント管理
uv run python cli.py tenant create --name "Company Name" [--private]
uv run python cli.py tenant list
# UUID                                  NAME        VISIBILITY  CREATED
# 550e8400-...                          大学A        public      2025-01-01
# 6ba7b810-...                          企業B        private     2025-02-15

uv run python cli.py tenant list --with-docs
# 550e8400-...  大学A  public
#   ├─ d86774f2-...  高等学校学習指導要領  (1557 items)
#   └─ a3f9c201-...  工学部コンピテンシー  (42 items)

# フレームワーク(CFDocument)管理
uv run python cli.py doc list --tenant {tenant-uuid}
# UUID                                  TITLE                     ITEMS  UPDATED
# d86774f2-...                          高等学校学習指導要領        1557   2025-10-08

# テナント更新
# --private / --public は相互排他（同時指定はエラー終了）
uv run python cli.py tenant update --tenant {tenant-uuid} --name "New Name"
uv run python cli.py tenant update --tenant {tenant-uuid} --private
uv run python cli.py tenant update --tenant {tenant-uuid} --public

# 削除（確認プロンプトあり、--force でスキップ）
uv run python cli.py tenant delete --tenant {tenant-uuid} [--force]
uv run python cli.py doc delete --tenant {tenant-uuid} --doc {doc-uuid} [--force]

# CSVインポート (新規: --doc省略、更新: --doc指定でupsert)
# --doc-title: CFDocumentタイトル。新規作成時はCSVの#title行があれば省略可、なければ必須。更新時は省略可（既存値を保持）
# --doc-version: バージョン（任意、省略時は既存値を保持。新規作成時のデフォルトは NULL）
uv run python cli.py import csv --tenant {uuid} --file framework.csv
uv run python cli.py import csv --tenant {uuid} --file framework.csv --doc-title "名称" --doc-version "1.0"
uv run python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework.csv

# 外部CASEソースインポート (v1.1対応、v1.0はPhase 2、upsert)
# --url: CASE APIベースパス or CFPackage直接URL（詳細は import-logic.md 参照）
uv run python cli.py import case-url --tenant {uuid} --url https://case.example.com/{tenant}/ims/case/v1p1
uv run python cli.py import case-url --tenant {uuid} --doc {doc-uuid} --url https://server/ims/case/v1p1/CFPackages/{uuid}

# ローカル CFPackage JSON ファイルからインポート（ネットワーク取得なし、永続化処理は case-url と同じ）
# 取り込み元 CASE サーバーがプライベートでこのホストから到達できない場合に使う
uv run python cli.py import case-file --tenant {uuid} --file framework.json
uv run python cli.py import case-file --tenant {uuid} --doc {doc-uuid} --file framework.json

# エクスポート (UUID付き独自形式 → 編集後にimportでupsert可能)
# --file: 出力先ファイルパス。既に存在する場合は上書きする（確認なし）
uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv --format opensalt
# --format: "custom"（デフォルト）/ "opensalt"
#           不正な値 → エラー終了（「Invalid format: '{value}'. Valid values: custom, opensalt」）

# CASE CFPackage JSON エクスポート（出力は GET /CFPackages/{id} と同一のバイト列）
# import case-file で再取り込みするか、任意の CASE 準拠エディタへ受け渡せる
uv run python cli.py export case --tenant {uuid} --doc {doc-uuid} --file output.json

# ルーブリックCSVインポート (--doc で対象ドキュメントを指定、upsert)
uv run python cli.py import csv-rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

# ルーブリックCSVエクスポート
uv run python cli.py export csv-rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

# DBマイグレーション
uv run python cli.py db migrate
```

## コマンド出力形式

### 作成・更新・削除の出力

```bash
# tenant create → 作成されたテナント情報を表示
uv run python cli.py tenant create --name "大学A"
# Created tenant: 550e8400-... (大学A, public)

# tenant update → 更新後のテナント情報を表示
uv run python cli.py tenant update --tenant {uuid} --name "New Name"
# Updated tenant: 550e8400-... (New Name, public)

# tenant delete → 削除確認プロンプト → 成功メッセージ
uv run python cli.py tenant delete --tenant {uuid}
# Delete tenant '大学A' (550e8400-...)? This will delete all documents and items. [y/N]: y
# Deleted tenant: 550e8400-... (大学A)

# doc delete → 削除確認プロンプト → 成功メッセージ
uv run python cli.py doc delete --tenant {uuid} --doc {doc-uuid}
# Delete document '高等学校学習指導要領' (d86774f2-..., 1557 items)? [y/N]: y
# Deleted document: d86774f2-... (高等学校学習指導要領)
```

### 削除の副作用

- **テナント削除**: 配下の全ドキュメント・アイテム・Association・lookup リソースが CASCADE 削除される
- **ドキュメント削除**: 配下のアイテム・Association が CASCADE 削除される。lookup リソース（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）はテナント所有のため削除されず、他ドキュメントから参照されないレコードは orphan としてテナント内に残る（CASE API の一覧エンドポイントで引き続き返却される）。他ドキュメントの CFAssociation が削除ドキュメントのアイテムを `originNodeURI` / `destinationNodeURI` で参照している場合、dangling reference となる（Association 自体は残り、参照先の `/uri/{uuid}` は 404 となる）

### 削除確認プロンプト

- プロンプトテキスト: 操作内容・対象リソース名・UUID・影響範囲を表示する（上記例参照）
- 入力: `y` または `yes`（大文字小文字不問）で実行、それ以外（空Enter含む）でキャンセル。デフォルトは No（`[y/N]`）
- `--force` 指定時: プロンプトを表示せず即時実行

## 終了コード

| コード | 意味 |
|--------|------|
| 0 | 正常終了（警告ありの場合も 0） |
| 1 | エラー終了（バリデーションエラー、接続エラー、ファイルが見つからない等） |
| 2 | ユーザーキャンセル（削除確認プロンプトで No を選択） |

## 共通エラーケース

- `--tenant` の値が UUID 形式でない → エラー終了（「Invalid UUID format: '{value}'」、終了コード 1）
- `--tenant` の UUID が存在しない → エラー終了（「Tenant not found: '{uuid}'」、終了コード 1）
- `--doc` の値が UUID 形式でない → エラー終了（「Invalid UUID format: '{value}'」、終了コード 1）
- `--doc` の UUID が指定テナント内に存在しない → エラー終了（「Document not found: '{uuid}'」、終了コード 1）
- `--file` で指定したファイルが存在しない → エラー終了（「File not found: '{filepath}'」、終了コード 1）
- `--file` で指定したファイルが読み取れない（パーミッションエラー等） → エラー終了（「Cannot read file: '{filepath}'」、終了コード 1）
- `--file` で指定した出力先に書き込めない（ディレクトリが存在しない、パーミッションエラー等） → エラー終了（「Cannot write file: '{filepath}'」、終了コード 1）
- CSVインポート時、ファイルが UTF-8 としてデコードできない → エラー終了（「CSV file is not valid UTF-8」、終了コード 1）
- `tenant update` に `--name` / `--private` / `--public` のいずれも指定されていない → エラー終了（「At least one of --name, --private, or --public is required」、終了コード 1）

## CSVインポートのデフォルト動作

- `--doc-title` 省略かつCSVに `#title` 行なし → 新規作成時はエラー終了（必須）、更新時（`--doc` 指定）は既存タイトルを保持
- `--doc-version` 省略 → 新規作成時は NULL（CSVに `#version` 行があればその値を使用）、更新時は既存値を保持
- `Identifier` 空 → UUID v4 を自動採番

## CSVエクスポートの出力

成功時に以下の形式で出力する:
```
Exported 1523 items to output.csv
```
`--file` で指定したパスにファイルを書き出す。
