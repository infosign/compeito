# OpenCASE round-trip status

OpenCASE → compeito → OpenCASE の round-trip で「データが情報量を保ったまま往復する」ことを保証するための文書。テストは [tests/integration/test_round_trip.py](../../tests/integration/test_round_trip.py)、fixture は [tests/fixtures/opencase_round_trip_baseline.json](../../tests/fixtures/opencase_round_trip_baseline.json)。

## ステータス

**達成済**。`test_lossless` は `strict=True` で通常 pass。

「bit-for-bit 完全一致」ではなく **情報量を失わずに往復できる** という意味での round-trip 保証。カテゴリ A〜G の全 308 件の差分が、`_normalize` のルールでカバーされる「仕様上等価な表現差」または「compeito が source 値を verbatim 保持する実装変更」のどちらかで処理されている。

## diff 正規化ルール（round-trip 違反として数えないもの）

- リストの順序（`identifier` でソートして比較）
- `null` ≡ missing key（CASE v1.1 仕様上等価。compeito は FR-2.10 で null を emit、OpenCASE は省略）
- `[]` ≡ missing key（同上。compeito は FR-2.3 で `CFDefinitions` のサブ配列を空時に省略、OpenCASE は `[]` を emit）
- `lastChangeDateTime` は無視（compeito は import 時にタイムスタンプを打ち直す。元タイムスタンプ保持は FR-7.2 系の別作業）
- LinkURI-shape dict（`{identifier, uri, title?, targetType?}`）の `title` を無視（cat E。OpenCASE は literal type label、compeito は実 title を emit。実機テストで OpenCASE が compeito の値を verbatim 保持することを確認済）

## ギャップカタログ（最終）

`tests/fixtures/opencase_round_trip_baseline.json`（OpenCASE から export したテスト用フレームワーク、36 CFItems / 36 CFAssociations / 2 CFRubrics）を流して計測した。

| カテゴリ | 状態 | 件数 | 内容 |
|---------|------|------|------|
| ~~A. URI 書き換え~~ | **解消** | ~~270~~ → 0 | CFPackage import が source URI を保持するよう `_resolve_uri()` を導入（カテゴリ A 単体で 262 件、残 8 件は F / G で対処） |
| ~~B. CFItem に CFDocumentURI 欠落~~ | **解消** | ~~36~~ → 0 | `CFPckgItemDType` に CFDocumentURI を emit するよう変更 |
| ~~C. score が int → float~~ | **解消** | ~~28~~ → 0 | `CASEBaseSchema` に整数値の float を int として emit する serializer を追加 |
| ~~D. CFDocument に CFPackageURI 欠落~~ | **解消** | ~~1~~ → 0 | `CFPckgDocumentDType` に CFPackageURI を emit するよう変更 |
| ~~E. LinkURI.title の表現差~~ | **受容（仕様適合の差）** | ~~37~~ → 0 | OpenCASE は literal type label、compeito は実 title を emit。CASE v1.1 仕様上どちらも有効。実機テストで OpenCASE が compeito の値を verbatim 保持することを確認したため、何往復しても情報量が減らない。normalize でこの差を無視する |
| ~~F. CFItemURI の denormalized URI 不一致~~ | **解消** | ~~7~~ → 0 | `cf_rubric_criteria.cf_item_uri_source` 列を追加し、source の CFItemURI.uri を verbatim 保存。export 時は被リンク CFItem.uri より優先 |
| ~~G. CFDocument.CFPackageURI.uri 不保持~~ | **解消** | ~~1~~ → 0 | `cf_documents.cf_package_uri_source` 列を追加し、同じパターンで保存。export 時は `_build_cf_package_uri()` で参照 |

合計 0 件。

### ~~A. URI 書き換え~~（概ね解消、残 8 件は F / G に分離）

`case_import_service` に `_resolve_uri(source, tenant_id, identifier)` ヘルパーを導入し、CFPackage import 経由のリソース URI は source の `uri` を優先、無ければ `_build_uri()` で生成、というポリシーに変更。CSV import（`csv_import_service`）はそのまま `_build_uri()` を直叩きするので影響なし。

主要パス（CFDocument / CFItem / CFAssociation / CFRubric / CFRubricCriterion / CFRubricCriterionLevel / CFDefinitions の各 lookup）の URI 書き換えは 262 件解消。残 8 件は **F**（CFRubricCriterion.CFItemURI.uri、7 件）と **G**（CFDocument.CFPackageURI.uri、1 件）に切り出し（後述）。これらは「DB に source の denormalized LinkURI を保存していない」ことに起因し、schema 列追加を伴うため別 PR で対応する。

### ~~B. CFItem に CFDocumentURI が欠落~~（解消済）

`CFPckgItemDType` に `cf_document_uri` フィールドを追加し、`_pckg_item_to_schema()` が CFDocument の LinkURI を埋めるようにした。

### ~~C. CFRubricCriterionLevel の score が int → float に化ける~~（解消済）

`CASEBaseSchema` に `serialize_int_or_float` field_serializer を追加（フィールド `score` / `weight` を対象、`check_fields=False`）。整数値の float（`5.0`）は int（`5`）として emit。CFRubricCriterion の `weight` にも自動適用される。

### ~~D. CFDocument に CFPackageURI が欠落~~（解消済）

`CFPckgDocumentDType` に `cf_package_uri` フィールドを追加し、`_pckg_document_to_schema()` が `_build_cf_package_uri()` で組み立てた LinkURI を埋めるようにした。

### ~~E. LinkURI.title の表現差~~（受容）

OpenCASE は LinkURI の `title` を、リンク種別を示す literal（`"Document"` / `"CFPackage"` 等）として emit する。compeito は実際の被リンクリソースの `title` を emit する。CASE v1.1 仕様上どちらも有効。

**実機テスト結果（2026-06-07）**: OpenCASE Docker 上で `CFDocumentURI.title` / `CFPackageURI.title` に識別可能なマーカー文字列を入れた CFPackage を POST し、GET し直したところ、両 title フィールドとも投入値を verbatim 保持して返ってきた。つまり OpenCASE → compeito → OpenCASE で何往復しても title の情報は失われず、むしろ compeito を経由することで「リンク種別」から「リンク先リソースの実 title」へと情報量が増える。

このため case 仕様上の等価性を踏まえ、round-trip テストの `_normalize` で LinkURI-shape の `title` を無視する扱いとし、compeito の既存挙動（被リンクリソースの実 title を emit）を据え置く。compeito の standalone CFItem / CFAssociation レスポンスに対する Open Badge Factory 等の消費者にとっても情報量が多い方が有用、という UX 判断も併せ。

### ~~F. CFRubricCriterion.CFItemURI.uri が source と一致しない~~（解消済）

`cf_rubric_criteria` テーブルに `cf_item_uri_source TEXT NULL` 列を追加（マイグレーション `0054ee62f823`）。CFPackage import 時に source の `CFItemURI.uri` を verbatim 保存し、export 時はそれを優先、無ければ被リンク CFItem.uri にフォールバック。これで OpenCASE の「denormalized LinkURI を再解決しない」挙動と一致するため、round-trip が壊れない。

### ~~G. CFDocument.CFPackageURI.uri が source と一致しない~~（解消済）

`cf_documents` テーブルに `cf_package_uri_source TEXT NULL` 列を追加（マイグレーション `bfbb97d3805a`）。CFPackage import 時に source の CFPackageURI.uri を verbatim 保存し、`_build_cf_package_uri()` でそれを優先、NULL なら compeito-native URL にフォールバック。cat F と同じパターン。

## 履歴

カテゴリ A〜G を 7 つの PR に分けて潰した（PR #174, #175, #176, #177, #178, #179, #180、および本カテゴリ E）。`test_lossless` は当初 `xfail` で baseline 計測 → 段階的にカテゴリを解消 → 最終的に `strict=True` の通常 pass に flip。

将来 fixture を enrich（OpenCASE で `notes` / `alternativeLabel` / `extensions` 等のフィールドを追加投入、CFAssociation の非 isChildOf type、追加の CFConcept / CFLicense / CFAssociationGrouping）して新たな差分が出たら、同じ手順でカテゴリ追加 → 解消、を繰り返す。

OpenCASE 上でフレームワークをさらに enrich（`conceptKeywordsURI` / `licenseURI` / non-isChildOf associationType / CFConcept / CFLicense / CFAssociationGrouping 等）して fixture を更新したい場合は、enrich 後の CFPackage を `GET /ims/case/v1p1/CFPackages/{id}` で再取得し `tests/fixtures/opencase_round_trip_baseline.json` を差し替える。
