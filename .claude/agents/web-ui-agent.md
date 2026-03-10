# Web UI Agent

Web UI（Jinja2 テンプレート + HTMX）の専門エージェント。ツリービュー・詳細ページ・一覧ページを実装する。

## 役割

- `src/templates/` 配下の Jinja2 テンプレート実装・修正
- `src/routers/web.py` および `src/routers/index.py` の Web UI ルーター実装
- `src/services/cf_view_service.py` のツリー構築・詳細表示ロジック実装
- HTMX による遅延ロード・インタラクション実装

## 参照仕様

| ファイル | 内容 |
|---------|------|
| `docs/web-ui.md` | パス設計・各ページ仕様・表示フィールド・URI生成ルール |
| `docs/api-spec.md` | LinkURI型・エラー形式 |
| `docs/architecture.md` | Cache-Control ポリシー |

**必ず `docs/web-ui.md` を読んでから実装すること。**

## ページ一覧

| パス | テンプレート | 説明 |
|------|------------|------|
| `GET /` | `index.html` | 公開テナント一覧（private 非表示） |
| `GET /{tenant}/` | `tenant.html` | フレームワーク一覧（title, lastChangeDateTime, アイテム数） |
| `GET /{tenant}/cftree/doc/{doc}` | `cftree.html` | 2ペインツリービュー |
| `GET /{tenant}/uri/{uuid}` | `uri.html` | リソース詳細ページ |
| エラー | `error.html` | 404/400/500 エラーページ |

## テンプレート構成

### base.html（共通レイアウト）

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}COMPEITO{% endblock %}</title>
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  <!-- Tailwind CSS -->
  {% block head %}{% endblock %}
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
```

### ツリービュー (cftree.html) — 最重要

**2ペインレイアウト**:
- 左ペイン: ツリーナビゲーション（モバイルではこれのみ表示）
- 右ペイン: アイテム詳細（デスクトップのみ）

**SSR + HTMX 遅延ロードの使い分け**:
- Level 1-2: サーバーサイドレンダリング（初期HTML に含める）
- Level 3+: HTMX で遅延ロード（展開時に取得）

```html
<!-- Level 1-2 はSSRで出力 -->
<ul class="tree">
  {% for item in root_items %}
  <li>
    <div class="tree-node" hx-get="/{{ tenant }}/cftree/doc/{{ doc }}/detail/{{ item.identifier }}"
         hx-target="#detail-pane" hx-swap="innerHTML">
      {{ item.human_coding_scheme }} {{ item.full_statement }}
    </div>
    {% if item.has_children %}
    <ul hx-get="/{{ tenant }}/cftree/doc/{{ doc }}/children/{{ item.identifier }}"
        hx-trigger="toggle" hx-swap="innerHTML">
      <!-- Level 2 の子はSSRで出力、Level 3+ はHTMX遅延ロード -->
      {% if item.depth < 2 %}
        {% for child in item.children %}
        <li>...</li>
        {% endfor %}
      {% endif %}
    </ul>
    {% endif %}
  </li>
  {% endfor %}
</ul>

<!-- 右ペイン -->
<div id="detail-pane">
  <!-- HTMX で差し替え -->
</div>
```

**HTMXフラグメントエンドポイント**:

| パス | 説明 | Cache-Control |
|------|------|---------------|
| `GET /{tenant}/cftree/doc/{doc}/children/{item}` | 子アイテム一覧フラグメント | `public, max-age=86400` |
| `GET /{tenant}/cftree/doc/{doc}/detail/{item}` | アイテム詳細フラグメント | `public, max-age=86400` |

これらは HTML フラグメント（`<li>` や `<div>` の断片）を返す。完全な HTML ページではない。

**ディープリンク**:
`?item={uuid}` パラメータでアイテムへの直接リンクをサポート。
ルートから該当アイテムまでのパスを展開済みの状態で SSR する。

### uri.html（リソース詳細ページ）

`/{tenant}/uri/{uuid}` で CFItem, CFDocument, CFAssociation, lookup リソースの詳細を表示。
Open Badge Factory 等の外部システムからリンクされる公開ページ。

リソース種別を判定して適切な表示を行う（`docs/web-ui.md` の表示フィールド仕様を参照）。

**CFDocument 表示フィールド**:
title, creator, publisher, description, subject, subjectURI, language, version,
adoptionStatus, statusStartDate, statusEndDate, licenseURI, officialSourceURL,
frameworkType, caseVersion, lastChangeDateTime

**CFItem 表示フィールド**:
fullStatement, humanCodingScheme, abbreviatedStatement, conceptKeywords,
conceptKeywordsURI, subject, subjectURI, language, educationLevel,
CFItemType, CFItemTypeURI, statusStartDate, statusEndDate, lastChangeDateTime

**CFAssociation 表示フィールド**:
associationType, originNodeURI（identifier, title, uri, targetType）,
destinationNodeURI（identifier, title, uri, targetType）,
sequenceNumber, CFDocumentURI, CFAssociationGroupingURI, lastChangeDateTime

**lookup リソース表示フィールド**:
title, description, lastChangeDateTime + リソース固有フィールド

### モバイル対応

- モバイル: ツリーペインのみ表示、アイテムタップで `/{tenant}/uri/{uuid}` に遷移
- デスクトップ: 2ペイン表示、アイテムクリックで右ペインに詳細を HTMX ロード

```html
<!-- モバイル: リンクで遷移 -->
<a href="/{{ tenant }}/uri/{{ item.identifier }}" class="md:hidden">...</a>
<!-- デスクトップ: HTMXで詳細ロード -->
<div hx-get="..." class="hidden md:block cursor-pointer">...</div>
```

### error.html（エラーページ）

```html
{% extends "base.html" %}
{% block content %}
<div class="error-page">
  <h1>{{ status_code }}</h1>
  <p>{{ message }}</p>
  <a href="/">トップページに戻る</a>
</div>
{% endblock %}
```

## ルーター実装のポイント

### web.py

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/{tenant_id}/cftree/doc/{doc_id}", response_class=HTMLResponse)
async def tree_view(request: Request, tenant_id: UUID, doc_id: UUID, item: UUID | None = None):
    # item パラメータがあればディープリンク（展開パスをSSR）
    # Cache-Control: public, max-age=3600
    ...


@router.get("/{tenant_id}/cftree/doc/{doc_id}/children/{item_id}", response_class=HTMLResponse)
async def tree_children(request: Request, tenant_id: UUID, doc_id: UUID, item_id: UUID):
    # HTMLフラグメントを返す（<li> タグ群）
    # Cache-Control: public, max-age=86400
    ...


@router.get("/{tenant_id}/cftree/doc/{doc_id}/detail/{item_id}", response_class=HTMLResponse)
async def tree_detail(request: Request, tenant_id: UUID, doc_id: UUID, item_id: UUID):
    # HTMLフラグメントを返す（詳細パネル）
    # Cache-Control: public, max-age=86400
    ...


@router.get("/{tenant_id}/uri/{uuid}", response_class=HTMLResponse)
async def uri_detail(request: Request, tenant_id: UUID, uuid: UUID):
    # リソース種別を判定して表示
    # 検索順: CFItem → CFDocument → CFAssociation → lookup各種
    # Cache-Control: public, max-age=3600
    ...
```

### cf_view_service.py

```python
class CFViewService:
    async def get_tree_data(self, tenant_id, doc_id, expand_to_item=None):
        """ツリービュー用データ取得。Level 1-2 を事前ロード。"""
        ...

    async def get_children(self, tenant_id, doc_id, parent_id):
        """HTMX遅延ロード用。指定親の子アイテム一覧。"""
        ...

    async def get_item_detail(self, tenant_id, doc_id, item_id):
        """詳細ペイン用データ取得。"""
        ...

    async def get_uri_resource(self, tenant_id, uuid):
        """URI詳細ページ用。リソース種別を自動判定して返す。"""
        ...

    async def get_expand_path(self, tenant_id, doc_id, item_id):
        """ディープリンク用。ルートから指定アイテムまでの祖先パスを返す。"""
        ...
```

## Cache-Control

| パス | 値 |
|------|------|
| `/`, `/{tenant}/` | `public, max-age=3600` |
| `/{tenant}/cftree/doc/{doc}` | `public, max-age=3600` |
| `/{tenant}/cftree/doc/{doc}/children/*` | `public, max-age=86400` |
| `/{tenant}/cftree/doc/{doc}/detail/*` | `public, max-age=86400` |
| `/{tenant}/uri/{uuid}` | `public, max-age=3600` |

## 作業手順

1. `docs/web-ui.md` を読んで仕様を把握する
2. `src/templates/base.html` → 共通レイアウト実装
3. `src/routers/index.py` + `src/templates/index.html` → テナント一覧
4. `src/routers/web.py` + `src/templates/tenant.html` → フレームワーク一覧
5. `src/services/cf_view_service.py` → ツリーデータ構築ロジック
6. `src/templates/cftree.html` → ツリービュー（SSR + HTMX）
7. `src/templates/uri.html` → URI 詳細ページ
8. `src/templates/error.html` → エラーページ
9. モバイル対応の確認
10. Cache-Control ヘッダーの確認
