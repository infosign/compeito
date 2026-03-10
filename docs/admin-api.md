# 管理用API仕様 (/admin/*)

AWS環境でCLIが叩く内部エンドポイント。Lambda Function URL 経由でアクセスする。
アプリ層（FastAPIミドルウェア）で `Authorization: Bearer <shared-secret>` を検証。
Docker環境では認証なし（ローカル開発用）。
エラーレスポンスは標準JSON形式（`{"error": "...", "detail": "..."}`）。CASE API の imsx_StatusInfo 形式は使わない。

**成功時の HTTP ステータスコード:**
- POST（リソース作成）: **201** Created（POST /admin/tenants）
- POST（処理実行）: **200** OK（POST import/csv, POST import/case-url, POST export/csv, POST /admin/migrate, POST /admin/cache/invalidate）
- GET: **200** OK
- PATCH: **200** OK
- DELETE: **200** OK（レスポンスボディに削除リソース情報を含むため 204 は使わない）

## エンドポイント一覧

| Path | リクエスト | レスポンス | 説明 |
|------|-----------|-----------|------|
| POST /admin/tenants | JSON body (name, is_private?) | JSON (tenant) | テナント作成。`id` は UUID v4 を自動採番 |
| GET  /admin/tenants | query: with_docs=true/false | JSON (tenant[]) | テナント一覧（private含む全件） |
| GET  /admin/tenants/{id} | - | JSON (tenant) | テナント取得（CLI の削除確認プロンプト等で使用） |
| PATCH /admin/tenants/{id} | JSON body (name?, is_private?) | JSON (tenant) | テナント更新 |
| DELETE /admin/tenants/{id} | - | JSON (message) | テナント削除（CASCADE） |
| GET  /admin/tenants/{id}/documents | - | JSON (document[]) | フレームワーク一覧 |
| GET  /admin/tenants/{id}/documents/{doc-uuid} | - | JSON (document) | フレームワーク取得（CLI の削除確認プロンプト等で使用） |
| DELETE /admin/tenants/{id}/documents/{doc-uuid} | - | JSON (message) | フレームワーク削除 |
| POST /admin/tenants/{id}/import/csv | JSON body (s3_key, doc_title?, doc_version?, doc_uuid?) | JSON (job結果) | CSVインポート |
| POST /admin/tenants/{id}/import/case-url | JSON body (url, doc_uuid?) | JSON (job結果) | 外部CASEインポート |
| POST /admin/tenants/{id}/documents/{doc-uuid}/export/csv | JSON body (format?) | JSON (presigned_url, filename) | CSVエクスポート |
| POST /admin/cache/invalidate | JSON body (tenant_id?, doc_uuid?) | JSON (message) | CloudFront invalidation。下記パターン参照 |
| POST /admin/migrate | - | JSON (message) | Alembicマイグレーション実行 |
| GET  /admin/upload-url | query: tenant_id, filename | JSON (s3_key, presigned_url) | CSVアップロード用presigned URL取得 |

`src/routers/admin.py` に実装する。

**パスパラメータの意味:**
- `{id}`（`/admin/tenants/{id}`）: テナントの `id`（= 公開URLに使われるUUID）
- `{doc-uuid}`（`/admin/tenants/{id}/documents/{doc-uuid}`）: CFDocument の `identifier`（CASE識別子）。内部PK（`id`）ではない

## レスポンススキーマ

**タイムスタンプ形式:** 全タイムスタンプフィールド（`created_at`, `last_change_date_time`）は ISO 8601 UTC（末尾 `Z`）で出力する（CASE API と同一方針）。

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
`name ASC, id ASC` でソート（Web UI のテナント一覧と同一順序）。
```json
[
  {"id": "550e8400-...", "name": "大学A", "is_private": false, "created_at": "..."},
  {"id": "6ba7b810-...", "name": "企業B", "is_private": true, "created_at": "..."}
]
```

`with_docs=true` の場合、各テナントに `documents` 配列を追加（`title ASC, identifier ASC` でソート。スタンドアロンのドキュメント一覧と同一順序）:
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
`title ASC, identifier ASC` でソート（Web UI のフレームワーク一覧と同一順序）。`item_count` は `SELECT COUNT(*) FROM cf_item WHERE cf_document_id = doc.id` で算出する。
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

### ドキュメント取得 (GET /admin/tenants/{id}/documents/{doc-uuid})
ドキュメント一覧と同一のスキーマ。CLI の `doc delete` 確認プロンプトで対象ドキュメントの名前・アイテム数を表示するために使用する。
```json
{
  "identifier": "d86774f2-...",
  "title": "高等学校学習指導要領",
  "item_count": 1557,
  "last_change_date_time": "2025-10-08T12:00:00Z"
}
```

### インポート結果 (POST import/csv, import/case-url)
```json
{
  "document_identifier": "d86774f2-...",
  "document_title": "高等学校学習指導要領",
  "items_created": 1523,
  "items_updated": 34,
  "items_skipped": 3,
  "associations_created": 2045,
  "associations_updated": 0,
  "associations_skipped": 0,
  "item_types_created": 5,
  "item_types_updated": 0,
  "item_types_existing": 2,
  "item_types_skipped": 0,
  "subjects_created": 3,
  "subjects_updated": 0,
  "subjects_existing": 0,
  "subjects_skipped": 0,
  "concepts_created": 12,
  "concepts_updated": 0,
  "concepts_existing": 0,
  "concepts_skipped": 0,
  "licenses_created": 0,
  "licenses_updated": 0,
  "licenses_existing": 0,
  "licenses_skipped": 0,
  "association_groupings_created": 0,
  "association_groupings_updated": 0,
  "association_groupings_existing": 0,
  "association_groupings_skipped": 0,
  "warnings": [
    "Row 45: fullStatement is empty, skipped",
    "Row 203: Parent 'f1a2b3c4-...' not found, treated as root"
  ]
}
```

### 削除の副作用

- **テナント削除（DELETE /admin/tenants/{id}）**: 配下の全リソース（cf_document, cf_item, cf_association, lookup テーブル全て）が CASCADE 削除される
- **ドキュメント削除（DELETE /admin/tenants/{id}/documents/{doc-uuid}）**: 配下の cf_item, cf_association が CASCADE 削除される。lookup リソース（cf_item_type, cf_subject, cf_concept, cf_license, cf_association_grouping）はテナント所有のため削除されず、orphan レコードが残りうる（db-schema.md 参照）。他ドキュメントの CFAssociation が削除ドキュメントのアイテムを参照している場合、dangling reference となる

### 削除レスポンス (DELETE)

削除されたリソースの情報を含める（CLI が `--force` モードで確認プロンプトをスキップした場合にもリソース名を表示できるようにするため）:

- DELETE /admin/tenants/{id}:
```json
{"message": "Tenant deleted successfully", "id": "550e8400-...", "name": "大学A"}
```

- DELETE /admin/tenants/{id}/documents/{doc-uuid}:
```json
{"message": "Document deleted successfully", "identifier": "d86774f2-...", "title": "高等学校学習指導要領"}
```

### 操作成功 (POST migrate, POST cache/invalidate)

- POST /admin/migrate: `"Migration completed successfully"`
- POST /admin/cache/invalidate: `"Cache invalidation submitted successfully"`

```json
{"message": "Migration completed successfully"}
```

### presigned URL (GET /admin/upload-url)

**`s3_key` の命名規則:** `uploads/{tenant_id}/{uuid}-{filename}`（UUID v4 をプレフィックスに付与し、並行アップロードでの上書きを防止する。`filename` はクエリパラメータの値をそのまま使用）。

```json
{
  "s3_key": "uploads/550e8400-.../a1b2c3d4-5678-90ab-cdef-1234567890ab-framework.csv",
  "presigned_url": "https://s3.amazonaws.com/..."
}
```

### エクスポート結果 (POST export/csv)

**`format` パラメータ:**
- `"custom"`（デフォルト）: 独自形式でエクスポート
- `"opensalt"`: OpenSALT互換形式でエクスポート（Phase 2）。Phase 1 では **400** (`{"error": "bad_request", "detail": "opensalt format is not yet supported"}`) を返す
- 上記以外の値 → **400** (`{"error": "bad_request", "detail": "Invalid format: '...'. Valid values: custom, opensalt"}`)
- `format` 省略時は `"custom"` として扱う

**`filename` の命名規則:** `export-{document_identifier}-{uuid}.csv`（例: `export-d86774f2-1234-5678-9abc-def012345678-a1b2c3d4-5678-90ab-cdef-1234567890ab.csv`）。UUID v4 をサフィックスに付与し、同一ドキュメントの並行エクスポートでの S3 オブジェクト競合を防止する。S3オブジェクトキーにもこのファイル名を使用する。

```json
{
  "presigned_url": "https://s3.amazonaws.com/...",
  "filename": "export-d86774f2-1234-5678-9abc-def012345678-a1b2c3d4-5678-90ab-cdef-1234567890ab.csv",
  "item_count": 1523
}
```
`item_count` はエクスポートされた CFItem の件数（CLI の出力「Exported {N} items to ...」に使用する）。

## 認証エラー

Docker環境では認証なし。AWS環境で Bearer token が不正または未指定の場合:

### 401 Unauthorized（トークン未指定）
`Authorization` ヘッダーが存在しない、または `Bearer` スキームでない（例: `Basic ...`）場合:
```json
{"error": "unauthorized", "detail": "Authorization header is required"}
```

### 401 Unauthorized（トークン不正）
`Bearer` スキームだがトークン値が空（`Authorization: Bearer` のみ）、または不正な場合:
```json
{"error": "unauthorized", "detail": "Invalid bearer token"}
```

## 共通エラー

### リクエストボディの JSON パースエラー

JSON ボディを期待するエンドポイント（POST/PATCH）で、リクエストボディが不正な JSON の場合:
```json
{"error": "bad_request", "detail": "Invalid JSON in request body"}
```
FastAPI のデフォルト 422 レスポンスは使用せず、Admin API の標準エラー形式（400）に変換する。
リクエストボディは JSON オブジェクト（`{...}`）であること。有効な JSON だがオブジェクト型でない場合（文字列・配列・数値等）も `Invalid JSON in request body` として扱う。
リクエストボディに仕様にないフィールドが含まれる場合は、そのフィールドを無視する（エラーにしない）。
フィールドの値が `null` の場合は「キー未指定」と同等に扱う（例: `{"name": null}` は `name` キーが存在しないのと同じ扱い。POST /admin/tenants では「name is required」エラー、PATCH では既存値保持）。

### パスパラメータのバリデーション

CASE API と同様のバリデーションを行う:
- `{id}`（テナントUUID）が UUID 形式でない → **400** (`{"error": "bad_request", "detail": "Invalid UUID format: '...'"}`)
- UUID 形式だがテナントが存在しない → **404** (`{"error": "not_found", "detail": "Tenant not found: '...'"}`)
- `{doc-uuid}` が UUID 形式でない → **400** (`{"error": "bad_request", "detail": "Invalid UUID format: '...'"}`)
- UUID 形式だがパスの `{id}` テナント内にドキュメントが存在しない → **404** (`{"error": "not_found", "detail": "Document not found: '...'"}`)

### 404 Not Found（テナント/ドキュメント不在）
```json
{"error": "not_found", "detail": "Tenant not found: '99999999-...'"}
```

### 500 Internal Server Error
```json
{"error": "internal_server_error", "detail": "Internal server error"}
```
予期しないサーバーエラー（DB接続障害等）が発生した場合に返す。`detail` にはユーザー向けの汎用メッセージを表示し、内部エラー情報は含めない（セキュリティ上、スタックトレースや DB エラー詳細はログにのみ出力する）。

### 400 Bad Request（バリデーションエラー）

各エンドポイントの必須フィールドが欠落・空・型不正の場合:
- POST /admin/tenants: `name` が未指定、空文字列、または空白文字のみ（前後空白をトリムした後に空） → `{"error": "bad_request", "detail": "name is required"}`。バリデーション通過後は前後空白をトリムした値を保存する（例: `"  大学A  "` → `"大学A"`）
- POST /admin/tenants: `is_private` がブール値でない（指定された場合） → `{"error": "bad_request", "detail": "is_private must be a boolean"}`
- PATCH /admin/tenants/{id}: `name` が空文字列または空白文字のみ（前後空白をトリムした後に空） → `{"error": "bad_request", "detail": "name must not be empty"}`。バリデーション通過後は前後空白をトリムした値を保存する（`name` キー自体が未指定の場合は既存値を保持。`is_private` も同様に未指定なら既存値保持。両方とも未指定の場合は既存値をそのまま返す）
- PATCH /admin/tenants/{id}: `is_private` がブール値でない（指定された場合） → `{"error": "bad_request", "detail": "is_private must be a boolean"}`
- POST import/csv: `s3_key` が未指定または空文字列 → `{"error": "bad_request", "detail": "s3_key is required"}`
- POST import/case-url: `url` が未指定または空文字列 → `{"error": "bad_request", "detail": "url is required"}`
- POST cache/invalidate: `tenant_id` と `doc_uuid` が両方未指定 → ルート `/` のみ invalidate する（テナント作成時用）。`tenant_id` のみ指定（`doc_uuid` なし） → `/{tenant_id}/*` を invalidate し、追加で `/` も invalidate する（テナント更新・テナント削除時用）。`doc_uuid` のみ指定（`tenant_id` なし） → **400** (`{"error": "bad_request", "detail": "tenant_id is required when doc_uuid is specified"}`)。`tenant_id` + `doc_uuid` 指定 → architecture.md のドキュメント更新パターン（5パス）で invalidate する
- GET /admin/upload-url: `tenant_id` が未指定 → `{"error": "bad_request", "detail": "tenant_id is required"}`
- GET /admin/upload-url: `filename` が未指定 → `{"error": "bad_request", "detail": "filename is required"}`
- GET /admin/upload-url: `filename` のバリデーション → 英数字・ハイフン・アンダースコア・ドットのみ許可（`[a-zA-Z0-9._-]+`）。255文字以下。不正な場合は **400** (`{"error": "bad_request", "detail": "Invalid filename"}`)
- GET /admin/tenants: `with_docs` が `true`/`false` 以外の値 → `with_docs=false` として扱う（エラーにしない）。`with_docs` パラメータ省略時も `false`

### インポート/エクスポートのビジネスロジックエラー

インポート処理中にビジネスロジックエラー（import-logic.md で「エラー終了」と定義されているケース）が発生した場合は **400** を返す:
```json
{"error": "import_error", "detail": "Document title is required"}
```

主なエラーケース:
- CSVインポート: タイトル未指定（新規作成時）、Is Part Of がUUID形式でない、データ行が0件で新規ドキュメント作成もできない場合、S3オブジェクトの読み取り失敗（下記参照）、CSV ファイルが UTF-8 でない
- 外部CASEインポート: 接続エラー、HTTPエラー、JSONパースエラー、CFPackage構造不正、SSL証明書エラー
- 共通: 指定ドキュメントが見つからない（`doc_uuid` パラメータ、上記 UUID バリデーションで捕捉）

**S3読み取りエラー（CSVインポート）:**
Lambda が `s3_key` で指定された S3 オブジェクトを読み取れない場合（オブジェクトが存在しない、アップロードが完了していない、S3 サービスエラー等）は **400** を返す:
```json
{"error": "import_error", "detail": "Failed to read CSV from S3: {error}"}
```

これらは import-logic.md のエラーハンドリングに従う。部分的に成功した場合（行スキップ等）は **200** でインポート結果を返し、`warnings` 配列にスキップ理由を含める。

### body/query 内の UUID パラメータのバリデーション

パスパラメータと同様に、リクエストボディ/クエリ内の UUID パラメータもバリデーションする:
- `tenant_id`（`GET /admin/upload-url`）: UUID 形式でない → **400**、UUID 形式だがテナントが存在しない → **404**
- `tenant_id`（`POST cache/invalidate`、任意パラメータ）: 指定された場合、UUID 形式でない → **400**。テナントの存在チェックは行わない（削除済みテナントのキャッシュ無効化に対応するため）
- `doc_uuid`（`POST cache/invalidate`、任意パラメータ）: 指定された場合、UUID 形式でない → **400**。ドキュメントの存在チェックは行わない（削除済みドキュメントのキャッシュ無効化に対応するため。`doc_uuid` は invalidation パスの構築にのみ使用する）
- `doc_uuid`（`POST import/csv`, `POST import/case-url`、任意パラメータ）: 指定された場合、UUID 形式でない → **400**、UUID 形式だがパスの `{id}` テナント内にドキュメントが存在しない → **404**（エラーメッセージ形式はパスパラメータと同一）

## 大規模ファイルのS3経由転送

Lambda API Gatewayの6MBリクエスト/レスポンス制限を回避するため、
CSVのインポート/エクスポートはS3経由で行う。

**インポートフロー:**
```
1. CLI: GET /admin/upload-url → S3 presigned upload URL取得
2. CLI: CSVファイルをS3に直接PUT（CLIがAWS署名なしでアップロード可能）
3. CLI: POST /admin/tenants/{id}/import/csv { s3_key: "..." } → LambdaがS3からCSVを読み込んでDB投入
```

**エクスポートフロー:**
```
1. CLI: POST /admin/tenants/{id}/documents/{doc-uuid}/export/csv → LambdaがCSV生成してS3にアップロード
2. Lambda: S3 presigned download URLを返す
3. CLI: presigned URLからCSVをダウンロード
```

S3バケットはCDKでprivateとして作成。presigned URLの有効期限は15分。
