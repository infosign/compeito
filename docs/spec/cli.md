# CLI Command Specification

## Runtime environment

The CLI connects directly to PostgreSQL. Specify the connection URL via either of:

1. The `DATABASE_URL` environment variable (the container's `environment` in Docker mode, or `export DATABASE_URL=...` for native execution).
2. A `DATABASE_URL=...` line in the `.env` file at the repository root (auto-loaded by Pydantic Settings).

If neither is set, the CLI exits with code 1. When both are set, the environment variable wins.

## Command reference

```bash
# Tenant management
uv run python cli.py tenant create --name "Company Name" [--private] [--id {uuid}] [--slug {slug}]
# --id   pins the UUID (useful for seed scripts re-creating the same tenant);
#        omit to auto-generate a UUID v4.
# --slug pins a URL-friendly alias used in public URLs alongside the UUID.
#        See "Tenant slug rules" below. Example: --slug ikenohata-u
uv run python cli.py tenant list
# UUID                                  SLUG          NAME          VISIBILITY  CREATED
# 550e8400-...                          ikenohata-u   池之端大学     public      2025-01-01
# 6ba7b810-...                          (—)           Company B     private     2025-02-15

uv run python cli.py tenant list --with-docs
# 550e8400-...  ikenohata-u  池之端大学  public
#   ├─ d86774f2-...  National Curriculum  (1557 items)
#   └─ a3f9c201-...  Engineering Competencies  (42 items)

# Framework (CFDocument) management
# --tenant takes the tenant UUID (the slug is a Web-UI convenience, not a CLI resolver key).
uv run python cli.py doc list --tenant {tenant-uuid}
# UUID                                  TITLE                     ITEMS  UPDATED
# d86774f2-...                          National Curriculum       1557   2025-10-08

# Tenant update
# --private / --public are mutually exclusive (combining them is an error).
# --slug / --clear-slug are mutually exclusive.
# --display-order / --clear-order are mutually exclusive.
uv run python cli.py tenant update --tenant {tenant-uuid} --name "New Name"
uv run python cli.py tenant update --tenant {tenant-uuid} --private
uv run python cli.py tenant update --tenant {tenant-uuid} --public
uv run python cli.py tenant update --tenant {tenant-uuid} --slug ikenohata-u
uv run python cli.py tenant update --tenant {tenant-uuid} --clear-slug
# Manual list order: smaller = higher; NULL (default / --clear-order) sorts last (then alphabetical).
uv run python cli.py tenant update --tenant {tenant-uuid} --display-order 10
uv run python cli.py tenant update --tenant {tenant-uuid} --clear-order

# Document update (display order only; --display-order / --clear-order mutually exclusive)
uv run python cli.py doc update --tenant {tenant-uuid} --doc {doc-uuid} --display-order 10
uv run python cli.py doc update --tenant {tenant-uuid} --doc {doc-uuid} --clear-order

# Delete (confirmation prompt; --force skips it)
uv run python cli.py tenant delete --tenant {tenant-uuid} [--force]
uv run python cli.py doc delete --tenant {tenant-uuid} --doc {doc-uuid} [--force]

# CSV import (new: omit --doc; update: with --doc → upsert)
# --doc-title: CFDocument title. On create, can be omitted if the CSV has a #title row, otherwise required. On update, optional (existing value retained).
# --doc-version: version (optional; on update existing value retained; default is NULL on create).
# --profile: format override. auto (default) auto-detects custom / opensalt / simple.
#            When set explicitly, the content must match that profile or it errors
#            (no silent fallback). Values: auto / custom / opensalt / simple.
uv run python cli.py import csv --tenant {uuid} --file framework.csv
uv run python cli.py import csv --tenant {uuid} --file framework.csv --doc-title "Name" --doc-version "1.0"
uv run python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework.csv
uv run python cli.py import csv --tenant {uuid} --file framework.csv --profile opensalt

# OpenSALT Excel (.xlsx) import — the full-fidelity OpenSALT interchange format
# (3 sheets: CF Doc / CF Item / CF Association). Hierarchy is carried by
# smartLevel; CFItemType / educationLevel are preserved (unlike OpenSALT's CSV).
# Verified against a running OpenSALT (round-trips items, hierarchy, item types).
uv run python cli.py import xlsx --tenant {uuid} --file framework.xlsx
uv run python cli.py import xlsx --tenant {uuid} --doc {doc-uuid} --file framework.xlsx

# External CASE import (v1.1 supported; v1.0 Phase 2; upsert).
# Exactly one of --url / --file must be given.
# --url:  CASE API base path or a direct CFPackage URL (see import-logic.md).
# --file: a local CFPackage JSON file (no network fetch; same persistence path).
#         Useful when the source CASE server is private / not reachable from this host.
uv run python cli.py import case --tenant {uuid} --url https://case.example.com/{tenant}/ims/case/v1p1
uv run python cli.py import case --tenant {uuid} --doc {doc-uuid} --url https://server/ims/case/v1p1/CFPackages/{uuid}
uv run python cli.py import case --tenant {uuid} --file framework.json
uv run python cli.py import case --tenant {uuid} --doc {doc-uuid} --file framework.json

# Export (custom format with UUIDs; editing + re-importing upserts)
# --file: output path. Overwrites without confirmation if the file exists.
uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv --profile opensalt
# --profile: "custom" (default) / "opensalt"
#            Invalid → error exit ("Invalid profile: '{value}'. Valid values: custom, opensalt")

# OpenSALT Excel (.xlsx) export — 3-sheet workbook consumable by OpenSALT's
# Excel importer. smartLevel encodes the hierarchy; CFItemType / educationLevel
# are included. isChildOf is NOT repeated in the CF Association sheet.
uv run python cli.py export xlsx --tenant {uuid} --doc {doc-uuid} --file output.xlsx

# CASE CFPackage JSON export (same payload as GET /CFPackages/{id}; the CLI pretty-prints with indent, the API serves compact JSON)
# Re-importable via `import case --file`, or feed-able to any CASE-conformant editor.
uv run python cli.py export case --tenant {uuid} --doc {doc-uuid} --file output.json

# Rubric CSV import (--doc selects the target document; upsert)
uv run python cli.py import rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

# Rubric CSV export
uv run python cli.py export rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

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
- `--file` path does not exist → for `import csv` / `export *`, exit ("File not found: '{filepath}'", code 1). For `import case` / `import xlsx` / `import rubric` (which use Click's `Path(exists=True)`), Click rejects it with a usage error (code 2) before the command runs.
- `--file` is not readable (permissions, etc.) → exit ("Cannot read file: '{filepath}'", code 1)
- `--file` output path is not writable (directory missing, permissions) → exit ("Cannot write file: '{filepath}'", code 1)
- CSV import: file is not valid UTF-8 → exit ("CSV file is not valid UTF-8", code 1)
- `tenant update` with none of `--name` / `--private` / `--public` / `--slug` / `--clear-slug` / `--display-order` / `--clear-order` → exit ("At least one of --name, --private, --public, --slug, --clear-slug, --display-order, or --clear-order is required", code 1)

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

## Tenant slug rules

`--slug` provides a URL-friendly alias for the tenant UUID. The UUID remains the canonical identifier — CASE API responses (`LinkURIDType.identifier` / `uri`) always carry the UUID, so client systems that store these references (e.g., Open Badge Factory) keep working when a slug is added, renamed, or removed. The slug is a Web UI / share-link convenience only.

Validation (enforced both by the CLI and by a DB CHECK constraint):

| Rule | Detail |
|------|--------|
| Length | 2–64 characters |
| Allowed characters | Lowercase ASCII letters `a-z`, digits `0-9`, hyphen `-` |
| First / last character | Must be alphanumeric (no leading / trailing hyphen) |
| Must NOT look like a UUID | Strings that parse as a UUID v4 are rejected (would shadow the canonical UUID URL path) |
| Reserved tokens | `health`, `static`, `admin`, `api`, `assets`, `favicon.ico`, `robots.txt`, `_` are rejected (they collide with top-level routes) |
| Uniqueness | Slugs are unique per deployment |

Examples:

- Valid: `ikenohata-u`, `acme`, `osaka-univ-2025`
- Invalid: `-foo` / `foo-` (leading/trailing hyphen), `Foo` (uppercase), `health` (reserved), `550e8400-e29b-41d4-a716-446655440000` (UUID), `a` (too short)

Errors:

- `--slug` value violates a rule → exit ("Slug '{value}' is invalid: ...", code 1)
- `--slug` value is already in use → exit ("Tenant slug '{value}' is already in use", code 1)
- `tenant update` with both `--slug` and `--clear-slug` → exit ("--slug and --clear-slug are mutually exclusive", code 1)

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
uv run python cli.py tenant create --name "Company Name" [--private] [--id {uuid}] [--slug {slug}]
# --id   を指定すると UUID を固定できる（seed スクリプトで再作成時にもテナント URL を保ちたい用途）。
#        省略時は UUID v4 を自動採番。
# --slug を指定すると公開 URL で UUID の代わりに使える短い別名を設定できる。
#        指定可能な文字は下記「テナント slug の制約」を参照。例: --slug ikenohata-u
uv run python cli.py tenant list
# UUID                                  SLUG          NAME          VISIBILITY  CREATED
# 550e8400-...                          ikenohata-u   池之端大学     public      2025-01-01
# 6ba7b810-...                          (—)           企業B          private     2025-02-15

uv run python cli.py tenant list --with-docs
# 550e8400-...  ikenohata-u  池之端大学  public
#   ├─ d86774f2-...  高等学校学習指導要領  (1557 items)
#   └─ a3f9c201-...  工学部コンピテンシー  (42 items)

# フレームワーク(CFDocument)管理
# --tenant はテナント UUID を取る（slug は Web UI 上の URL 別名であり、CLI の resolver キーではない）
uv run python cli.py doc list --tenant {tenant-uuid}
# UUID                                  TITLE                     ITEMS  UPDATED
# d86774f2-...                          高等学校学習指導要領        1557   2025-10-08

# テナント更新
# --private / --public は相互排他（同時指定はエラー終了）
# --slug / --clear-slug も相互排他
uv run python cli.py tenant update --tenant {tenant-uuid} --name "New Name"
uv run python cli.py tenant update --tenant {tenant-uuid} --private
uv run python cli.py tenant update --tenant {tenant-uuid} --public
uv run python cli.py tenant update --tenant {tenant-uuid} --slug ikenohata-u
uv run python cli.py tenant update --tenant {tenant-uuid} --clear-slug

# 削除（確認プロンプトあり、--force でスキップ）
uv run python cli.py tenant delete --tenant {tenant-uuid} [--force]
uv run python cli.py doc delete --tenant {tenant-uuid} --doc {doc-uuid} [--force]

# CSVインポート (新規: --doc省略、更新: --doc指定でupsert)
# --doc-title: CFDocumentタイトル。新規作成時はCSVの#title行があれば省略可、なければ必須。更新時は省略可（既存値を保持）
# --doc-version: バージョン（任意、省略時は既存値を保持。新規作成時のデフォルトは NULL）
# --profile: 形式の明示指定。auto（デフォルト）は custom / opensalt / simple を自動判定。
#            明示時は内容がその profile に一致しなければエラー終了（サイレントなフォールバックなし）。
#            値: auto / custom / opensalt / simple
uv run python cli.py import csv --tenant {uuid} --file framework.csv
uv run python cli.py import csv --tenant {uuid} --file framework.csv --doc-title "名称" --doc-version "1.0"
uv run python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework.csv
uv run python cli.py import csv --tenant {uuid} --file framework.csv --profile opensalt

# OpenSALT Excel (.xlsx) インポート — OpenSALT の完全交換形式（CF Doc / CF Item /
# CF Association の 3 シート）。階層は smartLevel で表現され、CFItemType /
# educationLevel も保持される（OpenSALT の CSV では落ちる項目）。
# 稼働中の OpenSALT で動作確認済（アイテム・階層・item type が往復する）。
uv run python cli.py import xlsx --tenant {uuid} --file framework.xlsx
uv run python cli.py import xlsx --tenant {uuid} --doc {doc-uuid} --file framework.xlsx

# 外部CASEインポート (v1.1対応、v1.0はPhase 2、upsert)。--url / --file のどちらか一方を指定する。
# --url:  CASE APIベースパス or CFPackage直接URL（詳細は import-logic.md 参照）
# --file: ローカルの CFPackage JSON ファイル（ネットワーク取得なし、永続化処理は --url と同じ）。
#         取り込み元 CASE サーバーがプライベートでこのホストから到達できない場合に使う
uv run python cli.py import case --tenant {uuid} --url https://case.example.com/{tenant}/ims/case/v1p1
uv run python cli.py import case --tenant {uuid} --doc {doc-uuid} --url https://server/ims/case/v1p1/CFPackages/{uuid}
uv run python cli.py import case --tenant {uuid} --file framework.json
uv run python cli.py import case --tenant {uuid} --doc {doc-uuid} --file framework.json

# エクスポート (UUID付き独自形式 → 編集後にimportでupsert可能)
# --file: 出力先ファイルパス。既に存在する場合は上書きする（確認なし）
uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
uv run python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv --profile opensalt
# --profile: "custom"（デフォルト）/ "opensalt"
#            不正な値 → エラー終了（「Invalid profile: '{value}'. Valid values: custom, opensalt」）

# OpenSALT Excel (.xlsx) エクスポート — OpenSALT の Excel インポーターが取り込める
# 3 シート構成。smartLevel で階層を表現し、CFItemType / educationLevel を含む。
# isChildOf は CF Association シートには重複出力しない。
uv run python cli.py export xlsx --tenant {uuid} --doc {doc-uuid} --file output.xlsx

# CASE CFPackage JSON エクスポート（内容は GET /CFPackages/{id} と同一。CLI は可読性のため indent 付き整形、API は compact JSON）
# import case --file で再取り込みするか、任意の CASE 準拠エディタへ受け渡せる
uv run python cli.py export case --tenant {uuid} --doc {doc-uuid} --file output.json

# ルーブリックCSVインポート (--doc で対象ドキュメントを指定、upsert)
uv run python cli.py import rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

# ルーブリックCSVエクスポート
uv run python cli.py export rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

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
- `--file` で指定したファイルが存在しない → `import csv` / `export *` ではエラー終了（「File not found: '{filepath}'」、終了コード 1）。`import case` / `import xlsx` / `import rubric`（Click の `Path(exists=True)` を使用）ではコマンド実行前に Click の usage error（終了コード 2）で弾かれる
- `--file` で指定したファイルが読み取れない（パーミッションエラー等） → エラー終了（「Cannot read file: '{filepath}'」、終了コード 1）
- `--file` で指定した出力先に書き込めない（ディレクトリが存在しない、パーミッションエラー等） → エラー終了（「Cannot write file: '{filepath}'」、終了コード 1）
- CSVインポート時、ファイルが UTF-8 としてデコードできない → エラー終了（「CSV file is not valid UTF-8」、終了コード 1）
- `tenant update` に `--name` / `--private` / `--public` / `--slug` / `--clear-slug` / `--display-order` / `--clear-order` のいずれも指定されていない → エラー終了（「--name、--private、--public、--slug、--clear-slug、--display-order、--clear-orderのいずれかを指定してください」、終了コード 1）

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

## テナント slug の制約

`--slug` はテナント UUID の URL 別名（エイリアス）を指定するためのオプション。canonical な識別子は UUID のままで、CASE API レスポンス（`LinkURIDType.identifier` / `uri`）は常に UUID を返す。よって CASE クライアント（Open Badge Factory など）が保存している参照は、slug を追加・変更・削除しても壊れない。slug は Web UI と共有リンクの利便性向上のためだけに用いる。

バリデーション（CLI と DB の CHECK 制約の双方で強制）:

| 項目 | 内容 |
|------|------|
| 長さ | 2〜64 文字 |
| 使用可能文字 | 小文字 ASCII `a-z`、数字 `0-9`、ハイフン `-` |
| 先頭・末尾 | 英数字（先頭・末尾のハイフンは不可） |
| UUID 形式は不可 | UUID v4 として解釈できる文字列は拒否（canonical な UUID URL と衝突するため） |
| 予約語 | `health`, `static`, `admin`, `api`, `assets`, `favicon.ico`, `robots.txt`, `_` は拒否（トップレベルルートと衝突するため） |
| 一意性 | デプロイメント内でユニーク |

例:

- 有効: `ikenohata-u`, `acme`, `osaka-univ-2025`
- 無効: `-foo` / `foo-`（先頭・末尾ハイフン）、`Foo`（大文字）、`health`（予約語）、`550e8400-e29b-41d4-a716-446655440000`（UUID）、`a`（短すぎる）

エラー:

- `--slug` の値が制約に違反 → エラー終了（「Slug '{value}' is invalid: ...」、終了コード 1）
- `--slug` の値が既に他テナントで使用中 → エラー終了（「Tenant slug '{value}' is already in use」、終了コード 1）
- `tenant update` で `--slug` と `--clear-slug` を同時指定 → エラー終了（「--slug and --clear-slug are mutually exclusive」、終了コード 1）
