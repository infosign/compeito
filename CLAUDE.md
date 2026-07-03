# COMPEITO — Claude Code Instructions

## プロジェクト概要

1EdTech CASE v1.1 準拠のWebサービス。コンピテンシーフレームワークをAPIで配信する。\
Open Badge Factory (OB v3) と TAO Testing (QTI v3.0) の参照先として機能する。\
インフォザインが開発・運用。Apache License 2.0 で公開。Docker + PostgreSQL で動作。

## 仕様ドキュメント

詳細な仕様は `docs/` 配下を参照。実装時は必ず該当する仕様を確認すること。\
CASE v1.1 公式仕様との照合が必要な場合は `docs/reference/` 配下を参照。

| ドキュメント                                           | 内容                                          |
| ------------------------------------------------ | ------------------------------------------- |
| docs/spec/architecture.md                        | システム構成・技術スタック・参照仕様                          |
| docs/spec/case-overview.md                       | CASE 標準の入門（背景・データモデル/API・v1.0/v1.1差・設計方針）   |
| docs/spec/data-model-overview.md                 | CASE データモデルの図解（関係図・〜URI規約・ルーブリック・つまずき集）   |
| docs/spec/api-spec.md                            | CASE v1.1 APIエンドポイント・レスポンス形式・エラー形式・ページネーション |
| docs/spec/api-examples.md                        | 各エンドポイントの具体的なJSON例・エラー例                     |
| docs/spec/db-schema.md                           | DBスキーマ・テーブル定義・インデックス                        |
| docs/spec/web-ui.md                              | Web UIパス設計・ツリービュー・詳細ページ・URI生成ルール            |
| docs/spec/csv-format.md                          | CSVフォーマット仕様（独自形式・OpenSALT形式・簡易形式）           |
| docs/spec/import-logic.md                        | インポート/エクスポートのビジネスロジック・upsertルール             |
| docs/spec/round-trip-fidelity.md                 | 経路別（CASE JSON / Excel / CSV）の全フィールド往復忠実度マトリクス |
| docs/spec/cli.md                                 | CLIコマンド仕様                                   |
| docs/guide/initial-setup.md                      | 初期データセットアップガイド（テナント作成〜ルーブリック取り込みまで）         |
| docs/guide/opencase-interop.md                   | OpenCASE 相互運用ガイド（公開/プライベートの配置パターンと運用フロー）         |
| docs/dev/conventions.md                          | コミット・PR・リリースノートの書き方規約                       |
| docs/dev/local-setup.md                          | ローカル開発セットアップ（ハイブリッド/全 Docker 両構成）             |
| docs/dev/backlog.md                              | **機能/相互運用バックログ**（未完了項目の索引。「バックログ」はまずここ）   |
| docs/dev/case-v1p1-conformance-backlog.md        | CASE v1.1 厳密適合バックログ（適合性ギャップ専用）              |
| docs/dev/designs/                                | バックログ項目ごとの設計ドキュメント（1項目1ファイル）              |
| docs/requirements/phases.md                      | フェーズ定義・ロードマップ                               |
| docs/requirements/functional-requirements.md     | 機能要件一覧（FR-1〜FR-12）                          |
| docs/requirements/non-functional-requirements.md | 非機能要件一覧（NFR-1〜NFR-11）                       |

### CASE v1.1 公式仕様リファレンス

実装時にフィールド型・必須/任意・列挙値等を確認するための参照資料。

| ドキュメント                                        | 内容                                                           |
| --------------------------------------------- | ------------------------------------------------------------ |
| docs/reference/case-v1p1-info-model.md        | データモデル定義（CFDocument, CFItem, CFAssociation 等の全フィールド・型・必須/任意） |
| docs/reference/case-v1p1-rest-binding.md      | REST API定義（エンドポイント・レスポンス型・Standalone vs Package型の差異）         |
| docs/reference/imscasev1p1_openapi3_v1p0.json | 公式 OpenAPI 3 スキーマ（権威的ソース）                                    |
| docs/reference/opensalt-csv-format.md         | OpenSALT の実際の CSV/Excel フォーマット調査結果（compeito との差異）            |

## ディレクトリ構成

```text
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
│   │   ├── web.py               # Web UI: GET / , /{tenant}/, /cftree/doc/*, /uri/{uuid}
│   │   ├── case_api.py          # CASE API ルーター (/{tenant}/ims/case/v1p1/)
│   │   ├── discovery.py         # ディスカバリ (OpenAPI/well-known 等)
│   │   ├── cf_documents.py / cf_items.py / cf_associations.py
│   │   ├── cf_association_groupings.py / cf_item_types.py / cf_concepts.py
│   │   ├── cf_subjects.py / cf_licenses.py / cf_packages.py
│   │   └── cf_rubrics.py
│   ├── templates/               # Jinja2 HTMLテンプレート
│   │   ├── base.html            # 共通レイアウト (自己ホスト HTMX/フォント, Tailwind ローカル/CDN, ツリーJS)
│   │   ├── index.html           # テナント一覧
│   │   ├── tenant.html          # フレームワーク一覧
│   │   ├── cftree.html          # ツリービュー (左ツリー+右ペイン, 定義/ルーブリック節)
│   │   ├── uri.html             # 単独詳細ページ (permalink)
│   │   ├── error.html           # エラーページ (404/400/500)
│   │   └── fragments/           # 共通パーシャル / HTMX フラグメント
│   │       ├── resource_detail.html  # 全リソース共通のフル詳細カード (マクロ群)
│   │       ├── detail.html           # 右ペイン用 (resource_detail を include)
│   │       ├── tree_nodes.html       # ツリー (ネスト <details>)
│   │       └── tree_node_macros.html # branch_summary / leaf マクロ (定義/ルーブリック節)
│   ├── services/                # ビジネスロジック (router → service → repository)
│   │   ├── tenant_service.py
│   │   ├── case_query_service.py    # CASE API 単一リソース取得・一覧取得
│   │   ├── case_query_params.py     # sort/orderBy/filter/fields パース共通
│   │   ├── cf_view_service.py       # ツリービュー・詳細・CFPackage構築・list_document_definitions
│   │   ├── tree_service.py          # build_ssr_tree (遅延・深さ0-1) / get_children / build_full_tree (dfs_index 用) / dfs_index
│   │   ├── uri_service.py           # /uri/{id} の任意リソース解決
│   │   ├── case_import_service.py
│   │   ├── csv_import_service.py / csv_export_service.py
│   │   ├── csv_rubric_import_service.py / csv_rubric_export_service.py
│   │   └── xlsx_import_service.py / xlsx_export_service.py
│   ├── repositories/            # DBアクセス層
│   │   ├── tenant_repository.py
│   │   ├── cf_document_repository.py
│   │   ├── cf_item_repository.py        # map_identifiers_to_documents 含む
│   │   ├── cf_association_repository.py
│   │   ├── cf_rubric_repository.py
│   │   └── cf_{association_grouping,item_type,concept,subject,license}_repository.py
│   └── static/                  # 静的アセット (自己ホスト・外部CDN非依存)
│       ├── vendor/              # htmx-2.0.4.min.js (+LICENSE)
│       ├── fonts/               # quicksand-700.woff2 (+OFL)
│       ├── css/                 # app.css (Dockerビルド時生成・非コミット)
│       └── *.svg / *.png        # ロゴ・favicon
├── cli.py                       # CLI エントリーポイント
├── tailwind/                    # tailwind/input.css (Docker で app.css にビルド)
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

* **レイヤー構成**: router → service → repository（DBアクセスはrepositoryに集約）

* **非同期**: 全DB操作は async/await (SQLAlchemy async session)

* **スキーマ**: CASEフィールド名はキャメルケース (仕様に準拠)、内部はスネークケース

* **UUID**: テナント・全CASEリソースのidentifierはUUID v4

* **Cache-Control**:

  * 全テナント (public/private共通): `Cache-Control: public, max-age=3600`

  * HTMXフラグメント (`/cftree/doc/*/detail/*`, `/cftree/doc/*/document`): `Cache-Control: public, max-age=86400`

* **エラー形式**: CASE API は imsx_StatusInfo 形式（詳細は docs/spec/api-spec.md）

* **LinkURI型**: 複合オブジェクト `{"title": "...", "identifier": "uuid", "uri": "https://..."}`（詳細は docs/spec/api-spec.md）

## 開発ワークフロー

* **コミット・PR・リリースノートの書き方**: docs/dev/conventions.md に従うこと。

* **コミット前チェック**: コードをコミットする前に、実装内容と docs/ 配下のドキュメント群 (api-spec.md, api-examples.md, db-schema.md 等) および CLAUDE.md に矛盾がないか必ず確認する。矛盾があればドキュメントまたはコードを修正してからコミットする。

* **mainへの直接push禁止**: 全ての変更はブランチを作成しPR経由でマージする。ドキュメントのみの変更でも直接pushしないこと。

* **PRマージ前の確認**: PRを作成しCIが通過したら、マージする前に必ずユーザーに確認を取る。自動的にマージしないこと。フローは「ブランチ作成 → PR作成 → CI通過確認 → チェックボックス更新 → ユーザーに確認 → 承認後にマージ」。

## ローカル開発

セットアップ手順の詳細は docs/dev/local-setup.md を参照。要点だけ:

**ハイブリッド構成（推奨）** — DB だけ Docker、アプリはネイティブ:

```bash
brew install uv                                # uv 未導入時のみ
uv sync                                        # 依存解決と venv 作成
cp .env.example .env                           # DATABASE_URL を localhost に向ける
docker compose up -d db                        # PostgreSQL を起動
uv run alembic upgrade head                    # マイグレーション
uv run pytest                                  # テスト
uv run uvicorn src.main:app --reload           # 開発サーバー
```

**全 Docker 構成** — 本番に近い構成で動かしたい場合:

```bash
docker compose up -d                                  # db + app
docker compose exec app uv run alembic upgrade head
docker compose exec app uv run pytest
```

### テスト環境

* DB: `pytest-asyncio` + `asyncpg` + Docker PostgreSQL（SQLiteは非同期ドライバの差異があるため使わない）

* `conftest.py` でテスト用DBを起動・ロールバック

* CI: GitHub Actions で `docker-compose up -d db` してからテスト実行

⠀