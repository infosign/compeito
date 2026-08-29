# 廃止項目の UI 実装方針（B8-3 / B8-4）

> **ステータス: 設計レビュー済み（実装着手可）**
> Claude Opus 5 レビュー 3 ラウンド＋指摘反映済み（2026-08）。
> 廃止された CFItem を UI 上で生きた項目と区別し、既定でツリーから隠す。バックログ [B8](../backlog.md) の B8-3 / B8-4。

## 決定事項

1. **廃止の判定は日付比較**。`status_end_date is not None and status_end_date <= 今日` のときだけ廃止として扱う。未来日は「廃止予定」であり、生きた項目として通常表示する（ユーザー確認済み）。
   CFItem の `statusEndDate` は **「廃止が確定した日」** であり、**その日から**非表示になる（B8-6 で定める書き分けに従う。CFDocument の `statusEndDate` は「有効期間の最終日」で意味が異なるが、今回は CFDocument を扱わない）。
   `今日` は **UTC の日付**とする。JST では朝 9 時に切り替わる。行政的な日付なので、この程度のずれは許容する。
2. **既定でツリーから隠すのは、サブツリー全体が廃止のときだけ**。生きた子孫を持つ廃止項目は、経路を保つために区別表示で残す（ユーザー確認済み）。
3. **permalink と詳細ページは廃止後も常に解決する**（発行済み OB v3 バッジの alignment 先を壊さない）。廃止バナーと後継リンクを出す。
4. **CASE API は変更しない**。全件返す。除外は Web UI のツリーと検索に限る（[infosign/to-case#9](https://github.com/infosign/to-case/issues/9) の合意）。
5. **隠す処理はツリー描画の3経路にだけ効かせる**。`build_full_tree` / `doc_tree_index` は**常に全項目**で計算する（理由は後述「隠してはいけない場所」）。

## 背景

CASE には項目の廃止を表す削除操作が無く、compeito のインポートも additive only である。元ソースから消えた項目は `statusEndDate` と `replacedBy` を持つ「墓標」としてテナントに残る（入力側は B8-1 / B8-2 で完了）。

現状、UI は墓標を生きた項目と全く同じに表示する。`status_end_date` は詳細カードの技術セクションに日付として出るだけで（`resource_detail.html:519`）、ツリー上の区別も無く、`replacedBy` は汎用の関連リストに紛れる。教材の対応づけやバッジのアライメント先を人が選ぶ画面で、これは誤りを生む。

## 廃止判定

```python
# src/services/retirement.py（新規）
def is_retired(item: CFItem, today: date) -> bool:
    """CFItem が今日時点で廃止済みか。未来日は「廃止予定」で、まだ有効。"""
    return item.status_end_date is not None and item.status_end_date <= today
```

`today` は呼び出し側が `datetime.now(timezone.utc).date()` で1回求めて渡す。**SQL 側で `CURRENT_DATE` を使わない**（テストで日付を固定できなくなるため。必ずパラメータとして渡す）。

## 隠す対象の決め方

**隠すのは「その項目が廃止済みで、かつ子孫に生きた項目が1つも無い」場合だけ**である。生きた子孫がいる廃止項目を隠すと、生きた項目への経路が消える。

判定は**ノード単位**である。`hidden(x)` は x の子孫だけに依存し、親が誰であるかに依存しない。したがって多重親の項目も、どの親の下に現れても同じ扱いになる。

### 文書単位で1回だけ計算する

判定は**文書単位で1回**行い、結果の集合をリクエスト内で使い回す。

```python
async def hidden_identifiers(
    session: AsyncSession,
    doc_id: uuid.UUID,
    today: date,
) -> set[str]:
    """既定のツリー表示から隠す CFItem の identifier 集合を返す。"""
```

アルゴリズム:

1. `cf_items` から `cf_document_id = doc_id AND status_end_date IS NOT NULL AND status_end_date <= today` の identifier を引く。**空なら即 `set()` を返す**（以降の処理も、ツリー側のフィルタも全て no-op になる）。
2. 廃止項目を起点に `isChildOf` の子を辿る。**1階層あたり1クエリ**（`cf_associations` に `cf_items` を join し、`CFItem` 行が実在する子だけを返す。`origin_node_identifier` は `String`、`identifier` は `UUID` なのでキャストが要る。`_strs_to_uuids` に前例がある）。
   子が廃止かどうかの判定に item を読む必要は無い。ステップ1が文書内の全廃止 identifier を返しているので、集合の membership で足りる。join が要るのは**行の実在確認**のため（ステップ7）。
3. **生きた子で枝刈りする**。生きたノード c は `hidden(c) = false` が確定しており、その子孫は誰の判定にも影響しない（親は c が生きている時点で false に確定する）。したがって**フロンティアに積むのは廃止の子だけ**。生きた子はそこで止める。
   これにより、探索範囲は「廃止領域 ＋ その直下の生存フリンジ」に収まる。**枝刈りをしないと、ルート直下に墓標が1つあるだけで配下の生きた2万項目を辿ることになる。**

   > **不変条件（この設計で最も壊れやすい前提）**: すべての廃止項目はステップ1で起点集合に入る。枝刈りが減らすのは**探索の経路**であって、**判定の対象**ではない。生きたノードの配下に廃止項目があっても、それは自身が起点なので独立に畳み込まれる。
   > ステップ1を「ツリーのルートから辿れる廃止項目だけ」のように最適化すると、この不変条件が崩れて `has_children` が静かに壊れる。
4. ボトムアップに畳む。`hidden(x) = is_retired(x) and all(hidden(c) for c in children(x))`。子を持たない廃止項目は `hidden`。
5. **メモ化と探索中スタックを分ける**。
   - `memo: dict[str, bool]` に確定した `hidden(x)` を記録し、再到達時はメモを返す
   - `on_stack: set[str]` に**現在の探索経路上**のノードを持ち、そこに在るノードへの辺だけを循環として扱い「隠さない」に倒す
   - 循環で倒した結果は**メモに書かない**（経路依存の暫定値なので、他経路からの確定判定を汚染する）

   訪問済み集合ひとつで循環を判定してはならない。多重親は CASE で正規の構造であり、循環でなくとも同じノードに二度到達する。次の菱形（全項目が廃止）で、C を「訪問済み＝循環」として安全側に倒すと `hidden(B)=false` → `hidden(X)=false` となり、**全体が廃止のサブツリーがまるごと残る**。

   ```
   X ──▶ A ──▶ C
   └────▶ B ──▶ C     (C は A と B の共通の子)
   ```

6. **循環の汚染は上に伝播させない**。X → A → B → A で辺 B→A が切られた場合、`hidden(B)` は「A を隠さない」を前提にした暫定値だが、それを消費した祖先（この例では X）まで遡って無効化することはしない。倒す方向が常に「隠さない」なので、誤りは安全側（隠すべきものを隠しそこねる）にしか出ない。循環データ自体が異常系であり、正確さより実装の単純さを採る。
7. **`CFItem` 行が存在しない子は数に入れない**（＝隠すのと同じ扱い）。`get_children_bulk` は isChildOf の origin に対応する CFItem 行が無い子を黙って落とすので（`items_by_ident.get(ident)` が None）、描画されないものを可視の子として数えると親が空展開になる。
   ステップ2の join がこれを担う。**同じ join を `_get_idents_with_children` にも入れる**ことで、廃止と無関係な位置にある壊れた `isChildOf`（生きた親 P の唯一の子 Q に CFItem 行が無い、など）も塞がる。墓標ゼロの文書ではステップ1が即 `set()` を返して畳み込みが走らないため、`hidden` 側の規則だけでは届かない。既存バグの修正を1クエリの書き換えで兼ねる。

### なぜ局所判定（描画する階層の子だけを見る）にしないか

`get_children_bulk` が既に子の `CFItem` 行を読んでいるので、その階層だけを判定すれば安く済む — と一度は考えたが、採らない。判定の対象を候補集合に閉じると、次の3箇所が壊れる。

- **`has_children`**: 判定したいのは「いま返す子 c が可視の子を持つか」であり、見る対象は**孫**である。候補集合（＝子）に孫は入らないので、`origin not in hidden` が常に真になり、空展開の穴（後述）が塞がらない。塞ぐには階層ごとに孫の `status_end_date` を引く追加クエリが要る
- **トグルリンク**: 初期 SSR は depth 0-1 しか描画しない。墓標が depth 3 にしかない文書では隠れた項目が0件に見え、ヘッダのリンクが出ない。後から枝を展開しても、ヘッダは HTMX の差し替え先ではないので出現しない。**2万3千項目の文書で墓標が深部にあるという最も普通の状況で、機能に到達できなくなる**。塞ぐには文書全体の EXISTS が別途要る
- **`?item=` の例外**: 祖先経路は複数の階層にまたがるので、「隠す集合から1回引く」で表現できない。`exempt` を全ビルダーと `has_children` の孫判定に通す必要がある

いずれも塞げるが、その結果は「階層ごとに1本＋文書全体に1本」であり、**文書単位（1本）より多くのクエリと、3箇所に散った規則**になる。文書単位なら集合が全階層を覆うので、3つとも自然に解ける。

### コスト

| 状況 | 追加クエリ |
|---|---|
| 墓標が1件も無い文書 | 1本（ステップ1のみ。以降は no-op） |
| 墓標がある | 1本 ＋ 廃止サブツリーの深さ × 1本 |
| トグルリンクの出し分け | 0本（ステップ1の結果から分かる） |

**この費用はページ1回あたりではなく、`children_fragment` の1リクエストごとにも掛かる**（遅延展開のクリックごと）。フラグメントは `max-age=86400` でキャッシュされるので繰り返しの負荷は小さい。

`?item=` で CFItem を選択しているページは、そもそも `doc_tree_index` → `build_full_tree` が全項目と全 isChildOf を読んでいる（`web.py:866`）。隠す判定のコストはその既存負荷に比べれば小さい。

**同一リクエスト内で1回だけ計算し、ルータが各ビルダーに渡す**。配り先は `build_ssr_tree` の depth 0 / depth 1、`get_orphan_items`、そして **`_expand_ancestor_path`**（`tree_service.py:531` 以降で `get_children` を呼んで深い階層を追加ロードするため）。ここに減算済みの `hidden` を渡し忘れると、渡さない場合は祖先経路の下だけフィルタが効かず、その場で再計算する場合は `exempt` の減算が失われて名指しした項目への経路が途中で切れる。

`children_fragment` は `?item=` を受けないルートなので `exempt` を持たない。実害は無い（`_expand_ancestor_path` が展開した祖先経路は inline 描画になり、`<details>` の開閉はネイティブなので再取得が起きない）。

### インデックス

ステップ1のために部分インデックスを1本足す。

```sql
CREATE INDEX ix_cf_items_doc_retired ON cf_items (cf_document_id, status_end_date)
WHERE status_end_date IS NOT NULL;
```

既存の4本（`(tenant_id, cf_document_id, human_coding_scheme)` / `(cf_document_id, depth)` / `subject_uri` の GIN / `(tenant_id, cf_item_type_id)`）とは重複しない。`ix_cf_items_document_depth` でも索引走査はできるが、墓標が0件の文書では「無いことを証明するために当該文書の全エントリを走査する」形になる。墓標だけを含む極小の索引なので入れて損はない。Alembic マイグレーションを1本追加する。

## 隠してはいけない場所

**`build_full_tree` と `doc_tree_index` は絶対にフィルタしない。**

`doc_tree_index`（`tree_service.py:429`）が作る `tree_index` は、`sort_related_by_tree_order` が「この文書のツリーにある項目か」を判定するのに使われる。ここから廃止項目が落ちると、次の連鎖で**廃止項目を指す関連の行が、詳細ペインの「関連」リストから跡形もなく消える**。

1. `tree_index` に無いので `related_in_doc` に入らない
2. `related_other_doc` にも入らない（`doc_identifier == cur` で除外。`web.py:557`）
3. `_resolve_cross_tenant` でも解決しない（自テナントの URI は `continue`。`web.py:239`）
4. テンプレートの「内部 URI なのに未解決 → 行ごとスキップ」分岐に落ちる

これは決定事項3（詳細は常に解決する）と決定事項4（除外はツリーと検索に限る）の両方に反する。しかも「非公開テナントの存在を隠す」ための分岐に相乗りして消えるため、警告にもログにも出ない。

フィルタを効かせるのは次の3経路だけである。

- `build_ssr_tree`（depth 0-1 の SSR）
- `get_orphan_items`（orphan 節）
- `children_fragment` → `get_children`（遅延読み込み）

## `has_children` を可視性ベースにする

`_get_idents_with_children`（`tree_service.py:397`）は「isChildOf の destination に現れるか」だけを見ている。生きた項目 P の子が全部「廃止かつ生きた子孫なし」だと、P は隠れないが子は全部隠れる。このとき `has_children=True` のまま `<details>` ＋ `hx-get` が描画され、`children_fragment` は空を返す。**開いても何も出ない枝**が残る。

`_get_idents_with_children` を「**隠す集合を除いた子が1つ以上あるか**」に変える。現在の DISTINCT な destination だけを返すクエリでは判定できないので、`(destination, origin)` のペアを取り、`origin not in hidden` を数える形にする。

ここで数える origin は、いま描画している階層から見て**孫**である。`hidden` が文書全体を覆う集合だからこの式が成立する（局所集合では孫が入らず、常に真になって空振りする）。`exempt`（`?item=` の例外）も同じ集合に反映済みなので、名指しされた廃止項目の親から `<details>` が消えることもない。

効かせる先は3箇所すべて。`build_ssr_tree` の depth 0（`get_children` 経由）、`get_children_bulk` のステップ3、`children_fragment` が返す各ノード。

## `?item=` の例外と処理順序

`?item=` / `/item/{id}` で廃止項目が名指しされた場合、`includeRetired` の有無にかかわらず**その項目と祖先の経路は表示する**。名指しされたものが見えないのは事故に見える。

現在の `build_ssr_tree`（`tree_service.py:313`）は、木を組み終えてから最後に `_expand_ancestor_path` を呼ぶ。**フィルタを先に効かせると、祖先は既に木から落ちていて展開対象に到達できない。** 順序を固定する。

1. 選択項目を解決する（`_resolve_selected_item`）
2. `_get_ancestor_path` で祖先経路を得る（`_expand_ancestor_path` から呼び出しを切り出すリファクタが要る）
3. 隠す判定を行う
4. `hidden -= set(祖先経路) | {選択項目}`
5. その `hidden` を使って木を組む
6. 従来どおり `_expand_ancestor_path` で `<details>` を開く（**減算済みの `hidden` を渡す**）

## 表示（B8-3）

### ツリー上の区別

`fragments/tree_nodes.html` のラベル本体（`label_body`）に、廃止バッジと減光を足す。

- バッジ: `t("retired_badge")`（"Retired" / "廃止"）をピンク系で。`adoption_status = Deprecated` のバッジ（`resource_detail.html:45`）と同系色にする
- 本文: `text-gray-800` → `text-stone-500`。`text-stone-400`（`#a8a29e`）は白地で約 2.5:1 しかなく、本文の WCAG AA（4.5:1）を満たさない
- **色だけに意味を持たせない**。意味はバッジが担保する
- 区別表示で残るのは「生きた子孫を持つ廃止項目」と「`includeRetired` で表示した廃止項目」の2つ

`TreeNode` に `is_retired: bool = False` を足し、`tree_service` の各ビルダーが埋める（テンプレートが日付比較をしない）。

### 詳細ペイン / permalink ページの廃止バナー

`resource_detail.html` の CFItem ブロック先頭（Zone A ヘッダの直後、`:534` 付近）に条件付きバナーを出す。`in_pane`（HTMX フラグメント）と permalink ページの両方で同じ partial を使う。

- 文面: 「この項目は {statusEndDate} に廃止されました」
- 後継: 発信側の `replacedBy` 関連を **1ホップだけ**出す。A→B→C の連鎖では B を出す（C は B のページで辿れる）
- 取得元: `_related_groups`（`web.py:185`）が既に非 isChildOf の発信関連を集めているので、そこから `association_type == "replacedBy"` を抜き出す
- **ラベルは `cf_item_repository.map_identifiers_to_items` で引く**（`human_coding_scheme` と `full_statement` を返す。`_resolve_cross_tenant` / `_cross_doc_hierarchy` が使っているもの）。`_detail_extras` が持っているのは identifier と `destination_node_title`（association のスナップショット）だけで、設計した文面は作れない
- 後継自身が廃止済みの場合、後継リンクにも廃止バッジを付ける（`status_end_date` は同じ呼び出しで取れる）
- 関連リストからは除外しない。関連リストは「この項目が持つ関連の全部」を見る場所なので、そこから消すと別の不正確さが生まれる

**非公開テナントの漏洩を防ぐ**。`destination_node_title` をそのまま出すと、後継が非公開テナントの項目でもタイトルが表示される。既存の関連リストは、この場合に**行ごとスキップして存在すら surfacing しない**（`web.py:225` 前後、`_incoming_refs` の case A）。バナーも同じ扱いにする。

- `related_in_doc` / `related_other_doc` / `related_other_tenant` の分類結果を後継にもそのまま適用し、`classified_ref` マクロ（`resource_detail.html:184`）を再利用する
- **解決できなければ行ごと出さない**（リンクを外すだけでは不十分。ラベルも出さない）

### CFDocument の廃止

CFDocument にも `status_end_date` はあるが、今回は**扱わない**。フレームワーク一覧の `adoption_status = Deprecated` バッジが既にあり、意味が重複する。B8-6 で日付の意味を書き分けるときに合わせて再考する。

## トグル（B8-4）

`?includeRetired=1` をクエリパラメータで受ける。値は `"1"` のみ真とする。

- 対象ルート: `GET /{tenant}/cftree/doc/{doc_id}`、`/item/{item_id}`、`/children/{parent_id}`（HTMX）
- ツリーのヘッダに切り替えリンクを置く。現在の URL に付け外しするだけの素の `<a href>`（JS 不要）
- **出し分けの条件は「隠れた項目があること」**（`hidden` が空でない）。廃止項目の有無ではない。廃止項目が全部「生きた子孫あり」で区別表示のまま残っている文書では、押しても表示が1つも変わらないため。文書単位で判定するので、墓標が depth 3 にしかない文書でもリンクが出る。`includeRetired=1` のときは常に出す（戻せなくなるため）
- **引き継ぎ先は `hx-get` だけでは足りない**。`tree_nodes.html` の `label_attrs` は `href` と `hx-push-url` にも `/item/{id}` を持つ。ここに載せないと、廃止表示中に項目をクリックした瞬間 URL からトグルが落ち、リロードや戻る操作で既定に戻る。選択項目自体は `?item=` の例外で見えるが、兄弟の廃止項目が消えて「ツリーが勝手に変わった」ように見える
- Cookie / セッションには保存しない。URL に出るので共有可能で、`Cache-Control: public` のままキャッシュが分かれる

### キャッシュと日付境界（受け入れる劣化）

`?includeRetired=1` はクエリ文字列なのでキャッシュキーに含まれ、トグルとキャッシュは両立する。両立しないのは「日付で判定が変わる」ほうである。

- ページ（`max-age=3600`）: 廃止日の切り替わりが最大1時間遅れる
- HTMX フラグメント（`max-age=86400`）: 日付境界を最大24時間またいで古い応答が返る。ツリーの展開部分だけ廃止前の状態が残る

**これは受け入れる。** 廃止は年に数回の編集イベントであり、「その日に廃止された項目が丸1日ツリーに残る」ことの実害は小さい。`docs/spec/web-ui.md` に制約として明記する。

（採らない選択肢: 廃止日を持つ項目がある文書に限り `max-age = min(既定値, UTC 翌0時までの秒数)` にする。正確になるがキャッシュ効率が落ち、実装も分岐が増える。必要が生じたら切り替える。）

## 変更するファイル

| ファイル | 変更内容 |
|---|---|
| `src/services/retirement.py` | 新規。`is_retired()` / `hidden_identifiers()` |
| `src/services/tree_service.py` | `TreeNode.is_retired` を追加。`get_children_bulk` / `get_children` / `get_orphan_items` / `build_ssr_tree` にフィルタと `today` を通す。`_get_idents_with_children` を可視性ベースにし、`cf_items` を join して行の実在も確認する。`_expand_ancestor_path` に `hidden` を通す。`_get_ancestor_path` の呼び出しを `_expand_ancestor_path` から切り出す。**`build_full_tree` / `doc_tree_index` は変更しない** |
| `src/routers/web.py` | 3ルートで `includeRetired` を受ける。詳細用に `successors`（分類済み）を組み立てる。トグルリンクの表示条件をコンテキストに入れる |
| `src/templates/fragments/tree_nodes.html` | 廃止バッジ・減光・`href` / `hx-get` / `hx-push-url` へのパラメータ引き継ぎ |
| `src/templates/fragments/resource_detail.html` | 廃止バナー＋後継リンク（`classified_ref` を再利用） |
| `src/templates/cftree.html` | トグルリンク |
| `src/locales/{en,ja}.json` | `retired_badge` / `retired_banner` / `retired_successor` / `show_retired` / `hide_retired` |
| `migrations/versions/*.py` | 部分インデックス1本 |
| `docs/spec/web-ui.md` | 廃止項目の扱い（既定非表示の規則、トグル、バナー、キャッシュの制約）を追記 |
| `docs/dev/backlog.md` | B8-3 / B8-4 のステータス更新 |

## 考慮すべきエッジケース

| ケース | 期待 |
|---|---|
| 墓標が1件も無い文書 | 追加クエリ 1 本（ステップ1のみ）。トグルリンクも出さない |
| 廃止項目の子が全部廃止 | 親ごと隠す（サブツリー全体が消える） |
| **菱形（多重親かつ全廃止）** | サブツリーごと隠す。メモ化で二度目の到達も同じ結論になる |
| 廃止項目の子に生きた項目が1つでもある | 親は区別表示で残す |
| 生きた項目の親が廃止 | 上と同じ。生きた項目への経路が保たれる |
| ルート直下の廃止項目 | 同じ規則。root_nodes と orphan の両方で効かせる |
| 多重親 | ノード単位で判定するので、どの親の下に現れても同じ扱い |
| `isChildOf` の循環 | 探索経路上のノードへの辺だけ「隠さない」に倒す。メモには書かない |
| 生きた項目だけの深い枝 | 枝刈りで辿らない |
| 未来日の `statusEndDate` | 廃止扱いにしない。バッジもバナーも出さない |
| `?item=` が廃止項目を指す | 常に表示（トグル不要）。祖先経路も表示 |
| 遅延読み込みで展開した枝 | 親ページと同じ規則。パラメータを引き継ぐ |
| 子が全部隠れた生きた項目 | `has_children=False`。展開の三角を出さない |
| `replacedBy` が複数 | 全部出す（連鎖ではなく分割された場合がある） |
| `replacedBy` の宛先が非公開テナント | 行ごと出さない（存在を surfacing しない） |
| 後継自身が廃止済み | 後継リンクにも廃止バッジ |
| `CFItem` 行が無い子（壊れた isChildOf） | 数に入れない。`_get_idents_with_children` の join で、墓標の有無に関係なく効く |
| 別文書にしか子を持たない廃止項目 | この文書のツリーでは葉として扱い、隠す（`get_children_bulk` は `cf_document_id` で絞るため）。別文書の子は詳細ペインの「下位（別FW）」に出る |
| 墓標が depth 2 以深にしかない | トグルリンクは出る（文書単位で判定するため） |

## テスト方針

- `tests/unit/test_retirement.py`（新規）: `is_retired` の日付境界（今日 / 昨日 / 明日）、`hidden_identifiers` の各形（全廃止サブツリー、生きた子孫あり、**菱形**、循環、墓標ゼロ、生きた枝の枝刈り）
- `tests/unit/test_tree_view.py`: 既定で隠れること、`includeRetired=1` で出ること、区別表示で残るケース、`?item=` の例外、遅延読み込みのパラメータ引き継ぎ、`has_children` が空展開を作らないこと
- **クエリ数のアサーション**: `tests/unit/test_tree_view.py:290-319` に前例がある（`before_cursor_execute` で数える）。墓標ゼロの文書で**追加クエリが1本に収まる**ことを直接検証する
- `tests/unit/test_web_ui.py`: 廃止バナーと後継リンクのレンダリング（詳細ペイン / permalink 両方）、未来日でバナーが出ないこと、非公開テナントの後継が行ごと出ないこと
- `doc_tree_index` が廃止項目を落とさないこと（関連リストの回帰。決定事項5の再発防止）
- **トグルリンクが depth 2 以深の墓標でも出ること**（局所判定を採らなかった理由そのものの回帰）
- `CFItem` 行が欠けた子を持つ親が、空展開にならないこと

## 非対象（今回やらないこと）

今回触るのは**ツリー描画の3経路と CFItem 詳細のバナーだけ**である。次の面では廃止項目が従来どおり表示される。

- 検索（B8-5。B4 / B2 の実装時に同じ規則を適用する）
- CASE API のフィルタ（方針として変更しない）
- CFSubject の「この主題を設定している項目」（`subject_items`）
- CFItemType の「この型の項目」（`item_type_items`）
- 詳細ペインの「上位 / 下位（別FW）」（`_cross_doc_hierarchy`）
- 「他機関からの参照」（`_incoming_refs`）
- 詳細ペインの「関連」リスト（決定事項4より、意図的に隠さない）
- CFDocument レベルの廃止表示（B8-6 で再考）
- `replacedBy` の取り消し手段（B8-7）
- 廃止項目の一覧ページ（要望が出てから）

**既知の制約**: `get_children` / `children_fragment` は訪問済みの概念を持たないので、循環データでは無限に展開できる（今回の範囲外の既存挙動）。循環を「隠さない」に倒す方針と組み合わせると、循環部分が展開し続けられる状態が残る。

## 残る決定事項（実装着手時に確定する点）

- バッジの文言。「廃止」か「廃止済み」か。`adoption_status` の "Deprecated" バッジと並んだときに紛らわしくない語を選ぶ
