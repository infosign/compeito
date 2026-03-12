# 初期データセットアップガイド

テナント作成からコンピテンシーフレームワーク・ルーブリックの登録までの手順。

## 前提条件

- Docker 環境が起動していること（`docker-compose up -d`）
- DBマイグレーション済み（`docker-compose exec app python cli.py db migrate`）

以下のコマンドはすべて Docker コンテナ内で実行する:

```bash
docker-compose exec app python cli.py <コマンド>
```

## 1. テナントの作成

まずデータの所有者となるテナントを作成する。

```bash
python cli.py tenant create --name "大学A"
# Created tenant: 550e8400-e29b-41d4-a716-446655440000 (大学A, public)
```

テナントUUIDを控えておく（以降 `{tenant}` と表記）。

既存テナントを使う場合:

```bash
python cli.py tenant list
```

## 2. アイテム（コンピテンシーフレームワーク）のインポート

ルーブリックを紐づける対象のドキュメントとアイテムを先にインポートする。

### 2a. CSVファイルの作成

最もシンプルな形式（簡易形式）。インデントで階層を表現する:

```csv
#title,情報Iコンピテンシー
#language,ja
情報社会の問題解決
  情報と情報技術を活用した問題発見・解決
  情報に関する法規や制度
コミュニケーションと情報デザイン
  メディアの特性とコミュニケーション手段の選択
  情報デザインの考え方や方法
```

UUID付き独自形式を使えば、後から再インポートで更新（upsert）できる:

```csv
#title,情報Iコンピテンシー
#language,ja
Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType
,情報社会の問題解決,A,,10,領域
,情報と情報技術を活用した問題発見・解決,A-1,,10,知識及び技能
,情報に関する法規や制度,A-2,,20,知識及び技能
```

フォーマットの詳細は [csv-format.md](csv-format.md) を参照。

### 2b. インポート実行

```bash
# 新規作成（--doc なし → 新しいドキュメントを作成）
python cli.py import csv --tenant {tenant} --file framework.csv

# 出力例:
# Imported '情報Iコンピテンシー' (d86774f2-...-...)
#   Items: 5 created, 0 updated, 0 skipped
#   Associations: 4 created
```

ドキュメントUUID を控えておく（以降 `{doc}` と表記）。

### 2c. 確認

```bash
# ドキュメント一覧で確認
python cli.py doc list --tenant {tenant}
```

Web UI（`http://localhost:8000/`）でもツリー構造を確認できる。

## 3. ルーブリックCSVの作成

ルーブリックCSVは `Type` 列で Rubric / Criterion / Level の3階層を表現する。

### 基本構造

```csv
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,,,,問題解決力ルーブリック,問題発見から解決までを評価,,,,,,,
Criterion,,,,,情報収集の適切さ,情報収集,1.0,1,,,,
Level,,,,,,,,1,優秀,5.0,多角的な視点で情報を収集し、信頼性を検証できている,
Level,,,,,,,,2,良好,4.0,複数の情報源から情報を収集できている,
Level,,,,,,,,3,要改善,2.0,情報収集が限定的である,
Criterion,,,,,分析の論理性,分析,1.0,2,,,,
Level,,,,,,,,1,優秀,5.0,データを適切に分析し、根拠のある結論を導ける,
Level,,,,,,,,2,良好,4.0,基本的な分析ができている,
Level,,,,,,,,3,要改善,2.0,分析が不十分である,
```

### 列の説明

| 列 | Rubric | Criterion | Level |
|----|--------|-----------|-------|
| **Type** | `Rubric` | `Criterion` | `Level` |
| **Identifier** | 空 → 自動採番 | 空 → 自動採番 | 空 → 自動採番 |
| **RubricIdentifier** | - | 直前のRubricを自動使用 | - |
| **CriterionIdentifier** | - | - | 直前のCriterionを自動使用 |
| **Title** | ルーブリック名 | - | - |
| **Description** | 説明 | 説明 | 説明 |
| **Category** | - | カテゴリ名 | - |
| **Weight** | - | 重み（小数） | - |
| **Position** | - | 表示順 | 表示順 |
| **Quality** | - | - | 品質ラベル |
| **Score** | - | - | スコア（小数） |
| **Feedback** | - | - | フィードバック文 |
| **CFItemIdentifier** | - | 紐づけるアイテムのUUID | - |

### ポイント

- **Identifier を空にすると UUID が自動採番される**。再インポートで更新したい場合は、一度エクスポートしてUUID付きCSVを取得する
- **親の指定は省略可能**。Criterion は直前の Rubric 行を、Level は直前の Criterion 行を自動的に親とする
- **CFItemIdentifier** で Criterion をアイテムに紐づけられる。紐づけない場合は空でよい

### CFItemIdentifier でアイテムに紐づける場合

先にインポートしたアイテムのUUIDが必要。エクスポートで取得できる:

```bash
python cli.py export csv --tenant {tenant} --doc {doc} --file items.csv
```

出力された `items.csv` の `Identifier` 列からUUIDを確認し、ルーブリックCSV の `CFItemIdentifier` 列に記入する。

## 4. ルーブリックのインポート

```bash
python cli.py import csv-rubric --tenant {tenant} --doc {doc} --file rubric.csv

# 出力例:
# Imported into '情報Iコンピテンシー' (d86774f2-...)
#   Rubrics:   1 created, 0 updated, 0 skipped
#   Criteria:  2 created, 0 updated, 0 skipped
#   Levels:    6 created, 0 updated, 0 skipped
```

`--doc` は必須。ルーブリックは既存ドキュメントに紐づける。

## 5. 確認とエクスポート

### エクスポート

```bash
python cli.py export csv-rubric --tenant {tenant} --doc {doc} --file rubric-export.csv

# 出力例:
# Exported 1 rubrics (2 criteria, 6 levels) to rubric-export.csv
```

エクスポートされたCSVにはUUIDが付与されている。このCSVを編集して再インポートすると、Identifier一致で既存データが更新される（upsert）。

### API で確認

```
GET http://localhost:8000/{tenant}/ims/case/v1p1/CFRubrics
GET http://localhost:8000/{tenant}/ims/case/v1p1/CFRubrics/{identifier}
GET http://localhost:8000/{tenant}/ims/case/v1p1/CFPackages/{doc}
```

CFPackage にもルーブリックが含まれる。

## 6. 更新（再インポート）

エクスポートしたCSVを編集して再インポートすれば、Identifierが一致するデータは更新される:

```bash
# エクスポート → 編集 → 再インポート
python cli.py export csv-rubric --tenant {tenant} --doc {doc} --file rubric.csv
# rubric.csv を編集（スコアの変更、レベルの追加等）
python cli.py import csv-rubric --tenant {tenant} --doc {doc} --file rubric.csv

# 出力例:
# Imported into '情報Iコンピテンシー' (d86774f2-...)
#   Rubrics:   0 created, 1 updated, 0 skipped
#   Criteria:  0 created, 2 updated, 0 skipped
#   Levels:    1 created, 5 updated, 0 skipped
```

## トラブルシューティング

| 症状 | 原因と対処 |
|------|-----------|
| `Document not found` | `--doc` のUUIDが間違っている。`doc list` で確認 |
| `Criterion has no parent rubric` | CSV内でRubric行より前にCriterion行がある。Rubric行を先に配置する |
| `Level has no parent criterion` | CSV内でCriterion行より前にLevel行がある。順序を確認 |
| `Invalid Rubric Identifier` | Identifierの値がUUID形式でない。空にすれば自動採番される |
| `CFItemIdentifier ... not found` | 指定したアイテムUUIDが存在しない。`export csv` で正しいUUIDを確認 |
| スコアや重みが null になる | 数値として解釈できない値が入っている（警告メッセージを確認） |
