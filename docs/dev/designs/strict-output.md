# CASE API strict/compat 出力層 実装方針 — conformance backlog C16 / C1 / C2 / C3

> **ステータス: 実装済み（2026-08）**
> C16 / C1 / C2 / C8 出力側 / N7 を実装。C3 は本設計の決定（案 (a)）どおり、strict でキー省略＝データ起因の残ギャップとして conformance backlog に残す。
> 第 2 段（既定の strict 反転）は未実施。`settings.case_output_default` の変更 1 つで行える状態にしてある。
> Codex レビュー 1 ラウンド（技術的前提の実コード検証・仕様間整合・方針整合）＋指摘反映済み（2026-07）。
> [case-v1p1-conformance-backlog.md](../case-v1p1-conformance-backlog.md) の P1 項目群（C16 / C1 / C2 / C3、および C8/N6 の出力側・N7 文言修正）をまとめて解消する設計。
> 目的: CASE API の出力を **compat（現状互換・既定）** と **strict（公式 OpenAPI スキーマ適合）** の 2 モードで対称に切り替えられるようにする。
> ※ strict の schema-valid は**データが required を満たす場合に成立**する。required 欠落データ（C3）は import 時の
> validation report（[import-dry-run-and-ai-guide.md](./import-dry-run-and-ai-guide.md)）で検出し運用で補完する方針であり、補完までは残ギャップ。
> 2026-07 のゴール転換（OpenSALT 完全互換 → **CASE v1.1 コンフォーマンステストのパス**。OpenSALT/OpenCASE は取り込み一方通行）に基づく。

## 決定事項

- **段取りは 2 段階、本仕様は第 1 段**: まず strict を opt-in（`?strict=1`）として**全 CASE GET エンドポイント・全変換**に完成させる（既存利用を壊さない）。将来のメジャーバージョンで既定を strict に反転し、旧挙動を `?compat=1` に降格する（第 2 段は非対象。ただし**反転が設定 1 つ（`case_output_default`）でできる実装**にする。`?compat=1` の受理自体は第 1 段で実装しておく）。
- **compat の既定応答はバイト単位で不変**とする（回帰条件）。strict は「公式スキーマ適合を求めた者だけが受け取る」モード。
- **シリアライズは中央関数に集約**: 各ルーターに散在する `model_dump(by_alias=True)` 直呼びを新設の `src/services/case_serializer.py` に置換し、strict/compat の分岐を 1 箇所にする。`GET /CFPackages/{id}` の既存インライン `?strict=1` 実装（[src/routers/cf_packages.py:32-43](../../../src/routers/cf_packages.py)）もここに統合する。
- **C3（required だが nullable な項目）は案 (a) を採用**: import 時 validation report（別バックログ項目として起票）＋残ギャップの文書化。strict 出力での捏造（プレースホルダ合成）はしない。理由は後述。
- **strict は動的 API のみ**で機能する（静的公開デプロイでは既定応答を焼くため opt-in 不可。既定反転後は静的公開も strict になる）。

## 背景

compeito は当初 OpenSALT (CASE v1.0) との双方向互換を思想としており、次の「意図的差異」を既定出力に残している。ゴール転換後、これらは**解消対象**となった:

| backlog | 差異 | 現状の実害 |
|---|---|---|
| C16 | optional フィールドの `null` emit（`exclude_none` 未使用） | 公式スキーマは nullable を定義しないため**型違反**。現状最大の schema-invalid 源（2026-07 外部レビュー N1）。`?strict=1` でも残る |

> **C16 を実装するときの注意（利用側との契約）**: 生成側のラウンドトリップ比較は「キー欠落と `null` は同義」という前提で作られている。`exclude_none=True` はその前提を満たす方向の変更なので比較は壊れない。壊れるのは逆で、**`null` に「値が無い」以上の意味を持つフィールドを増やしたとき**である（現状は `statusStartDate` / `statusEndDate` の2つだけ。[import-logic.md](../../spec/import-logic.md) の「例外：ライフサイクル日付」）。3つ目を作る場合は、出荷前に利用側へ周知する。
| C1 | 単一リソース取得の wrapper `{"CFDocument": {...}}`（OpenSALT 流） | 公式は flat DType をルートに返す契約 |
| C2 | パッケージ内 `CFPackageURI` / `CFDocumentURI` echo | 公式 `CFPckg*DType` は `additionalProperties:false` で非許容。既存 `?strict=1` は CFPackages のみ・この除去のみ |
| C8/N6 出力側 | `caseVersion` を保持値のまま emit（`1.0` 等） | v1.1 サーバーとして `"1.1"` を宣言すべき局面で保持値が出る |
| C3 | required だが null な項目（`creator`、lookup の `hierarchyCode` 等） | strict でも required 欠落として schema-invalid が残り得る |
| N7 | schemas docstring / api-spec の "strict conformance" 過大表現 | `?strict=1` が「完全適合」に見える文言（実際は URI 除去のみ） |

### 公式 OpenAPI（docs/reference/imscasev1p1_openapi3_v1p0.json）で確認済みの事実

- 単一リソースの 200 応答は flat DType: `/CFDocuments/{sourcedId}` → `CFDocumentDType`、`/CFItems/{sourcedId}` → `CFItemDType`、`/CFAssociations/{sourcedId}` → `CFAssociationDType`、`/CFLicenses/{sourcedId}` → `CFLicenseDType`、`/CFAssociationGroupings/{sourcedId}` → `CFAssociationGroupingDType`、`/CFRubrics/{sourcedId}` → `CFRubricDType`、`/CFPackages/{sourcedId}` → `CFPackageDType`。
- **Set 型は wrapper が公式形**: `/CFItemTypes/{sourcedId}` → `CFItemTypeSetDType` = `{"CFItemTypes": [...]}`、同様に `CFConceptSetDType` / `CFSubjectSetDType`。`/CFItemAssociations/{sourcedId}` → `CFAssociationSetDType` = `{"CFItem": ..., "CFAssociations": [...]}`（compeito の現行形と一致）。`/CFDocuments` → `CFDocumentSetDType` = `{"CFDocuments": [...]}`。**これらの wrapper は触らない**。
- 全 DType が `additionalProperties: false`。nullable な property は 1 つもない（= `null` を emit した時点で型違反）。
- required リスト（C3 の対象確定用）: `CFDocumentDType` は `creator` を required に含む。`CFItemTypeDType` は `description` と `hierarchyCode`、`CFConceptDType` / `CFSubjectDType` は `hierarchyCode`、`CFLicenseDType` は `licenseText`、`LinkGenURIDType` / `LinkURIDType` は `title` が required。
- 標準の CFAssociationDType（standalone）は `CFDocumentURI` を property に**持つ**（optional）ので、compeito の standalone 出力に追加の除去は不要。
- `caseVersion` は CFDocumentDType / CFPckgDocumentDType 双方の property（required ではない）。

## アプローチ

### 1. 出力モードの解決（API surface）

- 全 CASE GET エンドポイント（下表の 18 ルート。discovery は静的スキーマ配信なので対象外）に `strict` / `compat` クエリパラメータを追加する。
- truthy 判定は既存 `_TRUTHY = {"1", "true", "yes", "on"}`（大文字小文字無視）を中央に移して共用。**非 truthy 値（`strict=0` / `strict=abc` 等）は「未指定」扱い**（cf_packages.py の現行挙動を維持）。
- 解決規則:
  1. `strict` と `compat` が**両方 truthy → 400**。imsx_StatusInfo 形式（`imsx_error_response(400, "Conflicting output mode: 'strict' and 'compat' are mutually exclusive", "invalid_selection_field", field_name="strict")`）。
  2. どちらか一方が truthy → そのモード。
  3. どちらも未指定 → `settings.case_output_default`。
- `src/config.py` に追加: `case_output_default: Literal["compat", "strict"] = "compat"`（env: `CASE_OUTPUT_DEFAULT`）。**第 2 段の反転はこの既定値を `"strict"` に変えるだけ**で完了する（`?compat=1` は第 1 段から機能している）。
- 実装形: FastAPI dependency にする（14 エンドポイント超への boilerplate を避ける）。

```python
# src/errors.py に追加
class OutputModeConflictError(Exception):
    def __init__(self, message: str):
        self.message = message

# src/main.py にハンドラ追加（既存 InvalidUUIDError ハンドラと同型）
@app.exception_handler(OutputModeConflictError)
async def output_mode_conflict_handler(request, exc):
    return imsx_error_response(400, exc.message, "invalid_selection_field", field_name="strict")

# src/dependencies.py に追加
async def output_mode(
    strict: str | None = Query(default=None),
    compat: str | None = Query(default=None),
) -> OutputMode:
    return resolve_output_mode(strict, compat)  # 競合時 OutputModeConflictError
```

- `GET /CFDocuments` の **RFC 8288 `Link` ヘッダーに `strict` / `compat` を伝播**する: `build_link_header(..., extra_params={...})` の extra_params に生のパラメータ値を追加（`None` は既存仕様どおり省略）。ページ送りでモードが落ちるのを防ぐ。この目的のため `GET /CFDocuments` だけは dependency に加えて生値も受け取る（他のエンドポイントは dependency のみでよい）。

### 2. 中央シリアライザ `src/services/case_serializer.py`（新規）

```python
"""CASE API output serialization: compat (legacy/OpenSALT-style) vs strict
(official CASE v1.1 OpenAPI schema shape). Single place that decides wrapper
presence, exclude_none, package-context URI stripping and caseVersion."""

from typing import Literal, Sequence

OutputMode = Literal["compat", "strict"]
TRUTHY = {"1", "true", "yes", "on"}
CASE_VERSION_EMIT = "1.1"  # what a CASE v1.1 server declares in strict mode


def resolve_output_mode(strict: str | None, compat: str | None) -> OutputMode: ...
    # 上記の解決規則。競合時 OutputModeConflictError を raise。


def dump_model(model: CASEBaseSchema, mode: OutputMode) -> dict:
    """1 リソースを dict にする基本変換 (C16 + caseVersion)."""
    strict = mode == "strict"
    dumped = model.model_dump(by_alias=True, exclude_none=strict)
    if strict and isinstance(model, (CFDocumentDType, CFPckgDocumentDType)):
        dumped["caseVersion"] = CASE_VERSION_EMIT
    return dumped


def dump_single(model: CASEBaseSchema, mode: OutputMode, *, compat_wrapper: str) -> dict:
    """単一リソース応答 (C1). compat: {compat_wrapper: {...}} / strict: flat."""
    dumped = dump_model(model, mode)
    return dumped if mode == "strict" else {compat_wrapper: dumped}


def dump_collection(models: Sequence[CASEBaseSchema], mode: OutputMode, *, wrapper: str) -> dict:
    """Set 型・list 応答。wrapper は両モードで維持（公式形 or compeito 拡張形）."""
    return {wrapper: [dump_model(m, mode) for m in models]}


def dump_package(package: CFPackageDType, mode: OutputMode) -> dict:
    """CFPackage 応答（両モードで flat）。strict: exclude_none 伝播 + C2 の URI 除去 +
    CFDocument.caseVersion 書き換え。cf_packages.py のインライン実装をここへ移設."""
    strict = mode == "strict"
    content = package.model_dump(by_alias=True, exclude_none=strict)
    if strict:
        content["CFDocument"].pop("CFPackageURI", None)
        content["CFDocument"]["caseVersion"] = CASE_VERSION_EMIT
        for item in content.get("CFItems", []):
            item.pop("CFDocumentURI", None)
    return content
```

各ルーターは `model_dump(by_alias=True)` 直呼びをやめ、上記 4 関数のいずれかを呼ぶ。`GET /CFItemAssociations/{id}` は公式形が `{"CFItem": ..., "CFAssociations": [...]}` なので `{"CFItem": dump_model(item, mode), "CFAssociations": [dump_model(a, mode) for a in assocs]}` と合成する（wrapper キーは両モード共通）。

### 3. C16: exclude_none（strict 時のみ）

- strict 時は `model_dump(by_alias=True, exclude_none=True)`。compat は現状どおり `exclude_none` なし（null echo 維持）。
- **pydantic 2.12.5（本リポジトリの実バージョン）で検証済みの挙動**（設計の前提。テストでも固定する）:
  - `exclude_none=True` は **field_serializer が None を返すフィールドも除外**する（`CASEBaseSchema.serialize_date` / `serialize_datetime` が None を返す `statusStartDate` 等も正しく落ちる）。
  - **`dict` 型フィールド（`extensions`）の内部は不変**: `extensions={"k": None}` の内部 null は保持され、`extensions={}` は `{}` のまま emit される。除外されるのは「フィールド値そのものが None」の場合だけ。ユーザーデータを壊さない。
  - ネストした BaseModel（`LinkURIType` / `LinkGenURIDType` / CFRubric の criteria / levels）へは pydantic が自動で再帰適用する。
- **例外: `CFPackageDType` / `CFDefinitionsDType` は custom `@model_serializer` を持ち、内部で `model_dump(by_alias=True)` を手で呼んでいるため `exclude_none` が伝播しない**（[src/schemas/cf_package.py](../../../src/schemas/cf_package.py)）。両 serializer を `@model_serializer(mode="plain")` + `info: SerializationInfo` に変更し、ネスト dump に `exclude_none=bool(info.exclude_none)` を渡す（`SerializationInfo.exclude_none` の伝播も pydantic 2.12.5 で動作検証済み）。compat 時（exclude_none=False）は現行出力と同一になることを回帰で確認する。

### 4. C1: 単一リソース wrapper の除去（strict 時のみ）

エンドポイント別の変更一覧（実装時はこの表を網羅すること）:

| ルート | 現状の形 | strict での形 | wrapper 変更 |
|---|---|---|:--:|
| `GET /CFDocuments` | `{"CFDocuments": [...]}` ([cf_documents.py](../../../src/routers/cf_documents.py)) | 同（公式 `CFDocumentSetDType`）+ exclude_none + caseVersion | なし |
| `GET /CFDocuments/{id}` | `{"CFDocument": {...}}` (cf_documents.py:84) | **flat `CFDocumentDType`** | **除去** |
| `GET /CFItems/{id}` | `{"CFItem": {...}}` (cf_items.py:26) | **flat `CFItemDType`** | **除去** |
| `GET /CFItemAssociations/{id}` | `{"CFItem":..., "CFAssociations":[...]}` (cf_items.py) | 同（公式 `CFAssociationSetDType` と一致） | なし |
| `GET /CFAssociations/{id}` | `{"CFAssociation": {...}}` (cf_associations.py:26) | **flat `CFAssociationDType`** | **除去** |
| `GET /CFPackages/{id}` | flat（既に公式形） | 同 + URI 除去 + exclude_none + caseVersion | なし |
| `GET /CFItemTypes` | `{"CFItemTypes": [...]}`（compeito 拡張 list、C10） | 同（形は据え置き） | なし |
| `GET /CFItemTypes/{id}` | `{"CFItemTypes": [...]}`（公式 Set 型） | 同 | なし |
| `GET /CFConcepts` / `GET /CFConcepts/{id}` | 拡張 list / 公式 Set 型 | 同 | なし |
| `GET /CFSubjects` / `GET /CFSubjects/{id}` | 拡張 list / 公式 Set 型 | 同 | なし |
| `GET /CFLicenses` | `{"CFLicenses": [...]}`（拡張 list） | 同 | なし |
| `GET /CFLicenses/{id}` | `{"CFLicense": {...}}` (cf_licenses.py:49) | **flat `CFLicenseDType`** | **除去** |
| `GET /CFAssociationGroupings` | 拡張 list | 同 | なし |
| `GET /CFAssociationGroupings/{id}` | `{"CFAssociationGrouping": {...}}` (cf_association_groupings.py:49) | **flat `CFAssociationGroupingDType`** | **除去** |
| `GET /CFRubrics`（`doc=` 必須・拡張） | `{"CFRubrics": [...]}` | 同 | なし |
| `GET /CFRubrics/{id}` | `{"CFRubric": {...}}` (cf_rubrics.py:50) | **flat `CFRubricDType`** | **除去** |
| `GET /ims/case/v1p1/discovery/...json` | 公式 OpenAPI スキーマそのもの | 対象外（strict/compat 概念なし） | — |

- wrapper 除去対象は **6 ルートのみ**: CFDocuments/{id}, CFItems/{id}, CFAssociations/{id}, CFLicenses/{id}, CFAssociationGroupings/{id}, CFRubrics/{id}。
- **Set 型 3 ルート（CFItemTypes/{id} / CFConcepts/{id} / CFSubjects/{id}）と CFPackages/{id}・CFItemAssociations/{id}・CFDocuments list は wrapper 変更の対象外**（現行形＝公式形）。
- **list 系エンドポイントの wrapper（`CFDocuments` は公式形、拡張 list 6 本は compeito 独自）は両モードで触らない**。拡張 list は公式に存在しないので「strict での公式形」自体が定義されない（仕様超過・無害、backlog C10）。
- 全ルートで strict でも `exclude_none`（＋ CFDocument には caseVersion 書き換え）は適用する（拡張 list 含め対称に）。

### 5. C2: パッケージ内 URI 除去の中央統合

- cf_packages.py のインライン `_TRUTHY` 判定・`pop` ロジック（cf_packages.py:32, 40-43）を削除し、`output_mode` dependency + `dump_package()` に置換。応答は従来どおり両モードで flat。
- strict 時の除去対象は現行どおり `CFDocument.CFPackageURI` と各 `CFItems[].CFDocumentURI`（公式 `CFPckgDocumentDType` / `CFPckgItemDType` は `additionalProperties:false` でこれらを持たない）。
- **既存 `?strict=1` の挙動は強化される**（URI 除去のみ → null 除去・caseVersion 書き換えも付く）。strict は「公式スキーマ適合モード」なので意図された変更。api-spec.md に明記する。

### 6. C8/N6 出力側: caseVersion

- strict 時、`CFDocumentDType` / `CFPckgDocumentDType` の出力 dict で **`caseVersion` を常に `"1.1"` にする**（保持値が `1.0` でも、None（未設定）でも）。適用箇所: `GET /CFDocuments`（各要素）、`GET /CFDocuments/{id}`、`GET /CFPackages/{id}` の `CFDocument`。
- compat は現状どおり保持値をそのまま emit（round-trip 忠実度維持。import 側の検証・保持は旧 C8 対応済みのまま変更しない）。
- これは本設計で**唯一の値合成**だが、`caseVersion` は「この応答がどの CASE バージョンの形か」というサーバー宣言であり、ソースデータの捏造には当たらない（v1.0 由来データも compeito が v1.1 形で配信している事実の宣言）。

### 7. C3: nullable required の扱い — 案 (a) を採用

conformance backlog 方針メモの 3 候補から **(a) import 時 validation report ＋残ギャップの文書化** を採用する。

- (a) **採用**: import 時に「公式 required だが欠落/null の項目」（`creator`、CFItemType の `description`・`hierarchyCode`、CFConcept/CFSubject の `hierarchyCode`、`licenseText`、association ノードの `title`）を warning として一覧化し、運用でデータを補完する。**既存の捏造回避方針（出力側で値を取り繕わない）に合致**し、データ品質そのものを改善するため strict/compat 以外の経路（CSV/Excel エクスポート等）にも効く。validation report 自体は**本仕様の範囲外**（別バックログ項目として起票する。import は寛容なまま＝reject しない方針を維持）。
- (b) 不採用（strict 時の quarantine/明示エラー）: パッケージから一部リソースが黙って消える・単一取得が突然エラーになるのはクライアントにとって予測不能で、conformance テスト中のデバッグも困難。
- (c) 不採用（プレースホルダ合成）: `creator: "unknown"` のような捏造はデータ提供者の意図を偽る。方針メモの「出力側で fabricate しない」原則に反する。
- **本仕様での strict の挙動**: 該当フィールドが None なら `exclude_none` により**キー自体を省略**する。これで型違反（`null` は string でない）は解消し、違反は「required キー欠落」に変わる。これは**データ品質の問題としての残ギャップ**であり、strict 実装後も conformance backlog C3 行に「出力層は対応済み・required 欠落はデータ起因、validation report（別項目）で運用補完」と明記して残す。データが揃っているテナントでは strict 出力は完全に schema-valid になる。

### 8. N7: 文言修正

- [src/schemas/cf_document.py:34-](../../../src/schemas/cf_document.py)（`CFPckgDocumentDType` docstring）と [src/schemas/cf_item.py:35-](../../../src/schemas/cf_item.py)（`CFPckgItemDType` docstring）の「request `?strict=1` on GET /CFPackages/{id} ... for strict conformance」という表現を更新: `?strict=1` は全 CASE GET エンドポイント共通の出力モードで、URI 除去は `src/services/case_serializer.py` の `dump_package` が担う旨に書き換える。
- docs/spec/api-spec.md の strict 関連記述を全面更新（EN/JA 両節。対象行は「変更するファイル」表を参照）: 「`?strict=1` は現状パッケージ内 URI の除去のみ」という注記を「strict 出力モード（wrapper 除去・exclude_none・caseVersion="1.1"・パッケージ内 URI 除去）」の説明に置換し、`?compat=1`・`case_output_default`・両指定 400・残ギャップ（C3 のデータ起因 required 欠落、C4 の空配列）を記載する。

## 変更するファイル

| ファイル | 変更内容 |
|---|---|
| `src/services/case_serializer.py`（新規） | `OutputMode` / `TRUTHY` / `CASE_VERSION_EMIT` / `resolve_output_mode` / `dump_model` / `dump_single` / `dump_collection` / `dump_package` |
| `src/config.py` | `case_output_default: Literal["compat", "strict"] = "compat"` を追加 |
| `src/errors.py` | `OutputModeConflictError` を追加 |
| `src/main.py` | `OutputModeConflictError` の imsx 400 ハンドラを追加 |
| `src/dependencies.py` | `output_mode` dependency を追加 |
| `src/routers/cf_documents.py` | 両ルートを serializer 化。list は `dump_model`+`project_fields`、単一は `dump_single(compat_wrapper="CFDocument")`。`Link` ヘッダー extra_params に `strict`/`compat` を追加 |
| `src/routers/cf_items.py` | `CFItems/{id}` は `dump_single(compat_wrapper="CFItem")`、`CFItemAssociations/{id}` は `dump_model` 合成（wrapper 維持） |
| `src/routers/cf_associations.py` | `dump_single(compat_wrapper="CFAssociation")` |
| `src/routers/cf_packages.py` | インライン strict 実装（`_TRUTHY`・pop）を削除し `output_mode` + `dump_package` に置換 |
| `src/routers/cf_item_types.py` `cf_concepts.py` `cf_subjects.py` | list / Set 型とも `dump_collection`（wrapper 維持・exclude_none のみ効く） |
| `src/routers/cf_licenses.py` `cf_association_groupings.py` `cf_rubrics.py` | list は `dump_collection`、単一は `dump_single`（wrapper キーはそれぞれ `CFLicense` / `CFAssociationGrouping` / `CFRubric`） |
| `src/schemas/cf_package.py` | `CFPackageDType` / `CFDefinitionsDType` の `@model_serializer` を `mode="plain"` + `SerializationInfo` 受けに変更し `exclude_none` を伝播 |
| `src/schemas/cf_document.py` / `src/schemas/cf_item.py` | CFPckg* docstring の文言更新（N7） |
| `docs/spec/api-spec.md` | strict 節の全面更新（N7）。対象: 74-76 行・420-422 行（strict 説明）、226 行・573 行（targetType null 注記 → strict で解消と記載）、304 行・651 行（wrapper の意図的差異 → strict で公式形と記載）、316 行（nullable required 注記に C3 決定を反映）、472 行・480 行（動的 API 限定の注意に `strict`/`compat` を追加） |
| `docs/dev/case-v1p1-conformance-backlog.md` | C16 / C1 / C2 を「対応済み」へ移動、C3 行に本設計の決定（案 (a)・残ギャップ）を記録、方針メモの「どれを採るかは strict 出力設計時に決定」を解決済みに更新。import validation report を新規項目として起票 |
| `tests/unit/test_case_serializer.py`（新規） | 変換ごとの単体テスト（下記） |
| `tests/integration/test_strict_output.py`（新規） | 全エンドポイントの strict 応答テスト（下記） |

コード実装時は上記以外のファイル（web UI・CLI・import/export サービス）に触れない。

## エッジケース

- **`extensions` の null と `{}` の違い**: strict の `exclude_none` は「フィールド値が None」のみ除外する。`extensions: null`（未設定）→ strict でキー省略 / compat で `null` emit。`extensions: {}` → 両モードで `{}` のまま。`extensions` **内部**の null 値（`{"k": null}`）はユーザーデータなので両モードで保持（pydantic 2.12.5 で検証済み）。`CFRubricCriterionLevelDType.extensions`（`list[dict]`）も同様に内部不変。
- **CFPackage / CFDefinitions の既存挙動**: custom serializer は現状 falsy（None と `{}`）の `extensions`・空配列の CFDefinitions キーを**両モードで**落としている。この既存挙動は変えない（変更は exclude_none の伝播のみ）。compat 出力の回帰テストで固定する。
- **`notes` 等 optional の既定挙動維持**: compat では従来どおり `null` を emit する（既存クライアント・既存テスト・静的公開の焼き出しを壊さない）。
- **CFPackage 内ネストへの exclude_none 伝播**: custom `@model_serializer` が `exclude_none` を握りつぶす罠（本文 §3）。`CFItems[]` / `CFAssociations[]` / `CFDefinitions.*[]` / `CFRubrics[]`（criteria / levels のネスト含む）の全階層で null が消えることをテストで確認する。
- **field_serializer が None を返すフィールド**: `statusStartDate` / `statusEndDate` / `lastChangeDateTime` 系は serializer 経由でも `exclude_none` で正しく落ちる（検証済み）。`score` / `weight` の int/float serializer は非 None 値に対して従来どおり。
- **`LinkGenURIDType.targetType` が None**: strict でキー省略（api-spec.md 226/573 行の既知型違反が解消）。`title` が None の場合も省略されるが、これは C3 の残ギャップ（required 欠落）としてデータ側の問題。
- **caseVersion が None**: strict では `"1.1"` を emit（キー省略ではなく合成。§6 の理由）。compat では `null`。
- **`?strict=1&compat=1`**: 400 imsx（`field_name="strict"`）。`?strict=1&compat=0` は strict（非 truthy は未指定扱い）。`?strict=abc` は未指定扱い → 既定モード。
- **`fields` との併用**（`GET /CFDocuments` のみ）: 射影は strict dump の**後**に適用する。strict で None のため省略されたフィールドを `fields` に指定しても復活しない（キーが無いだけで正常応答）。`caseVersion` 書き換えは射影前に行う（`fields` から外れていれば射影で落ちる — 正しい挙動）。
- **`Link` ヘッダー**: `strict` / `compat` 指定時はページ送り URL に伝播する。未指定時は付かない（既存 URL 形の非破壊）。
- **リスト系 wrapper**: `{"CFDocuments": [...]}` は公式 Set 型の形なので strict でも**除去しない**こと（wrapper 除去を機械的に全適用しない）。Set 型 3 ルート・CFItemAssociations も同様。
- **空配列（C4）**: `CFDocumentSetDType` 等の `minItems:1` 違反（0 件時の `[]`）は本仕様の**非対象**（据え置き。backlog C4 のまま）。
- **キャッシュ**: `?strict=1` は URL が異なるためキャッシュキーも別。`Cache-Control` 値は両モード共通で変更なし。
- **静的公開**: 静的デプロイは既定応答を焼くため strict opt-in は不可（動的 API 限定）。既定反転（第 2 段）後は静的公開も strict になる。api-spec.md のデプロイ注意（472/480 行）に追記。
- **CLI / Web UI は不変**: `cli.py` の CASE JSON エクスポート（`model_dump(by_alias=True, exclude_none=False)`、cli.py:1290）と web/cf_view_service の dump は round-trip 忠実度のため compat 相当のまま（本仕様の対象外）。cf_package.py の serializer 変更が**既定（exclude_none 未指定）で従来と同一出力**であることが、これらを壊さない条件（回帰テストで担保）。

## テスト方針

**単体（`tests/unit/test_case_serializer.py`・新規）** — DB 不要、スキーマインスタンスを直接組む:

- `resolve_output_mode`: 未指定→config 既定（`compat`）、`settings.case_output_default="strict"` 上書き時→strict、truthy 各表記（`1`/`true`/`yes`/`on`/大文字）、非 truthy（`0`/`false`/`abc`）→未指定扱い、両指定→`OutputModeConflictError`。
- `dump_model`: strict で None フィールド（`notes`・`statusStartDate`・`targetType` 等）のキーが消える／compat で `null` のまま。`extensions={"k": None}` の内部保持、`extensions={}` の保持、`extensions=None` の省略。CFDocument の `caseVersion`（`"1.0"`→`"1.1"`、None→`"1.1"`、compat は保持値）。
- `dump_single`: compat wrapper あり／strict flat。
- `dump_package`: strict で `CFPackageURI`/`CFDocumentURI` の除去＋**全ネスト階層**（CFItems / CFAssociations / CFDefinitions 内の各配列 / CFRubrics→criteria→levels）から null が消えること（exclude_none 伝播の検証）。compat 出力が変更前実装と同一 dict であること。
- `cf_package.py` serializer 回帰: `model_dump(by_alias=True)`（exclude_none 未指定）が従来出力と同一。

**エンドポイント（`tests/integration/test_strict_output.py`・新規、既存 conftest の DB フィクスチャを利用）**:

- 18 ルート（上表）それぞれに `?strict=1` を付け:
  - 応答 JSON を再帰走査して **null 値が存在しない**こと（`extensions` サブツリーは走査から除外）。
  - wrapper の有無が表どおり（flat 6 ルート・wrapper 維持ルート）。
  - CFDocument を含む応答で `caseVersion == "1.1"`。
- 既定（パラメータなし）応答が**従来と同一**であること（代表ルートで固定値アサーション。既存の integration テスト群が無修正で通ることも回帰条件）。
- `?compat=1` が既定と同一応答。`?strict=1&compat=1` → 400 imsx（`imsx_codeMinorFieldName == "strict"`、`invalid_selection_field`）。
- `GET /CFDocuments?strict=1&limit=1` の `Link` ヘッダー各 rel に `strict=1` が含まれる。
- `settings.case_output_default="strict"` 上書き時に無指定で strict になり、`?compat=1` で旧形に戻る（第 2 段の反転リハーサル）。
- 既存 `tests/unit/test_notes_extensions.py::test_strict_omits_package_context_uris` は維持（strict 強化後も URI 非包含アサーションは成立する。null 除去が加わるため、もし null 存在を前提とするアサーションがあれば修正）。

**公式スキーマでの jsonschema 検証**（strict 応答を `imscasev1p1_openapi3_v1p0.json` の各 DType で validate する網羅テスト）は**別仕様 [openapi-schema-validation-tests.md](openapi-schema-validation-tests.md)（並行作成中）に委譲**する。本仕様のテストは「変換が仕様どおり行われたか」の構造アサーションまでを担う。

## conformance backlog との対応

| backlog 行 | 本仕様での扱い |
|---|---|
| C16（optional の null 出力） | **解消**: strict で `exclude_none=True` を全 18 ルートに適用（中央シリアライザ） |
| C1（単一リソース wrapper） | **解消**: strict で flat DType（対象 6 ルート、Set 型/Package/list は対象外） |
| C2（パッケージ内 URI） | **統合**: 既存 `?strict=1` 実装を `dump_package` へ移設（挙動は維持しつつ strict 全体に包含） |
| C8/N6 出力側（caseVersion） | **解消**: strict で常に `"1.1"` emit。compat は保持値（import 側の旧 C8 対応は不変） |
| C3（nullable required） | **方針決定**: 案 (a)。strict はキー省略（型違反→required 欠落に縮小）、validation report は別項目起票、残ギャップを backlog に明記 |
| N7（文言） | **解消**: schemas docstring / api-spec.md の "strict conformance" 表現を実態に合わせ更新 |
| C4 / C6 / C7 / C9 / C13 | **非対象**（下記） |

## 非対象（今回やらないこと）

- **既定の strict 反転（第 2 段）**: メジャーバージョンイベントとして別途実施。本仕様は `case_output_default` の切替だけで反転できる状態を作るまで。
- **C4**: Set 型の `minItems:1`（0 件時の空配列）。
- **C6**: filter の dot-notation / case-insensitive ordering。
- **C7 / C9**: strict モードでのリクエスト**検証**挙動の変更（不明 sort/fields の寛容化、不正 UUID→unknownobject、limit の OpenAPI どおり化）。本仕様の strict は**出力形のみ**を変える。`OutputMode` 基盤は将来これらのフックとして使える。
- **C13**: 出力時の field_validator（UUID パターン・enum 検証）の同梱。
- **C3 の import validation report 本体**（別バックログ項目として起票のみ）。
- **CLI（`export case-json` 等）への strict オプション・Web UI への露出**: CLI/Excel/CSV 経路は round-trip 忠実度優先で compat 相当のまま。
- **公式 OpenAPI スキーマによる jsonschema 検証テスト**: 別仕様 openapi-schema-validation-tests.md に委譲。
- **POST/PUT 等の書き込み API**（CASE v1.1 配信サーバーとして read-only の前提は不変）。
