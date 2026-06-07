# CLI import/export コマンド再設計メモ（議論用ドラフト）

> ステータス: **方針確定（実装待ち）**。OpenSALT Excel (.xlsx) import/export 追加に先立ち、乱立した import/export コマンドの命名を整理する。下記「確定事項」を正とする。

## 確定事項（2026-06-07 合意）

1. **命名モデルは Model A（コンテナ先頭）** を採用
2. **コンテナ名は `xlsx`**（`excel` は Microsoft 商標を避け、拡張子と一致するベンダー中立な `xlsx` を採用）
3. **`csv-rubric` → `rubric` に改名**
4. **方言オプションは `--profile`**（`--format` から改名。フォーマットはコマンド名が表すため）
5. **`import csv` に明示 `--profile` override を足す**（今回入れる。自動判定はデフォルトのまま、指定時は確定パース＋不一致はエラー）
6. **compeito-aws は別途あちら側で追従修正**（compeito は気にせず rename してよい）
7. **破壊的変更を許容**（まだ本番導入先が無いため、エイリアス無しのクリーンブレイクで進める）

全項目確定。実装に進む。

## 背景・目的

OpenSALT round-trip の調査（[round_trip_status.md](round_trip_status.md)）で、faithful な OpenSALT 相互運用には **Excel (.xlsx)** の import/export を compeito に足す必要があると判明した。実装に入る前に、既存の import/export コマンドの命名が複数の軸を混ぜていて整理が必要なので、本メモで方針を固める。

## 現状インベントリ

### import
| コマンド | ソース | 形式/方言 | 対象リソース | オプション |
|---------|--------|-----------|------------|-----------|
| `import csv` | file | custom / opensalt / simple（**自動判定**） | framework | `--tenant --file --doc --doc-title --doc-version` |
| `import case-url` | **URL** | CASE JSON (v1.1/v1.0) | framework | `--tenant --url --doc` |
| `import case-file` | **file** | CASE JSON | framework | `--tenant --file --doc` |
| `import csv-rubric` | file | rubric CSV | rubric | `--tenant --doc --file` |

### export
| コマンド | シンク | 形式/方言 | 対象リソース | オプション |
|---------|--------|-----------|------------|-----------|
| `export csv` | file | custom / opensalt（`--format`） | framework | `--tenant --doc --file --format` |
| `export case` | file | CASE JSON (v1.1) | framework | `--tenant --doc --file` |
| `export csv-rubric` | file | rubric CSV | rubric | `--tenant --doc --file` |

## 問題点 — 命名軸の混在

コマンド名が次の **4 つの独立した軸**を一貫性なく名前に混ぜている:

1. **コンテナ/形式**: `csv` / `case`(=JSON) / これから足す Excel
2. **ソース/シンク**: file / URL → `case-url` / `case-file` だけが名前に出ている
3. **方言**: custom / opensalt → export では `--format` フラグなのに概念として名前にも滲む
4. **対象リソース**: framework / rubric → `csv-rubric` で連結

具体的な不整合:

- **CASE だけ source を名前に持つ** (`case-url` / `case-file`)。一方 export は `case` 一本で非対称。本来 source は `--url` / `--file` オプションで表すべき（`import csv` は file 限定でそうしている）。
- **方言がフラグだったり名前だったり**。`export csv --format opensalt` はフラグ。では Excel は？ xlsx は CSV ではないので `--format` には乗らず別コマンドが要る → 「OpenSALT は方言なのかコンテナなのか」という破綻が顕在化する。
- **`csv-rubric` がコンテナ + リソースの連結**。rubric は CSV のみ（CASE JSON では CFRubrics として framework に内包、OpenSALT Excel には rubric シートが無い）。`csv` の隣に `csv-rubric` が並ぶと読みにくい。

## 設計原則（提案）

1. **コマンド = コンテナ/形式**（`csv` / `excel` / `case`）。最も具体的で、ファイル拡張子と一致し、ユーザーが最初に意識する単位。
2. **ソース/シンクは option**（`--file` / `--url`）。名前に出さない。
3. **方言は option**（`--profile`）。CSV は `custom` / `opensalt`、xlsx は OpenSALT 一択なので不要。
4. **rubric は独立コマンド**（コンテナは暗黙的に CSV）。

## 確定スキーム（Model A: コンテナ先頭）

```
# import
import csv     --tenant --file [--doc ...] [--doc-title ...] [--doc-version ...] [--profile auto|custom|opensalt|simple]
              # --profile 省略時は auto（自動判定・現状互換）。明示時は確定パースし不一致はエラー
import xlsx    --tenant --file [--doc ...]            # 🆕 OpenSALT .xlsx（3シート・フル）
import case    --tenant (--file | --url) [--doc ...]  # ♻️ case-url / case-file を統合
import rubric  --tenant --doc --file                  # ♻️ csv-rubric から改名

# export
export csv     --tenant --doc --file [--profile custom|opensalt]   # ♻️ --format → --profile
export xlsx    --tenant --doc --file                               # 🆕 OpenSALT .xlsx
export case    --tenant --doc --file                               # 現状維持
export rubric  --tenant --doc --file                               # ♻️ csv-rubric から改名
```

- `xlsx` = **OpenSALT の本命形式（フル）**、`csv --profile opensalt` = **OpenSALT 方言の CSV（lossy: CFItemType / educationLevel が落ちる）** と help で明示的に区別する。
- 破壊的変更（エイリアス無し・許容済）: `case-url` / `case-file` 廃止（→ `case --url/--file`）、`csv-rubric` → `rubric`、`export csv --format` → `--profile`。

## 代替案（Model B: 相互運用先頭）

「どのシステムと交換するか」を先頭に置き、コンテナを `--as` で選ぶ案:

```
import opensalt --file [--as csv|xlsx]   # 拡張子で自動判定も可
import case     (--file | --url)
import compeito --file                   # 旧 import csv (custom)
export opensalt --file [--as csv|xlsx]
export case     --file
export compeito --file
```

- 長所: OpenSALT の 2 コンテナ（csv/xlsx）が 1 コマンドに集約され、「OpenSALT と往復する」というメンタルモデルに合う。
- 短所: 現状からの乖離が大きい（`csv` → `compeito` / `opensalt`）。`compeito` / `simple` をコマンド名にするのは座りが悪い。

→ 現状維持度・直感性から **Model A を推奨**。

## Excel 固有の論点

- **依存追加**: xlsx 読み書きに `openpyxl`（または同等）が要る。pyproject に追加。
- **形式**: OpenSALT Excel は 3 シート（CF Doc / CF Item / CF Association）。詳細は [round_trip_status.md](round_trip_status.md) の OpenSALT 節。compeito の DB に無い `smartLevel`（階層）・`notes` 等の扱いを import/export ロジックで詰める必要あり（別途）。
- **命名**: `xlsx` に確定。「Excel」は Microsoft の登録商標で、`xlsx`（Office Open XML 拡張子）はベンダー中立かつ拡張子と一致するため安全側。
- **Web UI**: compeito には Web UI もある。Excel export を UI のダウンロードにも出すかは別スコープ（本メモは CLI に限定）。

## 後方互換

ユーザー方針: **エイリアスなしのクリーンブレイクで可**。

- 影響を受ける repo 内資産: `seed/seed.sh`（`import csv` / `import csv-rubric` を使用）、`docs/spec/cli.md`、`docs/guide/*`（initial-setup / opencase-interop）。rename と同時に更新する。
- `import csv` / `export csv` / `export case` は名前が変わらないので大半の手順は影響なし。実質 `csv-rubric` → `rubric` と `case-url/case-file` → `case` の追従のみ。

## クロスリポジトリ影響（compeito-aws）★要確認

調査結果:

- **ランタイム依存はない**。compeito-aws は**独自の `cli.py`**（Admin API を HTTP で叩く運用 CLI）を持ち、compeito の `cli.py` を呼ばない。よって compeito 側の CLI を rename しても **compeito-aws は壊れない**。
- ただし compeito-aws は**同じ命名語彙を意図的にミラー**している:
  - aws `cli.py` コマンド: `import csv` / `import csv-rubric` / `import case-url` / `import case-file` / `export csv` / `export case`
  - Admin API ルートパス（`src/admin/router.py`）: `/import/csv`, `/import/csv-rubric`, `/import/case-url`, `/import/case-file`, `/export/csv`, `/export/case`
- したがって compeito を rename すると、整合のため compeito-aws を **lockstep で更新**したくなる。特に **Admin API のパス rename は HTTP の破壊的変更**（デプロイ済みクライアント・テストに影響）。
- **Excel 対応も AWS モードで使うなら**、後日 compeito-aws の Admin API（`/import/excel`・`/export/excel`）と CLI にミラーが必要（追加スコープ）。

**決定**: compeito 側は本メモの確定スキームで rename する。**compeito-aws の追従（独自 cli.py / Admin API path / tests / docs の命名合わせ、Admin API パス rename を含む）は compeito-aws 側で別途対応する**。compeito からは compeito-aws の都合を気にせず進めてよい。Admin API パス rename（HTTP 破壊的変更）は本番導入先が無いため許容。

> compeito-aws 側 TODO（あちらのセッションで対応）: `cli.py` の `case-url`/`case-file`/`csv-rubric` 改名、Admin API ルート `/import/case-url` 等の rename、`tests/`・`docs/`（architecture.md / admin-api.md / cli.md / roadmap.md）追従。さらに Excel を AWS モードで使うなら `/import/xlsx`・`/export/xlsx` と CLI の追加。

## 未決事項

なし（全項目確定）。次は実装計画へ。`import csv --profile` は `auto`（既定・自動判定）を加えた 4 値とし、明示時はその profile で確定パース、シグナル不一致ならフォールバックせずエラーとする。
