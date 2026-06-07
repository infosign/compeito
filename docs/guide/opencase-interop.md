# OpenCASE Interoperability Guide

A practical guide to using [OpenCASE](https://github.com/1EdTech/OpenCASE) (the 1EdTech reference implementation) as an editor and COMPEITO as a publishing endpoint.

OpenCASE and COMPEITO target different parts of the CASE workflow — OpenCASE provides a visual editor, multi-user collaboration, and version history; COMPEITO is a lightweight publishing server with Japanese/English UI and easy embedding. Combining them lets each tool do what it's best at, with the CASE v1.1 standard as the contract between them.

## Topology

There are three realistic deployment topologies, all supported in principle:

| Topology | OpenCASE | COMPEITO | Typical use |
|---|---|---|---|
| **A** | Public (internet-reachable) | Public | Org publishes via a clear two-stage pipeline |
| **B** | Private (LAN / `localhost`) | Public | Authors edit privately; publish only the final framework externally |
| **C** | Private | Private | Closed evaluation / development |

This guide currently covers **Topology A** end-to-end. Topologies B and C require additional COMPEITO commands that are being added incrementally — sections will be appended as those commands land.

## OpenCASE's license model

OpenCASE uses the CFDocument's `licenseURI` field for two things at once:

1. **Rights statement** — what consumers may do with the framework (CC0 / CC BY / etc.)
2. **Public access gate** — whether the framework's CASE Provider API can be fetched **without authentication**

Every OpenCASE tenant is seeded with five licenses (UUIDs are stable across all tenants):

| Title | UUID suffix | Unauthenticated read? |
|---|---|---|
| Public Domain (CC0 1.0) | `...0001` | Yes |
| Open — Credit Required (CC BY 4.0) | `...0002` | Yes |
| Educational Use (CC BY-NC-SA 4.0) | `...0003` | Yes |
| View and Share Only (CC BY-NC-ND 4.0) | `...0004` | **No** (Bearer token required) |
| Private — All Rights Reserved | `...0005` | **No** (Bearer token required) |
| _(no license set)_ | — | **No** (private by default) |

The full UUID prefix is `c0c0c0c0-0000-4000-a000-00000000000X`.

CASE clients such as Open Badge Factory, COMPEITO, and TAO Testing fetch frameworks **without** OpenCASE credentials. For these clients to read a framework, the framework's `licenseURI` MUST be one of the three CC-based public licenses above. Custom licenses can still be set and are preserved verbatim through the API, but OpenCASE treats them as private (auth required).

COMPEITO, in contrast, does not enforce access control based on `licenseURI`. The license is stored as metadata and shown on every detail page, but the framework is always served publicly on COMPEITO once imported.

## Topology A: public OpenCASE → public COMPEITO

The simplest topology. OpenCASE publishes a framework with a public license; COMPEITO fetches it via the CASE Provider API.

### Step 1 — Author a framework in OpenCASE

In the OpenCASE editor, create or open a framework, then:

1. Click the framework root node on the canvas.
2. In the side panel, find the **License** dropdown.
3. Select one of the three public licenses (CC0 / CC BY / CC BY-NC-SA).
4. Save / publish.

> **Without a public license, COMPEITO's import will fail with HTTP 401 from OpenCASE.** If you forgot this step, OpenCASE returns an `imsx_StatusInfo` error message of `"Authentication required to access this framework."`.

### Step 2 — Get the CFPackage URL

The CFPackage URL is structured as:

```
https://{OPENCASE_HOST}/ims/case/v1p1/CFPackages/{CFDocument_identifier}
```

You can find the identifier in the OpenCASE editor's framework metadata pane, or from `GET /ims/case/v1p1/CFDocuments` on the OpenCASE API.

You can validate that the framework is publicly fetchable:

```bash
curl -s "https://YOUR_OPENCASE/ims/case/v1p1/CFPackages/{CFDocument_id}" \
  | head -c 300
```

If you see CASE JSON (`{"CFDocument": ..., "CFItems": [...], ...`), the license is set correctly.

### Step 3 — Import into COMPEITO

Create a tenant on COMPEITO if you don't already have one:

```bash
docker compose exec app uv run python cli.py tenant create --name "My Organization"
# Created tenant: 550e8400-e29b-41d4-a716-446655440000 (My Organization, public)
```

Import the framework:

```bash
docker compose exec app uv run python cli.py import case \
  --tenant 550e8400-e29b-41d4-a716-446655440000 \
  --url https://YOUR_OPENCASE/ims/case/v1p1/CFPackages/{CFDocument_id}
```

Expected output:

```
'Sample Framework' ({id}) をインポートしました
  アイテム: 36 作成, 0 更新, 0 スキップ
  アソシエーション: 36 作成, 0 更新, 0 スキップ
```

The license you set in OpenCASE is preserved as `licenseURI` metadata on the imported CFDocument and is shown on every detail page in COMPEITO (with a "from document" badge on items that don't have their own license).

### Updating

When you edit and republish the framework in OpenCASE, simply re-run the same `import case` command. COMPEITO upserts based on the framework's UUID, so items / associations are updated in place.

## Topology B: private OpenCASE → public COMPEITO

When OpenCASE is on a private network (LAN, `localhost`, behind a corporate firewall, etc.), COMPEITO cannot reach OpenCASE's CFPackage URL. Two alternatives:

1. **File-based handoff (this section)** — Export the CFPackage JSON from OpenCASE manually and import it into COMPEITO without any network call between the two. The simplest approach and works regardless of OpenCASE's license setting (because COMPEITO never touches OpenCASE's API gate).
2. **Temporary tunnel** — Use a tool like `ngrok` to expose OpenCASE temporarily; then proceed as Topology A. Useful for one-off publishing, but be aware that the framework must have a public license while the tunnel is active.

### Step 1 — Export the CFPackage JSON from OpenCASE

Anyone with read access to the OpenCASE framework can save the CFPackage JSON. From the OpenCASE host (or through a tunnel during a brief authenticated session):

```bash
# Get a Bearer token via Keycloak (one of the tenant's user credentials)
TOKEN=$(curl -s -X POST "https://YOUR_OPENCASE/realms/opencase/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" -d "client_id=tenant-{TENANT}" \
  -d "username=YOUR_EMAIL" -d "password=YOUR_PASSWORD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Save the CFPackage to a local file
curl -s "https://YOUR_OPENCASE/ims/case/v1p1/CFPackages/{CFDocument_id}" \
  -H "Authorization: Bearer $TOKEN" > framework.json
```

The license on the framework can be anything (CC0, all-rights-reserved, custom, none) — authenticated fetch always succeeds.

### Step 2 — Transfer the file

Move `framework.json` to the COMPEITO host by any means: scp / USB / cloud-storage upload / email / etc. There is no network connection between OpenCASE and COMPEITO at this point.

### Step 3 — Import into COMPEITO

```bash
docker compose exec app uv run python cli.py import case \
  --tenant {COMPEITO_tenant_id} \
  --file framework.json
```

Expected output (identical shape to `import case --url`):

```
'Sample Framework' ({id}) をインポートしました
  アイテム: 36 作成, 0 更新, 0 スキップ
  アソシエーション: 36 作成, 0 更新, 0 スキップ
```

The file's `licenseURI` (if set) is preserved as metadata on the imported CFDocument and displayed on every detail page, exactly as in Topology A.

### Updating

Re-export and re-run `import case --file` with the same `--tenant`. COMPEITO upserts by framework UUID.

> **Note**: `import case --file` accepts CFPackage JSON exported from **any CASE-conformant tool**, not just OpenCASE — OpenSALT, Standards Satchel, or a hand-edited JSON all work the same way.

## Reverse direction: COMPEITO → OpenCASE

In some workflows you'll want to move the other way — share a COMPEITO-hosted framework with someone running OpenCASE. Two approaches:

### Option 1 — OpenCASE pulls directly from COMPEITO (public COMPEITO)

If COMPEITO is on the internet, OpenCASE's import-from-URL endpoint can fetch your CFPackage:

```bash
curl -X POST "https://YOUR_OPENCASE/management/tenants/{tenant_id}/ims/case/v1p1/CFPackages/import" \
  -H "Authorization: Bearer $OPENCASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"endpointUrl": "https://YOUR_COMPEITO/{tenant}/ims/case/v1p1/CFPackages/{doc_id}"}'
```

COMPEITO is public by default, so no license / auth setup is required on the COMPEITO side. OpenCASE downloads the CFPackage and stores it in the specified tenant.

> The OpenCASE editor expects one of the 5 seeded license UUIDs (`c0c0c0c0-...0001`–`...0005`) to grant public access. If your framework has a custom license, OpenCASE will import it but treat the framework as private. To make it publicly readable from OpenCASE afterwards, change the license to one of the public CC variants in the OpenCASE editor.

### Option 2 — Export from COMPEITO as a JSON file

Use COMPEITO's `export case` command to write a CASE v1.1 CFPackage JSON file:

```bash
docker compose exec app uv run python cli.py export case \
  --tenant {tenant_id} \
  --doc {doc_id} \
  --file framework.json
# 36 アイテムを framework.json にエクスポートしました
```

The output is **byte-for-byte identical** to what `GET /ims/case/v1p1/CFPackages/{id}` would return. You can:

- Re-import into a different COMPEITO tenant via `import case --file` (handy for migrations / backups)
- Host the file at any URL and point OpenCASE's import-from-URL endpoint at it
- Share with collaborators who can manually feed it to their CASE-conformant editor

The exported JSON has top-level `CFDocument` / `CFItems` / `CFAssociations` / `CFDefinitions` / `CFRubrics` (no `CFPackage` wrapper, per CASE v1.1 spec).

## Known interop caveats

A few minor things to be aware of when going OpenCASE → COMPEITO:

- **`caseVersion: "1.1"` is not preserved in OpenCASE responses.** OpenCASE strips the `caseVersion` field from its CFDocument responses. For URL-based imports (Topology A) this is handled silently because COMPEITO trusts the `v1p1` segment in the source URL and skips the structural heuristic. For file-based imports (Topology B), COMPEITO falls back to a structural check and may emit a benign warning ("Detected CASE v1.0 response, normalizing to v1.1 format"). To suppress this warning, add `"caseVersion": "1.1"` to the CFDocument inside the exported JSON before importing.
- **Top-level items have no `isChildOf -> CFDocument` association.** OpenCASE doesn't generate this association for root items; OpenSALT does. COMPEITO handles both conventions: when a framework lacks the `isChildOf -> CFDocument` edge, items with no `isChildOf` at all are treated as roots and the depth tree is computed correctly. No action required; this is mentioned only for transparency.

## See also

- [Architecture overview](../spec/architecture.md) — COMPEITO's design and how it relates to OpenSALT / OpenCASE
- [API specification](../spec/api-spec.md) — CASE v1.1 endpoint details
- [Import logic](../spec/import-logic.md) — How external CASE sources are normalized and imported
- [OpenCASE on GitHub](https://github.com/1EdTech/OpenCASE)

---

# OpenCASE 相互運用ガイド（日本語）

[OpenCASE](https://github.com/1EdTech/OpenCASE)（1EdTech 公式リファレンス実装）をエディタとして、COMPEITO を配信エンドポイントとして組み合わせる運用ガイドです。

OpenCASE と COMPEITO は CASE ワークフローの異なる部分を担います。OpenCASE はビジュアルエディタ、共同編集、バージョン履歴を提供し、COMPEITO は英日対応 UI と組み込みやすさを重視した軽量配信サーバーです。CASE v1.1 標準を契約として、両者を組み合わせることでそれぞれの得意領域を活かせます。

## トポロジー

3 つの現実的な配置パターンを想定しています:

| トポロジー | OpenCASE | COMPEITO | 想定用途 |
|---|---|---|---|
| **A** | 公開（インターネット到達可） | 公開 | 編集と配信を 2 段階で公開運用 |
| **B** | プライベート（LAN / `localhost`） | 公開 | 編集は内部で、完成したフレームワークだけ外部公開 |
| **C** | プライベート | プライベート | クローズドな検証 / 開発 |

本ガイドは現時点で **トポロジー A** をエンドツーエンドでカバーします。トポロジー B / C には COMPEITO 側の追加コマンドが必要で、段階的に追加していきます。コマンドが揃い次第、対応する節を追記します。

## OpenCASE のライセンスモデル

OpenCASE は CFDocument の `licenseURI` フィールドを 2 つの役割で使います:

1. **権利情報** — フレームワークの利用許諾（CC0 / CC BY 等）
2. **公開アクセス制御** — CASE Provider API を**認証なし**で fetch できるかどうか

各 OpenCASE テナントには 5 種類のライセンスがシードされます（UUID は全テナント共通）:

| 名称 | UUID 末尾 | 認証なし read |
|---|---|---|
| Public Domain (CC0 1.0) | `...0001` | 可 |
| Open — Credit Required (CC BY 4.0) | `...0002` | 可 |
| Educational Use (CC BY-NC-SA 4.0) | `...0003` | 可 |
| View and Share Only (CC BY-NC-ND 4.0) | `...0004` | **不可**（Bearer トークン必須） |
| Private — All Rights Reserved | `...0005` | **不可**（Bearer トークン必須） |
| _（ライセンス未設定）_ | — | **不可**（デフォルト private） |

UUID の完全な接頭辞は `c0c0c0c0-0000-4000-a000-00000000000X` です。

Open Badge Factory、COMPEITO、TAO Testing といった CASE クライアントは OpenCASE の認証情報なしでフレームワークを fetch します。これらのクライアントから読み取れるようにするには、`licenseURI` を上記の CC ベース公開ライセンス 3 種のいずれかに設定する必要があります。カスタムライセンスも設定可能で API では正確に保持されますが、OpenCASE は private（認証必須）として扱います。

一方 COMPEITO は `licenseURI` をアクセス制御に使いません。ライセンス情報はメタデータとして保存され、すべての詳細ページに表示されますが、フレームワークは取り込まれた時点で COMPEITO 上では常に公開状態となります。

## トポロジー A: 公開 OpenCASE → 公開 COMPEITO

最もシンプルな構成です。OpenCASE で公開ライセンスを設定したフレームワークを、COMPEITO が CASE Provider API 経由で取り込みます。

### ステップ 1 — OpenCASE でフレームワークを作成

OpenCASE のエディタでフレームワークを作成 or 開いて:

1. キャンバス上のフレームワーク root ノードをクリック
2. 右側のプロパティパネルで **License** ドロップダウンを探す
3. 公開ライセンス 3 種（CC0 / CC BY / CC BY-NC-SA）のいずれかを選択
4. 保存 / 公開

> **公開ライセンスを設定していないと、COMPEITO のインポートは OpenCASE から HTTP 401 で失敗します。** 設定忘れの場合、OpenCASE は `imsx_StatusInfo` 形式で `"Authentication required to access this framework."` を返します。

### ステップ 2 — CFPackage URL の取得

CFPackage URL は以下の形式です:

```
https://{OPENCASE_HOST}/ims/case/v1p1/CFPackages/{CFDocument_identifier}
```

CFDocument の identifier は OpenCASE エディタのフレームワークメタデータ画面、または `GET /ims/case/v1p1/CFDocuments` から取得できます。

公開 fetch ができるか事前確認:

```bash
curl -s "https://YOUR_OPENCASE/ims/case/v1p1/CFPackages/{CFDocument_id}" \
  | head -c 300
```

CASE JSON（`{"CFDocument": ..., "CFItems": [...], ...`）が表示されればライセンス設定は正しいです。

### ステップ 3 — COMPEITO にインポート

COMPEITO 側でテナントを作成（既存テナントを使う場合はスキップ）:

```bash
docker compose exec app uv run python cli.py tenant create --name "私の組織"
# テナントを作成しました: 550e8400-e29b-41d4-a716-446655440000 (私の組織, 公開)
```

フレームワークを取り込み:

```bash
docker compose exec app uv run python cli.py import case \
  --tenant 550e8400-e29b-41d4-a716-446655440000 \
  --url https://YOUR_OPENCASE/ims/case/v1p1/CFPackages/{CFDocument_id}
```

出力例:

```
'サンプルフレームワーク' ({id}) をインポートしました
  アイテム: 36 作成, 0 更新, 0 スキップ
  アソシエーション: 36 作成, 0 更新, 0 スキップ
```

OpenCASE で設定したライセンスはインポートされた CFDocument の `licenseURI` メタデータとして保持され、COMPEITO の全詳細ページに表示されます（個別ライセンス未設定のアイテムには「ドキュメントから継承」バッジ付きで表示）。

### 更新時

OpenCASE で編集して再公開した場合は、同じ `import case` コマンドを再実行するだけです。COMPEITO はフレームワーク UUID で upsert するため、items / associations は同一行で更新されます。

## トポロジー B: プライベート OpenCASE → 公開 COMPEITO

OpenCASE がプライベートネットワーク（LAN、`localhost`、社内 firewall 内など）にあって COMPEITO から CFPackage URL に到達できないケースです。2 つの選択肢があります:

1. **ファイル経由のハンドオフ（この節）** — OpenCASE から CFPackage JSON を手動でエクスポートし、COMPEITO にファイルとして取り込む。両者の間にネットワーク接続を一切必要としません。OpenCASE 側のライセンス設定に関係なく動作します（COMPEITO は OpenCASE の API ゲートを通らないため）
2. **一時的なトンネル** — `ngrok` 等で OpenCASE を一時的に外部公開し、トポロジー A の手順で取り込む。単発の公開には便利ですが、トンネル中はフレームワークに公開ライセンスが設定されている必要があります

### ステップ 1 — OpenCASE から CFPackage JSON をエクスポート

OpenCASE フレームワークへの読み取り権限を持つ人なら誰でも CFPackage JSON を保存できます。OpenCASE ホスト上で（または短時間の認証セッションでトンネル経由で）:

```bash
# Keycloak から Bearer token を取得（テナント内ユーザーの認証情報を使用）
TOKEN=$(curl -s -X POST "https://YOUR_OPENCASE/realms/opencase/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" -d "client_id=tenant-{TENANT}" \
  -d "username=YOUR_EMAIL" -d "password=YOUR_PASSWORD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# CFPackage をローカルファイルに保存
curl -s "https://YOUR_OPENCASE/ims/case/v1p1/CFPackages/{CFDocument_id}" \
  -H "Authorization: Bearer $TOKEN" > framework.json
```

フレームワークのライセンスは何でも構いません（CC0 / All Rights Reserved / カスタム / 未設定 など）— 認証付き fetch は常に成功します。

### ステップ 2 — ファイルを転送

`framework.json` を任意の手段（scp / USB / クラウドストレージ / メール等）で COMPEITO ホストに移送します。この段階で OpenCASE と COMPEITO の間にネットワーク接続は不要です。

### ステップ 3 — COMPEITO に取り込み

```bash
docker compose exec app uv run python cli.py import case \
  --tenant {COMPEITO_tenant_id} \
  --file framework.json
```

出力例（`import case --url` と同じ形式）:

```
'サンプルフレームワーク' ({id}) をインポートしました
  アイテム: 36 作成, 0 更新, 0 スキップ
  アソシエーション: 36 作成, 0 更新, 0 スキップ
```

ファイル内に含まれる `licenseURI`（設定されていれば）は CFDocument のメタデータとして取り込まれ、トポロジー A と同じく全詳細ページに表示されます。

### 更新時

再エクスポートして同じ `--tenant` で `import case --file` を再実行するだけです。COMPEITO はフレームワーク UUID で upsert します。

> **補足**: `import case --file` は OpenCASE 限定ではなく、**任意の CASE 準拠ツール**がエクスポートした CFPackage JSON を受け入れます — OpenSALT、Standards Satchel、手書きの JSON もすべて同じように動作します。

## 逆方向: COMPEITO → OpenCASE

COMPEITO に登録したフレームワークを OpenCASE 側に渡したい場合の選択肢:

### オプション 1 — OpenCASE が COMPEITO から直接 pull する（公開 COMPEITO の場合）

COMPEITO がインターネットに公開されているなら、OpenCASE の import-from-URL エンドポイントから CFPackage を fetch できます:

```bash
curl -X POST "https://YOUR_OPENCASE/management/tenants/{tenant_id}/ims/case/v1p1/CFPackages/import" \
  -H "Authorization: Bearer $OPENCASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"endpointUrl": "https://YOUR_COMPEITO/{tenant}/ims/case/v1p1/CFPackages/{doc_id}"}'
```

COMPEITO はデフォルトで public 配信なので、COMPEITO 側にライセンス設定や認証準備は不要です。OpenCASE が CFPackage をダウンロードして、指定したテナントに保存します。

> OpenCASE のエディタは 5 種のシード済みライセンス UUID（`c0c0c0c0-...0001`〜`...0005`）でしか public 扱いになりません。フレームワークがカスタムライセンスだった場合、OpenCASE はインポートはしますが private 扱いにします。OpenCASE 側で公開可能にしたい場合は、エディタで CC ベースの公開ライセンス 3 種のいずれかに付け替えてください。

### オプション 2 — COMPEITO から JSON ファイルにエクスポート

COMPEITO の `export case` コマンドで CASE v1.1 CFPackage JSON ファイルを書き出します:

```bash
docker compose exec app uv run python cli.py export case \
  --tenant {tenant_id} \
  --doc {doc_id} \
  --file framework.json
# 36 アイテムを framework.json にエクスポートしました
```

出力は `GET /ims/case/v1p1/CFPackages/{id}` のレスポンスと**バイト単位で同一**です。以下のような使い方ができます:

- 別の COMPEITO テナントに `import case --file` で再取り込み（移行 / バックアップに便利）
- 任意の URL でホストして OpenCASE の import-from-URL エンドポイントから参照
- CASE 準拠の他のエディタに渡す（手動取り込み）

エクスポートされた JSON はトップレベルに `CFDocument` / `CFItems` / `CFAssociations` / `CFDefinitions` / `CFRubrics` を持ち、`CFPackage` ラッパーは付きません（CASE v1.1 仕様準拠）。

## 既知の相互運用上の注意点

OpenCASE → COMPEITO 方向で、知っておくと便利なポイント:

- **OpenCASE のレスポンスは `caseVersion: "1.1"` を含まない。** OpenCASE は CFDocument レスポンスから `caseVersion` フィールドを落とします。URL 経由のインポート（トポロジー A）では COMPEITO がソース URL の `v1p1` を信頼して構造ヒューリスティックをスキップするため、静かに正しく処理されます。ファイル経由のインポート（トポロジー B）では構造判定にフォールバックするため、無害な警告（「Detected CASE v1.0 response, normalizing to v1.1 format」）が出ることがあります。この警告を抑制したい場合は、エクスポートした JSON の CFDocument に `"caseVersion": "1.1"` を手動追加してから取り込んでください。
- **トップレベルアイテムに `isChildOf -> CFDocument` association がない。** OpenCASE はルートアイテムにこの association を生成しません（OpenSALT は生成する）。COMPEITO は両方の慣行に対応しており、`isChildOf -> CFDocument` がないフレームワークでは「`isChildOf` を一つも持たないアイテム」をルートとして扱い、深さの計算を正しく行います。対応は不要で、念のための説明です。

## 関連ドキュメント

- [アーキテクチャ概要](../spec/architecture.md) — COMPEITO の設計と OpenSALT / OpenCASE との関係
- [API 仕様](../spec/api-spec.md) — CASE v1.1 エンドポイント詳細
- [インポートロジック](../spec/import-logic.md) — 外部 CASE ソースの正規化と取り込み処理
- [OpenCASE on GitHub](https://github.com/1EdTech/OpenCASE)
