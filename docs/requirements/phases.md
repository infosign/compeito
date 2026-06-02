# Phases

## Phase 1 (initial release) — complete
- Local development / execution with Docker
- DB schema for all CASE resources (including CFRubric)
- 11 CASE v1.1 compliant API endpoints (excluding CFRubric) + 5 custom listing endpoints + health check
- v1p0 → v1p1 redirect
- CSV import (auto-detects custom format / OpenSALT format / simple format)
- External CASE source import (v1.1 and v1p0 formats)
- CSV export (custom format only)
- CLI (tenant/doc management, import/export, db migrate)
- Web UI: top list, tenant list, tree view, resource detail (`/uri/` — CFDocument / CFItem / CFAssociation / various lookups), error pages
- Pagination
- Internationalization (Japanese / English, Web UI + CLI)
- Unit / integration tests with pytest
- docker-compose.yml, Dockerfile
- pyproject.toml, README.md

## Phase 2 — complete
- OpenSALT-compatible CSV export (`--format opensalt`)
- CFRubric API endpoints + CFPackage integration
- CFRubric CSV import / export
- Rubric ingestion in the CASE API import
- v1.0 → v1.1 normalization on import (field-level)
- GitHub Actions CI

## Phase 3 (future)
- Improved OpenSALT compatibility (smartLevel / notes support, column ordering, etc.; see [reference/opensalt-csv-format.md](../reference/opensalt-csv-format.md))
- CSV import / export for CFAssociation types other than `isChildOf` (`isPeerOf`, `exactMatchOf`, etc.)
- OAuth 2.0 Bearer Token authentication (optional)
- Semantic search over competencies (vector embeddings)
- Automatic cross-framework mapping suggestions

---

# フェーズ定義（日本語）

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
