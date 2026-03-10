# 機能要件

## FR-1: マルチテナント

| ID | 要件 | Phase |
|----|------|-------|
| FR-1.1 | テナントをUUID v4で識別し、URLパス `/{tenant-uuid}/` で分離する | 1 |
| FR-1.2 | テナントに `is_private` フラグを持ち、private テナントはトップ一覧（`/`）に表示しない | 1 |
| FR-1.3 | private テナントもURL直接アクセスでは閲覧可能とする（URLの秘匿性で制御） | 1 |
| FR-1.4 | テナント削除時、配下の全リソース（CFDocument, CFItem, CFAssociation, lookup系）をCASCADE削除する | 1 |

## FR-2: CASE v1.1 API

| ID | 要件 | Phase |
|----|------|-------|
| FR-2.1 | CASE v1.1 準拠の全16エンドポイント（CFRubric除く）を `/{tenant}/ims/case/v1p1/` パスで提供する | 1 |
| FR-2.2 | CFPackage エンドポイントで、CFDocument・CFItems・CFAssociations・CFDefinitions を一括返却する | 1 |
| FR-2.3 | CFPackage の CFItems・CFAssociations はデータがなくても空配列として常に含める。CFDefinitions はデータがなければ省略する | 1 |
| FR-2.4 | 全一覧エンドポイントに `limit`（デフォルト100, 最大500）/ `offset`（デフォルト0）のページネーションを実装する | 1 |
| FR-2.5 | `sort` / `orderBy` / `filter` / `fields` パラメータは無視する（エラーにしない） | 1 |
| FR-2.6 | エラーレスポンスは CASE v1.1 の imsx_StatusInfo 形式で返す | 1 |
| FR-2.7 | LinkURI型（CFPackageURI, CFDocumentURI 等）は `{title, identifier, uri}` の複合オブジェクトで返す | 1 |
| FR-2.8 | `/ims/case/v1p0/` パスへのリクエストを `/ims/case/v1p1/` に301リダイレクトする | 1 |
| FR-2.9 | CASE API パスへの非GETリクエスト（POST/PUT/DELETE/PATCH）には 405 Method Not Allowed を返す | 1 |
| FR-2.10 | null 許容フィールドはレスポンスに `null` として含める（`exclude_none=False`）。CASE v1.1 仕様は含めるか省略するかを許容するが、本システムでは一貫性のため常に含める方針とする | 1 |
| FR-2.11 | CFRubric API エンドポイントを提供する | 2 |

## FR-3: バリデーション

| ID | 要件 | Phase |
|----|------|-------|
| FR-3.1 | `{tenant-uuid}` がUUID形式でない場合、400エラー（`invalid_uuid`）を返す | 1 |
| FR-3.2 | UUID形式だがテナントが存在しない場合、404エラー（`unknownobject`）を返す | 1 |
| FR-3.3 | `/uri/{uuid}` はテナントスコープ内で検索し、別テナントのリソースには404を返す | 1 |
| FR-3.4 | リソースID（`/CFItems/{id}` 等の `{id}`）がUUID形式でない場合、400エラー（`invalid_uuid`）を返す | 1 |
| FR-3.5 | リソースIDがUUID形式だがリソースが存在しない場合、404エラー（`unknownobject`）を返す | 1 |
| FR-3.6 | `GET /CFItems/{id}/associations` でアイテムが存在しない場合、空配列ではなく404エラーを返す | 1 |

## FR-4: ヘルスチェック

| ID | 要件 | Phase |
|----|------|-------|
| FR-4.1 | `GET /health` で `{"status": "ok"}` を返す（認証不要、テナントパス不要） | 1 |
| FR-4.2 | DB接続確認は行わない（コールドスタート高速化を優先） | 1 |

## FR-5: 管理API

| ID | 要件 | Phase |
|----|------|-------|
| FR-5.1 | テナントCRUD（作成・一覧・単一取得・更新・削除）を `/admin/tenants` で提供する | 2 |
| FR-5.2 | フレームワーク一覧・削除を `/admin/tenants/{id}/documents` で提供する | 2 |
| FR-5.3 | CSVインポートを `/admin/tenants/{id}/import/csv` で提供する（S3経由） | 2 |
| FR-5.4 | 外部CASEソースインポートを `/admin/tenants/{id}/import/case-url` で提供する | 2 |
| FR-5.5 | CSVエクスポートを `/admin/tenants/{id}/documents/{doc-uuid}/export/csv` で提供する（S3経由） | 2 |
| FR-5.6 | CloudFront invalidation を `/admin/cache/invalidate` で提供する | 2 |
| FR-5.7 | Alembicマイグレーションを `/admin/migrate` で提供する | 2 |
| FR-5.8 | CSVアップロード用 presigned URL を `/admin/upload-url` で提供する | 2 |
| FR-5.9 | AWS環境では Bearer token 認証を行い、Docker環境では認証なしとする | 2 |
| FR-5.10 | エラーレスポンスは `{"error": "...", "detail": "..."}` 形式とする（imsx_StatusInfo ではない） | 2 |

## FR-6: CSVインポート

| ID | 要件 | Phase |
|----|------|-------|
| FR-6.1 | 独自形式・OpenSALT形式・簡易形式の3種類をヘッダー行から自動判定する | 1 |
| FR-6.2 | `#` で始まるメタデータ行からCFDocumentフィールドを設定する | 1 |
| FR-6.3 | `--doc` 未指定時は新規CFDocumentを作成、指定時は既存を更新する | 1 |
| FR-6.4 | CFItem の upsert を Identifier一致 → humanCodingScheme一致 の優先順で行う | 1 |
| FR-6.5 | lookup テーブル（CFItemType, CFSubject, CFConcept）を同一テナント内 `title` 完全一致で自動生成する | 1 |
| FR-6.6 | isChildOf の CFAssociation を親子関係から自動生成する | 1 |
| FR-6.7 | 既存ドキュメントの更新時（`--doc` 指定、または OpenSALT `Is Part Of` で既存ドキュメントにマッチした場合）、該当ドキュメントの既存 isChildOf Association を全削除してから再生成する | 1 |
| FR-6.8 | sequenceNumber が空の場合、同一親内で出現順に 10, 20, 30... で自動採番する（各親ごとに独立したカウンタ） | 1 |
| FR-6.9 | 簡易形式ではインデント（スペース2つ or タブ1つ = 1段）で階層を判定する | 1 |
| FR-6.10 | 新規作成リソースの URI を `{BASE_URL}/{tenant_id}/uri/{identifier}` で生成する | 1 |
| FR-6.11 | 同一CSV内で Identifier が重複した場合、後の行を採用し警告を出力する | 1 |
| FR-6.12 | depth を isChildOf から BFS で計算し、循環参照を検出する | 1 |
| FR-6.13 | インポート結果（created/updated/skipped/warnings）をレポート出力する | 1 |
| FR-6.14 | UTF-8（BOM付き/無し）、CR+LF/LF の両方に対応する | 1 |

## FR-7: 外部CASEソースインポート

| ID | 要件 | Phase |
|----|------|-------|
| FR-7.1 | CASE v1.1 API から CFPackage JSON を取得し、DB に保存する | 1 |
| FR-7.2 | 外部リソースの URI と identifier をそのまま保持する（自サーバーの URI で上書きしない） | 1 |
| FR-7.3 | CFDefinitions（CFItemType, CFSubject, CFConcept, CFLicense, CFAssociationGrouping）も保存する | 1 |
| FR-7.4 | 接続エラー・HTTPエラー・JSONパースエラー・SSL証明書エラーを区別してエラー終了する | 1 |
| FR-7.5 | CFPackage内の個別リソース不正は警告付きでスキップし、他は処理を続行する | 1 |
| FR-7.6 | `--doc` 未指定時は外部CFDocumentのidentifierで既存を検索し、存在すれば更新、なければ新規作成する。`--doc` 指定時は既存を上書き更新する | 1 |
| FR-7.7 | CASE v1.0 のレスポンスを v1.1 形式に正規化して保存する | 2 |

## FR-8: CSVエクスポート

| ID | 要件 | Phase |
|----|------|-------|
| FR-8.1 | 独自形式でエクスポートする（Identifier・parentIdentifier・sequenceNumber を含む） | 1 |
| FR-8.2 | ツリーの depth-first 順にソートする（sequence_number → human_coding_scheme → identifier） | 1 |
| FR-8.3 | メタデータ行（`#title`, `#version` 等）を出力する | 1 |
| FR-8.4 | OpenSALT互換形式でエクスポートする（`--format opensalt`） | 2 |

## FR-9: Web UI

| ID | 要件 | Phase |
|----|------|-------|
| FR-9.1 | `GET /` で公開テナント一覧を表示する（private テナントは非表示） | 1 |
| FR-9.2 | `GET /{tenant}/` でフレームワーク一覧（CFDocument の title, lastChangeDateTime, アイテム数）を表示する | 1 |
| FR-9.3 | `GET /{tenant}/cftree/doc/{doc}` で2ペインのツリービューを表示する（左: ツリー、右: 詳細） | 1 |
| FR-9.4 | ツリービューは Level 1-2 を SSR、Level 3+ を HTMX 遅延ロードで返す | 1 |
| FR-9.5 | `GET /{tenant}/uri/{uuid}` でリソース詳細ページを表示する（CFItem, CFDocument, lookup, CFAssociation 対応） | 1 |
| FR-9.6 | `/uri/{uuid}` ページは Open Badge Factory 等の外部システムからリンクされる公開ページとして機能する | 1 |
| FR-9.7 | モバイルではツリーのみ表示し、アイテムタップで `/uri/` に遷移する | 1 |
| FR-9.8 | エラーページ（404/400/500）をユーザーフレンドリーに表示する | 1 |
| FR-9.9 | ツリービューの `?item={uuid}` パラメータでアイテムへのディープリンクをサポートする（ルートから該当アイテムまでの展開パスをSSRで返す） | 1 |

## FR-10: CLI

| ID | 要件 | Phase |
|----|------|-------|
| FR-10.1 | テナント管理（create, list, update, delete）コマンドを提供する | 1 |
| FR-10.2 | フレームワーク管理（list, delete）コマンドを提供する | 1 |
| FR-10.3 | CSVインポート（`import csv`）コマンドを提供する | 1 |
| FR-10.4 | 外部CASEソースインポート（`import case-url`）コマンドを提供する | 1 |
| FR-10.5 | CSVエクスポート（`export csv`）コマンドを提供する | 1 |
| FR-10.6 | DBマイグレーション（`db migrate`）コマンドを提供する | 1 |
| FR-10.7 | キャッシュ無効化（`cache invalidate`）コマンドを提供する（Phase 1 ではスタブのみ。AWS環境でのみ有効） | 2 |
| FR-10.8 | Docker環境では `DATABASE_URL` で直接DB接続する。AWS環境では管理API経由で動作する（管理APIはPhase 2） | 1/2 |
| FR-10.9 | 削除コマンドは確認プロンプトを表示し、`--force` でスキップ可能とする | 1 |
| FR-10.10 | rich ライブラリでテーブル・プログレスバー・カラー出力を行う | 1 |

## FR-11: コンテントネゴシエーション

| ID | 要件 | Phase |
|----|------|-------|
| FR-11.1 | コンテントネゴシエーションは使わない（CloudFront キャッシュとの競合回避） | 1 |
| FR-11.2 | Web UI パス（`/`, `/{tenant}/`, `/cftree/`, `/uri/{uuid}`）は常にHTMLを返す | 1 |
| FR-11.3 | CASE API パス（`/ims/case/v1p1/`）は常にJSONを返す | 1 |

## FR-12: Phase 3 機能（将来）

| ID | 要件 | Phase |
|----|------|-------|
| FR-12.1 | isChildOf 以外の CFAssociation（isPeerOf, exactMatchOf 等）の CSV インポート/エクスポートに対応する | 3 |
| FR-12.2 | コンピテンシーの意味検索をベクトル埋め込みで提供する | 3 |
| FR-12.3 | フレームワーク間の自動マッピング提案機能を提供する | 3 |
