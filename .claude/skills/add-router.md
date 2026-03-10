# Add Router

既存リソースに新しいエンドポイントを追加するスキル。
全レイヤーを一括生成する場合は `/scaffold-resource` を使うこと。

## 用途

- 既存リソースに追加のエンドポイントを生やす（例: `CFItemAssociations`）
- 特殊なレスポンス形式のエンドポイントを追加する

## 手順

### 1. 仕様確認

`docs/reference/case-v1p1-rest-binding.md` と `docs/api-spec.md` でエンドポイントの仕様を確認:
- パス
- レスポンスの DType 名（ルートキー）
- Set型（配列）か単体オブジェクトか
- ページネーションの有無

### 2. ルーター追加 (`src/routers/{resource}.py`)

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/{tenant_id}/ims/case/v1p1/CF{Resource}s/{id}")
async def get_{resource}(tenant_id: UUID, id: UUID, db=Depends(get_db)):
    # 1. テナント存在確認 → 404 (unknownobject)
    # 2. リソース取得 → 404 (unknownobject)
    # 3. レスポンス構築（exclude_none=False）
    return JSONResponse(
        content={"CF{Resource}": result.model_dump(by_alias=True, exclude_none=False)},
        headers={"Cache-Control": "public, max-age=3600"}
    )
```

**注意点**:
- ルートキーは DType 名を使用（`docs/reference/case-v1p1-rest-binding.md` で確認）
- Set型エンドポイント（CFConcepts/{id}, CFSubjects/{id}, CFItemTypes/{id}）は配列で返す
- `exclude_none=False` で null フィールドを含める（FR-2.10）
- エラーは imsx_StatusInfo 形式（`docs/api-spec.md` 参照）

### 3. ルーターを main.py に登録

```python
from src.routers.{resource} import router as {resource}_router
app.include_router({resource}_router)
```

### 4. テスト追加 (`tests/integration/test_{resource}.py`)

test-agent を使って対応するテストを追加。

### 5. 検証

```bash
uv run pytest tests/integration/test_{resource}.py -v
```

完了後 `/validate-case` を実行して全体の準拠確認をすること。
