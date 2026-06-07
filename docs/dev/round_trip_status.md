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
| A. URI 書き換え | 未対応 | 270 | `_build_uri()` で外部 URI を rewrite してしまっている |
| ~~B. CFItem に CFDocumentURI 欠落~~ | **解消** | ~~36~~ → 0 | `CFPckgItemDType` に CFDocumentURI を emit するよう変更 |
| ~~C. score が int → float~~ | **解消** | ~~28~~ → 0 | `CASEBaseSchema` に整数値の float を int として emit する serializer を追加 |
| ~~D. CFDocument に CFPackageURI 欠落~~ | **解消** | ~~1~~ → 0 | `CFPckgDocumentDType` に CFPackageURI を emit するよう変更 |
| E. LinkURI.title の表現差 | 未対応 | 37 | OpenCASE は literal type label（`"Document"` / `"CFPackage"`）を emit、compeito は実際の title を emit |

合計 307 件（カテゴリ A の細目は後述）。

### A. URI 書き換え（270 件、14 パス）

import 時に外部 URI を `{BASE_URL}/{tenant_id}/uri/{identifier}` で再生成しており、FR-7.2「外部リソースの URI と identifier をそのまま保持する」と矛盾している。`identifier` 自体は保持されているが、`uri` フィールドだけが書き換わる。

該当パス:

| 件数 | パス |
|------|------|
| 36 | `CFAssociations[*].uri` |
| 36 | `CFAssociations[*].originNodeURI.uri` |
| 36 | `CFAssociations[*].destinationNodeURI.uri` |
| 36 | `CFItems[*].uri` |
| 36 | `CFItems[*].CFItemTypeURI.uri` |
| 36 | `CFItems[*].CFDocumentURI.uri` |
| 28 | `CFRubrics[*].CFRubricCriteria[*].CFRubricCriterionLevels[*].uri` |
|  7 | `CFRubrics[*].CFRubricCriteria[*].uri` |
|  7 | `CFRubrics[*].CFRubricCriteria[*].CFItemURI.uri` |
|  5 | `CFDefinitions.CFItemTypes[*].uri` |
|  3 | `CFDefinitions.CFSubjects[*].uri` |
|  2 | `CFRubrics[*].uri` |
|  1 | `CFDocument.uri` |
|  1 | `CFDocument.CFPackageURI.uri` |

**対応案**: import 時に source の `uri` 文字列をそのまま DB に保存する（既に `_build_uri()` で再生成しているのを止める）。CSV 経由のインポートでは従来通り `_build_uri()` で生成、CFPackage JSON 経由では入力を尊重する、という分岐が必要。

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

## 作業の進め方

各カテゴリを別 PR で潰す。カテゴリ A は影響範囲が広いので慎重に。すべてのカテゴリが片付いたら、`test_lossless` の `xfail` を外す（`strict=True` にすると、不意に diff が増えた時に CI が落ちる）。

OpenCASE 上でフレームワークをさらに enrich（`conceptKeywordsURI` / `licenseURI` / non-isChildOf associationType / CFConcept / CFLicense / CFAssociationGrouping 等）して fixture を更新したい場合は、enrich 後の CFPackage を `GET /ims/case/v1p1/CFPackages/{id}` で再取得し `tests/fixtures/opencase_round_trip_baseline.json` を差し替える。
