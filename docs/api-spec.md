# CASE v1.1 API 仕様

APIパス: `/{tenant}/ims/case/v1p1/` (conformance必須) + `/{tenant}/ims/case/v1p0/` (後方互換)

## エンドポイント一覧

| Path | レスポンスルートキー | 説明 | 必須 |
|------|---------------------|------|------|
| GET /{tenant}/ims/case/v1p1/CFPackages/{id} | `{"CFPackage": {...}}` | パッケージ取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFDocuments | `{"CFDocuments": [...]}` | 文書一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFDocuments/{id} | `{"CFDocument": {...}}` | 文書取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItems/{id} | `{"CFItem": {...}}` | 項目取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItems/{id}/associations | `{"CFAssociations": [...]}` | 項目の関連一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociations/{id} | `{"CFAssociation": {...}}` | 関連取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings | `{"CFAssociationGroupings": [...]}` | 関連グループ一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id} | `{"CFAssociationGrouping": {...}}` | 関連グループ取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFConcepts | `{"CFConcepts": [...]}` | コンセプト一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFConcepts/{id} | `{"CFConcept": {...}}` | コンセプト取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItemTypes | `{"CFItemTypes": [...]}` | 項目種別一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItemTypes/{id} | `{"CFItemType": {...}}` | 項目種別取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFLicenses | `{"CFLicenses": [...]}` | ライセンス一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFLicenses/{id} | `{"CFLicense": {...}}` | ライセンス取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFSubjects | `{"CFSubjects": [...]}` | 教科一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFSubjects/{id} | `{"CFSubject": {...}}` | 教科取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFRubrics/{id} | `{"CFRubric": {...}}` | ルーブリック取得 | Phase 2 |

## CFPackage レスポンス構造

```json
{
  "CFPackage": {
    "CFDocument": {...},
    "CFItems": [...],
    "CFAssociations": [...],
    "CFDefinitions": {
      "CFItemTypes": [...],
      "CFSubjects": [...],
      "CFConcepts": [...],
      "CFLicenses": [...],
      "CFAssociationGroupings": [...]
    },
    "CFRubrics": [...]
  }
}
```
- `CFDefinitions` 内の各キーはデータがなければ省略する
- `CFRubrics` は Phase 2。データがなければキー自体を省略する

レスポンスにカスタムラッパー (`{"data": ...}` 等) を**追加してはならない**。
エラー時は `{"imsx_codeMajor": "failure", ...}` をルートレベルに直接返す（エラー形式参照）。

## テナントバリデーション（全エンドポイント共通）

- `{tenant-uuid}` が UUID 形式でない → **400** (`imsx_codeMinorFieldValue: invalid_uuid`)
- UUID 形式だがテナントが存在しない → **404** (`imsx_codeMinorFieldValue: unknownobject`)
- `/uri/{uuid}` はテナントスコープ内で検索する。別テナントの UUID を指定した場合は **404**

## ページネーション

CASE v1.1準拠。全一覧エンドポイントに `limit`(デフォルト100, 最大500) / `offset`(デフォルト0) を実装。
`sort` / `orderBy` / `filter` / `fields` パラメータは Phase 1 では実装しない（無視する）。
レスポンスに総件数は含めない（CASE v1.1仕様に総件数フィールドはない）。

**バリデーション:**
- `limit` < 0 → 400 (`invalid_selection_field`)
- `limit` > 500 → 500 として扱う（エラーにしない）
- `limit` が整数でない → 400 (`invalid_selection_field`)
- `offset` < 0 → 400 (`invalid_selection_field`)
- `offset` が整数でない → 400 (`invalid_selection_field`)

## ヘルスチェック

```
GET /health
```
レスポンス (200):
```json
{"status": "ok"}
```
- 認証不要、テナントパス不要
- Cache-Control は設定しない（CloudFront でキャッシュしない）
- DB接続確認は行わない（Lambda コールドスタートの高速化を優先）

## v1p0 後方互換

`/ims/case/v1p0/` パスへのリクエストは `/ims/case/v1p1/` に 301リダイレクト。
CASE API は GET のみのため 301 で問題ない（POST でメソッドが変わるリスクなし）。
ルーターを二重に実装しない。`src/main.py` にミドルウェアを1つ追加して一括処理する。
リダイレクト先はパスの `v1p0` を `v1p1` に置換したもの（クエリパラメータはそのまま引き継ぐ）。

```python
# src/main.py のミドルウェア例
@app.middleware("http")
async def redirect_v1p0(request, call_next):
    if "/ims/case/v1p0/" in request.url.path:
        new_path = request.url.path.replace("/ims/case/v1p0/", "/ims/case/v1p1/")
        new_url = str(request.url).replace(request.url.path, new_path)
        return RedirectResponse(url=new_url, status_code=301)
    return await call_next(request)
```

## LinkURI型

`CFPackageURI`, `CFDocumentURI`, `CFOriginNodeURI`, `CFDestinationNodeURI`, `CFItemTypeURI` 等は
文字列ではなく複合オブジェクト:
```json
{"title": "文書タイトル", "identifier": "uuid", "uri": "https://..."}
```
Pydantic で `LinkURIType` クラスを定義して共有する (`src/schemas/common.py`)。
DBには `_uri` (VARCHAR) と `_identifier` (UUID) カラムを持ち、`title` はJOINまたはアプリ層で解決する。

## エラーレスポンス形式

CASE v1.1 の imsx_StatusInfo 形式。ルートレベルに直接フィールドを配置する（ラッパーオブジェクトなし）:
```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Not found",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {"imsx_codeMinorFieldName": "sourcedId", "imsx_codeMinorFieldValue": "unknownobject"}
    ]
  }
}
```
- フィールド名は全て小文字始まり（`imsx_codeMajor` ○、`imsx_CodeMajor` ✗）
- `imsx_codeMajor`: `success` / `processing` / `failure` / `unsupported`
- `imsx_severity`: `status` / `warning` / `error`
- `imsx_description`: 人間向けの説明文字列（任意）
- `imsx_codeMinor`: 任意。ネストされたオブジェクト（文字列ではない）
- `imsx_codeMinorFieldValue`: `fullsuccess` / `invalid_sort_field` / `invalid_selection_field` / `forbidden` / `unauthorised_request` / `internal_server_error` / `unknownobject` / `server_busy` / `invalid_uuid`
- HTTPステータスコード対応: 400→`failure/error`, 404→`failure/error`+`unknownobject`, 500→`failure/error`+`internal_server_error`

## コンテントネゴシエーション

**コンテントネゴシエーションは使わない。** CloudFrontがAcceptヘッダーを無視して
キャッシュするため、HTML/JSONが混在するリスクがある。
- Web UI: `/{tenant}/uri/{uuid}` → 常にHTML
- CASE API: `/{tenant}/ims/case/v1p1/CFItems/{uuid}` → 常にJSON
