# Moodle competency CSV エクスポート 実装方針

> **ステータス: 設計レビュー済み（実装着手可）／バックログ入り・実装順は未定。**
> 設計は Codex によるレビューを 3 ラウンド経て確定済み（[backlog.md](../backlog.md) 参照）。
> 実装に着手する際はこのドキュメントの方針に従う。

> 目的: compeito の CFDocument を **Moodle のコンピテンシーフレームワーク取り込み**（管理 > コンピテンシー >
> フレームワークのインポート、プラグイン `tool_lpimportcsv`）にそのまま読み込める CSV として出力する。
> 新しいエクスポート profile `moodle` を追加する。

## 決定事項（ユーザー確認済み）

- **Scale**: 既定の2段階を固定出力（`Not yet competent,Competent`、上位を default かつ proficient）。CASE 側に尺度が無いため。
- **ID number（ツリー解決キー）**: `humanCodingScheme` 優先、無ければ UUID にフォールバック。ファイル内一意も担保。
- **提供範囲**: CLI の `export csv --profile moodle` のみ（Web UI 導線は今回入れない）。

## Moodle 取り込み CSV 形式（事実）

`tool_lpimportcsv` の正準形式は **14 列・固定順**（取り込み時に列マッピング確認があるため列名は緩いが順序が正準）。
本実装はエクスポートが正準形式となる Moodle の方針に合わせ、**正準ヘッダ行を出力**する。

列順（0-13）:
`Parent ID number, ID number, Short name, Description, Description format, Scale values, Scale configuration,
Rule type (optional), Rule outcome (optional), Rule config (optional),
Cross-referenced competency ID numbers, Exported ID (optional), Is framework, Taxonomy`

- ツリーは **Parent ID number → ID number（idnumber 文字列）**の一致で再帰解決。トップは Parent 空。
- **`Is framework=1` の行（= フレームワーク本体）にのみ Scale/Taxonomy を載せる**。Moodle は framework 行が無い時だけ失敗（厳密に1つを要求はしない）。本実装は正準出力として1行固定で出す（詳細は「出力する行の構成」）。
- Scale values=カンマ区切り（低→高）。Scale configuration=JSON。Rule 列は空/0/`null`（文字列）で無効化。
- `Cross-referenced competency ID numbers`=related の idnumber をカンマ区切り、値内カンマは `%2C` エスケープ。
- 文字コード UTF-8、標準 CSV ダブルクオート（フィールド内 `"`→`""`、改行は引用フィールドで可）。

## 出力する行の構成

> **Is framework について（表現の正確化）**: Moodle importer は framework 行が**無い**場合のみ失敗し、複数あると最後の
> framework 行で上書きされ得る（「ちょうど1つを厳密要求」ではない）。本実装は **compeito の正準出力として framework 行を1行固定で出す**。

1. **フレームワーク行（1行・正準）** ← CFDocument:
   - Is framework=`1`
   - ID number = CFDocument.identifier（UUID。doc に humanCodingScheme は無い）
   - Short name = CFDocument.title（100字に切詰）
   - Description = CFDocument.description / format=`1`(HTML)
   - Scale values = `Not yet competent,Competent`
   - Scale configuration = `[{"scaleid":"1"},{"id":2,"scaledefault":1,"proficient":1}]`
     （公式 fixture と同形＝**flagged item のみ**を列挙し互換性を最大化。先頭の `scaleid` はプレースホルダで取込時に実 scale id へ
     置換される。`id:2` = 1始まり序数で上位=Competent を default かつ proficient に。importer は `scaledefault`/`proficient` が
     最低1つあるかだけ検証するので flagged のみで十分）
   - Taxonomy = `competency`（深い階層は Moodle が `competency` にフォールバックするため単一語で十分。CFItemType ベースの
     写像は per-depth 制約と CFItemType の自由文字列性から近似になるので**今回は採用せず**、将来拡張として記録）
   - Rule/related 列は空
2. **コンピテンシー行（N行）** ← 各 CFItem（既存 `_load_document_tree`/`_build_tree_order` の DFS 順）:
   - Parent ID number = 親 CFItem の idnumber（トップレベル項目は空。※フレームワークの idnumber は親に使わない）
   - ID number = 後述の idnumber 解決
   - Short name = `abbreviatedStatement` → 無ければ idnumber → 無ければ fullStatement 切詰（必須・100字）
   - Description = fullStatement / format=`1`
   - Scale 列は空（コンピテンシー行は尺度を持たない）
   - Cross-referenced = `isRelatedTo` の相手の idnumber、`,`区切り・`%2C`エスケープ。**同一 CSV 内に出力された CFItem に限定**
     （= 解決済み idnumber 写像に存在する相手のみ。後述「related のフィルタ」）。`exemplar` 等は畳み込まず **`isRelatedTo` のみ**に限定（保守的・意味の取り違え回避）
   - Exported ID = **空**（Moodle では rule config migration 用の内部 ID であり、related の解決には使われない。本実装は Rule 非対応なので空でよい。将来 Rule 対応時に通し番号を入れる）
   - Is framework 空 / Taxonomy 空 / Rule 列は空

## idnumber 解決ロジック（要・一意性担保）

Moodle はツリーを idnumber 文字列で解決するため**ファイル内で一意**でなければならない。

1. 候補 = `humanCodingScheme`（trim 後、非空なら）／無ければ UUID 文字列。
2. 候補が**重複**する場合（humanCodingScheme の重複・空多数）は、衝突した行を **UUID にフォールバック**して一意化する。
3. 最終 idnumber は 100 字に切詰（Moodle 仕様）。切詰で再衝突する稀ケースも UUID フォールバックで回避。
4. Parent ID number と Cross-referenced も**同じ解決結果**を参照する（CFItem.identifier → 解決済み idnumber の写像を1度作って全行で共有）。

## 変更するファイル

| ファイル | 変更内容 |
|---|---|
| `src/services/csv_export_service.py` | `MOODLE_CSV_HEADER` 定数、`export_moodle_csv()` を追加。`_load_document_tree` を再利用。related は曖昧さ回避のため **Moodle 用に association records を直接読む**（または `_load_outgoing_associations` を使うなら、返却 token が doc 外で URI に変換済みである点に注意し「token が id_map に存在するものだけ採用」とする）。idnumber 解決ヘルパを内部に追加 |
| `cli.py` | `export csv` の `--profile` 検証に `moodle` を追加、分岐に `export_moodle_csv` を配線、import 追加 |
| `cli.py` の i18n（`t()` 文字列） | profile 検証エラー文言が既存の汎用 `err_invalid_profile` で賄えるか確認。新規メッセージが要るなら EN/JA 両方追加 |
| `tests/unit/test_csv_export.py` | Moodle 形式の単体テスト追加 |
| `docs/spec/csv-format.md` | "Moodle competency format" セクション（列対応表・階層・scale/idnumber 規則・example）を EN/JA で追加 |
| `docs/spec/cli.md` | `export csv` に `--profile moodle` を追記 |
| `docs/spec/round-trip-fidelity.md` | Moodle 経路は**一方向・lossy**（UUID 以外の多くの CASE 固有フィールドを保持しない）と明記。related は `isRelatedTo` のみを Moodle Cross-referenced に出し、`exemplar` 等他の association type・doc 外参照は落とすことを記載 |

## 考慮すべきエッジケース

- **idnumber 衝突**: humanCodingScheme が重複/空 → UUID フォールバックで一意化（上記ロジック）。テスト必須。
- **空のドキュメント（CFItem 0 件）**: フレームワーク行のみ出力（Moodle 的に有効）。
- **トップレベル項目の親**: Parent ID number は空にする（フレームワーク idnumber を入れない）。
- **related の相手がドキュメント外（must-fix）**: 既存 `_load_outgoing_associations` は**doc 外ターゲットを `destination_node_uri`（URI）に変換して残す**（doc 内に絞っていない／返却 token は identifier とは限らない）。Moodle は同一 CSV 内の idnumber しか解決できないため、related は **`destination_node_identifier` が解決済み idnumber 写像（id_map）に存在するものだけ**にフィルタする。曖昧さを避けるため Moodle 出力では association records を直接読み、`destination_node_identifier` を id_map で引く実装が無難。URI のみ/外部参照は出力しない。
- **related 値内のカンマ**: idnumber に `,` が含まれうる（humanCodingScheme 自由文字列）→ `%2C` エスケープ。
- **Short name / idnumber の 100 字超**: 切詰。切詰後の idnumber 再衝突は UUID フォールバック。
- **fullStatement の HTML/改行**: Description は HTML 可（format=1）。CSV 引用で改行を保持。
- **Description が空**: 空文字で出力（任意列）。
- **CFItem に humanCodingScheme も abbreviatedStatement も無い**: idnumber=UUID、shortname=fullStatement 切詰（fullStatement は必須なので常に存在）。
- **idnumber/shortname が空にならないこと**: Moodle は `idnumber` か `shortname` が空だと competency を作らない。切詰後も空にならないよう保証する（idnumber は UUID フォールバックで非空、shortname は fullStatement 由来で非空）。
- **CLI の行数カウント**: 既存の `export csv` は結果に行数を表示し、現状 `Identifier,` ヘッダ行のみ除外している。`--profile moodle` では **Moodle ヘッダ行とフレームワーク行を件数から除外**し、コンピテンシー行数（= CFItem 数）を表示する方針にする（分岐で明示）。

## テスト方針（`tests/unit/test_csv_export.py`）

既存の CSV エクスポートテストに倣い、DB に CFDocument+CFItem+CFItemType+CFAssociation を投入して `export_moodle_csv` を呼ぶ。
アサーションは行を CSV パースして列インデックス/値で検証（文字列完全一致に依存しない）。

- ヘッダが `MOODLE_CSV_HEADER`（14 列・正準順）と一致。
- フレームワーク行が1行・Is framework=1・Scale values/Scale configuration を持つ。Scale config JSON が妥当（flagged item のみ・上位 proficient+default）。
- コンピテンシー行は Is framework 空・Scale 列空。
- 階層: 子の Parent ID number が親の ID number と一致。トップレベルは Parent 空。
- idnumber: humanCodingScheme があればそれ、無ければ UUID。
- **idnumber 衝突**: 同一 humanCodingScheme を持つ 2 項目 → 少なくとも一方が UUID にフォールバックし、ファイル内で全 idnumber が一意。
- **100字切詰後の衝突**: 先頭100字が同一になる長い humanCodingScheme 2 項目 → UUID フォールバックで一意化。
- **humanCodingScheme の trim / 空白のみ**: 前後空白は trim、空白のみは空扱い → UUID。
- related: isRelatedTo が Cross-referenced 列に相手 idnumber で出る。値内カンマが `%2C`。**doc 外ターゲット（id_map に無い相手）は出力されない**。
- カンマを含む idnumber の扱い: **`%2C` エスケープは `Cross-referenced`（related）のリスト要素だけ**に適用する。Moodle importer は related のみ `explode(',')` 後に `%2C`→`,` を戻す。**`Parent ID number` は単一フィールドなので通常の CSV quoting で足り、`%2C` にすると親解決が壊れる**。parent はカンマを含んでも素の値＋CSV quoting で出す。テストで parent（素）と related（`%2C`）の両方を検証。
- Exported ID は空。
- Short name 100 字切詰。切詰後も shortname・idnumber が**空にならない**。
- 空ドキュメント: フレームワーク行のみ。
- CLI: `export csv --profile moodle` が `export_moodle_csv` を呼び、表示件数が CFItem 数（ヘッダ/フレームワーク行を除外）になる。

## 非対象（今回やらないこと）

- Moodle 形式の**インポート**（取り込みは Moodle 側で行う前提。compeito は出力のみ）。
- Web UI のエクスポート導線。
- CFItemType → Moodle taxonomy の精緻な写像（将来拡張）。
- Rule（competency_rule_*）の生成。
- CFRubric からの scale 導出（今回は既定固定）。
