# Scaffold Resource

CASE v1.1 リソースの全レイヤー（model → schema → repository → service → router → test）を一括生成するスキル。

## 使い方

リソース名（例: `CFItemType`）を指定して実行。以下の 7 ファイルを生成・更新する。

## 手順

### 0. 仕様確認

まず `docs/reference/imscasev1p1_openapi3_v1p0.json` と `docs/spec/db-schema.md` でリソースのフィールド定義を確認する。

- 必須/任意フィールド
- データ型（string, UUID, datetime, array 等）
- レスポンスの DType 名（Standalone vs Package）
- Set型（配列）か単体オブジェクトか

### 1. SQLAlchemy モデル (`src/models/{resource}.py`)

```python
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from src.database import Base
import uuid


class CF{Resource}(Base):
    __tablename__ = "cf_{resource}"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier = Column(PG_UUID(as_uuid=True), unique=True, nullable=False)
    uri = Column(String, nullable=False)
    title = Column(String, nullable=False)
    last_change_date_time = Column(DateTime(timezone=True), nullable=False)
    description = Column(String, nullable=True)
    # ... リソース固有カラム

    tenant_id = Column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
```

- `id` は内部PK、`identifier` は CASE v1.1 の公開識別子（UUID v4）
- `tenant_id` は全リソースに必須（マルチテナント）
- FK の ondelete は `docs/spec/db-schema.md` に従う

### 2. Pydantic スキーマ (`src/schemas/{resource}.py`)

```python
from pydantic import BaseModel, ConfigDict, Field, AnyUrl
from datetime import datetime
from uuid import UUID
from typing import Optional


class CF{Resource}(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    identifier: UUID
    uri: AnyUrl
    title: str
    last_change_date_time: datetime = Field(alias="lastChangeDateTime")
    description: Optional[str] = None
    # ... リソース固有フィールド（alias でキャメルケース）
```

- フィールド名は内部スネークケース + `alias` でキャメルケース
- `model_config = ConfigDict(populate_by_name=True)` 必須
- レスポンス用とDB読み込み用で型を分ける場合は `CF{Resource}Response` 等を定義

### 3. リポジトリ (`src/repositories/{resource}_repository.py`)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.{resource} import CF{Resource}
from uuid import UUID


class CF{Resource}Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_identifier(self, tenant_id: UUID, identifier: UUID) -> CF{Resource} | None:
        stmt = select(CF{Resource}).where(
            CF{Resource}.tenant_id == tenant_id,
            CF{Resource}.identifier == identifier,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> list[CF{Resource}]:
        stmt = (
            select(CF{Resource})
            .where(CF{Resource}.tenant_id == tenant_id)
            .order_by(CF{Resource}.last_change_date_time.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, tenant_id: UUID) -> int:
        # COUNT クエリ
        ...
```

- 全メソッドは `tenant_id` でスコープ
- 一覧は `limit`/`offset` ページネーション対応
- `get_by_identifier` で CASE identifier 検索

### 4. サービス (`src/services/` — 既存に追加)

- `case_query_service.py`: 単一リソース取得・一覧取得を追加
- リポジトリを呼び出し、Pydantic スキーマに変換して返す
- テナント存在確認 → リソース取得 → 404処理の共通パターン

### 5. ルーター (`src/routers/{resource}.py`)

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from uuid import UUID

router = APIRouter()


@router.get("/{tenant_id}/ims/case/v1p1/CF{Resource}s/{id}")
async def get_{resource}(tenant_id: UUID, id: UUID, db=Depends(get_db)):
    # 1. tenant_id の UUID 形式チェック（FastAPI が自動で行う）
    # 2. テナント存在確認 → 404 (unknownobject)
    # 3. リソース取得 → 404 (unknownobject)
    # 4. レスポンス構築
    return JSONResponse(
        content={"CF{Resource}": result.model_dump(by_alias=True, exclude_none=False)},
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{tenant_id}/ims/case/v1p1/CF{Resource}s")
async def get_{resource}s(
    tenant_id: UUID,
    limit: int = 100,
    offset: int = 0,
    db=Depends(get_db),
):
    # ページネーション（limit: max 500, offset: max 100000）
    # exclude_none=False で null フィールドも含める
    return JSONResponse(
        content={"CF{Resource}s": [r.model_dump(by_alias=True, exclude_none=False) for r in results]},
        headers={"Cache-Control": "public, max-age=3600"},
    )
```

**レスポンス形式の注意点**:
- ルートキーは DType 名（`docs/reference/case-v1p1-rest-binding.md` で確認）
- `exclude_none=False` で null フィールドを含める（FR-2.10）
- Set型エンドポイント（CFConcepts, CFSubjects, CFItemTypes の `/{id}`）は配列で返す
- エラーは imsx_StatusInfo 形式（`docs/spec/api-spec.md` 参照）

### 6. main.py にルーター登録

```python
from src.routers.{resource} import router as {resource}_router
app.include_router({resource}_router)
```

### 7. テスト (`tests/integration/test_{resource}.py`)

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_{resource}_success(client: AsyncClient, sample_{resource}):
    resp = await client.get(f"/{tenant_id}/ims/case/v1p1/CF{Resource}s/{identifier}")
    assert resp.status_code == 200
    data = resp.json()
    assert "CF{Resource}" in data  # or "CF{Resource}s" for Set type
    assert data["CF{Resource}"]["identifier"] == str(identifier)


@pytest.mark.asyncio
async def test_get_{resource}_not_found(client: AsyncClient, sample_tenant):
    resp = await client.get(f"/{tenant_id}/ims/case/v1p1/CF{Resource}s/{nonexistent_uuid}")
    assert resp.status_code == 404
    data = resp.json()
    assert data["imsx_codeMajor"] == "failure"


@pytest.mark.asyncio
async def test_get_{resource}_invalid_uuid(client: AsyncClient, sample_tenant):
    resp = await client.get(f"/{tenant_id}/ims/case/v1p1/CF{Resource}s/not-a-uuid")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_{resource}_wrong_tenant(client: AsyncClient, sample_{resource}, other_tenant):
    # テナント分離テスト
    resp = await client.get(f"/{other_tenant_id}/ims/case/v1p1/CF{Resource}s/{identifier}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_{resource}_cache_control(client: AsyncClient, sample_{resource}):
    resp = await client.get(f"/{tenant_id}/ims/case/v1p1/CF{Resource}s/{identifier}")
    assert resp.headers["Cache-Control"] == "public, max-age=3600"


@pytest.mark.asyncio
async def test_list_{resource}s_pagination(client: AsyncClient, sample_tenant):
    # limit/offset テスト
    ...
```

### 8. 検証

```bash
uv run pytest tests/integration/test_{resource}.py -v
```

完了後 `/validate-case` を実行して全体の準拠確認をすること。

## チェックリスト

- [ ] モデルの `tenant_id` FK あり
- [ ] スキーマの `model_config` と `alias` 設定済み
- [ ] リポジトリの全メソッドが `tenant_id` スコープ
- [ ] ルーターの Cache-Control ヘッダー付与
- [ ] ルーターの `exclude_none=False`
- [ ] エラーレスポンスが imsx_StatusInfo 形式
- [ ] Set型 vs 単体の正しい選択
- [ ] main.py にルーター登録
- [ ] テストに成功・404・400・テナント分離・Cache-Control を含む
