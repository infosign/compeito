# アーキテクチャ

## システム構成

```
Public:  CloudFront → API Gateway → Lambda (FastAPI + Mangum) → Aurora Serverless v2 (PostgreSQL)
Admin:   CLI → Lambda Function URL (HTTPS + Bearer token) → Lambda → Aurora
```

- **Lambda**: 基本的に単一の Lambda 関数。タイムアウト 300s。アクセス経路が2つ（API Gateway / Function URL）。ただし `POST /admin/migrate` は並行実行防止のため別 Lambda 関数（同一コード）として予約同時実行数=1 で CDK デプロイする（NFR-2.4）
- **Public API**: API Gateway 経由。API Gateway の統合タイムアウト (29s) で自然に制限される
- **Admin API**: Lambda Function URL 経由。API Gateway を通さないため 300s の長時間処理が可能

- **マルチテナント**: `/{tenant-uuid}/ims/case/v1p1/` でテナント分離（v1p0も後方互換で維持）
- **公開制御**: public/private フラグ。privateはトップ一覧に非表示、URL直接アクセスは可能
- **キャッシュ**: CloudFront が主キャッシュ。CLIインポート時にinvalidate
- **データ更新**: CLI経由のみ（Web UIなし）。CSV または外部CASEソースからインポート

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| API | Python 3.12 + FastAPI + Mangum |
| ORM | SQLAlchemy 2.x (async) |
| マイグレーション | Alembic |
| DB | PostgreSQL (Aurora Serverless v2 / ローカルはDocker) |
| キャッシュ | CloudFront (HTTP Cache-Control headers) |
| インフラ | AWS CDK (Python) |
| ローカル開発 | Docker + docker-compose |
| テスト | pytest + pytest-asyncio |
| パッケージ管理 | uv |
| CLI表示 | rich (テーブル・プログレスバー・カラー出力) |
| Web UI | Jinja2 + HTMX + Tailwind CSS (CDN) |

## Alembicマイグレーション実行戦略

Alembic は asyncpg（async ドライバ）をそのまま使用する。同期ドライバ（psycopg2）は不要。
`env.py` で `run_async_migrations()` パターンを使い、`connectable = create_async_engine(...)` で接続する。

**ローカル/Docker環境:**
```bash
docker-compose exec app alembic upgrade head
```

**AWS環境:**
CLIから管理APIを叩いてLambda内でマイグレーションを実行する。
```bash
python cli.py db migrate   # POST /admin/migrate → Lambda内でalembic upgrade head
```
Lambda起動時の自動マイグレーションは行わない（並列実行時の競合リスクのため）。

## CLI実行環境と認証

### Docker環境（ローカル開発）
CLIは `DATABASE_URL` 環境変数で PostgreSQL に直接接続。
Admin APIに認証なし（ローカル開発用）。

### AWS環境
CLIは Lambda Function URL 経由で Lambda を呼び出す。
Lambda がVPC内でAuroraに接続する。

```
CLI → HTTPS + Bearer token → Lambda Function URL (/admin/*) → Lambda → Aurora
```

**認証:**
- Lambda Function URL: `auth_type=NONE`（インフラ層の認証なし）
- アプリ層: FastAPIミドルウェアで `Authorization: Bearer <shared-secret>` を検証（timing attack 防止のため `hmac.compare_digest()` で定数時間比較する）
- CDKデプロイ時にシークレットを生成し、Secrets Manager に保存。CDK Outputs に Function URL を出力
- オペレーター側: `.env` ファイル（ローカル）、Repository Secrets（CI/CD）

```bash
# .env (gitignoreに追加)
CASE_ADMIN_URL=https://xxxxxxxx.lambda-url.ap-northeast-1.on.aws
CASE_ADMIN_KEY=xxxxxxxxxxxxxxxxxxxx
```

CLIは環境変数で接続先を自動判定:
- `DATABASE_URL` あり → 直接DB接続（Docker環境）
- `CASE_ADMIN_URL` + `CASE_ADMIN_KEY` あり → 管理API経由（AWS環境）
- `CASE_ADMIN_URL` と `CASE_ADMIN_KEY` のどちらか一方のみ設定 → エラー終了（「CASE_ADMIN_URL and CASE_ADMIN_KEY must both be set」）
- 両方設定されている場合 → `DATABASE_URL` を優先（直接DB接続）。ログに警告を出す。
- どちらもない場合 → エラー終了（「DATABASE_URL or CASE_ADMIN_URL+CASE_ADMIN_KEY must be set」）

## CloudFront Invalidation戦略

ワイルドカードを使い常に無料枠（月1000パス）内に収める。
CLIのデータ変更操作（import csv, import case-url, doc delete, tenant create, tenant update, tenant delete）完了時に自動でinvalidationを実行する（Phase 2）。

| 操作 | invalidationパス | カウント |
|------|----------------|---------|
| テナント全体（手動） | `/{tenant-uuid}/*` / `/` | 2 |
| ドキュメント更新（import） | `/{tenant-uuid}/cftree/doc/{doc-uuid}*` / `/{tenant-uuid}/uri/*` / `/{tenant-uuid}/ims/case/v1p1/CFPackages/{doc-uuid}` / `/{tenant-uuid}/ims/case/v1p1/CFDocuments*` / `/{tenant-uuid}/` | 5 |
| ドキュメント削除（doc delete） | `/{tenant-uuid}/cftree/doc/{doc-uuid}*` / `/{tenant-uuid}/uri/*` / `/{tenant-uuid}/ims/case/v1p1/CFPackages/{doc-uuid}` / `/{tenant-uuid}/ims/case/v1p1/CFDocuments*` / `/{tenant-uuid}/` | 5 |
| テナント作成（tenant create） | `/` | 1 |
| テナント更新（tenant update） | `/{tenant-uuid}/*` / `/` | 2 |
| テナント削除（tenant delete） | `/{tenant-uuid}/*` / `/` | 2 |

**ドキュメント更新時のトレードオフ:** 個別リソースAPI（`/CFItems/{id}`, `/CFItemAssociations/{id}`, `/CFAssociations/{id}`, `/CFItemTypes`, `/CFSubjects`, `/CFConcepts`, `/CFLicenses`, `/CFAssociationGroupings` 等）は
invalidation対象に含めない。これらは `max-age=3600` の自然失効に委ねる（最大1時間のステール許容）。
全パスを個別にinvalidateすると無料枠を超過するリスクがあるため、アクセス頻度の高いパス（ツリービュー・詳細ページ・CFPackage・CFDocuments一覧）に絞る。
即座に全API応答を最新化したい場合は、テナント全体の invalidation（`/{tenant-uuid}/*`、1パス）を使用する。

```bash
# import実行時は自動でinvalidation（手動実行も可能）
python cli.py cache invalidate --tenant {uuid}
python cli.py cache invalidate --tenant {uuid} --doc {doc-uuid}
```

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
