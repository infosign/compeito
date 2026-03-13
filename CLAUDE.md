# COMPEITO — Claude Code Instructions

## プロジェクト概要

1EdTech CASE v1.1 準拠のWebサービス。コンピテンシーフレームワークをAPIで配信する。
Open Badge Factory (OB v3) と TAO Testing (QTI v3.0) の参照先として機能する。
インフォザインが開発・運用。Apache License 2.0 で公開。Docker + PostgreSQL で動作。

## 仕様ドキュメント

詳細な仕様は `docs/` 配下を参照。実装時は必ず該当する仕様を確認すること。
CASE v1.1 公式仕様との照合が必要な場合は `docs/reference/` 配下を参照。

| ドキュメント | 内容 |
|-------------|------|
| [docs/spec/architecture.md](docs/spec/architecture.md) | システム構成・技術スタック・参照仕様 |
| [docs/spec/api-spec.md](docs/spec/api-spec.md) | CASE v1.1 APIエンドポイント・レスポンス形式・エラー形式・ページネーション |
| [docs/spec/api-examples.md](docs/spec/api-examples.md) | 各エンドポイントの具体的なJSON例・エラー例 |
| [docs/spec/db-schema.md](docs/spec/db-schema.md) | DBスキーマ・テーブル定義・インデックス |
| [docs/spec/web-ui.md](docs/spec/web-ui.md) | Web UIパス設計・ツリービュー・詳細ページ・URI生成ルール |
| [docs/spec/csv-format.md](docs/spec/csv-format.md) | CSVフォーマット仕様（独自形式・OpenSALT形式・簡易形式） |
| [docs/spec/import-logic.md](docs/spec/import-logic.md) | インポート/エクスポートのビジネスロジック・upsertルール |
| [docs/spec/cli.md](docs/spec/cli.md) | CLIコマンド仕様 |
| [docs/guide/initial-setup.md](docs/guide/initial-setup.md) | 初期データセットアップガイド（テナント作成〜ルーブリック取り込みまで） |
| [docs/dev/conventions.md](docs/dev/conventions.md) | コミット・PR・リリースノートの書き方規約 |
| [docs/requirements/phases.md](docs/requirements/phases.md) | フェーズ定義・ロードマップ |
| [docs/requirements/functional-requirements.md](docs/requirements/functional-requirements.md) | 機能要件一覧（FR-1〜FR-12） |
| [docs/requirements/non-functional-requirements.md](docs/requirements/non-functional-requirements.md) | 非機能要件一覧（NFR-1〜NFR-11） |

### CASE v1.1 公式仕様リファレンス

実装時にフィールド型・必須/任意・列挙値等を確認するための参照資料。

| ドキュメント | 内容 |
|-------------|------|
| [docs/reference/case-v1p1-info-model.md](docs/reference/case-v1p1-info-model.md) | データモデル定義（CFDocument, CFItem, CFAssociation 等の全フィールド・型・必須/任意） |
| [docs/reference/case-v1p1-rest-binding.md](docs/reference/case-v1p1-rest-binding.md) | REST API定義（エンドポイント・レスポンス型・Standalone vs Package型の差異） |
| [docs/reference/imscasev1p1_openapi3_v1p0.json](docs/reference/imscasev1p1_openapi3_v1p0.json) | 公式 OpenAPI 3 スキーマ（権威的ソース） |
| [docs/reference/opensalt-csv-format.md](docs/reference/opensalt-csv-format.md) | OpenSALT の実際の CSV/Excel フォーマット調査結果（compeito との差異） |

## ディレクトリ構成

```
compeito/
├── src/
│   ├── main.py                  # FastAPI app エントリーポイント + GET /health + v1p0リダイレクトミドルウェア
│   ├── config.py                # 設定 (Pydantic Settings)
│   ├── database.py              # DB接続 (async SQLAlchemy)
│   ├── errors.py                # imsx_StatusInfo エラーレスポンス生成 + 例外クラス
│   ├── dependencies.py          # 共通依存 (require_tenant, validate_uuid)
│   ├── models/                  # SQLAlchemy ORM モデル
│   │   ├── tenant.py
│   │   ├── cf_document.py
│   │   ├── cf_item.py
│   │   ├── cf_association.py
│   │   ├── cf_association_grouping.py
│   │   ├── cf_item_type.py
│   │   ├── cf_concept.py
│   │   ├── cf_subject.py
│   │   ├── cf_license.py
│   │   ├── cf_rubric.py              # Phase 2 (APIは後回し、DBは初期から)
│   │   ├── cf_rubric_criterion.py
│   │   └── cf_rubric_criterion_level.py
│   ├── schemas/                 # Pydantic スキーマ (CASE v1.1 準拠)
│   │   ├── common.py            # LinkURIType, LinkGenURIDType, imsx_StatusInfo, CASEBaseSchema 等の共通型
│   │   ├── cf_document.py
│   │   ├── cf_item.py
│   │   ├── cf_association.py
│   │   ├── cf_association_grouping.py
│   │   ├── cf_item_type.py
│   │   ├── cf_concept.py
│   │   ├── cf_subject.py
│   │   ├── cf_license.py
│   │   ├── cf_package.py
│   │   └── cf_rubric.py              # Phase 2
│   ├── routers/                 # FastAPI ルーター
│   │   ├── web.py               # Web UI: /{tenant}/, /cftree/doc/*, /uri/{uuid}
│   │   ├── index.py             # GET / テナント一覧
│   │   ├── cf_documents.py
│   │   ├── cf_items.py
│   │   ├── cf_associations.py
│   │   ├── cf_association_groupings.py
│   │   ├── cf_item_types.py
│   │   ├── cf_concepts.py
│   │   ├── cf_subjects.py
│   │   ├── cf_licenses.py
│   │   ├── cf_packages.py
│   │   └── cf_rubrics.py             # Phase 2
│   ├── templates/               # Jinja2 HTMLテンプレート
│   │   ├── base.html            # 共通レイアウト
│   │   ├── index.html           # テナント一覧
│   │   ├── tenant.html          # フレームワーク一覧
│   │   ├── cftree.html          # ツリービュー
│   │   ├── uri.html             # アイテム詳細
│   │   └── error.html           # エラーページ (404/400/500)
│   ├── services/                # ビジネスロジック (router → service → repository)
│   │   ├── tenant_service.py
│   │   ├── case_query_service.py    # CASE API 単一リソース取得・一覧取得
│   │   ├── cf_view_service.py       # ツリービュー・アイテム詳細・CFPackage構築
│   │   ├── csv_import_service.py
│   │   ├── csv_export_service.py
│   │   └── case_import_service.py
│   └── repositories/            # DBアクセス層
│       ├── tenant_repository.py
│       ├── cf_document_repository.py
│       ├── cf_item_repository.py
│       ├── cf_association_repository.py
│       ├── cf_association_grouping_repository.py
│       ├── cf_item_type_repository.py
│       ├── cf_concept_repository.py
│       ├── cf_subject_repository.py
│       └── cf_license_repository.py
├── cli.py                       # CLI エントリーポイント
├── migrations/                  # Alembic マイグレーション
├── tests/
│   ├── unit/
│   └── integration/
├── docs/                        # 仕様ドキュメント
│   └── reference/               # CASE v1.1 公式仕様リファレンス (OpenAPI スキーマ等)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .claude/
    ├── agents/                  # Claude Code サブエージェント定義
    └── skills/                  # Claude Code スキル定義
```

## コーディング規約

- **レイヤー構成**: router → service → repository（DBアクセスはrepositoryに集約）
- **非同期**: 全DB操作は async/await (SQLAlchemy async session)
- **スキーマ**: CASEフィールド名はキャメルケース (仕様に準拠)、内部はスネークケース
- **UUID**: テナント・全CASEリソースのidentifierはUUID v4
- **Cache-Control**:
  - 全テナント (public/private共通): `Cache-Control: public, max-age=3600`
  - HTMXフラグメント (`/cftree/doc/*/children/*`, `/cftree/doc/*/detail/*`): `Cache-Control: public, max-age=86400`
- **エラー形式**: CASE API は imsx_StatusInfo 形式（詳細は [docs/spec/api-spec.md](docs/spec/api-spec.md)）
- **LinkURI型**: 複合オブジェクト `{"title": "...", "identifier": "uuid", "uri": "https://..."}`（詳細は [docs/spec/api-spec.md](docs/spec/api-spec.md)）

## 開発ワークフロー

- **コミット・PR・リリースノートの書き方**: [docs/dev/conventions.md](docs/dev/conventions.md) に従うこと。
- **コミット前チェック**: コードをコミットする前に、実装内容と docs/ 配下のドキュメント群 (api-spec.md, api-examples.md, db-schema.md 等) および CLAUDE.md に矛盾がないか必ず確認する。矛盾があればドキュメントまたはコードを修正してからコミットする。
- **mainへの直接push禁止**: 全ての変更はブランチを作成しPR経由でマージする。ドキュメントのみの変更でも直接pushしないこと。
- **PRマージ前の確認**: PRを作成しCIが通過したら、マージする前に必ずユーザーに確認を取る。自動的にマージしないこと。フローは「ブランチ作成 → PR作成 → CI通過確認 → チェックボックス更新 → ユーザーに確認 → 承認後にマージ」。

## ローカル開発

```bash
docker compose up -d          # PostgreSQL + アプリ起動
docker compose exec app alembic upgrade head   # マイグレーション実行
docker compose exec app pytest                 # テスト実行
```

開発時はアプリもDockerで実行する（Fargate等へのポータビリティ確保）。
ホットリロードは docker-compose.yml の volumes マウント + uvicorn `--reload` で対応。

### テスト環境
- DB: `pytest-asyncio` + `asyncpg` + Docker PostgreSQL（SQLiteは非同期ドライバの差異があるため使わない）
- `conftest.py` でテスト用DBを起動・ロールバック
- CI: GitHub Actions で `docker-compose up -d db` してからテスト実行
