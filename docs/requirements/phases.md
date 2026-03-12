# フェーズ定義

## Phase 1（初期リリース）— 完了
- Docker環境でのローカル開発・実行
- 全CASEリソースのDBスキーマ（CFRubric含む）
- CASE v1.1 準拠 API 11 エンドポイント（CFRubric除く）+ 独自拡張一覧 5 エンドポイント + ヘルスチェック
- v1p0 → v1p1 リダイレクト
- CSVインポート（独自形式 + OpenSALT形式 + 簡易形式の自動判定）
- 外部CASEソースインポート（v1.1 + v1p0形式対応）
- CSVエクスポート（独自形式のみ）
- CLIツール（tenant/doc管理, import/export, db migrate）
- Web UI: トップ一覧, テナント一覧, ツリービュー, リソース詳細（/uri/ — CFDocument・CFItem・CFAssociation・lookup各種）, エラーページ
- ページネーション
- 国際化（i18n）対応（日本語・英語、Web UI + CLI）
- pytest による unit/integration テスト
- docker-compose.yml, Dockerfile
- pyproject.toml, README.md

## Phase 2 — 完了
- CSVエクスポートのOpenSALT互換形式 (`--format opensalt`)
- CFRubric API エンドポイント + CFPackage 統合
- CFRubric CSV インポート/エクスポート
- CASE API インポートでのルーブリック取り込み
- CASE v1.0 インポートの v1.1 正規化（フィールドレベル）
- GitHub Actions CI

## Phase 3（将来）
- OpenSALT 形式の互換性改善（smartLevel/notes 対応、列順調整等。詳細は [reference/opensalt-csv-format.md](../reference/opensalt-csv-format.md)）
- isChildOf 以外の CFAssociation の CSV インポート/エクスポート対応（isPeerOf, exactMatchOf 等）
- OAuth 2.0 Bearer Token 認証（オプション）
- コンピテンシーの意味検索（ベクトル埋め込み）
- フレームワーク間自動マッピング提案
