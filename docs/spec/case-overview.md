# CASE 入門 — 背景・全体像・バージョン

CASE という標準そのものの入門ドキュメント。「何のための標準か」「何を定義しているか（データモデルと API）」
「v1.0 と v1.1 の違いと設計方針」をまとめる。データモデルの詳細図解は
[`data-model-overview.md`](./data-model-overview.md) を参照。フィールド型などの権威的定義は
`docs/reference/` 配下（公式仕様の写し）にある。

---

## 1. CASE とは

**CASE = Competencies and Academic Standards Exchange**（コンピテンシー・学習到達基準交換）。
**1EdTech Consortium**（旧 IMS Global）が策定したオープン標準で、
**コンピテンシー（能力）や学習到達基準のフレームワークを、機械可読な形で交換・参照する**ための仕様。

一言でいえば「**到達目標の一覧を、URL で一意に指せる形で配信し、ツール間でやり取りする**」ための共通言語。

---

## 2. なぜ必要か（背景）

学習到達基準・コンピテンシーは、従来こういう形で扱われていた:

- PDF や Word、Excel の表 → 機械が読めない／項目を個別に参照できない
- 各ベンダーが独自フォーマット → ツール間で共有できない
- 「この設問はどの到達目標を測るのか」を**機械的に紐付けられない**

CASE はこれを解決するために、次を標準化した:

- **どの項目にもグローバル一意な `identifier`(UUID) と解決可能な `uri` を与える**
  → 設問・バッジ・教材から「この到達目標」を URL で名指しできる
- **フレームワークの構造（親子・関連）をデータとして表現する**
- **配信のための共通 REST/JSON API を定める**
  → どの実装でも同じ叩き方でフレームワークを取得できる

結果として、評価システム（例: QTI/TAO のテスト）やバッジ発行（例: Open Badges）が、
**同じ到達目標を URI で共有**できるようになる。

---

## 3. CASE が定義しているもの（2本柱）

CASE は **「データモデル」と「REST/JSON API」の2つ**を定義している（API も仕様の一部）。

```
CASE 仕様
├─ ① Information Model … データの構造（どんなエンティティが、どう繋がるか）
│     CFDocument / CFItem / CFAssociation / 定義(lookup) / CFRubric / CFPackage
│     → 詳細は data-model-overview.md
│
└─ ② REST/JSON Binding … 配信 API（どう取得するか）
      ベースパス /ims/case/v1p1 ・ GET 中心 ・ imsx_StatusInfo エラー形式
```

### ① データモデル（要約）

| エンティティ | 役割 |
|---|---|
| CFDocument | フレームワークのメタ情報（入れ物）|
| CFItem | 1つ1つのコンピテンシー / 到達目標（ノード）|
| CFAssociation | 項目同士の関係（枝。isChildOf でツリーを表現）|
| CFItemType / CFSubject / CFConcept / CFLicense | 参照マスタ（CFDefinitions）|
| CFRubric → Criterion → Level | 評価基準（3段ネスト）|
| CFPackage | 上記すべてを束ねた配布単位 |

> 重要な発想: **ツリーは木構造として保存されず、項目のフラットな集合 ＋ `isChildOf` 関連で表す**。
> 参照は外部キーではなく **URI（複合オブジェクト）による疎結合**。詳細と図解は data-model-overview.md。

### ② REST/JSON API

ベースパス `/ims/case/v1p1`。公開バインディングは**取得（GET）中心＝コンシューマ向け**で、
データ投入は仕様外（パッケージ/CSV の取り込みなどで行う）。主なエンドポイント:

| Method | Path | 返すもの |
|---|---|---|
| GET | `/CFDocuments` | フレームワーク一覧（唯一の一覧 API。ページネーション対応）|
| GET | `/CFDocuments/{id}` | CFDocument 単体 |
| GET | `/CFItems/{id}` | CFItem 単体 |
| GET | `/CFItemAssociations/{id}` | ある項目に関わる関連の集合 |
| GET | `/CFAssociations/{id}` | CFAssociation 単体 |
| GET | `/CFAssociationGroupings/{id}` | 関連グルーピング |
| GET | `/CFConcepts/{id}` `/CFSubjects/{id}` `/CFItemTypes/{id}` | 各 lookup（階層付き集合で返る）|
| GET | `/CFLicenses/{id}` | ライセンス単体 |
| GET | `/CFRubrics/{id}` | ルーブリック単体 |
| GET | `/CFPackages/{id}` | **フレームワーク丸ごと**（文書＋全項目＋全関連＋定義＋ルーブリック）|

補足:

- **`/CFPackages/{id}` が実質の主役**。1リクエストでフレームワーク全体を取得できる。
- 個別取得（`Standalone`）と、パッケージ内（`CFPckg*` 型）で**同じ種別でも持つフィールドが少し違う**
  （Standalone は `CFDocumentURI` 等が付く / パッケージ内は付かない）。
- エラーは **`imsx_StatusInfo`** という共通形式で返す（`docs/spec/api-spec.md` 参照）。
- サービス記述（OpenAPI）を **`/discovery/...` で自己配信**でき、クライアントが API 仕様を発見できる。

---

## 4. 設計方針（CASE の思想）

CASE のモデルとAPIを貫く考え方。これを知ると「なぜこの形なのか」が腑に落ちる。

- **URI で一意・解決可能**: すべてのリソースが UUID と解決可能 URI を持つ。外部から名指しできる。
- **疎結合な参照**: 参照は外部キーではなく `〜URI`（複合オブジェクト）。参照先が同じパッケージに
  無くてもよい（外部・別フレームワーク・未解決を許容）。
- **構造とノードの分離**: 親子や関連を項目に埋め込まず、独立した CFAssociation で表す。
  → 多重親・横断リンク・関連の付け替えが柔軟。
- **フレームワーク横断**: 関連の両端（origin/destination）は別フレームワークの項目も指せる
  （`targetType`）。`exactMatchOf` 等で「相当する到達目標」を跨いで結べる。
- **拡張性**: 列挙値は `ext:` 接頭辞で拡張でき、各エンティティに `extensions` を持てる。
  標準を壊さずに独自データを足せる。
- **同期しやすさ**: 全リソースが `lastChangeDateTime` を持ち、差分同期・キャッシュ制御に使える。
- **Model Driven Specification**: 1EdTech のモデル駆動手法で、抽象モデル → REST/JSON という
  プラットフォーム固有モデル(PSM)として導出されている（だから JSON 名はキャメルケースで規則的）。

> 💡 **CASE は「索引・地図」であって「本文」ではない**
>
> CASE を触ると「説明文を入れる場所が少なく、あっさりしている」と感じる。これは設計どおり。
> CASE の狙いは **①識別（URI を与える）・②構造（関連で位置づける）・③連結（URI で結ぶ）** の3つで、
> **リッチな説明文書を作る標準ではない**。
>
> - テキスト欄自体はある（`fullStatement` / `description` / `notes` / `feedback` 等）が、
>   いずれも **プレーン文字列**（Markdown/HTML などの書式は規定外）。`fullStatement` は
>   「その基準の正式な文言」を入れる場所で、解説を書く欄ではない。
> - 「意味」は文章ではなく **関連のネットワークと外部リンク**から立ち上がる。本格的な解説・教材は
>   CASE の外に置き、`officialSourceURL` や URI で**指す**のが流儀。
> - なぜ禁欲的か → **相互運用性**。スキーマが薄く規則的だからこそ、多数のベンダーが同じ形で
>   実装・交換でき、機械処理しやすい。リッチな自由記述は互換性と機械処理の敵になる。
>
> 説明を足したくなったときの CASE 流: 編集メモは `notes`、短い説明は `description`、
> 本格的な内容は URL で外部参照、構造化した独自データは `extensions`、
> 「細目を文章で書きたい」ときは **子の CFItem に分割**（文章ではなくノードで表す）。
>
> 要するに、**CASE はインデックス（索引・地図）であって、本文ではない**。
> 地図に小説を書き込まないのと同じ感覚で捉えるとちょうどいい。

---

## 5. v1.0 と v1.1 の違い

CASE 1.0 が最初の公開仕様、**CASE 1.1 はその上位互換（後方互換）のマイナー改訂版**。
1.1 は基本的に「**既存を壊さず項目を足す**」方針で、新しい用途（国際化・横断・拡張）に対応した。
（正確な公開年は 1EdTech 公式を参照。）

### 主な変更点（1.0 → 1.1）

| 変更 | 内容 | 設計意図 |
|---|---|---|
| `frameworkType` 追加（CFDocument）| フレームワークの種別を表す | 分類・発見性 |
| `caseVersion` 追加（CFDocument）| 自身が 1.1 準拠だと自己申告（値は `"1.1"`）| バージョン判別 |
| `subject` / `subjectURI` 追加（CFItem）| 項目レベルで教科を持てる | 粒度の向上 |
| `notes` 追加（CFAssociation）| 関連に注記 | 説明性 |
| `targetType` 追加（LinkGenURIDType）| 参照先の種別（`CASE` / `ext:`）| **フレームワーク横断**の明確化 |
| `isTranslationOf` 追加（associationType）| 翻訳関係を表す関連 | **国際化(i18n)** |
| NormalizedString → String | `fullStatement`(CFItem) / `description`(CFDocument・CFRubric) | 改行など自由記述を許容 |
| `extensions` 追加（全クラス）| 任意の拡張データ領域 | **拡張性** |
| ベースパス変更 | `/ims/case/v1p0` → `/ims/case/v1p1` | バージョン分離 |

### 設計方針の差をざっくり

```
CASE 1.0 … コア確立
   到達目標を URI で表し、構造(association)と配信API(GET)を定義した最初の版。

CASE 1.1 … 上位互換の拡張
   壊さず足す方針で、横断(targetType)・国際化(isTranslationOf)・
   拡張(extensions)・自己記述(caseVersion)を強化。
```

> compeito は **`/ims/case/v1p0` への古いパスを v1p1 へ正規化**して受けるため、1.0 世代のクライアントとも繋がる。

---

## 6. compeito はどこを実装しているか

compeito は CASE v1.1 の**配信側**（コンシューマに提供する側）を実装する OSS。

- **CASE v1.1 REST/JSON API（読み取り）** … 上記エンドポイント群 ＋ discovery ＋ `imsx_StatusInfo`
- **Web UI** … ツリービュー・詳細・permalink（外部システムからの URI 参照先になる）
- **取り込み/書き出し** … CFPackage(JSON) ・ CSV ・ Excel の import/export（CLI 中心）
- **参照先としての役割** … バッジ発行や QTI ベースのテストから、到達目標を URI で参照できる

詳細は `docs/spec/architecture.md`（構成）・`docs/spec/api-spec.md`（API 仕様）を参照。

---

## 7. もっと知るには（リポジトリ内）

| ドキュメント | 内容 |
|---|---|
| [`data-model-overview.md`](./data-model-overview.md) | データモデルの図解・つまずきポイント |
| `docs/reference/case-v1p1-info-model.md` | 公式データモデル定義（全フィールド・型・必須/任意）|
| `docs/reference/case-v1p1-rest-binding.md` | 公式 REST API 定義（エンドポイント・レスポンス型）|
| `docs/reference/imscasev1p1_openapi3_v1p0.json` | 公式 OpenAPI 3 スキーマ（権威的ソース）|
| `docs/spec/api-spec.md` | compeito の API 仕様（エラー形式・ページネーション等）|
