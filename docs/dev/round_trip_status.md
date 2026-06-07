# OpenCASE round-trip status

このドキュメントは「OpenCASE → compeito → OpenCASE で 100% 再現できる」目標に対する現在の compeito 側のギャップを記録する。テストは [tests/integration/test_round_trip.py](../../tests/integration/test_round_trip.py)、fixture は [tests/fixtures/opencase_round_trip_baseline.json](../../tests/fixtures/opencase_round_trip_baseline.json)。

## 受け入れ条件

`tests/integration/test_round_trip.py::TestOpenCaseRoundTrip::test_lossless` が `strict=True` の通常 pass になること（現在 `strict=False` の xfail）。

## diff 正規化ルール（round-trip 違反として数えないもの）

- リストの順序（`identifier` でソートして比較）
- `null` ≡ missing key（CASE v1.1 仕様上等価。compeito は FR-2.10 で null を emit、OpenCASE は省略）
- `[]` ≡ missing key（同上。compeito は FR-2.3 で `CFDefinitions` のサブ配列を空時に省略、OpenCASE は `[]` を emit）
- `lastChangeDateTime` は無視（compeito は import 時にタイムスタンプを打ち直す。元タイムスタンプ保持は FR-7.2 系の別作業）

## ギャップカタログ（最新）

`tests/fixtures/opencase_round_trip_baseline.json`（OpenCASE から export したテスト用フレームワーク、36 CFItems / 36 CFAssociations / 2 CFRubrics）を流して計測した。

| カテゴリ | 状態 | 件数 | 内容 |
|---------|------|------|------|
| ~~A. URI 書き換え~~ | **概ね解消** | ~~270~~ → 8 | CFPackage import が source URI を保持するよう `_resolve_uri()` を導入。残 8 件はカテゴリ F / G の denormalized LinkURI 系（schema 追加が必要）に分離 |
| ~~B. CFItem に CFDocumentURI 欠落~~ | **解消** | ~~36~~ → 0 | `CFPckgItemDType` に CFDocumentURI を emit するよう変更 |
| ~~C. score が int → float~~ | **解消** | ~~28~~ → 0 | `CASEBaseSchema` に整数値の float を int として emit する serializer を追加 |
| ~~D. CFDocument に CFPackageURI 欠落~~ | **解消** | ~~1~~ → 0 | `CFPckgDocumentDType` に CFPackageURI を emit するよう変更 |
| E. LinkURI.title の表現差 | 未対応 | 37 | OpenCASE は literal type label（`"Document"` / `"CFPackage"`）を emit、compeito は実際の title を emit |
| ~~F. CFItemURI の denormalized URI 不一致~~ | **解消** | ~~7~~ → 0 | `cf_rubric_criteria.cf_item_uri_source` 列を追加し、source の CFItemURI.uri を verbatim 保存。export 時は被リンク CFItem.uri より優先 |
| G. CFDocument.CFPackageURI.uri 不保持 | 未対応 | 1 | CFPackage import 時に source の CFPackageURI.uri を捨てている（compeito 側で BASE_URL から組み立て直す） |

合計 38 件。

### ~~A. URI 書き換え~~（概ね解消、残 8 件は F / G に分離）

`case_import_service` に `_resolve_uri(source, tenant_id, identifier)` ヘルパーを導入し、CFPackage import 経由のリソース URI は source の `uri` を優先、無ければ `_build_uri()` で生成、というポリシーに変更。CSV import（`csv_import_service`）はそのまま `_build_uri()` を直叩きするので影響なし。

主要パス（CFDocument / CFItem / CFAssociation / CFRubric / CFRubricCriterion / CFRubricCriterionLevel / CFDefinitions の各 lookup）の URI 書き換えは 262 件解消。残 8 件は **F**（CFRubricCriterion.CFItemURI.uri、7 件）と **G**（CFDocument.CFPackageURI.uri、1 件）に切り出し（後述）。これらは「DB に source の denormalized LinkURI を保存していない」ことに起因し、schema 列追加を伴うため別 PR で対応する。

### ~~B. CFItem に CFDocumentURI が欠落~~（解消済）

`CFPckgItemDType` に `cf_document_uri` フィールドを追加し、`_pckg_item_to_schema()` が CFDocument の LinkURI を埋めるようにした。

### ~~C. CFRubricCriterionLevel の score が int → float に化ける~~（解消済）

`CASEBaseSchema` に `serialize_int_or_float` field_serializer を追加（フィールド `score` / `weight` を対象、`check_fields=False`）。整数値の float（`5.0`）は int（`5`）として emit。CFRubricCriterion の `weight` にも自動適用される。

### ~~D. CFDocument に CFPackageURI が欠落~~（解消済）

`CFPckgDocumentDType` に `cf_package_uri` フィールドを追加し、`_pckg_document_to_schema()` が `_build_cf_package_uri()` で組み立てた LinkURI を埋めるようにした。

### E. LinkURI.title の表現差（37 件、2 パス）

| 件数 | パス |
|------|------|
| 36 | `CFItems[*].CFDocumentURI.title` |
| 1 | `CFDocument.CFPackageURI.title` |

OpenCASE は LinkURI の `title` を、リンク種別を示す literal（`"Document"` / `"CFPackage"` 等）として emit する。compeito は実際の `CFDocument.title`（例: `"OpenCASE Sample Framework"`）を emit する。CASE v1.1 仕様上どちらも有効だが、round-trip では一致しない。

**対応案**: round-trip 優先なら compeito も LinkURI.title を type label（`"Document"`、`"CFPackage"` 等）に揃える。ただし compeito の standalone CFItem / CFAssociation レスポンスにも影響するため、Web UI / 既存テストの互換性を併せて検討する。

### ~~F. CFRubricCriterion.CFItemURI.uri が source と一致しない~~（解消済）

`cf_rubric_criteria` テーブルに `cf_item_uri_source TEXT NULL` 列を追加（マイグレーション `0054ee62f823`）。CFPackage import 時に source の `CFItemURI.uri` を verbatim 保存し、export 時はそれを優先、無ければ被リンク CFItem.uri にフォールバック。これで OpenCASE の「denormalized LinkURI を再解決しない」挙動と一致するため、round-trip が壊れない。

### G. CFDocument.CFPackageURI.uri が source と一致しない（1 件、1 パス）

| 件数 | パス |
|------|------|
| 1 | `CFDocument.CFPackageURI.uri` |

CFPackageURI は compeito 側で `_build_cf_package_uri(tenant_id, doc)` により `{BASE_URL}/{tenant_id}/ims/case/v1p1/CFPackages/{doc.identifier}` で組み立てている。source CFDocument の CFPackageURI.uri を保存していないため、re-export では compeito のホスト/テナント URL が使われ、source とは一致しない。

**対応案**: `cf_documents` テーブルに source の CFPackageURI.uri を保持する列を追加し、export 時はそれを優先、無ければ build。あるいは「compeito ホスト中のリソースの CFPackageURI は compeito 自身が emit すべき canonical」として割り切る判断もあり得る（OpenCASE round-trip 目標とは衝突）。マイグレーション + 移行が必要。

## 作業の進め方

各カテゴリを別 PR で潰す。すべてのカテゴリが片付いたら、`test_lossless` の `xfail` を外す（`strict=True` にすると、不意に diff が増えた時に CI が落ちる）。

OpenCASE 上でフレームワークをさらに enrich（`conceptKeywordsURI` / `licenseURI` / non-isChildOf associationType / CFConcept / CFLicense / CFAssociationGrouping 等）して fixture を更新したい場合は、enrich 後の CFPackage を `GET /ims/case/v1p1/CFPackages/{id}` で再取得し `tests/fixtures/opencase_round_trip_baseline.json` を差し替える。
