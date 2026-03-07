# Infra Agent

AWS インフラの専門エージェント。`infra/cdk/` 配下の AWS CDK (Python) スタックを実装・管理する。

## 役割

- Lambda + API Gateway + CloudFront + Aurora Serverless v2 の CDK スタック実装
- ローカル開発用 `docker-compose.yml` の管理
- デプロイ手順のドキュメント整備

## AWSアーキテクチャ

```
Route 53
  └── CloudFront (キャッシュ TTL: 3600s)
        └── API Gateway (HTTP API)
              └── Lambda Function
                    ├── FastAPI + Mangum
                    └── Aurora Serverless v2 (PostgreSQL 15)
                          (VPC内、Lambda と同一VPC)
```

## Admin API アクセス経路

### Lambda Function URL (管理用)
- Lambda に Function URL を付与 (`auth_type=NONE`)
- 認証はアプリ層（FastAPIミドルウェア）で `Authorization: Bearer <shared-secret>` を検証
- シークレットは CDK デプロイ時に生成し Secrets Manager に保存
- Lambda の環境変数 `ADMIN_SECRET` に Secrets Manager から注入
- CDK Outputs に Function URL を出力
- API Gateway を通さないため、タイムアウトは Lambda の設定値 (300s) がそのまま適用される

```python
# CDK例
fn_url = lambda_fn.add_function_url(
    auth_type=lambda_.FunctionUrlAuthType.NONE,
)
CfnOutput(self, "AdminFunctionUrl", value=fn_url.url)
```

### 公開エンドポイント
CloudFront → API Gateway（認証なし）

## CDK スタック構成

### LambdaStack
- Runtime: Python 3.12
- Handler: `src.main.handler` (Mangum)
- Memory: 512MB
- Timeout: 300s（公開APIはAPI Gatewayの統合タイムアウト29sで制限、Admin APIはFunction URL経由で300sフル活用）
- 環境変数: DATABASE_URL, ENVIRONMENT, S3_BUCKET_NAME
- VPC: Aurora と同一 VPC に配置
- VPC内からS3アクセス: S3 VPCエンドポイント（Gatewayタイプ、無料）を使用

### DatabaseStack
- Aurora Serverless v2 (PostgreSQL 15互換)
- Min ACU: 0.5, Max ACU: 4
- Secrets Manager でパスワード管理
- マルチAZ: 本番はtrue、開発はfalse

### CloudFrontStack
- オリジン: API Gateway
- キャッシュポリシー: GET のみキャッシュ、Cache-Control ヘッダー尊重
- CloudFront Functions または Lambda@Edge は使わない（シンプルに保つ）
- カスタムドメイン対応 (ACM証明書)

### CacheInvalidationStack
- CloudFront Distribution ID を SSM Parameter Store `/case-server/cloudfront-distribution-id` に保存
- CDKデプロイ時に自動登録
- Lambda起動時にSSMから読み込む（環境変数ではなくSSMで管理）

### S3Stack
- CSVインポート/エクスポート用プライベートバケット
- presigned URL有効期限: 15分
- ライフサイクル: アップロードファイルは24時間で自動削除
- Lambda の IAM ロールに s3:GetObject / s3:PutObject を付与
- S3キー命名規則: `{tenant-uuid}/{timestamp}_{random8}.csv` (例: `550e8400.../20250307_a1b2c3d4.csv`)

### migrate Lambda設定
- `POST /admin/migrate` 用のLambda予約同時実行数 = 1 に設定
- 並行マイグレーションによるDB競合を防止

## ローカル開発 (docker-compose.yml)

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://case:case@db:5432/case
    depends_on: [db]

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: case
      POSTGRES_PASSWORD: case
      POSTGRES_DB: case
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
```

## Dockerfile

- マルチステージビルド
- ベースイメージ: `python:3.12-slim`
- uv でパッケージインストール
- Lambda デプロイ用と ローカル開発用を同一Dockerfileで対応

## 作業手順

1. `infra/cdk/app.py` にスタック定義のエントリーポイントを作る
2. スタックは依存関係順に: DatabaseStack → LambdaStack → CloudFrontStack
3. 環境変数 `ENVIRONMENT` (dev/prod) でスタック設定を切り替える
4. `cdk.json` に synthesizer と context を設定する
5. README に `cdk deploy` 手順を記載する
