# インポート/エクスポート ビジネスロジック

## CSVインポート処理フロー

```
1. CSVファイル読み込み・フォーマット自動判定
2. メタデータ行のパース
3. CFDocument の作成または更新
4. 行ごとのパース・バリデーション
5. lookup系テーブルの自動生成 (CFItemType, CFSubject, CFConcept)
6. CFItem の作成または更新 (upsert)
7. CFAssociation (isChildOf) の生成
8. depth の計算
9. 結果レポート出力
```

### ステップ1: フォーマット判定

フォーマット自動判定ロジックは [csv-format.md](csv-format.md) を参照。

### ステップ2: メタデータパース

`#` で始まる行をキー・バリューとしてパースし、CFDocument のフィールドにマッピングする。
CLI引数が指定されている場合はCLI引数が優先。

### ステップ3: CFDocument 作成/更新

| 条件 | 動作 |
|------|------|
| `--doc` 未指定 | 新規CFDocumentを作成。`identifier` は UUID v4 自動採番 |
| `--doc {uuid}` 指定、存在する | 既存CFDocumentを更新（メタデータ行の値で上書き） |
| `--doc {uuid}` 指定、存在しない | エラー終了（「指定されたドキュメントが見つかりません」） |

CFDocumentの `uri` は新規作成時のみ生成: `{BASE_URL}/{tenant_id}/uri/{identifier}`

`last_change_date_time` はインポート実行時のUTCタイムスタンプを設定する。

### ステップ4: 行パース・バリデーション

各行を内部表現に変換する。エラーは行番号と共に収集し、最後にまとめてレポートする。

**バリデーションルール:**
- `fullStatement` が空 → 行スキップ（警告）
- `Identifier` が空 → UUID v4 自動採番
- `Identifier` がUUID形式でない → エラー（行スキップ）
- **同一CSV内で `Identifier` が重複** → 後の行を採用（警告「Row N: Duplicate Identifier 'xxx', overwriting Row M」）
- `educationLevel` のパース → カンマ区切りで文字列配列に変換
- `conceptKeywords` のパース → カンマ区切りで文字列配列に変換
- `sequenceNumber` → 整数に変換。変換失敗時はエラー（行スキップ）

### ステップ5: lookup系テーブル自動生成

CSVの `CFItemType` 列の値から、lookup系テーブルのレコードを自動生成する。

**マッチングルール（全lookup共通）:**
1. 同一テナント内で `title` の**完全一致**を検索（大文字小文字を区別する）
2. 一致するレコードがあれば、そのレコードのIDを使用
3. なければ新規レコードを作成（`identifier` = UUID v4、`uri` = `{BASE_URL}/{tenant_id}/uri/{identifier}`）

**対象テーブルと元データ:**
| lookup テーブル | CSVの列 | 備考 |
|---------------|---------|------|
| cf_item_type | CFItemType | 値が空なら cf_item.cf_item_type_id = NULL |
| cf_subject | メタデータ `#subject` | カンマ区切り。cf_documentの `subject` / `subject_uri` に格納 |
| cf_concept | conceptKeywords | cf_item の `concept_keywords` / `concept_keywords_uri` に格納 |

### ステップ6: CFItem upsert

**upsertマッチングキー（優先順）:**

1. **Identifier一致**: CSVの `Identifier` が既存CFItemの `identifier` と一致 → 更新
2. **humanCodingScheme一致**: 同一テナント・同一ドキュメント内で `human_coding_scheme` が一致 → 更新
3. **いずれも不一致** → 新規作成

**更新時の動作:**
- CSVに値がある列 → 上書き
- CSVに値がない列（空セル） → 既存値を保持（NULLで上書きしない）
- `last_change_date_time` → インポート実行時のUTCタイムスタンプで上書き

**新規作成時の動作:**
- `identifier` → CSVの値。空なら UUID v4 自動採番
- `uri` → `{BASE_URL}/{tenant_id}/uri/{identifier}`
- `last_change_date_time` → インポート実行時のUTCタイムスタンプ

### ステップ7: CFAssociation (isChildOf) 生成

親子関係を `isChildOf` タイプの CFAssociation として保存する。

**parentIdentifier の解決:**
1. 独自形式・OpenSALT形式: `parentIdentifier` / `Is Child Of` 列の UUID で親を特定
2. 簡易形式: インデントから depth を計算し、直前の浅い depth のアイテムを親とする
3. 親が見つからない場合: CFDocument を親とする（ルートレベル扱い）

**生成ルール:**
- origin_node = 子アイテム（自分自身）
- destination_node = 親アイテム or CFDocument
- `association_type` = `isChildOf`
- `identifier` = UUID v4 自動採番
- `sequence_number` = CSVの `sequenceNumber`。空なら出現順に 10, 20, 30... を自動採番

**upsert時の既存Association処理:**
- `--doc` 指定の更新時: 該当ドキュメントの既存 `isChildOf` Association を**全削除**してから再生成する
- 新規作成時: そのまま生成

### ステップ8: depth計算

全CFItemの `depth` を isChildOf Association から計算する。

**アルゴリズム:**
```
1. CFDocument直下のアイテム（parentがCFDocument）を depth=0 とする
2. BFS（幅優先探索）で isChildOf を辿り、子に parent.depth + 1 を設定
3. どの親からも到達できないアイテム（孤立ノード）は depth=0 とする（警告出力）
4. 循環参照を検出した場合: 該当アイテムの depth=0 とし、エラーレポートに追記
```

**循環参照検出:**
BFS 中に訪問済みノードを再訪問した場合、循環参照と判定する。
循環に含まれるアイテムのIdentifierをレポートに出力する。

### ステップ9: 結果レポート

インポート完了後、結果サマリーを出力する（CLI: rich テーブル形式）。

```
Import Result:
  Document:  高等学校学習指導要領 (d86774f2-...)
  Created:   1523 items
  Updated:   34 items
  Skipped:   3 items (see warnings below)
  ItemTypes: 5 created, 2 existing

Warnings:
  Row 45: fullStatement is empty, skipped
  Row 102: Invalid Identifier "abc", skipped
  Row 203: Parent "f1a2b3c4-..." not found, treated as root
```

## 外部CASEソースインポート

外部CASE APIからCFPackageを取得してDBに保存する。

### 処理フロー

```
1. GET {url}/CFPackages/{id} でCFPackage JSONを取得
   - URLがCFPackagesパスでない場合:
     a. GET {url}/CFDocuments で文書一覧を取得
     b. 最初（または唯一）のドキュメントの identifier を使用
     c. GET {url}/CFPackages/{identifier} で取得
2. JSON をパース・バリデーション
3. CFDocument を作成/更新
4. CFDefinitions (CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping) を保存
5. CFItems を一括保存
6. CFAssociations を一括保存
7. depth を計算
```

### URI保持ルール

外部インポート時は元のURIをそのまま保持する:
- `cf_document.uri` → 外部サーバーのURI（上書きしない）
- `cf_item.uri` → 外部サーバーのURI（上書きしない）
- `cf_association.uri` → 外部サーバーのURI（上書きしない）
- `identifier` → 外部のidentifier をそのまま使用

自サーバーの `/uri/{uuid}` では `identifier` で検索するため、
外部URIのリソースも自サーバー経由でアクセス可能になる。

### エラーハンドリング

| エラー | 動作 |
|--------|------|
| 外部URLに接続できない（タイムアウト含む） | エラー終了。タイムアウトは30秒。リトライしない |
| HTTPステータスが2xx以外 | エラー終了（「外部サーバーがHTTP {status}を返しました: {url}」） |
| レスポンスがJSONとしてパースできない | エラー終了（「レスポンスが有効なJSONではありません」） |
| JSONは有効だがCFPackage構造でない | エラー終了（「有効なCFPackageレスポンスではありません: {具体的な不備}」） |
| CFPackage内の個別リソースが不正 | 該当リソースをスキップし、警告をレポートに追記。他のリソースは処理続行 |
| SSL証明書エラー | エラー終了（「SSL証明書の検証に失敗しました」） |

### v1.0 → v1.1 正規化（Phase 2）

CASE v1.0 の CFPackage レスポンスを v1.1 形式に変換する:
- フィールド名の差異を吸収
- 欠落フィールドにデフォルト値を設定
- 詳細は Phase 2 実装時に定義

## CSVエクスポート処理フロー

```
1. CFDocument + 配下の全 CFItem を取得
2. isChildOf Association から親子関係を解決
3. ツリー順序（depth-first）でソート
4. 指定フォーマットでCSV生成
```

### 独自形式エクスポート

- メタデータ行を出力（`#title`, `#version` 等）
- 全列を出力（Identifier含む）
- `parentIdentifier` にはUUIDを出力
- `sequenceNumber` は実際の値を出力

### OpenSALT形式エクスポート（Phase 2）

- OpenSALTのヘッダー名で出力
- `Is Child Of` に親のIdentifierを出力
- `Is Part Of` にCFDocumentのIdentifierを出力

### ソート順序

ツリーの depth-first 順でソートする:
1. ルートレベルのアイテムを `sequence_number` 昇順で並べる
2. 各アイテムの子を `sequence_number` 昇順で再帰的に挿入
3. `sequence_number` が同じ場合は `human_coding_scheme` の自然順ソート
4. それも同じ場合は `identifier` の辞書順
