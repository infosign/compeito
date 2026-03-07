# CLIコマンド仕様

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
python cli.py tenant update --tenant {tenant-uuid} --name "New Name"
python cli.py tenant update --tenant {tenant-uuid} --private
python cli.py tenant update --tenant {tenant-uuid} --public

# 削除（確認プロンプトあり、--force でスキップ）
python cli.py tenant delete --tenant {tenant-uuid} [--force]
python cli.py doc delete --tenant {tenant-uuid} --doc {doc-uuid} [--force]

# CSVインポート (新規: --doc省略、更新: --doc指定でupsert)
# --doc-title: CFDocumentタイトル（フォーマット3の#title行があれば省略可、なければ必須）
# --doc-version: バージョン（任意、デフォルト ""）
python cli.py import csv --tenant {uuid} --file framework.csv
python cli.py import csv --tenant {uuid} --file framework.csv --doc-title "名称" --doc-version "1.0"
python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework.csv

# 外部CASEソースインポート (v1.0/v1.1対応、upsert)
python cli.py import case-url --tenant {uuid} --url https://...
python cli.py import case-url --tenant {uuid} --doc {doc-uuid} --url https://...

# エクスポート (UUID付き独自形式 → 編集後にimportでupsert可能)
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file output.csv --format opensalt

# DBマイグレーション
python cli.py db migrate
# Docker環境: alembic upgrade head を直接実行
# AWS環境:    POST /admin/migrate を呼び出す

# キャッシュ無効化 (CloudFront、AWS環境のみ有効)
python cli.py cache invalidate --tenant {uuid}
python cli.py cache invalidate --tenant {uuid} --doc {doc-uuid}
# Docker環境で実行した場合: "This command requires AWS environment" と表示して終了
```

## CSVインポートのデフォルト動作

- `--doc-title` 省略かつCSVに `#title` 行なし → エラー終了（必須）
- `--doc-version` 省略 → `""` （任意）
- `Identifier` 空 → UUID v4 を自動採番
