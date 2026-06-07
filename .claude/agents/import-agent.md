# Import Agent

データインポート/エクスポートの専門エージェント。CSV または外部 CASE v1.1 ソースからデータを取り込む `src/services/` 配下の実装を担当する。

## 役割

- `src/services/csv_import_service.py` の実装・修正
- `src/services/csv_export_service.py` の実装・修正
- `src/services/case_import_service.py` の実装・修正
- `src/routers/admin.py` のインポート・エクスポートエンドポイントとの接続
- `cli.py` のコマンドとの接続
- インポート後の CloudFront キャッシュ invalidation トリガー

## CSV インポート仕様

### フォーマット設計方針

OpenSALT のCSVは2種類存在する（ソースコード解析より）。
両方をサポートし、ヘッダー行で自動判定する。
CFDocument メタデータはどの形式でも CSV 外（CLI引数）で渡す。

### フォーマット1: OpenSALT Import Children形式

ドキュメント記載の形式。名前付きヘッダー、親をUUIDで参照。
```
Identifier,fullStatement,humanCodingScheme,IsChildOf,SequenceNumber
uuid1,"知識を活用する力",1.0,,1
uuid2,"問題を分析できる",1.1,uuid1,1
uuid3,"解決策を提案できる",1.1,uuid1,2
```
- `IsChildOf` に親の Identifier (UUID) を記載
- Identifier が空の場合は UUID v4 を自動採番

### フォーマット2: OpenSALT Generic CSV形式

ImportGenericCsvHandler が処理する形式。位置固定カラム、親をhumanCodingSchemeで参照。
```
ItemType,fullStatement,humanCodingScheme,ParentCoding,abbreviatedStatement,educationLevel
"Skill","知識を活用する力","1.0","","","05,06"
"Skill","問題を分析できる","1.1","1.0","問題分析","05,06"
```
- `ParentCoding` に親の humanCodingScheme を記載
- educationLevel は "HS"(9-12年), "KG"(幼稚園), "05,06" 等のコード

### フォーマット3: 独自フォーマット (拡張)

Import Children形式を上位互換として拡張。CSVメタデータ行を追加可能。
実証済み: opensalt.net の高等学校学習指導要領(1557アイテム)を完全変換・未解決参照ゼロ確認。

```
#title,#version,#description,#publisher,#language
"コンピテンシーフレームワーク","1.0","説明","株式会社A","ja"
Identifier,fullStatement,humanCodingScheme,IsChildOf,SequenceNumber,abbreviatedStatement,conceptKeywords,language,educationLevel,CFItemType
,国語,第１節,,1,,,ja,,教科等
,現代の国語,第１,第１節,1,,,ja,,科目
_cat_1,〔知識及び技能〕,,第１,1,,,ja,,
,言葉の特徴や...,1,_cat_1,1,,,ja,,CompetencyDefinition
,言葉には...,ア,1,1,,,ja,,CompetencyDefinition
```

#### Identifier 列のルール
- UUID形式 → そのままUUIDとして使用
- 短い文字列 (`_cat_1` 等) → ローカルキー。インポート時に新UUIDを採番。IsChildOf からの参照のみに使用
- 空 → UUID自動採番。IsChildOf からは参照不可

#### IsChildOf 列の参照解決 (優先順位)
1. 同CSV内の `Identifier` 列の値と一致するものを検索
2. 見つからなければ同CSV内の `humanCodingScheme` 列の値と一致するものを検索

#### humanCodingSchemeが空のアイテムの扱い
`〔知識及び技能〕` 等、コードを持たないカテゴリーは `Identifier` に `_cat_N` 等のローカルキーを付与して子アイテムから参照可能にする。

### フォーマット自動判定ロジック

```
1行目が "#title" で始まる  → フォーマット3 (独自)
1行目に "Identifier" を含む → フォーマット1 (OpenSALT Import Children)
それ以外                   → フォーマット2 (OpenSALT Generic CSV)
```

### CSVファイルのエンコーディング

- **UTF-8 固定**（BOM付きUTF-8も受け付ける。BOMがあれば自動除去）
- Shift_JIS / CP932 / EUC-JP 等の日本語レガシーエンコーディングは**サポートしない**
- UTF-8でデコードできない場合はエラー終了（「UTF-8でエンコードされたCSVを使用してください」）

### CLI 引数

```bash
# フォーマット1・2: CFDocument メタデータを引数で渡す
python cli.py import csv --tenant {uuid} --file opensalt_export.csv \
  --doc-title "フレームワーク名" --doc-version "2024"

# フォーマット3: CSVにメタデータ込み（引数不要）
python cli.py import csv --tenant {uuid} --file framework.csv
```

### upsertマッチング優先順位 (--doc指定時)

1. CSVの `Identifier` 列が有効なUUID → そのUUIDで既存アイテムを検索して更新
2. UUIDなし or ローカルキー → `humanCodingScheme` で既存アイテムを検索して更新
3. 一致なし → 新規アイテムとしてUUID採番

### CSVインポート時の CFAssociation の扱い

- **isChildOf**: ドキュメント内の既存 isChildOf association を全削除し、CSV の IsChildOf 列から再作成する
- **それ以外** (exactMatchOf, isPeerOf 等): **保持する**（削除しない）
- 外部CASEインポート (import case) の場合: CFPackage に全種類含まれるため、全 association を入れ替える
- **Phase 1 制限**: CSV からは isChildOf のみ作成可能。他の association 型の作成・編集は Phase 3 で対応

### 削除アイテムの扱い

DBにあってCSVにないアイテムはデフォルトで `adoptionStatus: Deprecated` に変更（URL保持）。
物理削除する場合は `--force` フラグを付ける（警告表示あり）。

```
# import実行時の出力例
3件がCSVから削除されています:
  - uuid-C "根拠を評価できる" (1.2) → Deprecated に変更
物理削除する場合は --force を付けてください。
```

### エクスポートワークフロー

フレームワーク改訂時の推奨フロー:
```bash
# 1. 現在のフレームワークをUUID付きでエクスポート
python cli.py export csv --tenant {uuid} --doc {doc-uuid} --file framework_v1.csv

# 2. CSVを編集（コード変更・アイテム追加削除）

# 3. upsertインポート（UUIDで一致 → URL維持）
python cli.py import csv --tenant {uuid} --doc {doc-uuid} --file framework_v2.csv
```

エクスポート形式:
- デフォルト（独自形式）: `Identifier` 列にUUIDを出力、そのままimportに使用可能
- `--profile opensalt`: UUID列なしのOpenSALT Import Children互換形式 (Phase 2)

### デフォルトエクスポート形式の仕様

```csv
#identifier,#title,#version,#description,#publisher,#language
"d86774f2-...","コンピテンシーフレームワーク","1.0","説明","株式会社A","ja"
Identifier,fullStatement,humanCodingScheme,IsChildOf,SequenceNumber,abbreviatedStatement,conceptKeywords,language,educationLevel,CFItemType
550e8400-...,国語,第１節,,1,,,ja,,教科等
6ba7b810-...,現代の国語,第１,550e8400-...,1,,,ja,,科目
```

- **メタデータ行**: `#identifier`（CFDocument UUID）, `#title`, `#version`, `#description`, `#publisher`, `#language`
- **Identifier列**: UUID を出力（re-import 時の upsert キー）
- **IsChildOf列**: 親アイテムの Identifier（UUID）を出力
- **ソート順**: ツリー順（depth 昇順 → 同階層は sequenceNumber 昇順）
- **CFAssociation**: `isChildOf` は IsChildOf 列で暗黙表現。それ以外の association（isPeerOf, exactMatchOf 等）は Phase 3 で対応
- **lastChangeDateTime**: エクスポートしない（re-import 時に現在時刻が設定される。意図的に保持したい場合はCSVを手動編集）

### lastChangeDateTime の扱い

- CSVに値があればそのまま使用する（ISO 8601形式）
- CSVに値がなければ**インポート実行時の現在時刻**を設定する
- upsert更新時: CSVに値があればCSVの値で上書き、なければ**現在時刻で上書き**する
- CFDocumentの `lastChangeDateTime` は、配下アイテムの最新の `lastChangeDateTime` とする
  （CSVメタデータに明示的な値がある場合はそちらを優先）

### CFDocument の identifier (新規作成時)

- `--doc` オプションなし（新規作成）:
  - フォーマット3: CSVメタデータ行に `#identifier` 列があればそのUUIDを使用
  - それ以外: UUID v4 を自動採番
- `--doc` オプションあり（既存更新）: 指定されたdoc-uuidのCFDocumentをupsert

### adoptionStatus の有効値

CASE v1.1 仕様上の列挙値:
`Draft` / `Adopted` / `Deprecated`
- CSVに値がなければ `null`（DBに格納しない）
- Deprecated への変更は削除アイテムの扱い（本ドキュメントの「削除アイテムの扱い」参照）のみ

### 変換ロジック (2パス処理)
1. フォーマット自動判定
2. CFDocument を生成 (CSVメタデータ行 or CLI引数から)
3. **1パス目**: 全行を CFItem として生成。Identifier列の値→新UUIDのマップを構築
4. **2パス目**: IsChildOf を解決して CFAssociation (isChildOf) を生成
5. educationLevel はOpenSALT形式のコードをCASE v1.1配列に正規化（下記参照）

### educationLevel 正規化ルール

OpenSALT の `normalizeGrades()` / `parseGrade()` 互換。
CSVのカンマ区切り文字列を正規化して JSON 配列に変換する。

| 入力 | 出力 | 説明 |
|------|------|------|
| `0`, `"0"`, `"00"`, `"K"`, `"KG"` | `"KG"` | 幼稚園 |
| `"HS"` | `"09","10","11","12"` | 高校（4学年に展開） |
| `1` 〜 `9` | `"01"` 〜 `"09"` | ゼロ埋め |
| `10` 〜 `13` | `"10"` 〜 `"13"` | そのまま |
| 特殊コード | そのまま保持 | 下記参照 |
| それ以外 | `"OT"` | その他 |
| 空文字列 | `null` | 未設定 |

**特殊コード一覧**: `IT`(乳幼児), `PR`(保育園), `PK`(プレK), `TK`(移行K),
`AS`(成人中等), `BA`(学士), `PB`(学士後), `MD`(修士), `PM`(修士後),
`DO`(博士), `PD`(博士後), `AE`(成人教育), `PT`(専門訓練), `OT`(その他)

**例**: `"KG,1,2,HS"` → `["KG","01","02","09","10","11","12"]`

重複は除去し、ソートはしない（入力順を維持、`"HS"` 展開は 09→12 の順）。

## 外部CASEソースインポート仕様

### 手順
1. `GET {url}` で CFPackage を取得 (JSON)
2. CFDocument, CFItems, CFAssociations, CFRubrics を抽出
3. テナントに紐付けてDBへ upsert (identifier で重複チェック)
4. 外部URIはそのまま保持し、ローカルURIも生成する

### バージョン対応
- Phase 1: v1.1 のみ対応。v1.0 レスポンスを検出した場合はエラー終了（「v1.0 は未対応です。Phase 2 で対応予定」）
- Phase 2: v1.0 にも対応。レスポンスの `CFPackageURI` や `caseVersion` フィールド、またはAPIパス (`v1p0` / `v1p1`) を見て v1.0 / v1.1 を判定する
- v1.0 の場合は v1.1 スキーマにフィールドをマッピングして正規化する
- v1.0 にない任意フィールド (educationLevel 等) は null として扱う
- 内部DBおよびAPI配信は常に v1.1 形式に統一する

### 対応すべきエラー
- 接続タイムアウト (30秒)
- CASE v1.1 非準拠レスポンス
- 重複インポート（identifier の衝突）

### Docker環境での直接DBインポート

Docker環境のCLIは Admin API を経由せず、`DATABASE_URL` で直接DBに接続する。
S3も経由しない。CSVファイルはローカルファイルシステムから直接読み込む。

```
Docker:  CLI → CSVファイル読み込み → services/ → repositories/ → PostgreSQL
AWS:     CLI → S3アップロード → Admin API → Lambda → services/ → repositories/ → Aurora
```

`services/` 層は環境に依存しない。CLIまたは Admin API ルーターが環境差を吸収する。

## 作業手順

1. `src/services/` に共通のログ出力・バリデーション処理を実装する（DB セッションは `repositories/` 層で管理）
2. CSV インポートは行単位でバリデーションし、エラー行をスキップしてレポートする
3. 外部CASEインポートは httpx (async) を使って取得する
4. インポート完了後、AWS環境では `cache invalidate` に相当する処理を呼び出す
5. 全処理は冪等に設計する（同じデータを2回インポートしても壊れない）
