# 生成 AI で Excel をフレームワークに変換する

Excel で作った原案を compeito に取り込みたい。列の並びも見出しの付け方も手元の都合で決めてあるので、そのままでは取り込めない。変換を生成 AI にやらせたい。

やれます。ただし AI は**それらしく間違える**ので、間違え方を知って予防し、取り込む前に検知する手順が要ります。このガイドはその手順です。

## 全体の流れ

compeito への書き込みは CLI だけです。Web UI からは取り込めません。

```
Excel  →  (生成 AI)  →  CSV / CASE JSON  →  import --dry-run  →  レポート確認  →  本番 import
```

**`--dry-run` が要です。** 実際に取り込んでからロールバックするので、出てくる数値は推定ではなく実測です。何件入って何が消えるかを、コミット前に読めます。

## どの形式に変換させるか

| 形式 | 向く場面 | identifier の扱い |
|---|---|---|
| **custom CSV** | **新規作成。まずこれ** | `Identifier` 列を空にすると UUID v4 が自動採番される |
| custom CSV（エクスポート起点） | 既存の更新 | エクスポートに入っている既存 UUID をそのまま使う |
| CASE JSON | 他システムとの受け渡し | identifier が**必須**。欠落や不正な UUID の項目は skip される |
| simple 形式 | 下書き | インデントで階層だけ表す。メタデータは最小 |

### 新規作成では、AI に UUID を作らせない

**`Identifier` 列を空にしてください。** compeito が UUID v4 を採番します。

AI に UUID を生成させると、必ずしも新しい値になりません。仕様書の例や既存文書からコピーしてくることがあります。**有効な UUID がテナント内の別文書の項目と一致すると、その項目を現在の文書へ引き剥がします。** 移動元の木が壊れます。

CASE JSON を新規で生成させる場合は identifier を省けないので、プロンプトで明示してください（後述のテンプレートに入っています）。

### 既存の更新は、必ずエクスポート起点で

**一部だけ直したいときも、全量をエクスポートして、編集して、全量を取り込みます。**

更新の取り込みは「この CSV に書かれた木が、この文書の木の全量である」という扱いです。一部の行だけを書いた CSV を取り込むと、**書かれなかった項目の関連が削除されます**。項目自体は残りますが、親を失ってツリーから浮きます。

```bash
uv run python cli.py export csv --tenant {tenant-uuid} --doc {doc-uuid} --file current.csv
# current.csv を AI に渡して編集させる
uv run python cli.py import csv --tenant {tenant-uuid} --file edited.csv --dry-run --report report.json
```

この経路なら、AI が扱う UUID はすべてエクスポート由来です。捏造が入り込みません。

> **補足**: `Identifier` を空にした行は、新規作成とは限りません。更新の取り込みでは、同じ文書内で `humanCodingScheme` が一致する項目があればそれを更新します。コード体系を持つデータでは、これが意図した挙動になることも、ならないこともあります。確実なのはエクスポート起点です。

## プロンプトのテンプレート

形式仕様（`docs/spec/csv-format.md`）の該当節と、**実際のエクスポートを1件**を一緒に渡すと精度が上がります。お手本があると、AI は列の並びを勝手に変えません。

### 日本語

```
添付の Excel をコンピテンシーフレームワークの CSV に変換してください。

出力形式: 添付の見本ファイルと同じ列構成の CSV（UTF-8）。

必ず守ること:
- Identifier 列はすべて空にする。UUID を作ったり、どこかからコピーしたりしない
- 元データに値がある列だけを出力する。関連の列（isRelatedTo, isPeerOf など）は、
  元データがその関連を明示していない限り追加しない
- 毎回、文書の全量を出力する。行の一部を省略しない。「以下略」も書かない
- ファイルの中に説明文やコードブロックの記号を入れない。CSV そのものだけを出力する
- 日付は YYYY-MM-DD 形式。language は 10 文字以内
- 階層は parentIdentifier 列ではなく、humanCodingScheme の体系で表現できる場合はそう伝えてください

先頭に次のメタデータ行を入れてください:
#title,（フレームワーク名）
#creator,（作成者）
#language,ja
```

### English

```
Convert the attached Excel file into a competency framework CSV.

Output: CSV (UTF-8) with the same columns as the attached sample file.

Rules you must follow:
- Leave the Identifier column empty for every row. Never invent or copy UUIDs.
- Include ONLY the columns for which the source data has values. Do not add
  association columns (isRelatedTo, isPeerOf, ...) unless the source explicitly
  defines those relations.
- Output the complete document every time. Never omit rows, and never write
  "(remaining rows omitted)".
- Output raw CSV only. No commentary, no code fences inside the file.
- Dates are YYYY-MM-DD. `language` is at most 10 characters.

Start the file with these metadata rows:
#title,<framework name>
#creator,<author>
#language,ja
```

**`#creator` は入れてください。** 取り込みは通りますが、CASE v1.1 の公式スキーマは `creator` を必須にしています。空のままだと、適合性を求める出力（`?strict=1`）でこのフィールドが欠けます。CSV の取り込みは警告を出さないので、ここで入れておくのが唯一の防ぎ方です。

## AI がやりがちな間違い

| 間違い | compeito 側で起きること | 予防と検知 |
|---|---|---|
| **UUID を作る・コピーする** | 不正な UUID なら行が skip される。有効でテナント内の既存項目と一致すると、**他の文書からその項目を奪う** | 新規は `Identifier` を空に。dry-run のレポートで `itemsMoved` を見る |
| **元データに無い列を足す** | 関連の列があると、**その種類の関連が文書全体で削除され、CSV の内容で作り直される**。空欄の列は「関連なし」の意味になる | プロンプトで列を明示。レポートの `lostAssociationsCount` を見る |
| **行を省略する** | 省かれた項目の関連が消える。項目は残るが親を失う | 「全量を出力」と指示。レポートの件数を元データと突き合わせる |
| **`associationType` の綴り違い** | CSV では**列ごと黙って無視される**（エラーにならない）。CASE JSON では該当の関連が skip される | 正しい値は下記。dry-run で `associationsCreated` が想定どおりか見る |
| **区切り文字の混同** | 値が1つの文字列として入る | `educationLevel` と `conceptKeywords` はカンマ区切り、関連列のターゲットは `\|` 区切り |
| **インデントの崩れ**（simple 形式） | 深さが飛ぶと（0 → 2）警告つきで直前の項目の子として扱われる | 半角スペース2個で1階層。タブは2スペース換算。階層が重要なら custom 形式を使う |
| **日付や列挙値の形式違い** | 日付は警告を出して**既存値を保持**（新規なら空）。`adoption_status` は既定の4値以外だと警告 | 日付は `YYYY-MM-DD`。`adoption_status` は `Draft` / `Private Draft` / `Adopted` / `Deprecated` |

`associationType` に使える値は次の10種類です。大文字小文字も含めて一致している必要があります。

`isChildOf` / `isPeerOf` / `isPartOf` / `exactMatchOf` / `precedes` / `isRelatedTo` / `replacedBy` / `exemplar` / `hasSkillLevel` / `isTranslationOf`

拡張する場合は `ext:` で始めます（`ext:` に続けて英数字・ドット・ハイフン・アンダースコア）。

**綴り違いが一番見つけにくい間違いです。** CSV では、列名が一致しなければその列ごと無視されます。エラーは出ません。「関連を書いたのに反映されない」ときは、まず列名を疑ってください。

## 取り込む前に確認する

```bash
uv run python cli.py import csv --tenant {tenant-uuid} --file converted.csv --dry-run --report report.json
```

`report.json` で次を見ます。

| 見る場所 | 期待する値 |
|---|---|
| `counts.itemsCreated` / `itemsUpdated` | 元データの行数と合っているか |
| `counts.itemsSkipped` | **0**。0 でなければ `issues` に理由が出ている |
| `destructive.lostAssociationsCount` | **0**（更新時。消える関連があるなら意図したものか） |
| `destructive.itemsMoved` | **0**。0 でなければ UUID の衝突が起きている |
| `issues` | 空が理想。`required_field_missing` があれば元データを直す |
| `applied` | dry-run では `false`。本番実行の記録では `true` |

問題がなければ `--dry-run` を外して実行します。破壊的な変更が残っている場合は確認を求められるので、**表示される内容を読んでから答えてください。** 削除される関連のサンプルが最大20件出ます。

自動化から実行する場合、確認プロンプトは出せません。破壊的な変更があると `--yes` が無い限り止まります（終了コード 1）。**先に `--dry-run` で内容を見てから `--yes` を付けるのが正しい順序です。**

最後に Web UI のツリーを開いて目を通してください。件数が合っていても、階層が意図と違うことはあります。

## 更新のときに一番気をつけること

繰り返しになりますが、ここが一番事故の多い場所です。

**「10項目だけ直したい」ときに、その10行だけの CSV を作ってはいけません。** 更新の取り込みは全量として扱われるので、書かれなかった項目の関連が消えます。

AI に「この項目を修正して」と頼むと、修正した行だけを返してくることがあります。そのまま取り込むと、残りの項目が親を失います。**全量が返ってきているか、行数を数えてください。**

確認ガードはこの事故を検知します。ただし、検知できるのは**関連が実際に失われる場合**です。1項目だけの文書や、関連を持たない項目ばかりの文書では発火しません。行数の確認は自分でやってください。

---

# Converting Excel with generative AI

*[日本語](#生成-ai-で-excel-をフレームワークに変換する) | English*

The Japanese text above is the full guide. This section covers the parts you would copy into a prompt.

## Which format

- **New framework → custom CSV, with the `Identifier` column left empty.** compeito assigns UUID v4. Never let the model produce identifiers: a UUID copied from a spec example or another document will, if it happens to match an existing item in the tenant, **move that item out of its own document**.
- **Updating an existing framework → export first, edit the export, import the whole thing back.** An update import treats the file as the complete tree of that document. Rows you leave out lose their associations.
- **CASE JSON** requires an identifier on every item; items without one, or with a malformed one, are skipped.

## Prompt rules that matter

```
- Leave the Identifier column empty for every row. Never invent or copy UUIDs.
- Include ONLY the columns for which the source data has values. Do not add
  association columns (isRelatedTo, isPeerOf, ...) unless the source explicitly
  defines those relations.
- Output the complete document every time. Never omit rows, and never write
  "(remaining rows omitted)".
- Output raw CSV only. No commentary, no code fences inside the file.
- Dates are YYYY-MM-DD. `language` is at most 10 characters.
```

The second rule is not cosmetic. **A present association column means "these are all the links of this type"**, so an empty column deletes every existing link of that type in the document.

## Association types

`isChildOf` / `isPeerOf` / `isPartOf` / `exactMatchOf` / `precedes` / `isRelatedTo` / `replacedBy` / `exemplar` / `hasSkillLevel` / `isTranslationOf`, or an extension of the form `ext:<token>`.

Spelling must match exactly. **In CSV a column whose name does not match is ignored silently** — no error. If links do not appear after an import, check the column name first.

## Check before you commit

```bash
uv run python cli.py import csv --tenant {tenant-uuid} --file converted.csv --dry-run --report report.json
```

In `report.json`: `counts.itemsSkipped` should be 0, `destructive.lostAssociationsCount` and `destructive.itemsMoved` should be 0 unless you meant them, and `issues` should be empty. `required_field_missing` means the source data left a field the official CASE schema requires — fix it at the source; compeito will not invent a value.
