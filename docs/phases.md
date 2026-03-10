# フェーズ定義

## Phase 1（初期リリース）
- Docker環境でのローカル開発・実行
- 全CASEリソースのDBスキーマ（CFRubric含む）
- CASE v1.1 必須APIエンドポイント16種（CFRubric除く）+ ヘルスチェック
- v1p0 → v1p1 リダイレクト
- CSVインポート（独自形式 + OpenSALT形式 + 簡易形式の自動判定）
- 外部CASEソースインポート（v1.1のみ）
- CSVエクスポート（独自形式のみ）
- CLIツール（tenant/doc管理, import/export, db migrate）
- Web UI: トップ一覧, テナント一覧, ツリービュー, リソース詳細（/uri/ — CFDocument・CFItem・CFAssociation・lookup各種）, エラーページ
- ページネーション
- pytest による unit/integration テスト
- docker-compose.yml, Dockerfile
- pyproject.toml, README.md

## Phase 2
- CSVエクスポートのOpenSALT互換形式 (`--format opensalt`)
- 外部CASEソースインポートの v1.0 対応（v1.1に正規化）
- CFRubric API エンドポイント + CSVインポート/エクスポート
- AWS CDK インフラ構築
- Admin API エンドポイント（S3転送含む）
- CloudFront invalidation
- 1EdTech Conformance テスト通過（lookup リソースの required フィールド null 対応含む）

## Phase 3（将来）
- isChildOf 以外の CFAssociation の CSV インポート/エクスポート対応（isPeerOf, exactMatchOf 等）
- OAuth 2.0 Bearer Token 認証（オプション）
- コンピテンシーの意味検索（ベクトル埋め込み）
- フレームワーク間自動マッピング提案
