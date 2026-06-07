# Web UI Specification

## Meaning of path parameters

- `{tenant}`: tenant URL segment. Resolved to a tenant by first trying to parse it as a UUID v4 (matches `tenants.id` — the canonical identifier) and, failing that, by looking it up against `tenants.slug` (the optional URL-friendly alias). Either form addresses the same tenant.
- `{tenant-uuid}`: tenant `id` (the UUID PK). Always valid as `{tenant}`; this is what CASE API responses use and what the Web UI emits for canonical permalinks / API URLs.
- `{tenant-slug}`: tenant `slug` (URL-friendly alias, optional). When set, the Web UI emits this in navigation `href` / HTMX URLs in place of the UUID. The slug never appears in CASE API response bodies; only canonical UUIDs do. See [cli.md](cli.md#tenant-slug-rules) for the slug format.
- `{doc-uuid}`: CFDocument `identifier` (the CASE identifier), not the internal PK (`id`). Same definition as in the Admin API.
- `{item-uuid}`: CFItem `identifier` (the CASE identifier), not the internal PK (`id`).
- `/uri/{uuid}`: the UUID searched across `identifier` columns within the tenant scope.

### UUID vs slug — which one appears where?

- **Navigation `href` / HTMX `hx-get` URLs (rendered on a tenant-scoped page)**: **sticky to the request URL form** — if the incoming request was `/{tenant-uuid}/...`, every nav link in the rendered page uses `{tenant-uuid}`; if the incoming request was `/{tenant-slug}/...`, every nav link uses `{tenant-slug}`. This prevents the URL bar from drifting mid-session (a visitor who arrived via a UUID permalink stays on UUID URLs as they navigate, and vice versa).
- **Navigation links on the public tenant list (`GET /`)**: not sticky — the index page has no incoming `{tenant}` form to inherit, so it emits `{tenant-slug}` when a slug is set, else `{tenant-uuid}`. This means the slug becomes the "discoverable" friendly URL.
- **Displayed permalink / CASE API URLs (the strings users copy)**: always `{tenant-uuid}`, regardless of the request URL form. These are canonical references stored by CASE clients (e.g., Open Badge Factory), so they must not change when a slug is added, renamed, or removed.
- **CASE API response bodies (`LinkURIDType.identifier` / `uri`)**: always `{tenant-uuid}`. The slug is a UI-only convenience and is intentionally absent from JSON-LD. URI fields are stamped at import time and never rewritten on slug change.

### Implications for static rendering

A static deployment (e.g., pre-rendering pages to S3 + CloudFront) must, for tenants that have a slug, generate **both** URL families — `/{tenant-uuid}/...` and `/{tenant-slug}/...` — and serve each as a distinct cached page. The two pages render the same content but with different nav `href` values (UUID-form vs slug-form), so they cannot share a cache entry. Tenants without a slug only need the UUID family.

## Response headers (Cache-Control)

**Standard pages** (`/`, `/{tenant}/`, `/cftree/doc/{doc}`, `/uri/{uuid}`): `Cache-Control: public, max-age=3600`.

**HTMX fragments** (`/cftree/doc/{doc}/children/{item}`, `/cftree/doc/{doc}/detail/{item}`): `Cache-Control: public, max-age=86400`. Tree sub-content changes infrequently, so the TTL is long; CloudFront invalidation refreshes it on import.

**Error responses** (4xx / 5xx): no `Cache-Control` (same policy as CASE API).

## URL design

| Path | Description |
|------|-------------|
| GET / | Public tenant list. Tenant names (private tenants hidden). Sort: `name ASC, id ASC`. Each name links to `/{tenant-uuid}/`. If there are no public tenants, show "No public tenants". |
| GET /{tenant-uuid}/ | Framework list: CFDocument title, lastChangeDateTime, item count (`SELECT COUNT(*) FROM cf_item WHERE cf_document_id = doc.id`). Sort: `title ASC, identifier ASC`. Each title links to `/{tenant-uuid}/cftree/doc/{doc-uuid}`. If no documents, show "No frameworks". |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid} | Tree view (Levels 1–2 SSR, Levels 3+ lazy-loaded via HTMX). |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/children/{item-uuid} | HTML fragment of child items (for HTMX). |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/detail/{item-uuid} | HTML fragment of an item's detail (for the HTMX right pane). |
| GET /{tenant-uuid}/uri/{uuid} | Resource detail page (HTML by default; **303 See Other** to the matching CASE API endpoint when the `Accept` header signals a JSON client — see [api-spec.md](api-spec.md#tenanturiuuid-content-negotiation)). |

## Tree view (`/cftree/doc/{doc-uuid}`)

A two-pane layout inspired by OpenSALT's tree view. Visually, use a modern Tailwind CSS default (do not copy OpenSALT's look).

**HTML `<title>`** per page:
- `GET /`: "COMPEITO" (fixed).
- `GET /{tenant}/`: "{tenant name} - COMPEITO".
- `GET /{tenant}/cftree/doc/{doc}`: "{document title} - {tenant name} - COMPEITO".
- `GET /{tenant}/uri/{uuid}`: depends on the resource type. CFItem → "{first 50 chars of fullStatement} - COMPEITO". CFDocument → "{title} - COMPEITO". Lookup / CFAssociation → "{title or identifier} - COMPEITO".
- Error pages: "{status code} - COMPEITO".

**HTML `<html lang>`**: `base.html` sets `lang="ja"` as a fixed value (the management UI is in Japanese). Even when a resource on a `/uri/` page has a `language` field, `<html lang>` is not changed (content language is expressed by the resource's `language` field, not by the `lang` attribute).

**Navigation:** every page shows a breadcrumb in the header:
- `GET /`: no breadcrumb (top page).
- `GET /{tenant}/`: "[Tenants](/)".
- `GET /{tenant}/cftree/doc/{doc}`: "[Tenants](/) > [Tenant name](/{tenant}/) > Document title" (the last segment is the current page, no link).
- `GET /{tenant}/uri/{uuid}`: depends on the resource. CFItem / CFAssociation → "[Tenants](/) > [Tenant name](/{tenant}/)" (the owning document is shown via `CFDocumentURI` inside the page). CFDocument → same. Lookup → same.

```
┌─────────────────────────────────────────────────────┐
│ Header: CFDocument title + adoptionStatus badge     │
├──────────────────────┬──────────────────────────────┤
│ Left pane (tree)     │ Right pane (detail)          │
│                      │                              │
│ ▼ Japanese           │ fullStatement                │
│   ▼ Modern Japanese  │ humanCodingScheme            │
│     【Knowledge & ..│ identifier                   │
│     ● Items on the …│ CFItemType                   │
│     ● Words have …  │ educationLevel               │
│   ▶ Language Culture │ "Detail" link → /uri/{uuid}  │
│ ▶ Geography & Hist.  │                              │
│ ▶ Civics             │                              │
└──────────────────────┴──────────────────────────────┘
```

- **Left pane**: tree structure. Click to expand/collapse (▶/▼). Clicking an item shows its details in the right pane. The display text for each item is `fullStatement` (truncated to 100 chars with "…" when long). When `humanCodingScheme` is non-NULL, it's shown before fullStatement (e.g., `A-1-(1) Items on …`). When `CFItemType` is non-NULL, it's shown as a small badge.
- **Right pane**: shows the detail of the selected item. A "Detail" link goes to `/uri/{uuid}`. The detail HTML fragment is swapped in via HTMX `hx-get` (fragment endpoint: `GET /{tenant}/cftree/doc/{doc-uuid}/detail/{item-uuid}`, returns an HTML fragment).
  - **Fields shown for the selected item**: fullStatement, humanCodingScheme (non-NULL), identifier, CFItemType (non-NULL), educationLevel (non-NULL), language (non-NULL), conceptKeywords (non-NULL), and a "Detail" link to `/uri/{uuid}`.
  - **Initial state** (no item selected): show CFDocument info in the right pane (title, description, adoptionStatus, lastChangeDateTime, version, language). Additionally, if the document has any CFRubric rows, show a rubric list section (each rubric's title links to `/uri/{rubric-uuid}`; if title is null, show identifier; sort by `identifier ASC`; hide the entire section if there are no rubrics). If the document has 0 items, show "No items" in the left pane.
  - On access with `?item={item-uuid}`, the target item is shown as selected, with its detail rendered inline via SSR (no extra HTMX fetch). If the value isn't a UUID, doesn't exist, or belongs to a different document, the parameter is ignored and the initial state is shown.
- **Responsive**: on mobile the layout stacks (tree on top, detail pane below) so all info is reachable without leaving the page. HTMX runs in both layouts — tapping an item swaps `#detail-pane` content and, on mobile (`window.innerWidth < 768`), smooth-scrolls to the detail pane. The `<a href="/{tenant}/uri/{item-uuid}">` fallback is preserved for non-JS clients and middle-click / ⌘-click navigation. Above the tree, show the CFDocument's title and a "Document detail" link (`/{tenant}/uri/{doc-uuid}`) so document info is reachable on mobile.

### Level detection and initial expansion

`cf_item.depth` is stored in the column (computed at import time by recursively following `isChildOf`).
Levels 1–2 = depth 0–1 are returned via SSR; depth 2+ are lazy-loaded via HTMX.
**SSR item sort order**: every item returned via SSR (depth 0–1 and items along an `?item=` expand path) follows the same order as the `/children/` fragment (`sequence_number` ASC → `human_coding_scheme` natural sort → `identifier` lexicographic; NULL last).
**Initial expand state**: depth 0 items are shown expanded (▼) with their depth 1 children visible. Depth 1 items are shown collapsed (▶) when they have children, or as leaves (●) otherwise. This makes the first two levels visible on the initial render.
**Exception**: with `?item={item-uuid}`, all items on the expand path from the root to that item (including depth 2+) are also returned via SSR. The expand path is computed by walking `isChildOf` ancestors within the same document (same scope as the `/children/` endpoint; `isChildOf` in other documents is out of scope). Children of each node on the path are also included in SSR (siblings of items not on the expand path use the normal lazy-load rule). When an item has multiple `isChildOf` parents, the same rule as the "Show in tree" link on the `/uri/` page applies (smallest `sequence_number`, NULL after non-NULL → `destination_node_identifier` lexicographic). **Orphan items** (those without an `isChildOf`) yield an empty expand path, and SSR returns them as part of the root-level orphan list (the normal depth 0–1 expansion plus the expanded orphan list).

### Children retrieval (`/children/{item-uuid}`)

Searches for `isChildOf` associations whose `destination_node_identifier = item-uuid`. The search scope is restricted to the document specified by `{doc-uuid}` (resolve `{doc-uuid}` = CFDocument `identifier` to the internal PK, then filter by `cf_association.cf_document_id`; `isChildOf` in other documents is excluded).
For each association, fetch the item pointed to by `origin_node_identifier` (the child).
Sort by `sequence_number` ASC. When `sequence_number` is NULL, place those rows at the end. When `sequence_number` matches, sort by `human_coding_scheme` natural-sort (numeric parts compared numerically; e.g., `"A-2"` < `"A-10"`; defaults from Python `natsort.natsorted()`; NULL after non-NULL). For further ties, use `identifier` lexicographic order (same rule as the export sort).

**Orphan items**: items without any `isChildOf` association (e.g., when associations were skipped during external CASE source import) are not returned via the children query. They are appended at the end of the root level: depth=0 items that are **not** an origin of any `isChildOf` within the **same document** (items that only appear as origins of `isChildOf` in other documents are also treated as orphans in the current document). The sort order is the same as above, with `sequence_number` always treated as NULL.

**Expand icons (▶/▼)**: whether each item has children is decided by whether the same document's `isChildOf` association table contains its `identifier` as a `destination_node_identifier`. Items with children show ▶, leaves show ●. The same check is applied to children returned in a `/children/` fragment (to avoid N+1, the existence of grandchildren is fetched in bulk along with the children).

> Note: `origin isChildOf destination` reads as "origin is a child of destination". To find children, search on the destination side.

Including `{doc-uuid}` in the children path lets CloudFront invalidate `/{tenant}/cftree/doc/{doc-uuid}*` in one go.

## `/uri/{uuid}` detail page

A public page linked from external systems such as Open Badge Factory. Use OpenSALT's `/uri/{uuid}` page as a reference, with a modern Tailwind CSS default look.
Hide fields with no value (omit the whole row). "No value" means `null`, an empty string `""`, or an empty array `[]`. JSONB array fields (`educationLevel`, `conceptKeywords`, `subject`, etc.) are also hidden for `null` or `[]`.

**Content negotiation:** the same URL doubles as the JSON identifier for CASE clients. When the request's `Accept` header signals a JSON consumer (contains `application/json` or `application/ld+json` AND does not contain `text/html`), the handler responds with **303 See Other** pointing to the matching CASE API endpoint (e.g., CFItem → `/{tenant}/ims/case/v1p1/CFItems/{uuid}`). Otherwise the HTML page below is served. Resource types without an individual CASE API endpoint (CFRubricCriterion / CFRubricCriterionLevel) always serve HTML. See [api-spec.md](api-spec.md#tenanturiuuid-content-negotiation) for details.

**Security:** URL fields (`uri`, `officialSourceURL`, the `uri` field in LinkURIDType, etc.) are rendered as clickable links **only** when the scheme is `http:` / `https:`. Other schemes (e.g., `javascript:`, `data:`) are rendered as plain text (to prevent XSS). All text fields are HTML-escaped via Jinja2 autoescaping.

### CFItem

| Field | Required/Optional | Display |
|-------|-------------------|---------|
| identifier | required | UUID |
| uri | required | URL (link) |
| CFDocumentURI | required | Nested display (title, identifier, uri); title links to the tree view |
| fullStatement | required | Text |
| lastChangeDateTime | required | ISO 8601 |
| humanCodingScheme | optional | Text |
| abbreviatedStatement | optional | Text |
| CFItemType | optional | Nested display of CFItemTypeURI (title, identifier, uri) |
| educationLevel | optional | Array shown comma-separated |
| conceptKeywords | optional | Array shown comma-separated |
| conceptKeywordsURI | optional | Nested display (title, identifier, uri); built from `cf_concept_id` FK |
| subject | optional | Array shown comma-separated (v1.1 new; may be set via external import) |
| subjectURI | optional | Each element shown as a nested object (title, identifier, uri); array (v1.1 new) |
| language | optional | Language code |
| licenseURI | optional | Nested display (title, identifier, uri); same shape as CFItemTypeURI |
| statusStartDate | optional | Date |
| statusEndDate | optional | Date |
| listEnumeration | optional | Text |
| "Show in tree" link | — | Navigates to `/{tenant}/cftree/doc/{doc-uuid}?item={item-uuid}`. The server computes the expand path from root to this item and SSR-renders the tree expanded through that node. When the item has multiple `isChildOf` parents, the association with the smallest `sequence_number` wins (NULL after non-NULL; tie-broken by `destination_node_identifier` lexicographic — same parent-selection rule as export). |

### CFDocument

| Field | Required/Optional | Display |
|-------|-------------------|---------|
| identifier | required | UUID |
| uri | required | URL (link) |
| title | required | Text |
| lastChangeDateTime | required | ISO 8601 |
| creator | optional (required in CASE v1.1 but DB is nullable) | Text |
| publisher | optional | Text |
| description | optional | Text |
| language | optional | Language code |
| version | optional | Text |
| adoptionStatus | optional | Badge (Draft / Private Draft / Adopted / Deprecated) |
| statusStartDate | optional | Date |
| statusEndDate | optional | Date |
| licenseURI | optional | Nested (title, identifier, uri); same as CFItem |
| officialSourceURL | optional | URL (link) |
| frameworkType | optional | Text (v1.1 new; may be set via external import) |
| caseVersion | optional | Text (v1.1 new; valid value is "1.1") |
| subject | optional | Array shown comma-separated |
| subjectURI | optional | Each element nested (title, identifier, uri); array |
| CFPackageURI | required | Nested (title, identifier, uri) |
| "Show in tree" link | — | Navigates to the tree view's root |

### Lookup resources (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping)

When `/uri/{uuid}` resolves to a lookup, show common + specific fields:

| Field | Display |
|-------|---------|
| identifier | UUID |
| uri | URL (link) |
| title | Text |
| description | Text (only when present) |
| Resource type | Badge (e.g., "CFItemType", "CFSubject") |
| Specific fields | typeCode, hierarchyCode, licenseText, etc. (only when present) |
| lastChangeDateTime | ISO 8601 |

### CFRubric

When `/uri/{uuid}` resolves to a CFRubric, show the rubric detail along with Criteria/Levels in a table:

| Field | Required/Optional | Display |
|-------|-------------------|---------|
| identifier | required | UUID |
| uri | required | URL (link) |
| CFDocumentURI | — | Nested (title, identifier, uri); title links to the tree view |
| title | optional | Text |
| description | optional | Text |
| lastChangeDateTime | required | ISO 8601 |
| CFRubricCriteria | optional | Table or list (see below) |
| "Show in tree" link | — | Navigates to the tree view root |

**Rubric tabular display:**
Rows are CFRubricCriterion; columns are CFRubricCriterionLevel.

- **Columns**: collect the unique `position` values across all criteria's levels. Column headers show `quality` (when available) and `score` (when available). Sort columns by position ASC.
- **Rows**: each criterion (`position` ASC → `identifier` ASC). Row header shows `category`, `description`, `weight` (when available), `CFItemURI` (when available).
- **Cells**: the level `description` for that criterion × position. If `feedback` exists, also display it.
- **When criteria have different level counts**: leave the missing cells empty.

**List fallback**: when the levels cannot be arranged in a table (e.g., all `position` are null), render as a list (each criterion as a card containing its levels).

**Tabular display condition**: use the table when at least one criterion exists and at least one level has a `position` set.

### CFRubricCriterion

When `/uri/{uuid}` resolves to a CFRubricCriterion:

| Field | Display |
|-------|---------|
| identifier | UUID |
| uri | URL (link) |
| category | Text (only when present) |
| description | Text (only when present) |
| CFItemURI | Nested display (only when present) |
| weight | Number (only when present) |
| position | Number (only when present) |
| lastChangeDateTime | ISO 8601 |
| Owning rubric | Link to the CFRubric `/uri/` page |
| CFRubricCriterionLevels | List of child levels |

### CFRubricCriterionLevel

When `/uri/{uuid}` resolves to a CFRubricCriterionLevel:

| Field | Display |
|-------|---------|
| identifier | UUID |
| uri | URL (link) |
| description | Text (only when present) |
| quality | Text (only when present) |
| score | Number (only when present) |
| feedback | Text (only when present) |
| position | Number (only when present) |
| lastChangeDateTime | ISO 8601 |
| Owning criterion | Link to the CFRubricCriterion `/uri/` page |

### CFAssociation

When `/uri/{uuid}` resolves to a CFAssociation, show the minimal fields:

| Field | Display |
|-------|---------|
| identifier | UUID |
| uri | URL (link) |
| CFDocumentURI | Nested (title, identifier, uri); title links to the tree view |
| associationType | Text (e.g., isChildOf) |
| originNodeURI | Nested (title, identifier, uri, targetType); show targetType only when present |
| destinationNodeURI | Nested (title, identifier, uri, targetType); show targetType only when present |
| sequenceNumber | Number (only when present) |
| CFAssociationGroupingURI | Nested (title, identifier, uri) (only when present) |
| lastChangeDateTime | ISO 8601 |

## Validation

Web UI paths follow the same validation as the CASE API and render the error page:
- `{tenant-uuid}` is not a UUID → 400 page.
- Valid UUID but the tenant doesn't exist → 404 page.
- **Direct access to a private tenant**: a path under `/{tenant-uuid}/` is rendered normally even if the tenant is private (access control is by URL secrecy; see architecture.md). Only `GET /` hides private tenants from the list.
- `{doc-uuid}` is not a UUID → 400 page.
- Valid UUID but the document doesn't exist → 404 page.
- `{uuid}` in `/uri/{uuid}` is not a UUID → 400 page.
- `/uri/{uuid}` finds no resource within the tenant scope → 404 page.
- `/children/` and `/detail/` endpoints: `{tenant-uuid}` is not a UUID → 400 (HTML fragment "リクエストが不正です" + status 400; not the full error page — return a fragment for HTMX swap).
- `/children/` and `/detail/` endpoints: valid UUID but tenant doesn't exist → 404 (HTML fragment "テナントが見つかりません" + status 404).
- `/children/` and `/detail/` endpoints: `{doc-uuid}` is not a UUID → 400 (HTML fragment "リクエストが不正です" + status 400).
- `/children/` and `/detail/` endpoints: valid UUID but document doesn't exist → 404 (HTML fragment "ドキュメントが見つかりません" + status 404).
- `/children/{item-uuid}` with non-UUID `{item-uuid}` → 400 (empty HTML fragment + status 400).
- `/children/{item-uuid}` with valid UUID but the item doesn't exist (or exists but isn't in `{doc-uuid}`) → empty HTML fragment (200; same as "no children". The association's `cf_document_id` scope filters naturally).
- `/detail/{item-uuid}` with non-UUID `{item-uuid}` → 400 (empty HTML fragment + status 400).
- `/detail/{item-uuid}` with valid UUID but the item doesn't exist → 404 error fragment.
- `/detail/{item-uuid}` with valid UUID and item exists but belongs to a different document → 404 error fragment (do not show another document's item inside this tree view).
- The 404 error fragment for `/detail/` is an HTML fragment "アイテムが見つかりません" with status 404.
- 500 Internal Server Error on `/children/` or `/detail/` → HTML fragment "サーバーエラーが発生しました" + status 500.
- **HTMX non-2xx response handling**: HTMX does not swap content from non-2xx responses by default. To show 400/404/500 error fragments in the right pane, set `shouldSwap = true` in the `htmx:beforeSwap` event handler (in `base.html`).

## Error pages

Error display for the Web UI. Styled with Tailwind CSS, user-friendly.

| HTTP status | Display |
|-------------|---------|
| 404 | "Page not found" + link back to `/` |
| 400 | "Bad request" + details + link back to `/` |
| 500 | "Server error" + link back to `/` |

Template: `src/templates/error.html` (a shared error template that receives the status code and message).

## URI generation rule

The `uri` field of CASE resources points at `/uri/{uuid}` (same pattern as OpenSALT):
`https://example.com/{tenant-uuid}/uri/{resource-uuid}`

- `config.py` has a `BASE_URL` setting (e.g., `https://case.example.com`).
- Docker default: `http://localhost:8000`.
- Override via the `BASE_URL` env var.
- On create: `uri = f"{BASE_URL}/{tenant_id}/uri/{identifier}"`.
- **On external import**: the original `uri` is preserved (not overwritten).
  Even resources with external URIs are also reachable via our own `/uri/{uuid}` because the `/uri/{uuid}` router searches by `identifier` (independent of the DB `uri` column).

---

# Web UI 仕様（日本語）

## パスパラメータの意味

- `{tenant}`: テナント URL セグメント。まず UUID v4 として解釈を試み（`tenants.id` — canonical な識別子）、解釈失敗時に `tenants.slug`（任意の URL 別名）で検索する。どちらの形式でも同一テナントを指す
- `{tenant-uuid}`: テナント `id`（UUID PK）。常に `{tenant}` として有効。CASE API レスポンスおよび Web UI の canonical な permalink / API URL 表示はこちらを使う
- `{tenant-slug}`: テナント `slug`（URL 別名、任意）。設定されていれば Web UI のナビゲーション `href` / HTMX URL では UUID の代わりに slug を出力する。CASE API レスポンス本文に slug が現れることはなく、canonical な UUID のみが返される。slug のフォーマット仕様は [cli.md](cli.md#テナント-slug-の制約) を参照
- `{doc-uuid}`: CFDocument の `identifier`（CASE識別子）。内部PK（`id`）ではない。Admin API と同一定義
- `{item-uuid}`: CFItem の `identifier`（CASE識別子）。内部PK（`id`）ではない
- `/uri/{uuid}`: テナントスコープ内で `identifier` カラムを横断検索する UUID

### UUID と slug の使い分け

- **ナビゲーションの `href` / HTMX `hx-get` URL（テナントスコープのページ内）**: **リクエスト URL の形に sticky** — `/{tenant-uuid}/...` でアクセスされたら描画されるページ内の全ナビリンクは `{tenant-uuid}`、`/{tenant-slug}/...` なら全部 `{tenant-slug}` を出力する。これにより URL バーがセッション中に勝手に切り替わる挙動を防ぐ（UUID パーマリンクで来た訪問者は UUID URL のまま回遊し、slug で来た人は slug のまま回遊する）
- **公開テナント一覧（`GET /`）のナビリンク**: sticky の対象外 — リクエスト URL に `{tenant}` が含まれないため継承元がない。slug があれば `{tenant-slug}`、なければ `{tenant-uuid}` を出力する。これにより「最初に見える URL」は slug 形式となり、共有 / ブックマーク用の入口が読みやすい形に揃う
- **画面に表示する permalink / CASE API URL（ユーザーがコピーする文字列）**: リクエスト URL の形に関わらず常に `{tenant-uuid}`。これらは CASE クライアント（Open Badge Factory など）が保存する canonical な参照なので、slug を追加・変更・削除しても壊れない
- **CASE API レスポンス本文（`LinkURIDType.identifier` / `uri`）**: 常に `{tenant-uuid}`。slug は UI 上の利便性のみを目的とし、JSON-LD 上には意図的に現れない。URI フィールドはインポート時に書き込まれ、slug 変更で再書き込みはしない

### 静的レンダリングへの含意

静的デプロイ（事前レンダした HTML を S3 + CloudFront 等で配信する構成）では、slug が設定されたテナントについて **両形式** — `/{tenant-uuid}/...` と `/{tenant-slug}/...` — を別々のキャッシュエントリとして書き出す必要がある。両者は本文は同じだがナビ `href` の値が異なる（UUID 形式 vs slug 形式）ため、同一キャッシュは共有できない。slug 未設定のテナントは UUID 形式のみで足りる。

## レスポンスヘッダー（Cache-Control）

**通常ページ**（`/`, `/{tenant}/`, `/cftree/doc/{doc}`, `/uri/{uuid}`）: `Cache-Control: public, max-age=3600`

**HTMX フラグメント**（`/cftree/doc/{doc}/children/{item}`, `/cftree/doc/{doc}/detail/{item}`）: `Cache-Control: public, max-age=86400`（ツリーの部分コンテンツは変更頻度が低いため長めに設定。インポート時に CloudFront invalidation で即時更新）

**エラーレスポンス**（4xx/5xx）: `Cache-Control` を設定しない（CASE API と同一方針）。

## URLパス設計

| Path | 説明 |
|------|------|
| GET / | 公開テナント一覧: テナント名の一覧（privateは非表示）。`name ASC, id ASC` でソート。各テナント名は `/{tenant-uuid}/` へのリンク。公開テナントが0件の場合は「公開テナントはありません」を表示 |
| GET /{tenant-uuid}/ | フレームワーク一覧: CFDocumentのtitle, lastChangeDateTime, アイテム数（`SELECT COUNT(*) FROM cf_item WHERE cf_document_id = doc.id`）。`title ASC, identifier ASC` でソート。各ドキュメントのタイトルは `/{tenant-uuid}/cftree/doc/{doc-uuid}` へのリンク。ドキュメントが0件の場合は「フレームワークはありません」を表示 |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid} | ツリービュー (Level 1-2をSSR、Level 3+はHTMX遅延ロード) |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/children/{item-uuid} | 子アイテムHTMLフラグメント (HTMX用) |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/detail/{item-uuid} | アイテム詳細HTMLフラグメント (HTMX右ペイン用) |
| GET /{tenant-uuid}/uri/{uuid} | リソース詳細ページ（デフォルトは HTML。`Accept` が JSON クライアントを示す場合は該当 CASE API エンドポイントへ **303 See Other**。詳細は [api-spec.md](api-spec.md#tenanturiuuid-のコンテントネゴシエーション) を参照） |

## ツリービュー (`/cftree/doc/{doc-uuid}`)

OpenSALT のツリービューを参考にした 2 ペイン構成。見た目は Tailwind CSS のデフォルトスタイルでモダンに仕上げる（OpenSALT の見た目をコピーしない）。

**HTML `<title>` 要素:** ページごとに設定する:
- `GET /`: 「COMPEITO」（固定）
- `GET /{tenant}/`: 「{テナント名} - COMPEITO」
- `GET /{tenant}/cftree/doc/{doc}`: 「{ドキュメントタイトル} - {テナント名} - COMPEITO」
- `GET /{tenant}/uri/{uuid}`: リソース種別による。CFItem → 「{fullStatement の先頭50文字} - COMPEITO」。CFDocument → 「{title} - COMPEITO」。lookup/CFAssociation → 「{title or identifier} - COMPEITO」
- エラーページ: 「{ステータスコード} - COMPEITO」

**HTML `<html lang>` 属性:** `base.html` で `lang="ja"` を固定値として設定する（管理UIの言語が日本語であるため）。`/uri/` ページでリソースに `language` フィールドがある場合も `<html lang>` は変更しない（コンテンツの言語は `lang` 属性ではなくリソースの `language` フィールドで表現される）。

**ナビゲーション:** 全ページ共通でパンくずリンクをヘッダーに表示する:
- `GET /`: パンくずなし（トップページ自体）
- `GET /{tenant}/`: 「[テナント一覧](/)」
- `GET /{tenant}/cftree/doc/{doc}`: 「[テナント一覧](/) > [テナント名](/{tenant}/) > ドキュメントタイトル」（最後の要素は現在のページなのでリンクなし）
- `GET /{tenant}/uri/{uuid}`: リソース種別による。CFItem・CFAssociation → 「[テナント一覧](/) > [テナント名](/{tenant}/)」（所属ドキュメントはページ内の CFDocumentURI に表示）。CFDocument → 「[テナント一覧](/) > [テナント名](/{tenant}/)」。lookup リソース → 「[テナント一覧](/) > [テナント名](/{tenant}/)」

```
┌─────────────────────────────────────────────────────┐
│ ヘッダー: CFDocument title + adoptionStatus バッジ    │
├──────────────────────┬──────────────────────────────┤
│ 左ペイン（ツリー）     │ 右ペイン（詳細）              │
│                      │                              │
│ ▼ 国語               │ fullStatement                │
│   ▼ 現代の国語        │ humanCodingScheme            │
│     【知識及び技能】   │ identifier                   │
│     ● 言葉の特徴や... │ CFItemType                   │
│     ● 言葉には...     │ educationLevel               │
│   ▶ 言語文化          │ 「詳細」リンク → /uri/{uuid}  │
│ ▶ 地理歴史            │                              │
│ ▶ 公民                │                              │
└──────────────────────┴──────────────────────────────┘
```

- **左ペイン**: ツリー構造。クリックで展開/折りたたみ（▶/▼）。アイテムクリックで右ペインに詳細表示。各アイテムの表示テキストは `fullStatement`（長い場合は先頭100文字で打ち切り「...」を付与）。`humanCodingScheme` が非 NULL の場合は fullStatement の前に表示する（例: `A-1-(1) 実社会に必要な...`）。`CFItemType` が非 NULL の場合は小さなバッジで表示する
- **右ペイン**: 選択アイテムの詳細フィールドを表示。`/uri/{uuid}` への「詳細」リンク。HTMX `hx-get` でアイテム詳細フラグメントを取得して差し替える（フラグメントエンドポイント: `GET /{tenant}/cftree/doc/{doc-uuid}/detail/{item-uuid}`、HTMLフラグメントを返す）。
  - **アイテム選択時の表示フィールド**: fullStatement、humanCodingScheme（非NULL時）、identifier、CFItemType（非NULL時）、educationLevel（非NULL時）、language（非NULL時）、conceptKeywords（非NULL時）、`/uri/{uuid}` への「詳細」リンク
  - **初期状態**（アイテム未選択時）: CFDocument の情報（title, description, adoptionStatus, lastChangeDateTime, version, language）を右ペインに表示する。さらに、Document に属する CFRubric がある場合は、ルーブリック一覧セクションを表示する（各ルーブリックは title をリンクとして `/uri/{rubric-uuid}` に遷移。title が null の場合は identifier を表示。ソートは `identifier ASC`。0件の場合はセクション自体を非表示）。ドキュメントにアイテムが0件の場合、左ペインに「アイテムがありません」メッセージを表示する
  - `?item={item-uuid}` パラメータ付きアクセス時は該当アイテムを選択状態で表示する。右ペインの詳細も SSR でインライン出力する（HTMX での追加フェッチは不要）。UUID形式でない場合・該当アイテムが存在しない場合・該当アイテムが別ドキュメントに属する場合はパラメータを無視し初期状態を表示する
- **レスポンシブ**: モバイルではレイアウトを縦積みにし（ツリーが上、詳細ペインが下）、ページ遷移なしですべての情報にアクセスできるようにする。HTMX はモバイル / デスクトップの両方で動作し、アイテムタップで `#detail-pane` の中身を入れ替える。モバイル（`window.innerWidth < 768`）では入れ替え後に詳細ペインへスムーズスクロールする。非 JS クライアントや中クリック / ⌘+クリックでの遷移用に `<a href="/{tenant}/uri/{item-uuid}">` のフォールバックは残す。ツリー上部に CFDocument のタイトルと「ドキュメント詳細」リンク（`/{tenant}/uri/{doc-uuid}`）を表示し、モバイルでもドキュメント情報にアクセスしやすくする

### Level判定と初期展開状態
`cf_item.depth` カラムに格納（インポート時に `isChildOf` を再帰的にたどって計算）。
Level 1-2 = depth 0-1 をSSRで返し、depth 2+ はHTMX遅延ロード。
**SSR アイテムのソート順:** SSR で返す全アイテム（depth 0-1、および `?item=` 展開パス上のアイテム）のソート順は `/children/` フラグメントのソート順と同一とする（`sequence_number` 昇順 → `human_coding_scheme` 自然順ソート → `identifier` 辞書順。NULL は最後に配置）。
**初期展開状態:** depth 0 アイテムは展開状態（▼）で表示し、depth 1 の子アイテムを表示する。depth 1 アイテムは子を持つ場合は折りたたみ状態（▶）、子がない場合はリーフ（●）で表示する。これにより初期表示でツリーの2階層が一度に見える。
**例外**: `?item={item-uuid}` パラメータ付きアクセス時は、ルートからそのアイテムまでの展開パス上にある全アイテム（depth 2+ を含む）もSSRで返す。展開パスの計算は同一ドキュメント内の isChildOf を祖先方向にたどる（`/children/` エンドポイントと同じドキュメントスコープ。別ドキュメントの isChildOf は対象外）。パス上の各ノードの子もSSRに含める（展開パスから外れる兄弟ノードの子は通常ルール通りHTMX遅延ロード）。アイテムが複数の isChildOf 親を持つ場合は、`/uri/` ページの「ツリーで表示」リンクと同一ルール（`sequence_number` 最小、NULL は非NULLの後 → `destination_node_identifier` 辞書順）で親を選択する。**孤立アイテム**（isChildOf を持たないアイテム）の場合は展開パスが空となり、ルートレベルの孤立アイテム一覧にそのアイテムが含まれる状態で SSR を返す（通常の depth 0-1 展開に加えて孤立アイテム一覧も展開済み）。

### 子アイテム取得 (`/children/{item-uuid}`)
`isChildOf` association で `destination_node_identifier = item-uuid` の association を検索する。検索スコープはパスの `{doc-uuid}` で指定されたドキュメント内に限定する（`{doc-uuid}` = CFDocument の `identifier` → 対応する内部PK を解決し、`cf_association.cf_document_id` でフィルタする。別ドキュメントの isChildOf は含めない）。
各 association の `origin_node_identifier` が指すアイテム（= 子アイテム）を取得する。
`sequence_number` 昇順でソートする。`sequence_number` が NULL の場合は最後に配置する。`sequence_number` が同じ場合は `human_coding_scheme` の自然順ソート（数値部分を数値として比較する。例: `"A-2"` < `"A-10"`。Python の `natsort.natsorted()` デフォルト設定。NULL は非NULLの後に配置する）、それも同じ場合は `identifier` の辞書順（エクスポートのソート順と同一ルール）。

**孤立アイテムの表示:** isChildOf Association を持たないアイテム（外部CASEソースインポートで association がスキップされた場合等に発生しうる）は、ツリーの children クエリでは取得されない。これらのアイテムはルートレベルの末尾に別途表示する（depth=0 のアイテムのうち、**同一ドキュメント内の** isChildOf の origin でないものを追加取得する。別ドキュメントの isChildOf でのみ origin となっているアイテムも、現在のドキュメント内では孤立として扱う）。ソート順は上記と同じだが、sequence_number は常に NULL 扱いとなる。

**展開アイコン（▶/▼）の判定:** 各アイテムが子を持つかどうかは、同一ドキュメント内の isChildOf Association の `destination_node_identifier` にそのアイテムの `identifier` が存在するかで判定する。子が存在するアイテムには展開アイコン（▶）を表示し、存在しないアイテムにはリーフアイコン（●）を表示する。`/children/` フラグメントのレスポンスに含まれる各子アイテムにもこの判定を適用する（N+1 クエリ回避のため、子アイテム取得時に孫の存在を一括で確認する）。

※ `origin isChildOf destination` = 「origin は destination の子」。
子を探すには destination 側で検索する。

childrenパスに `{doc-uuid}` を含めることで、CloudFrontのワイルドカード
`/{tenant}/cftree/doc/{doc-uuid}*` で一括invalidation可能。

## `/uri/{uuid}` 詳細ページ

Open Badge Factory 等の外部システムからリンクされる公開ページ。
OpenSALT の `/uri/{uuid}` ページを参考にしつつ、デザインは Tailwind CSS のデフォルトスタイルでモダンに仕上げる。
値がないフィールドは非表示（行ごと省略）。「値がない」の定義: `null`、空文字列 `""`、空配列 `[]` のいずれも非表示とする。JSONB 配列フィールド（`educationLevel`, `conceptKeywords`, `subject` 等）は `null` でも `[]` でも行を表示しない。

**コンテントネゴシエーション:** この URL は CASE クライアント向けの JSON 識別子も兼ねる。リクエストの `Accept` ヘッダが JSON クライアント（`application/json` または `application/ld+json` を含み、かつ `text/html` を含まない）を示す場合、該当する CASE API エンドポイント（例: CFItem → `/{tenant}/ims/case/v1p1/CFItems/{uuid}`）へ **303 See Other** リダイレクトを返す。それ以外は本セクションで定義する HTML ページを返す。CASE API エンドポイントを持たないリソース種別（CFRubricCriterion / CFRubricCriterionLevel）は常に HTML を返す。詳細は [api-spec.md](api-spec.md#tenanturiuuid-のコンテントネゴシエーション) を参照。

**セキュリティ:** URL として表示するフィールド（`uri`, `officialSourceURL`, LinkURIDType 内の `uri` 等）は、`http:` / `https:` スキームの場合のみクリック可能なリンクとして描画する。それ以外のスキーム（`javascript:`, `data:` 等）はプレーンテキストとして表示する（XSS 防止）。全テキストフィールドは Jinja2 の autoescaping で HTML エスケープする。

### CFItem の場合

| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID |
| uri | 必須 | URL（リンク） |
| CFDocumentURI | 必須 | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| fullStatement | 必須 | テキスト |
| lastChangeDateTime | 必須 | ISO 8601 |
| humanCodingScheme | 任意 | テキスト |
| abbreviatedStatement | 任意 | テキスト |
| CFItemType | 任意 | CFItemTypeURI のネスト表示（title, identifier, uri） |
| educationLevel | 任意 | 配列をカンマ区切りで表示 |
| conceptKeywords | 任意 | 配列をカンマ区切りで表示 |
| conceptKeywordsURI | 任意 | ネスト表示（title, identifier, uri）。cf_concept_id FK から構築 |
| subject | 任意 | 配列をカンマ区切りで表示（v1.1 new。外部インポート由来で設定される場合がある） |
| subjectURI | 任意 | 各要素のネスト表示（title, identifier, uri）。配列（v1.1 new） |
| language | 任意 | 言語コード |
| licenseURI | 任意 | ネスト表示（title, identifier, uri）。CFItemTypeURI と同一形式 |
| statusStartDate | 任意 | 日付 |
| statusEndDate | 任意 | 日付 |
| listEnumeration | 任意 | テキスト |
| 「ツリーで表示」リンク | - | `/{tenant}/cftree/doc/{doc-uuid}?item={item-uuid}` へ遷移。サーバー側でルートからこのアイテムまでの展開パスを計算し、該当ノードまで展開済みのツリーをSSRで返す。アイテムが複数の isChildOf 親を持つ場合は、`sequence_number` が最小の association の親を選択する（NULL は非NULLの後に配置する。`sequence_number` が同じ場合は `destination_node_identifier` の辞書順で最初のもの。エクスポートの親選択ルールと同一） |

### CFDocument の場合

| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID |
| uri | 必須 | URL（リンク） |
| title | 必須 | テキスト |
| lastChangeDateTime | 必須 | ISO 8601 |
| creator | 任意（CASE v1.1 では必須だが DB は nullable） | テキスト |
| publisher | 任意 | テキスト |
| description | 任意 | テキスト |
| language | 任意 | 言語コード |
| version | 任意 | テキスト |
| adoptionStatus | 任意 | バッジ表示（Draft / Private Draft / Adopted / Deprecated） |
| statusStartDate | 任意 | 日付 |
| statusEndDate | 任意 | 日付 |
| licenseURI | 任意 | ネスト表示（title, identifier, uri）。CFItem と同一形式 |
| officialSourceURL | 任意 | URL（リンク） |
| frameworkType | 任意 | テキスト（v1.1 new。外部インポート由来で設定される場合がある） |
| caseVersion | 任意 | テキスト（v1.1 new。値は "1.1" のみ） |
| subject | 任意 | 配列をカンマ区切りで表示 |
| subjectURI | 任意 | 各要素のネスト表示（title, identifier, uri）。配列 |
| CFPackageURI | 必須 | ネスト表示（title, identifier, uri） |
| 「ツリーで表示」リンク | - | ツリービュートップへ遷移 |

### lookup リソースの場合（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）

uuid横断検索で lookup リソースに当たった場合、共通フィールド + 固有フィールドを表示する:

| フィールド | 表示形式 |
|-----------|---------|
| identifier | UUID |
| uri | URL（リンク） |
| title | テキスト |
| description | テキスト（値がある場合のみ） |
| リソース種別 | バッジ表示（例: "CFItemType", "CFSubject"） |
| 固有フィールド | typeCode, hierarchyCode, licenseText 等（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |

### CFRubric の場合

uuid横断検索で CFRubric に当たった場合、ルーブリックの詳細と Criteria/Levels を表形式で表示する:

| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID |
| uri | 必須 | URL（リンク） |
| CFDocumentURI | - | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| title | 任意 | テキスト |
| description | 任意 | テキスト |
| lastChangeDateTime | 必須 | ISO 8601 |
| CFRubricCriteria | 任意 | 表形式またはリスト形式（下記参照） |
| 「ツリーで表示」リンク | - | ツリービュートップへ遷移 |

**ルーブリック表形式表示:**
CFRubricCriteria を行、CFRubricCriterionLevel を列とするテーブルで表示する。

- **列**: 全 Criterion の Level から `position` のユニーク値を収集。列ヘッダーに `quality`（あれば）と `score`（あれば）を表示。position 昇順
- **行**: 各 Criterion（`position` 昇順 → `identifier` 昇順）。行ヘッダーに `category`, `description`, `weight`（あれば）, `CFItemURI`（あれば）を表示
- **セル**: 該当 Criterion × position の Level の `description`。`feedback` があれば追加表示
- **Criterion 間で Level 数が異なる場合**: 該当セルを空欄

**リスト形式フォールバック:** Level に `position` が全て null など、表形式に整列できない場合はリスト形式で表示（各 Criterion をカード、その中に Level をリスト）。

**表形式の判定条件:** Criterion が 1 件以上存在し、かつ少なくとも 1 件の Level に `position` が設定されている場合に表形式を使用。

### CFRubricCriterion の場合

uuid横断検索で CFRubricCriterion に当たった場合:

| フィールド | 表示形式 |
|-----------|---------|
| identifier | UUID |
| uri | URL（リンク） |
| category | テキスト（値がある場合のみ） |
| description | テキスト（値がある場合のみ） |
| CFItemURI | ネスト表示（値がある場合のみ） |
| weight | 数値（値がある場合のみ） |
| position | 数値（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |
| 所属ルーブリック | CFRubric の `/uri/` ページへのリンク |
| CFRubricCriterionLevels | 子 Level のリスト表示 |

### CFRubricCriterionLevel の場合

uuid横断検索で CFRubricCriterionLevel に当たった場合:

| フィールド | 表示形式 |
|-----------|---------|
| identifier | UUID |
| uri | URL（リンク） |
| description | テキスト（値がある場合のみ） |
| quality | テキスト（値がある場合のみ） |
| score | 数値（値がある場合のみ） |
| feedback | テキスト（値がある場合のみ） |
| position | 数値（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |
| 所属評価基準 | CFRubricCriterion の `/uri/` ページへのリンク |

### CFAssociation の場合

uuid横断検索で CFAssociation に当たった場合、最低限の情報を表示する:

| フィールド | 表示形式 |
|-----------|---------|
| identifier | UUID |
| uri | URL（リンク） |
| CFDocumentURI | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| associationType | テキスト（例: isChildOf） |
| originNodeURI | ネスト表示（title, identifier, uri, targetType）。targetType は値がある場合のみ表示 |
| destinationNodeURI | ネスト表示（title, identifier, uri, targetType）。targetType は値がある場合のみ表示 |
| sequenceNumber | 数値（値がある場合のみ） |
| CFAssociationGroupingURI | ネスト表示（title, identifier, uri）（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |

## バリデーション

Web UI パスでも CASE API と同様のバリデーションを行い、エラーページを表示する:
- `{tenant-uuid}` が UUID 形式でない → 400 エラーページ
- UUID 形式だがテナントが存在しない → 404 エラーページ
- **private テナントの直接アクセス:** `/{tenant-uuid}/` 以下のパスに直接アクセスした場合、テナントが private であっても通常通り表示する（アクセス制御は URL の秘匿性で実現する方針。architecture.md 参照）。GET / のテナント一覧のみ private テナントを非表示にする
- `{doc-uuid}` が UUID 形式でない → 400 エラーページ
- UUID 形式だがドキュメントが存在しない → 404 エラーページ
- `/uri/{uuid}` の `{uuid}` が UUID 形式でない → 400 エラーページ
- `/uri/{uuid}` でテナントスコープ内にリソースが見つからない → 404 エラーページ
- `/children/` および `/detail/` エンドポイントの `{tenant-uuid}` が UUID 形式でない → 400（「リクエストが不正です」テキストを含むHTMLフラグメント + ステータスコード400。フルエラーページではなくフラグメントを返す。HTMX スワップ対応）
- `/children/` および `/detail/` エンドポイントの `{tenant-uuid}` が UUID 形式だがテナントが存在しない → 404（「テナントが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404）
- `/children/` および `/detail/` エンドポイントの `{doc-uuid}` が UUID 形式でない → 400（「リクエストが不正です」テキストを含むHTMLフラグメント + ステータスコード400）
- `/children/` および `/detail/` エンドポイントの `{doc-uuid}` が UUID 形式だがドキュメントが存在しない → 404（「ドキュメントが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404）
- `/children/{item-uuid}` の `{item-uuid}` が UUID 形式でない → 400（空HTMLフラグメント + ステータスコード400）
- `/children/{item-uuid}` の `{item-uuid}` が UUID 形式だがアイテムが存在しない、または存在するが `{doc-uuid}` のドキュメントに属さない → 空のHTMLフラグメントを返す（200。子がないのと同じ扱い。association の `cf_document_id` スコープで自然にフィルタされる）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式でない → 400（空HTMLフラグメント + ステータスコード400）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式だがアイテムが存在しない → 404 エラーフラグメント
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式でアイテムが存在するが `{doc-uuid}` のドキュメントに属さない → 404 エラーフラグメント（別ドキュメントのアイテム詳細をツリービュー内で表示しない）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式だがアイテムが存在しない、または別ドキュメントに属する場合の 404 エラーフラグメント → 「アイテムが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404
- `/children/` および `/detail/` エンドポイントで 500 Internal Server Error が発生した場合 → 「サーバーエラーが発生しました」テキストを含むHTMLフラグメント + ステータスコード500 を返す
- **HTMX の非2xxレスポンス処理:** HTMX はデフォルトで非2xxレスポンスのコンテンツをスワップしない。400/404/500 のエラーフラグメントを右ペインに表示するため、`htmx:beforeSwap` イベントハンドラで `shouldSwap = true` を設定する（`base.html` に記述）

## エラーページ

Web UI のエラー表示。Tailwind CSS でスタイリングし、ユーザーフレンドリーに。

| HTTPステータス | 表示内容 |
|---------------|---------|
| 404 | 「ページが見つかりません」+ トップ（/）へのリンク |
| 400 | 「リクエストが不正です」+ エラー詳細 + トップへのリンク |
| 500 | 「サーバーエラーが発生しました」+ トップへのリンク |

テンプレート: `src/templates/error.html`（共通エラーテンプレート、ステータスコードとメッセージを受け取る）

## URI生成ルール

CASEリソースの `uri` フィールドは `/uri/{uuid}` を指す (OpenSALTと同じパターン):
`https://example.com/{tenant-uuid}/uri/{resource-uuid}`

- `config.py` に `BASE_URL` 設定を持つ（例: `https://case.example.com`）
- Docker環境のデフォルト: `http://localhost:8000`
- 環境変数 `BASE_URL` で上書き可能
- 新規作成時: `uri = f"{BASE_URL}/{tenant_id}/uri/{identifier}"`
- **外部インポート時**: 元の `uri` をそのまま DB に保持する（上書きしない）。
  外部URIのリソースを自サーバーの `/uri/{uuid}` でもアクセス可能にするため、
  `identifier` での検索を `/uri/{uuid}` ルーターが行う（DB の `uri` カラムとは別）
