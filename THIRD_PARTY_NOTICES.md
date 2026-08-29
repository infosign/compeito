# Third-party notices

*English | [日本語](#サードパーティ表記)*

COMPEITO is licensed under the [Apache License 2.0](LICENSE). That license covers
the code and documentation written for this project. It does **not** cover the
third-party material listed below. Some of it is redistributed as part of this
repository under its own terms; the rest is acknowledged because it is used at
build time or referenced in documentation. Each section says which applies.
Copyright in each item remains with its owner.

Dependencies that are merely installed from a package registry are not listed
here; see `pyproject.toml` and `uv.lock` and the license metadata of each
package.

## 1EdTech — CASE v1.1 OpenAPI definition

| | |
|---|---|
| File | `docs/reference/imscasev1p1_openapi3_v1p0.json` |
| Source | https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/imscasev1p1_openapi3_v1p0.json |
| SHA-256 | `40f183b6ca3ce4979e4908d4414b9d099dd22493bea45694b60e7a72a19a22bf` |
| Verified against upstream | 2026-07-28 (byte-identical) |
| Terms | [1EdTech specification license](https://www.1edtech.org/standards/specification-license) |

> © 2025 1EdTech™ Consortium, Inc. All Rights Reserved.

This is the copyright legend given in the IPR and Distribution Notice of the CASE
v1.1 specification. Legal and trademark information:
https://www.1edtech.org/about/legal

This is an unmodified, verbatim copy. The file's own `info.license` and
`info.contact` metadata are preserved as published.

**Why it is here.** The CASE v1.1 REST/JSON Binding, §2.5 Service Discovery,
requires a Service Provider to *provide a localized version of the OpenAPI file
at a prescribed endpoint* in order to enable service discovery. COMPEITO
implements that endpoint (`GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json`,
see `src/routers/discovery.py`) and this file is the upstream artifact it serves
from.

Two things this does **not** claim. The specification does not require anyone to
place the file in a public source repository; that is our packaging choice.
And the copy shipped here is not yet localized — its `servers` block is still the
published template — so COMPEITO does not currently meet §2.5 in full. That gap
is tracked as item C18 in
[docs/dev/case-v1p1-conformance-backlog.md](docs/dev/case-v1p1-conformance-backlog.md),
separately from this notice.

**No local mirror of the specification.** The 1EdTech specification license
itself grants no right to create modifications or derivatives of their documents,
and their guidance requires a separate agreement with 1EdTech before publishing or
commercially distributing a derived document. Accordingly this repository
keeps no comprehensive local mirror or restatement of the CASE specification, and
`docs/reference/` links to the official documents instead.

Documents such as `docs/spec/case-overview.md`, `docs/spec/data-model-overview.md`
and `docs/spec/api-spec.md` do describe CASE concepts, but their purpose is to
record what COMPEITO implements and how it differs from the specification. They
cite the official documents rather than substituting for them.

## Contributor Covenant — Code of Conduct

| | |
|---|---|
| File | `CODE_OF_CONDUCT.md` |
| Source | https://www.contributor-covenant.org/version/2/1/code_of_conduct/ |
| Terms | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

`CODE_OF_CONDUCT.md` is adapted from the Contributor Covenant, version 2.1.
It is an abridged rendering in English and Japanese, with this project's own
reporting contact substituted; the four-step enforcement ladder is not
reproduced and is instead linked.

## htmx

| | |
|---|---|
| Files | `src/static/vendor/htmx-2.0.4.min.js` |
| Version | 2.0.4 |
| Source | https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js |
| Terms | Zero-Clause BSD (0BSD) — full text in `src/static/vendor/htmx-2.0.4.LICENSE.txt` |

## Quicksand (font)

| | |
|---|---|
| Files | `src/static/fonts/quicksand-700.woff2` |
| Version | v37, latin subset, weight 700 |
| Source | Google Fonts |
| Terms | SIL Open Font License 1.1 — full text in `src/static/fonts/Quicksand-OFL.txt` |

Embedded unmodified. The reserved font name "Quicksand" is not used for any
modified version.

See `src/static/vendor/README.md` for why these two assets are self-hosted.

## Build-time tools (not redistributed in this repository)

These are downloaded when the container image is built and are therefore present
in the resulting image, but their source is not vendored here.

| Tool | Terms | Where |
|------|-------|-------|
| [uv](https://github.com/astral-sh/uv) | dual-licensed MIT or Apache-2.0; we rely on the MIT option | `Dockerfile` (`ghcr.io/astral-sh/uv`) |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) standalone CLI | MIT | `Dockerfile` (release binary) |

Both binaries remain in the built image. MIT requires the copyright and
permission notice to travel with copies, so **before any container image is
published**, the two license texts must be included in the image and the
versions pinned (`uv:latest` is currently unpinned). This is a tracked follow-up;
it does not affect source-only distribution of this repository.

## Interoperability targets referenced in documentation

No code or content from these projects is redistributed here. They are named
because COMPEITO interoperates with them, and their observable behavior is
documented for that purpose.

| Project | Terms | Where referenced |
|---------|-------|------------------|
| [OpenSALT](https://github.com/opensalt/opensalt) | MIT | `docs/reference/opensalt-csv-format.md` — notes on its CSV/Excel format, written from reading its source |
| [OpenCASE](https://github.com/1EdTech/OpenCASE) | Apache-2.0 | `docs/guide/opencase-interop.md`, round-trip test fixtures generated by exporting from a local OpenCASE instance |

---

# サードパーティ表記

*[English](#third-party-notices) | 日本語*

COMPEITO のライセンスは [Apache License 2.0](LICENSE)。これは本プロジェクトのために
書かれたコードとドキュメントに適用される。以下に挙げる第三者素材は**対象外**であり、
一部は各自の条項のもとで本リポジトリの一部として再配布しており、残りはビルド時に使用しているか
ドキュメントで言及しているために記載している。どちらに当たるかは各節に記す。
著作権は各権利者に帰属する。

パッケージレジストリから取得するだけの依存関係はここに挙げない（`pyproject.toml`、
`uv.lock`、および各パッケージのライセンス情報を参照）。

## 1EdTech — CASE v1.1 OpenAPI 定義

| | |
|---|---|
| ファイル | `docs/reference/imscasev1p1_openapi3_v1p0.json` |
| 取得元 | https://purl.imsglobal.org/spec/case/v1p1/schema/openapi/imscasev1p1_openapi3_v1p0.json |
| SHA-256 | `40f183b6ca3ce4979e4908d4414b9d099dd22493bea45694b60e7a72a19a22bf` |
| 上流との照合 | 2026-07-28（バイト単位で一致） |
| 条項 | [1EdTech specification license](https://www.1edtech.org/standards/specification-license) |

> © 2025 1EdTech™ Consortium, Inc. All Rights Reserved.

これは CASE v1.1 仕様の IPR and Distribution Notice に記載されている copyright legend。
法務・商標に関する情報: https://www.1edtech.org/about/legal

無改変の逐語コピー。ファイル自身が持つ `info.license` と `info.contact` は公開時のまま保持している。

**ここに置いてある理由。** CASE v1.1 REST/JSON Binding の §2.5 Service Discovery は、
service discovery を可能にするため、Service Provider が*所定のエンドポイントで
localized version の OpenAPI ファイルを提供すること*を要求している。COMPEITO は
そのエンドポイント（`GET /ims/case/v1p1/discovery/imscasev1p1_openapi3_v1p0.json`、
実装は `src/routers/discovery.py`）を実装しており、このファイルはその配信元となる上流成果物である。

主張していないことが 2 つある。仕様は公開ソースリポジトリへのファイル配置を
誰にも要求していない。それは当方のパッケージングの選択である。また同梱しているコピーは
まだ localize されておらず（`servers` が公開時のテンプレートのまま）、現状 §2.5 を
完全には満たしていない。このギャップは本表記とは別に、[docs/dev/case-v1p1-conformance-backlog.md](docs/dev/case-v1p1-conformance-backlog.md) の C18 として管理している。

**仕様のローカルミラーは置かない。** 1EdTech の specification license 自体は文書の改変・派生物を
作る権利を付与しておらず、同団体のガイダンスは派生文書の公開・商用配布に先立って
1EdTech との別途の合意を求めている。よって本リポジトリは CASE 仕様の
網羅的なローカルミラーや再構成を持たず、`docs/reference/` は公式文書へのリンクに留める。

`docs/spec/case-overview.md`、`docs/spec/data-model-overview.md`、`docs/spec/api-spec.md` は
CASE の概念に言及しているが、その目的は COMPEITO が何を実装し仕様とどう異なるかを
記録することである。公式文書を代替するものではなく、公式文書を参照する位置づけである。

## Contributor Covenant — 行動規範

| | |
|---|---|
| ファイル | `CODE_OF_CONDUCT.md` |
| 取得元 | https://www.contributor-covenant.org/ja/version/2/1/code_of_conduct/ |
| 条項 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.ja) |

`CODE_OF_CONDUCT.md` は Contributor Covenant バージョン 2.1 を翻案したもの。
英日の抄録であり、報告先を本プロジェクトのものに差し替えている。
4 段階の対応はしごは収録せず、リンクで示している。

## htmx

| | |
|---|---|
| ファイル | `src/static/vendor/htmx-2.0.4.min.js` |
| バージョン | 2.0.4 |
| 取得元 | https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js |
| 条項 | Zero-Clause BSD (0BSD) — 全文は `src/static/vendor/htmx-2.0.4.LICENSE.txt` |

## Quicksand（フォント）

| | |
|---|---|
| ファイル | `src/static/fonts/quicksand-700.woff2` |
| バージョン | v37、latin サブセット、weight 700 |
| 取得元 | Google Fonts |
| 条項 | SIL Open Font License 1.1 — 全文は `src/static/fonts/Quicksand-OFL.txt` |

無改変で埋め込んでいる。予約名 "Quicksand" を改変版に使用していない。

この 2 件をセルフホストしている理由は `src/static/vendor/README.md` を参照。

## ビルド時ツール（本リポジトリでは再配布していない）

コンテナイメージのビルド時に取得されるため成果物イメージには含まれるが、
ソースを本リポジトリに同梱してはいない。

| ツール | 条項 | 場所 |
|-------|------|------|
| [uv](https://github.com/astral-sh/uv) | MIT / Apache-2.0 のデュアルライセンス。当方は MIT を選択 | `Dockerfile`（`ghcr.io/astral-sh/uv`） |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) standalone CLI | MIT | `Dockerfile`（リリースバイナリ） |

どちらのバイナリもビルド後のイメージに残る。MIT は複製に著作権表示と許諾表示を
同伴させることを求めるため、**コンテナイメージを公開する前に**この 2 つのライセンス本文を
イメージに含め、版を固定する必要がある（`uv:latest` は現在未固定）。これは後続対応として
管理しており、本リポジトリのソース配布には影響しない。

## ドキュメントで言及している相互運用先

これらのプロジェクトのコードやコンテンツは再配布していない。COMPEITO が相互運用する
対象として名前を挙げ、その目的のために観測可能な挙動を記録している。

| プロジェクト | 条項 | 言及箇所 |
|------------|------|---------|
| [OpenSALT](https://github.com/opensalt/opensalt) | MIT | `docs/reference/opensalt-csv-format.md` — ソースを読んで記録した CSV / Excel 形式の調査記録 |
| [OpenCASE](https://github.com/1EdTech/OpenCASE) | Apache-2.0 | `docs/guide/opencase-interop.md`、ローカルの OpenCASE インスタンスからエクスポートして生成した round-trip テストフィクスチャ |

