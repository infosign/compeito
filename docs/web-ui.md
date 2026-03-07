# Web UI 仕様

## URLパス設計

| Path | 説明 |
|------|------|
| GET / | 公開テナント一覧: テナント名の一覧（privateは非表示） |
| GET /{tenant-uuid}/ | フレームワーク一覧: CFDocumentのtitle, lastChangeDateTime, アイテム数 |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid} | ツリービュー (Level 1-2をSSR、Level 3+はHTMX遅延ロード) |
| GET /{tenant-uuid}/cftree/doc/{doc-uuid}/children/{item-uuid} | 子アイテムHTMLフラグメント (HTMX用) |
| GET /{tenant-uuid}/uri/{uuid} | リソース詳細ページ (HTML固定) |

## ツリービュー (`/cftree/doc/{doc-uuid}`)

OpenSALT のツリービューを参考にした 2 ペイン構成。見た目は Tailwind CSS のデフォルトスタイルでモダンに仕上げる（OpenSALT の見た目をコピーしない）。

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

- **左ペイン**: ツリー構造。クリックで展開/折りたたみ（▶/▼）。アイテムクリックで右ペインに詳細表示
- **右ペイン**: 選択アイテムの主要フィールドを表示。`/uri/{uuid}` への「詳細」リンク
- **レスポンシブ**: モバイルではツリーのみ表示、アイテムタップで詳細ページ (`/uri/`) に遷移

### Level判定
`cf_item.depth` カラムに格納（インポート時に `isChildOf` を再帰的にたどって計算）。
Level 1-2 = depth 0-1 をSSRで返し、depth 2+ はHTMX遅延ロード。

### 子アイテム取得 (`/children/{item-uuid}`)
`isChildOf` association で `destination_node_identifier = item-uuid` の association を検索し、
各 association の `origin_node_identifier` が指すアイテム（= 子アイテム）を取得する。
`sequence_number` 昇順でソートする。

※ `origin isChildOf destination` = 「origin は destination の子」。
子を探すには destination 側で検索する。

childrenパスに `{doc-uuid}` を含めることで、CloudFrontのワイルドカード
`/{tenant}/cftree/doc/{doc-uuid}*` で一括invalidation可能。

## `/uri/{uuid}` 詳細ページ

Open Badge Factory 等の外部システムからリンクされる公開ページ。
OpenSALT の `/uri/{uuid}` ページを参考にしつつ、デザインは Tailwind CSS のデフォルトスタイルでモダンに仕上げる。
値がないフィールドは非表示（行ごと省略）。

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
| listEnumeration | 任意 | テキスト |
| 「ツリーで表示」リンク | - | ツリービューの該当アイテム位置へ遷移 |

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
| adoptionStatus | 任意 | バッジ表示（Draft / Adopted / Deprecated） |
| officialSourceURL | 任意 | URL（リンク） |
| subject | 任意 | 配列をカンマ区切りで表示 |
| CFPackageURI | 任意 | ネスト表示（title, identifier, uri） |
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
| associationType | テキスト（例: isChildOf） |
| originNodeURI | ネスト表示（title, identifier, uri） |
| destinationNodeURI | ネスト表示（title, identifier, uri） |
| sequenceNumber | 数値（値がある場合のみ） |
| lastChangeDateTime | ISO 8601 |

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
