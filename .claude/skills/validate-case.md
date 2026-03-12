# Validate CASE Compliance

CASE v1.1 仕様への準拠を確認するスキル。

## 手順

以下を順番に確認してください。

### 1. Pydantic スキーマの確認 (`src/schemas/`)

各スキーマについて:
- [ ] 必須フィールドが全て定義されているか (`docs/reference/imscasev1p1_openapi3_v1p0.json` で確認)
- [ ] `identifier` は `UUID` 型か
- [ ] `uri` はレスポンススキーマで `AnyUrl` 型か（コンフォーマンス準拠。DBは VARCHAR、インポート時は警告付きで寛容に受け入れ）
- [ ] `lastChangeDateTime` は `datetime` 型か
- [ ] `associationType` は 10個の列挙値 + `ext:` パターンをバリデーションしているか
- [ ] フィールド名がキャメルケース (alias) になっているか
- [ ] `model_config = ConfigDict(populate_by_name=True)` が設定されているか
- [ ] `LinkURIType` と `LinkGenURIDType` が区別されているか
  - `LinkURIType`: CFPackageURI, CFDocumentURI, licenseURI, CFItemTypeURI, subjectURI, CFAssociationGroupingURI 等
  - `LinkGenURIDType`: originNodeURI, destinationNodeURI（identifier に UUID 制約なし、`targetType` フィールドあり）
- [ ] lookup リソースの `description` が required になっているか

### 2. レスポンス構造の確認 (`src/routers/`)

- [ ] REST/JSON形式で返しているか（JSON-LDの `@context` / `@type` は不要）
- [ ] ルートキーが正しい DType 名か（`docs/reference/case-v1p1-rest-binding.md` で確認）
- [ ] CFPackage レスポンスに CFDocument, CFItems, CFAssociations が含まれるか
- [ ] CFItems, CFAssociations はデータがなくても空配列を返しているか
- [ ] CFDefinitions はデータがなければキーごと省略しているか
- [ ] ページネーション (`limit`, `offset`) が全一覧エンドポイントに実装されているか
- [ ] `exclude_none=False` で null フィールドをレスポンスに含めているか
- [ ] Set型エンドポイントが正しく配列で返しているか:
  - `GET /CFConcepts/{id}` → `{"CFConcepts": [{...}]}`
  - `GET /CFSubjects/{id}` → `{"CFSubjects": [{...}]}`
  - `GET /CFItemTypes/{id}` → `{"CFItemTypes": [{...}]}`
- [ ] 単体エンドポイントがオブジェクトで返しているか:
  - `GET /CFLicenses/{id}` → `{"CFLicense": {...}}`
  - `GET /CFAssociationGroupings/{id}` → `{"CFAssociationGrouping": {...}}`

### 3. Cache-Control ヘッダーの確認

- [ ] CASE API エンドポイント: `Cache-Control: public, max-age=3600`
- [ ] Web UI ページ: `Cache-Control: public, max-age=3600`
- [ ] HTMX フラグメント: `Cache-Control: public, max-age=86400`

### 4. エラーレスポンスの確認

- [ ] 404 エラーが imsx_StatusInfo 形式で返るか:
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
- [ ] フィールド名が全て小文字始まり（`imsx_codeMajor` ○、`imsx_CodeMajor` ✗）
- [ ] `imsx_codeMinor` がネストされたオブジェクト構造になっているか（文字列ではない）
- [ ] 不正 UUID → 400 (`invalid_uuid`)
- [ ] 存在しないテナント → 404 (`unknownobject`)
- [ ] 存在しないリソース → 404 (`unknownobject`)
- [ ] 非GETリクエスト → 405 Method Not Allowed

### 5. Phase 1 意図的差異の確認

`docs/spec/api-spec.md` の「CASE v1.1 公式仕様との意図的差異」セクションに記載された13項目が正しく実装されているか確認:
- [ ] ラッパー構造の差異（DType 名をルートキーに使用）
- [ ] CFItems/CFAssociations の空配列返却（仕様は minItems:1 だが空配列を許容）
- [ ] 不正UUID → 400（仕様は404のみ定義）
- [ ] limit=0 の扱い
- [ ] テナントプレフィックスパス
- [ ] targetType の null 許容

### 6. テスト実行

```bash
uv run pytest tests/ -v
```

問題があれば schema-agent を使って修正してください。
