# 管理用API仕様 (/admin/*)

AWS環境でCLIが叩く内部エンドポイント。Lambda Function URL 経由でアクセスする。
アプリ層（FastAPIミドルウェア）で `Authorization: Bearer <shared-secret>` を検証。
Docker環境では認証なし（ローカル開発用）。
エラーレスポンスは標準JSON形式（`{"error": "...", "detail": "..."}`）。CASE API の imsx_StatusInfo 形式は使わない。

## エンドポイント一覧

| Path | リクエスト | レスポンス | 説明 |
|------|-----------|-----------|------|
| POST /admin/tenants | JSON body (name, is_private?) | JSON (tenant) | テナント作成 |
| GET  /admin/tenants | query: with_docs=bool | JSON (tenant[]) | テナント一覧（private含む全件） |
| PATCH /admin/tenants/{id} | JSON body (name?, is_private?) | JSON (tenant) | テナント更新 |
| DELETE /admin/tenants/{id} | - | JSON (message) | テナント削除（CASCADE） |
| GET  /admin/tenants/{id}/documents | - | JSON (document[]) | フレームワーク一覧 |
| DELETE /admin/tenants/{id}/documents/{doc-uuid} | - | JSON (message) | フレームワーク削除 |
| POST /admin/tenants/{id}/import/csv | JSON body (s3_key, doc_title, doc_uuid?) | JSON (job結果) | CSVインポート |
| POST /admin/tenants/{id}/import/case-url | JSON body (url, doc_uuid?) | JSON (job結果) | 外部CASEインポート |
| POST /admin/tenants/{id}/documents/{doc-uuid}/export/csv | JSON body (format?) | JSON (s3_presigned_url) | CSVエクスポート |
| POST /admin/cache/invalidate | JSON body (tenant_id, doc_id?) | JSON (message) | CloudFront invalidation |
| POST /admin/migrate | - | JSON (message) | Alembicマイグレーション実行 |
| GET  /admin/upload-url | query: tenant_id, filename | JSON (s3_key, presigned_url) | CSVアップロード用presigned URL取得 |

`src/routers/admin.py` に実装する。

## レスポンススキーマ

### テナント（POST/PATCH/GET共通）
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "大学A",
  "is_private": false,
  "created_at": "2025-01-01T00:00:00Z"
}
```

### テナント一覧 (GET /admin/tenants)
```json
[
  {"id": "550e8400-...", "name": "大学A", "is_private": false, "created_at": "..."},
  {"id": "6ba7b810-...", "name": "企業B", "is_private": true, "created_at": "..."}
]
```

`with_docs=true` の場合、各テナントに `documents` 配列を追加:
```json
[
  {
    "id": "550e8400-...", "name": "大学A", "is_private": false, "created_at": "...",
    "documents": [
      {"identifier": "d86774f2-...", "title": "高等学校学習指導要領", "item_count": 1557, "last_change_date_time": "..."}
    ]
  }
]
```

### ドキュメント一覧 (GET /admin/tenants/{id}/documents)
```json
[
  {
    "identifier": "d86774f2-...",
    "title": "高等学校学習指導要領",
    "item_count": 1557,
    "last_change_date_time": "2025-10-08T12:00:00Z"
  }
]
```

### インポート結果 (POST import/csv, import/case-url)
```json
{
  "document_identifier": "d86774f2-...",
  "document_title": "高等学校学習指導要領",
  "items_created": 1523,
  "items_updated": 34,
  "items_skipped": 3,
  "item_types_created": 5,
  "warnings": [
    "Row 45: fullStatement is empty, skipped",
    "Row 203: Parent 'f1a2b3c4-...' not found, treated as root"
  ]
}
```

### 削除/操作成功 (DELETE, POST migrate, POST cache/invalidate)
```json
{"message": "Tenant deleted successfully"}
```

### presigned URL (GET /admin/upload-url)
```json
{
  "s3_key": "uploads/550e8400-.../framework.csv",
  "presigned_url": "https://s3.amazonaws.com/..."
}
```

### エクスポート結果 (POST export/csv)
```json
{
  "presigned_url": "https://s3.amazonaws.com/...",
  "filename": "export-d86774f2-....csv"
}
```

## 認証エラー

Docker環境では認証なし。AWS環境で Bearer token が不正または未指定の場合:

### 401 Unauthorized（トークン未指定）
```json
{"error": "unauthorized", "detail": "Authorization header is required"}
```

### 401 Unauthorized（トークン不正）
```json
{"error": "unauthorized", "detail": "Invalid bearer token"}
```

## 共通エラー

### 404 Not Found（テナント/ドキュメント不在）
```json
{"error": "not_found", "detail": "Tenant not found: '99999999-...'"}
```

### 400 Bad Request（バリデーションエラー）
```json
{"error": "bad_request", "detail": "name is required"}
```

## 大規模ファイルのS3経由転送

Lambda API Gatewayの6MBリクエスト/レスポンス制限を回避するため、
CSVのインポート/エクスポートはS3経由で行う。

**インポートフロー:**
```
1. CLI: GET /admin/upload-url → S3 presigned upload URL取得
2. CLI: CSVファイルをS3に直接PUT（CLIがAWS署名なしでアップロード可能）
3. CLI: POST /admin/import/csv { s3_key: "..." } → LambdaがS3からCSVを読み込んでDB投入
```

**エクスポートフロー:**
```
1. CLI: POST /admin/export/csv → LambdaがCSV生成してS3にアップロード
2. Lambda: S3 presigned download URLを返す
3. CLI: presigned URLからCSVをダウンロード
```

S3バケットはCDKでprivateとして作成。presigned URLの有効期限は15分。
