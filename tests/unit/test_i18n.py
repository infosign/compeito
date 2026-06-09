"""Tests for i18n module."""

from src.i18n import detect_lang_from_env, get_translator, parse_accept_language


class TestParseAcceptLanguage:
    def test_simple_ja(self):
        assert parse_accept_language("ja") == "ja"

    def test_simple_en(self):
        assert parse_accept_language("en") == "en"

    def test_ja_with_region(self):
        assert parse_accept_language("ja-JP") == "ja"

    def test_en_with_region(self):
        assert parse_accept_language("en-US") == "en"

    def test_quality_values(self):
        assert parse_accept_language("ja,en-US;q=0.9,en;q=0.8") == "ja"

    def test_en_preferred(self):
        assert parse_accept_language("en-US,en;q=0.9,ja;q=0.8") == "en"

    def test_unsupported_falls_back_to_en(self):
        assert parse_accept_language("fr,de;q=0.9") == "en"

    def test_empty_string(self):
        assert parse_accept_language("") == "en"

    def test_mixed_quality(self):
        assert parse_accept_language("fr;q=0.5,ja;q=0.9,en;q=0.8") == "ja"


class TestGetTranslator:
    def test_ja_translation(self):
        t = get_translator("ja")
        assert t("tenant_list") == "テナント一覧"
        assert t("no_public_tenants") == "公開テナントはありません"

    def test_en_translation(self):
        t = get_translator("en")
        assert t("tenant_list") == "Tenants"
        assert t("no_public_tenants") == "No public tenants"

    def test_unknown_lang_falls_back_to_en(self):
        t = get_translator("fr")
        assert t("tenant_list") == "Tenants"

    def test_unknown_key_returns_key(self):
        t = get_translator("en")
        assert t("nonexistent_key") == "nonexistent_key"

    def test_all_keys_present_in_both_locales(self):
        t_ja = get_translator("ja")
        t_en = get_translator("en")
        keys = [
            "tenant_list",
            "no_public_tenants",
            "title",
            "last_updated",
            "item_count",
            "no_frameworks",
            "document_details",
            "no_items",
            "show_in_tree",
            "go_to_top_page",
            "details",
            "error_bad_request",
            "error_not_found",
            "error_tenant_not_found",
            "error_document_not_found",
            "error_item_not_found",
            "error_server",
            "error_invalid_uuid",
        ]
        for key in keys:
            assert t_ja(key) != key, f"Missing ja translation for '{key}'"
            assert t_en(key) != key, f"Missing en translation for '{key}'"

    def test_placeholder_substitution(self):
        t = get_translator("en")
        assert t("error_invalid_uuid", value="bad") == "Invalid UUID format: 'bad'"

    def test_placeholder_substitution_ja(self):
        t = get_translator("ja")
        assert t("error_invalid_uuid", value="bad") == "不正なUUID形式: 'bad'"


class TestDetectLangFromEnv:
    def test_ja_jp_utf8(self, monkeypatch):
        monkeypatch.setenv("LANG", "ja_JP.UTF-8")
        assert detect_lang_from_env() == "ja"

    def test_en_us_utf8(self, monkeypatch):
        monkeypatch.setenv("LANG", "en_US.UTF-8")
        assert detect_lang_from_env() == "en"

    def test_unsupported_lang(self, monkeypatch):
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        assert detect_lang_from_env() == "en"

    def test_empty_env(self, monkeypatch):
        monkeypatch.delenv("LANG", raising=False)
        assert detect_lang_from_env() == "en"


class TestCliTranslator:
    def test_cli_en(self):
        t = get_translator("en", cli=True)
        assert t("cli_description") == "COMPEITO CLI."
        assert t("cmd_tenant_create") == "Create a new tenant."

    def test_cli_ja(self):
        t = get_translator("ja", cli=True)
        assert t("cli_description") == "COMPEITO CLI。"
        assert t("cmd_tenant_create") == "新しいテナントを作成する。"

    def test_cli_placeholder(self):
        t = get_translator("en", cli=True)
        assert t("err_invalid_uuid", value="bad") == "Invalid UUID format: 'bad'"

    def test_cli_all_keys_present_in_both_locales(self):
        t_en = get_translator("en", cli=True)
        t_ja = get_translator("ja", cli=True)
        keys = [
            "cli_description",
            "tenant_group",
            "doc_group",
            "import_group",
            "export_group",
            "db_group",
            "cmd_tenant_create",
            "cmd_tenant_list",
            "cmd_tenant_update",
            "cmd_tenant_delete",
            "cmd_doc_list",
            "cmd_doc_delete",
            "cmd_import_csv",
            "cmd_import_case",
            "cmd_export_csv",
            "cmd_db_migrate",
            "err_invalid_uuid",
            "err_tenant_not_found",
            "err_doc_not_found",
            "msg_created_tenant",
            "msg_deleted_tenant",
            "msg_no_tenants",
            "visibility_public",
            "visibility_private",
        ]
        for key in keys:
            assert t_en(key) != key, f"Missing cli_en translation for '{key}'"
            assert t_ja(key) != key, f"Missing cli_ja translation for '{key}'"
