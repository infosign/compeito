# Web UI Agent

Web UI（Jinja2 テンプレート + HTMX）の専門エージェント。ツリービュー・詳細ページ・一覧ページを実装する。

## 役割

- `src/templates/` 配下の Jinja2 テンプレート実装・修正
- `src/routers/web.py` の Web UI ルーター実装（テナント一覧・フレームワーク一覧・ツリー・詳細・HTMX フラグメント）
- `src/services/cf_view_service.py`（詳細・CFPackage 構築・`list_document_definitions`）と
  `src/services/tree_service.py`（`build_full_tree` / `dfs_index` / `get_children` 等）のロジック実装
- `src/services/uri_service.py`（`/uri/{id}` の任意リソース解決）
- HTMX による右ペイン差し替え・インタラクション実装

## 参照仕様

| ファイル | 内容 |
|---------|------|
| `docs/spec/web-ui.md` | パス設計・各ページ仕様・表示フィールド・URI生成ルール |
| `docs/spec/api-spec.md` | LinkURI型・エラー形式 |
| `docs/spec/architecture.md` | Cache-Control ポリシー |

**必ず `docs/spec/web-ui.md` を読んでから実装すること。** 本ファイルは概要であり、表示フィールドや
バリデーションの正確な定義は web-ui.md が一次情報。

## ページ一覧（すべて `src/routers/web.py`）

| パス | テンプレート | 説明 |
|------|------------|------|
| `GET /` | `index.html` | テナント一覧（private は非掲載、`display_order` 昇順 NULLS LAST） |
| `GET /{tenant}/` | `tenant.html` | フレームワーク一覧（title, lastChangeDateTime 等、`display_order` 順） |
| `GET /{tenant}/cftree/doc/{doc}` | `cftree.html` | 2ペインツリービュー（`?item=` でディープリンク・後方互換） |
| `GET /{tenant}/cftree/doc/{doc}/item/{item}` | `cftree.html` | 同上の正規・共有可能・静的化可能な形（ツリー内ナビが push する URL） |
| `GET /{tenant}/uri/{uuid}` | `uri.html` | リソース詳細ページ（permalink） |
| エラー | `error.html` | 404/400/500 エラーページ |

`/uri/{uuid}` はコンテンツネゴシエーションを行う: ブラウザ（`Accept: text/html`）には HTML を返し、
JSON クライアント（Open Badge Factory 等）には対応する CASE v1.1 API エンドポイントへ 303 リダイレクトする。
個別 API を持たない種別（CFRubricCriterion / CFRubricCriterionLevel）は HTML にフォールスルー。

## テンプレート構成

```
src/templates/
├── base.html            # 共通レイアウト（自己ホスト HTMX/フォント, Tailwind ローカル/CDN, ツリーJS）
├── index.html           # テナント一覧
├── tenant.html          # フレームワーク一覧
├── cftree.html          # ツリービュー（左ツリー + 右ペイン）
├── uri.html             # 単独詳細ページ（permalink）
├── error.html           # エラーページ
└── fragments/
    ├── resource_detail.html  # 全リソース共通のフル詳細カード（マクロ群）
    ├── detail.html           # 右ペイン用（resource_detail を include）
    ├── tree_nodes.html       # ツリー本体（ネスト <details>）
    └── tree_node_macros.html # branch_summary / leaf マクロ（定義/ルーブリック節）
```

### ツリービュー (cftree.html) — 最重要

**2ペインレイアウト**:
- 左ペイン: ツリーナビゲーション（モバイルではこれのみ表示）
- 右ペイン (`#detail-pane`): リソース詳細

**完全 SSR（遅延ロードしない）**:
ツリーはネストした `<details>` で**全件サーバーサイドレンダリング**する。展開/折りたたみは
ネイティブ `<details>` で完結し、JS もサーバー往復も不要。`/children/` のような遅延ロード用
エンドポイントは**存在しない**（過去の設計を引きずらないこと）。

- ラベルは実体のある `<a href=".../item/{id}">`（JS 無しでも遷移可）に HTMX を重ねて右ペインを差し替える。
- ツリーは CFItem 階層に加えて **Definitions 節**（CFItemType/CFSubject/CFConcept/CFLicense/
  CFAssociationGrouping）と **Rubrics 節**（CFRubric → Criterion → Level）を持つ。
- 右ペインに表示するものは必ず左ツリーに存在し、選択状態にする（画面外なら自動スクロール）。

**初期ペイン（SSR）**: `?item=` / `/item/{id}` で選択があればそのリソースのフル詳細を、
無ければドキュメント自身を右ペインに SSR する（HTMX 往復なしで復元）。

**HTMX フラグメントエンドポイント**:

| パス | 説明 | Cache-Control |
|------|------|---------------|
| `GET /{tenant}/cftree/doc/{doc}/detail/{item}` | リソース詳細フラグメント（item/定義/ルーブリック） | `public, max-age=86400` |
| `GET /{tenant}/cftree/doc/{doc}/document` | ドキュメント自身の詳細フラグメント | `public, max-age=86400` |

`/document` を `/detail/{item}` と分けているのは、ドキュメントと identifier が衝突する CFItem が
あっても衝突しないようにするため（`/uri/` は item 優先で解決する）。フラグメントは HTML 断片を返す。

### 共有詳細カード

`/uri/`（単独ページ）・右ペイン HTMX フラグメント・ツリー初期ペインの 3 経路はすべて
`fragments/resource_detail.html`（マクロ群）で同一のフル詳細を描画する。

- `fragments/detail.html` … 右ペイン用ラッパー（`resource_detail` を include）
- `uri.html` … 単独ページ用ラッパー
- コンテキストは `web.py` の `_detail_pane_context()` が一元組み立て（新フィールドはここ 1 箇所で配線）

表示フィールド（CFDocument / CFItem / CFAssociation / lookup / CFRubric*）の正確な定義は
`docs/spec/web-ui.md` を参照。CFItem 詳細には関連（related）・参照ルーブリック・別 FW の上位/下位
（cross-document isChildOf）も含まれる。

### クロスリファレンスの遷移（動線）

詳細内のリンクは 3 種に分類して動線を変える:
- **同一ドキュメント内のアイテム** → 右ペイン内ナビ（ツリーの選択も移動）
- **同一テナントの別ドキュメントのアイテム** → そのドキュメントのツリーへ切替
- **外部 / 解決不能** → 新規タブでリンクアウト（http(s) のみ許可）

### モバイル対応

- モバイル: ツリーペインのみ表示。アイテム選択で右ペインへ差し替え後、`#detail-pane` を自動スクロール。
- デスクトップ: 2ペイン表示、左ツリーのクリックで右ペインを HTMX ロード。

## ルーター実装のポイント（web.py）

- `templates = Jinja2Templates(...)`、autoescape 有効。サーバー値をインライン JS に**置かない**
  （DOM-XSS 対策。コピーボタンは `data-copy` 属性 + 委譲ハンドラ方式）。
- テナントは UUID / slug どちらでも解決（`tenant_service.resolve_tenant`）。URL に出すセグメントは
  `_tenant_url_segment` でユーザーが要求した形を維持（permalink/API 文字列は `tenant.id` を使う）。
- UUID は `_parse_uuid` で検証（不正なら 400、未存在なら 404）。
- 言語は `_get_lang`（Accept-Language）＋ `get_translator`。
- ヘルパー: `_detail_extras`（カードに必要な付随データ取得）/ `_detail_pane_context`（コンテキスト組立）/
  `_related_groups` / `_cross_doc_hierarchy`。

## サービス層

- `tree_service.py` — `build_full_tree`（全件ツリー＋選択解決）, `dfs_index` / `doc_tree_index`,
  `get_children`, `sort_related_by_tree_order`, `get_document_for_tree`
- `cf_view_service.py` — `list_document_definitions`, 詳細・CFPackage 構築
- `uri_service.py` — `find_resource_by_identifier`（item → document → association → lookup → rubric 順）

## Cache-Control

`web.py` に定数化: `CACHE_CONTROL = "public, max-age=3600"`, `CACHE_CONTROL_FRAGMENT = "public, max-age=86400"`。

| パス | 値 |
|------|------|
| `/`, `/{tenant}/`, `/{tenant}/cftree/doc/{doc}`(/item/*), `/{tenant}/uri/{uuid}` | `public, max-age=3600` |
| `/{tenant}/cftree/doc/{doc}/detail/*`, `/{tenant}/cftree/doc/{doc}/document` | `public, max-age=86400` |

## 作業手順

1. `docs/spec/web-ui.md` を読んで仕様（表示フィールド・バリデーション）を把握する
2. テンプレートは `base.html` → 一覧（`index.html` / `tenant.html`）→ `cftree.html` →
   共有カード（`fragments/resource_detail.html` + `detail.html`）→ `uri.html` → `error.html` の順で確認
3. ロジックは `tree_service.py` / `cf_view_service.py` / `uri_service.py` を確認
4. ルーターは `web.py`（ページ + フラグメント）
5. モバイル動作・Cache-Control・autoescape（インライン JS にサーバー値を入れない）を確認
