# アーキテクチャ

## システム構成

```
Docker (FastAPI + uvicorn) → PostgreSQL
```

- **マルチテナント**: `/{tenant-uuid}/ims/case/v1p1/` でテナント分離（v1p0も後方互換で維持）
- **公開制御**: public/private フラグ。privateはトップ一覧に非表示、URL直接アクセスは可能
- **データ更新**: CLI経由のみ（Web UIなし）。CSV または外部CASEソースからインポート

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| API | Python 3.12 + FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| マイグレーション | Alembic |
| DB | PostgreSQL (Docker) |
| ローカル開発 | Docker + docker-compose |
| テスト | pytest + pytest-asyncio |
| パッケージ管理 | uv |
| CLI表示 | rich (テーブル・プログレスバー・カラー出力) |
| Web UI | Jinja2 + HTMX + Tailwind CSS (CDN) |

## Alembicマイグレーション実行戦略

Alembic は asyncpg（async ドライバ）をそのまま使用する。同期ドライバ（psycopg2）は不要。
`env.py` で `run_async_migrations()` パターンを使い、`connectable = create_async_engine(...)` で接続する。

```bash
docker compose exec app alembic upgrade head
```

## CLI実行環境

CLIは `DATABASE_URL` 環境変数で PostgreSQL に直接接続。

## バージョン対応方針

| 操作 | v1.0 | v1.1 |
|------|------|------|
| インポート (CSV / 外部CASEソース) | ○ (v1.1に正規化して保存、Phase 2) | ○ |
| API配信 | なし | ○ (v1.1のみ) |

## 背景・差別化

現在のデファクトCASE実装は **OpenSALT** (PCG Education製OSS) だが CASE v1.0 止まり。
本プロジェクトは CASE v1.1 対応の現代的な実装として差別化する。
OpenSALT で公開されているフレームワークをインポートできることも重要な価値。

## 参照仕様

### CASE v1.1 (1EdTech Competency and Academic Standards Exchange)
- 仕様トップ: https://www.imsglobal.org/spec/case/v1p1
- Information Model: https://www.imsglobal.org/sites/default/files/spec/case/v1p1/information_model/caseservicev1p1_infomodelv1p0.html
  - §5 Data Model: CFDocument, CFItem, CFAssociation 等のフィールド定義
  - ローカル参照: [docs/reference/case-v1p1-info-model.md](reference/case-v1p1-info-model.md)
- REST/JSON Binding: https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html
  - §4 REST API: エンドポイント一覧、リクエスト/レスポンス形式
  - §6 UML to JSON Mappings: 全DType・列挙値の定義
  - §7 Conformance: 必須エンドポイントと準拠要件
  - 付録B: OpenAPI定義 (YAML/JSON) — 1EdTechメンバーログイン要
  - 付録C: JSON Schema — 1EdTechメンバーログイン要
  - ローカル参照: [docs/reference/case-v1p1-rest-binding.md](reference/case-v1p1-rest-binding.md)
- OpenAPI 3 スキーマ（権威的ソース）: [docs/reference/imscasev1p1_openapi3_v1p0.json](reference/imscasev1p1_openapi3_v1p0.json)
  - 公式配布元: https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/imscasev1p1_openapi3_v1p0.json
- レスポンス形式: 標準JSON（JSON-LDの `@context` / `@type` はREST APIに含めない）
- imsx_StatusInfo エラー形式: REST Binding §4.4

### 関連仕様
- Open Badges v3: https://www.imsglobal.org/spec/ob/v3p0
- QTI v3.0: https://www.imsglobal.org/spec/qti/v3p0
- OpenSALT (既存CASE実装): https://github.com/opensalt/opensalt
