# Initial Data Setup Guide

End-to-end walkthrough from creating a tenant to registering competency frameworks and rubrics.

## Prerequisites

See [docs/dev/local-setup.md](../dev/local-setup.md) for development environment setup. Two configurations are supported: hybrid (DB in Docker, app native) and full Docker.

The examples below assume the **full Docker** configuration (`docker compose exec app uv run python cli.py ...`). For the hybrid configuration, drop the `docker compose exec app` prefix and use `uv run python cli.py ...` (or `uv run case-cli ...`).

```bash
# Full Docker
docker compose up -d                                       # PostgreSQL + app
docker compose exec app uv run python cli.py db migrate    # DB migration

# Hybrid
docker compose up -d db                                    # PostgreSQL only
uv run python cli.py db migrate                            # DB migration
```

## 1. Create a tenant

First, create the tenant that will own the data. `--slug` adds an optional URL-friendly alias used in the Web UI in place of the UUID (see [cli.md](../spec/cli.md#tenant-slug-rules) for the format).

```bash
docker compose exec app uv run python cli.py tenant create --name "Ikenohata University" --slug ikenohata-u
# Created tenant: 550e8400-e29b-41d4-a716-446655440000 (Ikenohata University, public)
```

After this, both URL forms address the same tenant:

- Canonical: `http://localhost:8000/550e8400-e29b-41d4-a716-446655440000/`
- Friendly: `http://localhost:8000/ikenohata-u/`

Note the tenant UUID (referred to as `{tenant}` below). Subsequent CLI commands take the UUID via `--tenant`; the slug is for Web UI URLs only.

To list existing tenants:

```bash
docker compose exec app uv run python cli.py tenant list
```

## 2. Import items (competency framework)

Import the document and its items first so rubrics can reference them later.

### 2a. Create a CSV file

The simplest format uses indentation to express hierarchy:

```csv
#title,Information I Competencies
#language,en
Problem-solving in the information society
  Discovering and solving problems using information technology
  Laws and regulations related to information
Communication and information design
  Characteristics of media and choice of communication means
  Concepts and methods of information design
```

The custom UUID-aware format enables update-via-re-import (upsert):

```csv
#title,Information I Competencies
#language,en
Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType
,Problem-solving in the information society,A,,10,Domain
,Discovering and solving problems using information technology,A-1,,10,Knowledge & Skills
,Laws and regulations related to information,A-2,,20,Knowledge & Skills
```

Format details are in [csv-format.md](../spec/csv-format.md).

### 2b. Run the import

```bash
# New document (without --doc → creates a new document)
docker compose exec app uv run python cli.py import csv --tenant {tenant} --file framework.csv

# Sample output:
# Imported 'Information I Competencies' (d86774f2-...-...)
#   Items: 5 created, 0 updated, 0 skipped
#   Associations: 4 created
```

Note the document UUID (referred to as `{doc}` below).

### 2c. Verify

```bash
# List documents
docker compose exec app uv run python cli.py doc list --tenant {tenant}
```

You can also view the tree structure in the Web UI at `http://localhost:8000/`.

## 3. Create a rubric CSV

A rubric CSV uses the `Type` column to express the three-level hierarchy (Rubric / Criterion / Level).

### Basic structure

```csv
Type,Identifier,RubricIdentifier,CriterionIdentifier,Title,Description,Category,Weight,Position,Quality,Score,Feedback,CFItemIdentifier
Rubric,,,,Problem-solving rubric,Evaluates from problem discovery to resolution,,,,,,,
Criterion,,,,,Appropriateness of information gathering,Information gathering,1.0,1,,,,
Level,,,,,,,,1,Excellent,5.0,Gathers information from multiple perspectives and verifies reliability,
Level,,,,,,,,2,Good,4.0,Gathers information from multiple sources,
Level,,,,,,,,3,Needs Improvement,2.0,Information gathering is limited,
Criterion,,,,,Logical analysis,Analysis,1.0,2,,,,
Level,,,,,,,,1,Excellent,5.0,Analyzes data appropriately and reaches well-supported conclusions,
Level,,,,,,,,2,Good,4.0,Performs basic analysis,
Level,,,,,,,,3,Needs Improvement,2.0,Analysis is insufficient,
```

### Column reference

| Column | Rubric | Criterion | Level |
|--------|--------|-----------|-------|
| **Type** | `Rubric` | `Criterion` | `Level` |
| **Identifier** | blank → auto-generated | blank → auto-generated | blank → auto-generated |
| **RubricIdentifier** | - | the preceding Rubric is used automatically | - |
| **CriterionIdentifier** | - | - | the preceding Criterion is used automatically |
| **Title** | rubric name | - | - |
| **Description** | description | description | description |
| **Category** | - | category name | - |
| **Weight** | - | weight (float) | - |
| **Position** | - | display order | display order |
| **Quality** | - | - | quality label |
| **Score** | - | - | score (float) |
| **Feedback** | - | - | feedback text |
| **CFItemIdentifier** | - | UUID of the linked item | - |

### Tips

- **A blank Identifier auto-generates a UUID.** To update via re-import, first export the data to obtain a CSV with UUIDs.
- **Parent references are optional.** A Criterion automatically refers to the preceding Rubric row; a Level automatically refers to the preceding Criterion row.
- **`CFItemIdentifier`** links a Criterion to an item. Leave it blank when no link is needed.

### Linking to items via CFItemIdentifier

The item UUID is required. Obtain it via export:

```bash
docker compose exec app uv run python cli.py export csv --tenant {tenant} --doc {doc} --file items.csv
```

Check the `Identifier` column in the exported `items.csv` and enter the UUID in the `CFItemIdentifier` column of the rubric CSV.

## 4. Import the rubric

```bash
docker compose exec app uv run python cli.py import rubric --tenant {tenant} --doc {doc} --file rubric.csv

# Sample output:
# Imported into 'Information I Competencies' (d86774f2-...)
#   Rubrics:   1 created, 0 updated, 0 skipped
#   Criteria:  2 created, 0 updated, 0 skipped
#   Levels:    6 created, 0 updated, 0 skipped
```

`--doc` is required. Rubrics are attached to an existing document.

## 5. Verify and export

### Export

```bash
docker compose exec app uv run python cli.py export rubric --tenant {tenant} --doc {doc} --file rubric-export.csv

# Sample output:
# Exported 1 rubrics (2 criteria, 6 levels) to rubric-export.csv
```

The exported CSV includes UUIDs. Editing it and re-importing updates existing rows by Identifier match (upsert).

### Verify via API

```
GET http://localhost:8000/{tenant}/ims/case/v1p1/CFRubrics
GET http://localhost:8000/{tenant}/ims/case/v1p1/CFRubrics/{identifier}
GET http://localhost:8000/{tenant}/ims/case/v1p1/CFPackages/{doc}
```

The CFPackage response also includes rubrics.

## 6. Update (re-import)

Editing the exported CSV and re-importing updates rows whose Identifiers match:

```bash
# Export → edit → re-import
docker compose exec app uv run python cli.py export rubric --tenant {tenant} --doc {doc} --file rubric.csv
# Edit rubric.csv (change scores, add levels, etc.)
docker compose exec app uv run python cli.py import rubric --tenant {tenant} --doc {doc} --file rubric.csv

# Sample output:
# Imported into 'Information I Competencies' (d86774f2-...)
#   Rubrics:   0 created, 1 updated, 0 skipped
#   Criteria:  0 created, 2 updated, 0 skipped
#   Levels:    1 created, 5 updated, 0 skipped
```

## Troubleshooting

| Symptom | Cause and remedy |
|---------|------------------|
| `Document not found` | The `--doc` UUID is wrong. Verify with `doc list`. |
| `Criterion has no parent rubric` | A Criterion row appears before any Rubric row. Place the Rubric row first. |
| `Level has no parent criterion` | A Level row appears before any Criterion row. Check ordering. |
| `Invalid Rubric Identifier` | The Identifier value is not a UUID. Leave it blank to auto-generate. |
| `CFItemIdentifier ... not found` | The specified item UUID does not exist. Run `export csv` to obtain the correct UUID. |
| Scores or weights become null | A non-numeric value was supplied (check the warning messages). |

---

# 初期データセットアップガイド（日本語）

テナント作成からコンピテンシーフレームワーク・ルーブリックの登録までの手順。

## 前提条件

開発環境のセットアップ手順は [docs/dev/local-setup.md](../dev/local-setup.md) を参照。ハイブリッド構成（DB だけ Docker、アプリは macOS ネイティブ）と全 Docker 構成の 2 通りがある。

以降の例は **全 Docker 構成** を前提にコマンドを記載する（`docker compose exec app uv run python cli.py ...`）。ハイブリッド構成で実行する場合は `docker compose exec app` を省略し、`uv run python cli.py ...`（または `uv run case-cli ...`）に読み替える。

```bash
# 全 Docker 構成の場合
docker compose up -d                                       # PostgreSQL + アプリ
docker compose exec app uv run python cli.py db migrate    # DB マイグレーション

# ハイブリッド構成の場合
docker compose up -d db                                    # PostgreSQL のみ
uv run python cli.py db migrate                            # DB マイグレーション
```

## 1. テナントの作成

まずデータの所有者となるテナントを作成する。`--slug` を指定すると、Web UI で UUID の代わりに使える URL 別名（任意）を設定できる（フォーマット仕様は [cli.md](../spec/cli.md#テナント-slug-の制約) を参照）。

```bash
docker compose exec app uv run python cli.py tenant create --name "池之端大学" --slug ikenohata-u
# Created tenant: 550e8400-e29b-41d4-a716-446655440000 (池之端大学, public)
```

設定後は次のどちらの URL でも同じテナントを指せる:

- canonical: `http://localhost:8000/550e8400-e29b-41d4-a716-446655440000/`
- 読みやすい URL: `http://localhost:8000/ikenohata-u/`

テナントUUIDを控えておく（以降 `{tenant}` と表記）。以降の CLI コマンドの `--tenant` には UUID を渡す（slug は Web UI の URL 別名であり、CLI の resolver キーではない）。

既存テナントを使う場合:

```bash
docker compose exec app uv run python cli.py tenant list
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

フォーマットの詳細は [csv-format.md](../spec/csv-format.md) を参照。

### 2b. インポート実行

```bash
# 新規作成（--doc なし → 新しいドキュメントを作成）
docker compose exec app uv run python cli.py import csv --tenant {tenant} --file framework.csv

# 出力例:
# Imported '情報Iコンピテンシー' (d86774f2-...-...)
#   Items: 5 created, 0 updated, 0 skipped
#   Associations: 4 created
```

ドキュメントUUID を控えておく（以降 `{doc}` と表記）。

### 2c. 確認

```bash
# ドキュメント一覧で確認
docker compose exec app uv run python cli.py doc list --tenant {tenant}
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
docker compose exec app uv run python cli.py export csv --tenant {tenant} --doc {doc} --file items.csv
```

出力された `items.csv` の `Identifier` 列からUUIDを確認し、ルーブリックCSV の `CFItemIdentifier` 列に記入する。

## 4. ルーブリックのインポート

```bash
docker compose exec app uv run python cli.py import rubric --tenant {tenant} --doc {doc} --file rubric.csv

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
docker compose exec app uv run python cli.py export rubric --tenant {tenant} --doc {doc} --file rubric-export.csv

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
docker compose exec app uv run python cli.py export rubric --tenant {tenant} --doc {doc} --file rubric.csv
# rubric.csv を編集（スコアの変更、レベルの追加等）
docker compose exec app uv run python cli.py import rubric --tenant {tenant} --doc {doc} --file rubric.csv

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
