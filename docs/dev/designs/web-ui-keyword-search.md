# Web UI キーワード検索（ツリービュー内） 実装方針

> **ステータス: 設計レビュー済み（実装着手可・実装順未定）**
> Codex レビュー 1 ラウンド（技術的前提の実コード検証・仕様間整合・方針整合）＋指摘反映済み（2026-07）。
>
> 目的: 2026-07 の外部レビュー（インストラクショナルデザイン視点）で「**検索の不在**」が重大度・高と
> 指摘された。1,500 項目規模の大きなフレームワークではツリー展開だけでは目的の
> CFItem に到達できない。本仕様は **PostgreSQL ILIKE による素朴なキーワード部分一致検索**を
> ツリービュー（`/cftree/doc/{doc}`）に追加する。意味検索（backlog B2 /
> [semantic-search.md](./semantic-search.md)、設計済み・未実装）とは**独立に動作**し、B2 実装時には
> この検索ボックス UI を共有できる形にする。

## 決定事項（本設計で確定させる判断）

- **検索方式**: PostgreSQL `ILIKE '%q%'`（部分一致・大文字小文字無視）。日本語は形態素解析の問題が
  あるため全文検索（tsvector）は使わず、**部分一致で十分**とする（CJK は case-folding の影響を
  受けず、部分一致がそのまま機能する）。pg_trgm ＋ GIN index は**今回は非対象**（後述）。
- **検索対象フィールド**: `full_statement` / `human_coding_scheme` / `abbreviated_statement` の
  3 フィールドの OR。**`notes` は含めない** — 結果リストに notes は表示されないため「なぜヒット
  したか」が画面から分からず混乱を招く。将来オプション（チェックボックス等）として拡張余地を残す。
- **スコープ**: ツリービュー内の検索は**現在のドキュメントに限定**（`cf_document_id` で絞る）。
  テナント横断・複数ドキュメント横断は非対象（将来 B2 の検索 API と統合）。クエリは常に
  `tenant_id` スコープ厳守（private テナントの秘匿を壊さない）。
- **検索の入口はツリービューのみ**: `tenant.html`（フレームワーク一覧）には**今回は置かない**。
  テナントページに置く検索は必然的に複数ドキュメント横断になり、結果 UI（ドキュメント別グルー
  ピング等）の設計が別物になる。B2 の `GET /{tenant}/search`（テナントスコープの JSON API）実装時に
  Web UI 入口ごと統合検討する方が二度手間にならない。→「非対象」に記録。
- **結果リストの部品**: `fragments/subject_items.html` を**そのまま再利用**する
  （[web-ui.md](../../spec/web-ui.md) に "intended for reuse by a future search results list" と
  明記済みの意図どおり）。行フォーマット（`humanCodingScheme` 太字 + `fullStatement` 先頭100字 +
  自ドキュメントのツリーへのリンク）は検索結果に必要なものと完全に一致する。
- **上限とページネーション**: **50 件で打ち切り**（`limit+1` フェッチで超過検知、COUNT クエリなし）。
  検索結果に「もっと見る」ページネーションは**付けない** — 50 件で見つからない検索は語を足して
  絞り込むべきで、ページ送りは UX 的に無意味。`subject_items.html` には `has_more=False` を渡す
  （load-more ブロックは描画されず、既存テンプレート無改修で済む）。
- **ハイライト**: 初版は**なし**（`subject_items.html` 無改修の再利用を優先）。将来やる場合は
  markupsafe で escape 後に `<mark>` を挿入する Jinja フィルタで autoescape を壊さず実装できる。

## ゴールと非対象

- **ゴール**: ツリービューを開いたユーザーが、キーワード（日本語・英語・コード）で現在の
  フレームワーク内の CFItem を即座に見つけ、クリックでそのアイテムのツリー位置＋詳細に到達できる。
- **非対象（今回やらないこと）**: 末尾「非対象」節を参照。

## アーキテクチャ概要

```
[検索ボックス (cftree.html 左ペイン上部)]
   ├─ JS あり: HTMX インクリメンタル (input delay:300ms) + submit
   │     → GET /{tenant}/cftree/doc/{doc}/search?q=…  (HTML フラグメント)
   │     → #search-results に swap
   └─ JS なし: <form method=get action=/cftree/doc/{doc}> submit
         → GET /{tenant}/cftree/doc/{doc}?q=…  (フルページ SSR、結果をツリー上部に描画)

フラグメント/SSR 共通:
   web.py ルート → cf_item_repository.search_items(ILIKE, tenant+doc スコープ)
   → fragments/search_results.html（件数/0件/打ち切り表示 + subject_items.html の行リスト）
   → 各行は既存の /cftree/doc/{doc}/item/{id} への素の <a href>
     （既存 SSR が祖先パス展開＋右ペイン詳細を再構築 — 遅延ツリーの未ロード枝でも確実に到達）
```

レイヤ: 既存の web.py の逆参照リスト系フラグメント（`subject_items_fragment` /
`item_type_items_fragment`）と同じく、**router から repository を直接呼ぶ**
（web.py の既存プラクティスに従う。専用 service は作らない）。

## UI 仕様（cftree.html）

### 検索フォーム

左ペイン（`#tree-scroll`）内、ドキュメント名ブロック（`data-tree-item` の `<div class="p-4 …">`）の
直下・ツリー本体（`<div class="p-2">`）の直上に置く。マークアップの骨子:

```html
<div class="px-4 py-2 border-b border-stone-200">
    <form role="search" method="get"
          action="/{{ tenant_url }}/cftree/doc/{{ doc.identifier }}"
          hx-get="/{{ tenant_url }}/cftree/doc/{{ doc.identifier }}/search"
          hx-target="#search-results" hx-swap="innerHTML"
          class="flex gap-2">
        <label for="tree-search" class="sr-only">{{ t("search_label") }}</label>
        <input id="tree-search" type="search" name="q" value="{{ q or '' }}"
               maxlength="200" autocomplete="off"
               placeholder="{{ t('search_placeholder') }}"
               hx-get="/{{ tenant_url }}/cftree/doc/{{ doc.identifier }}/search"
               hx-target="#search-results" hx-swap="innerHTML"
               hx-trigger="input changed delay:300ms, search"
               class="flex-1 min-w-0 rounded border border-stone-300 px-2 py-1 text-sm
                      focus:border-violet-400 focus:ring-violet-400">
        <button type="submit"
                class="px-3 py-1 text-sm rounded bg-violet-600 text-white hover:bg-violet-700
                       transition-colors">{{ t("search_button") }}</button>
    </form>
    <div id="search-results" aria-live="polite">
        {% if q %}{% include "fragments/search_results.html" %}{% endif %}
    </div>
</div>
```

挙動のポイント:

- **HTMX（自己ホスト htmx-2.0.4、外部 CDN 不可 — base.html で読込済み。追加アセットなし）**:
  - `<input>` の `hx-trigger="input changed delay:300ms, search"` でインクリメンタル検索
    （300ms デバウンス。`search` は `type="search"` の × クリア時に発火し、空 q → 結果クリア）。
  - `<form>` の `hx-get` が submit（Enter / ボタン）を横取りしてフラグメント取得（フォーム内
    input は自動で `q=` として送られる）。
  - `hx-push-url` は**使わない**。フラグメント URL（`…/search?q=`）を push するのは誤りで、
    ページ URL（`…?q=`）を動的に組むには追加 JS が要る。検索状態の共有が必要なら no-JS 形式の
    `/cftree/doc/{doc}?q=…` URL が使える（SSR で同じ結果が出る）ので初版はこれで足りる。
- **no-JS フォールバック**: `<form method="get" action=（ツリーページ自身）>` なので、JS なしでは
  submit 型検索としてフルページ遷移（`GET /{tenant}/cftree/doc/{doc}?q=…`）で動く。ツリーページの
  SSR が同じ結果ブロックを `#search-results` に描画する（`subject_items.html` が SSR インクルードと
  フラグメントの両方を担う既存パターンの踏襲）。
- **結果行のクリック**: `subject_items.html` の行は素の
  `<a href="/{tenant}/cftree/doc/{doc}/item/{item}">`。既存の `/item/{id}` SSR が**祖先パスを展開した
  ツリー＋右ペインのフル詳細**を再構築するので、遅延ツリーの未ロード枝にあるアイテムでも確実に
  選択状態で表示される（`selectTreeNode` は未ロード枝で no-op になるため、フルページ遷移が正解。
  HTMX でのペイン swap 化は将来最適化）。中クリック/新規タブも自然に動く。
- **表示位置**: 結果はツリー上部のリスト（右ペインではない）。右ペインは「選択ノードの詳細」という
  不変条件（pane content ⟺ tree node）を保っており、検索結果リストを入れると壊れるため。

### 結果表示（fragments/search_results.html — 新規パーシャル）

コンテキスト: `q`（表示用の生文字列。Jinja autoescape でエスケープされる）、`rows`
（`search_items` の返値、最大 50 件）、`truncated`（bool）、`tenant_url`、`t`。

```html
{# 検索結果ブロック: 件数 / 0件 / 打ち切り + 行リスト（subject_items.html を再利用） #}
{% if rows %}
<p class="mt-2 text-xs text-stone-400">
    {{ t("search_results_count", count=rows|length|string) }}
    {%- if truncated %} — {{ t("search_results_truncated", limit="50") }}{% endif %}
</p>
<ul class="mt-1 space-y-1 max-h-60 overflow-auto border-t border-stone-100 pt-2">
    {% with has_more=False %}{% include "fragments/subject_items.html" %}{% endwith %}
</ul>
{% else %}
<p class="mt-2 text-sm text-stone-500">{{ t("search_no_results", q=q) }}</p>
{% endif %}
```

- `subject_items.html` は `has_more=False` で行部分のみ描画される（`items_endpoint` /
  `next_offset` / `scope_doc` は `{% if has_more %}` ブロック内でしか参照されないため未定義でよい）。
  **subject_items.html 自体は無改修**。
- 0 件時: 「該当する項目はありません」（q を含めてエスケープ表示）。
- 51 件フェッチで 51 件返った場合: 先頭 50 件を表示し「先頭 50 件を表示しています（キーワードを
  追加して絞り込んでください）」を付記。
- 空 q（クリア時）: フラグメントは**空ボディ 200** を返し、結果表示が消える。

## ルーティング（src/routers/web.py）

### 新規フラグメントルート

```python
SEARCH_LIMIT = 50      # 打ち切り上限
SEARCH_Q_MAX = 200     # q の最大長（超過分は切り捨て。エラーにしない）

@router.get("/{tenant}/cftree/doc/{doc_id}/search", response_class=HTMLResponse)
async def search_fragment(
    tenant: str,
    doc_id: str,
    request: Request,
    q: str = "",
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
```

処理（バリデーションは `children_fragment` と同一パターン・同一文言）:

1. テナント解決失敗 → 404 エラーフラグメント（`error_tenant_not_found`）。
2. `doc_id` が UUID でない → 400 フラグメント（`error_bad_request`）。ドキュメントが存在しない
   （`tree_service.get_document_for_tree` が None）→ 404 フラグメント（`error_document_not_found`）。
   **ドキュメント実在チェックが tenant スコープを兼ねる**（他テナントの doc は None になる）。
3. `q = q.strip()[:SEARCH_Q_MAX]`。空なら `HTMLResponse("", 200)`（結果クリア）。
4. `rows = await cf_item_repository.search_items(session, tenant_obj.id, q, document_id=doc.id, limit=SEARCH_LIMIT + 1)`
5. `truncated = len(rows) > SEARCH_LIMIT`、`rows = rows[:SEARCH_LIMIT]`。
6. `fragments/search_results.html` を描画（ctx: `q, rows, truncated, tenant_url, t`。
   `tenant_url` は `_tenant_url_segment(tenant, tenant_obj)` — sticky UUID/slug 規約に従う）。

**Cache-Control**: `CACHE_CONTROL_FRAGMENT`（`public, max-age=86400`）を設定する。
判断根拠: (a) 検索結果はインポートでしか変わらず、他の doc フラグメントと同じ変更頻度、
(b) URL のクエリ文字列（q）ごと共有キャッシュのキーになるので q 依存でも共有キャッシュ可能、
(c) パスが `/cftree/doc/{doc-uuid}/search` なので既存の CloudFront ワイルドカード invalidation
（`/{tenant}/cftree/doc/{doc-uuid}*`）がインポート時にそのまま効く。エラーフラグメント（4xx）は
既存方針どおり Cache-Control なし（`_error_fragment` がヘッダを付けないのでそのまま）。

### 既存ツリーページへの `?q=` 追加（no-JS SSR）

- `tree_view`（`GET /{tenant}/cftree/doc/{doc_id}`）に `q: str = Query(default=None)` を追加し、
  `_render_tree_page` に渡す。`/item/{id}` パスルートには追加しない（検索フォームの action は
  常にツリー根 URL）。
- `_render_tree_page` 内: `q` を strip/切り捨て後、非空なら `search_items` を実行し、ctx に
  `q, search_rows, search_truncated` を追加。cftree.html が `{% if q %}` で `#search-results` 内に
  `search_results.html` を SSR インクルードする（フラグメントと同一マークアップ）。
- `?item=` と `?q=` が同時に付いた場合は両方独立に処理する（ペインは item、結果ブロックは q）。
- ページ自体の Cache-Control は既存どおり `public, max-age=3600`（変更なし）。

## 廃止項目の扱い（B8-5）

検索結果からは、**廃止された CFItem を既定で除外する**。`?includeRetired=1` を付けたときだけ含め、そのときは結果行に廃止バッジを出す（ツリーと同じ見え方。[retired-item-ui.md](./retired-item-ui.md)）。

### ツリーの `hidden_identifiers` を流用しない

ツリーは「廃止済みでも、生きた子孫を持つなら残す」規則を採っている。生きた項目への経路が切れるからである。

**検索結果に経路は無い。** 平坦な一覧なので、廃止項目を残す理由がそのまま消える。したがって判定は `retirement.is_retired(item, today)` を直接使い、`hidden_identifiers()` は使わない。流用すると「生きた子孫を持つ廃止項目」が検索結果に出続け、除外した意味が薄くなる。

### SQL で絞る（後段フィルタにしない）

条件は `_list_items_where` の `conditions` に足す。

```python
if not include_retired:
    conditions.append(
        or_(CFItem.status_end_date.is_(None), CFItem.status_end_date > today)
    )
```

**取得後に Python で除くのは誤りである。** この設計は `limit=51` を取って 51 件目の有無で `has_more` を決める。後段で除くと、除いた件数だけページが目減りし、`has_more` も嘘になる。「次へ」を押すと項目が飛ぶ。

`today` は呼び出し側が UTC で1回求めて渡す（SQL 側で `CURRENT_DATE` を使わない。テストで日付を固定できなくなる）。

### パラメータの引き継ぎ

`includeRetired` は検索フォームの hidden input と、結果の「もっと見る」の URL に載せる。ツリー側のリンクにも同じ値が乗るので（B8-4 で実装済み）、検索とツリーを行き来してもモードが落ちない。

### インデックス

`status_end_date` の条件が付いても、既存の `ix_cf_items_tenant_document_coding` で対象ドキュメントに絞ってから ILIKE と日付の両方を評価する形は変わらない。B8-4 で足した部分インデックス `ix_cf_items_doc_retired` は墓標だけを含むので、この用途（生きた項目を残す条件）には効かない。追加のインデックスは要らない。

## リポジトリ（src/repositories/cf_item_repository.py）

既存の `_list_items_where` ヘルパ（label/link 列 + doc join + 安定ソート + offset/limit）を
そのまま使う。返値の形（`{identifier, human_coding_scheme, full_statement, doc_identifier,
doc_title}`）は `subject_items.html` の rows 契約と一致済み。

```python
def _escape_like(q: str) -> str:
    """LIKE パターンのメタ文字（\\ % _）をリテラル検索できるようエスケープする。"""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    *,
    document_id: uuid.UUID | None = None,
    include_retired: bool = False,
    today: date | None = None,
    offset: int = 0,
    limit: int = 51,
) -> list[dict]:
    """CFItem のキーワード部分一致検索（ILIKE・大文字小文字無視）。

    対象: full_statement / human_coding_scheme / abbreviated_statement の OR。
    テナントスコープ厳守。document_id 指定で 1 ドキュメントに限定
    （ツリービューは常に指定。将来のテナント横断入口は None を渡せる形）。
    """
    pattern = f"%{_escape_like(query)}%"
    conditions = [
        CFItem.tenant_id == tenant_id,
        or_(
            CFItem.full_statement.ilike(pattern, escape="\\"),
            CFItem.human_coding_scheme.ilike(pattern, escape="\\"),
            CFItem.abbreviated_statement.ilike(pattern, escape="\\"),
        ),
    ]
    if document_id is not None:
        conditions.append(CFItem.cf_document_id == document_id)
    if not include_retired:
        # B8-5: retired items are dropped in SQL, never after the fetch — the
        # limit+1 has_more trick breaks if rows disappear afterwards.
        conditions.append(or_(CFItem.status_end_date.is_(None), CFItem.status_end_date > today))
    return await _list_items_where(session, conditions, offset, limit)
```

- `or_` を `sqlalchemy` import に追加。`ilike(..., escape="\\")` は `ILIKE … ESCAPE '\'` を出力し、
  ユーザー入力中の `%` `_` `\` をリテラル扱いにする（`q="100%"` が「100 で始まる全件」に
  化けない）。
- **ソート順**: `_list_items_where` の既存安定順（`human_coding_scheme` NULLS LAST →
  `full_statement` → `identifier`）をそのまま使う。コード順はフレームワークの掲載順に近く、
  関連度ランキングは B2（意味検索）の役割とする。
- **性能**: 検索は常に `(tenant_id, cf_document_id)` で絞られ、既存 index
  `ix_cf_items_tenant_document_coding (tenant_id, cf_document_id, human_coding_scheme)` で対象
  ドキュメントの行に絞ってから ILIKE フィルタになる。1,557 項目規模では数 ms オーダーで十分。
  **pg_trgm 拡張 + GIN index（`gin_trgm_ops`）は数万〜数十万項目規模が出たときの追加最適化**とし、
  今回はマイグレーションを入れない（非対象。導入時は `CREATE EXTENSION pg_trgm` が必要で
  semantic-search.md の pgvector と同様に DB イメージ/CI へ波及するため、規模の実需が出てから）。

## i18n（src/locales/en.json / ja.json）

既存機構（`i18n.get_translator` + フラット JSON カタログ、`{key}` プレースホルダ置換）に従い
以下を **en / ja 両方**に追加する:

| キー | en | ja |
|---|---|---|
| `search_label` | Search in this framework | このフレームワーク内を検索 |
| `search_placeholder` | Search items… | 項目を検索… |
| `search_button` | Search | 検索 |
| `search_results_count` | {count} results | {count}件 |
| `search_results_truncated` | showing first {limit} | 先頭{limit}件を表示（キーワードを追加して絞り込んでください） |
| `search_no_results` | No items match "{q}" | 「{q}」に一致する項目はありません |

- プレースホルダ値は既存慣行どおり文字列で渡す（例:
  `t("search_results_count", count=rows|length|string)`）。
- CLI カタログ（`cli_*.json`）への追加はなし。

## アクセシビリティ

既存方針（native 要素・no-JS 耐性・`:focus-visible` リング）に従う:

- `<form role="search">` + `<label class="sr-only">`（または `aria-label`）+ `type="search"` の
  ネイティブ input / submit ボタン。キーボードのみで完結（Enter submit）。
- 結果コンテナ `#search-results` に `aria-live="polite"` — HTMX swap（インクリメンタル結果更新）を
  スクリーンリーダーが読み上げる。件数行が先頭にあるので更新の要旨が最初に伝わる。
- JS なしでは submit 型検索として完全動作（上記 no-JS フォールバック）。結果行は実 `<a href>`。
- `sr-only` ユーティリティは Tailwind 標準（ローカルビルド app.css に含まれる）。

## 考慮すべきエッジケース

- **空 / 空白のみの q**: strip 後空 → フラグメントは空ボディ 200（結果クリア）、ページ SSR は
  結果ブロック非表示。エラーにしない。
- **LIKE メタ文字**（`%` `_` `\`）: `_escape_like` でリテラル化。`q="%"` は「% を含む項目」の検索に
  なる（全件マッチではない）。
- **XSS**: `q` は `search_no_results` の文言等でエコーされるが Jinja autoescape で無害化。
  `search_results.html` に `|safe` を書かないこと。`<script>alert(1)</script>` を q に入れた
  結合テストで担保する。
- **q が 200 字超**: 黙って 200 字に切り捨て（パターン肥大の抑止。エラーにしない）。
  input 側にも `maxlength="200"`。
- **51 件以上ヒット**: 先頭 50 件 + 打ち切りメッセージ。COUNT クエリは発行しない（limit+1 検知）。
- **0 項目のドキュメント**: 検索フォームは表示してよい（常に 0 件表示になるだけ）。
- **大文字小文字**: ASCII は ILIKE で無視（"CRITICAL" が "critical thinking" にヒット）。日本語は
  case の概念がなくそのまま部分一致。**全角/半角・かな/カナ・NFKC 正規化はしない**（初版仕様として
  明記。正規化が要る場合は将来 `normalize()`（PG14+）または B2 の意味検索で吸収）。
- **多義 UUID / 別ドキュメントのアイテム**: 検索は `document_id` で絞るため、同一 identifier が
  別ドキュメントに存在しても現ドキュメントの行しか返らない。
- **private テナント**: 検索クエリが `tenant_id` + `cf_document_id` で完結しており、他テナントの
  データは構造上返り得ない（`_list_items_where` に渡す conditions でテナント条件必須）。
  結合テストで「同一 fullStatement を持つ別テナント項目がヒットしない」ことを固定する。
- **定義（lookup）・ルーブリックは検索対象外**: 対象は CFItem のみ。CFRubric の description 等は
  ヒットしない（初版仕様。必要なら将来拡張）。
- **HTMX 4xx フラグメント**: base.html の `htmx:beforeSwap`（`shouldSwap = true`）は全 swap に
  効くため、search のエラーフラグメントも `#search-results` に表示される（既存挙動、追加実装不要）。

## 変更するファイル

| ファイル | 変更内容 |
|---|---|
| `src/repositories/cf_item_repository.py` | `_escape_like()` / `search_items()` を追加（`_list_items_where` 再利用、`or_` import 追加） |
| `src/routers/web.py` | `SEARCH_LIMIT` / `SEARCH_Q_MAX` 定数、`search_fragment` ルート（`GET /{tenant}/cftree/doc/{doc_id}/search`）を追加。`tree_view` に `q` クエリパラメータ、`_render_tree_page` に SSR 検索を追加 |
| `src/templates/fragments/search_results.html` | 新規: 件数/0件/打ち切り + `subject_items.html` を include した行リスト |
| `src/templates/cftree.html` | 左ペイン上部に検索フォーム + `#search-results`（`{% if q %}` で SSR 結果を include） |
| `src/locales/en.json` / `src/locales/ja.json` | `search_*` 6 キーを追加 |
| `tests/unit/test_web_search.py` | 新規（下記テスト方針） |
| `docs/spec/web-ui.md` | ツリービュー節に「検索」サブセクション（EN/JA 両方）: フォーム位置・`/search` フラグメントルート・`?q=` SSR・上限 50・Cache-Control を追記。URL 設計表に `/search` 行を追加 |
| `docs/dev/backlog.md` | 本項目の行を追加し本設計ドキュメントへリンク（B2 の前段である旨を記載） |

`fragments/subject_items.html` は**無改修**（`has_more=False` で行のみ再利用）。
マイグレーションなし・依存追加なし・静的アセット追加なし。

## テスト方針（tests/unit/test_web_search.py）

`test_subject_items.py` の構成（リポジトリ層 + Web フラグメント層、`db_session` / `tenant` /
`sample_document` フィクスチャ、`httpx.AsyncClient` 相当の既存クライアントフィクスチャ）に倣う。

**リポジトリ（`search_items`）:**

- 3 フィールドそれぞれの部分一致でヒット（`full_statement` のみ / `human_coding_scheme` のみ /
  `abbreviated_statement` のみに語を仕込んだ 3 項目）。
- `notes` にだけ語がある項目はヒット**しない**。
- 大文字小文字無視: `q="CRITICAL"` が "critical thinking" にヒット。
- 日本語部分一致: `q="批判"` が「批判的思考ができる」にヒット。語中一致（`q="的思考"`）も確認。
- LIKE メタ文字: `full_statement="50% 以上"` の項目が `q="50%"` でヒットし、`%` が全件マッチに
  化けないこと（無関係項目が返らない）。`_` `\` も同様。
- `document_id` スコープ: 同一テナント別ドキュメントの同文項目が返らない。
- テナントスコープ: 別テナントに同一 fullStatement の項目を作り、返らないことを確認。
- limit: 60 件ヒットするデータで `limit=51` → 51 件返る（呼び出し側打ち切りの前提を固定）。

**フラグメントエンドポイント（`GET /{tenant}/cftree/doc/{doc}/search`）:**

- 正常系: 200、ヒット行の `humanCodingScheme` / `fullStatement` 断片と `/item/{id}` リンクを含む。
  `Cache-Control: public, max-age=86400`。
- 0 件: `search_no_results` 文言（ja / en どちらかで固定）を含む 200。
- 51+ 件: 先頭 50 行のみ + 打ち切り文言。
- 空 q / 空白のみ: 空ボディ 200。
- doc 限定: 別ドキュメントの項目・別テナントの項目（private 含む）が本文に現れない。
- バリデーション: 非 UUID doc → 400 フラグメント、実在しない doc / tenant → 404 フラグメント
  （エラー時 Cache-Control なし）。
- XSS: `q=<script>alert(1)</script>` → レスポンス本文に生の `<script>` が現れない
  （`&lt;script&gt;` にエスケープされている）。

**SSR（`GET /{tenant}/cftree/doc/{doc}?q=…`）:**

- 200 で結果ブロック（件数文言 + ヒット行）がページ内に SSR される。`?q=` なしでは結果ブロックが
  出ない。`?item=` と併用時に両方描画される。

## B2（意味検索）との関係 — UI 共有の構想

本機能は B2 の**前段**であり、B2 実装時に置き換えではなく統合する:

- **パス衝突なし**: B2 の API は `GET /{tenant}/search`（JSON・imsx エラー形式）、本機能は
  `GET /{tenant}/cftree/doc/{doc}/search`（HTML フラグメント）。共存できる。
- **検索ボックス UI は共有**: cftree.html の同じフォームを入口とし、B2 実装後は
  (a) モード切替（「キーワード / 意味」トグルで hx-get 先を切り替え）または
  (b) フォールバック（意味検索を既定にし、`embedding_enabled=false`・未インデックス時は本機能の
  ILIKE に自動フォールバック）のいずれかを B2 側設計で選ぶ。サーバー側はどちらも
  `search_results.html` + `subject_items.html` の行契約（`{identifier, human_coding_scheme,
  full_statement, doc_identifier, doc_title}`）に載せられる（B2 の `score` は行契約への追加列として
  表示拡張可能）。
- **リポジトリ関数のシグネチャも B2 を意識済み**: `search_items(..., document_id=None)` は
  テナント横断呼び出しが可能な形にしてあり、B2 の Web UI 入口（テナントページ検索）を作るとき
  ハイブリッド（キーワード + ベクトル）の キーワード側として再利用できる。

## 非対象（今回やらないこと）

- **pg_trgm 拡張 + GIN index**: 規模（数万項目〜）が出たときの追加最適化として見送り。DB イメージ /
  CI への波及を伴うため、実需が出た時点で単独のマイグレーションとして導入する。
  ※ `full_statement` / `abbreviated_statement` への ILIKE は index が効かない seq scan のため、数万件規模では
  体感遅延が出うる（1,557 件規模の現実データでは問題にならない）。その閾値を超えたら本項目を再訪する。
- **テナントページ（tenant.html）/ テナント横断・複数ドキュメント横断の検索**: B2 の検索 API と
  Web UI 入口を統合する際に設計。
- **意味検索そのもの**（backlog B2 / [semantic-search.md](./semantic-search.md)）。
- **notes / 定義（lookup）/ ルーブリックの検索対象化**（将来拡張）。
- **ヒット語のハイライト**（`<mark>`）と関連度ランキング。
- **検索結果のページネーション**（50 件打ち切りのみ）と検索 URL の `hx-push-url` 同期。
- **全角/半角・かな/カナ等の文字正規化**。
- **CASE 標準 API への検索追加**（本機能は Web UI 専用の compeito 拡張。`/ims/case/v1p1/` 配下には
  置かない）。
