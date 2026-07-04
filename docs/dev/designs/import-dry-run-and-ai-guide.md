# import の dry-run・確認ガード・validation report ＋ AI 変換ガイド 実装方針

> **ステータス: 設計ドラフト（レビュー前）**
>
> 目的: compeito の書き込みは CLI import のみ（攻撃面削減の意図的設計。Web インポート UI は作らない）。
> コンテンツ編集の想定フローは「設計者の Excel 元データ → 生成 AI が CASE JSON / CSV へ変換 → CLI で import」。
> AI 変換は速いが間違え方が独特（UUID 捏造・列の勝手な補完・部分出力等）なので、**受け取る側の安全網**に投資する。
> 2026-07 外部レビューの **L1**（CSV 部分再インポートで既存の関連が黙って消える罠に確認ガードがない）も本件で解消する。

## 決定事項

- **`--dry-run`**: 全 import コマンド（`import csv` / `import xlsx` / `import case` / `import rubric`）に追加。
  実装方式は **rollback 方式**（実 import をトランザクション内で最後まで実行し、commit の代わりに rollback）。事前差分計算方式は採らない（後述の比較）。
- **確認ガード（L1）**: dry-run なしの実行でも、**破壊的変更**（再作成されない関連の消失・他ドキュメントからの項目移動）が検知されたら
  commit 直前に確認プロンプトを出す。閾値は **1**（= 1 件でも失われるなら確認）。非対話環境向けに `--yes` フラグ。
- **破壊的変更の定義**: (a) 削除された関連のうち **(associationType, origin, destination) の組で再作成されないもの**（lost links）、
  (b) **他ドキュメントからの CFItem 付け替え**（items moved）。単純な「削除件数」ではなく **net loss** で判定する
  （document-level rebuild は更新のたびに全削除→再作成するため、削除件数そのものでは毎回プロンプトが出て形骸化する）。
- **validation report**: `--report <path>` で構造化 JSON を出力。警告を `code` 付きの issue に構造化する
  （既存の `warnings: list[str]` は互換維持のため派生プロパティとして残す）。
  strict 出力設計（[designs/strict-output.md](./strict-output.md)、並行作成中）の **C3 対応候補 (a)「import 時 validation report」の実装**を兼ねる。
  required 欠落（CFDocument.creator 等）の一覧化を含む。
- **AI 向け変換ガイド**: `docs/guide/ai-conversion.md` を新規作成（成果物その2）。本文は日本語、
  AI に渡すプロンプトテンプレートとルール箇条書きは **EN/JA 併記**。
- **import の寛容さは維持**: skip-and-warn の既存挙動は変えない（reject 化しない）。

## 背景（実コードの確認結果）

### トランザクション構造（dry-run の実装根拠）

- 4 つの import コマンドはすべて `cli.py` 内で `_get_session()` → サービス呼び出し → **CLI 側で `await session.commit()`** という構造
  （[cli.py](../../../cli.py) の `import_csv_cmd` / `import_xlsx_cmd` / `import_case` / `import_csv_rubric_cmd`）。
  サービス（`import_csv` / `import_xlsx` / `import_case_from_dict` / `import_case_package` / `import_rubric_csv`）は
  `flush()` のみで commit しない（docstring にも "caller manages transaction" と明記）。
- したがって **commit をスキップして rollback するだけで dry-run が成立**する。サービス層の変更は不要
  （`_get_session` は commit しなければ close 時に暗黙 rollback だが、明示的に `await session.rollback()` する）。
- 更新時は Step 3 で対象 CFDocument に `SELECT ... FOR UPDATE` を取り、トランザクション終了まで保持する
  （[import-logic.md](../../spec/import-logic.md) 参照）。dry-run では rollback でロックも解放される。

### 各 import の削除・破壊挙動（何を「破壊的」と数えるか）

| 経路 | 削除しうるもの | 実コード根拠 |
|---|---|---|
| `import csv` | **更新時（データ行 ≥1）**: ① 当該ドキュメントの **isChildOf 全削除→再生成**（`existing_is_child_of_deleted`）。② **ヘッダに列が存在する associationType** をドキュメント全体で削除→再生成（`existing_associations_deleted`）。列が無い type は温存 | `csv_import_service.py` Step 7 / Step 7.5 |
| `import xlsx` | 内部で custom CSV に変換して `import_csv` を呼ぶため **①と同じ**（smartLevel 由来の parentIdentifier 列は常に存在）。CF Association シートの第2パスは「存在しなければ作成」のみで削除しない | `xlsx_import_service.py` `import_xlsx` / `_import_associations` |
| `import case` | **削除なし**（additive-only upsert。「外部ソースに無いリソースは消さない」仕様）。ただし tenant-wide identifier マッチにより **CFItem / CFAssociation の他ドキュメントからの付け替え（move）** が起こりうる | `case_import_service.py` / import-logic.md「--doc semantics」 |
| `import rubric` | **削除なし**（純 upsert） | `csv_rubric_import_service.py` |

- **L1 の罠の実体**: 部分 CSV（一部項目を省いたもの）を `--doc` / `#identifier` / OpenSALT `Is Part Of` 経由で再インポートすると、
  ① 省かれた項目の isChildOf も全削除の対象になり再作成されない → その項目は orphan としてルート depth=0 に浮く。
  ② 省かれた項目が持っていた present-type の関連（isRelatedTo 等）も黙って消える。既存実装は削除件数を report に載せるだけで確認は無い。
- **item move**: CSV の Identifier / CASE の identifier が **テナント内の別ドキュメントの既存項目**に一致すると、その項目を現ドキュメントへ付け替える
  （警告 "Item '...' moved from document '...' to current document"）。AI が UUID を捏造・コピペした場合にまさに起きる事故であり、
  移動元ドキュメントの木を壊すため破壊的変更に含める。**CFItem が import で完全削除されることは無い**（どの経路にも item delete は存在しない）。

### 警告機構の現状

- 警告はすべて `list[str]` に英語文字列で蓄積（`ImportReport.warnings` / `CaseImportReport.warnings` / `RubricImportReport.warnings`）。
  CSV パーサ内部は `warnings: list[str]` を引数で引き回す。CLI は `report.warnings` を黄色で列挙表示するのみ。
- required 欠落の警告は既にある: `case_import_service._create_document` /`_update_document` の
  "CFDocument '...': creator is missing (CASE v1.1 requires it); ..."。これを report で機械可読にするのが C3 (a)。
- CLI の i18n は `src/i18n.py` の `t()` ＋ `src/locales/cli_en.json` / `cli_ja.json`。確認プロンプトの先例は
  `tenant delete` / `doc delete`（`click.prompt` + `prompt_delete_*` キー、拒否時 `msg_cancelled` + `SystemExit(2)`、スキップは `--force`）。
  import 系は既存の `--force` ではなく、意味を明確にするため **`--yes`** を採用する（削除コマンドの `--force` は据え置き）。

## アプローチ

### 1. `--dry-run`（rollback 方式）

**方式比較（rollback 方式 vs 事前差分計算方式）:**

| 観点 | rollback 方式（採用） | 事前差分計算方式 |
|---|---|---|
| 件数の正確さ | 実コードパスそのもの → 完全一致 | upsert/照合ロジック（Identifier→HCS フォールバック、move、find-or-create…）を二重実装する必要があり、乖離リスク大 |
| 警告の再現 | 本番と同一 | 別実装になり差が出る |
| 実装コスト | CLI に分岐を足すだけ | サービス全体の差分版が必要 |
| 実行コスト | 本番 import と同等の時間・DB 書き込み（rollback される） | 読み取りのみで速い |
| 副作用 | FOR UPDATE ロックを実行中保持（rollback で解放）。`import case --url` はネットワーク取得を行う | なし |

書き込みは全て同一トランザクション内で rollback されるため DB は不変。import 系サービスに DB 外の副作用（ファイル書き込み等）は無い。
実行コストとロック保持は CLI 用途では許容範囲 → **rollback 方式を推奨・採用**。

**CLI の共通フロー**（4 コマンド共通のヘルパ `_finalize_import()` を `cli.py` に追加して重複排除する）:

```
report = await import_xxx(session, ...)        # 既存のサービス呼び出し（flush 済み）
destructive = _destructive_summary(report)     # lost links / items moved を集計
if report_path: レポート JSON を書き出し        # dry-run でも書く（applied フラグで区別）
if dry_run:
    サマリ表示 + t("msg_dry_run_no_changes") 表示
    await session.rollback(); return (exit 0)
if destructive.total >= 1 and not yes:
    非TTY なら err_confirm_noninteractive → rollback, exit 1
    click.prompt(t("prompt_destructive_import", ...))  # 既定 N
    拒否 → msg_cancelled, rollback, exit 2
await session.commit()
サマリ表示（既存どおり）
```

- 新オプション（4 コマンド共通）: `--dry-run`（flag）、`--yes`（flag）、`--report <path>`（`click.Path()`。
  export 系と同じ「`touch`/`unlink` による書き込み可能性の事前チェック」を行う）。
- dry-run 時のサマリは既存の `msg_items_summary` 等をそのまま使い、削除系
  （`existing_is_child_of_deleted` / `existing_associations_deleted` / lost links / items moved）と警告一覧を追加表示する。
  **現状 CLI は削除件数を表示していない**（report にはあるが未表示）ので、dry-run/実実行の両方で表示するようにする（新キー `msg_assoc_deleted_summary`）。
- 注意（表示にも一言添える）: dry-run で自動採番された UUID（新規 CFDocument / CFItem / CFAssociation の identifier）は
  **本実行では別の値になる**（uuid4 再生成）。`#identifier` 等で固定した identifier は一致する。
- `import case --url --dry-run` はリモート取得を実行する（DB 変更なしの保証のみで、ネットワーク副作用は対象外と明記）。

### 2. 確認ガード（L1 対応）

**判定は commit 直前（サービス実行後・同一トランザクション内）に行う「commit ゲート」方式。**
実行前の事前推定はしない — 削除範囲は「ヘッダにどの列があるか」「何行が有効か」等に依存し、事前計算は dry-run と同じ二重実装問題を持つ。
サービスを 1 回だけ実行し、report の実測値で判定 → 承認なら commit、拒否なら rollback。二重実行も不要。

**破壊的変更の集計（report 側に材料を追加する）:**

- `csv_import_service.import_csv` の Step 7 / 7.5 で、削除した既存関連の `(association_type, origin_node_identifier, destination_node_identifier)`
  タプル集合を記録し、再作成した関連の同タプル集合との差集合を **lost links** とする:
  - `report.lost_associations_count: int` — `len(deleted_tuples - created_tuples)`
  - `report.lost_associations_sample: list[tuple[str, str, str]]` — 先頭 20 件（プロンプト・レポート表示用）
  - origin/destination はどちらも既に小文字 UUID 正規化済みの文字列カラム由来なのでそのまま比較できる。
  - これにより「並び替え・親変更だけの再インポート」（同一タプルが再作成される）はガードに掛からず、
    「項目を省いた部分 CSV」（省いた項目のタプルが再作成されない）だけが掛かる。sequence_number は比較キーに含めない（並び替えは破壊ではない）。
- `items_moved: int` を `ImportReport` と `CaseImportReport` の両方に追加（現状は警告文字列のみ）。
  `_upsert_item`（CSV）と `_import_items` / `_import_associations`（CASE）の move 警告箇所でインクリメント。
  CASE 側の association move もカウントする（`associations_moved: int`）。
- xlsx は `import_csv` 経由なので lost links / items_moved を自動的に得る。rubric は削除・move が無いのでガード対象外（フラグは受けるが常に非発火）。

**ガード発火条件**: `lost_associations_count + items_moved + associations_moved >= 1`（閾値は固定値 1。
調整フラグは今回入れない — 自動化は `--yes` で明示するのが方針。将来必要なら `--threshold` を検討）。

**プロンプト文言（例・EN）**:
`This import will permanently delete {lost} existing association(s) that will not be re-created and move {moved} item(s)/association(s) from other documents. Continue? [y/N]`
（JA: 「再作成されない既存の関連 {lost} 件が削除され、他ドキュメントからの移動が {moved} 件発生します。続行しますか? [y/N]」）
発火時は lost links のサンプル（type / origin / destination、最大 20 件）と move 対象を先に表示する。

**非対話環境**: `sys.stdin.isatty()` が偽で `--yes` が無い場合、プロンプトを出さずに
`err_confirm_noninteractive`（「破壊的変更が検知されました。--yes で承認するか --dry-run で内容を確認してください」）を表示し
rollback + exit 1。CI・スクリプトが黙って先に進むこと・ハングすることの両方を防ぐ。

**回答の扱い**: 既存の delete 系と同じ（`click.prompt` 既定 "N"、`y`/`yes` のみ承認、拒否は `msg_cancelled` + `SystemExit(2)`）。

**留意点（仕様として明記）**: プロンプト表示中も FOR UPDATE ロックとトランザクションを保持する。同一ドキュメントへの並行 import は
回答までブロックされる（むしろ整合的）。DB 側に `idle_in_transaction_session_timeout` が設定されている環境では放置でセッションが切られうる。

### 3. validation report（`--report <path>`、strict-output C3 (a)）

**警告の構造化**: 新モジュール `src/services/import_issues.py` を追加。

```python
@dataclass
class ValidationIssue:
    severity: str                 # 当面 "warning" 固定（将来 "error" を追加可能に）
    code: str                     # 安定した snake_case コード（下表）
    message: str                  # 既存の英語警告文そのまま（メッセージは英語標準化の既存方針を踏襲）
    row: int | None = None        # CSV 行番号（該当時）
    resource_type: str | None = None   # "CFItem" / "CFAssociation" / "CFDocument" / ...
    identifier: str | None = None      # 対象リソースの identifier（該当時）
```

- 3 つの report dataclass（`ImportReport` / `CaseImportReport` / `RubricImportReport`）に `issues: list[ValidationIssue]` を追加し、
  `warnings` は **`@property` に変更**して `[i.message for i in self.issues]` を返す（フィールドとしては削除）。
  既存テスト・CLI 表示・`report.warnings.append(...)` 呼び出しは動かなくなるため、**全 append 呼び出し箇所を
  `report.warn(code, message, row=..., resource_type=..., identifier=...)` ヘルパ（issues に追加）へ置換**する。
  CSV パーサ内部で `warnings: list[str]` を引き回している関数（`_parse_custom_rows` 等）は、
  同じ `.warn()` を持つ軽量コレクタ（または report 本体）を受け取るようシグネチャ変更する。
- **コード体系**: 既存警告 1 メッセージ種別 = 1 コード。実装時に registry（`import_issues.py` 内の定数群）として列挙する。代表例:

| code | 元メッセージ（例） |
|---|---|
| `required_field_missing` | "CFDocument '...': creator is missing (CASE v1.1 requires it); stored as null" ← **C3 (a) の主対象** |
| `invalid_identifier` | "Row N: Invalid Identifier 'xxx', skipped" / "Skipped CFItem: identifier is not a valid UUID..." |
| `duplicate_identifier` | "Row N: Duplicate Identifier 'xxx', overwriting Row M" |
| `invalid_association_type` | "Skipped CFAssociation: invalid associationType 'xxx'..." |
| `invalid_parent_identifier` | "Row N: parentIdentifier 'xxx' is not a valid UUID, treated as root" |
| `parent_not_found` | "Row N: Parent 'xxx' not found, treated as root" |
| `item_moved` | "Row N: Item 'xxx' moved from document 'yyy' to current document" |
| `assoc_target_not_found` | "Row N: {type} target 'xxx' not found in tenant; link built from identifier" |
| `self_reference` | "Row N: {type} references self, skipped" / parentIdentifier 自己参照 |
| `orphan_item` / `circular_reference` | depth 計算の orphan / cycle 警告 |
| `invalid_value` | 不正な日付・sequenceNumber・language 長超過・adoption_status・caseVersion 等の値系 |
| `metadata_only_csv` | "No data rows in CSV; metadata updated, ..." |

**JSON スキーマ**（キーは camelCase。`reportVersion` でスキーマ進化に備える）:

```json
{
  "reportVersion": 1,
  "command": "import csv",
  "generatedAt": "2026-07-04T12:34:56+00:00",
  "dryRun": true,
  "applied": false,
  "cancelled": false,
  "tenant": "e3b0c442-...",
  "source": "path/to/file.csv または URL",
  "document": { "identifier": "d86774f2-...", "title": "High School Curriculum" },
  "counts": {
    "itemsCreated": 120, "itemsUpdated": 34, "itemsSkipped": 3, "itemsMoved": 1,
    "associationsCreated": 154, "isChildOfDeleted": 150, "associationsDeleted": 12,
    "itemTypesCreated": 5, "...": "（各 report dataclass の全カウンタを camelCase で列挙。CASE では associationsUpdated / rubrics* 等、rubric では criteria* / levels* も含む）"
  },
  "destructive": {
    "lostAssociationsCount": 3,
    "lostAssociationsSample": [ { "associationType": "isRelatedTo", "origin": "aaa...", "destination": "bbb..." } ],
    "itemsMoved": 1,
    "associationsMoved": 0
  },
  "issues": [
    { "severity": "warning", "code": "required_field_missing", "message": "CFDocument 'd867...': creator is missing (CASE v1.1 requires it); stored as null", "row": null, "resourceType": "CFDocument", "identifier": "d867..." },
    { "severity": "warning", "code": "invalid_identifier", "message": "Row 102: Invalid Identifier 'abc', skipped", "row": 102, "resourceType": "CFItem", "identifier": null }
  ]
}
```

- `message` は英語固定（import-logic.md 冒頭の「エラー/警告メッセージは英語標準化」方針に従う。i18n はコンソール UI 文言のみ）。
- 書き出しタイミング: サービス呼び出しが正常に return した後（dry-run・確認拒否時も書く。`applied` / `cancelled` で区別）。
  `ValueError` で import 自体が失敗した場合はレポートは書かない（従来どおり stderr にエラー）。
- JSON 生成は `import_issues.py` に `build_report_json(report, *, command, tenant, source, dry_run, applied, cancelled) -> dict` を置き、
  dataclass のフィールド名を snake→camel 変換して counts に詰める（コマンド別の if 分岐を避ける）。

### 4. AI 向け変換ガイド（成果物その2: `docs/guide/ai-conversion.md` の内容設計）

対象読者: フレームワーク設計者（Excel で原案を持っている人）。本文は日本語、**プロンプトテンプレートとルール箇条書きは EN/JA 併記**
（AI への指示は英語の方が安定するケースがあるため、コピペで両言語使えるようにする）。構成:

1. **前提と全体フロー** — compeito の書き込みは CLI のみ。`Excel → (生成 AI) → CSV/CASE JSON → import --dry-run → report 確認 → 本番 import`。
2. **変換先形式の選び方**
   - **新規作成は custom CSV を推奨**: `Identifier` 列を**空にすれば UUID v4 が自動採番される**
     （実仕様確認済み: import-logic.md Step 4「`Identifier` is empty → auto-generate UUID v4」）。AI に UUID を作らせない。
   - **既存更新はエクスポート起点**: `export csv`（または `export case`）で全量を出し、それを AI に渡して編集させ、全量を再インポート。
     このとき初めて既存 UUID を使う（エクスポート由来なので捏造ではない）。
   - CASE JSON は identifier が**必須**（欠落・不正 UUID の CFItem は skip される）。AI に CASE JSON を新規生成させる場合は
     「全 identifier を新規 uuid4 で生成し、例示・仕様書・他文書から UUID をコピーしない」ことを明示指示する。
   - simple 形式はドラフト用（インデント階層のみ・メタデータ最小）。
3. **プロンプトレシピ（EN/JA テンプレート）** — 要素:
   - 形式仕様の提示: `docs/spec/csv-format.md` の該当節（custom 形式）と、可能なら**実エクスポート 1 件をお手本として添付**する。
   - 必須ルール（テンプレートに固定文言で入れる）:
     - "Leave the Identifier column empty for all new items. Never invent or copy UUIDs."（新規時）
     - "Include ONLY the columns for which the source data has values. Do not add association columns (isRelatedTo, isPeerOf, ...) unless the source explicitly defines those relations."（列を足すと**その type がドキュメント全体で delete+rebuild される**ため）
     - "Output the complete document every time — never a partial list of rows."（L1 の部分再インポート罠の予防）
     - "Output raw CSV (UTF-8), no commentary inside the file."
   - メタデータ行（`#title` / `#creator` / `#language` 等）の指定方法。`#creator` を入れておくと `required_field_missing` を予防できる。
4. **AI がやりがちなミス チェックリスト**（表: ミス / compeito 側で起きること / 予防・検知）:
   - **UUID 捏造**: 不正 UUID → 行 skip（`invalid_identifier`）。有効な UUID を捏造/コピペしテナント内既存項目に衝突 → **他ドキュメントから項目を奪う**（`item_moved`、確認ガードが検知）。予防: 新規は Identifier 空。
   - **列の勝手な補完**: 元データに無い関連列・値の創作。関連列はその type の**全削除→再構築**を引き起こす。予防: プロンプトで列を明示列挙、dry-run の `associationsDeleted` / `lostAssociations` を確認。
   - **階層のインデント崩れ（simple 形式）**: インデントは半角スペース 2 個 = 1 階層（タブは 2 スペース換算）。深さの飛び（0→2）は警告付きで直前項目の子扱い。予防: custom 形式 + parentIdentifier を推奨、`depth` 系警告を確認。
   - **associationType のスペル**: 正確な camelCase enum（`isChildOf` / `isPeerOf` / `isPartOf` / `exactMatchOf` / `precedes` / `isRelatedTo` / `replacedBy` / `exemplar` / `hasSkillLevel` / `isTranslationOf`、拡張は `ext:[a-zA-Z0-9.\-_]+`）。CASE JSON では不正 type は skip（`invalid_association_type`）。CSV では列名が一致しないと**その列ごと無視**される（エラーにならない）点を強調。
   - **区切り文字の混同**: `educationLevel` / `conceptKeywords` はカンマ区切り、関連列のターゲットは `|` 区切り。
   - **値形式**: 日付は `YYYY-MM-DD`、`language` は 10 文字以内、`#adoption_status` は `Draft`/`Private Draft`/`Adopted`/`Deprecated`。
   - **部分出力・途中省略**: 「(remaining rows omitted)」等の省略 → 部分再インポートで関連消失。予防: 行数を数えて元データと突き合わせ、dry-run の counts で確認。
5. **変換後の検証手順**: ① `import csv --tenant ... --file ... --dry-run --report report.json` → ② report を確認
   （counts が元データの行数と整合するか / `issues` が空か / `destructive.lostAssociationsCount` と `itemsMoved` が 0 か）→
   ③ 問題なければ dry-run を外して本番 import（更新時に確認プロンプトが出たら内容を読んで判断）→ ④ Web UI のツリーで目視確認。
6. **既存ドキュメント更新時の注意**（L1 の利用者向け説明）: 更新 import は「CSV に書いた木がドキュメントの木の全量」扱い。
   一部の項目だけ直したい場合も必ず**全量エクスポート → 編集 → 全量インポート**。

### 5. i18n（CLI メッセージ）

`src/locales/cli_en.json` / `cli_ja.json` に以下を追加（既存 `t()` 機構、Click ヘルプは import 時評価の既存パターン踏襲）:

- `help_dry_run` / `help_yes` / `help_report_file`（オプションヘルプ）
- `msg_dry_run_no_changes`（"Dry run: no changes were made to the database" / 「dry-run のため DB は変更されていません」）
- `msg_dry_run_note_uuid`（自動採番 UUID は本実行で変わる旨の注記）
- `msg_assoc_deleted_summary`（削除件数表示: isChildOf / その他関連）
- `msg_destructive_header`（lost links / moves のサンプル一覧見出し）
- `prompt_destructive_import`（確認プロンプト。`{lost}` / `{moved}` プレースホルダ）
- `err_confirm_noninteractive`（非 TTY で `--yes` 無しの中断メッセージ）
- `msg_report_written`（"Validation report written to {path}"）

report JSON 内の `message` は英語固定（前述）。プロンプト・サマリ等の**コンソール表示のみ** i18n 対象。

## 変更するファイル

| ファイル | 変更内容 |
|---|---|
| `cli.py` | 4 つの import コマンドに `--dry-run` / `--yes` / `--report` を追加。共通ヘルパ `_finalize_import()`（レポート書き出し→dry-run 分岐→確認ガード→commit/rollback、exit code 0/1/2）と `_destructive_summary()` を追加。削除件数のサマリ表示を追加 |
| `src/services/import_issues.py` **(新規)** | `ValidationIssue` dataclass、issue code registry、`build_report_json()`（counts の snake→camel 変換込み） |
| `src/services/csv_import_service.py` | `ImportReport` に `issues` / `items_moved` / `lost_associations_count` / `lost_associations_sample` を追加し `warnings` を property 化＋`warn()` ヘルパ。Step 7 / 7.5 で削除・再作成タプルを記録して lost links を算出。全 `warnings.append` を `warn()` へ置換（パーサ関数のシグネチャ変更含む） |
| `src/services/case_import_service.py` | `CaseImportReport` に `issues` / `items_moved` / `associations_moved` を追加（削除は無いので lost links は常に 0）。`warn()` 置換。creator 欠落警告に `required_field_missing` コードを付与 |
| `src/services/csv_rubric_import_service.py` | `RubricImportReport` に `issues` を追加、`warn()` 置換（破壊カウンタは不要） |
| `src/services/xlsx_import_service.py` | `import_csv` 経由のため report 拡張は自動継承。第 2 パスの `report.warnings.append` を `warn()` へ置換 |
| `src/locales/cli_en.json` / `cli_ja.json` | 上記 i18n キーを EN/JA 追加 |
| `docs/guide/ai-conversion.md` **(新規)** | §4 の内容設計に沿った AI 変換ガイド（本文 JA、プロンプト/ルールは EN/JA 併記） |
| `docs/spec/cli.md` | import 系 4 コマンドに `--dry-run` / `--yes` / `--report` と exit code（0/1/2）を追記 |
| `docs/spec/import-logic.md` | 「dry-run と確認ガード」「validation report」節を追加（lost links の定義、commit ゲート方式、report JSON スキーマ）。Step 7.5 の部分 CSV 注意書きにガードへの言及を追加 |
| `docs/dev/backlog.md` | 本設計の行を追加（設計→実装ステータス管理） |
| `tests/unit/test_csv_import*.py` ほか | `warnings` property 互換の確認、新カウンタ・lost links のテスト追加（詳細は下記） |
| `tests/unit/test_cli_import_guard.py` **(新規)** | dry-run / ガード / report の CLI レベルテスト（`CliRunner`） |

## 考慮すべきエッジケース

- **dry-run と自動採番 UUID**: 新規ドキュメント/項目の identifier は本実行で変わる。`#identifier` 固定時は一致。注記を表示（`msg_dry_run_note_uuid`）。
- **dry-run + `--yes`**: プロンプト自体が無いので `--yes` は無視（エラーにしない）。
- **`import case --url` の dry-run**: リモート取得は実行される（DB 不変のみ保証）。
- **メタデータのみ CSV（データ行 0）**: 既存のセーフガードにより削除ゼロ → ガード非発火（既存挙動を壊さない）。
- **並び替え・親付け替えのみの再インポート**: isChildOf は全削除→再作成されるが (type, origin, dest) タプルが一致
  （親変更分は差分になる — 親変更は destination が変わるため lost link として現れる。**親変更は CSV に明示的に書かれた編集**なので
  ガードに掛かるのは過剰検知だが、「旧親との関連が消える」のは事実であり安全側。ガイドとプロンプト表示で判断材料を出す）。
  → レビュー論点: 親変更を除外したい場合は「origin が今回 CSV に存在する行の lost link は除外」する緩和が可能。初版は安全側（含める）で出す。
- **重複タプル**: 同一 (type, origin, dest) の関連が複数あった場合、set 比較では件数減が見えない。頻度が低く安全性への影響も小さいので許容（明記）。
- **ガード発火→承認までロック保持**: 同一ドキュメントへの並行 import はブロック。`idle_in_transaction_session_timeout` 環境では切断されうる（ドキュメントに明記）。
- **非 TTY + ガード発火 + `--yes` 無し**: rollback + exit 1（ハング・黙認の両方を防止）。パイプ実行や CI がこの経路に入る。
- **`--report` のパスが書けない**: import 実行**前**に export 系と同じ writability チェックで exit 1（実行後に書けず結果が失われるのを防ぐ）。
- **import 自体が ValueError で失敗**: レポートは書かない（従来どおり stderr + exit 1）。
- **rubric import**: 破壊操作が無いためガードは常に非発火。`--dry-run` / `--report` は有効。
- **`warnings` property 化の互換性**: `report.warnings` を読むコード（CLI・テスト）はそのまま動く。`warnings.append()` を直接呼ぶ箇所が
  残っていると AttributeError になるため、置換漏れを ripgrep で全数確認すること（`xlsx_import_service` の第 2 パス含む）。
- **exit code の一貫性**: 承認拒否 = 2（既存 `msg_cancelled` 系と同じ）、エラー = 1、成功/dry-run = 0。

## テスト方針

既存テストの流儀（Docker PostgreSQL + pytest-asyncio、`tests/unit/` にサービス直呼びテスト、CLI は `click.testing.CliRunner`）に従う。

- **dry-run が DB を変更しない**: 各経路（csv / xlsx / case(file) / rubric）で、dry-run 実行前後に
  cf_items / cf_associations / cf_documents / cf_rubrics の全行数・更新時刻が不変であること。新規・更新の両シナリオ。
- **dry-run の件数がそのまま本実行と一致**: 同じ入力で dry-run → 本実行し、report の counts（identifier 以外）が一致。
- **削除件数集計の正確さ**: 更新 import で `existing_is_child_of_deleted` / `existing_associations_deleted` が既存件数と一致（既存テストの拡張）。
- **lost links**:
  - 全量再インポート（同一 CSV）→ `lost_associations_count == 0`（ガード非発火）。
  - 部分 CSV（項目 1 つ省略）→ 省略項目の isChildOf と関連列由来の関連が lost に計上され、サンプルに (type, origin, dest) が入る。
  - 並び替えのみ（sequenceNumber 変更）→ lost 0。親変更 → lost 1（初版仕様どおり安全側で検知されること）。
- **items_moved**: 別ドキュメントの既存 item と同じ Identifier を持つ CSV / CASE JSON → `items_moved == 1` でガード発火。
- **確認プロンプト分岐**（`CliRunner` + `input=`）: `y` → commit されている / `N`（既定含む）→ rollback + exit 2 + `msg_cancelled` /
  `--yes` → プロンプト無しで commit / 非 TTY 相当（input 無し・isatty モック偽）+ ガード発火 → exit 1 + rollback。
- **report の JSON スキーマ**: `reportVersion` / `dryRun` / `applied` / `cancelled` / `counts`（camelCase 網羅）/ `destructive` / `issues[].code`。
  dry-run・確認拒否・通常成功の 3 パターンで `applied` / `cancelled` の組み合わせを検証。サンプルの 20 件キャップ。
- **required 欠落の構造化（C3 (a)）**: creator 無しの CASE JSON import → `issues` に `code == "required_field_missing"` /
  `resourceType == "CFDocument"` の issue が入り、report JSON に出力される。
- **`warnings` property 互換**: 既存の警告文字列アサーションが変更後も通ること（メッセージ文字列は変えない）。
- **i18n**: 新キーが `cli_en.json` / `cli_ja.json` の両方に存在すること（キー欠落はフォールバックで露見しにくいため明示テスト）。

## 非対象（今回やらないこと）

- **Web インポート UI**（設計方針として作らない。書き込みは CLI のみ＝攻撃面削減）。
- **import の reject 化**（skip-and-warn の寛容な取り込みは維持。severity "error" の導入は将来拡張）。
- `--clear-items`（メタデータのみ CSV での木の明示ワイプ。import-logic.md に既記載の将来項目のまま）。
- ガード閾値の調整フラグ（`--threshold` 等）。初版は固定 1 + `--yes`。
- export 系コマンドへの `--report`。
- CASE import の「外部に無いリソースの削除」（full sync）。additive-only は維持。
- 生成 AI による変換の自動実行（compeito が AI を呼ぶ機能は持たない。ガイドはあくまで人間+AI の運用手順）。
