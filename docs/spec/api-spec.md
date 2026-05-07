# CASE v1.1 API 仕様

APIパス: `/{tenant}/ims/case/v1p1/` (conformance必須) + `/{tenant}/ims/case/v1p0/` (後方互換)

**パスパラメータ `{id}` の意味:** 全エンドポイントの `{id}` は CASE 識別子（DB の `identifier` カラム）を指す。内部PK（`id` カラム）ではない。

## エンドポイント一覧

CASE v1.1 準拠の 12 エンドポイント:

| Path | レスポンスルートキー | 説明 | CASE v1.1 |
|------|---------------------|------|-----------|
| GET /{tenant}/ims/case/v1p1/CFPackages/{id} | `{"CFPackage": {...}}` | パッケージ取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFDocuments | `{"CFDocuments": [...]}` | 文書一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFDocuments/{id} | `{"CFDocument": {...}}` | 文書取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItems/{id} | `{"CFItem": {...}}` | 項目取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItemAssociations/{id} | `{"CFItem": {...}, "CFAssociations": [...]}` | 項目の関連一覧 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociations/{id} | `{"CFAssociation": {...}}` | 関連取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings/{id} | `{"CFAssociationGrouping": {...}}` | 関連グループ取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFConcepts/{id} | `{"CFConcepts": [...]}` | コンセプト取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFItemTypes/{id} | `{"CFItemTypes": [...]}` | 項目種別取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFLicenses/{id} | `{"CFLicense": {...}}` | ライセンス取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFSubjects/{id} | `{"CFSubjects": [...]}` | 教科取得 | ○ |
| GET /{tenant}/ims/case/v1p1/CFRubrics/{id} | `{"CFRubric": {...}}` | ルーブリック取得 | ○ |

**独自拡張エンドポイント**（CASE v1.1 仕様外。テナント内の全リソースを一覧取得。利便性のため提供）:

| Path | レスポンスルートキー | 説明 |
|------|---------------------|------|
| GET /{tenant}/ims/case/v1p1/CFItemTypes | `{"CFItemTypes": [...]}` | 項目種別一覧 |
| GET /{tenant}/ims/case/v1p1/CFSubjects | `{"CFSubjects": [...]}` | 教科一覧 |
| GET /{tenant}/ims/case/v1p1/CFConcepts | `{"CFConcepts": [...]}` | コンセプト一覧 |
| GET /{tenant}/ims/case/v1p1/CFLicenses | `{"CFLicenses": [...]}` | ライセンス一覧 |
| GET /{tenant}/ims/case/v1p1/CFAssociationGroupings | `{"CFAssociationGroupings": [...]}` | 関連グループ一覧 |
| GET /{tenant}/ims/case/v1p1/CFRubrics?doc={id} | `{"CFRubrics": [...]}` | ルーブリック一覧（`doc` 必須） |

**CFRubrics 一覧の `doc` パラメータについて:** CFRubric は CFDefinitions 系（CFItemType 等）と異なり、特定の CFDocument に所属する。CASE v1.1 の CFRubricDType には所属 Document を示すフィールドがないため、テナント全体で返すとどの Document のルーブリックか判別できない。そのため `doc` クエリパラメータ（CFDocument の identifier, UUID）を**必須**とする。`doc` 未指定は 400、不正な UUID は 400、Document が存在しない場合は 404 を返す。

**Set 型エンドポイント（`/CFConcepts/{id}`, `/CFSubjects/{id}`, `/CFItemTypes/{id}`）**: CASE v1.1 仕様に従い、それぞれ Set 型（`CFConceptSetDType`, `CFSubjectSetDType`, `CFItemTypeSetDType`）を返す。配列の先頭は要求されたリソース、後続は `hierarchyCode` の階層下に位置する子孫リソースとなる。子孫の判定は文字列マッチで行い、対象の `hierarchyCode` を `<root>` とすると `<root>.` で始まる `hierarchyCode` を持つレコードを子孫として含める（例: `<root>` が `"1"` の場合、`"1.1"`, `"1.2.3"` 等が該当）。子孫の並び順は `hierarchyCode` の昇順（同値時は `identifier` 昇順）。要求されたリソースの `hierarchyCode` が NULL の場合、または該当する子孫が存在しない場合は、要求されたリソース 1 件のみを返す。`/CFLicenses/{id}` は単一オブジェクト `CFLicenseDType` を返す（Set 型ではない）。

**lookup リソースの必須フィールドに関する準拠性（Phase 2 対応）:**
CASE v1.1 OpenAPI 仕様では、lookup リソースの一部フィールドが "required"（non-nullable）として定義されている:
- CFItemType: `description`, `hierarchyCode`
- CFSubject: `hierarchyCode`
- CFConcept: `hierarchyCode`
- CFLicense: `licenseText`

Phase 1 ではこれらのフィールドを DB 上 nullable として扱い、値がない場合は `null` を返す（CSV インポートで自動生成された lookup レコードではこれらのフィールドは常に NULL）。Phase 2 の 1EdTech Conformance テスト対応で、`null` の代わりに空文字列 `""` を返すか、スキーマ上 nullable として扱うかを検討する。

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
- `CFItems` と `CFAssociations` はデータがなくても空配列 `[]` として常に含める（CASE v1.1 OpenAPI では `CFItems` / `CFAssociations` は required ではなく省略可能だが、クライアントの利便性のため常に含める）。いずれも `cf_document_id` でフィルタする（このドキュメントに属するリソースのみ。他ドキュメントからこのドキュメントのアイテムを参照する Association は含まない）
- `CFDefinitions` はデータがなければオブジェクトごと省略する。内部の各キーもデータがなければ省略する（`exclude_none=False` グローバルポリシーの例外。CFDefinitions 内の空配列キーは `null` として含めるのではなく、キー自体を省略する。Pydantic のカスタムシリアライザ（`model_serializer` 等）で空配列のキーを除外する。`exclude_none=True` は `None` 値のみ除外し空配列 `[]` は除外しないため、それだけでは不十分）
- `CFDefinitions` に含めるスコープ: このドキュメントのリソースから参照されている定義のみ（テナント内の全定義ではない）。具体的には: CFItemTypes = ドキュメント配下の CFItem が `cf_item_type_id` で参照するもの、CFSubjects = CFDocument および配下の CFItem の `subject_uri` から参照されるもの、CFConcepts = ドキュメント配下の CFItem が `cf_concept_id` で参照するもの、CFLicenses = CFDocument または配下の CFItem が `cf_license_id` で参照するもの、CFAssociationGroupings = ドキュメント配下の CFAssociation が `cf_association_grouping_id` で参照するもの
- `CFRubrics` は `CFItems` / `CFAssociations` と同様に空配列 `[]` として常に含める（`CFRubrics` は配列型であり、CFDefinitions のオブジェクト型省略ルールとは異なる）
- **CFPackage 内のソート順**: CFItems・CFAssociations・CFDefinitions 内の各配列は `identifier ASC` で並べる（一覧エンドポイントのデフォルトソート順と統一し、決定的な出力を保証する）
- **CFPackage 内のリソーススキーマ（CFPckg* 型）**: CASE v1.1 では CFPackage 内のリソースはスタンドアロン型とは異なる CFPckg* 型を使用する:
  - `CFPckgDocument`: スタンドアロン `CFDocument` から `CFPackageURI` を**除外**（CFPackage 自体がこのドキュメントを包含しているため冗長）
  - `CFPckgItem`: スタンドアロン `CFItem` から `CFDocumentURI` を**除外**（CFPackage のコンテキストからドキュメントが明確なため冗長）
  - `CFPckgAssociation`: スタンドアロン `CFAssociation` から `CFDocumentURI` を**除外**（同上）
  - CFDefinitions 内の各リソース（CFItemType, CFSubject 等）はスタンドアロンと同一スキーマ
  - Pydantic で CFPckg* 用の派生スキーマを定義し、`CFPackageURI` / `CFDocumentURI` フィールドを除外する

レスポンスにカスタムラッパー (`{"data": ...}` 等) を**追加してはならない**。
**null フィールドの扱い:** null 許容フィールドはレスポンスに含める方針とする（Pydantic の `exclude_none=False`）。全エンドポイントで同一の方針を適用し、一貫性を優先する。
エラー時は `{"imsx_codeMajor": "failure", ...}` をルートレベルに直接返す（エラー形式参照）。

## CFItemAssociations レスポンス構造

CASE v1.1 の `CFAssociationSetDType` 形式。対象 CFItem と、そのアイテムに関連する全 Association を返す:
```json
{
  "CFItem": {...},
  "CFAssociations": [...]
}
```
- `CFItem`: 対象アイテムのスタンドアロンスキーマ（`GET /CFItems/{id}` と同一。`CFDocumentURI` を含む）
- `CFAssociations`: 対象アイテムに関連する全 Association の配列。各 Association は `CFDocumentURI` を**含まない**（CASE v1.1 の `CFPckgAssociationDType`。CFPackage 内の CFAssociation と同じスキーマ）
- `CFAssociations` はデータがなくても空配列 `[]` として常に含める（CASE v1.1 OpenAPI の CFAssociationSetDType は `CFAssociations` を required + `minItems: 1` と定義しているが、Association がないアイテムに対して空配列を返すのは実運用上必要なため、空配列を許容する）

## バリデーション（全エンドポイント共通）

**テナントUUID:**
- `{tenant-uuid}` が UUID 形式でない → **400** (`imsx_codeMinorFieldValue: invalid_uuid`)（CASE v1.1 仕様では invalid UUID を 404 で返す定義もあるが、本システムでは UUID 形式不正と リソース未存在を区別するため 400 を返す）
- UUID 形式だがテナントが存在しない → **404** (`imsx_codeMinorFieldValue: unknownobject`)

**リソースID:**
- 全リソース取得エンドポイントはテナントスコープ内で検索する（パスの `{tenant-uuid}` で指定されたテナント内のみ）
- `{id}`（`/CFItems/{id}`, `/CFDocuments/{id}` 等）が UUID 形式でない → **400** (`imsx_codeMinorFieldValue: invalid_uuid`)
- UUID 形式だがテナント内にリソースが存在しない → **404** (`imsx_codeMinorFieldValue: unknownobject`)
- `GET /CFItemAssociations/{id}` で `{id}` のアイテムが存在しない → **404** (`imsx_codeMinorFieldValue: unknownobject`)（空配列ではなく404を返す）
- `GET /CFItemAssociations/{id}` の検索スコープ: テナント内の全ドキュメントから `origin_node_identifier = {id}` OR `destination_node_identifier = {id}` の Association を返す（アイテムが属するドキュメントに限定しない）

**スコープ:**
- `/uri/{uuid}` はテナントスコープ内で検索する。別テナントの UUID を指定した場合は **404**
- `/uri/{uuid}` の検索順序: cf_document → cf_item → cf_association → cf_item_type → cf_subject → cf_concept → cf_license → cf_association_grouping（最初にヒットした時点で検索を打ち切る）。同一 UUID が複数テーブルに存在する場合（テーブル間の UNIQUE 制約はないため理論上可能）、この順序で最初にマッチしたリソースを返す

## ページネーション

CASE v1.1準拠。全一覧エンドポイントに `limit`(デフォルト100, 最大500) / `offset`(デフォルト0) を実装。
対象: `CFDocuments`, `CFItemAssociations/{id}`, `CFItemTypes`, `CFSubjects`, `CFConcepts`, `CFLicenses`, `CFAssociationGroupings`（レスポンスが配列の全エンドポイント）。CASE v1.1 OpenAPI ではページネーションパラメータは `GET /CFDocuments` のみに定義されているが、本システムでは利便性のため全一覧エンドポイントに拡張適用する。
`CFPackages/{id}` はページネーション対象外。CASE v1.1 仕様に従い、CFPackage 内の CFItems・CFAssociations・CFDefinitions は全件を返す。**注意**: API Gateway のレスポンスペイロード上限は 10MB。大規模ドキュメント（10,000+ アイテム）ではこの制限に達する可能性がある。制限超過時は API Gateway が 502 を返す。必要に応じて Lambda Function URL 経由での直接アクセスを検討する（Phase 2 以降）。
`sort` / `orderBy` / `filter` / `fields` パラメータは Phase 1 では実装しない（無視する）。
レスポンスに総件数は含めない。CASE v1.1 OpenAPI スキーマでは `GET /CFDocuments` に `X-Total-Count` レスポンスヘッダーと `links`（next, last, first, prev）が定義されているが、本システムでは Phase 1 では実装しない（Phase 2 で検討）。
デフォルトソート順: 全一覧エンドポイントは `identifier ASC` で並べる（決定的な順序を保証し、ページ間の重複・欠落を防ぐ）。
スコープ: 全一覧エンドポイントはテナント内の全件を返す（ドキュメントでフィルタリングしない）。`CFDocuments` はテナント内の全ドキュメント、`CFItemTypes` / `CFSubjects` / `CFConcepts` / `CFLicenses` / `CFAssociationGroupings` はテナント内の全 lookup リソースを返す。`CFItems/{id}/associations` はテナント内の全ドキュメントを横断して検索する（api-spec.md バリデーション節参照）。CFPackage 内の CFDefinitions はドキュメントから参照されている定義のみに絞り込むが、一覧APIは絞り込まない。

**バリデーション:**
- `limit` = 0 → 空配列を返す（有効なリクエストとして扱う。CASE v1.1 OpenAPI は `minimum: 1` を定義しているが、実用上 `limit=0` は空結果を返す有効なリクエストとして扱う）
- `limit` < 0 → 400 (`invalid_selection_field`)
- `limit` > 500 → 500 として扱う（エラーにしない）
- `limit` が整数でない → 400 (`invalid_selection_field`)
- `offset` < 0 → 400 (`invalid_selection_field`)
- `offset` が整数でない → 400 (`invalid_selection_field`)
- `offset` > 100000 → 100000 として扱う（`limit` の cap と同様。PostgreSQL の OFFSET に渡す上限を設ける）
- `offset` が総件数以上 → 空配列を返す（エラーではない）

## レスポンスヘッダー（Cache-Control）

**正常レスポンス（200）:** 全 CASE API エンドポイントに `Cache-Control: public, max-age=3600` を設定する（public/private テナント共通）。

**エラーレスポンス（4xx/5xx）:** `Cache-Control` を設定しない。CloudFront のデフォルト Error Caching Minimum TTL（デフォルト10秒）に委ねる。インポート直後に一部リソースの 404 キャッシュが残る可能性があるが、短時間で失効する。

**例外:**
- ヘルスチェック（`GET /health`）: `Cache-Control: no-store`（下記参照）
- v1p0 リダイレクト（301）: `Cache-Control` を設定しない（HTTP 仕様上、301 はデフォルトでキャッシュ可能）

## ヘルスチェック

```
GET /health
```
レスポンス (200):
```json
{"status": "ok"}
```
- 認証不要、テナントパス不要
- `Content-Type: application/json` で返す
- `Cache-Control: no-store` を設定する（CloudFront でキャッシュさせない）
- DB接続確認は行わない（Lambda コールドスタートの高速化を優先）

## v1p0 後方互換

`/ims/case/v1p0/` パスへのリクエストは `/ims/case/v1p1/` に 301リダイレクト。
CASE API は GET のみのため 301 で問題ない（POST でメソッドが変わるリスクなし）。
ルーターを二重に実装しない。`src/main.py` にミドルウェアを1つ追加して一括処理する。
リダイレクト先はパスの `v1p0` を `v1p1` に置換したもの（クエリパラメータはそのまま引き継ぐ）。
`Cache-Control` は設定しない（301 は HTTP 仕様上デフォルトでキャッシュ可能であり、CloudFront・ブラウザがデフォルト挙動でキャッシュする。恒久的なリダイレクトなのでこの挙動で問題ない）。

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

## 日付・タイムスタンプ形式

- **TIMESTAMP 型フィールド**（`lastChangeDateTime`）: ISO 8601 UTC（末尾 `Z`）で出力する（例: `"2025-10-08T12:00:00Z"`）。ミリ秒は含めない。Pydantic のシリアライズ設定で統一する
- **DATE 型フィールド**（`statusStartDate`, `statusEndDate`）: `YYYY-MM-DD` 形式で出力する（例: `"2018-03-30"`）。CASE v1.1 仕様の `xsd:date` 型に準拠

## LinkURI型

`CFPackageURI`, `CFDocumentURI`, `CFOriginNodeURI`, `CFDestinationNodeURI`, `CFItemTypeURI` 等は
文字列ではなく複合オブジェクト:
```json
{"title": "文書タイトル", "identifier": "uuid", "uri": "https://..."}
```
Pydantic で `LinkURIType` クラスを定義して共有する (`src/schemas/common.py`)。
DBには `_uri` (VARCHAR) と `_identifier` (UUID) カラムを持ち、`title` はJOINまたはアプリ層で解決する。
JOINで解決できない外部参照に備え、cf_association の originNodeURI / destinationNodeURI は `_title` カラムも保持する。

**CFPackageURI の構築:**
`CFPackageURI` はDBに保存せず、APIレスポンス生成時にアプリ層で構築する:
- `title` = CFDocument.title
- `identifier` = CFDocument.identifier
- `uri` = `{BASE_URL}/{tenant}/ims/case/v1p1/CFPackages/{CFDocument.identifier}`

外部インポートしたドキュメントでも、CFPackageURI.uri は**自サーバーのAPIエンドポイント**を指す（CFDocument.uri は外部URIを保持するが、CFPackageURI.uri は「このパッケージをどこで取得できるか」を示すため自サーバーを指す）。

**CFDocumentURI の構築（CFItem / CFAssociation 内）:**
`cf_document_id` FK で JOIN し、CFDocument の `{title, identifier, uri}` を使用する。CASE v1.1 OpenAPI では CFDocumentURI は CFItemDType では **required**、CFAssociationDType では **optional** だが、本システムでは `cf_document_id` が NOT NULL のため常に値があり、両方のケースで CFDocumentURI を含める。

**CFItemTypeURI の構築（CFItem 内）:**
`cf_item_type_id` FK で JOIN し、CFItemType の `{title, identifier, uri}` を使用する。`cf_item_type_id` が NULL の場合は `CFItemTypeURI` も null（`exclude_none=False` のため JSON に `null` として含まれる）。`CFItemType`（文字列フィールド）は同じ JOIN で CFItemType の `title` を使用する。`cf_item_type_id` が NULL の場合は `CFItemType` も null。

**licenseURI の構築（CFDocument / CFItem 内）:**
`cf_license_id` FK で JOIN し、CFLicense の `{title, identifier, uri}` を使用する。`cf_license_id` が NULL の場合は `licenseURI` も null（`exclude_none=False` のため JSON に `null` として含まれる）。CFItemTypeURI と同じ FK → JOIN パターン。

**CFAssociationGroupingURI の構築（CFAssociation 内）:**
`cf_association_grouping_id` FK で JOIN し、CFAssociationGrouping の `{title, identifier, uri}` を使用する。`cf_association_grouping_id` が NULL の場合は null（`exclude_none=False` のため JSON に `null` として含まれる）。

**originNodeURI / destinationNodeURI の構築（CFAssociation 内）:**
DBの `origin_node_identifier`, `origin_node_uri`, `origin_node_title`, `origin_node_target_type` カラムから直接構築する（JOINしない）。外部参照のリソースに対応するため、保存時点の値をそのまま使用する。CASE v1.1 では `LinkGenURIDType` を使用し、`identifier` は UUID 制限なし、`targetType` フィールドが追加されている。`targetType` は NULL の場合レスポンスに null として含める（CASE v1.1 OpenAPI では `targetType` は anyOf（`"CASE"` enum / `ext:` パターン）で null を許容しない定義だが、実運用上 targetType が未設定のケースは一般的であるため null を含める方針とする。strict な準拠が必要な場合は `exclude_none` で省略する対応を Phase 2 で検討する）。

**subject / subjectURI の構築（CFDocument / CFItem 内）:**
DB の `subject` JSONB カラム（文字列配列）と `subject_uri` JSONB カラム（LinkURI オブジェクト配列）をそのまま出力する。NULL の場合は null（`exclude_none=False` のため JSON に `null` として含まれる）。CASE v1.1 では `subject` と `subjectURI` は CFDocument と CFItem の両方に定義されている。

**conceptKeywordsURI の構築（CFItem 内）:**
`cf_concept_id` FK で JOIN し、CFConcept の `{title, identifier, uri}` を使用する。`cf_concept_id` が NULL の場合は null（`exclude_none=False` のため JSON に `null` として含まれる）。CASE v1.1 仕様では `conceptKeywordsURI` は単一の LinkURIDType（配列ではない）。CFItemTypeURI と同じ FK → JOIN パターン。

**API レスポンスに含めない内部フィールド:**
`cf_item.depth` は内部用フィールド（ツリービューの描画用）であり、CASE v1.1 仕様に存在しないため、全 API レスポンス（CFItem, CFPackage 内の CFItems）に含めない。Pydantic スキーマで除外すること。

**Phase 1 で省略する CASE v1.1 フィールド:**
`notes`（CFDocument / CFItem / CFAssociation）、`alternativeLabel`（CFItem）、`extensions`（全リソース共通、v1.1 新規）は DB に保存しない（db-schema.md 参照）。これらのフィールドは Pydantic スキーマに**含めない**（API レスポンスに一切出力しない。`exclude_none=False` ポリシーの対象外）。CASE v1.1 ではこれらは任意フィールドであり、省略しても準拠性に影響しない。Phase 2 でカラム追加時に Pydantic スキーマにも追加し、`null` として出力されるようにする。

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
- `imsx_codeMinor`: 任意。ネストされたオブジェクト（文字列ではない）。`imsx_codeMinorFieldName` は全エラーで `"sourcedId"` 固定（CASE v1.1 imsx 標準の慣例に従う）
- `imsx_codeMinorFieldValue`: `fullsuccess` / `invalid_sort_field` / `invalid_selection_field` / `forbidden` / `unauthorised_request` / `internal_server_error` / `unknownobject` / `server_busy` / `invalid_uuid`
- HTTPステータスコード対応: 400→`failure/error`, 404→`failure/error`+`unknownobject`, 405→`failure/error`+`invalid_selection_field`, 429→`failure/error`+`server_busy`, 500→`failure/error`+`internal_server_error`
- **429 (Server Busy):** CASE v1.1 OpenAPI で全エンドポイントに定義されている。Phase 1 では明示的なレート制限を実装しないが、API Gateway / Lambda のスロットリングにより 429 が返される可能性がある。その場合は imsx_StatusInfo 形式で `server_busy` を返す
- FastAPI のデフォルト 422 Validation Error レスポンスは使用せず、imsx_StatusInfo 形式の **400**（`invalid_selection_field`）に変換する。カスタム例外ハンドラで RequestValidationError をキャッチし、imsx_StatusInfo 形式で返す
- CASE API パス配下（`/{tenant}/ims/case/v1p1/...`）の未定義サブパスへのアクセスには **404**（`unknownobject`）を imsx_StatusInfo 形式で返す。FastAPI/Starlette のデフォルト 404 レスポンスは imsx_StatusInfo 形式ではないため、CASE API パス配下の catch-all ルートまたはカスタム例外ハンドラで変換する

## 非対応HTTPメソッド

CASE API は読み取り専用（GET のみ）。POST / PUT / DELETE / PATCH を CASE API パスに送信した場合は **405 Method Not Allowed** を返す:
```json
{
  "imsx_codeMajor": "failure",
  "imsx_severity": "error",
  "imsx_description": "Method not allowed",
  "imsx_codeMinor": {
    "imsx_codeMinorField": [
      {"imsx_codeMinorFieldName": "sourcedId", "imsx_codeMinorFieldValue": "invalid_selection_field"}
    ]
  }
}
```
`Allow: GET` レスポンスヘッダーを含める。

## associationType 列挙値

CASE v1.1 で定義されている有効値:
- `isChildOf` / `isPeerOf` / `isPartOf` / `exactMatchOf` / `precedes` / `isRelatedTo` / `replacedBy` / `exemplar` / `hasSkillLevel` / `isTranslationOf`
- 拡張パターン: `ext:` プレフィックス付きの値（正規表現: `(ext:)[a-zA-Z0-9\.\-_]+`）も CASE v1.1 で有効として定義されている

外部CASEソースインポート時にこの列挙値および拡張パターンを検証し、いずれにも該当しない値の場合は該当 Association をスキップして警告を出力する。`ext:` プレフィックス付きの値は有効な associationType として受け入れる。

## adoptionStatus 列挙値

CASE v1.1 情報モデルで定義されている標準値:
- `Draft` / `Private Draft` / `Adopted` / `Deprecated`

**注意:** CASE v1.1 OpenAPI スキーマでは `adoptionStatus` の型は `string`（enum 制約なし）のため、上記以外の値も技術的には有効。本システムでは上記の値を推奨するが、インポート時に上記以外の値が指定されてもエラーにしない（警告のみ出力し、値をそのまま保存する）。

## CASE v1.1 公式仕様との意図的差異

以下は CASE v1.1 OpenAPI スキーマとの差異のうち、意図的な設計判断として本システムで採用しているもの:

1. **レスポンスラッパー構造:** OpenAPI スキーマの strict な読み方では、単一リソース取得（`GET /CFDocuments/{id}` 等）は DType をルートに直接返す（ラッパーなし）。本システムでは `{"CFDocument": {...}}` のようにルートキーでラップする。これは OpenSALT 等の既存 CASE 実装の慣行に合わせた設計。CFPackage も `{"CFPackage": {...}}` でラップする
2. **空配列の許容:** `CFDocumentSetDType` (`minItems: 1`) や `CFAssociationSetDType` (`minItems: 1`) に対して、0 件時に空配列を返す（上記各セクション参照）
3. **invalid UUID → 400:** CASE v1.1 では invalid UUID も 404 に含むが、本システムでは 400 に分離（上記バリデーション節参照）
4. **`limit=0` の許容:** OpenAPI は `minimum: 1` だが、本システムでは空配列を返す有効リクエストとして扱う（上記ページネーション節参照）
5. **ページネーション拡張:** OpenAPI では `limit`/`offset` 等は `GET /CFDocuments` のみに定義。本システムでは全一覧エンドポイントに適用する独自拡張
6. **`X-Total-Count` / `links` ヘッダー省略:** Phase 1 では実装しない（上記ページネーション節参照）
7. **`targetType: null` の出力:** OpenAPI の anyOf 定義上 null は有効値でないが、実運用上必要なため null を含める（上記 LinkURI 型節参照）
8. **テナントプレフィックス:** `/{tenant}/ims/case/v1p1/` パスは CASE v1.1 仕様にない独自拡張（マルチテナント対応）
9. **Service Discovery エンドポイント:** CASE v1.1 では `GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json` が定義されている。Phase 1 では未実装。Phase 2 の Conformance テスト対応で実装を検討する
10. **405 Method Not Allowed:** CASE v1.1 OpenAPI に定義はないが、GET only の API として合理的なため追加
11. **401/403 未実装:** CASE v1.1 OpenAPI で全エンドポイントに定義されているが、CASE API は public（認証不要）のため不要
12. **CFDocument `creator` の nullable 化:** CASE v1.1 OpenAPI では `creator` は required（CFDocumentDType の required リストに含まれる）だが、CSV インポートで未指定のケースに対応するため DB では nullable。API レスポンスで `null` が返る可能性がある。外部 CASE CFPackage インポート時の挙動: 新規作成時に `creator` が欠落・null・空白文字列であれば警告を出力した上で `null` で保存する。更新時は欠落・null は既存値を保持（無警告）、空白文字列の場合は警告を出した上で既存値を保持する（既存 creator を空文字に上書きしない）。Phase 2 の Conformance テスト対応で空文字列デフォルト化を検討する
13. **lookup リソースの required フィールドの nullable 化:** CFItemType の `description`/`hierarchyCode`、CFSubject の `hierarchyCode`、CFConcept の `hierarchyCode`、CFLicense の `licenseText` を nullable として扱う（上記「lookup リソースの必須フィールドに関する準拠性」節参照）

## コンテントネゴシエーション

**コンテントネゴシエーションは使わない。** CloudFrontがAcceptヘッダーを無視して
キャッシュするため、HTML/JSONが混在するリスクがある。
- Web UI: `/`, `/{tenant}/`, `/{tenant}/cftree/doc/*`, `/{tenant}/uri/{uuid}` → 常にHTML（`Content-Type: text/html; charset=utf-8`）。HTMX フラグメント（`/children/*`, `/detail/*`）も HTML
- CASE API: `/{tenant}/ims/case/v1p1/CFItems/{uuid}` → 常にJSON（`Content-Type: application/json`）
- Admin API: → 常にJSON（`Content-Type: application/json`）
