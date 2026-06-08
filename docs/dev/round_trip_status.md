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
| ~~A. URI 書き換え~~ | **解消** | ~~270~~ → 0 | CFPackage import が source URI を保持するよう `_resolve_uri()` を導入（カテゴリ A 単体で 262 件解消。残 8 件は denormalized LinkURI の verbatim 保存が必要な系統で、F / G にて schema 列追加で解決） |
| ~~B. CFItem に CFDocumentURI 欠落~~ | **解消** | ~~36~~ → 0 | `CFPckgItemDType` に CFDocumentURI を emit するよう変更 |
| ~~C. score が int → float~~ | **解消** | ~~28~~ → 0 | `CASEBaseSchema` に整数値の float を int として emit する serializer を追加 |
| ~~D. CFDocument に CFPackageURI 欠落~~ | **解消** | ~~1~~ → 0 | `CFPckgDocumentDType` に CFPackageURI を emit するよう変更 |
| ~~E. LinkURI.title の表現差~~ | **受容（仕様適合の差）** | ~~37~~ → 0 | OpenCASE は literal type label、compeito は実 title を emit。CASE v1.1 仕様上どちらも有効。実機テストで OpenCASE が compeito の値を verbatim 保持することを確認したため、何往復しても情報量が減らない。normalize でこの差を無視する |
| ~~F. CFItemURI の denormalized URI 不一致~~ | **解消** | ~~7~~ → 0 | `cf_rubric_criteria.cf_item_uri_source` 列を追加し、source の CFItemURI.uri を verbatim 保存。export 時は被リンク CFItem.uri より優先 |
| ~~G. CFDocument.CFPackageURI.uri 不保持~~ | **解消** | ~~1~~ → 0 | `cf_documents.cf_package_uri_source` 列を追加し、同じパターンで保存。export 時は `_build_cf_package_uri()` で参照 |

合計 0 件。

### ~~A. URI 書き換え~~（解消）

`case_import_service` に `_resolve_uri(source, tenant_id, identifier)` ヘルパーを導入し、CFPackage import 経由のリソース URI は source の `uri` を優先、無ければ `_build_uri()` で生成、というポリシーに変更。CSV import（`csv_import_service`）はそのまま `_build_uri()` を直叩きするので影響なし。

主要パス（CFDocument / CFItem / CFAssociation / CFRubric / CFRubricCriterion / CFRubricCriterionLevel / CFDefinitions の各 lookup）の URI 書き換え 262 件は本カテゴリで解消。残 8 件は denormalized LinkURI を DB に保存していない系統で、カテゴリ F / G で schema 列を追加して解決済。

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

---

# OpenSALT round-trip（調査結果・方針保留）

OpenCASE round-trip 完了を受け、次は OpenSALT round-trip を同じ playbook で実施しようとした。\
着手にあたり OpenSALT (`opensalt/opensalt` の `develop` ブランチ = 4.0.0-dev) を Docker で起動し、import/export 経路をソースコードで精査したところ、**当初計画の前提「OpenSALT から CSV export してベースラインにする」が成立しないことが判明した**。実装には踏み込まず、まず調査結果を記録する。

## OpenSALT の入出力形式（4.0.0-dev / develop 時点）

| 形式 | Import | Export | 出典 |
|------|--------|--------|------|
| **Excel (.xlsx)** | ✅ 完全 | ✅ 完全 | `core/src/Service/ExcelImport.php` / `ExcelExport.php`、`/salt/excel/import`（POST）/ `/cfdoc/{id}/excel`（GET） |
| **CSV** | △ 限定 | ❌ **未実装** | import: `core/src/Service/GithubImport.php`、`/cf/github/import`（POST）。export: `core/templates/framework/cf_package/export.csv.twig` は中身がプレースホルダ文のみ |
| **CASE JSON** | ✅ | ✅（**v1.0**） | `/salt/case/import`（POST）/ `/cfpackage/doc/{id}.json`。export は `generate-package => 'v1p0'` 固定 |

### 1. OpenSALT は CSV を export できない

`CfPackageController::export` は `_format=csv` を受理するが、レンダリング先の `export.csv.twig` は

```twig
<p>This should export a CSV version of the Competency Framework document. ...</p>
```

というスタブで、CSV を生成しない。よって **計画 step 3「OpenSALT から CSV export → `opensalt_round_trip_baseline.csv`」は実行不能**。

### 2. OpenSALT の本命の完全交換形式は Excel (.xlsx) 3 シート

`ExcelImport` / `ExcelExport` は同一の 3 シート構成で往復する。これが OpenSALT が全フィールドを保持できる唯一の表形式。

- **CF Doc** シート（1 行目ヘッダ・2 行目データ、列 A–P）: `identifier, creator, title, lastChangeDate, officialSourceURL, publisher, description, subject(`\|` 区切り), language, version, adoptionStatus, statusStartDate, statusEndDate, licenseTitle, licenseText, notes`
- **CF Item** シート（列 A–L、データは 2 行目以降）: `identifier, fullStatement, humanCodingScheme, smartLevel, listEnumeration, abbreviatedStatement, conceptKeywords, notes, language, educationLevel, CFItemType, license`。**階層は `smartLevel`（`1` / `1.1` / `1.1.1` …）で表現**し、最終セグメントが親内 sequence。13 列目以降は AdditionalField（custom field）
- **CF Association** シート（列 A–J）: `identifier, originNodeURI, originNodeIdentifier, originNodeHumanCodingScheme, associationType, destinationNodeURI, destinationNodeIdentifier, destinationNodeHumanCodingScheme, associationGroupIdentifier, associationGroupName`。`isChildOf` は CF Item の smartLevel から自動生成されるため、ここでの CHILD_OF 行は重複時スキップ

### 3. OpenSALT の CSV import は限定的で compeito の CSV と非互換

`GithubImport::saveCSVGithubDocument`（`/cf/github/import` の実体）が取り込むのは次のみ:

```
fullStatement(必須), identifier, humanCodingScheme, abbreviatedStatement,
conceptKeywords, language, notes, sequenceNumber, isChildOf,
（association 系）isPartOf, replacedBy, exemplar, precedes, isPeerOf,
hasSkillLevel, isRelatedTo
```

- **`CFItemType` / `educationLevel` / `listEnumeration` を取り込まない**（Excel import との大きな差）。CSV では item type と学年が失われる
- `isChildOf` は**親の `humanCodingScheme` で照合**する（`humanCodingScheme → 行 index` のマップ）。空なら humanCodingScheme をドット記法（`1.1` の末尾を落として `1`）で親を導出、見つからなければ top-level
- compeito の OpenSALT 形式 CSV（`csv_export_service.export_opensalt_csv`）との非互換が 2 点:
  1. 先頭に `#identifier,...` 等の **`#`metadata 行**を出すが、OpenSALT は CSV の **1 行目を無条件にヘッダ扱い**するため、そのまま渡すと壊れる
  2. `Is Child Of` 列に**親の identifier（UUID）**を出すが、OpenSALT は humanCodingScheme で照合するため一致せず、さらに compeito の humanCodingScheme（`CS-A-1` 等のハイフン区切り）にはドットが無いため親が導出できず、**全アイテムが top-level に潰れる**

`docs/reference/opensalt-csv-format.md`（2026-03-12 調査）が記載していた「CSV importer が認識する 19 フィールド」はクライアント側 JS（`core/assets/js/lsdoc/index.js`）の話で、サーバ側 `GithubImport` が実際に保存するのは上記サブセットである点に注意。

## 含意（round-trip の faithful なターゲット）

- 「OpenSALT UI で設定できる項目を満遍なく埋めたフレームワークを往復させる」faithful な経路は **Excel (.xlsx)** である。CSV では item type / 学年 / 階層が落ちるため、満遍ない round-trip は CSV では閉じない
- 当初 **compeito は CSV しか喋れなかった**ため、OpenSALT との完全な round-trip には **compeito 側に OpenSALT-Excel (.xlsx) の import/export を追加する**必要があった。これは [phases.md](../requirements/phases.md) Phase 3 の "Improved OpenSALT compatibility" の具体的中身に相当する。→ **下記「実装」のとおり対応済**
- CASE JSON 経由は OpenSALT の export が v1.0 固定でバージョン非対称（v1p0 → v1p1 正規化の検証にはなるが、OpenCASE round-trip と大部分が重複する）

## OpenSALT Docker セットアップ（調査時の構成・再現用）

`opensalt/opensalt` を clone し `develop`（4.0.0-dev）で起動した。要点:

- ビルド済みイメージ `opensalt/opensalt:web-4.x` / `db-4.x` が Docker Hub にあるため、`./core` からの composer/yarn ビルドは不要（`docker compose pull db web`）
- 既定の `docker-compose.yml` は MySQL 8.0 + FrankenPHP/Symfony + Caddy に加え、ベクトル検索用の `qdrant` / `t2v`（huggingface text-embeddings-inference）と `scheduler` を含む。CSV/Excel round-trip にこれらは不要なので、`docker-compose.override.yml` で web の `depends_on` を `!override` で db のみにし、`qdrant`/`t2v`/`scheduler` を `profiles: ["full"]` に退避して既定起動から外した（`depends_on` はマージされるため `!override` が必要）
- `cp .env.dist .env` → データ/キャッシュディレクトリを `chmod 777` → `docker compose up -d` → `bin/console doctrine:migrations:migrate` → `salt:group:add` / `salt:user:add <user> <group> --password=... --role=super-user`（**group は位置引数で必須**）

## 実装（Excel 採用・完了）

方針として **Excel (.xlsx) を OpenSALT の交換形式に採用**し、compeito に xlsx import/export を追加した。

- `src/services/xlsx_export_service.py` / `xlsx_import_service.py`、CLI `export xlsx` / `import xlsx`（依存 `openpyxl`）
- export は CF Doc / CF Item / CF Association の 3 シートを生成。**階層は smartLevel（1 / 1.1 / 1.1.1 …、1-based 兄弟位置）**で表現し、isChildOf は CF Association シートに重複させない。CFItemType / educationLevel / conceptKeywords を含む
- import は CF Doc + CF Item を compeito の custom CSV に変換して既存 `csv_import_service.import_csv` を再利用（アイテム upsert・CFItemType find-or-create・educationLevel・smartLevel→isChildOf を流用）。CF Association シートの非 isChildOf 関連は専用パスで取り込む
- **実 OpenSALT で検証済（2026-06-07）**: compeito 出力の xlsx を稼働中 OpenSALT の `/salt/excel/import` に投入し、36 items・日本語の humanCodingScheme/fullStatement・smartLevel からの 36 isChildOf 階層・5 種の CFItemType（領域/分野/知識/技能/態度）・CF Doc メタデータがすべて復元されることを確認

### 既知のギャップ

- ~~compeito は CFItem/CFDocument に `notes` 列を持たないため `notes` セルは空~~ → **解消**: CASE v1.1 の `notes` を CFItem/CFDocument/CFAssociation に実装済み。xlsx でも CFItem(H)/CFDoc(P) の `notes` を入出力する（OpenSALT 列準拠）。`alternativeLabel`/`extensions` は OpenSALT Excel に列が無いため xlsx 対象外（CASE JSON で往復）
- OpenSALT の Excel import は CF Doc の identifier をシートから設定せず**新規採番**する（`ExcelImport::saveDoc` の identifier 設定がコメントアウト）。そのため OpenSALT 側の doc UUID は投入値と変わる（items の identifier は保持される）
- smartLevel は 1-based 兄弟位置で再採番するため、compeito の sequenceNumber（10, 20 …）は xlsx 往復で 1, 2 … に変わる（OpenSALT は smartLevel を再計算するモデルなので相互運用上は問題ない）

## 状態

**Excel round-trip 実装済・実機検証済**。CSV は依然として OpenSALT 側 export 不在のため双方向 round-trip は閉じないが、満遍ない相互運用は xlsx 経路で達成。
