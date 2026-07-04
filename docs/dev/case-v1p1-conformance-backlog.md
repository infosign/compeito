# CASE v1.1 conformance backlog

compeito は当初「**OpenSALT (CASE v1.0) と完全互換を保ったまま CASE v1.1 に対応する配信サーバー**」を目指して出発した。公式 CASE v1.1 OpenAPI / REST/JSON Binding と**意図的に異なる**挙動（wrapper・URI echo・null echo・caseVersion 保持等）は、この「v1.0 OpenSALT との双方向データ交換」前提の名残である。

**2026-07 に方針を転換した。** OpenSALT も v1.1 開発が進み OpenCASE も標準化しつつある現在、OpenSALT/OpenCASE とは**取り込みの一方通行**（import は寛容なまま維持）で十分であり、プロジェクトのゴールは **1EdTech CASE v1.1 コンフォーマンステストのパス**に移った。かつての「意図的差異」は「歴史的経緯を持つ解消対象」となり、出力側の OpenSALT 互換挙動は段階的に opt-in へ退役させる（strict/compat の既定反転はメジャーバージョンイベントとして実施）。

このドキュメントは **conformance テストをパスするために着手すべき項目を一箇所に集約**したもの。各項目の現状・優先度・必要作業を記す。詳細な挙動は [docs/spec/api-spec.md](../spec/api-spec.md) の "Intentional differences from CASE v1.1" 節を参照。

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
- **`Link` ページネーションヘッダー**（旧 C5）。`GET /CFDocuments` に RFC 8288 形式の `Link`（first/prev/next/last）を実装。既存クエリ（sort/orderBy/filter/fields）を URL エンコードして保持。テナント部分は常に UUID。`offset` 上限（100000）超のページは再丸めによる自己ループを避けるため省略（上限超の最終ページはページ送り不可）。空結果・`limit=0`・先頭ページ単独で全件収まる場合はヘッダーを付けない（`limit` 上限超は 500 に clamp されたうえで通常どおり Link を出す）。`last` のみ binding 例（残件数 limit）と異なり `limit` を保持（意図的差異として api-spec.md に明記）。`build_link_header` の単体テスト＋エンドポイント結合テストあり。

## certification 着手項目（未対応 / 意図的差異）

| # | 項目 | 現状 | 優先 | certification 時の作業 |
|---|------|------|:--:|------|
| C16 | **optional フィールドの null 出力**（exclude_none 未使用） | 全 DType が optional フィールドを `null` で emit（`model_dump` に `exclude_none` なし）。公式スキーマは nullable を定義しないため**型違反**。`?strict=1` でも残る。**現状最大の schema-invalid 源**（2026-07 外部レビュー N1） | P1 | strict 出力で `exclude_none=True` を全エンドポイントに適用。あわせて strict 時は `caseVersion` を `"1.1"` で emit（C8 の出力側）。schemas docstring / api-spec の "strict conformance" 過大表現も同時修正。**設計: [designs/strict-output.md](./designs/strict-output.md)**（C1/C2/C3 も同設計で扱う） |
| C17 | **HEAD / OPTIONS が 405・CORS 未実装**（2026-07 外部レビュー N2） | CASE API パスの middleware が GET 以外を一律 405 に。HEAD プローブが壊れ、ブラウザからのクロスオリジン取得不可 | P3（運用改善） | HEAD 許容＋CORSMiddleware＋405 の Allow ヘッダ更新。certification の直接要件ではなく HTTP/ブラウザ相互運用改善。**設計: [designs/http-head-cors.md](./designs/http-head-cors.md)** |
| C1 | **単一リソースの wrapper** | `{"CFDocument": {...}}` で包む（OpenSALT 流）。公式は flat DType（root に直接） | P1 | wrapper を外す、または「公式 flat 形」を返す別経路/モードを用意。`?strict=1` の対象拡張も一案 |
| C2 | **パッケージ内 URI の既定出力** | 既定で `CFPackage.CFDocument.CFPackageURI` / `CFItems[].CFDocumentURI` を出す（OpenCASE/OpenSALT 互換）。公式 `CFPckg*DType` は `additionalProperties:false` で非許容。`?strict=1` で除去可 | P1 | certification 時は**既定を strict 側に反転**し、現状の echo を opt-in 化 |
| C3 | **required だが nullable な項目** | `creator`、lookup の `hierarchyCode`（CFItemType/CFConcept/CFSubject）、CFItemType の `description`、`licenseText`、`LinkGenURIDType.title` を null 許容（寛容 import 優先） | P1 | **出力時の捏造は避ける**方針。import 厳格化（必須欠落を reject/quarantine）か、strict 出力モードでのみ安全なプレースホルダを合成 |
| C4 | **Set 型の `minItems:1`** | `CFDocumentSetDType` 等は必須・非空配列だが、0 件時に空配列 `[]` を返す | P2 | 仕様の過剰制約。空時の挙動を仕様準拠にするか（=返さない/404 は非現実的）、差異として明文化のまま据え置き |
| C6 | **filter の網羅性** | scalar + `subject`(JSONB) 対応。ネストのドット記法（`licenseURI.identifier` 等）未対応。ordering は大小区別のまま（等価は大小無視に対応済） | P2 | dot-notation のリンクフィールド filter、必要なら collation 指定の case-insensitive ordering |
| C7 | **不明な `sort` / `fields` → 400** | binding 散文は「不明 sort は既定順」「不明 field は全件返す（空 field のみ invalid_selection_field）」。compeito は 400 で明示エラー（typo 可視で親切） | P2 | strict/compat モードでのみ binding 散文どおりの寛容挙動に切替（既定は現状維持を推奨） |
| C9 | **UUID 不正 → 400 / `limit`=0 許容 / `limit`・`offset` の上限 cap** | 実用優先の挙動（OpenAPI は invalid を unknownobject 扱い、`minimum:1` 等） | P3 | strict モードでのみ OpenAPI どおりに（既定は現状維持） |
| C10 | **拡張 list エンドポイント** | `CFItemTypes` 等の list は compeito 拡張（公式 list は `CFDocuments` のみ）。`sort/filter/fields` も `CFDocuments` のみ対応 | — | 仕様超過なので certification 上は無害。必要なら他 list にも query を展開 |
| C13 | **スキーマ層の出力時検証なし** | Pydantic スキーマで identifier の UUID パターン・associationType / targetType の enum を検証していない（import 側で防いでいるため実害は低い） | P3 | strict 出力モード導入時に field_validator で同梱 |

> C14（未定義サブパスの 404 imsx 化）と C15（500 imsx 化）は対応済み。上記「すでに対応済み」を参照。

## デプロイ上の制約（参考）

- `sort` / `filter` / `fields` / `?strict=1` は**動的 API でのみ機能**する。静的公開のデプロイでは既定応答（未ソート・未フィルタ・全フィールド・非 strict）を焼くため、これらを使うには動的公開が前提。

## 方針メモ

- **出力側で値を取り繕う（fabricate）より、入口（import）で厳格化する**ほうがデータ品質を損なわない（C3）。ただし import の寛容さは一方通行方針でも受け側として必要なので、reject はしない。その代わり **conformance-grade の出力には「検証失敗データをそのまま出さない」仕組みが要る**: 候補は (a) import 時の validation report（required 欠落の一覧化）＋運用での補完、(b) strict 出力時に required 欠落リソースを明示エラー/除外（quarantine）、(c) strict 出力時のみ安全なプレースホルダ合成。どれを採るかは strict 出力設計（C16 実装）時に決定する。
- 段取りは2段階: まず **`?strict=1` 系の opt-in を全エンドポイント・全変換（wrapper 除去・exclude_none 等）に拡張**して完成させる（既存利用を壊さない）。その後、**メジャーバージョンイベントとして既定を strict 側に反転**し、旧来の OpenSALT 互換出力を `?compat=1` 系の opt-in に降格する（2026-07 のゴール転換による）。第1段の設計: [designs/strict-output.md](./designs/strict-output.md)。
- **回帰検証基盤**: 公式 OpenAPI スキーマで実レスポンスを機械検証する統合テスト（xfail=既知ギャップ、直ると XPASS で検出）を導入する。設計: [designs/openapi-schema-validation-tests.md](./designs/openapi-schema-validation-tests.md)。
