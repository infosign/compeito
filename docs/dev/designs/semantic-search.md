# コンピテンシー意味検索（ベクトル埋め込み）実装方針 — backlog B2

> **ステータス: 設計レビュー済み（実装着手可・実装順未定）。** backlog [B2](../backlog.md)（FR-12.2「コンピテンシーの意味検索をベクトル埋め込みで提供」優先度3）の設計。
> Codex レビューを 2 ラウンド経て確定。実装に着手する際はこのドキュメントの方針に従う。末尾「残る決定事項」は着手時に確定する。

## 決定事項（ユーザー確認済み）

- **埋め込み生成**: ローカルモデルを同梱（オフライン・外部送信なし。compeito の自己ホスト/CDN非依存の方針に合わせる）。
- **検索の入口**: まず API エンドポイント（後から Web UI / CLI を載せられる形に）。
- **ベクトルストア**: PostgreSQL の **pgvector**（既存 DB に拡張を入れる。新規外部サービスを足さない）。

## ゴールと非対象

- **ゴール**: キーワード一致ではなく**意味の近さ**で CFItem を検索する。例: 「批判的思考」→ `critical thinking` や `論理的に分析する` がヒット。テナント内（任意で1ドキュメントに絞り込み）を対象。
- **非対象（今回やらない）**: Web UI 検索ボックス（後続）、フレームワーク間自動マッピング（backlog B3。本機能の類似度計算を基盤に将来実現）、リランキング、ハイブリッド（キーワード+ベクトル）検索、CASE 公式 API への組み込み（本機能は **compeito 拡張**であり CASE 標準ではない）。

## アーキテクチャ概要

```
[case-cli index build] --(埋め込み生成: ローカルモデル)--> cf_item_embeddings (pgvector)
[API: GET /{tenant}/search?q=] --(クエリ埋め込み)--> pgvector 近傍検索 --> ランキング済み CFItem
```

3 つの部品:
1. **Embedder（埋め込み生成器）**: ローカルモデルでテキスト→ベクトル。インターフェース化し、テスト用フェイクと差し替え可能にする（後述）。
2. **ベクトルストア**: pgvector。`cf_item_embeddings` テーブル。
3. **検索サービス + API**: クエリを埋め込み、コサイン近傍で top-k を返す。

## 埋め込みモデル（ローカル・オフライン）

- **モデル**: 多言語対応の軽量モデル。第一候補 **`intfloat/multilingual-e5-small`**（約118M・**384次元**・日本語/英語とも実用）。日本語強化が要れば e5-base 系も検討（次元・サイズ増）。
- **実行方法**: torch 同梱は重いので、**ONNX Runtime（`onnxruntime` + `tokenizers`）で推論**し、torch 依存を避けて Docker イメージを軽く保つ。モデルは ONNX 形式で**ビルド時にイメージへ焼く**（実行時ダウンロードなし＝オフライン保証）。
  - ⚠️ 代替案: sentence-transformers/torch を使う（実装は楽だがイメージ +1GB 級）。または別コンテナで TEI を立てる（“外部サービスを足さない”方針と外れる）。→ **ONNX 同梱を推奨**。
- **e5 系の作法**: 入力に接頭辞が必要。文書側 `passage: <text>`、クエリ側 `query: <text>`。実装で必ず付与する。
- **ONNX 推論 → 埋め込みベクトル化の手順（must-fix で明記）**: `tokenizers` で truncation=512・padding 付きでトークナイズ → ONNX Runtime で
  last_hidden_state を取得 → **`attention_mask` を使った mean pooling**（pad トークンを除外した平均）→ **L2 正規化**。この一連を Embedder 内に固定実装する。
  ここを曖昧にすると 384 次元でも検索品質が壊れるため、pooling/正規化/接頭辞/truncation を仕様として固定。
- **正規化と距離の一本化**: L2 正規化済みベクトルを格納。pgvector は **`vector_cosine_ops`** の HNSW を使い、`ORDER BY embedding <=> :q`（cosine distance 昇順）で近傍を取り、**`score = 1 - distance`** をレスポンスの類似度とする。index operator class・ORDER BY 演算子・score 変換はこの cosine 一系統に統一する（内積 `vector_ip_ops` 系とは混在させない）。

## 埋め込む対象テキスト

- 主: `full_statement`（必須・常に存在）。
- 補強（連結）: `human_coding_scheme`・`abbreviated_statement`・`concept_keywords`（JSONB の語を結合）。空はスキップ。
- 連結後にモデルの最大トークン長（e5=512）で**切詰**。切詰方針はドキュメント化。

## データモデル / マイグレーション

- **pgvector 拡張の導入**（Alembic マイグレーションで `CREATE EXTENSION IF NOT EXISTS vector`）。
- **新テーブル `cf_item_embeddings`**（cf_items に列を生やさず分離 — モデル差し替え・再計算・肥大回避のため）:
  - `cf_item_id`（FK → cf_items.id, ON DELETE CASCADE）
  - `tenant_id`（検索スコープと索引のため非正規化）
  - `cf_document_id`（`doc=` 絞り込みを join 無しで効かせるため非正規化。出所は cf_items.cf_document_id）
  - `model_id`（例 `multilingual-e5-small`。モデル変更時に併存/再計算判定）
  - `dim`（次元数。整合性チェック用）
  - `embedding`（`vector(384)`）
  - `source_hash`（埋め込み元テキストのハッシュ。**次回 index build の差分再計算判定**に使う。※検索時の stale 排除ではない。後述）
  - `updated_at`（= indexed_at。レスポンスの `indexedAt` に使う）
  - PK/UNIQUE: `(cf_item_id, model_id)`
- **索引**:
  - pgvector の **HNSW**（`vector_cosine_ops`）。件数が小さいうちは無索引でも可だが HNSW を既定に。パラメータ（m, ef_construction）は既定値から。
  - フィルタ用の通常 btree index: `(tenant_id, model_id)`、必要なら `(tenant_id, cf_document_id, model_id)`。
  - ⚠️ **HNSW + フィルタの性能**: pgvector の近傍探索はフィルタ条件との組合せで期待件数を取り切れない/効率が落ちることがある。`ef_search` を調整可能にし、過取得してから top-k へ絞る。**過取得は必ず同一 SQL 内で `WHERE tenant_id = :t AND model_id = :m [AND cf_document_id = :d]` を効かせたうえで**行う（アプリ側で全テナント候補を取得してから絞る実装にはしない＝テナント秘匿とパフォーマンスの両立）。当初は許容範囲だが運用で要観察。

## インデックス生成パイプライン（バックグラウンドワーカー無し前提）

compeito には常駐ワーカー/キューが無いため、**明示的な CLI コマンドで一括生成**する。

- `case-cli index build --tenant <uuid> [--doc <uuid>] [--rebuild]`（entry point は `case-cli`）:
  - 対象 CFItem を取得 → 埋め込み元テキスト構築 → `source_hash` が既存と一致する行はスキップ（冪等・差分のみ再計算）→ バッチで埋め込み生成 → upsert。
  - `--rebuild` で全再計算。
- **stale の意味（must-fix で明確化）**: `source_hash` は**次回 `index build` の差分再計算判定**にのみ使う（検索時の stale 排除ではない）。
  既定の挙動は「**再 index するまでは古いベクトルで検索される**」。import で CFItem が更新されても、次に `index build` を走らせるまでベクトルは古いまま。
  検索結果の**本文は CFItem 実体から引く**ので本文は常に最新（ベクトルだけ古い可能性）。削除は FK CASCADE で消える。未インデックス項目はヒットしない。
  - 将来オプション（今回非対象）: 検索時に `cf_item_embeddings.updated_at` と `cf_items.last_change_date_time` を比較し stale 行を除外/降格する。
- 任意拡張: CLI import 完了時に対象ドキュメントの `index build` を自動実行するフック（オプション。既定オフ）。

## 検索 API（最初に作る入口）

- `GET /{tenant}/search?q=<text>&limit=<n>&doc=<uuid>`
  - `q` 必須。`limit` 既定10・**検索専用の小さめ cap（例 50）**を新規定義（CFDocuments の `LIMIT_CAP=500` は流用しない）。`doc` 任意でドキュメント絞り込み。
  - 処理: `q` を `query:` 接頭辞付きで埋め込み → 同一 `model_id`・`tenant_id`（+任意 `cf_document_id`）で pgvector コサイン近傍 top-k → CFItem を返す。
  - レスポンス: `{ "items": [ { identifier, fullStatement, humanCodingScheme, uri, score } ... ], "modelId": "...", ... }`。各 item に `score`（類似度）。**CASE 標準ではない拡張**なので形は compeito 独自。本文は CFItem 実体から引く。
  - **エラー契約（must-fix）**: `main.py` の imsx ハンドラは `/ims/case/v1p1/` を含むパスにしか効かない（[main.py](src/main.py)）。本エンドポイントはそのパス外なので、**ルート内で 400（q 欠落・不正 limit）/404（テナント無し）/503（後述）等を明示的に `errors.imsx_error_response` で imsx 形式に整形して返す**。グローバルハンドラには依存しない。
  - **`embedding_enabled=false` 時**: 機能オフ。**503 Service Unavailable** を imsx 形式で返す（検索不可を明示）。テスト対象に含める。
  - `Cache-Control`: 既定方針（public, max-age=3600）に合わせる。
  - **テナント秘匿**: 検索は `tenant_id` スコープ厳守（プライベートテナントの秘匿性を壊さない）。
  - **パス配置**: `/ims/case/v1p1/` 配下に置かない（CASE 標準 API と混同させない）。`/{tenant}/search` 等の拡張パス。
- 後続: Web UI（ツリーに検索ボックス、HTMX）／CLI `search`。今回は API のみ。

## 設定（config.py）

- `embedding_enabled`（既定 true / 無効化で機能オフ）
- `embedding_model_id`（既定 `multilingual-e5-small`）
- `embedding_model_path`（イメージ内の ONNX/トークナイザのパス）
- `embedding_dim`（既定 384・マイグレーションと整合）
- `embedding_search_limit_cap`（検索専用 cap。既定 50）
- `ef_search`（HNSW 探索パラメータ。調整可能に）
- レイヤ構成は既存どおり router → service → repository。Embedder はサービス層に注入。

## 依存・DDL の方針（should）

- **pgvector の Python 連携**: `pgvector` パッケージ（SQLAlchemy 型 `Vector`）を `pyproject.toml` に追加して ORM で扱う。現状 `pgvector` 依存は無い。HNSW 索引作成や `<=>` 演算子の一部は raw SQL / `text()` で書く（Alembic も同様）。
- 新規 ORM モデル `CFItemEmbedding` を作るので **`src/models/__init__.py` に登録**する（Alembic `migrations/env.py` が `src.models` を import して metadata を集めるため、未登録だと autogenerate に乗らない）。

## Docker / ビルド・NFR への影響（要注意）

- ⚠️ **Postgres イメージ変更**: `postgres:15` は pgvector を含まない。`pgvector/pgvector:pg15` へ差し替え（または拡張をインストール）。**docker-compose.yml・CI・テスト DB・ローカル DB すべてに波及**。
- ⚠️ **既存 volume / マイグレーション手順**: `docker-compose.yml` は `pgdata` 永続 volume を使う。イメージ差し替え自体は既存 DB でも可だが、拡張は **Alembic マイグレーションで `CREATE EXTENSION IF NOT EXISTS vector`** を実行して有効化する。ローカル利用者向けに「イメージ更新 → `docker compose up -d db` 再作成 → `alembic upgrade head`」の手順を docs に明記（pgvector イメージへの切替時に既存 `pgdata` のままでも拡張は作成可能なことを確認のうえ記載）。
- **モデル同梱**: ONNX 重み（数百MB）＋ `onnxruntime`/`tokenizers` 依存をイメージへ。イメージサイズ・メモリ・初回ロード時間が増える（NFR に影響。許容値を要確認）。重みはイメージに焼く（オフライン保証）／ボリュームマウントのどちらか要決定。

## テスト方針

- pgvector を使うため**テスト DB も pgvector イメージ**に。`tests/conftest.py` はテーブル削除を手書きしているので、**`cf_item_embeddings` を cleanup 順（cf_items より先＝CASCADE 前）に追加**する。
- **Embedder インターフェース＋フェイク**: CI で実モデルをロードしないよう、決定的なベクトルを返すフェイク Embedder を注入してテスト（検索ランキングの正しさを安定検証）。実モデルのスモークテストは別途任意。
- 単体: 埋め込み元テキスト構築（接頭辞 `passage:`/`query:`、連結、切詰）、mean pooling + L2 正規化（フェイクで形だけでも）、`source_hash` による差分スキップ、dim 整合。
- 結合: `index build` 後に `GET /search` が意味的に近い順で返す（フェイク埋め込みで順位を制御）。`doc` 絞り込み・テナントスコープ・空インデックス時の挙動・limit cap・`embedding_enabled=false` 時に 503(imsx) を返すこと。

## エッジケース

- **未インデックス**: 埋め込み未生成の項目はヒットしない。インデックス0件なら空結果（エラーにしない）。
- **モデル不一致**: `cf_item_embeddings.model_id` と現行 `embedding_model_id` が異なる行は検索対象外（再計算を促す）。
- **長文 full_statement**: 512トークン超は切詰。
- **多言語クエリ**: e5 は多言語埋め込みなので日↔英のクロス言語ヒットを許容（仕様として明記）。
- **プライベートテナント**: 検索は tenant スコープ。秘匿性維持。
- **更新後の stale**: 再 index まで古い埋め込み。検索結果の本文は CFItem 実体から引くので本文は最新（ベクトルだけ古い可能性）。

## 段階実装（このバックログ項目の中の順序）

1. **基盤**: pgvector 導入（イメージ・マイグレーション）＋ Embedder（ONNX・モデル同梱）＋ `cf_item_embeddings` ＋ `index build` CLI。
2. **検索 API**: `GET /{tenant}/search`。
3. （後続・別バックログ）Web UI 検索、B3 フレームワーク間マッピング。

## 残る決定事項（レビュー/ユーザー確認したい点）

- 採用モデルの最終決定（multilingual-e5-small で十分か、日本語強化版が要るか）と**イメージサイズ許容値**。
- モデル重みを**イメージに焼く** vs **ボリューム**。
- HNSW パラメータ（m / ef_construction / ef_search）の既定。
- 検索のスコア閾値（足切り）を設けるか、純粋に top-k のみか。
- import 完了時の自動 index フックを入れるか（既定オン/オフ）。
