# 公式 OpenAPI スキーマによるレスポンス機械検証テスト 実装方針

> **ステータス: 設計レビュー済み（実装着手可・実装順未定）**
> Codex レビュー 1 ラウンド（技術的前提の実コード検証・仕様間整合・方針整合）＋指摘反映済み（2026-07）。
>
> 目的: CASE API の**実レスポンス（HTTP ボディ）を公式 CASE v1.1 OpenAPI スキーマで機械検証する**
> 結合テストを追加し、適合性ギャップ解消（並行作成中の [strict-output.md](strict-output.md) = C16/C1 等）を
> **回帰から守る検証基盤**を作る。2026-07 適合性監査で「実レスポンスを公式スキーマで機械検証するテストが無い」
> ことが指摘された（[conformance backlog](../case-v1p1-conformance-backlog.md) C13 の実質的な補完でもある）。

## 決定事項

- **権威ソース**: リポジトリ同梱の公式 OpenAPI 3 スキーマ `docs/reference/imscasev1p1_openapi3_v1p0.json`
  （discovery エンドポイントが配信しているのと同一ファイル）をテストから直接ロードして使う。
- **検証ライブラリ**: `openapi-schema-validator`（OAS 3.0 方言対応・jsonschema ベース）。dev 依存に追加。
- **検証対象は strict モード応答**（`?strict=1`）。既定（compat）応答は**意図的に非適合**なので検証対象外。
- **既知ギャップは `xfail(strict=True)`** でマークし、ギャップが直った瞬間に XPASS(strict) で CI が落ちて
  「マーカーを外す」運用を強制する（= ギャップ解消の検出装置を兼ねる）。
- **検証はレスポンスボディのみ**。ページネーションヘッダ（`Link` / `X-Total-Count`）・`Cache-Control` 等の
  HTTP レベルは非対象（既存テストが個別にカバー）。
- **エラー封筒（`imsx_StatusInfoDType`）も検証範囲に含める**（既に適合済みのため xfail 無しで守る）。

## 背景

- 2026-07 にプロジェクトゴールが「OpenSALT v1.0 完全互換」から「**1EdTech CASE v1.1 コンフォーマンステストのパス**」へ
  転換した（[conformance backlog](../case-v1p1-conformance-backlog.md) 冒頭参照）。
- 既存の結合テスト（`tests/integration/test_cf_*.py`）は個別フィールドの値をアサートするが、
  **公式スキーマとの構造適合（`additionalProperties: false`・required・型・enum・pattern・format）を
  機械検証するテストは無い**。C16（optional フィールドの null 出力）のような「全 DType 横断の型違反」は
  個別アサートでは検出できない。
- strict 出力層（C16/C1/C2/C8 出力側）の設計・実装が並行して進む。実装前でも動き、実装後は
  「strict 応答 = 公式スキーマ valid」を恒久的に保証するテストが要る。

## 権威ソースとスキーマ解決

### スキーマファイル

`docs/reference/imscasev1p1_openapi3_v1p0.json`（OpenAPI **3.0.0**、約 163 KB）。
`src/routers/discovery.py` が Service Discovery でこの同じファイルを配信しており、リリースに固定されている。
テストは `Path` でリポジトリ相対に直接ロードする（`discovery._SCHEMA` の import はプライベート属性依存になるので避ける）。

スキーマの検証上の特徴（実ファイルを確認済み）:

- `components/schemas` 内の相互参照はすべて `#/components/schemas/...` の内部 `$ref`。外部参照なし。
- `components/schemas` は全 39 型。**非 Extension の 26 DType が `additionalProperties: false`** — 余計なキー（wrapper、`CFPckg*` 内の URI echo 等）は即違反になる。残り 13 の `*ExtensionDType` は `additionalProperties: true`（自由形）。
- `nullable` は**一切使われていない**（出現 0 件）— optional フィールドの `null` emit は型違反（= C16）。
- `oneOf`/`allOf` なし。`anyOf` は `associationType` / `targetType` の拡張語彙（enum ∪ `ext:` パターン）のみ。
- 使用 format: `date-time`, `date`, `uri`, `float`, `int32`。
- identifier 系は UUID パターン `[0-9a-f]{8}-[0-9a-f]{4}-[1-5]{1}[0-9a-f]{3}-[8-9a-b]{1}[0-9a-f]{3}-[0-9a-f]{12}`
  （**version nibble が 1–5、variant が 8/9/a/b に限定**される点に注意 — シード設計に影響、後述）。
- Set 型（`CFDocumentSetDType` 等）は配列に `minItems: 1`（= 空配列は違反、C4）。

### $ref 解決の方法

ルートスキーマに `components` を埋め込む方式を採る（referencing の Registry 構築より単純で、
内部参照のみの本ケースには十分）:

```python
import json
from pathlib import Path

from openapi_schema_validator import OAS30Validator, oas30_format_checker

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "reference" / "imscasev1p1_openapi3_v1p0.json"
SPEC = json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def assert_conformant(body: dict, schema_name: str) -> None:
    """body を components/schemas/{schema_name} で検証。全違反を列挙して assert。"""
    schema = dict(SPEC["components"]["schemas"][schema_name])  # 浅いコピー（SPEC は変更しない）
    schema["components"] = SPEC["components"]  # "#/components/schemas/..." がルート相対で解決される
    validator = OAS30Validator(schema, format_checker=oas30_format_checker)
    errors = sorted(validator.iter_errors(body), key=lambda e: e.json_path)
    assert not errors, f"{schema_name} violations:\n" + "\n".join(f"  {e.json_path}: {e.message}" for e in errors)
```

- `iter_errors` で**全違反を列挙**する（最初の 1 件で止めない）。C16 のような横断違反のデバッグに必須。
- `openapi-schema-validator` のバージョンによっては validator 生成 API が referencing ベースに変わっている。
  上記の「components 埋め込み」はルートドキュメント相対の `$ref` 解決なのでどのバージョンでも動くが、
  実装時に `uv run pytest tests/integration/test_openapi_conformance.py -k documents` 等で 1 本通して確認すること。

### エンドポイント → スキーマ対応表（公式 OpenAPI の paths から機械抽出・検証済み）

compeito のパスは `/{tenant}/ims/case/v1p1/` プレフィックス付き。200 応答のスキーマは以下の 12 本
（公式 paths と 1:1 対応。compeito 拡張の list エンドポイント（`CFItemTypes` 等の一覧、C10）は公式契約外なので対象外）:

| # | compeito パス（GET） | 公式パス | 200 スキーマ |
|---|---|---|---|
| 1 | `/{tenant}/ims/case/v1p1/CFDocuments` | `/CFDocuments` | `CFDocumentSetDType` |
| 2 | `/{tenant}/ims/case/v1p1/CFDocuments/{id}` | `/CFDocuments/{sourcedId}` | `CFDocumentDType` |
| 3 | `/{tenant}/ims/case/v1p1/CFItems/{id}` | `/CFItems/{sourcedId}` | `CFItemDType` |
| 4 | `/{tenant}/ims/case/v1p1/CFItemAssociations/{id}` | `/CFItemAssociations/{sourcedId}` | `CFAssociationSetDType` |
| 5 | `/{tenant}/ims/case/v1p1/CFAssociations/{id}` | `/CFAssociations/{sourcedId}` | `CFAssociationDType` |
| 6 | `/{tenant}/ims/case/v1p1/CFAssociationGroupings/{id}` | `/CFAssociationGroupings/{sourcedId}` | `CFAssociationGroupingDType` |
| 7 | `/{tenant}/ims/case/v1p1/CFConcepts/{id}` | `/CFConcepts/{sourcedId}` | `CFConceptSetDType` |
| 8 | `/{tenant}/ims/case/v1p1/CFSubjects/{id}` | `/CFSubjects/{sourcedId}` | `CFSubjectSetDType` |
| 9 | `/{tenant}/ims/case/v1p1/CFItemTypes/{id}` | `/CFItemTypes/{sourcedId}` | `CFItemTypeSetDType` |
| 10 | `/{tenant}/ims/case/v1p1/CFLicenses/{id}` | `/CFLicenses/{sourcedId}` | `CFLicenseDType` |
| 11 | `/{tenant}/ims/case/v1p1/CFPackages/{id}` | `/CFPackages/{sourcedId}` | `CFPackageDType` |
| 12 | `/{tenant}/ims/case/v1p1/CFRubrics/{id}` | `/CFRubrics/{sourcedId}` | `CFRubricDType` |

エラー応答（4xx/5xx/default）は全パス共通で `imsx_StatusInfoDType`。

現状の compeito 実装のレスポンス形（gap 判定の根拠、実コード確認済み）:

- #2,3,5,6,10,12 は `{"CFDocument": {...}}` 等の **wrapper 付き**（= C1。`src/routers/cf_*.py`）。
- #1 (`{"CFDocuments": [...]}`), #4 (`{"CFItem": ..., "CFAssociations": [...]}`),
  #7–9（lookup は Set 形 `{"CFConcepts": [...]}` 等）, #11（flat な `CFPackageDType`）は**形は既に公式どおり**。
- #11 のみ `?strict=1` が実装済み（`CFPackageURI` / `CFDocumentURI` の除去 = C2 対応、`src/routers/cf_packages.py`）。
  他エンドポイントでは `?strict=1` は現状**無視される**（未知クエリはエラーにならない）ので、
  strict 実装前からテストは同一 URL で実行でき、strict-output 実装が入った時点で挙動だけが変わる。

## 検証ライブラリの選定

**採用: `openapi-schema-validator`（>= 0.6）** を dev 依存に追加。

理由:

- OpenAPI **3.0 方言**の validator（`OAS30Validator`）を提供する。素の `jsonschema` の Draft 検証と
  OAS 3.0 は方言差がある（`nullable` キーワード、`type` の扱い等）。本スキーマは `nullable` を使っていないが、
  **方言を正しく名乗るライブラリを使うことで将来のスキーマ更新にも安全**。
- `oas30_format_checker` が付属し、`int32` / `float` / `date` / `date-time` 等の format を検証できる
  （`rfc3339-validator` は本ライブラリの依存として入る）。`lastChangeDateTime` は
  `src/schemas/common.py` の serializer が `%Y-%m-%dT%H:%M:%SZ` で emit しており RFC 3339 valid。
- `jsonschema` ベースの薄いラッパーで、`iter_errors` による全違反列挙がそのまま使える。

不採用の代替案:

- **素の `jsonschema`（Draft4Validator）**: 動くが OAS 方言を自前で気にする必要があり、format checker も自前登録になる。
- **`openapi-core`**: リクエスト/レスポンス両方向の検証フレームワークで重い。paths レベルの検証機構は
  本件（テナントプレフィックス付きパスと公式 paths の突合）にそのまま使えず、components 単位の検証で十分。

`pyproject.toml` の変更:

```toml
[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "ruff>=0.9",
    "openapi-schema-validator>=0.6",   # 追加
]
```

`uv sync` で `uv.lock` が更新される。**CI は `uv sync --frozen` なので `uv.lock` を同一 PR でコミットすること**。

補足: `uri` format は `oas30_format_checker` に含まれず（`rfc3987` 依存を避ける）、jsonschema は
未登録 format を**黙ってスキップ**する。URI の書式検証はしない（型・required・pattern・additionalProperties が主眼）。

## テスト構造

新規ファイル: `tests/integration/test_openapi_conformance.py`

### fixture（既存 conftest.py に従う）

既存の `tests/conftest.py` の `db_session` / `db_client` / `tenant` fixture をそのまま使う
（Docker PostgreSQL 前提・テスト後に全テーブル DELETE でクリーンアップ、これは新規テーブル追加が無いので変更不要）。
**conftest の `sample_document`（identifier `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`）は使わない** —
公式スキーマの UUID パターンは version=4/variant=8-b を要求するため、この identifier はパターン違反になる（エッジケース節参照）。

本ファイル内に 2 種類のシード fixture を定義する（ORM モデル直挿入。
`tests/integration/test_cf_packages.py` の `full_package_data` fixture が構築パターンの手本）:

1. **`full_seed`** — 「全 optional フィールドが埋まった」ドキュメント一式。
   - CFDocument: `src/models/cf_document.py` の**全カラム**を埋める（`creator`, `publisher`, `description`,
     `framework_type`, `case_version="1.1"`（公式 enum は `["1.1"]` のみ）, `language`, `version`,
     `adoption_status`, `status_start_date`/`status_end_date`, `official_source_url`, `subject`, `subject_uri`,
     `notes`, `extensions`, license FK, …）。
   - CFItem ×2（親子）: 全 optional（`human_coding_scheme`, `abbreviated_statement`, `concept_keywords`,
     `education_level`, `language`, `license_uri`, `status_start_date`/`end_date`, `alternative_label`, `notes`,
     `extensions`, item type / concept / subject への参照）を埋める。
   - CFAssociation: `isChildOf`（origin/destination の identifier・uri・**title**・target_type を全部埋める —
     `LinkGenURIDType.title` は required なので C3 を踏まないため）+ `ext:` 型 1 本（anyOf の第 2 枝を通す）+
     grouping 参照付き 1 本。`sequence_number`, `notes`, `extensions` も埋める。
   - CFItemType / CFConcept / CFSubject: **`hierarchy_code` と `description`（ItemType）を必ず埋める**（C3 回避）。
     lookup Set 応答は「指定リソース + hierarchyCode 上の子孫」なので、hierarchyCode で親子になる 2 件ずつ入れると
     Set の複数要素も検証できる。
   - CFLicense: `license_text` を埋める（C3 回避）。
   - CFAssociationGrouping / CFRubric（criterion / criterion level 各 2 件、float の `weight`・`score` 等も埋める）。
   - **identifier はすべて `uuid.uuid4()` か、手書きなら `xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx` 形**にする。
2. **`minimal_seed`** — NOT NULL カラムのみのドキュメント一式（optional は全部 NULL）。
   CFDocument（creator 無し）+ CFItem 1 件 + isChildOf 1 本（origin/destination title 無し）+
   CFItemType / CFConcept / CFSubject / CFLicense 各 1 件（hierarchyCode / description / licenseText 無し）+
   grouping / rubric（criteria 0 件）。null emit（C16）と required-but-null（C3）を最も強く踏む側。

fixture は pytest の通常スコープ（テストごと）なので、`full_seed` だけを要求したテストの DB には
minimal 側のデータは存在しない（`GET /CFDocuments` の件数・内容が fixture 選択で決まる）。

### テスト本体

エンドポイント 12 本 × シード 2 種を dataclass + `pytest.param` でパラメトライズする:

```python
@dataclass(frozen=True)
class EndpointCase:
    name: str                 # テスト ID（gap 対応表のキー）
    path_template: str        # "/{tenant}/ims/case/v1p1/CFItems/{id}" 等
    schema: str               # components/schemas のキー
    gaps: tuple[str, ...]     # 既知ギャップ ID（空なら xfail なし）

GAP_REASONS = {
    "C1": "single-resource wrapper（公式は flat DType）",
    "C3": "required だが null なフィールド（creator/hierarchyCode/description/licenseText/LinkGenURI.title）",
    "C4": "Set 型の minItems:1 と空配列",
    "C16": "optional フィールドの null 出力（exclude_none 未適用）",
}

def _param(case: EndpointCase):
    marks = [pytest.mark.conformance]
    if case.gaps:
        reason = "; ".join(f"{g}: {GAP_REASONS[g]}" for g in case.gaps)
        marks.append(pytest.mark.xfail(strict=True, reason=f"known conformance gaps — {reason}"))
    return pytest.param(case, id=case.name, marks=marks)
```

テスト関数は 2 本（+ エラー封筒 + エッジ）:

```python
@pytest.mark.parametrize("case", [_param(c) for c in FULL_CASES])
async def test_strict_response_conforms_full(db_client, full_seed, case):
    resp = await db_client.get(case.render_path(...), params={"strict": "1"})
    assert resp.status_code == 200
    assert_conformant(resp.json(), case.schema)
```

- **リクエストは全エンドポイントで `?strict=1` を付ける**（#11 以外は現状 no-op。strict-output 実装後に
  そのまま strict 応答の検証になる。strict-output 側がクエリ名/値を変える場合はここを追随）。
- アサートは「HTTP 200」+「ボディがスキーマ valid」のみ。**値の正しさは既存テストの責務**であり重複させない。
- `pytest.ini_options` に marker 登録を追加（`-m conformance` で単独実行できるように）:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = ["conformance: official CASE v1.1 OpenAPI schema validation tests"]
```

### エラー封筒（imsx_StatusInfoDType）の検証 — xfail なし

エラー封筒は適合済み（backlog「すでに対応済み」）。`imsx_codeMinorFieldValue` の公式 enum に
`invalid_uuid` / `unknownobject` / `invalid_selection_field` / `invalid_sort_field` / `internal_server_error` が
含まれることは確認済み。以下を `imsx_StatusInfoDType` で検証する（シード不要、`tenant` fixture のみ）:

- 404: 存在しない sourcedId — 12 エンドポイント全部をパラメトライズ（安い）。
- 400: 不正 UUID（`/CFItems/not-a-uuid` 等の代表 1 本）。
- 400: `GET /CFDocuments?sort=unknown`（`invalid_sort_field`）と `?limit=-1`（`invalid_selection_field`）。
- 404: 未定義サブパス `/{tenant}/ims/case/v1p1/NoSuchResource`（旧 C14 のグローバルハンドラ経由）。

### discovery ドリフトガード（小物・任意だが推奨）

`GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json` の応答 JSON が
テストがロードした `SPEC` と等価（`==`）であることを 1 本アサートする。
「テストが検証している権威ソース」と「クライアントに配信している契約」の乖離を防ぐ。

> **C18 との関係。** §2.5 は localized version の提供を要求しており（適合性バックログ C18）、これを実装すると応答は `SPEC` と等価でなくなる。C18 着手時にこのアサートを、localize 後の期待値との比較か、localize 対象フィールド（`servers`・`info.contact` 等）を除いた比較に変更する。

## 既知ギャップの扱い（xfail 機構と対応表）

- **`pytest.mark.xfail(strict=True, reason=...)`** を使う。`strict=True` により、
  ギャップが解消されてテストが通るようになった瞬間 **XPASS(strict) で CI が fail** し、
  「対応表から gap ID を消してマーカーを外す（= 以後は通常のパステストとして回帰を守る）」作業が強制される。
- 1 テストに複数 gap がぶら下がる場合、**全部直るまで xfail のまま**（部分修正では flip しない）。
  gap 単位の進捗は backlog 側で管理し、この表はテストの期待状態だけを持つ。
- 実装時は着手時点の実挙動で下表を検証し、ズレていれば表を実態に合わせて直すこと
  （本設計は 2026-07 時点・strict-output 未実装の実コード読解に基づく）。

### テスト ID ↔ 既知ギャップ対応表（strict-output 実装前の初期値）

`full` シード側（C3 を踏まないようデータで回避しているため、strict-output（C16+C1）が入れば全て XPASS になる想定）:

| テスト ID（full） | スキーマ | gaps | 根拠 |
|---|---|---|---|
| CFDocuments | CFDocumentSetDType | C16 | 形は Set どおり。null emit のみ |
| CFDocuments/{id} | CFDocumentDType | C1, C16 | `{"CFDocument": ...}` wrapper + null |
| CFItems/{id} | CFItemDType | C1, C16 | wrapper + null |
| CFItemAssociations/{id} | CFAssociationSetDType | C16 | 形は `{CFItem, CFAssociations}` で公式どおり |
| CFAssociations/{id} | CFAssociationDType | C1, C16 | wrapper + null |
| CFAssociationGroupings/{id} | CFAssociationGroupingDType | C1, C16 | wrapper + null |
| CFConcepts/{id} | CFConceptSetDType | C16 | lookup は Set 形で公式どおり |
| CFSubjects/{id} | CFSubjectSetDType | C16 | 同上 |
| CFItemTypes/{id} | CFItemTypeSetDType | C16 | 同上 |
| CFLicenses/{id} | CFLicenseDType | C1, C16 | wrapper + null |
| CFPackages/{id} | CFPackageDType | C16 | `?strict=1` で C2 は除去済み。null のみ残る |
| CFRubrics/{id} | CFRubricDType | C1, C16 | wrapper + null |

`minimal` シード側（上表の gaps に加えて、該当エンドポイントに **C3** を追加。
strict-output（C16 = exclude_none）実装後は null が消える代わりに required 欠落として C3 違反が残るため、
**import 時の validation report（採用済み方針 — designs/import-dry-run-and-ai-guide.md で設計）で欠落が検出され、データが補完されるまで xfail が続く**のが期待状態）:

| テスト ID（minimal） | 追加 gap | C3 の violating フィールド |
|---|---|---|
| CFDocuments | C3 | `creator`（required） |
| CFDocuments/{id} | C3 | 同上 |
| CFItems/{id} | —（C1, C16 のみ） | CFItem の required（fullStatement/uri/lastChangeDateTime/CFDocumentURI）は常に emit される |
| CFItemAssociations/{id} | C3 | origin/destination `LinkGenURIDType.title` |
| CFAssociations/{id} | C3 | 同上 |
| CFAssociationGroupings/{id} | — | required は identifier/uri/title/lastChangeDateTime のみで常在 |
| CFConcepts/{id} | C3 | `hierarchyCode`（required） |
| CFSubjects/{id} | C3 | `hierarchyCode`（required） |
| CFItemTypes/{id} | C3 | `description` / `hierarchyCode`（required） |
| CFLicenses/{id} | C3 | `licenseText`（required） |
| CFPackages/{id} | C3 | 内包する CFDocument の `creator` ほか |
| CFRubrics/{id} | — | CFRubricDType の required は identifier / uri / lastChangeDateTime（lastChangeDateTime の充足は実装時にシードで確認） |

C2 は `?strict=1` で解消済みのため初期値の表に**登場しない**（strict の除去ロジックが壊れたら
CFPackages テストが additionalProperties 違反で fail する = 回帰検出になる）。
C8（caseVersion）は full シードが `"1.1"` を持つため full 側では踏まず、minimal 側は null → C16 に包含される。
`"1.0"` 等を持つデータの strict 時挙動は strict-output 設計の決定事項なので本テストでは扱わない（非対象）。

## compat モード（既定応答）の扱い

既定（compat）応答は wrapper・URI echo・null emit を**意図的に**含む OpenSALT 互換出力であり、
公式スキーマに適合しないことが仕様である。よって**スキーマ検証の対象外**とする
（xfail で網羅する案は、意図的非適合を「いつか直るもの」と誤provisionするノイズになるため不採用）。
compat 応答の形・値の回帰は既存の `tests/integration/test_cf_*.py` が引き続き守る。
将来「既定の strict 反転」（backlog の段取り 2 段階目）が実施されたら、本テストの `?strict=1` を
外す/パラメトライズする改修を backlog 化する（そのときの旧 compat は `?compat=1` 側の別枠）。

## 変更するファイル

| ファイル | 変更内容 |
|---|---|
| `tests/integration/test_openapi_conformance.py` | **新規**。SPEC ロード + `assert_conformant` ヘルパ、`EndpointCase` / gap 対応表、`full_seed` / `minimal_seed` fixture、strict 応答検証 ×12×2、エラー封筒検証、discovery ドリフトガード |
| `pyproject.toml` | dev 依存に `openapi-schema-validator>=0.6` 追加、`[tool.pytest.ini_options]` に `markers = ["conformance: ..."]` 追加 |
| `uv.lock` | `uv sync` の結果をコミット（CI は `--frozen`） |
| `docs/dev/case-v1p1-conformance-backlog.md` | C13 行または方針メモに「実レスポンスの機械検証テスト（test_openapi_conformance.py）が xfail 対応表でギャップを追跡している」旨と、ギャップ解消時に xfail を外す運用を 1–2 行追記 |

他のファイル（src/ 配下・conftest.py・CI 定義）は**変更しない**。

## 考慮すべきエッジケース

- **UUID パターンの罠（must）**: 公式パターンは version nibble `[1-5]`・variant `[8-9a-b]` を要求する。
  conftest の `sample_document`（`aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`）や既存テストの
  `11111111-aaaa-...` 系の手書き identifier は**パターン違反**になる。本テストのシードは
  `uuid.uuid4()` を使う（決定的にしたい場合は `xxxxxxxx-xxxx-4xxx-8xxx-...` 形の固定値）。
  なお jsonschema の `pattern` は**非アンカー（部分一致）**なので、パターンを満たす部分文字列があれば通る点も
  頭に入れておく（過信しない。identifier の値検証は本テストの主目的ではない）。
- **空 Set と `minItems:1`（C4）**: CFItem/CFAssociation が 0 件のドキュメントに対する
  `GET /CFDocuments`（テナントに doc 0 件）や `GET /CFItemAssociations/{id}`（関連 0 件）は
  `[]` を返しスキーマ違反になる。**専用のエッジテストを 1–2 本だけ**用意し `xfail(strict=True, reason="C4")` を付ける
  （C4 は「据え置き」判断もあり得る P2。据え置き決定時はテストを「違反のままが仕様」を明示する形に書き換える）。
  通常の 12×2 マトリクスのシードは**必ず 1 件以上**入れて C4 を踏まないようにする。
- **`ext:` associationType**: anyOf の第 2 枝（`(ext:)[a-zA-Z0-9\.\-_]+`）を full シードで 1 本通す。
  import 側の文字種検証（旧 C12）が守っている前提を出力側でも確認できる。
- **CFPackage の rubric/definitions**: `CFPackageDType` の required は `CFDocument` のみだが、
  compeito は `CFItems`/`CFAssociations` を常に emit する（スキーマ上 optional なので違反ではない）。
  full シードに rubric・definitions（itemType/concept/subject/license/grouping）を含め、
  `CFDefinitionDType` / `CFPckg*DType` の枝も検証が通ることを確認する。
- **date/datetime の format**: serializer は `...Z`（datetime）/ `YYYY-MM-DD`（date）で emit しており
  RFC 3339 valid。`oas30_format_checker` の date-time 検証はこの前提の回帰ガードになる。
- **`extensions`**: `CF*ExtensionDType` は自由形（additionalProperties 制約なし）。full シードの extensions は
  ネスト dict を入れて通ることだけ確認（深い検証は不要）。
- **SPEC dict の共有**: モジュールレベルでロードした `SPEC` は読み取り専用として扱い、
  `assert_conformant` 内では浅いコピーにのみキーを足す（テスト間の汚染防止）。
- **strict クエリの表記**: `src/routers/cf_packages.py` の truthy 集合は `{"1","true","yes","on"}`。
  テストは `strict=1` に統一する（strict-output 実装も同じ規約を踏襲する想定）。

## CI

追加の CI 変更は**不要**であることを確認済み:

- `.github/workflows/ci.yml` の test ジョブは `docker compose up -d db` → `uv sync --frozen` →
  `alembic upgrade head` → `uv run pytest tests/ -v`。本テストは `tests/integration/` に置くだけで実行される。
- 新規テーブル・マイグレーション・環境変数なし。DB は既存スキーマのまま。
- 依存追加は `uv.lock` 更新のコミットで `--frozen` と整合。
- lint ジョブ（ruff check / format）対象に `tests/` が含まれるため、新規ファイルも
  `uv run ruff format` を通してからコミットする。
- xfail はテスト結果上 `XFAIL` として成功扱い、`XPASS(strict)` は失敗扱い — 追加設定不要で
  「ギャップ解消の検出」が CI 上で機能する。

## 将来: 1EdTech 公式 conformance テストハーネスとの関係

本テストは**社内回帰用**であり、1EdTech の公式 conformance テスト（certification）の**代替ではない**:

- 公式ハーネスは実際の HTTP サーバーに対して Service Discovery（compeito は
  `GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json` 実装済み）経由でエンドポイントを叩き、
  スキーマ以外（HTTP セマンティクス・エラーコード・クエリパラメータ挙動等）も含めて判定する。
- 本テストが全緑（xfail が全部外れた状態）になることは「公式テストに挑める前提条件」であって十分条件ではない。
  certification 実施時の段取り・残項目は [conformance backlog](../case-v1p1-conformance-backlog.md) で管理する。
- 公式スキーマファイルが 1EdTech 側で改版された場合は `docs/reference/` の同ファイルを更新すれば
  本テストは自動で新契約に追随する（discovery ドリフトガードが配信側との整合も守る）。

## 非対象（今回やらないこと）

- **strict 出力層そのものの実装**（C16/C1/C8 出力側）— 並行の [strict-output.md](strict-output.md) の範囲。
  本テストは実装前は xfail、実装後は回帰ガードとして機能する。
- **既定（compat）応答のスキーマ検証**（意図的非適合のため。上記「compat モードの扱い」参照）。
- **HTTP レベルの検証**: `Link` / `X-Total-Count` / `Cache-Control` ヘッダ、ステータスコードの網羅、
  content negotiation。既存テストと backlog（C5 済み等）の範囲。
- **クエリパラメータ挙動の適合検証**（sort/orderBy/filter/fields/limit/offset の意味論、C6/C7/C9）。
  本テストではエラー封筒の形だけ見る。
- **リクエスト側（import）の検証**、CSV/Excel 経路、Web UI。
- **公式ハーネスの実行・certification 手続き**（将来の別項目）。
- **値の正しさのアサート**（フィールド値・件数・順序）— 既存の `test_cf_*.py` の責務。
