# External references

*English | [日本語](#外部リファレンス)*

This directory holds pointers to third-party specifications and one verbatim
copy of a 1EdTech artifact. It deliberately does **not** mirror or restate the
content of the CASE specification.

## CASE v1.1 (1EdTech) — read the official documents

| Document | URL |
|----------|-----|
| CASE v1.1 specification (entry point) | https://www.imsglobal.org/spec/case/v1p1 |
| Information Model | https://www.imsglobal.org/sites/default/files/spec/case/v1p1/information_model/caseservicev1p1_infomodelv1p0.html |
| REST/JSON Binding | https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html |
| OpenAPI 3 definition (JSON) | https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/ |

Field types, cardinality, endpoint contracts and response shapes are defined
there and only there. When you need the authoritative answer, follow the links
above.

> **Why there is no local mirror.** This directory previously contained two
> Markdown documents that restated the information model and the REST binding in
> tabular form. 1EdTech's terms grant no right to create derivative works from
> their documents, and publishing a derived document requires a separate
> agreement, so those files were removed. See `THIRD_PARTY_NOTICES.md`.

## Files in this directory

| File | What it is |
|------|-----------|
| `imscasev1p1_openapi3_v1p0.json` | Verbatim, unmodified copy of the official 1EdTech OpenAPI definition. Served at the specification's service discovery endpoint. **Not** covered by this project's Apache-2.0 license — see `THIRD_PARTY_NOTICES.md` |
| `opensalt-csv-format.md` | compeito's own investigation notes on OpenSALT's CSV/Excel format, which is not part of any specification |

## Where compeito's own behavior is documented

| Topic | Document |
|-------|----------|
| API surface as implemented, and intentional differences from CASE v1.1 | [docs/spec/api-spec.md](../spec/api-spec.md) |
| Remaining conformance gaps and their priority | [docs/dev/case-v1p1-conformance-backlog.md](../dev/case-v1p1-conformance-backlog.md) |
| Data model as implemented | [docs/spec/data-model-overview.md](../spec/data-model-overview.md) |
| Database schema | [docs/spec/db-schema.md](../spec/db-schema.md) |

---

# 外部リファレンス

*[English](#external-references) | 日本語*

このディレクトリには、第三者仕様への参照と、1EdTech 成果物の逐語コピー 1 件を置く。
CASE 仕様の内容をミラーしたり再構成したりは**しない**。

## CASE v1.1（1EdTech）— 公式文書を参照する

| 文書 | URL |
|------|-----|
| CASE v1.1 仕様（入口） | https://www.imsglobal.org/spec/case/v1p1 |
| Information Model | https://www.imsglobal.org/sites/default/files/spec/case/v1p1/information_model/caseservicev1p1_infomodelv1p0.html |
| REST/JSON Binding | https://www.imsglobal.org/sites/default/files/spec/case/v1p1/rest_binding/caseservicev1p1_restbindv1p0.html |
| OpenAPI 3 定義（JSON） | https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/ |

フィールドの型・必須性・エンドポイントの契約・レスポンス形は公式文書が唯一の権威。
確実な答えが必要なときは上記を辿る。

> **ローカルミラーを置かない理由。** このディレクトリには以前、情報モデルと REST binding を
> 表形式で再構成した Markdown 2 本があった。1EdTech の条項は文書の派生物を作る権利を
> 付与しておらず、派生文書の公開には別途合意が必要であるため、これらを削除した。
> `THIRD_PARTY_NOTICES.md` を参照。

## このディレクトリのファイル

| ファイル | 内容 |
|---------|------|
| `imscasev1p1_openapi3_v1p0.json` | 公式 1EdTech OpenAPI 定義の無改変の逐語コピー。仕様が定める service discovery エンドポイントで配信している。本プロジェクトの Apache-2.0 の**対象外** — `THIRD_PARTY_NOTICES.md` 参照 |
| `opensalt-csv-format.md` | OpenSALT の CSV / Excel 形式に関する compeito 独自の調査記録（この形式はいかなる仕様にも属さない） |

## compeito 自身の挙動はどこに書いてあるか

| 主題 | 文書 |
|------|------|
| 実装された API と、CASE v1.1 との意図的な差異 | [docs/spec/api-spec.md](../spec/api-spec.md) |
| 残っている適合性ギャップと優先度 | [docs/dev/case-v1p1-conformance-backlog.md](../dev/case-v1p1-conformance-backlog.md) |
| 実装されたデータモデル | [docs/spec/data-model-overview.md](../spec/data-model-overview.md) |
| DB スキーマ | [docs/spec/db-schema.md](../spec/db-schema.md) |
