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

## Response headers (Cache-Control)

**Standard pages** (`/`, `/{tenant}/`, `/cftree/doc/{doc}`, `/uri/{uuid}`): `Cache-Control: public, max-age=3600`.

**HTMX fragments** (`/cftree/doc/{doc}/detail/{item}`): `Cache-Control: public, max-age=86400`. Tree sub-content changes infrequently, so the TTL is long; CloudFront invalidation refreshes it on import.

**Error responses** (4xx / 5xx): no `Cache-Control` (same policy as CASE API).

## URL design

| Path | Description |
|------|-------------|
| GET / | Public tenant list. Tenant names (private tenants hidden). Sort: `display_order ASC NULLS LAST, name ASC, id ASC`. Each name links to `/{tenant-uuid}/`. If there are no public tenants, show "No public tenants". |
| GET /{tenant-uuid}/ | Framework list: CFDocument title, lastChangeDateTime, item count (`SELECT COUNT(*) FROM cf_item WHERE cf_document_id = doc.id`), and rubric count (`COUNT` of CFRubrics for the document). Sort: `display_order ASC NULLS LAST, title ASC, identifier ASC`. Each title links to `/{tenant-uuid}/cftree/doc/{doc-uuid}`. If no documents, show "No frameworks". |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid} | Tree view. **Lazy tree** — initial SSR of depth 0-1 with native `<details>`; deeper levels load on expand via the `/children/` route. `?item={uuid}` (back-compat) SSRs the ancestor path to that item + its detail in the right pane. |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/children/{parent-uuid} | HTML fragment of one level of a parent item's children (lazy tree expand). Same `tree_nodes.html` markup as the initial SSR. |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/item/{item-uuid} | Same tree view with an item selected via the **URL path** — the canonical, shareable, reload-safe form that in-tree navigation pushes (`hx-push-url`). Opening/reloading/sharing reconstructs the tree (the ancestor path expanded to the item) + the item's full detail via SSR. |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/detail/{item-uuid} | HTML fragment of an item's detail (for the HTMX right pane). |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/document | HTML fragment of the document's own detail (right pane). Separate from `/detail/{item}` to avoid identifier collisions. |
| GET /{tenant-uuid}/uri/{uuid} | Resource detail page (HTML by default; **303 See Other** to the matching CASE API endpoint when the `Accept` header signals a JSON client — see [api-spec.md](api-spec.md#tenanturiuuid-content-negotiation)). |

**Manual list ordering (`display_order`)**: both lists honor an optional `display_order` integer (on `tenants` / `cf_documents`) so an operator can pin/arrange entries without renaming. Smaller = higher; `NULL` (the default) sinks below all explicitly-ordered entries and then sorts alphabetically. It's a compeito-local display field — not a CASE field, never emitted in CASE export, and preserved on re-import. Set it via `cli.py tenant update --display-order N` / `--clear-order` and `cli.py doc update --display-order N` / `--clear-order` (see [cli.md](cli.md)).

## Tree view (`/cftree/doc/{doc-uuid}`)

A two-pane layout inspired by OpenSALT's tree view. Visually, use a modern Tailwind CSS default (do not copy OpenSALT's look).

**HTML `<title>`** per page:
- `GET /`: "COMPEITO" (fixed).
- `GET /{tenant}/`: "{tenant name} - COMPEITO".
- `GET /{tenant}/cftree/doc/{doc}`: "{document title} - {tenant name} - COMPEITO".
- `GET /{tenant}/uri/{uuid}`: depends on the resource type. CFItem → "{first 50 chars of fullStatement} - COMPEITO". CFDocument → "{title} - COMPEITO". Lookup / CFAssociation → "{title or identifier} - COMPEITO".
- Error pages: "{status code} - COMPEITO".

**HTML `<html lang>`**: `base.html` sets `lang` from the request language (`{{ lang|default('en') }}`), which is negotiated from the `Accept-Language` header (default `en`; see `i18n.parse_accept_language`). The UI itself is bilingual (en/ja). Note: this is the *UI chrome* language; the content language of a resource is expressed separately by the resource's own `language` field and does not drive `<html lang>`.

**Navigation:** every page shows a breadcrumb in the header:
- `GET /`: no breadcrumb (top page).
- `GET /{tenant}/`: "[Tenants](/)".
- `GET /{tenant}/cftree/doc/{doc}`: "[Tenants](/) > [Tenant name](/{tenant}/) > Document title" (the last segment is the current page, no link).
- `GET /{tenant}/uri/{uuid}`: depends on the resource. For CFItem / CFAssociation / CFRubric the owning document is resolved, so a third segment links to it: "[Tenants](/) > [Tenant name](/{tenant}/) > [Document title](/{tenant}/cftree/doc/{doc})". CFDocument and lookups (no owning document) show the two-segment breadcrumb. The page body also shows the document via `CFDocumentURI`.

```
┌─────────────────────────────────────────────────────┐
│ Header: CFDocument title + adoptionStatus badge     │
├──────────────────────┬──────────────────────────────┤
│ Left pane (tree)     │ Right pane (detail)          │
│                      │                              │
│ ▼ Japanese           │ [CFItem] [code chip]         │
│   ▼ Modern Japanese  │ fullStatement (heading)      │
│     【Knowledge & ..│ [⧉ID] [⧉Permalink] [⧉API]  │
│     ● Items on the …│ Classification (item type …) │
│     ● Words have …  │ Relations (document, related)│
│   ▶ Language Culture │ ──────────────────────────  │
│ ▶ Geography & Hist.  │ Technical details (muted:    │
│ ▶ Civics             │  identifier, license, dates) │
└──────────────────────┴──────────────────────────────┘
```

- **Left pane**: tree structure. Native `<details>` expand/collapse (▶/▼, no JS). Each item label is a real `<a href>` to its path-form item URL (`/cftree/doc/{doc}/item/{item}`); HTMX layers on top to swap the right pane and **push that URL** (`hx-push-url`), so the address bar syncs and the view is shareable / reload-safe / back-button-safe. Without JS, the link is a plain navigation to the same SSR page. Display text is `fullStatement` (truncated to 100 chars); `humanCodingScheme` shown before it when present; `CFItemType` as a small badge.
  - **Definitions section**: below the competency items, a collapsed-by-default `<details>` "Definitions" lists the lookups **referenced by this document** (same scope as the CFPackage `CFDefinitions`), grouped by type (Item Types / Concepts / Subjects / Licenses / Association Groupings; non-empty groups only, sorted by title). Each entry is a navigable node (same path-form URL + pane swap + `selectTreeNode` as items), so e.g. a license is reachable and shown in the pane. Built by `cf_view_service.list_document_definitions`.
  - **Rubrics section**: below Definitions, a collapsed-by-default `<details>` "Rubrics" nests `CFRubric → CFRubricCriterion → CFRubricCriterionLevel` (non-empty only; criteria/levels ordered by `position, identifier`). Each is a navigable tree node like items/definitions. Criterion labels show `category` plus the description to disambiguate siblings that share a category.
  - **Loading a tree node by URL** (`/item/{id}`) auto-scrolls the selected node into view and auto-expands its ancestor `<details>` (incl. the Definitions/Rubrics section and the rubric/criterion path). A resource that is **not** a node in this document's tree — a lookup outside the doc's definitions, or a rubric part of another doc — returns **404** on both the `/item/{id}` page and the `/detail/{id}` fragment (the "pane content ⟺ tree node" invariant). `/uri/{id}` stays the unrestricted permalink for any resource.
- **Right pane**: shows the selected item's detail, swapped in via HTMX `hx-get` (`GET /{tenant}/cftree/doc/{doc-uuid}/detail/{item-uuid}`). The redundant "Show in tree" link is **hidden in the pane** (`in_pane`) — it only appears on the standalone `/uri/` page.
  - **In-pane navigation**: a "Related" link whose target is a **CFItem in the same document** navigates within the tree — it swaps the pane (`hx-get` detail), pushes the path-form URL, and calls `selectTreeNode(id)` (JS) to open the target's ancestor `<details>`, highlight it, and scroll it into view. Same-document membership and ordering are computed server-side: `tree_service.dfs_index` maps each item to its position in the tree's depth-first display order, and `sort_related_by_tree_order` orders each related group by that index. This reproduces the **exact tree display order** (full root→node path, not just the item's own sibling key), so the "Related" list reads in the same order as the tree.
  - **Cross-references are classified and routed** (the same buckets apply to related items, definition references, rubric ↔ item links, and a CFAssociation's origin/destination nodes — via the `def_nav` / `nav_button` / `classified_ref` macros and `_detail_extras`):
    - **same document** → in-pane navigation (as above).
    - **same tenant, another framework** → link to that document's tree (`/cftree/doc/{other-doc}/item/{id}`, a full tree switch) with an "Other framework" badge. Resolved server-side via `cf_item_repository.map_identifiers_to_documents` (`related_other_doc` / `assoc_node_*`).
    - **another tenant on this instance, public** → the relation is **owned by the declaring tenant**, but if a `*NodeURI` points at a CFItem in a *public* other tenant on this same compeito instance (a `{base_url}/{tenant}/uri/{item}` permalink — see `uri_service.parse_internal_tenant_id`), it is resolved to the target's title and linked to **that tenant's tree** (`/{other-tenant}/cftree/doc/{other-doc}/item/{id}`) with an "Other institution" badge (`related_other_institution`). Resolved server-side via `web._resolve_cross_tenant` → `tenant_service.get_tenant` (visibility check) + `cf_item_repository.map_identifiers_to_items` (`related_other_tenant` / `assoc_node_*` carry a `tenant_segment`).
    - **another tenant on this instance, private** → **fully hidden**: a private (or nonexistent) target tenant's endpoint is dropped entirely (no title, no URI, no link, no badge) — its existence is never surfaced.
    - **external / unresolvable** → link out to the stored URI in a new tab (`target=_blank`) with an "External" badge, **http(s) only** — other schemes (`javascript:` / `data:`) render as plain text. Internal `{base_url}` URIs that did not resolve to a public item are *not* linkified here (they fall into the private/hidden case above).
  - **Incoming references ("Referenced by other institutions" / 参照元（他機関）)**: the reverse direction of the public cross-tenant case above. A CFItem's pane lists CFAssociations *owned by other tenants* that point **at this item** as their destination — i.e. who on this instance has adopted/linked to this item. Resolved server-side by `web._incoming_refs`: it builds this item's permalink (`{base_url}/{tenant}/uri/{identifier}`), looks up incoming associations tenant-wide via `cf_association_repository.list_incoming_by_destination_uri` (excludes `isChildOf`), drops references from the current tenant, and — like the outgoing case — is **public-only**: associations owned by **private** tenants are excluded *before* resolution, so a private adopter is never surfaced (neither forward nor in reverse). Each entry shows the origin item's title with an "Other institution ↩" badge (`incoming_refs` / `related_other_institution_in`, `incoming_refs_label`) linking to that tenant's tree.
  - In-pane "back to the linked item" / parent links use **path-neutral labels** (`view_linked_item` "View linked item", `go_to_top_page`) so they read correctly however the node was reached.
  - **Cross-document hierarchy (上位/下位 別FW)**: a CFItem's pane shows "Parent (other framework)" / "Child (other framework)" sections when its `isChildOf` parents/children live in **another framework** (a large framework split across documents). The tree stays per-document; only the boundary neighbors surface here, each a tree-switch link (or external link-out). Same-document hierarchy is omitted (it's already in the tree). Resolved server-side from tenant-wide `isChildOf` (`cf_association_repository.list_ischildof_parents` / `_children` + `cf_item_repository.map_identifiers_to_items`, `_cross_doc_hierarchy`). isChildOf direction: origin=child, destination=parent. The same cross-tenant routing applies: a parent/child in a **public other tenant** links to that tenant's tree with the "Other institution" badge; one in a **private** other tenant is dropped (not shown).
  - **Right pane = full detail.** The pane renders the **same full-detail card as the standalone `/uri/{uuid}` page** (shared partial `fragments/resource_detail.html`), so every field — including the permalink, API URLs, effective license, and the grouped "Related" associations — is visible without leaving the tree. The right-pane fragment endpoint and the deep-link `?item=` SSR both produce this full card. (The previous lightweight summary + "Detail" link round-trip is replaced.)
  - **Initial state** (no item selected): the right pane shows the **document's own full detail** via the shared partial (same card as `/uri/{doc-uuid}`, including the rubrics list). The left-pane **document name is a self-link** that re-selects the document into the pane (HTMX swap of `#detail-pane` via the dedicated `/cftree/doc/{doc}/document` fragment + `hx-push-url` to the tree root `/cftree/doc/{doc}`); it's highlighted when nothing else is selected. (The former separate "Document details" link is removed — the name link + pane cover it.) If the document has 0 items, show "No items" in the left pane. The document fragment is a **separate route** from `/detail/{item-uuid}` so it never collides with a CFItem that happens to share the document's identifier (identifier collisions are allowed; `/uri/` resolves item-before-document).
  - On access with `?item={item-uuid}`, the target item is shown as selected, with its detail rendered inline via SSR (no extra HTMX fetch). If the value isn't a UUID, doesn't exist, or belongs to a different document, the parameter is ignored and the initial state is shown.
- **Responsive**: on mobile the layout stacks (tree on top, detail pane below) so all info is reachable without leaving the page. HTMX runs in both layouts — tapping an item swaps `#detail-pane` content and, on mobile (`window.innerWidth < 768`), smooth-scrolls to the detail pane. The item links' `<a href>` (path-form item URL) fallback is preserved for non-JS clients and middle-click / ⌘-click navigation. Above the tree, the CFDocument's title is shown as a self-link (selects the document into the pane) so document info is reachable on mobile.

### Level detection and initial expansion

`cf_item.depth` is stored in the column (computed at import time by recursively following `isChildOf`).
**The tree loads lazily** (`tree_service.build_ssr_tree`): the initial page server-renders only **depth 0-1** (root nodes + their immediate children), nested in `<details>/<summary>`. Deeper branches render as a collapsed `<details>` whose child container has an `hx-get` to `GET /{tenant}/cftree/doc/{doc}/children/{parent}` with `hx-trigger="toggle … once"` — so **one level of children is fetched on first expand** (returns the same `tree_nodes.html` markup, so expansion is uniform at any depth). This keeps the initial page small for large frameworks (and within the Lambda/API Gateway response-size limits on a serverless deployment). Each level is one bulk fetch (`get_children`); a per-path visited set guards cyclic `isChildOf`.
**Item sort order**: `sequence_number` ASC → `human_coding_scheme` natural sort → `identifier` lexicographic (NULL last). Multi-parent items appear under each parent.
**Initial expand state**: top-level (depth 0) nodes render expanded (`<details open>`, ▶ rotated to point down) showing depth 1; deeper nodes render collapsed (lazy); leaves show a `●`.
**`?item={item-uuid}` / `/item/{id}`**: the **ancestor path from the root to that item is SSR'd expanded** (so the item is visible in context on a direct load / reload / share, even though the rest of the tree is lazy) and the item's full detail is SSR'd into the right pane. The expand path walks `isChildOf` ancestors within the same document. Multi-parent items follow the same parent-selection rule as the "Show in tree" link on `/uri/` (smallest `sequence_number`, NULL after non-NULL → `destination_node_identifier` lexicographic). A small load-time `scrollIntoView` brings the selected node into view.
**No-JS / crawlers**: interactive in-place expansion needs JS, but every node label is a real `<a href>` to its `/item/{id}` page, and each `/item/{id}` SSRs the tree expanded to that item — so all content stays reachable (and crawlable) without JS, and middle-click / new-tab work.
**Accessibility**: native `<details>/<summary>` provides keyboard operation and screen-reader expand/collapse announcement; decorative ▶/● icons are `aria-hidden`; the selected node carries `aria-current="true"`; the lazy child container is `aria-busy` while loading (with a `role="status"` "Loading…" placeholder); summaries/links have a visible `:focus-visible` ring. (This is enhanced native semantics, not a formal `role="tree"` widget.)

### Orphan items

Items without any `isChildOf` association (e.g., when associations were skipped during external CASE source import) are appended at the end of the root level: depth=0 items that are **not** an origin of any `isChildOf` within the **same document** (items that only appear as origins of `isChildOf` in other documents are also treated as orphans here). Sort order as above, with `sequence_number` treated as NULL.


**Orphan items**: items without any `isChildOf` association (e.g., when associations were skipped during external CASE source import) are not returned via the children query. They are appended at the end of the root level: depth=0 items that are **not** an origin of any `isChildOf` within the **same document** (items that only appear as origins of `isChildOf` in other documents are also treated as orphans in the current document). The sort order is the same as above, with `sequence_number` always treated as NULL.

**Expand icons (▶/▼)**: a node has children when it is a `destination_node_identifier` of some `isChildOf` in the same document. Nodes with children render as `<details>` with a ▶ triangle (rotated to point down when open); leaves render a `●`. `get_children` / `build_ssr_tree` determine `has_children` per level from a bulk association fetch (no N+1).

> Note: `origin isChildOf destination` reads as "origin is a child of destination". To find children, search on the destination side.

Including `{doc-uuid}` in the children path lets CloudFront invalidate `/{tenant}/cftree/doc/{doc-uuid}*` in one go.

## `/uri/{uuid}` detail page

A public page linked from external systems such as Open Badge Factory. Use OpenSALT's `/uri/{uuid}` page as a reference, with a modern Tailwind CSS default look.
Hide fields with no value (omit the whole row). "No value" means `null`, an empty string `""`, or an empty array `[]`. JSONB array fields (`educationLevel`, `conceptKeywords`, `subject`, etc.) are also hidden for `null` or `[]`.

**Content negotiation:** the same URL doubles as the JSON identifier for CASE clients. When the request's `Accept` header signals a JSON consumer (contains `application/json` or `application/ld+json` AND does not contain `text/html`), the handler responds with **303 See Other** pointing to the matching CASE API endpoint (e.g., CFItem → `/{tenant}/ims/case/v1p1/CFItems/{uuid}`). Otherwise the HTML page below is served. Resource types without an individual CASE API endpoint (CFRubricCriterion / CFRubricCriterionLevel) always serve HTML. See [api-spec.md](api-spec.md#tenanturiuuid-content-negotiation) for details.

**Security:** URL fields (`uri`, `officialSourceURL`, the `uri` field in LinkURIDType, etc.) are rendered as clickable links **only** when the scheme is `http:` / `https:`. Other schemes (e.g., `javascript:`, `data:`) are rendered as plain text (to prevent XSS). All text fields are HTML-escaped via Jinja2 autoescaping.

**`extensions` display (all resource types):** `extensions` is a free-form JSONB payload where different frameworks store their own data, so it is rendered by recursively dispatching on the JSON value type:
- object → key/value block (nested objects are indented)
- array of scalars → chips/badges
- array of objects → stacked blocks
- string that is an `http:` / `https:` URL → clickable link (same scheme rule as above; other strings are plain text)
- other scalar (number, boolean, etc.) → text

The section is omitted entirely when `extensions` is `null` or empty. CFDocument additionally shows the container-level `package_extensions` (`CFPackage.extensions`) and `definitions_extensions` (`CFDefinitions.extensions`) as separate sections. The same `extensions` section appears on every resource type's detail page below.

### Detail card layout (zones)

Both the `/uri/{uuid}` page and the tree right pane render the shared detail card (`fragments/resource_detail.html`) with a user-first information hierarchy, top to bottom:

1. **Header** — resource-type badge (plus CFDocument's adoptionStatus badge / CFItem's humanCodingScheme code chip / CFAssociation's associationType chip / CFRubricCriterionLevel's score chip), the resource **name as the card heading (`h2`)**, and a **copy-chip cluster** (Identifier and Permalink for every type; CFItem / CFDocument additionally get their CASE API URL) so integration URLs stay copyable without scrolling. The heading per type: CFItem → fullStatement, CFDocument / CFRubric / lookups → title, CFRubricCriterion → category, CFRubricCriterionLevel → quality, CFAssociation → an "origin → destination" summary; the identifier is the fallback when the name is absent. The name shown in the heading is **not repeated** as a labeled row.
2. **Content** — description / notes / abbreviatedStatement etc., directly under the header (no section title). CFRubric's criteria table/list also renders here, right after the description.
3. **Classification** ("Classification" / 「分類」) — educational metadata: item type, education level, concept keywords, subject, language, creator/publisher/version (CFDocument), …
4. **Relations** ("Relations" / 「関連情報」) — owning document, cross-document hierarchy, related items, rubrics, parent rubric / criterion, linked item.
5. **Technical details** ("Technical Details" / 「技術情報」) — identifier, uri, effective license, status dates, lastChangeDateTime, extensions. CFItem / CFDocument additionally repeat the permalink and their CASE API URL here as full copyable strings (for the other types the permalink is available from the header chip only). Rendered as a visually muted, **always-open** section at the bottom (not a collapsible — it must stay visible for OBF/QTI integration and printing).

Zones 3–5 render with a top separator and a small uppercase section title, and each zone is omitted entirely when it has no content. Short scalar fields inside a zone may be arranged in a 2-column grid. The standalone `/uri/` page's own `<h1>` shows only `page_title`; the type / adoptionStatus badges live in the card header.

The field tables below define each field's presence rule and rendering; the zone placement follows the mapping above.

### CFItem

| Field | Required/Optional | Display |
|-------|-------------------|---------|
| identifier | required | UUID (technical section + header copy chip) |
| uri | required | URL (link) |
| CFDocumentURI | required | Nested display (title, identifier, uri); title links to the tree view |
| fullStatement | required | Card heading (`h2`) — not repeated as a labeled row |
| lastChangeDateTime | required | ISO 8601 |
| humanCodingScheme | optional | Code chip in the header badge row |
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
| extensions | optional | Free-form (see "extensions display" above) |
| "Show in tree" link | — | Navigates to `/{tenant}/cftree/doc/{doc-uuid}?item={item-uuid}`. The server computes the expand path from root to this item and SSR-renders the tree expanded through that node. When the item has multiple `isChildOf` parents, the association with the smallest `sequence_number` wins (NULL after non-NULL; tie-broken by `destination_node_identifier` lexicographic — same parent-selection rule as export). |

### CFDocument

| Field | Required/Optional | Display |
|-------|-------------------|---------|
| identifier | required | UUID (technical section + header copy chip) |
| uri | required | URL (link) |
| title | required | Card heading (`h2`) |
| lastChangeDateTime | required | ISO 8601 |
| creator | optional (required in CASE v1.1 but DB is nullable) | Text |
| publisher | optional | Text |
| description | optional | Text |
| language | optional | Language code |
| version | optional | Text |
| adoptionStatus | optional | Badge in the card header (Draft / Private Draft / Adopted / Deprecated) |
| statusStartDate | optional | Date |
| statusEndDate | optional | Date |
| licenseURI | optional | Nested (title, identifier, uri); same as CFItem |
| officialSourceURL | optional | URL (link) |
| frameworkType | optional | Text (v1.1 new; may be set via external import) |
| caseVersion | optional | Text (v1.1 new; valid value is "1.1") |
| subject | optional | Array shown comma-separated |
| subjectURI | optional | Each element nested (title, identifier, uri); array |
| CFPackageURI | required | Nested (title, identifier, uri) |
| extensions | optional | Free-form (see "extensions display" above) |
| package_extensions / definitions_extensions | optional | Container-level extensions, each its own section |
| "Show in tree" link | — | Navigates to the tree view's root |

### Lookup resources (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping)

When `/uri/{uuid}` resolves to a lookup, show common + specific fields:

| Field | Display |
|-------|---------|
| identifier | UUID (technical section + header copy chip) |
| uri | URL (link) |
| title | Card heading (`h2`) |
| description | Text (only when present) |
| Resource type | Badge in the card header (e.g., "CFItemType", "CFSubject") |
| Specific fields | typeCode, hierarchyCode, licenseText, etc. (only when present) |
| lastChangeDateTime | ISO 8601 |

### CFRubric

When `/uri/{uuid}` resolves to a CFRubric, show the rubric detail along with Criteria/Levels in a table:

| Field | Required/Optional | Display |
|-------|-------------------|---------|
| identifier | required | UUID (technical section + header copy chip) |
| uri | required | URL (link) |
| CFDocumentURI | — | Nested (title, identifier, uri); title links to the tree view |
| title | optional | Card heading (`h2`; identifier when absent) |
| description | optional | Text |
| lastChangeDateTime | required | ISO 8601 |
| CFRubricCriteria | optional | Table or list (see below), right after the description |
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
| identifier | UUID (technical section + header copy chip) |
| uri | URL (link) |
| category | Card heading (`h2`; identifier when absent) |
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
| identifier | UUID (technical section + header copy chip) |
| uri | URL (link) |
| description | Text (only when present) |
| quality | Card heading (`h2`; identifier when absent) |
| score | Number (only when present); also a chip in the card header |
| feedback | Text (only when present) |
| position | Number (only when present) |
| lastChangeDateTime | ISO 8601 |
| Owning criterion | Link to the CFRubricCriterion `/uri/` page |

### CFAssociation

When `/uri/{uuid}` resolves to a CFAssociation, show the minimal fields. The card heading summarizes the relation as "origin → destination" (node titles, falling back to node identifiers):

| Field | Display |
|-------|---------|
| identifier | UUID (technical section + header copy chip) |
| uri | URL (link) |
| CFDocumentURI | Nested (title, identifier, uri); title links to the tree view |
| associationType | Text (e.g., isChildOf); also a chip in the card header |
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
- `/detail/` / `/document` endpoints: `{tenant-uuid}` is not a UUID → 400 (HTML fragment "リクエストが不正です" + status 400; not the full error page — return a fragment for HTMX swap).
- `/detail/` / `/document` endpoints: valid UUID but tenant doesn't exist → 404 (HTML fragment "テナントが見つかりません" + status 404).
- `/detail/` / `/document` endpoints: `{doc-uuid}` is not a UUID → 400 (HTML fragment "リクエストが不正です" + status 400).
- `/detail/` / `/document` endpoints: valid UUID but document doesn't exist → 404 (HTML fragment "ドキュメントが見つかりません" + status 404).
- `/detail/{item-uuid}` with non-UUID `{item-uuid}` → 400 (empty HTML fragment + status 400).
- `/detail/{item-uuid}` with valid UUID but the item doesn't exist → 404 error fragment.
- `/detail/{item-uuid}` with valid UUID and item exists but belongs to a different document → 404 error fragment (do not show another document's item inside this tree view).
- The 404 error fragment for `/detail/` is an HTML fragment "アイテムが見つかりません" with status 404.
- 500 Internal Server Error on `/detail/` / `/document` → HTML fragment "サーバーエラーが発生しました" + status 500.
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

## レスポンスヘッダー（Cache-Control）

**通常ページ**（`/`, `/{tenant}/`, `/cftree/doc/{doc}`, `/uri/{uuid}`）: `Cache-Control: public, max-age=3600`

**HTMX フラグメント**（`/cftree/doc/{doc}/detail/{item}`, `/cftree/doc/{doc}/document`）: `Cache-Control: public, max-age=86400`（ツリーの部分コンテンツは変更頻度が低いため長めに設定。インポート時に CloudFront invalidation で即時更新）

**エラーレスポンス**（4xx/5xx）: `Cache-Control` を設定しない（CASE API と同一方針）。

## URLパス設計

| Path | 説明 |
|------|------|
| GET / | 公開テナント一覧: テナント名の一覧（privateは非表示）。`display_order ASC NULLS LAST, name ASC, id ASC` でソート。各テナント名は `/{tenant-uuid}/` へのリンク。公開テナントが0件の場合は「公開テナントはありません」を表示 |
| GET /{tenant-uuid}/ | フレームワーク一覧: CFDocumentのtitle, lastChangeDateTime, アイテム数（`SELECT COUNT(*) FROM cf_item WHERE cf_document_id = doc.id`）, ルーブリック数（そのドキュメントの CFRubrics の `COUNT`）。`display_order ASC NULLS LAST, title ASC, identifier ASC` でソート。各ドキュメントのタイトルは `/{tenant-uuid}/cftree/doc/{doc-uuid}` へのリンク。ドキュメントが0件の場合は「フレームワークはありません」を表示 |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid} | ツリービュー。**遅延ツリー** — 初期は深さ0-1 をネイティブ `<details>` で SSR、深い階層は展開時に `/children/` で取得。`?item={uuid}`（後方互換）で当該アイテムまでの祖先パスと右ペイン詳細を SSR |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/children/{parent-uuid} | 親アイテムの子1階層の HTML フラグメント（遅延ツリーの展開用）。初期 SSR と同じ `tree_nodes.html` マークアップ |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/item/{item-uuid} | アイテムを **URL パス**で選択したツリービュー。ツリー内ナビが push する正規・共有可能・リロード安全な形式（`hx-push-url`）。直接開く/リロード/共有でツリー（当該アイテムまでの祖先パスを展開）＋フル詳細を SSR 再構築 |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/detail/{item-uuid} | アイテム詳細HTMLフラグメント (HTMX右ペイン用) |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/document | ドキュメント自身の詳細HTMLフラグメント（右ペイン）。identifier 衝突回避のため `/detail/{item}` と別ルート |
| GET /{tenant-uuid}/uri/{uuid} | リソース詳細ページ（デフォルトは HTML。`Accept` が JSON クライアントを示す場合は該当 CASE API エンドポイントへ **303 See Other**。詳細は [api-spec.md](api-spec.md#tenanturiuuid-のコンテントネゴシエーション) を参照） |

## ツリービュー (`/cftree/doc/{doc-uuid}`)

OpenSALT のツリービューを参考にした 2 ペイン構成。見た目は Tailwind CSS のデフォルトスタイルでモダンに仕上げる（OpenSALT の見た目をコピーしない）。

**HTML `<title>` 要素:** ページごとに設定する:
- `GET /`: 「COMPEITO」（固定）
- `GET /{tenant}/`: 「{テナント名} - COMPEITO」
- `GET /{tenant}/cftree/doc/{doc}`: 「{ドキュメントタイトル} - {テナント名} - COMPEITO」
- `GET /{tenant}/uri/{uuid}`: リソース種別による。CFItem → 「{fullStatement の先頭50文字} - COMPEITO」。CFDocument → 「{title} - COMPEITO」。lookup/CFAssociation → 「{title or identifier} - COMPEITO」
- エラーページ: 「{ステータスコード} - COMPEITO」

**HTML `<html lang>` 属性:** `base.html` はリクエスト言語（`{{ lang|default('en') }}`）から `lang` を設定する。言語は `Accept-Language` ヘッダーから決定（既定は `en`。`i18n.parse_accept_language` 参照）。UI は en/ja のバイリンガル。これは*UI の言語*であり、リソースのコンテンツ言語は別途リソース自身の `language` フィールドで表現され、`<html lang>` には影響しない。

**ナビゲーション:** 全ページ共通でパンくずリンクをヘッダーに表示する:
- `GET /`: パンくずなし（トップページ自体）
- `GET /{tenant}/`: 「[テナント一覧](/)」
- `GET /{tenant}/cftree/doc/{doc}`: 「[テナント一覧](/) > [テナント名](/{tenant}/) > ドキュメントタイトル」（最後の要素は現在のページなのでリンクなし）
- `GET /{tenant}/uri/{uuid}`: リソース種別による。CFItem・CFAssociation・CFRubric は所属ドキュメントが解決されるので3段目にそのリンクを出す → 「[テナント一覧](/) > [テナント名](/{tenant}/) > [ドキュメントタイトル](/{tenant}/cftree/doc/{doc})」。CFDocument・lookup リソース（所属ドキュメントなし）は2段「[テナント一覧](/) > [テナント名](/{tenant}/)」。ページ本文にも CFDocumentURI でドキュメントを表示。

```
┌─────────────────────────────────────────────────────┐
│ ヘッダー: CFDocument title + adoptionStatus バッジ    │
├──────────────────────┬──────────────────────────────┤
│ 左ペイン（ツリー）     │ 右ペイン（詳細）              │
│                      │                              │
│ ▼ 国語               │ [CFItem] [コードチップ]       │
│   ▼ 現代の国語        │ fullStatement（見出し）       │
│     【知識及び技能】   │ [⧉ID] [⧉Permalink] [⧉API]  │
│     ● 言葉の特徴や... │ 分類（アイテム種別・教科 …）  │
│     ● 言葉には...     │ 関連情報（ドキュメント・関連）│
│   ▶ 言語文化          │ ──────────────────────────  │
│ ▶ 地理歴史            │ 技術情報（薄色: 識別子・      │
│ ▶ 公民                │  ライセンス・更新日時）       │
└──────────────────────┴──────────────────────────────┘
```

- **左ペイン**: ツリー構造。ネイティブ `<details>` で展開/折りたたみ（▶/▼、JS不要）。各アイテムのラベルはパス形式の item URL（`/cftree/doc/{doc}/item/{item}`）への実 `<a href>`。HTMX がその上に乗り、右ペインを差し替えつつ **その URL を push**（`hx-push-url`）するので、アドレスバーが同期し共有/リロード/戻るに対応。JS なしではそのまま同じ SSR ページへ素の遷移。表示テキストは `fullStatement`（先頭100文字）。`humanCodingScheme` が非NULLなら前置、`CFItemType` は小バッジ。
  - **定義セクション**: コンピテンシー項目の下に、既定で畳んだ `<details>`「定義」を置き、**このドキュメントが参照する** lookup（CFPackage の `CFDefinitions` と同スコープ）を型別（アイテムタイプ / コンセプト / 教科 / ライセンス / アソシエーショングルーピング。非空のみ・title 順）に列挙する。各エントリは項目と同じくナビ可能ノード（パス形式 URL ＋ ペイン差し替え ＋ `selectTreeNode`）なので、例えばライセンスにも辿れてペインに表示される。`cf_view_service.list_document_definitions` が構築。
  - **ルーブリックセクション**: 定義の下に既定で畳んだ `<details>`「ルーブリック」を置き、`CFRubric → CFRubricCriterion → CFRubricCriterionLevel` をネスト（非空のみ・criteria/levels は `position, identifier` 順）。各ノードは項目/定義と同じくナビ可能。評価基準のラベルは sibling 区別のため `category` に description を併記。
  - **ツリーノードを URL で直接ロード**（`/item/{id}`）すると、選択ノードを自動スクロールして表示し祖先 `<details>`（定義/ルーブリック節やルーブリック→基準の経路を含む）を自動展開する。このドキュメントのツリーノードでないリソース（doc が参照しない lookup、別 doc のルーブリック部）は `/item/{id}` ページ・`/detail/{id}` フラグメントとも **404**（「ペイン内容 ⟺ ツリーノード」不変条件）。`/uri/{id}` は任意リソースの permalink として制限なし。
- **右ペイン**: 選択アイテムの詳細を HTMX `hx-get`（`GET /{tenant}/cftree/doc/{doc-uuid}/detail/{item-uuid}`）で差し替え表示。冗長な「ツリーで表示」リンクは**ペインでは非表示**（`in_pane`）— 単独 `/uri/` ページでのみ出す。
  - **ペイン内ナビ**: 「関連」リンクの遷移先が**同一ドキュメント内の CFItem** の場合、ツリー内で完結する — ペインを差し替え（`hx-get` detail）、パス形式 URL を push、`selectTreeNode(id)`（JS）で対象の祖先 `<details>` を開いてハイライト＋スクロール。同一ドキュメント判定と並び順はサーバー側で計算する。`tree_service.dfs_index` が各 item をツリーの深さ優先表示順の位置にマップし、`sort_related_by_tree_order` が各関連グループをその位置順に並べる。これで**ツリーの実表示順（item 自身の sibling キーでなくルート→ノードのフルパス順）**が再現され、「関連」リストはツリーと同じ順序で読める。
  - **相互参照の出し分け**（関連アイテム・定義参照・ルーブリック⇄アイテム・CFAssociation の origin/destination ノードに共通適用。`def_nav` / `nav_button` / `classified_ref` マクロと `_detail_extras`）:
    - **同一ドキュメント** → ペイン内ナビ（上記）。
    - **同一テナントの別フレームワーク** → そのドキュメントのツリーへ（`/cftree/doc/{別doc}/item/{id}`、ツリーごと切替）＋「別フレームワーク」バッジ。`cf_item_repository.map_identifiers_to_documents` でサーバー側解決（`related_other_doc` / `assoc_node_*`）。
    - **同一インスタンスの別テナント（public）** → 関連は**宣言した側のテナントが所有**するが、`*NodeURI` が同一 compeito インスタンス上の*公開*別テナントの CFItem（`{base_url}/{tenant}/uri/{item}` 形式の permalink。`uri_service.parse_internal_tenant_id` で判定）を指す場合は、相手の title を解決し**相手テナントのツリー**へリンク（`/{別テナント}/cftree/doc/{別doc}/item/{id}`）＋「他機関」バッジ（`related_other_institution`）。`web._resolve_cross_tenant` → `tenant_service.get_tenant`（可視性チェック）＋ `cf_item_repository.map_identifiers_to_items` でサーバー側解決（`related_other_tenant` / `assoc_node_*` が `tenant_segment` を持つ）。
    - **同一インスタンスの別テナント（private）** → **完全非表示**: private（または存在しない）テナントを指す端点は丸ごと除外（title・URI・リンク・バッジ いずれも出さない）。存在自体を一切出さない。
    - **外部 / 解決不能** → 保存済み URI を別タブ（`target=_blank`）＋「外部」バッジ。**http(s) のみ**リンク化し、それ以外（`javascript:` / `data:`）はプレーンテキスト。public 項目に解決できなかった `{base_url}` 内部 URI はここでリンク化せず、上記の private/非表示扱いになる。
  - **参照元（他機関）**: 上記 public クロステナントの逆方向。CFItem のペインに、**他テナントが所有する** CFAssociation のうち**この項目を destination として指している**ものを一覧する（＝このインスタンス上で誰がこの項目を採用/参照しているか）。`web._incoming_refs` でサーバー側解決: この項目の permalink（`{base_url}/{tenant}/uri/{identifier}`）を組み立て、`cf_association_repository.list_incoming_by_destination_uri` でテナント横断に逆引き（`isChildOf` は除外）、現テナント発のものを除外し、外向きと同様に **public 限定**＝**private** テナント所有の関連は解決前に除外する（private な採用元は順方向でも逆方向でも一切出さない）。各エントリは origin 項目の title を「他機関 ↩」バッジ付きで相手テナントのツリーへリンク（`incoming_refs` / `related_other_institution_in`、`incoming_refs_label`）。
  - ペイン内の「対象アイテムへ」/親リンクは**経路非依存のラベル**（`view_linked_item`「対象アイテムを表示」、`go_to_top_page`）で、どの経路で来ても自然に読める。
  - **クロス文書の階層（上位/下位 別FW）**: CFItem の `isChildOf` の親/子が**別フレームワーク**（大規模フレームワークを複数ドキュメントに分割した場合）に在るとき、ペインに「上位（別フレームワーク）／下位（別フレームワーク）」節を出す。ツリーは per-doc のままで、境界の親/子だけここに出す（同一ドキュメントの階層はツリーにあるので省く）。各エントリは別FWへのツリー切替リンク（または外部リンクアウト）。テナント横断の `isChildOf` から解決（`cf_association_repository.list_ischildof_parents` / `_children` ＋ `cf_item_repository.map_identifiers_to_items`、`_cross_doc_hierarchy`）。isChildOf の向き: origin=子・destination=親。クロステナントの出し分けも同様: **public 別テナント**の親/子は相手テナントのツリーへ「他機関」バッジ付きでリンク、**private** 別テナントのものは除外（出さない）。
  - **右ペイン = フル詳細。** ペインは**単独 `/uri/{uuid}` ページと同じフル詳細カード**（共通パーシャル `fragments/resource_detail.html`）を描画する。permalink・API URL・実効ライセンス・関連（grouping 別）など全フィールドが、ツリーを離れずに見える。右ペイン用フラグメントと deep-link `?item=` の SSR はどちらもこのフルカードを返す。（従来の軽量サマリ＋「詳細」リンクへの往復は廃止）
  - **初期状態**（アイテム未選択時）: 右ペインに**ドキュメント自身のフル詳細**を共通パーシャルで表示する（`/uri/{doc-uuid}` と同じカード。ルーブリック一覧を含む）。左ペインの**ドキュメント名は自己リンク**で、クリックでドキュメントをペインに再選択する（専用フラグメント `/cftree/doc/{doc}/document` で `#detail-pane` を HTMX 差し替え＋`hx-push-url` でツリー根 `/cftree/doc/{doc}` へ）。他に何も選択されていないときはハイライト。（従来の別「ドキュメント詳細」リンクは削除 — 名前リンク＋ペインで足りる。）アイテムが0件なら左ペインに「アイテムがありません」。ドキュメントフラグメントは `/detail/{item-uuid}` とは**別ルート**で、doc と同じ identifier を持つ CFItem があっても衝突しない（identifier 衝突は許容され、`/uri/` は item を document より優先）。
  - `?item={item-uuid}` パラメータ付きアクセス時は該当アイテムを選択状態で表示する。右ペインの詳細も SSR でインライン出力する（HTMX での追加フェッチは不要）。UUID形式でない場合・該当アイテムが存在しない場合・該当アイテムが別ドキュメントに属する場合はパラメータを無視し初期状態を表示する
- **レスポンシブ**: モバイルではレイアウトを縦積みにし（ツリーが上、詳細ペインが下）、ページ遷移なしですべての情報にアクセスできるようにする。HTMX はモバイル / デスクトップの両方で動作し、アイテムタップで `#detail-pane` の中身を入れ替える。モバイル（`window.innerWidth < 768`）では入れ替え後に詳細ペインへスムーズスクロールする。非 JS クライアントや中クリック / ⌘+クリックでの遷移用に、アイテムリンクの `<a href>`（パス形式 item URL）フォールバックは残す。ツリー上部に CFDocument のタイトルを自己リンク（クリックでドキュメントをペインに選択）として表示し、モバイルでもドキュメント情報にアクセスしやすくする

### Level判定と初期展開状態
`cf_item.depth` カラムに格納（インポート時に `isChildOf` を再帰的にたどって計算）。
**ツリーは遅延ロードする**（`tree_service.build_ssr_tree`）。初期ページは**深さ0-1のみ** SSR し、`<details>/<summary>` でネストする。深い枝は折りたたんだ `<details>` として描画し、その子コンテナに `GET /{tenant}/cftree/doc/{doc}/children/{parent}` への `hx-get`（`hx-trigger="toggle … once"`）を仕込み、**初回展開時に子1階層を取得**する（初期 SSR と同じ `tree_nodes.html` を返すので、どの深さでも展開挙動は同一）。大規模フレームワークでも初期ページが小さく保たれる（サーバレス配信の Lambda/API Gateway 応答サイズ上限内）。各階層は1回の一括取得（`get_children`）。サイクルはパスごとの visited セットでガードする。
**ソート順:** `sequence_number` 昇順 → `human_coding_scheme` 自然順 → `identifier` 辞書順（NULL は最後）。複数親のアイテムは各親の下に出る。
**初期展開状態:** 最上位（depth 0）は展開（`<details open>`、▶ が下向きに回転）、それより深い階層は既定で折りたたみ、リーフは `●`。
**`?item={item-uuid}` / `/item/{id}`**: ルートから当該アイテムまでの**祖先パスを展開状態で SSR** し（ツリーが遅延でも、直接アクセス/リロード/共有でアイテムが文脈付きで見える）、右ペインにそのアイテムのフル詳細を SSR する。展開パスは同一ドキュメント内の isChildOf を祖先方向にたどる（別ドキュメントの isChildOf は対象外）。複数親の場合は `/uri/` の「ツリーで表示」と同一ルール（`sequence_number` 最小、NULL は後 → `destination_node_identifier` 辞書順）で親を選択。load 時の軽い `scrollIntoView` で選択ノードを画面内に出す。

**no-JS / クローラ**: その場展開は JS が要るが、各ノードのラベルは `/item/{id}` への実 `<a href>` で、各 `/item/{id}` は当該アイテムまで展開したツリーを SSR する。よって JS なし（非 JS クライアント・クローラ・中クリック/新タブ）でも全コンテンツに到達できる。

**アクセシビリティ**: ネイティブ `<details>/<summary>` でキーボード操作と開閉のスクリーンリーダー読み上げを担保。装飾アイコン ▶/● は `aria-hidden`、選択ノードは `aria-current="true"`、遅延の子コンテナは読込中 `aria-busy`（`role="status"` の「読み込み中…」プレースホルダ付き）、summary/リンクに `:focus-visible` のフォーカスリング。（正式な `role="tree"` ウィジェットではなく、ネイティブ要素の強化）。

### 孤立アイテム
isChildOf Association を持たないアイテム（外部CASEソースインポートで association がスキップされた場合等）は、ルートレベルの末尾に表示する（depth=0 のうち、**同一ドキュメント内の** isChildOf の origin でないもの。別ドキュメントでのみ origin のものも現ドキュメントでは孤立扱い）。ソート順は上記と同じで `sequence_number` は NULL 扱い。

**展開アイコン（▶/▼）の判定:** 各アイテムが子を持つかは、同一ドキュメント内の isChildOf の `destination_node_identifier` にその `identifier` が存在するかで判定。子があれば `<details>`＋▶、無ければ `●`。`get_children` / `build_ssr_tree` が階層ごとの一括取得から `has_children` を判定する（N+1 なし）。


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

**`extensions` の表示（全リソース種別共通）:** `extensions` は各フレームワークが独自データを格納する自由形式の JSONB であり、JSON の値の型に応じて再帰的に描き分ける:
- object → キー/値ブロック（ネストした object はインデント）
- スカラーの配列 → チップ/バッジ
- object の配列 → 縦積みブロック
- `http:` / `https:` の URL 文字列 → クリック可能なリンク（上記スキームルールと同一。それ以外の文字列はプレーンテキスト）
- その他のスカラー（数値・真偽値等） → テキスト

`extensions` が `null` または空の場合はセクションごと非表示。CFDocument はさらにコンテナレベルの `package_extensions`（`CFPackage.extensions`）と `definitions_extensions`（`CFDefinitions.extensions`）を別セクションで表示する。以下の各リソース種別の詳細ページに同じ `extensions` セクションが現れる。

### 詳細カードのレイアウト（ゾーン構成）

`/uri/{uuid}` ページとツリービュー右ペインは、共通の詳細カード（`fragments/resource_detail.html`）を「ユーザーが見たい順」の情報階層で描画する。上から:

1. **ヘッダー** — リソース種別バッジ（CFDocument の adoptionStatus バッジ / CFItem の humanCodingScheme コードチップ / CFAssociation の associationType チップ / CFRubricCriterionLevel の score チップを併置）、リソースの**名前をカード見出し（`h2`）**として表示、その直下に**コピー用チップ列**（全タイプで識別子・パーマリンク。CFItem / CFDocument はさらに CASE API URL）。連携用 URL はスクロールせずにコピーできる。見出しに使う名前: CFItem → fullStatement、CFDocument / CFRubric / lookup → title、CFRubricCriterion → category、CFRubricCriterionLevel → quality、CFAssociation → 「origin → destination」要約。名前が無い場合は identifier にフォールバックする。見出しに出した名前は**ラベル付き行として重複表示しない**。
2. **内容** — description / notes / abbreviatedStatement 等をヘッダー直下に表示（セクション見出しなし）。CFRubric の評価基準テーブル/リストも description の直後にここで描画する。
3. **分類**（`sec_classification`）— 教育メタデータ: アイテム種別・教育段階・コンセプトキーワード・教科・言語、CFDocument の creator / publisher / version 等。
4. **関連情報**（`sec_relations`）— 所属ドキュメント・クロス文書階層・関連アイテム・ルーブリック・所属ルーブリック/評価基準・対象アイテム。
5. **技術情報**（`sec_technical`）— 識別子・uri・実効ライセンス・status 日付・lastChangeDateTime・extensions。CFItem / CFDocument はさらにパーマリンクと CASE API URL をコピー用の完全な文字列としてここに再掲する（他のタイプのパーマリンクはヘッダーのチップのみ）。最下部に**薄いグレーの常時表示セクション**として描画する（折りたたみにしない — OBF/QTI 連携用 URL の視認性と印刷のため）。

ゾーン 3〜5 は上罫線 + 小さな大文字セクション見出し付きで描画し、内容が無いゾーンはセクションごと省略する。ゾーン内の短いスカラー値は 2 カラムグリッドに並べる場合がある。単独 `/uri/` ページ自体の `<h1>` は `page_title` のみを表示し、種別 / adoptionStatus バッジはカードヘッダー側に置く。

以下のフィールド表は各フィールドの表示条件と形式を定義する。配置（ゾーン）は上記マッピングに従う。

### CFItem の場合

| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID（技術情報セクション + ヘッダーのコピー用チップ） |
| uri | 必須 | URL（リンク） |
| CFDocumentURI | 必須 | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| fullStatement | 必須 | カード見出し（`h2`）。ラベル付き行としては重複表示しない |
| lastChangeDateTime | 必須 | ISO 8601 |
| humanCodingScheme | 任意 | ヘッダーバッジ行のコードチップ |
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
| extensions | 任意 | 自由形式（上記「extensions の表示」参照） |
| 「ツリーで表示」リンク | - | `/{tenant}/cftree/doc/{doc-uuid}?item={item-uuid}` へ遷移。サーバー側でルートからこのアイテムまでの展開パスを計算し、該当ノードまで展開済みのツリーをSSRで返す。アイテムが複数の isChildOf 親を持つ場合は、`sequence_number` が最小の association の親を選択する（NULL は非NULLの後に配置する。`sequence_number` が同じ場合は `destination_node_identifier` の辞書順で最初のもの。エクスポートの親選択ルールと同一） |

### CFDocument の場合

| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID（技術情報セクション + ヘッダーのコピー用チップ） |
| uri | 必須 | URL（リンク） |
| title | 必須 | カード見出し（`h2`） |
| lastChangeDateTime | 必須 | ISO 8601 |
| creator | 任意（CASE v1.1 では必須だが DB は nullable） | テキスト |
| publisher | 任意 | テキスト |
| description | 任意 | テキスト |
| language | 任意 | 言語コード |
| version | 任意 | テキスト |
| adoptionStatus | 任意 | カードヘッダーのバッジ表示（Draft / Private Draft / Adopted / Deprecated） |
| statusStartDate | 任意 | 日付 |
| statusEndDate | 任意 | 日付 |
| licenseURI | 任意 | ネスト表示（title, identifier, uri）。CFItem と同一形式 |
| officialSourceURL | 任意 | URL（リンク） |
| frameworkType | 任意 | テキスト（v1.1 new。外部インポート由来で設定される場合がある） |
| caseVersion | 任意 | テキスト（v1.1 new。値は "1.1" のみ） |
| subject | 任意 | 配列をカンマ区切りで表示 |
| subjectURI | 任意 | 各要素のネスト表示（title, identifier, uri）。配列 |
| CFPackageURI | 必須 | ネスト表示（title, identifier, uri） |
| extensions | 任意 | 自由形式（上記「extensions の表示」参照） |
| package_extensions / definitions_extensions | 任意 | コンテナレベルの extensions。それぞれ別セクション |
| 「ツリーで表示」リンク | - | ツリービュートップへ遷移 |

### lookup リソースの場合（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）

uuid横断検索で lookup リソースに当たった場合、共通フィールド + 固有フィールドを表示する:

| フィールド | 表示形式 |
|-----------|---------|
| identifier | UUID（技術情報セクション + ヘッダーのコピー用チップ） |
| uri | URL（リンク） |
| title | カード見出し（`h2`） |
| description | テキスト（値がある場合のみ） |
| リソース種別 | カードヘッダーのバッジ表示（例: "CFItemType", "CFSubject"） |
| 固有フィールド | typeCode, hierarchyCode, licenseText 等（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |

### CFRubric の場合

uuid横断検索で CFRubric に当たった場合、ルーブリックの詳細と Criteria/Levels を表形式で表示する:

| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID（技術情報セクション + ヘッダーのコピー用チップ） |
| uri | 必須 | URL（リンク） |
| CFDocumentURI | - | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| title | 任意 | カード見出し（`h2`。無い場合は identifier） |
| description | 任意 | テキスト |
| lastChangeDateTime | 必須 | ISO 8601 |
| CFRubricCriteria | 任意 | 表形式またはリスト形式（下記参照）。description の直後に表示 |
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
| identifier | UUID（技術情報セクション + ヘッダーのコピー用チップ） |
| uri | URL（リンク） |
| category | カード見出し（`h2`。無い場合は identifier） |
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
| identifier | UUID（技術情報セクション + ヘッダーのコピー用チップ） |
| uri | URL（リンク） |
| description | テキスト（値がある場合のみ） |
| quality | カード見出し（`h2`。無い場合は identifier） |
| score | 数値（値がある場合のみ）。カードヘッダーにもチップ表示 |
| feedback | テキスト（値がある場合のみ） |
| position | 数値（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |
| 所属評価基準 | CFRubricCriterion の `/uri/` ページへのリンク |

### CFAssociation の場合

uuid横断検索で CFAssociation に当たった場合、最低限の情報を表示する。カード見出しは「origin → destination」の要約（ノードの title。無い場合はノード identifier）:

| フィールド | 表示形式 |
|-----------|---------|
| identifier | UUID（技術情報セクション + ヘッダーのコピー用チップ） |
| uri | URL（リンク） |
| CFDocumentURI | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| associationType | テキスト（例: isChildOf）。カードヘッダーのチップにも表示 |
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
- `/detail/` / `/document` エンドポイントの `{tenant-uuid}` が UUID 形式でない → 400（「リクエストが不正です」テキストを含むHTMLフラグメント + ステータスコード400。フルエラーページではなくフラグメントを返す。HTMX スワップ対応）
- `/detail/` / `/document` エンドポイントの `{tenant-uuid}` が UUID 形式だがテナントが存在しない → 404（「テナントが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404）
- `/detail/` / `/document` エンドポイントの `{doc-uuid}` が UUID 形式でない → 400（「リクエストが不正です」テキストを含むHTMLフラグメント + ステータスコード400）
- `/detail/` / `/document` エンドポイントの `{doc-uuid}` が UUID 形式だがドキュメントが存在しない → 404（「ドキュメントが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式でない → 400（空HTMLフラグメント + ステータスコード400）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式だがアイテムが存在しない → 404 エラーフラグメント
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式でアイテムが存在するが `{doc-uuid}` のドキュメントに属さない → 404 エラーフラグメント（別ドキュメントのアイテム詳細をツリービュー内で表示しない）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式だがアイテムが存在しない、または別ドキュメントに属する場合の 404 エラーフラグメント → 「アイテムが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404
- `/detail/` / `/document` エンドポイントで 500 Internal Server Error が発生した場合 → 「サーバーエラーが発生しました」テキストを含むHTMLフラグメント + ステータスコード500 を返す
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
