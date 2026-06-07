# OpenCASE round-trip status

このドキュメントは「OpenCASE → compeito → OpenCASE で 100% 再現できる」目標に対する現在の compeito 側のギャップを記録する。テストは [tests/integration/test_round_trip.py](../../tests/integration/test_round_trip.py)、fixture は [tests/fixtures/opencase_round_trip_baseline.json](../../tests/fixtures/opencase_round_trip_baseline.json)。

## 受け入れ条件

`tests/integration/test_round_trip.py::TestOpenCaseRoundTrip::test_lossless` が `strict=True` の通常 pass になること（現在 `strict=False` の xfail）。

## diff 正規化ルール（round-trip 違反として数えないもの）

- リストの順序（`identifier` でソートして比較）
- `null` ≡ missing key（CASE v1.1 仕様上等価。compeito は FR-2.10 で null を emit、OpenCASE は省略）
- `[]` ≡ missing key（同上。compeito は FR-2.3 で `CFDefinitions` のサブ配列を空時に省略、OpenCASE は `[]` を emit）
- `lastChangeDateTime` は無視（compeito は import 時にタイムスタンプを打ち直す。元タイムスタンプ保持は FR-7.2 系の別作業）

## 2026-06-07 時点のギャップカタログ

`tests/fixtures/opencase_round_trip_baseline.json`（OpenCASE から export したテスト用フレームワーク、36 CFItems / 36 CFAssociations / 2 CFRubrics）を流すと、**15 カテゴリ・298 件**の差分が出る。

### A. URI 書き換え（233 件、12 カテゴリ）

import 時に外部 URI を `{BASE_URL}/{tenant_id}/uri/{identifier}` で再生成しており、FR-7.2「外部リソースの URI と identifier をそのまま保持する」と矛盾している。`identifier` 自体は保持されているが、`uri` フィールドだけが書き換わる。

該当パス:

| 件数 | パス |
|------|------|
| 36 | `CFAssociations[*].uri` |
| 36 | `CFAssociations[*].originNodeURI.uri` |
| 36 | `CFAssociations[*].destinationNodeURI.uri` |
| 36 | `CFItems[*].uri` |
| 36 | `CFItems[*].CFItemTypeURI.uri` |
| 28 | `CFRubrics[*].CFRubricCriteria[*].CFRubricCriterionLevels[*].uri` |
|  7 | `CFRubrics[*].CFRubricCriteria[*].uri` |
|  7 | `CFRubrics[*].CFRubricCriteria[*].CFItemURI.uri` |
|  5 | `CFDefinitions.CFItemTypes[*].uri` |
|  3 | `CFDefinitions.CFSubjects[*].uri` |
|  2 | `CFRubrics[*].uri` |
|  1 | `CFDocument.uri` |

**対応案**: import 時に source の `uri` 文字列をそのまま DB に保存する（既に `_build_uri()` で再生成しているのを止める）。CSV 経由のインポートでは従来通り `_build_uri()` で生成、CFPackage JSON 経由では入力を尊重する、という分岐が必要。

### B. CFItem に CFDocumentURI が欠落（36 件、1 カテゴリ）

| 件数 | パス |
|------|------|
| 36 | `CFItems[*].CFDocumentURI` |

compeito の `CFPckgItemDType` スキーマが `CFDocumentURI` を emit していない。CASE v1.1 仕様では CFItem の `CFDocumentURI` は所属ドキュメントへの LinkURI で、OpenCASE も emit している。

**対応案**: `src/schemas/cf_package.py`（または該当箇所）の CFPckgItemDType に `CFDocumentURI` フィールドを追加。値は item の親 CFDocument から組み立てる。

### C. CFRubricCriterionLevel の score が int → float に化ける（28 件、1 カテゴリ）

| 件数 | パス |
|------|------|
| 28 | `CFRubrics[*].CFRubricCriteria[*].CFRubricCriterionLevels[*].score` |

fixture 側は `5`（int）、compeito 出力は `5.0`（float）。CASE v1.1 OpenAPI 上 `score` は `number`（int/float どちらも有効）だが、型が変わると OpenSALT 等の strict なパーサで取り回しが変わる可能性。

**対応案**: DB に float で保存している score を、API 出力時に元の型を保持するか、整数で表現できる値は int として serialize する。簡単な対応として、入力時の型情報を持たないなら「整数値なら int として emit」というルールにする手もある。

### D. CFDocument に CFPackageURI が欠落（1 件、1 カテゴリ）

| 件数 | パス |
|------|------|
| 1 | `CFDocument.CFPackageURI` |

compeito の CFPackage レスポンスの CFDocument に CFPackageURI フィールドが含まれていない。OpenCASE は emit している。

**対応案**: CFPckgDocumentDType に CFPackageURI を追加（uri は `{BASE_URL}/{tenant}/ims/case/v1p1/CFPackages/{doc.identifier}` で組み立て）。

## 作業の進め方

各カテゴリ（A〜D）を別 PR で潰す。カテゴリ A は影響範囲が広いので慎重に。B / C / D は比較的局所的。すべてのカテゴリが片付いたら、`test_lossless` の `xfail` を外す（`strict=True` にすると、不意に diff が増えた時に CI が落ちる）。

OpenCASE 上でフレームワークをさらに enrich（`conceptKeywordsURI` / `licenseURI` / non-isChildOf associationType / CFConcept / CFLicense / CFAssociationGrouping 等）して fixture を更新したい場合は、enrich 後の CFPackage を `GET /ims/case/v1p1/CFPackages/{id}` で再取得し `tests/fixtures/opencase_round_trip_baseline.json` を差し替える。
