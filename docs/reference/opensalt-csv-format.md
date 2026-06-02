# OpenSALT CSV / Excel Format — Investigation Notes

> Investigated: 2026-03-12
> Source: source code of the [opensalt/opensalt](https://github.com/opensalt/opensalt) repository

## Background

The official CASE v1.1 specification (1EdTech) defines only a JSON REST API; there is **no official CSV/Excel standard**. CSV/Excel I/O is an OpenSALT-specific feature.

compeito's "OpenSALT format" is intended for interoperability with OpenSALT, but it is not fully compatible. This document records OpenSALT's actual format so the differences are explicit.

## Source code references

| File | Purpose |
|------|---------|
| `core/src/Service/ExcelExport.php` | Excel (.xlsx) export logic |
| `core/src/Service/ExcelImport.php` | Excel (.xlsx) import logic (position-based) |
| `core/assets/js/lsdoc/index.js` | CSV import logic (header-name based) |
| `core/assets/js/util-salt.js` | `simplify()` (header name normalization) |
| `core/docs/sample files/sample_case.csv` | Official sample CSV |
| `docs/index.rst` ([opensalt-docs](https://github.com/opensalt/opensalt-docs)) | User documentation |

## OpenSALT Excel export (CF Item sheet)

OpenSALT exports as **Excel (.xlsx)**, not CSV. The CF Item sheet uses a positional layout:

| Column | Header | Description |
|--------|--------|-------------|
| A | `identifier` | UUID |
| B | `fullStatement` | Full text |
| C | `humanCodingScheme` | Human-readable code |
| D | `smartLevel` | Hierarchical position (e.g., `1.2.3`, auto-computed) |
| E | `listEnumeration` | Enumeration |
| F | `abbreviatedStatement` | Shortened form |
| G | `conceptKeywords` | Keywords |
| H | `notes` | Notes |
| I | `language` | Language code |
| J | `educationLevel` | Education level |
| K | `CFItemType` | Item type name |
| L | `license` | License |

## OpenSALT CSV import

The CSV importer normalizes header names via `simplify()` to match fields. `simplify()` strips non-letters and lower-cases (e.g., `"Human Coding Scheme"` → `"humancodingscheme"` → matches `humanCodingScheme`).

Recognized fields (19):

```
identifier, fullStatement, humanCodingScheme, abbreviatedStatement,
conceptKeywords, notes, language, educationLevel, cfItemType, license,
isChildOf, isPartOf, replacedBy, exemplar, precedes, isPeerOf,
hasSkillLevel, isRelatedTo, sequenceNumber
```

## Headers in the official sample CSV

```csv
"Identifier","fullStatement","Human Coding Scheme","sequenceNumber","Abbreviated Statement","ConceptKeywords","Notes","Is Child Of","IsPartOf","replacedBy","Exemplar","hasSkillLevel","IsRelatedTo"
```

Casing is inconsistent (`fullStatement`, `Human Coding Scheme`, `IsPartOf`, etc.), but `simplify()` makes them all match.

## Differences from compeito's "OpenSALT format"

### Column 1: `Identifier`

compeito uses `Identifier`. OpenSALT uses lowercase `identifier`, but its `simplify()` is case-insensitive so they match. (An earlier compeito implementation used `CASE Item Identifier`, which OpenSALT did not recognize; this has been fixed.)

### Columns missing from the export

OpenSALT's Excel export omits `Is Child Of`, `Is Part Of`, and `Sequence Number`. The hierarchy is expressed via `smartLevel`. The CSV importer, however, does recognize these fields.

### Columns missing in compeito

- `smartLevel`: auto-computed hierarchical position. compeito expresses hierarchy via `Is Child Of` + `Sequence Number`.
- `notes`: CASE v1.1 `CFItem.notes` field. Not present in compeito's DB schema.

### Header casing

OpenSALT exports use camelCase (e.g., `fullStatement`). compeito uses space-separated Title Case (e.g., `Full Statement`). Columns 2–12 are compatible via OpenSALT's `simplify()`; column 1 (above) is the exception.

### Auto-detection on import

compeito's format auto-detection treats the presence of `Is Child Of` or `Is Part Of` as the OpenSALT signal (see [csv-format.md](../spec/csv-format.md)). These column names are absent from the custom format, so even with a shared `Identifier` column the two are distinguishable.

---

# OpenSALT CSV/Excel フォーマット調査結果（日本語）

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

### 1列目: `Identifier`

compeito は `Identifier` を使用。OpenSALT は `identifier`（小文字）を使用するが、OpenSALT の `simplify()` により大文字小文字は区別されないためマッチする。（初期実装では `CASE Item Identifier` を使用していたが、OpenSALT で認識されないため修正済み。）

### エクスポートに含まれない列

OpenSALT の Excel エクスポートには `Is Child Of`, `Is Part Of`, `Sequence Number` が含まれない。階層は `smartLevel` で表現される。ただし CSV インポート側ではこれらのフィールドを認識する。

### compeito にない列

- `smartLevel`: 階層位置の自動計算値。compeito は `Is Child Of` + `Sequence Number` で階層を表現
- `notes`: CASE v1.1 の CFItem.notes フィールド。compeito の DB スキーマには存在しない

### ヘッダーのケーシング

OpenSALT のエクスポートはキャメルケース（`fullStatement`）。compeito はスペース区切りタイトルケース（`Full Statement`）。OpenSALT の `simplify()` により 2〜12列目は互換性があるが、1列目（上記）は非互換。

### インポート時のフォーマット自動判定

compeito のフォーマット自動判定は `Is Child Of` または `Is Part Of` の存在で OpenSALT 形式と判定する（[csv-format.md](../spec/csv-format.md) 参照）。これらの列名は独自形式に存在しないため、`Identifier` 列名が共通でも区別可能。
