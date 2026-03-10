# CLIコマンド仕様

## 実行環境（Docker / AWS）

CLIは環境変数により実行モードを自動判定する:
- **Docker環境**: `DATABASE_URL` が設定されている場合。直接DB接続で全操作を実行する
- **AWS環境**: `CASE_ADMIN_URL` + `CASE_ADMIN_KEY` が設定されている場合。管理API (`/admin/*`) 経由で全操作を実行する
- `CASE_ADMIN_URL` と `CASE_ADMIN_KEY` のどちらか一方のみ設定 → エラー終了（「CASE_ADMIN_URL and CASE_ADMIN_KEY must both be set」、終了コード 1）
- 全て未設定 → エラー終了（「DATABASE_URL or CASE_ADMIN_URL+CASE_ADMIN_KEY must be set」、終了コード 1）
- `DATABASE_URL` と `CASE_ADMIN_URL`+`CASE_ADMIN_KEY` の両方が設定されている場合 → `DATABASE_URL` を優先（Docker環境として動作。警告ログを出力）

全コマンド（tenant/doc CRUD、import、export、migrate、cache）がこの共通ルールに従う。以下のコマンド説明では、Docker/AWS で動作が異なる場合にのみ個別に注記する。

## コマンド一覧

```bash
# テナント管理
python cli.py tenant create --name "Company Name" [--private]
python cli.py tenant list
# UUID                                  NAME        VISIBILITY  CREATED
# 550e8400-...                          大学A        public      2025-01-01
# 6ba7b810-...                          企業B        private     2025-02-15

python cli.py tenant list --with-docs
# 550e8400-...  大学A  public
#   ├─ d86774f2-...  高等学校学習指導要領  (1557 items)
#   └─ a3f9c201-...  工学部コンピテンシー  (42 items)

# フレームワーク(CFDocument)管理
python cli.py doc list --tenant {tenant-uuid}
# UUID                                  TITLE                     ITEMS  UPDATED
# d86774f2-...                          高等学校学習指導要領        1557   2025-10-08

# テナント更新
# --private / --public は相互排他（同時指定はエラー終了）
python cli.py tenant update --tenant {tenant-uuid} --name "New Name"
python cli.py tenant update --tenant {tenant-uuid} --private
python cli.py tenant update --tenant {tenant-uuid} --public

# 削除（確認プロンプトあり、--force でスキップ）
python cli.py tenant delete --tenant {tenant-uuid} [--force]
python cli.py doc delete --tenant {tenant-uuid} --doc {doc-uuid} [--force]

# CSVインポート (新規: --doc省略、更新: --doc指定でupsert)
# --doc-title: CFDocumentタイトル。新規作成時はCSVの#title行があれば省略可、なければ必須。更新時は省略可（既存値を保持）
# --doc-version: バージョン（任意、省略時は既存値を保持。新規作成時のデフォルトは NULL）
# Docker環境: 直接DB接続でインポート処理を実行
# AWS環境:    S3にCSVアップロード後、POST /admin/tenants/{id}/import/csv を呼び出す
#             upload-url API の filename には --file パスのベースネームを使用する。
#             ベースネームが API のバリデーション（[a-zA-Z0-9._-]+）に通らない場合は
#             "import.csv" を代替ファイル名として使用する（S3キーにUUIDプレフィックスが
#             付与されるため、ファイル名の一意性は不要）
python cli.py import csv --tenant {uuid} --file framework.csv
python cli.py import csv --tenant {uuid} --file framework.csv --doc-title "名称" --doc-version "1.0"
python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework.csv

# 外部CASEソースインポート (v1.1対応、v1.0はPhase 2、upsert)
# --url: CASE APIベースパス or CFPackage直接URL（詳細は import-logic.md 参照）
# Docker環境: 直接DB接続で外部URLからフェッチ・インポート処理を実行
# AWS環境:    POST /admin/tenants/{id}/import/case-url を呼び出す（Lambda が外部URLにアクセス）
python cli.py import case-url --tenant {uuid} --url https://case.example.com/{tenant}/ims/case/v1p1
python cli.py import case-url --tenant {uuid} --doc {doc-uuid} --url https://server/ims/case/v1p1/CFPackages/{uuid}

# エクスポート (UUID付き独自形式 → 編集後にimportでupsert可能)
# --file: 出力先ファイルパス。既に存在する場合は上書きする（確認なし）
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv --format opensalt
# --format: "custom"（デフォルト）/ "opensalt"（Phase 2）。Phase 1 で opensalt を指定した場合は
#           エラー終了（「opensalt format is not yet supported」）
#           不正な値 → エラー終了（「Invalid format: '{value}'. Valid values: custom, opensalt」）

# DBマイグレーション
python cli.py db migrate
# Docker環境: alembic upgrade head を直接実行
# AWS環境:    POST /admin/migrate を呼び出す

# キャッシュ無効化 (CloudFront、AWS環境のみ有効)
python cli.py cache invalidate --tenant {uuid}
python cli.py cache invalidate --tenant {uuid} --doc {doc-uuid}
# Docker環境で実行した場合: "This command requires AWS environment" と表示して終了（終了コード 1）

# 自動キャッシュ無効化 (Phase 2、AWS環境のみ)
# import csv / import case-url / doc delete / tenant create / tenant update / tenant delete コマンドの
# 完了時に CloudFront invalidation を自動実行する。
# invalidation パスの詳細は architecture.md の CloudFront Invalidation戦略を参照。
# Docker環境では自動invalidationはスキップされる（CloudFrontがないため）。
```

## コマンド出力形式

### 作成・更新・削除の出力

```bash
# tenant create → 作成されたテナント情報を表示
python cli.py tenant create --name "大学A"
# Created tenant: 550e8400-... (大学A, public)

# tenant update → 更新後のテナント情報を表示
python cli.py tenant update --tenant {uuid} --name "New Name"
# Updated tenant: 550e8400-... (New Name, public)

# tenant delete → 削除確認プロンプト → 成功メッセージ
python cli.py tenant delete --tenant {uuid}
# Delete tenant '大学A' (550e8400-...)? This will delete all documents and items. [y/N]: y
# Deleted tenant: 550e8400-... (大学A)

# doc delete → 削除確認プロンプト → 成功メッセージ
python cli.py doc delete --tenant {uuid} --doc {doc-uuid}
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
Docker環境（直接DB接続）では `--file` で指定したパスにファイルを書き出す。AWS環境（管理API経由）では presigned URL 経由で S3 からダウンロードし、`--file` で指定したパスに保存する

### AWS環境での管理API接続エラー

Admin API への HTTP リクエストが失敗した場合:
- 接続エラー（タイムアウト・接続拒否・DNS解決失敗等） → エラー終了（「Admin API connection failed: {error}」、終了コード 1）
- HTTP ステータスが 4xx/5xx → Admin API のエラーレスポンス（`detail` フィールド）をそのまま表示してエラー終了（終了コード 1）
- レスポンスが JSON としてパースできない → エラー終了（「Admin API returned invalid response」、終了コード 1）

### AWS環境での S3 操作エラー

AWS環境での presigned URL 操作（インポート時の S3 アップロード、エクスポート時の S3 ダウンロード）が失敗した場合:
- ネットワークエラー → エラー終了（「S3 upload failed: {error}」/「S3 download failed: {error}」、終了コード 1）
- HTTP ステータスが 2xx 以外 → エラー終了（「S3 upload returned HTTP {status}」/「S3 download returned HTTP {status}」、終了コード 1）
- presigned URL 期限切れ（403 Forbidden） → 上記の HTTP ステータスエラーとして処理される。リトライしない
