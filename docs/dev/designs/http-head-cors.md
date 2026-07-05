# CASE API の HEAD 許容と CORS 対応 実装方針 — 2026-07 適合性監査 N2

> **ステータス: 設計レビュー済み（実装着手可・実装順未定）**
> Codex レビュー 1 ラウンド（技術的前提の実コード検証・仕様間整合・方針整合）＋指摘反映済み（2026-07）。
> 2026-07 適合性監査 N2（HTTP/ブラウザ相互運用の改善）への対応設計。
> **certification（CASE v1.1 コンフォーマンステスト）の直接要件ではない**が、公開読み取り専用 API としての
> HTTP 相互運用性（リンクチェッカー・監視ツールの HEAD、ブラウザ上の JS クライアントからの fetch）を改善する。

## 決定事項（本設計の提案。レビューで確定）

- **HEAD 許容**: CASE API パスの 405 middleware を `GET`/`HEAD` 許容に変更し、あわせて **アプリ全体の GET ルートに
  HEAD を後付けで有効化**する（`main.py` で `APIRoute.methods` に `"HEAD"` を追加する一括ループ。理由は後述の「重要な事実」参照）。
- **CORS**: `CORSMiddleware` を**アプリ全体**に追加。既定 `cors_allow_origins=["*"]`（公開読み取り専用・認証なしの API なので
  ワイルドカードが安全かつ相互運用最大）。**credentials なし・許可メソッドは GET/HEAD のみ・expose は `X-Total-Count` と `Link`**。
- **素の OPTIONS**（preflight でない OPTIONS）: CASE API パスでは **405 のまま**とし、`Allow: GET, HEAD` を返す。
  preflight OPTIONS は CORSMiddleware（405 middleware より外側）が処理するので 405 にならない。
- **405 の Allow ヘッダ**: `Allow: GET` → **`Allow: GET, HEAD`** に修正（RFC 9110 §15.5.6 は 405 応答に Allow を要求。現状も付けているが値を更新）。
- **設計原則: 攻撃面を増やさない**。書き込みは引き続き CLI のみ。API は GET/HEAD 以外を受けない。CORS は「サーバ側の新機能」ではなく
  「ブラウザが既に公開されている読み取り応答を JS から読めるようにする許可ヘッダ」であり、認証・Cookie が存在しない compeito では
  `*` 許可によって新たに漏れる情報はない（サーバサイドのクライアントは元から全応答を取得できる）。

## 背景

- compeito は読み取り専用の公開 CASE API（書き込みは CLI のみ＝攻撃面削減の意図的設計）。OB v3 / QTI 3.0 の参照先として、
  ブラウザ上で動くクライアント（バッジ表示 UI、TAO のオーサリング画面、汎用の fetch ベースツール）から直接参照されうる。
- 現状は CASE API パスで **HEAD も OPTIONS も一律 405** になり、(1) リンク検証・監視ツールの HEAD が失敗する、
  (2) ブラウザの cross-origin fetch が CORS ヘッダ不在でブロックされる。2026-07 適合性監査でこの 2 点が N2 として指摘された。
- 関連: `docs/spec/api-spec.md`「Unsupported HTTP methods」「Security posture」、`docs/dev/case-v1p1-conformance-backlog.md`。

## 現状と重要な事実（コード検証済み）

実装前に把握しておくべき、リポジトリと依存ライブラリの実挙動。バージョンは lock 済み環境の
fastapi 0.135.1 / starlette 0.52.1 / httpx 0.28.1 / uvicorn 0.41.0 で確認。

1. **405 middleware**: [src/main.py](../../../src/main.py) L52–58 の `method_not_allowed` が
   `_CASE_API_MARKER = "/ims/case/v1p1/"`（L15）を含むパスで `request.method != "GET"` を一律 405（imsx 形式、
   `invalid_selection_field`）にし、`Allow: GET` を付けている。HEAD / OPTIONS もここで 405 になる。

   ```python
   @app.middleware("http")
   async def method_not_allowed(request: Request, call_next):
       if _CASE_API_MARKER in request.url.path and request.method != "GET":
           response = imsx_error_response(405, "Method not allowed", "invalid_selection_field")
           response.headers["Allow"] = "GET"
           return response
       return await call_next(request)
   ```

2. **⚠️ FastAPI は GET ルートの HEAD を自動処理しない（must-know。タスク前提の訂正）**:
   素の Starlette の `Route` は GET ルートに HEAD を自動追加する（starlette `routing.py` L247–248
   `if "GET" in self.methods: self.methods.add("HEAD")`）が、**FastAPI の `APIRoute` はこれを継承していない**
   （fastapi `routing.py` L886–888 は `self.methods = {method.upper() for method in methods}` のみで HEAD を足さない）。
   したがって **middleware の条件を緩めるだけでは不十分**で、HEAD は Starlette ルーターの partial match に落ち、
   `HTTPException(405, headers={"Allow": "GET"})` → `main.py` の `StarletteHTTPException` ハンドラ（404 以外は既定処理）
   → **imsx でない素の `{"detail": "Method Not Allowed"}` 405** になってしまう。HEAD をルートに明示的に足す必要がある。

3. **HEAD のボディ除去はサーバ層が行う**: `APIRoute.methods` に HEAD を足すと GET ハンドラがそのまま実行され、
   Response はボディ込みで生成される。実運用では **uvicorn がボディ送出を抑止**する
   （`uvicorn/protocols/http/httptools_impl.py` L512 で HEAD は chunked にしない、L530 で
   `if self.scope["method"] == "HEAD": self.expected_content_length = 0` としてボディを送らない。h11 実装も同等）。
   テストで使う **httpx `ASGITransport` もクライアント側でボディを破棄**する（`httpx/_transports/asgi.py` L163
   `if body and request.method != "HEAD"`）。つまり **ヘッダ（`Cache-Control` / `X-Total-Count` / `Link` /
   `Content-Type` / `Content-Length`）は GET と完全に同一のまま、ボディだけ空**になる。`Content-Length` は
   GET 相当ボディの長さを保持し、これは RFC 9110 §9.3.2（HEAD の Content-Length は GET 時の値を表してよい）に適合。
   なお `/static` の `StaticFiles` は Starlette 側で HEAD 対応済み（`send_header_only`）。

4. **CORSMiddleware の実挙動**（starlette `middleware/cors.py`）:
   - `Origin` ヘッダが無いリクエストは**完全素通し**（ヘッダを一切足さない）→ 既存のテスト・利用者に無影響。
   - preflight と判定されるのは **OPTIONS かつ `Access-Control-Request-Method` ヘッダあり**のときだけ。
     それ以外の OPTIONS は内側にそのまま流れる（→ 405 middleware に到達する。決定事項どおり）。
   - `allow_origins=["*"]` + `allow_credentials=False` のとき、通常応答・preflight とも
     `Access-Control-Allow-Origin: *` を固定で付け、`Vary: Origin` は付かない（キャッシュ・CDN に安全）。
   - `X-Total-Count` と `Link` は **CORS-safelisted response header ではない**ため、`expose_headers` に
     明示指定しないと cross-origin の JS から読めない（ページネーションが使えなくなる）。**必ず指定する**。
   - `max_age` は `Access-Control-Max-Age`（preflight 結果のブラウザキャッシュ秒数）。
5. **middleware の順序**: `@app.middleware("http")` はデコレート時に `add_middleware` 相当で登録され、
   **後から add したものほど外側**になる。`main.py` の Middleware 節（L43–58）より**後ろの行**で
   `app.add_middleware(CORSMiddleware, ...)` を呼べば CORS が最外になり、preflight が 405 middleware より先に処理される。
   例外: Starlette の `ServerErrorMiddleware`（`@app.exception_handler(Exception)` の 500 imsx を返す層）だけは
   CORS よりさらに外側のため、**未捕捉 500 の応答には CORS ヘッダが付かない**（既知の限界としてエッジケース参照）。

## アプローチ

### 1. HEAD 許容（src/main.py）

- 405 middleware の条件を変更し、Allow を更新する:

  ```python
  if _CASE_API_MARKER in request.url.path and request.method not in ("GET", "HEAD"):
      response = imsx_error_response(405, "Method not allowed", "invalid_selection_field")
      response.headers["Allow"] = "GET, HEAD"
      return response
  ```

- ルーター登録（`app.include_router(...)` 2 行）の直後に、全 GET ルートへ HEAD を一括追加する:

  ```python
  from fastapi.routing import APIRoute

  # FastAPI's APIRoute does not auto-add HEAD for GET routes (unlike plain
  # Starlette Route), so enable it explicitly. The GET handler runs as-is and
  # the ASGI server suppresses the body per RFC 9110.
  for route in app.routes:
      if isinstance(route, APIRoute) and "GET" in route.methods:
          route.methods.add("HEAD")
  ```

  - 対象は CASE API に限らず**全 GET ルート**（Web UI・`/health` 含む）。HEAD は GET の意味論のサブセットであり
    Web UI に許しても無害（むしろリンクチェッカーに有益）。`Mount`（`/static`）は `APIRoute` でないのでループ対象外
    （StaticFiles が自前で HEAD 対応済み）。
  - `/health` は `@app.get` 定義（L114）だが `include_router` より後の行なので、**ループは `/health` 定義より後**
    （＝モジュール末尾近く、または `/health` 定義の直後）に置くか、`/health` 定義をループより前に移す。
    実装では「ループをモジュールの最後（全ルート定義後）に置く」のが安全。
  - 副作用: FastAPI 自動生成の `/openapi.json`・`/docs` に HEAD オペレーションが並ぶ（`route.methods` から生成されるため）。
    CASE の Service Discovery は公式スキーマの静的配信（`discovery.py`）なので影響なし。cosmetic として許容し、隠す加工はしない。
  - HEAD 応答のヘッダ仕様（api-spec.md に明記する内容）: **GET と同一のハンドラが実行されるため、
    `Cache-Control` / `X-Total-Count` / `Link` / `Content-Type` / `Content-Length` は GET と完全同一。ボディのみ空**。
    処理コストも GET と同じ（DB クエリまで実行される）。読み取り専用 + `max-age=3600` の性質上許容し、最適化はしない。
  - 採らなかった代替案:
    - 各ルーターのデコレータを `methods=["GET", "HEAD"]` に書き換える — 10 ルーター超に侵襲的で漏れやすい。
    - HEAD→GET に scope を書き換える ASGI middleware — scope を in-place 変更すると uvicorn（同じ scope オブジェクトを参照）
      が GET と誤認してボディを送り**プロトコル違反**になる罠があり、コピー必須など繊細。一括ループで足りるので不採用。
    - v1p0 リダイレクト middleware は method 非依存なので変更不要（HEAD の v1p0 パスも従来どおり 301）。

### 2. CORS（src/config.py + src/main.py）

- `src/config.py` に追加:

  ```python
  # CORS: compeito is a public, read-only, credential-less API, so the
  # wildcard default is safe and maximizes interoperability. Set to [] to
  # effectively disable cross-origin access.
  cors_allow_origins: list[str] = ["*"]
  cors_max_age: int = 86400  # Access-Control-Max-Age (browsers cap: Chromium 7200s, Firefox 86400s)
  ```

  - 環境変数での上書きは pydantic-settings の list 形式（例: `CORS_ALLOW_ORIGINS='["https://example.com"]'`）。
  - **既定 `["*"]` の根拠**: (1) 認証・Cookie・セッションが存在しないため、CORS で保護すべき「credentialed な状態」がない。
    (2) private テナントの秘匿は URL 秘匿によるもので、CORS はそれを強めも弱めもしない（非ブラウザクライアントは元から
    無制限に取得可能）。(3) `*` + credentials なしなら `Vary: Origin` が付かず、`Cache-Control: public` や CDN キャッシュと
    相性が良い。(4) 公開オープンデータ API の一般的な posture に一致。限定したい運用者は env で上書きできる。
  - 空リスト `[]` は「どの Origin も許可しない」= 実質 CORS 無効（middleware は付くが許可ヘッダを出さない）。分岐は作らない。

- `src/main.py` の Middleware 節末尾（`method_not_allowed` 定義より後の行）に追加:

  ```python
  from starlette.middleware.cors import CORSMiddleware

  # Outermost user middleware (added last): handles CORS preflight before the
  # 405 middleware, and decorates all responses (Web UI included — harmless,
  # since there are no cookies or credentials anywhere in compeito).
  app.add_middleware(
      CORSMiddleware,
      allow_origins=settings.cors_allow_origins,
      allow_methods=["GET", "HEAD"],
      allow_headers=[],           # safelisted headers suffice; no custom request headers
      allow_credentials=False,    # deliberately not configurable — keep the attack surface flat
      expose_headers=["X-Total-Count", "Link"],  # pagination metadata (not CORS-safelisted)
      max_age=settings.cors_max_age,
  )
  ```

  - `allow_credentials` と `allow_methods` は**設定項目にしない**（誤設定で攻撃面を広げないための固定値）。
  - 適用範囲は**アプリ全体**（CASE API + Web UI + `/health`。`/static` は Mount のため CORSMiddleware の内側だが、
    Origin 付きリクエストにはやはりヘッダが付く）。Web UI への CORS は無害: 認証がなく、許可メソッドも GET/HEAD のみ。
    CASE パス限定のラッパーを書くより単純で、フォント等の静的アセットの cross-origin 読み込みにも有益。

### 3. OPTIONS の扱い

- **preflight OPTIONS**（`Origin` + `Access-Control-Request-Method` あり）: CORSMiddleware が最外で応答
  （200、`Access-Control-Allow-Origin` / `Access-Control-Allow-Methods: GET, HEAD` / `Access-Control-Max-Age`）。
  405 middleware には到達しない。
- **素の OPTIONS**（preflight でない）: CASE API パスでは **405 のまま + `Allow: GET, HEAD`**。
  根拠: ブラウザは素の OPTIONS を送らず、実クライアントの需要がない。200/204 + Allow で応える案は
  「受け付けるメソッドが増えたように見える」だけで実益がなく、現行の「GET 系以外は一律 405」の単純さを保つ方を採る。
  RFC 9110 上も OPTIONS を実装しないこと自体は違反ではなく、405 には Allow を正しく付ける。
- Web UI パス（マーカー外）の素の OPTIONS は現状どおり Starlette 既定（405、Allow はルートの methods 由来で
  HEAD 追加後は `GET, HEAD` になる）。

### 4. 静的公開デプロイへの注意

- 本設計は**動的 API（FastAPI アプリ）にのみ効く**。静的公開（S3 + CloudFront 等に応答 JSON を焼くデプロイ）では、
  HEAD は S3/CloudFront がネイティブに処理し、CORS は **CDN 側の設定**（CloudFront response headers policy /
  S3 CORS configuration）で同等ポリシー（`*`・GET/HEAD・expose `X-Total-Count`/`Link` 相当）を再現する必要がある。
  conformance backlog の「デプロイ上の制約」節と同種の注意として api-spec.md に明記する。
- **`allow_headers=[]`（カスタムリクエストヘッダ不可）の制約も api-spec.md に明記する**: 現方針（認証なし・公開
  read-only）では問題ないが、将来 `Authorization` 等のヘッダを送るブラウザクライアントが現れると preflight で
  落ちる。制約として文書化しておけば、その時点で設定拡張の判断ができる。

## 変更するファイル

| ファイル | 変更内容 |
|---|---|
| `src/main.py` | ① 405 middleware の条件を `method not in ("GET", "HEAD")` に変更、`Allow: GET, HEAD` に更新 ② 全ルート定義後に `APIRoute.methods.add("HEAD")` の一括ループ ③ Middleware 節末尾に `CORSMiddleware` 追加（`allow_methods=["GET","HEAD"]`・credentials なし・`expose_headers=["X-Total-Count","Link"]`） |
| `src/config.py` | `cors_allow_origins: list[str] = ["*"]`、`cors_max_age: int = 86400` を追加 |
| `tests/test_error_handling.py` | `TestMethodNotAllowed` の Allow アサーションを `"GET, HEAD"` に更新。parametrize に `"options"`（素の OPTIONS、Origin なし）を追加 |
| `tests/test_http_head_cors.py`（新規） | HEAD・CORS・preflight のテスト（下記テスト方針） |
| `tests/integration/test_error_envelope.py` | `test_non_case_405_keeps_default` のリグレッション確認（CASE 外 405 の既定挙動維持。HEAD ループで Allow 値が変わる可能性があるため要確認） |
| `docs/spec/api-spec.md`（EN/JA 両節） | ①「Unsupported HTTP methods」節: `Allow: GET, HEAD` に更新し、HEAD が許容されること・素の OPTIONS は 405 のままであることを追記 ② 新節「HEAD requests / CORS」: HEAD のヘッダ同一性（Cache-Control / X-Total-Count / Link / Content-Length は GET と同一・ボディ空）、CORS ポリシー（`*` 既定・GET/HEAD・credentials なし・expose ヘッダ・Max-Age・env での上書き）、静的公開時は CDN 側設定になる旨 ③「Security posture」節: CORS `*` が攻撃面を増やさない根拠を 1 段落追記 |
| `docs/dev/case-v1p1-conformance-backlog.md` | 実装完了時に「すでに対応済み」へ記録: 「CASE API の HEAD 許容 + CORS（certification 直接要件ではなく HTTP/ブラウザ相互運用の改善。2026-07 適合性監査 N2、PR #xxx）」 |

## 考慮すべきエッジケース

- **HEAD で 404/400 になるケース**: 未知 ID・不正パラメータの HEAD も GET と同じ imsx ハンドラを通り、
  ステータスとヘッダのみ返る（ボディはサーバ層が破棄）。正しい挙動としてテストで固定する。
- **HEAD の v1p0 パス**: redirect middleware は method 非依存なので 301（Location 付き・ボディなし）。現状維持。
- **素の OPTIONS + Origin あり（preflight でない）**: CORSMiddleware は「simple response」経路で内側に流し、
  405 応答に `Access-Control-Allow-Origin` が付く。405 のままで正しい（ブラウザからエラーが読める）。
- **不許可 Origin の preflight**（`cors_allow_origins` を限定リスト運用した場合）: Starlette は
  400 `PlainTextResponse("Disallowed CORS origin...")` を返す。imsx 形式ではないが、preflight はブラウザ内部処理であり
  CASE クライアントが直接見るものではないため許容（api-spec には書かない。本ドキュメントの記録に留める）。
- **限定リスト運用時の `Vary: Origin`**: `*` 以外を設定すると応答に `Vary: Origin` が付き、`Cache-Control: public,
  max-age=3600` のキャッシュ効率・CDN 設定に影響する。既定 `*` を推奨する理由の一つとして api-spec に注記。
- **未捕捉 500 に CORS ヘッダが付かない**: `Exception` ハンドラは `ServerErrorMiddleware`（CORS より外側）で実行される
  ため、cross-origin JS からは 500 の imsx ボディが読めない（ブラウザがブロック）。例外時のみの既知の限界として許容し、
  本ドキュメントに記録（対処するなら CORS ヘッダの手動付与が要るが、複雑さに見合わない）。
- **`Origin` ヘッダなしのリクエスト**: CORSMiddleware は完全素通し。既存クライアント・既存テストに一切影響しない。
- **HEAD のボディ空アサーションはトランスポート依存**: テスト（httpx `ASGITransport`）ではクライアント側破棄、
  本番では uvicorn 破棄と、削る主体が異なる。テストでは「ボディ空」に加えて「`Content-Length` が GET と同値」も
  検証して二重に担保する。
- **`/health` 定義位置とループの順序**: HEAD 追加ループは**全ルート定義後**に置く（先に置くと `/health` に HEAD が付かない）。
- **FastAPI の将来バージョン**: 万一 FastAPI が HEAD 自動追加を実装しても `set.add` は冪等なので壊れない。

## テスト方針

新規 `tests/test_http_head_cors.py`（既存 fixture `client` / `db_client` / `tenant` / `sample_document` を利用）:

- **HEAD 基本**: `HEAD /{tenant}/ims/case/v1p1/CFDocuments`（db_client）→ 200・ボディ空。
  同一 URL の GET と比較し `Cache-Control` / `Content-Type` / `X-Total-Count` / `Content-Length` が完全一致。
- **HEAD + Link**: CFDocument を 2 件投入し `?limit=1` → HEAD の `Link` ヘッダが GET と一致して付く。
- **HEAD 単一リソース**: `HEAD /CFDocuments/{identifier}` → 200・ボディ空。未知 ID → 404・ボディ空（ヘッダのみ）。
- **HEAD /health**: 200（HEAD 有効化ループが `include_router` 外のルートにも効いていることの確認）。
- **HEAD v1p0**: 301 リダイレクト（`follow_redirects=False`）。
- **CORS simple**: `GET .../CFDocuments` に `Origin: https://example.org` → `access-control-allow-origin: *`、
  `access-control-expose-headers` に `X-Total-Count` と `Link` を含む。**Origin なしの GET には CORS ヘッダが付かない**こと。
- **CORS preflight**: `OPTIONS .../CFDocuments` + `Origin` + `Access-Control-Request-Method: GET` → 200、
  `access-control-allow-origin: *`、`access-control-allow-methods == "GET, HEAD"`、
  `access-control-max-age == str(settings.cors_max_age)`。**405 にならない**（middleware 順序のリグレッション検知）。

既存テストの更新・リグレッション:

- `tests/test_error_handling.py::TestMethodNotAllowed`: parametrize を `["post", "put", "delete", "patch", "options"]` に拡張
  （httpx の素の OPTIONS は Origin を送らないので preflight にならない）。全メソッドで 405 + imsx 封筒 +
  `response.headers["allow"] == "GET, HEAD"`。
- `tests/test_discovery.py::test_non_get_returns_405`: Allow 値の変更に追随（POST は引き続き 405）。
  あわせて discovery JSON への HEAD が 200 になることを追加確認。
- `tests/integration/test_error_envelope.py::test_non_case_405_keeps_default`: CASE 外の 405 既定挙動が維持されること
  （HEAD 有効化により Allow 値だけ `GET, HEAD` に変わりうる。アサーションが Allow に触れていなければ変更不要）。
- CORS の限定 origin リスト・空リストの挙動は Starlette 実装に委ね、compeito 側ではテストしない
  （settings がモジュールロード時に束縛されるため app 再構築が必要になり、コストに見合わない）。

## 非対象（今回やらないこと）

- **書き込みメソッド（POST/PUT/DELETE/PATCH）の開放**: しない。読み取り専用は不変（設計原則）。
- **認証・レート制限**: 対象外（既存方針のまま。429 は従来どおりインフラ層委せ）。
- **ETag / Last-Modified / 条件付き GET（304）**: HTTP 相互運用の次候補だが別項目。今回は入れない。
- **`Access-Control-Allow-Headers` のカスタム許可**・`allow_credentials` の設定項目化: 需要がなく、攻撃面を広げないため固定。
- **FastAPI 自動生成 OpenAPI から HEAD オペレーションを隠す加工**: cosmetic のため対応しない。
- **静的公開（CloudFront 等）側の CDN 設定作業**: 本設計の適用範囲外（api-spec に注意書きのみ）。
- **未捕捉 500 応答への CORS ヘッダ付与**: 既知の限界として記録のみ（上記エッジケース参照）。
