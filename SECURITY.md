# Security Policy

## Supported Versions

The `main` branch and the latest minor release receive security fixes. Older minor versions are not officially supported; please upgrade.

| Version | Supported |
|---------|-----------|
| Latest `v1.3.x` | ✅ |
| `v1.2.x` and older | ❌ (please upgrade) |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Use one of the following private channels:

1. **GitHub Private Vulnerability Reporting** (preferred): open <https://github.com/infosign/compeito/security/advisories/new>. This creates a private advisory only the maintainers can see.
2. **Email**: <saida@infosign.co.jp> with the subject prefix `[compeito security]`. Encrypt with PGP only if you've coordinated a key in advance; plain text is acceptable.

Please include:

- The version / commit SHA you reproduced on
- Steps to reproduce, or a proof-of-concept
- The impact you believe is realistic (data exposure, RCE, DoS, etc.)
- Whether you intend to publicly disclose, and on what timeline

## Response expectations

- **Acknowledgement**: within 5 business days.
- **Triage and initial assessment**: within 10 business days.
- **Fix timeline**: depends on severity and complexity; we will keep you updated.
- **Coordinated disclosure**: we aim for a 90-day window from acknowledgement to public disclosure, but will move faster for critical issues. We credit reporters in the release notes unless asked otherwise.

## Out of scope

The following typically fall outside our security model and are accepted as known limitations:

- The default development credentials (`POSTGRES_PASSWORD=case` in `docker-compose.yml`) — these are for local development only; production deployments are expected to change them (see [docs/guide/deployment.md](docs/guide/deployment.md)).
- Lack of authentication on the public CASE API — this is by design (CASE v1.1 is a public publishing API).
- Reports based purely on automated scanner output without a working PoC.

---

# セキュリティポリシー（日本語）

## サポート対象バージョン

`main` ブランチと最新マイナーバージョンに対してセキュリティ修正を提供します。それより古いマイナーは公式サポート対象外なので、アップグレードしてください。

| バージョン | サポート |
|-----------|---------|
| 最新の `v1.3.x` | ✅ |
| `v1.2.x` 以前 | ❌（アップグレードしてください） |

## 脆弱性の報告

**セキュリティ脆弱性について、公開 GitHub Issue を作成しないでください。**

以下のいずれかの非公開チャネルを使用してください:

1. **GitHub Private Vulnerability Reporting**（推奨）: <https://github.com/infosign/compeito/security/advisories/new> を開く。メンテナのみが閲覧可能な非公開アドバイザリが作成されます。
2. **メール**: <saida@infosign.co.jp> 宛、件名プレフィックス `[compeito security]`。PGP 暗号化は事前に鍵をやり取りしていた場合のみ。平文メールでも可です。

報告内容には以下を含めてください:

- 再現したバージョン / コミット SHA
- 再現手順または PoC
- 想定される影響度（情報漏洩、RCE、DoS など）
- 公開予定の有無とタイムライン

## 対応の目安

- **受領確認**: 5 営業日以内
- **トリアージ・初期評価**: 10 営業日以内
- **修正タイムライン**: 重大度と複雑度に依存。進捗を随時共有
- **協調的開示**: 受領から 90 日以内の公開を目安とします。重大なものはより迅速に対応します。報告者の名前はリリースノートでクレジットします（希望しない場合は除く）。

## サポート対象外

以下は本プロジェクトのセキュリティモデルの範囲外で、既知の制約として扱います:

- `docker-compose.yml` のデフォルト開発用パスワード（`POSTGRES_PASSWORD=case`） — ローカル開発専用であり、本番デプロイ時には変更が必要です（[docs/guide/deployment.md](docs/guide/deployment.md) 参照）。
- 公開 CASE API に認証がないこと — 仕様上の設計です（CASE v1.1 は公開配信 API）。
- 動作する PoC を伴わない自動スキャナーの結果のみの報告。
