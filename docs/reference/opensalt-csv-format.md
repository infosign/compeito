# OpenSALT CSV/Excel フォーマット調査結果

> 調査日: 2026-03-12
> 調査対象: [opensalt/opensalt](https://github.com/opensalt/opensalt) リポジトリのソースコード

## 背景

CASE v1.1 公式仕様（1EdTech）は JSON REST API のみを定義しており、CSV/Excel フォーマットの公式標準は存在しない。CSV/Excel による入出力は OpenSALT 独自の機能である。

compeito の「OpenSALT形式」は OpenSALT との相互運用を意図した形式だが、完全互換ではない。本ドキュメントは OpenSALT の実際のフォーマットを記録し、差異を明確にするためのものである。

## 出典（ソースコード）

| ファイル | 内容 |
|---------|------|
| `core/src/Service/ExcelExport.php` | Excel (.xlsx) エクスポート処理 |
| `core/src/Service/ExcelImport.php` | Excel (.xlsx) インポート処理（位置ベース） |
| `core/assets/js/lsdoc/index.js` | CSV インポート処理（ヘッダー名ベース） |
| `core/assets/js/util-salt.js` | `simplify()` 関数（ヘッダー名正規化） |
| `core/docs/sample files/sample_case.csv` | 公式サンプル CSV |
| `docs/index.rst` ([opensalt-docs](https://github.com/opensalt/opensalt-docs)) | ユーザードキュメント |

## OpenSALT Excel エクスポート（CF Item シート）

OpenSALT のエクスポートは **Excel (.xlsx)** であり CSV ではない。CF Item シートの列は位置ベースで以下の順序:

| 列位置 | ヘッダー名 | 説明 |
|--------|-----------|------|
| A | `identifier` | UUID |
| B | `fullStatement` | 全文テキスト |
| C | `humanCodingScheme` | 人間可読コード |
| D | `smartLevel` | 階層位置（"1.2.3" 形式、自動計算） |
| E | `listEnumeration` | 列挙番号 |
| F | `abbreviatedStatement` | 短縮表記 |
| G | `conceptKeywords` | キーワード |
| H | `notes` | 備考 |
| I | `language` | 言語コード |
| J | `educationLevel` | 教育段階 |
| K | `CFItemType` | アイテム種別名 |
| L | `license` | ライセンス |

## OpenSALT CSV インポート

CSV インポーターは `simplify()` 関数でヘッダー名を正規化してフィールドマッチングを行う。`simplify()` は非英字を除去し小文字化する（例: `"Human Coding Scheme"` → `"humancodingscheme"` → `humanCodingScheme` にマッチ）。

認識されるフィールド（19個）:

```
identifier, fullStatement, humanCodingScheme, abbreviatedStatement,
conceptKeywords, notes, language, educationLevel, cfItemType, license,
isChildOf, isPartOf, replacedBy, exemplar, precedes, isPeerOf,
hasSkillLevel, isRelatedTo, sequenceNumber
```

## 公式サンプル CSV のヘッダー

```csv
"Identifier","fullStatement","Human Coding Scheme","sequenceNumber","Abbreviated Statement","ConceptKeywords","Notes","Is Child Of","IsPartOf","replacedBy","Exemplar","hasSkillLevel","IsRelatedTo"
```

ケーシングが混在している（`fullStatement`, `Human Coding Scheme`, `IsPartOf` 等）が、`simplify()` により全てマッチする。

## compeito「OpenSALT形式」との差異

### 1列目: `CASE Item Identifier` vs `identifier`

compeito は `CASE Item Identifier` を使用しているが、OpenSALT は `identifier` を使用する。`simplify("CASE Item Identifier")` = `"caseitemidentifier"` は `simplify("identifier")` = `"identifier"` にマッチ**しない**。そのため、compeito がエクスポートした CSV を OpenSALT にインポートすると、identifier 列が認識されない。

### エクスポートに含まれない列

OpenSALT の Excel エクスポートには `Is Child Of`, `Is Part Of`, `Sequence Number` が含まれない。階層は `smartLevel` で表現される。ただし CSV インポート側ではこれらのフィールドを認識する。

### compeito にない列

- `smartLevel`: 階層位置の自動計算値。compeito は `Is Child Of` + `Sequence Number` で階層を表現
- `notes`: CASE v1.1 の CFItem.notes フィールド。compeito の DB スキーマには存在しない

### ヘッダーのケーシング

OpenSALT のエクスポートはキャメルケース（`fullStatement`）。compeito はスペース区切りタイトルケース（`Full Statement`）。OpenSALT の `simplify()` により 2〜12列目は互換性があるが、1列目（上記）は非互換。

### インポート時のフォーマット自動判定への影響

compeito のフォーマット自動判定は `CASE Item Identifier` の存在で OpenSALT 形式と判定する（[csv-format.md](../csv-format.md) 参照）。ヘッダー名を `identifier` に変更すると、独自形式の `Identifier` との区別が必要になる。
