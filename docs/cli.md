# CLIコマンド仕様

## 実行環境

CLIは `DATABASE_URL` 環境変数で PostgreSQL に直接接続する。
`DATABASE_URL` が未設定の場合はエラー終了する（終了コード 1）。

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
python cli.py import csv --tenant {uuid} --file framework.csv
python cli.py import csv --tenant {uuid} --file framework.csv --doc-title "名称" --doc-version "1.0"
python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework.csv

# 外部CASEソースインポート (v1.1対応、v1.0はPhase 2、upsert)
# --url: CASE APIベースパス or CFPackage直接URL（詳細は import-logic.md 参照）
python cli.py import case-url --tenant {uuid} --url https://case.example.com/{tenant}/ims/case/v1p1
python cli.py import case-url --tenant {uuid} --doc {doc-uuid} --url https://server/ims/case/v1p1/CFPackages/{uuid}

# エクスポート (UUID付き独自形式 → 編集後にimportでupsert可能)
# --file: 出力先ファイルパス。既に存在する場合は上書きする（確認なし）
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv --format opensalt
# --format: "custom"（デフォルト）/ "opensalt"
#           不正な値 → エラー終了（「Invalid format: '{value}'. Valid values: custom, opensalt」）

# ルーブリックCSVインポート (--doc で対象ドキュメントを指定、upsert)
python cli.py import csv-rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

# ルーブリックCSVエクスポート
python cli.py export csv-rubric --tenant {uuid} --doc {doc-uuid} --file rubric.csv

# DBマイグレーション
python cli.py db migrate
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
`--file` で指定したパスにファイルを書き出す。
