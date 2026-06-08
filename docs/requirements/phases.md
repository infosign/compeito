# Phases

## Phase 1 (initial release) — complete
- Local development / execution with Docker
- DB schema for all CASE resources (including CFRubric)
- 11 CASE v1.1 compliant API endpoints (excluding CFRubric) + 5 custom listing endpoints + health check
- v1p0 → v1p1 redirect
- CSV import (auto-detects custom format / OpenSALT format / simple format)
- External CASE source import (v1.1 and v1p0 formats)
- CSV export (custom format only)
- CLI (tenant/doc management, import/export, db migrate)
- Web UI: top list, tenant list, tree view, resource detail (`/uri/` — CFDocument / CFItem / CFAssociation / various lookups), error pages
- Pagination
- Internationalization (Japanese / English, Web UI + CLI)
- Unit / integration tests with pytest
- docker-compose.yml, Dockerfile
- pyproject.toml, README.md

## Phase 2 — complete
- OpenSALT-compatible CSV export (`--profile opensalt`)
- CFRubric API endpoints + CFPackage integration
- CFRubric CSV import / export
- Rubric ingestion in the CASE API import
- v1.0 → v1.1 normalization on import (field-level)
- GitHub Actions CI

## Phase 3 (in progress)

Priority within the phase reflects an OpenCASE conformance-gap analysis: items 1 and 2 closed concrete spec / discovery gaps and were done first; the rest carry forward from earlier planning.

1. ✅ **CASE v1.1 Service Discovery endpoint** — `GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json` returning the official OpenAPI 3 schema as static JSON. Allows CASE clients (and the 1EdTech conformance tester) to discover compeito's API surface. (done)
2. ✅ **CASE v1.1 optional fields**: `notes` (CFItem / CFAssociation / CFDocument), `alternativeLabel` (CFItem), `extensions` (all resources). Persisted in DB and emitted in API responses. (done)
3. ✅ **OpenSALT Excel (.xlsx) round-trip** — 3-sheet OpenSALT Excel import / export, the concrete realization of "improved OpenSALT compatibility" (see [reference/opensalt-csv-format.md](../reference/opensalt-csv-format.md)). (done)
4. ✅ **`GET /CFDocuments` query parameters** — `sort` / `orderBy` / `filter` / `fields` + `X-Total-Count` header (see [api-spec.md](../spec/api-spec.md) and the [conformance backlog](../dev/case-v1p1-conformance-backlog.md)). (done)
5. CSV import / export for CFAssociation types other than `isChildOf` (`isPeerOf`, `exactMatchOf`, etc.)
6. Semantic search over competencies (vector embeddings)
7. Automatic cross-framework mapping suggestions

Remaining strict-conformance gaps (wrappers, package-context URIs, Link headers, etc.) are tracked separately in the [CASE v1.1 conformance backlog](../dev/case-v1p1-conformance-backlog.md).

## Non-goals (explicitly out of scope)

These features are not on the roadmap. The positioning rationale is documented here so future readers can tell "not yet" apart from "not planned."

- **Write API (POST / PUT / DELETE on CASE endpoints)** — compeito is positioned as a read-only CASE publisher to be paired with an external editor (OpenCASE, OpenSALT, or compeito's own CLI). All edits flow through the CLI / import paths, not the public API. Returning 405 Method Not Allowed on non-GET requests is an explicit policy, not a placeholder for future write support. See FR-2.9.
- **Authentication / authorization on the CASE Provider API** (OAuth, Keycloak, Bearer tokens, role-based access, etc.) — the CASE API is public by default. Private tenants are protected by URL secrecy (the tenant UUID is the secret; see FR-1.3). When authenticated access is required for admin operations, that responsibility lives in a separate deployment/management layer, not the CASE API surface compeito itself exposes.

---

# フェーズ定義（日本語）

## Phase 1（初期リリース）— 完了
- Docker環境でのローカル開発・実行
- 全CASEリソースのDBスキーマ（CFRubric含む）
- CASE v1.1 準拠 API 11 エンドポイント（CFRubric除く）+ 独自拡張一覧 5 エンドポイント + ヘルスチェック
- v1p0 → v1p1 リダイレクト
- CSVインポート（独自形式 + OpenSALT形式 + 簡易形式の自動判定）
- 外部CASEソースインポート（v1.1 + v1p0形式対応）
- CSVエクスポート（独自形式のみ）
- CLIツール（tenant/doc管理, import/export, db migrate）
- Web UI: トップ一覧, テナント一覧, ツリービュー, リソース詳細（/uri/ — CFDocument・CFItem・CFAssociation・lookup各種）, エラーページ
- ページネーション
- 国際化（i18n）対応（日本語・英語、Web UI + CLI）
- pytest による unit/integration テスト
- docker-compose.yml, Dockerfile
- pyproject.toml, README.md

## Phase 2 — 完了
- CSVエクスポートのOpenSALT互換形式 (`--profile opensalt`)
- CFRubric API エンドポイント + CFPackage 統合
- CFRubric CSV インポート/エクスポート
- CASE API インポートでのルーブリック取り込み
- CASE v1.0 インポートの v1.1 正規化（フィールドレベル）
- GitHub Actions CI

## Phase 3（進行中）

フェーズ内の優先順は OpenCASE との conformance ギャップ分析を反映している。1・2 は CASE v1.1 仕様 / discovery のギャップを直接埋めるため先行し、それ以降は従来の計画を引き継ぐ。

1. ✅ **CASE v1.1 Service Discovery エンドポイント** — `GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json` で公式 OpenAPI 3 スキーマを静的 JSON として返す。CASE クライアント（および 1EdTech conformance テスタ）が compeito の API サーフェスを discover できるようになる（完了）
2. ✅ **CASE v1.1 オプションフィールド対応**: `notes`（CFItem / CFAssociation / CFDocument）、`alternativeLabel`（CFItem）、`extensions`（全リソース）。DB に永続化し API レスポンスに含める（完了）
3. ✅ **OpenSALT Excel (.xlsx) round-trip** — 3 シートの OpenSALT Excel インポート/エクスポート。「OpenSALT 互換性の改善」の具体的な実現（詳細は [reference/opensalt-csv-format.md](../reference/opensalt-csv-format.md)）（完了）
4. ✅ **`GET /CFDocuments` クエリパラメータ** — `sort` / `orderBy` / `filter` / `fields` + `X-Total-Count` ヘッダー（詳細は [api-spec.md](../spec/api-spec.md) と [conformance backlog](../dev/case-v1p1-conformance-backlog.md)）（完了）
5. isChildOf 以外の CFAssociation の CSV インポート/エクスポート対応（isPeerOf, exactMatchOf 等）
6. コンピテンシーの意味検索（ベクトル埋め込み）
7. フレームワーク間自動マッピング提案

残る厳密適合のギャップ（wrapper、パッケージ内 URI、Link ヘッダー等）は [CASE v1.1 conformance backlog](../dev/case-v1p1-conformance-backlog.md) で別途管理する。

## Non-goals（明示的な対象外）

ロードマップに載せない機能の一覧。「まだやっていない」と「やらない」を将来の読み手が区別できるよう、ポジショニング根拠と合わせて記載する。

- **Write API（CASE エンドポイントへの POST / PUT / DELETE）** — compeito は外部エディタ（OpenCASE、OpenSALT、または自身の CLI）と組み合わせて使う read-only な CASE publisher として位置付けられている。編集はすべて CLI / インポート経路を通り、公開 API は経由しない。非 GET リクエストに 405 Method Not Allowed を返すのは将来の書き込み対応のためのプレースホルダではなく、明示的な方針である（FR-2.9 参照）
- **CASE Provider API の認証 / 認可**（OAuth、Keycloak、Bearer トークン、ロールベースアクセス制御 等） — CASE API はデフォルトで公開。private テナントは URL の秘匿性で保護する（テナント UUID が秘密として機能、FR-1.3 参照）。管理用途で認証付きアクセスが必要な場合は、その責務は別途のデプロイ/管理レイヤーが担い、compeito 自身が露出する CASE API サーフェスでは扱わない
