<!--
Thanks for your contribution! Please read CONTRIBUTING.md and docs/dev/conventions.md before opening a PR.
寄稿ありがとうございます！PR を出す前に CONTRIBUTING.md と docs/dev/conventions.md にひととおり目を通してください。
-->

## Summary

<!--
One to three bullet points describing what changes and why.
Use Japanese or English — whichever is more natural.

何がどう変わるかと、その理由を 1〜3 行で。日本語でも英語でもどちらでも構いません。
-->

-
-

## Test plan

<!--
Checklist of what you tested. Include relevant commands and outputs where helpful.
何をテストしたかチェックリストで。コマンドや出力が補足として有用なら添えてください。
-->

- [ ] `uv run pytest tests/` passes locally
- [ ] `uv run ruff check src/ tests/ cli.py` passes
- [ ] `uv run ruff format --check src/ tests/ cli.py` passes
- [ ] Updated relevant documentation in `docs/` (if applicable) / 関連する `docs/` を更新した（必要なら）

## Related issues / 関連 Issue

<!-- Closes #123 / Refs #456 など -->
