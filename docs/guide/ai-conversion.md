# 生成 AI で Excel をフレームワークに変換する

*日本語 | [English](#converting-excel-with-generative-ai)*

Excel で作った原案を compeito に取り込みたい。
列の並びも見出しの付け方も手元の都合で決めてあるので、そのままでは取り込めない。
変換を生成 AI にやらせたい。

やれます。
ただし AI は**それらしく間違える**ので、間違え方を知って予防し、取り込む前に検知する手順が要ります。
このガイドはその手順です。

> 手元の Excel が OpenSALT のエクスポート形式なら、AI を挟む必要はありません。`import xlsx` がそのまま読みます。

## 全体の流れ

compeito への書き込みは CLI だけです。
Web UI からは取り込めません。

```
Excel  →  (生成 AI)  →  CSV / CASE JSON  →  import --dry-run  →  レポート確認  →  本番 import
```

`--dry-run` が要です。
実際に取り込んでからロールバックするので、出てくる数値は推定ではなく実測です。
何件入って何が消えるかを、コミット前に読めます。

コマンド例はハイブリッド構成（アプリはネイティブ）のものです。
全 Docker 構成なら `docker compose exec app` を前に付けてください（[docs/guide/initial-setup.md](initial-setup.md) 参照）。

## どの形式に変換させるか

| 形式 | 向く場面 | identifier の扱い |
|---|---|---|
| **simple 形式** | **階層のある新規作成。まずこれ** | 全て自動採番。指定できない |
| custom CSV | 新規作成で列を多く使いたいとき | 空にすると自動採番。ただし階層を作るには UUID が要る（後述） |
| custom CSV（エクスポート起点） | 既存の更新 | エクスポートに入っている既存 UUID をそのまま使う |
| CASE JSON | 他システムとの受け渡し | identifier が必須。欠落や不正な UUID の項目は skip される |

### 階層のある新規作成は simple 形式で

simple 形式はインデントだけで木を表します。
identifier がどこにも要りません。

```csv
#title,情報活用能力
言語表現
  言語表現I
    表現技法に関する事項
  言語文化
社会探究
  地理総合
```

半角スペース2つで1階層です。
タブは2スペース換算。
列は左から `fullStatement` / `humanCodingScheme` / `CFItemType` / `educationLevel` の4つで、5列目以降は無視されます。

取り込んだら、そのままエクスポートしてください。

```bash
uv run python cli.py import csv --tenant {tenant-uuid} --file draft.csv --dry-run --report report.json
uv run python cli.py import csv --tenant {tenant-uuid} --file draft.csv
uv run python cli.py export csv --tenant {tenant-uuid} --doc {doc-uuid} --file current.csv
```

出てきた `current.csv` は UUID の入った custom CSV です。
以後の追記・修正はこのファイルを起点にします（次節）。
**構造を先に作り、フィールドは後から足す**のがこの経路です。

### custom CSV で新規に階層を作る場合

`parentIdentifier` 列は UUID しか受け付けません。
UUID でない値は警告を出してルート扱いになります。
そして親として指せるのは、**他の行の `Identifier` 列に書かれた UUID だけ**です。

つまり `Identifier` を全行空にすると、`parentIdentifier` に書ける値が存在しなくなります。
取り込みは成功し、件数も合い、警告も出ませんが、**全項目がルートに並んだ平坦な文書**ができます。
この事故はレポートのどの数値にも現れません。

custom CSV で階層を作るなら、AI に新しい UUID v4 を生成させるしかありません。
そのときは次の2つをプロンプトで押さえてください。

- 例示・仕様書・既存の文書から UUID をコピーしない。必ず新規に生成する
- 生成した UUID は、そのファイルの中でだけ使う

そのうえで dry-run の `destructive.itemsMoved` を衝突検査として読みます。
**有効な UUID がテナント内の別文書の項目と一致すると、その項目を現在の文書へ引き剥がします。**
移動元の木が壊れます。
`itemsMoved` が 0 でなければ、コピーされた UUID が混ざっています。

CASE JSON も同じです。
identifier を省けないので、全て新規の uuid4 を生成させてください。

### 既存の更新は、必ずエクスポート起点で

一部だけ直したいときも、全量をエクスポートして、編集して、全量を取り込みます。

更新の取り込みは「この CSV に書かれた木が、この文書の木の全量である」という扱いです。
一部の行だけを書いた CSV を取り込むと、**書かれなかった項目の関連が削除されます**。
項目自体は残りますが、親を失ってツリーから浮きます。

```bash
uv run python cli.py export csv --tenant {tenant-uuid} --doc {doc-uuid} --file current.csv
# current.csv を AI に渡して編集させる
uv run python cli.py import csv --tenant {tenant-uuid} --doc {doc-uuid} --file edited.csv --dry-run --report report.json
```

**`--doc` を必ず付けてください。**
どの文書への更新かは、本来ファイル先頭の `#identifier` 行で決まります。
AI がメタデータ行を書き直してこの行を落とすと、取り込みは新規文書の作成に化けます。
そのとき各行の `Identifier` は既存項目の UUID なので、**元の文書から全項目が新文書へ移動します**。
元の文書は空になり、宙に浮いた関連だけが残ります。

`--doc` は `#identifier` より優先され、指定した文書が無ければ "Document not found" で止まります。
この事故が起きようがなくなります。

この経路なら、AI が扱う UUID はすべてエクスポート由来です。
捏造が入り込みません。

> **補足**: `Identifier` を空にした行は、新規作成とは限りません。更新の取り込みでは、同じ文書内で `humanCodingScheme` が一致する項目があればそれを更新します。コード体系を持つデータでは、これが意図した挙動になることも、ならないこともあります。確実なのはエクスポート起点です。

## プロンプトのテンプレート

形式仕様（[docs/spec/csv-format.md](../spec/csv-format.md)）の該当節と、実際のエクスポートを 1 件、一緒に渡すと精度が上がります。
お手本があると、AI は列の並びを勝手に変えません。

英語版は[下の EN 節](#prompt-template)にあります。

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
- 先頭の # で始まる行（#identifier など）は、書き換えずにそのまま残す

見本ファイルに # 行が無い場合だけ、次のメタデータ行を先頭に入れてください:
#title,（フレームワーク名）
#creator,（作成者）
#language,ja
```

階層を持つ新規作成でこのテンプレートを使う場合は、1つめのルールを次に差し替えます。

```
- Identifier 列には、行ごとに新しい UUID v4 を生成して入れる。
  例示・仕様書・他のファイルから UUID をコピーしない。
  parentIdentifier には、親の行の Identifier に書いた UUID をそのまま書く
```

`#creator` は入れてください。
取り込みは通りますが、CASE v1.1 の公式スキーマは `creator` を必須にしています。
空のままだと、適合性を求める出力（`?strict=1`）でこのフィールドが欠けます。
CSV の取り込みは creator の欠落を警告しないので、ここで入れておくのが唯一の防ぎ方です。

## AI がやりがちな間違い

| 間違い | compeito 側で起きること | 予防と検知 |
|---|---|---|
| UUID を作る、コピーする | 不正な UUID なら行が飛ばされる。有効でテナント内の既存項目と一致すると、**他の文書からその項目を奪う** | dry-run のレポートで `itemsMoved` を見る |
| 元データに無い列を足す | 関連の列があると、その種類の関連が文書全体で削除され、CSV の内容で作り直される。空欄の列は「関連なし」の意味になる | プロンプトで列を明示。レポートの `lostAssociationsCount` を見る |
| 行を省略する | 省かれた項目の関連が消える。項目は残るが親を失う | 「全量を出力」と指示。レポートの件数を元データと突き合わせる |
| メタデータ行を書き直す | `#identifier` が落ちると更新が新規作成に化け、全項目が移動する | 更新では `--doc` を付ける |
| `associationType` の綴り違い | CSV では列ごと黙って無視される（エラーにならない）。CASE JSON では該当の関連が飛ばされる | 正しい値は下記。dry-run で `associationsCreated` が想定どおりか見る |
| 区切り文字の混同 | 値が1つの文字列として入る | `educationLevel` と `conceptKeywords` はカンマ区切り、関連列のターゲットは `\|` 区切り |
| インデントの崩れ（simple 形式） | 深さが飛ぶと（0 → 2）警告つきで直前の項目の子として扱われる | 半角スペース2個で1階層。タブは2スペース換算 |
| 日付や列挙値の形式違い | 日付は警告を出して既存値を保持（新規なら空）。`adoption_status` は既定の4値以外だと警告を出したうえで、値はそのまま保存される | 日付は `YYYY-MM-DD`。`adoption_status` は `Draft` / `Private Draft` / `Adopted` / `Deprecated` |

### 関連の書き方は CSV と CASE JSON で違う

**CSV の関連列は9種類です。**

`isPeerOf` / `isPartOf` / `exactMatchOf` / `precedes` / `isRelatedTo` / `replacedBy` / `exemplar` / `hasSkillLevel` / `isTranslationOf`

`isChildOf` に列はありません。
親子は `parentIdentifier` 列（custom CSV）またはインデント（simple 形式）で表します。
`isChildOf` という列を作っても無視されます。

列名の大文字小文字は区別されません。
`isRelatedTo` も `IsRelatedTo` も同じ列になります。
OpenSALT 形式の `Is Related To` も同じ列に落ちます。
`ext:` で始まる拡張の関連は CSV では使えません。

**CASE JSON の `associationType` は10種類**で、CSV の9種類に `isChildOf` を加えたものです。
こちらは大文字小文字も含めて一致している必要があり、`ext:` で始まる拡張が使えます（`ext:` に続けて英数字、ドット、ハイフン、アンダースコア）。

**綴り違いが一番見つけにくい間違いです。**
CSV では、列名が一致しなければその列ごと無視されます。
エラーは出ません。
「関連を書いたのに反映されない」ときは、まず列名を疑ってください。

## 取り込む前に確認する

```bash
uv run python cli.py import csv --tenant {tenant-uuid} --file converted.csv --dry-run --report report.json
```

`--dry-run` は結果をコンソールに要約しません。
`--report` と併用してください。

`report.json` で次を見ます。

| 見る場所 | 期待する値 |
|---|---|
| `counts.itemsCreated` / `itemsUpdated` | 足した数が元データの行数と合っているか |
| `destructive.lostAssociationsCount` | 0（更新時。消える関連があるなら意図したものか） |
| `destructive.itemsMoved` | **0**。0 でなければ UUID の衝突が起きている |
| `issues` | 空が理想。飛ばされた行は `Invalid Identifier` / `fullStatement is empty, skipped` として出る |
| `applied` | dry-run では `false`。本番実行の記録では `true` |

`counts.itemsSkipped` は CSV の取り込みでは常に 0 です。
飛ばされた行は `issues` にしか出ないので、件数の突き合わせは `itemsCreated + itemsUpdated` で行ってください。
`itemsSkipped` が意味を持つのは `import case`（CASE JSON）だけです。

`issues` の `required_field_missing` も CASE JSON の取り込みでしか出ません。
これが出たら、compeito 側で値を捏造することはないので、元データを直してください。

dry-run で採番された UUID はロールバックで捨てられます。
レポートに出た UUID を控えても、本番実行では別の値になります。

問題がなければ `--dry-run` を外して実行します。
破壊的な変更が残っている場合は確認を求められるので、**表示される内容を読んでから答えてください。**
削除される関連のサンプルが最大20件出ます。

自動化から実行する場合、確認プロンプトは出せません。
破壊的な変更があると `--yes` が無い限り止まります（終了コード 1）。
先に `--dry-run` で内容を見てから `--yes` を付けるのが正しい順序です。

最後に Web UI のツリーを開いて目を通してください。
件数が合っていても、階層が意図と違うことはあります。

## 確認ガードが見ていないもの

AI に「この項目を修正して」と頼むと、修正した行だけを返してくることがあります。
そのまま取り込むと、残りの項目が親を失います。
**全量が返ってきているか、行数を数えてください。**

既存の文書への更新であれば、ガードはこれを検知します。
CSV 経路では全ての項目がちょうど1本の `isChildOf` を持つ（ルート項目は宛先が CFDocument になる）ので、項目を落とせば必ずその関連が失われるからです。

**ガードが沈黙するのは、新規文書として取り込まれた場合です。**
削除が一切走らないので、比較の対象がありません。
`#identifier` が落ちて更新が新規作成に化けたときが、まさにこの形に片足を突っ込みます。
だから更新では `--doc` を付け、行数は自分で数えます。

---

# Converting Excel with generative AI

*[日本語](#生成-ai-で-excel-をフレームワークに変換する) | English*

The Japanese text above is the full guide.
This section covers the parts you would copy into a prompt, plus the checks that go with them.

## Which format

- **New framework with a hierarchy → simple format.** Indentation alone expresses the tree, so no identifier is needed anywhere. Import it, then `export csv` to get a custom CSV with UUIDs filled in, and work from that export afterwards.
- **New framework in custom CSV.** `parentIdentifier` accepts a UUID only, and it can only point at a UUID written in another row's `Identifier` column. Leaving every `Identifier` empty therefore produces a **flat document** — the import succeeds, the counts match, and nothing warns. If you need custom CSV for a hierarchy, have the model generate a fresh UUID v4 per row and use `destructive.itemsMoved` as the collision check.
- **Updating an existing framework → export first, edit the export, import the whole thing back with `--doc`.** An update import treats the file as the complete tree of that document. Rows you leave out lose their associations.
- **CASE JSON** requires an identifier on every item; items without one, or with a malformed one, are skipped. Have the model generate fresh UUID v4 values.

## Prompt template

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
- Keep any leading `#` metadata rows (`#identifier`, ...) exactly as they are.

Only if the sample file has no `#` rows, start the file with:
#title,<framework name>
#creator,<author>
#language,ja
```

For a **new** hierarchical framework in custom CSV, replace the first rule with:

```
- Put a freshly generated UUID v4 in the Identifier column of every row.
  Never copy a UUID from an example, a specification, or another file.
  In parentIdentifier, write the UUID you put in the parent row's Identifier.
```

The second rule is not cosmetic.
**A present association column means "these are all the links of this type"**, so an empty column deletes every existing link of that type in the document.

Include `#creator`.
The import accepts a document without it, but the official CASE v1.1 schema requires `creator`, so conformant output (`?strict=1`) will simply be missing the field.
A CSV import does not warn about it.

## Association types

**CSV association columns — nine types:**

`isPeerOf` / `isPartOf` / `exactMatchOf` / `precedes` / `isRelatedTo` / `replacedBy` / `exemplar` / `hasSkillLevel` / `isTranslationOf`

There is no `isChildOf` column: parentage comes from `parentIdentifier` (custom) or indentation (simple).
Column names are matched case-insensitively, and `ext:` extensions are not available in CSV.

**CASE JSON `associationType` — ten values:** the nine above plus `isChildOf`, or an extension of the form `ext:<token>`.
Here the spelling must match exactly, case included.

**In CSV a column whose name does not match is ignored silently** — no error.
If links do not appear after an import, check the column name first.

## Check before you commit

```bash
uv run python cli.py import csv --tenant {tenant-uuid} --file converted.csv --dry-run --report report.json
```

`--dry-run` prints no summary of its own, so pass `--report`.

In `report.json`: `destructive.itemsMoved` should be 0 (anything else means a UUID collided with an item in another document), `destructive.lostAssociationsCount` should be 0 unless you meant it, and `issues` should be empty.
Reconcile the row count against `counts.itemsCreated + itemsUpdated` — `counts.itemsSkipped` is always 0 for CSV imports, and skipped rows appear only as `issues`.
`required_field_missing` appears for CASE JSON imports only; it means the source data left out a field the official CASE schema requires — fix it at the source, because compeito will not invent a value.

Without `--dry-run`, a destructive change triggers a confirmation prompt (up to 20 of the disappearing links are listed).
There is no prompt in a non-interactive environment: the run stops with exit code 1 unless you pass `--yes`.
Look at a dry run first, then add `--yes`.

Finally, open the tree in the web UI.
The counts can be right while the hierarchy is not.
