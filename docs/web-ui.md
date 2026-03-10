# Web UI 仕様

## パスパラメータの意味

- `{tenant-uuid}`: テナントの `id`（UUID PK。公開URLに使われるUUID）
- `{doc-uuid}`: CFDocument の `identifier`（CASE識別子）。内部PK（`id`）ではない。Admin API と同一定義
- `{item-uuid}`: CFItem の `identifier`（CASE識別子）。内部PK（`id`）ではない
- `/uri/{uuid}`: テナントスコープ内で `identifier` カラムを横断検索する UUID

## レスポンスヘッダー（Cache-Control）

**通常ページ**（`/`, `/{tenant}/`, `/cftree/doc/{doc}`, `/uri/{uuid}`）: `Cache-Control: public, max-age=3600`

**HTMX フラグメント**（`/cftree/doc/{doc}/children/{item}`, `/cftree/doc/{doc}/detail/{item}`）: `Cache-Control: public, max-age=86400`（ツリーの部分コンテンツは変更頻度が低いため長めに設定。インポート時に CloudFront invalidation で即時更新）

**エラーレスポンス**（4xx/5xx）: `Cache-Control` を設定しない（CASE API と同一方針）。

## URLパス設計

| Path | 説明 |
|------|------|
| GET / | 公開テナント一覧: テナント名の一覧（privateは非表示）。`name ASC, id ASC` でソート。各テナント名は `/{tenant-uuid}/` へのリンク。公開テナントが0件の場合は「公開テナントはありません」を表示 |
| GET /{tenant-uuid}/ | フレームワーク一覧: CFDocumentのtitle, lastChangeDateTime, アイテム数（`SELECT COUNT(*) FROM cf_item WHERE cf_document_id = doc.id`）。`title ASC, identifier ASC` でソート。各ドキュメントのタイトルは `/{tenant-uuid}/cftree/doc/{doc-uuid}` へのリンク。ドキュメントが0件の場合は「フレームワークはありません」を表示 |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid} | ツリービュー (Level 1-2をSSR、Level 3+はHTMX遅延ロード) |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/children/{item-uuid} | 子アイテムHTMLフラグメント (HTMX用) |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/detail/{item-uuid} | アイテム詳細HTMLフラグメント (HTMX右ペイン用) |
| GET /{tenant-uuid}/uri/{uuid} | リソース詳細ページ (HTML固定) |

## ツリービュー (`/cftree/doc/{doc-uuid}`)

OpenSALT のツリービューを参考にした 2 ペイン構成。見た目は Tailwind CSS のデフォルトスタイルでモダンに仕上げる（OpenSALT の見た目をコピーしない）。

**HTML `<title>` 要素:** ページごとに設定する:
- `GET /`: 「CASE Server」（固定）
- `GET /{tenant}/`: 「{テナント名} - CASE Server」
- `GET /{tenant}/cftree/doc/{doc}`: 「{ドキュメントタイトル} - {テナント名} - CASE Server」
- `GET /{tenant}/uri/{uuid}`: リソース種別による。CFItem → 「{fullStatement の先頭50文字} - CASE Server」。CFDocument → 「{title} - CASE Server」。lookup/CFAssociation → 「{title or identifier} - CASE Server」
- エラーページ: 「{ステータスコード} - CASE Server」

**HTML `<html lang>` 属性:** `base.html` で `lang="ja"` を固定値として設定する（管理UIの言語が日本語であるため）。`/uri/` ページでリソースに `language` フィールドがある場合も `<html lang>` は変更しない（コンテンツの言語は `lang` 属性ではなくリソースの `language` フィールドで表現される）。

**ナビゲーション:** 全ページ共通でパンくずリンクをヘッダーに表示する:
- `GET /`: パンくずなし（トップページ自体）
- `GET /{tenant}/`: 「[テナント一覧](/)」
- `GET /{tenant}/cftree/doc/{doc}`: 「[テナント一覧](/) > [テナント名](/{tenant}/) > ドキュメントタイトル」（最後の要素は現在のページなのでリンクなし）
- `GET /{tenant}/uri/{uuid}`: リソース種別による。CFItem・CFAssociation → 「[テナント一覧](/) > [テナント名](/{tenant}/)」（所属ドキュメントはページ内の CFDocumentURI に表示）。CFDocument → 「[テナント一覧](/) > [テナント名](/{tenant}/)」。lookup リソース → 「[テナント一覧](/) > [テナント名](/{tenant}/)」

```
┌─────────────────────────────────────────────────────┐
│ ヘッダー: CFDocument title + adoptionStatus バッジ    │
├──────────────────────┬──────────────────────────────┤
│ 左ペイン（ツリー）     │ 右ペイン（詳細）              │
│                      │                              │
│ ▼ 国語               │ fullStatement                │
│   ▼ 現代の国語        │ humanCodingScheme            │
│     【知識及び技能】   │ identifier                   │
│     ● 言葉の特徴や... │ CFItemType                   │
│     ● 言葉には...     │ educationLevel               │
│   ▶ 言語文化          │ 「詳細」リンク → /uri/{uuid}  │
│ ▶ 地理歴史            │                              │
│ ▶ 公民                │                              │
└──────────────────────┴──────────────────────────────┘
```

- **左ペイン**: ツリー構造。クリックで展開/折りたたみ（▶/▼）。アイテムクリックで右ペインに詳細表示。各アイテムの表示テキストは `fullStatement`（長い場合は先頭100文字で打ち切り「...」を付与）。`humanCodingScheme` が非 NULL の場合は fullStatement の前に表示する（例: `A-1-(1) 実社会に必要な...`）。`CFItemType` が非 NULL の場合は小さなバッジで表示する
- **右ペイン**: 選択アイテムの詳細フィールドを表示。`/uri/{uuid}` への「詳細」リンク。HTMX `hx-get` でアイテム詳細フラグメントを取得して差し替える（フラグメントエンドポイント: `GET /{tenant}/cftree/doc/{doc-uuid}/detail/{item-uuid}`、HTMLフラグメントを返す）。
  - **アイテム選択時の表示フィールド**: fullStatement、humanCodingScheme（非NULL時）、identifier、CFItemType（非NULL時）、educationLevel（非NULL時）、language（非NULL時）、conceptKeywords（非NULL時）、`/uri/{uuid}` への「詳細」リンク
  - **初期状態**（アイテム未選択時）: CFDocument の情報（title, description, adoptionStatus, lastChangeDateTime, version, language）を右ペインに表示する。ドキュメントにアイテムが0件の場合、左ペインに「アイテムがありません」メッセージを表示する
  - `?item={item-uuid}` パラメータ付きアクセス時は該当アイテムを選択状態で表示する。右ペインの詳細も SSR でインライン出力する（HTMX での追加フェッチは不要）。UUID形式でない場合・該当アイテムが存在しない場合・該当アイテムが別ドキュメントに属する場合はパラメータを無視し初期状態を表示する
- **レスポンシブ**: モバイルではツリーのみ表示（右ペインは `display: none`）。アイテムタップで `/{tenant}/uri/{item-uuid}` に遷移する（デスクトップでは HTMX で右ペイン更新、モバイルでは `<a>` リンクとして機能する。Tailwind の `md:` ブレークポイントで切り替え）。ツリー上部に CFDocument のタイトルと「ドキュメント詳細」リンク（`/{tenant}/uri/{doc-uuid}`）を表示し、モバイルでもドキュメント情報にアクセス可能にする

### Level判定と初期展開状態
`cf_item.depth` カラムに格納（インポート時に `isChildOf` を再帰的にたどって計算）。
Level 1-2 = depth 0-1 をSSRで返し、depth 2+ はHTMX遅延ロード。
**SSR アイテムのソート順:** SSR で返す全アイテム（depth 0-1、および `?item=` 展開パス上のアイテム）のソート順は `/children/` フラグメントのソート順と同一とする（`sequence_number` 昇順 → `human_coding_scheme` 自然順ソート → `identifier` 辞書順。NULL は最後に配置）。
**初期展開状態:** depth 0 アイテムは展開状態（▼）で表示し、depth 1 の子アイテムを表示する。depth 1 アイテムは子を持つ場合は折りたたみ状態（▶）、子がない場合はリーフ（●）で表示する。これにより初期表示でツリーの2階層が一度に見える。
**例外**: `?item={item-uuid}` パラメータ付きアクセス時は、ルートからそのアイテムまでの展開パス上にある全アイテム（depth 2+ を含む）もSSRで返す。展開パスの計算は同一ドキュメント内の isChildOf を祖先方向にたどる（`/children/` エンドポイントと同じドキュメントスコープ。別ドキュメントの isChildOf は対象外）。パス上の各ノードの子もSSRに含める（展開パスから外れる兄弟ノードの子は通常ルール通りHTMX遅延ロード）。アイテムが複数の isChildOf 親を持つ場合は、`/uri/` ページの「ツリーで表示」リンクと同一ルール（`sequence_number` 最小、NULL は非NULLの後 → `destination_node_identifier` 辞書順）で親を選択する。**孤立アイテム**（isChildOf を持たないアイテム）の場合は展開パスが空となり、ルートレベルの孤立アイテム一覧にそのアイテムが含まれる状態で SSR を返す（通常の depth 0-1 展開に加えて孤立アイテム一覧も展開済み）。

### 子アイテム取得 (`/children/{item-uuid}`)
`isChildOf` association で `destination_node_identifier = item-uuid` の association を検索する。検索スコープはパスの `{doc-uuid}` で指定されたドキュメント内に限定する（`{doc-uuid}` = CFDocument の `identifier` → 対応する内部PK を解決し、`cf_association.cf_document_id` でフィルタする。別ドキュメントの isChildOf は含めない）。
各 association の `origin_node_identifier` が指すアイテム（= 子アイテム）を取得する。
`sequence_number` 昇順でソートする。`sequence_number` が NULL の場合は最後に配置する。`sequence_number` が同じ場合は `human_coding_scheme` の自然順ソート（数値部分を数値として比較する。例: `"A-2"` < `"A-10"`。Python の `natsort.natsorted()` デフォルト設定。NULL は非NULLの後に配置する）、それも同じ場合は `identifier` の辞書順（エクスポートのソート順と同一ルール）。

**孤立アイテムの表示:** isChildOf Association を持たないアイテム（外部CASEソースインポートで association がスキップされた場合等に発生しうる）は、ツリーの children クエリでは取得されない。これらのアイテムはルートレベルの末尾に別途表示する（depth=0 のアイテムのうち、**同一ドキュメント内の** isChildOf の origin でないものを追加取得する。別ドキュメントの isChildOf でのみ origin となっているアイテムも、現在のドキュメント内では孤立として扱う）。ソート順は上記と同じだが、sequence_number は常に NULL 扱いとなる。

**展開アイコン（▶/▼）の判定:** 各アイテムが子を持つかどうかは、同一ドキュメント内の isChildOf Association の `destination_node_identifier` にそのアイテムの `identifier` が存在するかで判定する。子が存在するアイテムには展開アイコン（▶）を表示し、存在しないアイテムにはリーフアイコン（●）を表示する。`/children/` フラグメントのレスポンスに含まれる各子アイテムにもこの判定を適用する（N+1 クエリ回避のため、子アイテム取得時に孫の存在を一括で確認する）。

※ `origin isChildOf destination` = 「origin は destination の子」。
子を探すには destination 側で検索する。

childrenパスに `{doc-uuid}` を含めることで、CloudFrontのワイルドカード
`/{tenant}/cftree/doc/{doc-uuid}*` で一括invalidation可能。

## `/uri/{uuid}` 詳細ページ

Open Badge Factory 等の外部システムからリンクされる公開ページ。
OpenSALT の `/uri/{uuid}` ページを参考にしつつ、デザインは Tailwind CSS のデフォルトスタイルでモダンに仕上げる。
値がないフィールドは非表示（行ごと省略）。「値がない」の定義: `null`、空文字列 `""`、空配列 `[]` のいずれも非表示とする。JSONB 配列フィールド（`educationLevel`, `conceptKeywords`, `subject` 等）は `null` でも `[]` でも行を表示しない。

**セキュリティ:** URL として表示するフィールド（`uri`, `officialSourceURL`, LinkURIDType 内の `uri` 等）は、`http:` / `https:` スキームの場合のみクリック可能なリンクとして描画する。それ以外のスキーム（`javascript:`, `data:` 等）はプレーンテキストとして表示する（XSS 防止）。全テキストフィールドは Jinja2 の autoescaping で HTML エスケープする。

### CFItem の場合

| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID |
| uri | 必須 | URL（リンク） |
| CFDocumentURI | 必須 | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| fullStatement | 必須 | テキスト |
| lastChangeDateTime | 必須 | ISO 8601 |
| humanCodingScheme | 任意 | テキスト |
| abbreviatedStatement | 任意 | テキスト |
| CFItemType | 任意 | CFItemTypeURI のネスト表示（title, identifier, uri） |
| educationLevel | 任意 | 配列をカンマ区切りで表示 |
| conceptKeywords | 任意 | 配列をカンマ区切りで表示 |
| language | 任意 | 言語コード |
| licenseURI | 任意 | ネスト表示（title, identifier, uri）。CFItemTypeURI と同一形式 |
| statusStartDate | 任意 | 日付 |
| statusEndDate | 任意 | 日付 |
| listEnumeration | 任意 | テキスト |
| 「ツリーで表示」リンク | - | `/{tenant}/cftree/doc/{doc-uuid}?item={item-uuid}` へ遷移。サーバー側でルートからこのアイテムまでの展開パスを計算し、該当ノードまで展開済みのツリーをSSRで返す。アイテムが複数の isChildOf 親を持つ場合は、`sequence_number` が最小の association の親を選択する（NULL は非NULLの後に配置する。`sequence_number` が同じ場合は `destination_node_identifier` の辞書順で最初のもの。エクスポートの親選択ルールと同一） |

### CFDocument の場合

| フィールド | 必須/任意 | 表示形式 |
|-----------|----------|---------|
| identifier | 必須 | UUID |
| uri | 必須 | URL（リンク） |
| title | 必須 | テキスト |
| lastChangeDateTime | 必須 | ISO 8601 |
| creator | 任意 | テキスト |
| publisher | 任意 | テキスト |
| description | 任意 | テキスト |
| language | 任意 | 言語コード |
| version | 任意 | テキスト |
| adoptionStatus | 任意 | バッジ表示（Draft / Private Draft / Adopted / Deprecated） |
| statusStartDate | 任意 | 日付 |
| statusEndDate | 任意 | 日付 |
| licenseURI | 任意 | ネスト表示（title, identifier, uri）。CFItem と同一形式 |
| officialSourceURL | 任意 | URL（リンク） |
| subject | 任意 | 配列をカンマ区切りで表示 |
| CFPackageURI | 必須 | ネスト表示（title, identifier, uri） |
| 「ツリーで表示」リンク | - | ツリービュートップへ遷移 |

### lookup リソースの場合（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）

uuid横断検索で lookup リソースに当たった場合、共通フィールド + 固有フィールドを表示する:

| フィールド | 表示形式 |
|-----------|---------|
| identifier | UUID |
| uri | URL（リンク） |
| title | テキスト |
| description | テキスト（値がある場合のみ） |
| リソース種別 | バッジ表示（例: "CFItemType", "CFSubject"） |
| 固有フィールド | typeCode, hierarchyCode, licenseText 等（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |

### CFAssociation の場合

uuid横断検索で CFAssociation に当たった場合、最低限の情報を表示する:

| フィールド | 表示形式 |
|-----------|---------|
| identifier | UUID |
| uri | URL（リンク） |
| CFDocumentURI | ネスト表示（title, identifier, uri）。title はツリービューへのリンク |
| associationType | テキスト（例: isChildOf） |
| originNodeURI | ネスト表示（title, identifier, uri） |
| destinationNodeURI | ネスト表示（title, identifier, uri） |
| sequenceNumber | 数値（値がある場合のみ） |
| CFAssociationGroupingURI | ネスト表示（title, identifier, uri）（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |

## バリデーション

Web UI パスでも CASE API と同様のバリデーションを行い、エラーページを表示する:
- `{tenant-uuid}` が UUID 形式でない → 400 エラーページ
- UUID 形式だがテナントが存在しない → 404 エラーページ
- **private テナントの直接アクセス:** `/{tenant-uuid}/` 以下のパスに直接アクセスした場合、テナントが private であっても通常通り表示する（アクセス制御は URL の秘匿性で実現する方針。architecture.md 参照）。GET / のテナント一覧のみ private テナントを非表示にする
- `{doc-uuid}` が UUID 形式でない → 400 エラーページ
- UUID 形式だがドキュメントが存在しない → 404 エラーページ
- `/uri/{uuid}` の `{uuid}` が UUID 形式でない → 400 エラーページ
- `/uri/{uuid}` でテナントスコープ内にリソースが見つからない → 404 エラーページ
- `/children/` および `/detail/` エンドポイントの `{tenant-uuid}` が UUID 形式でない → 400（「リクエストが不正です」テキストを含むHTMLフラグメント + ステータスコード400。フルエラーページではなくフラグメントを返す。HTMX スワップ対応）
- `/children/` および `/detail/` エンドポイントの `{tenant-uuid}` が UUID 形式だがテナントが存在しない → 404（「テナントが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404）
- `/children/` および `/detail/` エンドポイントの `{doc-uuid}` が UUID 形式でない → 400（「リクエストが不正です」テキストを含むHTMLフラグメント + ステータスコード400）
- `/children/` および `/detail/` エンドポイントの `{doc-uuid}` が UUID 形式だがドキュメントが存在しない → 404（「ドキュメントが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404）
- `/children/{item-uuid}` の `{item-uuid}` が UUID 形式でない → 400（空HTMLフラグメント + ステータスコード400）
- `/children/{item-uuid}` の `{item-uuid}` が UUID 形式だがアイテムが存在しない、または存在するが `{doc-uuid}` のドキュメントに属さない → 空のHTMLフラグメントを返す（200。子がないのと同じ扱い。association の `cf_document_id` スコープで自然にフィルタされる）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式でない → 400（空HTMLフラグメント + ステータスコード400）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式だがアイテムが存在しない → 404 エラーフラグメント
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式でアイテムが存在するが `{doc-uuid}` のドキュメントに属さない → 404 エラーフラグメント（別ドキュメントのアイテム詳細をツリービュー内で表示しない）
- `/detail/{item-uuid}` の `{item-uuid}` が UUID 形式だがアイテムが存在しない、または別ドキュメントに属する場合の 404 エラーフラグメント → 「アイテムが見つかりません」テキストを含むHTMLフラグメント + ステータスコード404
- `/children/` および `/detail/` エンドポイントで 500 Internal Server Error が発生した場合 → 「サーバーエラーが発生しました」テキストを含むHTMLフラグメント + ステータスコード500 を返す
- **HTMX の非2xxレスポンス処理:** HTMX はデフォルトで非2xxレスポンスのコンテンツをスワップしない。400/404/500 のエラーフラグメントを右ペインに表示するため、`htmx:beforeSwap` イベントハンドラで `shouldSwap = true` を設定する（`base.html` に記述）

## エラーページ

Web UI のエラー表示。Tailwind CSS でスタイリングし、ユーザーフレンドリーに。

| HTTPステータス | 表示内容 |
|---------------|---------|
| 404 | 「ページが見つかりません」+ トップ（/）へのリンク |
| 400 | 「リクエストが不正です」+ エラー詳細 + トップへのリンク |
| 500 | 「サーバーエラーが発生しました」+ トップへのリンク |

テンプレート: `src/templates/error.html`（共通エラーテンプレート、ステータスコードとメッセージを受け取る）

## URI生成ルール

CASEリソースの `uri` フィールドは `/uri/{uuid}` を指す (OpenSALTと同じパターン):
`https://example.com/{tenant-uuid}/uri/{resource-uuid}`

- `config.py` に `BASE_URL` 設定を持つ（例: `https://case.example.com`）
- Docker環境のデフォルト: `http://localhost:8000`
- 環境変数 `BASE_URL` で上書き可能
- 新規作成時: `uri = f"{BASE_URL}/{tenant_id}/uri/{identifier}"`
- **外部インポート時**: 元の `uri` をそのまま DB に保持する（上書きしない）。
  外部URIのリソースを自サーバーの `/uri/{uuid}` でもアクセス可能にするため、
  `identifier` での検索を `/uri/{uuid}` ルーターが行う（DB の `uri` カラムとは別）
