# Commit / PR / Release Note Conventions

## Commit messages

### Format

```
<type>: <summary (Japanese or English)>

<body (optional)>
```

### Type table

| type | Purpose | Example |
|------|---------|---------|
| `feat` | New feature | `feat: CFRubrics一覧エンドポイントを追加` |
| `fix` | Bug fix | `fix: CSVインポートでアイテムが失われるバグを修正` |
| `style` | UI / design change (no behavior change) | `style: ラベルの色をstone-500に変更` |
| `a11y` | Accessibility improvement | `a11y: WCAG AA準拠のカラーコントラスト改善` |
| `docs` | Documentation only | `docs: デプロイガイドを追加` |
| `refactor` | Refactoring (no behavior change) | `refactor: repository層のクエリを共通化` |
| `perf` | Performance improvement | `perf: ツリービューのN+1クエリを解消` |
| `test` | Adding or fixing tests | `test: CSVインポートのエッジケーステストを追加` |
| `chore` | Build / CI / dependencies, etc. | `chore: seed スクリプトを追加` |

### Rules

- Keep the summary concise. Japanese is preferred for this project; English is fine when the author works in English.
- Describe **what changes**, not **what you did** (e.g., "Add X" rather than "Did the work to add X").
- For non-trivial changes, leave a blank line after the summary and explain **why** in the body.
- Reference Issues in the body, not the summary.

## Pull request titles

### Format

```
<type>: <summary>
```

Use the same `type` prefix as commits. Keep the title under ~70 characters.

### Examples

- `feat: CFRubrics一覧エンドポイントを追加`
- `fix: CSVインポートのHCS upsertバグを修正`
- `style: ラベルとリンクの色分けで視覚的区別を改善`
- `docs: 本番デプロイガイドを追加`

### PR body

```markdown
## Summary
- 1〜3 bullet points covering what changes

## Test plan
- [ ] checklist of what you tested
```

## Release notes

### Heading rules

Use the following headings **only when relevant**, in **this order**:

| Heading | Types covered | Content |
|---------|---------------|---------|
| `## Features` | `feat` | New features |
| `## Improvements` | `style`, `a11y`, `perf`, `refactor` | UI improvements, accessibility, performance, etc. |
| `## Bug Fixes` | `fix` | Bug fixes |
| `## Documentation` | `docs` | Documentation-only changes |
| `## Maintenance` | `chore`, `test`, `ci` | Build, CI, tests, dependencies, etc. |

### Format

```markdown
## Features

### Theme or PR (#PR-number)

- Bullet describing the change

## Improvements

### Theme or PR (#PR-number)

- Bullet describing the change

**Full Changelog**: https://github.com/infosign/compeito/compare/vX.Y.Z-1...vX.Y.Z
```

### Rules

- Within each heading, group by PR or theme using `###`.
- Reference issues / PRs with `(#number)` next to the `###` heading.
- Always end the release notes with a `**Full Changelog**` link.
- The very first release (`v1.0.0`) is exempt from the format.

---

# コミット・PR・リリースノート規約（日本語）

## コミットメッセージ

### フォーマット

```
<type>: <概要（日本語または英語）>

<本文（任意）>
```

### type 一覧

| type | 用途 | 例 |
|------|------|-----|
| `feat` | 新機能・機能追加 | `feat: CFRubrics一覧エンドポイントを追加` |
| `fix` | バグ修正 | `fix: CSVインポートでアイテムが失われるバグを修正` |
| `style` | UI・デザイン変更（機能変更なし） | `style: ラベルの色をstone-500に変更` |
| `a11y` | アクセシビリティ改善 | `a11y: WCAG AA準拠のカラーコントラスト改善` |
| `docs` | ドキュメントのみの変更 | `docs: デプロイガイドを追加` |
| `refactor` | リファクタリング（機能変更なし） | `refactor: repository層のクエリを共通化` |
| `perf` | パフォーマンス改善 | `perf: ツリービューのN+1クエリを解消` |
| `test` | テストの追加・修正 | `test: CSVインポートのエッジケーステストを追加` |
| `chore` | ビルド・CI・依存関係等 | `chore: seed スクリプトを追加` |

### ルール

- 概要は簡潔に。本プロジェクトは日本語推奨、英語で作業する貢献者は英語でも可
- 「何をしたか」ではなく「何が変わるか」を書く
- 本文が必要な場合は空行を挟んで「なぜ」を説明する
- Issue に紐づく場合、本文で参照してよいが概要には含めない

## PRタイトル

### フォーマット

```
<type>: <概要>
```

コミットメッセージと同じ type prefix を使う。70文字以内を目安にする。

### 例

- `feat: CFRubrics一覧エンドポイントを追加`
- `fix: CSVインポートのHCS upsertバグを修正`
- `style: ラベルとリンクの色分けで視覚的区別を改善`
- `docs: 本番デプロイガイドを追加`

### PR本文

```markdown
## Summary
- 変更の要点を箇条書き（1〜3行）

## Test plan
- [ ] テスト項目をチェックリストで記載
```

## リリースノート

### 見出しルール

以下の見出しを**該当するものだけ**、**この順番**で使う：

| 見出し | 対応する type | 内容 |
|--------|-------------|------|
| `## Features` | `feat` | 新機能・機能追加 |
| `## Improvements` | `style`, `a11y`, `perf`, `refactor` | UI改善・アクセシビリティ・パフォーマンス等 |
| `## Bug Fixes` | `fix` | バグ修正 |
| `## Documentation` | `docs` | ドキュメントのみの変更 |
| `## Maintenance` | `chore`, `test`, `ci` | ビルド・CI・テスト・依存関係等 |

### フォーマット

```markdown
## Features

### 見出し（PR単位またはテーマ単位）(#PR番号)

- 変更点の箇条書き

## Improvements

### 見出し (#PR番号)

- 変更点の箇条書き

**Full Changelog**: https://github.com/infosign/compeito/compare/vX.Y.Z-1...vX.Y.Z
```

### ルール

- 各見出し内はPR単位またはテーマ単位の `###` で区切る
- `###` にはIssue/PR番号を `(#番号)` で付ける
- 末尾に `**Full Changelog**` リンクを必ず付ける
- 初回リリース（v1.0.0）のみ特別な構成でよい
