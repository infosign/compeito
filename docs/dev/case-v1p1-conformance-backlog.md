# CASE v1.1 conformance backlog

compeito の現在のゴールは **OpenCASE / OpenSALT との実用的な相互運用**であり、1EdTech の **Provider 認証（certification）取得そのものは目標にしていない**。そのため公式 CASE v1.1 OpenAPI / REST/JSON Binding と**意図的に異なる**挙動や、未実装の契約項目がいくつかある。

このドキュメントは **将来 conformance / certification を本気で狙うときに着手すべき項目を一箇所に集約**したもの。各項目の現状・優先度・必要作業を記す。詳細な挙動は [docs/spec/api-spec.md](../spec/api-spec.md) の "Intentional differences from CASE v1.1" 節を参照。

> 凡例 — 優先度は **certification 観点**。P1=厳密適合に必須級 / P2=契約として望ましい / P3=軽微。

## すでに対応済み（過去はギャップだったもの）

仕様適合を進めた結果、以下は解消済み（参考）:

- CFItem/CFDocument/CFAssociation の `notes`、CFItem の `alternativeLabel`、全エンティティ + CFPackage/CFDefinitions の `extensions`（PR #191）
- `GET /CFDocuments` の `sort` / `orderBy` / `filter` / `fields`（PR #192）+ `X-Total-Count`・大小無視の文字列等価・`subject` フィルタ（本バックログ作成時の PR）
- パッケージ内 URI を除く厳密出力 `GET /CFPackages/{id}?strict=1`（PR #191）
- Service Discovery `GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json`（実装済・テストあり）
- エラー封筒 `imsx_StatusInfo`（codeMajor / severity / codeMinor.codeMinorField[].{Name,Value}）は適合
- `GET /CFItemAssociations/{id}` の既定を全件返却に（公式契約にページネーション定義なし。既定 limit=100 のサイレント切り詰めを廃止、`limit`/`offset` は明示指定時のみの拡張に。2026-06 適合性監査 N1、PR #220）
- **未定義サブパスの 404 / 未捕捉の 500 を imsx_StatusInfo 形式で返す**（旧 C14 / C15）。`main.py` に `StarletteHTTPException` ハンドラ（CASE API パスの 404 → `unknownobject`）とグローバル `Exception` ハンドラ（CASE API パスの 500 → `internal_server_error`）を追加。CASE API 以外は既定挙動を維持。
- **エラー封筒の `imsx_codeMinorFieldName` を実フィールド名に**（旧 C11）。`imsx_error_response` に `field_name` 引数を追加し、sort / orderBy / filter / fields / limit / offset と request-validation 由来のフィールド名を渡す（既定は `sourcedId`）。
- **`ext:` associationType の文字種検証**（旧 C12）。import 受理を公式パターン `^ext:[a-zA-Z0-9.\-_]+$` で検証し、不一致（`ext:日本語` / `ext:` / 空白入り等）は invalid associationType として skip + warning。
- **`caseVersion` の import 検証**（旧 C8）。想定外の値（`1.0` / `1.1` 以外）は警告を出す。値そのものは保持する（round-trip 忠実度を保つため emit 固定はしない）。

## certification 着手項目（未対応 / 意図的差異）

| # | 項目 | 現状 | 優先 | certification 時の作業 |
|---|------|------|:--:|------|
| C1 | **単一リソースの wrapper** | `{"CFDocument": {...}}` で包む（OpenSALT 流）。公式は flat DType（root に直接） | P1 | wrapper を外す、または「公式 flat 形」を返す別経路/モードを用意。`?strict=1` の対象拡張も一案 |
| C2 | **パッケージ内 URI の既定出力** | 既定で `CFPackage.CFDocument.CFPackageURI` / `CFItems[].CFDocumentURI` を出す（OpenCASE/OpenSALT 互換）。公式 `CFPckg*DType` は `additionalProperties:false` で非許容。`?strict=1` で除去可 | P1 | certification 時は**既定を strict 側に反転**し、現状の echo を opt-in 化 |
| C3 | **required だが nullable な項目** | `creator`、lookup の `hierarchyCode`（CFItemType/CFConcept/CFSubject）、CFItemType の `description`、`licenseText`、`LinkGenURIDType.title` を null 許容（寛容 import 優先） | P1 | **出力時の捏造は避ける**方針。import 厳格化（必須欠落を reject/quarantine）か、strict 出力モードでのみ安全なプレースホルダを合成 |
| C4 | **Set 型の `minItems:1`** | `CFDocumentSetDType` 等は必須・非空配列だが、0 件時に空配列 `[]` を返す | P2 | 仕様の過剰制約。空時の挙動を仕様準拠にするか（=返さない/404 は非現実的）、差異として明文化のまま据え置き |
| C5 | **`Link` ページネーションヘッダ** | 未実装（next/prev/first/last）。`X-Total-Count` は実装済み | P2 | `GET /CFDocuments` に RFC 8288 形式の `Link` を追加。既存クエリ（sort/filter/fields）を保持してリンク生成 |
| C6 | **filter の網羅性** | scalar + `subject`(JSONB) 対応。ネストのドット記法（`licenseURI.identifier` 等）未対応。ordering は大小区別のまま（等価は大小無視に対応済） | P2 | dot-notation のリンクフィールド filter、必要なら collation 指定の case-insensitive ordering |
| C7 | **不明な `sort` / `fields` → 400** | binding 散文は「不明 sort は既定順」「不明 field は全件返す（空 field のみ invalid_selection_field）」。compeito は 400 で明示エラー（typo 可視で親切） | P2 | strict/compat モードでのみ binding 散文どおりの寛容挙動に切替（既定は現状維持を推奨） |
| C9 | **UUID 不正 → 400 / `limit`=0 許容 / `limit`・`offset` の上限 cap** | 実用優先の挙動（OpenAPI は invalid を unknownobject 扱い、`minimum:1` 等） | P3 | strict モードでのみ OpenAPI どおりに（既定は現状維持） |
| C10 | **拡張 list エンドポイント** | `CFItemTypes` 等の list は compeito 拡張（公式 list は `CFDocuments` のみ）。`sort/filter/fields` も `CFDocuments` のみ対応 | — | 仕様超過なので certification 上は無害。必要なら他 list にも query を展開 |
| C13 | **スキーマ層の出力時検証なし** | Pydantic スキーマで identifier の UUID パターン・associationType / targetType の enum を検証していない（import 側で防いでいるため実害は低い） | P3 | strict 出力モード導入時に field_validator で同梱 |

> C14（未定義サブパスの 404 imsx 化）と C15（500 imsx 化）は対応済み。上記「すでに対応済み」を参照。

## デプロイ上の制約（参考）

- `sort` / `filter` / `fields` / `?strict=1` は**動的 API でのみ機能**する。静的公開のデプロイでは既定応答（未ソート・未フィルタ・全フィールド・非 strict）を焼くため、これらを使うには動的公開が前提。

## 方針メモ

- certification を狙う場合、**出力側で値を取り繕う（fabricate）より、入口（import）で厳格化する**ほうがデータ品質を損なわない（C3）。
- 既定の挙動は**実用相互運用優先**のまま、厳密適合は **`?strict=1` 系の opt-in を拡張**して両立させるのが、既存利用を壊さない筋（C1/C2/C7/C9）。
