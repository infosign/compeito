# Validate CASE Compliance

CASE v1.1 仕様への準拠を確認するスキル。

## 手順

以下を順番に確認してください。

### 1. Pydantic スキーマの確認 (`src/schemas/`)

各スキーマについて:
- [ ] 必須フィールドが全て定義されているか (CLAUDE.md の schema-agent 参照)
- [ ] `identifier` は `UUID` 型か
- [ ] `uri` はレスポンススキーマで `AnyUrl` 型か（コンフォーマンス準拠。DBは VARCHAR、インポート時は警告付きで寛容に受け入れ）
- [ ] `lastChangeDateTime` は `datetime` 型か
- [ ] `associationType` は Literal または Enum で列挙値を制限しているか
- [ ] フィールド名がキャメルケース (alias) になっているか
- [ ] `model_config = ConfigDict(populate_by_name=True)` が設定されているか

### 2. レスポンス構造の確認 (`src/routers/`)

- [ ] REST/JSON形式で返しているか（JSON-LDの `@context` / `@type` は不要）
- [ ] CFPackage レスポンスに CFDocument, CFItems, CFAssociations が含まれるか
- [ ] ページネーション (`limit`, `offset`) が実装されているか (CFDocuments一覧)

### 3. Cache-Control ヘッダーの確認

- [ ] `src/main.py` またはミドルウェアで `Cache-Control: public, max-age=3600` が付与されているか

### 4. エラーレスポンスの確認

- [ ] 404 エラーがルートレベルの imsx_StatusInfo 形式で返るか（ラッパーオブジェクトなし）:
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

### 5. テスト実行

```bash
uv run pytest tests/ -v
```

問題があれば schema-agent を使って修正してください。
