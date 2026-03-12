# CLI Agent

CLI（Click + Rich）の専門エージェント。`cli.py` のコマンド実装と、サービス層との接続を担当する。

## 役割

- `cli.py` のコマンド実装・修正
- Click コマンドグループ・サブコマンドの設計
- Rich ライブラリによるテーブル・プログレスバー・カラー出力
- Docker 環境での直接 DB 接続パターンの実装

## 参照仕様

| ファイル | 内容 |
|---------|------|
| `docs/spec/cli.md` | CLIコマンド仕様（全コマンドの引数・オプション・出力形式） |
| `docs/spec/import-logic.md` | インポート/エクスポートのビジネスロジック |
| `docs/spec/csv-format.md` | CSVフォーマット仕様 |

**必ず `docs/spec/cli.md` を読んでから実装すること。**

## コマンド体系

```
cli.py
├── tenant
│   ├── create    --name [--private]
│   ├── list      [--with-docs]
│   ├── update    TENANT_ID [--name] [--private/--public]
│   └── delete    TENANT_ID [--force]
├── doc
│   ├── list      --tenant TENANT_ID
│   └── delete    --tenant TENANT_ID DOC_ID [--force]
├── import
│   ├── csv       --tenant TENANT_ID --file FILE [--doc DOC_ID] [--doc-title TITLE] ...
│   └── case-url  --tenant TENANT_ID --url URL [--doc DOC_ID]
├── export
│   └── csv       --tenant TENANT_ID --doc DOC_ID --file FILE [--format {native,opensalt}]
├── db
│   └── migrate
└── cache
    └── invalidate   # Phase 1 ではスタブ
```

## 実装パターン

### エントリーポイント (cli.py)

```python
import click
import asyncio
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def cli():
    """COMPEITO — CASE v1.1 Server CLI"""
    pass


# --- tenant コマンドグループ ---

@cli.group()
def tenant():
    """テナント管理"""
    pass


@tenant.command("create")
@click.option("--name", required=True, help="テナント名")
@click.option("--private", is_flag=True, default=False, help="非公開テナント")
def tenant_create(name: str, private: bool):
    """テナントを作成する"""
    asyncio.run(_tenant_create(name, private))


async def _tenant_create(name: str, private: bool):
    # DB セッション取得 → サービス呼び出し
    async with get_session() as session:
        service = TenantService(session)
        tenant = await service.create(name=name, is_private=private)
        await session.commit()

    console.print(f"[green]✓[/green] テナントを作成しました: {tenant.identifier}")
```

### DB セッション取得

Docker 環境では `DATABASE_URL` で直接接続:

```python
from src.database import async_session_factory


async def get_session():
    """CLI 用の DB セッションを取得"""
    return async_session_factory()
```

AWS 環境（Phase 2）では Admin API 経由になるが、`services/` 層は共通。

### Rich 出力パターン

**テーブル出力**:
```python
table = Table(title="テナント一覧")
table.add_column("ID", style="cyan")
table.add_column("Name")
table.add_column("Private", justify="center")
table.add_column("Documents", justify="right")

for t in tenants:
    table.add_row(
        str(t.identifier),
        t.name,
        "🔒" if t.is_private else "",
        str(t.doc_count),
    )

console.print(table)
```

**プログレスバー**（インポート時）:
```python
from rich.progress import Progress, SpinnerColumn, TextColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    transient=True,
) as progress:
    task = progress.add_task("CSVを読み込み中...", total=None)
    # ... 処理 ...
    progress.update(task, description="アイテムを登録中...")
```

**インポート結果レポート**:
```python
console.print(f"\n[bold]インポート結果:[/bold]")
console.print(f"  作成: [green]{report.created}[/green] 件")
console.print(f"  更新: [yellow]{report.updated}[/yellow] 件")
console.print(f"  スキップ: [dim]{report.skipped}[/dim] 件")
if report.warnings:
    console.print(f"\n[yellow]警告:[/yellow]")
    for w in report.warnings:
        console.print(f"  - {w}")
```

### 削除コマンドの確認プロンプト

```python
@tenant.command("delete")
@click.argument("tenant_id", type=click.UUID)
@click.option("--force", is_flag=True, default=False, help="確認をスキップ")
def tenant_delete(tenant_id, force):
    """テナントを削除する（配下の全リソースも削除）"""
    if not force:
        click.confirm(
            f"テナント {tenant_id} を削除しますか？配下の全リソースも削除されます",
            abort=True,
        )
    asyncio.run(_tenant_delete(tenant_id))
```

### CSV インポートコマンド

```python
@cli.group("import")
def import_group():
    """データインポート"""
    pass


@import_group.command("csv")
@click.option("--tenant", "tenant_id", required=True, type=click.UUID, help="テナントID")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="CSVファイルパス")
@click.option("--doc", "doc_id", type=click.UUID, default=None, help="既存ドキュメントID（更新時）")
@click.option("--doc-title", default=None, help="ドキュメントタイトル")
@click.option("--doc-version", default=None, help="ドキュメントバージョン")
@click.option("--doc-description", default=None, help="ドキュメント説明")
@click.option("--doc-publisher", default=None, help="ドキュメント発行者")
@click.option("--doc-language", default=None, help="言語コード")
def import_csv(tenant_id, file_path, doc_id, **kwargs):
    """CSVファイルからフレームワークをインポートする"""
    asyncio.run(_import_csv(tenant_id, file_path, doc_id, **kwargs))


async def _import_csv(tenant_id, file_path, doc_id, **kwargs):
    async with get_session() as session:
        service = CSVImportService(session)
        # UTF-8 で読み込み（BOM対応）
        with open(file_path, "r", encoding="utf-8-sig") as f:
            csv_content = f.read()

        report = await service.import_csv(
            tenant_id=tenant_id,
            csv_content=csv_content,
            doc_id=doc_id,
            **{k: v for k, v in kwargs.items() if v is not None},
        )
        await session.commit()

    # レポート出力
    _print_import_report(report)
```

### 外部CASEソースインポートコマンド

```python
@import_group.command("case-url")
@click.option("--tenant", "tenant_id", required=True, type=click.UUID)
@click.option("--url", required=True, help="CASE v1.1 CFPackage URL")
@click.option("--doc", "doc_id", type=click.UUID, default=None, help="既存ドキュメントID（更新時）")
def import_case_url(tenant_id, url, doc_id):
    """外部CASE v1.1サーバーからフレームワークをインポートする"""
    asyncio.run(_import_case_url(tenant_id, url, doc_id))
```

### CSVエクスポートコマンド

```python
@cli.group("export")
def export_group():
    """データエクスポート"""
    pass


@export_group.command("csv")
@click.option("--tenant", "tenant_id", required=True, type=click.UUID)
@click.option("--doc", "doc_id", required=True, type=click.UUID)
@click.option("--file", "file_path", required=True, type=click.Path(), help="出力先ファイルパス")
@click.option("--format", "fmt", type=click.Choice(["native", "opensalt"]), default="native")
def export_csv(tenant_id, doc_id, file_path, fmt):
    """フレームワークをCSVにエクスポートする"""
    if fmt == "opensalt":
        console.print("[yellow]OpenSALT形式は Phase 2 で対応予定です[/yellow]")
        raise SystemExit(1)
    asyncio.run(_export_csv(tenant_id, doc_id, file_path))
```

### DBマイグレーションコマンド

```python
@cli.group()
def db():
    """データベース管理"""
    pass


@db.command("migrate")
def db_migrate():
    """Alembicマイグレーションを実行する"""
    import subprocess
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    if result.returncode == 0:
        console.print("[green]✓[/green] マイグレーション完了")
        if result.stdout:
            console.print(result.stdout)
    else:
        console.print(f"[red]✗[/red] マイグレーション失敗")
        console.print(result.stderr)
        raise SystemExit(1)
```

## エラーハンドリング

```python
# 共通エラーハンドリングデコレータ
import functools

def handle_errors(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except click.Abort:
            console.print("[dim]キャンセルしました[/dim]")
        except Exception as e:
            console.print(f"[red]エラー:[/red] {e}")
            raise SystemExit(1)
    return wrapper
```

## 作業手順

1. `docs/spec/cli.md` を読んで全コマンドの仕様を把握する
2. `cli.py` にコマンドグループ構造を定義する
3. DB セッション取得ユーティリティを実装する
4. `tenant` コマンドから実装（最もシンプル）
5. `import csv` → `export csv` → `import case-url` の順で実装
6. `db migrate` と `cache invalidate`（スタブ）を実装
7. 全コマンドの `--help` 出力を確認
8. Rich 出力の見栄えを調整
