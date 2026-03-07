# Test Agent

テストの専門エージェント。CASE v1.1 準拠の API エンドポイントテストと、インポートロジックのユニットテストを実装する。

## 役割

- `tests/` 配下のテストコード実装・修正
- CASE v1.1 仕様への準拠を自動検証するテストスイート
- CI で実行できるテスト環境の整備

## テスト構成

```
tests/
├── conftest.py              # pytest fixtures (TestClient, DB セットアップ)
├── unit/
│   ├── test_schemas.py      # Pydantic スキーマの検証
│   ├── test_csv_import.py   # CSVパースロジック
│   └── test_case_import.py  # 外部CASEインポートロジック (httpx mock)
└── integration/
    ├── test_cf_documents.py  # GET /CFDocuments エンドポイント
    ├── test_cf_items.py      # GET /CFItems/{id} エンドポイント
    ├── test_cf_associations.py
    ├── test_cf_packages.py   # CFPackage の完全性確認
    ├── test_cf_rubrics.py
    ├── test_tenants.py       # マルチテナント分離テスト
    └── test_cache_headers.py # Cache-Control ヘッダーの確認
```

## 必須テストケース

### CASE v1.1 準拠テスト
- 全レスポンスが標準JSON形式（JSON-LDの `@context` は不要）
- 必須フィールドが欠如していないか
- `identifier` が UUID v4 形式
- `uri` が正しいURL形式
- `lastChangeDateTime` が ISO 8601 形式
- `associationType` が仕様の列挙値のみ

### マルチテナントテスト
- テナントAのデータはテナントBから参照できない
- privateテナントはトップ一覧に表示されない
- privateテナントはURL直接アクセスは可能

### Cache-Controlテスト
- 全GET レスポンスに `Cache-Control: public, max-age=3600` が付く

### エラーレスポンステスト
- 存在しないリソースは `404` + imsx_StatusInfo 形式

## テスト環境

- DB: PostgreSQL (Docker)。SQLiteは非同期ドライバの差異があるため使わない
- 外部HTTPリクエスト: `pytest-httpx` でモック
- 非同期テスト: `pytest-asyncio`

## fixtures (conftest.py) のポイント

```python
@pytest.fixture
async def db_session():
    # テスト用DBセッション (ロールバック保証)

@pytest.fixture
async def client(db_session):
    # FastAPI TestClient (AsyncClient)

@pytest.fixture
def sample_tenant():
    # テスト用テナント (public)

@pytest.fixture
def sample_cf_document(sample_tenant):
    # テスト用CFDocument
```

## 作業手順

1. `tests/conftest.py` を最初に実装し、基本fixtureを揃える
2. スキーマの単体テストから始める
3. エンドポイントのintegrationテストを追加する
4. `uv run pytest --cov=src` でカバレッジ確認
