# Add Router

新しい CASE v1.1 エンドポイントをプロジェクトの規約に沿って追加するスキル。

## 手順

追加するリソース名を確認してから以下を実行してください。

### 1. スキーマ追加 (`src/schemas/{resource}.py`)

- CLAUDE.md の schema-agent セクションを参照して必須/任意フィールドを確認
- `model_config = ConfigDict(populate_by_name=True)` を設定
- フィールド名は alias でキャメルケースに変換

```python
from pydantic import BaseModel, ConfigDict, Field, AnyUrl
from datetime import datetime
from uuid import UUID

class CF{Resource}(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    identifier: UUID
    uri: AnyUrl
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
    # ... 他フィールド (schema-agent.md 参照)
```

### 2. モデル追加 (`src/models/{resource}.py`)

- SQLAlchemy 2.x の Mapped 型を使用
- `Base` を `src/database.py` からインポート

### 3. ルーター追加 (`src/routers/{resource}.py`)

- `/{tenant_id}/ims/case/v1p1/CF{Resource}s/{id}` のパスで実装（**v1p1**）
- `Cache-Control` ヘッダーを必ず付与
- テナント存在確認を必ず行う
- レスポンスのルートキーはリソース名（例: `{"CF{Resource}": {...}}`）

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/{tenant_id}/ims/case/v1p1/CF{Resource}s/{id}")
async def get_{resource}(tenant_id: UUID, id: UUID, db=Depends(get_db)):
    # テナント確認
    # リソース取得
    # 404 は imsx_StatusInfo 形式で返す（ルートレベル、ラッパーなし）
    return JSONResponse(
        content={"CF{Resource}": result.model_dump(by_alias=True)},
        headers={"Cache-Control": "public, max-age=3600"}
    )
```

### 4. ルーターを main.py に登録

```python
from src.routers.{resource} import router as {resource}_router
app.include_router({resource}_router)
```

### 5. テスト追加 (`tests/integration/test_{resource}.py`)

test-agent を使って対応するテストを追加してください。

### 6. 検証

```bash
uv run pytest tests/integration/test_{resource}.py -v
```

完了後 `/validate-case` を実行して全体の準拠確認をしてください。
