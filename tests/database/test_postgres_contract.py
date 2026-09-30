import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEBUI = ROOT / 'apps/web-client/backend/open_webui'


class PostgreSQLContractTests(unittest.TestCase):
    def test_models_use_native_jsonb_wrapper(self) -> None:
        for model in (WEBUI / 'models').glob('*.py'):
            source = model.read_text()
            self.assertNotIn('Column(JSON)', source, model.name)
            self.assertNotIn('Column(JSON,', source, model.name)

    def test_live_query_paths_do_not_use_sqlite_json_functions(self) -> None:
        for relative in (
            'models/chat_messages.py',
            'models/chats.py',
            'models/users.py',
            'models/prompts.py',
            'models/models.py',
        ):
            source = (WEBUI / relative).read_text()
            self.assertNotIn('sqlite', source.lower(), relative)
            self.assertNotIn('json_extract', source, relative)

    def test_usage_aggregation_uses_jsonb_text_operators(self) -> None:
        source = (WEBUI / 'models/chat_messages.py').read_text()
        self.assertIn("ChatMessage.usage[key].astext", source)
        self.assertNotIn('func.json_extract', source)

    def test_migration_chain_adds_chat_jsonb_gin_index(self) -> None:
        migration = (WEBUI / 'migrations/versions/f2a4b6c8d0e1_add_chat_jsonb_gin_index.py').read_text()
        self.assertIn("down_revision: Union[str, None] = '461111b60977'", migration)
        self.assertIn('CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_content_gin ON chat USING GIN (chat)', migration)

    def test_bootstrap_uses_canonical_partitioned_spend_schema(self) -> None:
        bootstrap = (ROOT / 'scripts/db/init-postgres.sh').read_text()
        indexes = (ROOT / 'scripts/db/migrations/03_indexes.sql').read_text()
        self.assertIn('01_litellm_core.sql', bootstrap)
        self.assertIn('03_indexes.sql', bootstrap)
        self.assertIn('ensure_litellm_spend_log_partitions', indexes)
        self.assertIn('LiteLLMSpendLogs_legacy_flat', indexes)

    def test_developer_portal_uses_litellm_keys_and_domain_cookie(self) -> None:
        source = (WEBUI / 'routers/wolinet_docs.py').read_text()
        self.assertIn('/key/generate', source)
        self.assertTrue(
            'domain=os.getenv("WEBUI_AUTH_COOKIE_DOMAIN", ".wolinet.com")' in source
            or "domain=os.getenv('WEBUI_AUTH_COOKIE_DOMAIN', '.wolinet.com')" in source
        )
        self.assertNotIn('generated or create_api_key()', source)

    def test_composite_billing_and_audit_indexes(self) -> None:
        indexes = (ROOT / 'scripts/db/migrations/03_indexes.sql').read_text()
        self.assertIn('idx_spend_logs_user_apikey_time', indexes)
        self.assertIn('idx_token_user_created', indexes)
        self.assertIn('idx_token_user_spend', indexes)


if __name__ == '__main__':
    unittest.main()
