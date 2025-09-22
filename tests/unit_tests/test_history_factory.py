"""
Tests unitaires pour HistoryProviderFactory
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.history.history_factory import HistoryProviderFactory
from backend.history.cosmosdbservice import CosmosConversationClient
from backend.history.mongodbservice import MongoConversationClient


class TestHistoryProviderFactory:
    """Tests pour la classe HistoryProviderFactory"""

    @pytest.fixture
    def mock_app_settings(self):
        """Mock des paramètres d'application"""
        with patch('backend.history.history_factory.app_settings') as mock:
            # Configuration par défaut
            mock.base_settings.history_provider = "COSMOSDB"

            # Mock CosmosDB settings
            mock.chat_history = MagicMock()
            mock.chat_history.account = "test-account"
            mock.chat_history.account_key = "test-key"
            mock.chat_history.database = "test-db"
            mock.chat_history.conversations_container = "conversations"
            mock.chat_history.enable_feedback = False

            # Mock MongoDB settings
            mock.mongo_history = MagicMock()
            mock.mongo_history.uri = "mongodb://test:test@localhost:27017"
            mock.mongo_history.database = "test_mongo_db"
            mock.mongo_history.enable_feedback = True

            yield mock

    @pytest.mark.asyncio
    async def test_create_history_client_cosmosdb_success(self, mock_app_settings):
        """Test de création client CosmosDB - succès"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"

        with patch('backend.history.history_factory.CosmosConversationClient') as mock_cosmos:
            # Mock du client CosmosDB
            mock_client = AsyncMock()
            mock_client.ensure.return_value = (True, "Success")
            mock_cosmos.return_value = mock_client

            result = await HistoryProviderFactory.create_history_client()

            assert result is mock_client
            mock_cosmos.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_history_client_mongodb_success(self, mock_app_settings):
        """Test de création client MongoDB - succès"""
        mock_app_settings.base_settings.history_provider = "MONGODB"

        with patch('backend.history.history_factory.MongoConversationClient') as mock_mongo:
            # Mock du client MongoDB
            mock_client = AsyncMock()
            mock_client.ensure.return_value = (True, "Success")
            mock_mongo.return_value = mock_client

            result = await HistoryProviderFactory.create_history_client()

            assert result is mock_client
            mock_mongo.assert_called_once_with(
                connection_string=mock_app_settings.mongo_history.uri,
                database_name=mock_app_settings.mongo_history.database,
                enable_message_feedback=mock_app_settings.mongo_history.enable_feedback
            )

    @pytest.mark.asyncio
    async def test_create_history_client_unknown_provider(self, mock_app_settings):
        """Test avec provider inconnu"""
        mock_app_settings.base_settings.history_provider = "UNKNOWN"

        result = await HistoryProviderFactory.create_history_client()

        assert result is None

    @pytest.mark.asyncio
    async def test_create_history_client_cosmosdb_no_settings(self, mock_app_settings):
        """Test CosmosDB sans configuration"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"
        mock_app_settings.chat_history = None

        result = await HistoryProviderFactory.create_history_client()

        assert result is None

    @pytest.mark.asyncio
    async def test_create_history_client_mongodb_no_settings(self, mock_app_settings):
        """Test MongoDB sans configuration"""
        mock_app_settings.base_settings.history_provider = "MONGODB"
        mock_app_settings.mongo_history = None

        result = await HistoryProviderFactory.create_history_client()

        assert result is None

    @pytest.mark.asyncio
    async def test_create_history_client_cosmosdb_connection_failure(self, mock_app_settings):
        """Test échec de connexion CosmosDB"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"

        with patch('backend.history.history_factory.CosmosConversationClient') as mock_cosmos:
            # Mock du client qui échoue au test de connexion
            mock_client = AsyncMock()
            mock_client.ensure.return_value = (False, "Connection failed")
            mock_cosmos.return_value = mock_client

            result = await HistoryProviderFactory.create_history_client()

            assert result is None

    @pytest.mark.asyncio
    async def test_create_history_client_mongodb_connection_failure(self, mock_app_settings):
        """Test échec de connexion MongoDB"""
        mock_app_settings.base_settings.history_provider = "MONGODB"

        with patch('backend.history.history_factory.MongoConversationClient') as mock_mongo:
            # Mock du client qui échoue au test de connexion
            mock_client = AsyncMock()
            mock_client.ensure.return_value = (False, "Connection failed")
            mock_mongo.return_value = mock_client

            result = await HistoryProviderFactory.create_history_client()

            assert result is None

    @pytest.mark.asyncio
    async def test_create_history_client_cosmosdb_exception(self, mock_app_settings):
        """Test exception lors de la création du client CosmosDB"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"

        with patch('backend.history.history_factory.CosmosConversationClient') as mock_cosmos:
            # Mock qui lève une exception
            mock_cosmos.side_effect = Exception("Initialization failed")

            result = await HistoryProviderFactory.create_history_client()

            assert result is None

    @pytest.mark.asyncio
    async def test_create_history_client_mongodb_exception(self, mock_app_settings):
        """Test exception lors de la création du client MongoDB"""
        mock_app_settings.base_settings.history_provider = "MONGODB"

        with patch('backend.history.history_factory.MongoConversationClient') as mock_mongo:
            # Mock qui lève une exception
            mock_mongo.side_effect = Exception("Initialization failed")

            result = await HistoryProviderFactory.create_history_client()

            assert result is None

    def test_get_provider_name(self, mock_app_settings):
        """Test de récupération du nom du provider"""
        mock_app_settings.base_settings.history_provider = "mongodb"

        result = HistoryProviderFactory.get_provider_name()

        assert result == "MONGODB"

    def test_is_mongodb_enabled_true(self, mock_app_settings):
        """Test is_mongodb_enabled - activé"""
        mock_app_settings.base_settings.history_provider = "MONGODB"
        mock_app_settings.mongo_history = MagicMock()

        result = HistoryProviderFactory.is_mongodb_enabled()

        assert result is True

    def test_is_mongodb_enabled_false_wrong_provider(self, mock_app_settings):
        """Test is_mongodb_enabled - mauvais provider"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"
        mock_app_settings.mongo_history = MagicMock()

        result = HistoryProviderFactory.is_mongodb_enabled()

        assert result is False

    def test_is_mongodb_enabled_false_no_settings(self, mock_app_settings):
        """Test is_mongodb_enabled - pas de configuration"""
        mock_app_settings.base_settings.history_provider = "MONGODB"
        mock_app_settings.mongo_history = None

        result = HistoryProviderFactory.is_mongodb_enabled()

        assert result is False

    def test_is_cosmosdb_enabled_true(self, mock_app_settings):
        """Test is_cosmosdb_enabled - activé"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"
        mock_app_settings.chat_history = MagicMock()

        result = HistoryProviderFactory.is_cosmosdb_enabled()

        assert result is True

    def test_is_cosmosdb_enabled_false_wrong_provider(self, mock_app_settings):
        """Test is_cosmosdb_enabled - mauvais provider"""
        mock_app_settings.base_settings.history_provider = "MONGODB"
        mock_app_settings.chat_history = MagicMock()

        result = HistoryProviderFactory.is_cosmosdb_enabled()

        assert result is False

    def test_is_cosmosdb_enabled_false_no_settings(self, mock_app_settings):
        """Test is_cosmosdb_enabled - pas de configuration"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"
        mock_app_settings.chat_history = None

        result = HistoryProviderFactory.is_cosmosdb_enabled()

        assert result is False

    @pytest.mark.asyncio
    async def test_create_cosmosdb_client_with_env_key(self, mock_app_settings):
        """Test création client CosmosDB avec clé depuis variable d'environnement"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"
        mock_app_settings.chat_history.account_key = None  # Pas de clé dans les settings

        with patch('backend.history.history_factory.os.getenv') as mock_getenv:
            mock_getenv.return_value = "env-cosmos-key"

            with patch('backend.history.history_factory.CosmosConversationClient') as mock_cosmos:
                mock_client = AsyncMock()
                mock_client.ensure.return_value = (True, "Success")
                mock_cosmos.return_value = mock_client

                result = await HistoryProviderFactory.create_history_client()

                assert result is mock_client
                # Vérifier que la clé d'environnement a été utilisée
                call_args = mock_cosmos.call_args
                assert call_args[1]['credential'] == "env-cosmos-key"

    @pytest.mark.asyncio
    async def test_create_cosmosdb_client_no_key(self, mock_app_settings):
        """Test création client CosmosDB sans clé disponible"""
        mock_app_settings.base_settings.history_provider = "COSMOSDB"
        mock_app_settings.chat_history.account_key = None

        with patch('backend.history.history_factory.os.getenv') as mock_getenv:
            mock_getenv.return_value = None  # Pas de clé d'environnement

            result = await HistoryProviderFactory.create_history_client()

            assert result is None


@pytest.mark.integration
class TestHistoryProviderFactoryIntegration:
    """Tests d'intégration pour HistoryProviderFactory"""

    @pytest.mark.asyncio
    async def test_factory_with_real_settings_cosmosdb(self):
        """Test avec vraies settings CosmosDB (mock des clients)"""
        with patch('backend.history.history_factory.app_settings') as mock_settings:
            mock_settings.base_settings.history_provider = "COSMOSDB"
            mock_settings.chat_history = MagicMock()
            mock_settings.chat_history.account = "test-account"
            mock_settings.chat_history.account_key = "test-key"
            mock_settings.chat_history.database = "test-db"
            mock_settings.chat_history.conversations_container = "conversations"
            mock_settings.chat_history.enable_feedback = False

            with patch('backend.history.history_factory.CosmosConversationClient') as mock_cosmos:
                mock_client = AsyncMock()
                mock_client.ensure.return_value = (True, "CosmosDB ready")
                mock_cosmos.return_value = mock_client

                result = await HistoryProviderFactory.create_history_client()

                assert isinstance(result, type(mock_client))
                assert HistoryProviderFactory.get_provider_name() == "COSMOSDB"
                assert HistoryProviderFactory.is_cosmosdb_enabled() is True
                assert HistoryProviderFactory.is_mongodb_enabled() is False

    @pytest.mark.asyncio
    async def test_factory_with_real_settings_mongodb(self):
        """Test avec vraies settings MongoDB (mock des clients)"""
        with patch('backend.history.history_factory.app_settings') as mock_settings:
            mock_settings.base_settings.history_provider = "MONGODB"
            mock_settings.mongo_history = MagicMock()
            mock_settings.mongo_history.uri = "mongodb://test:test@localhost:27017"
            mock_settings.mongo_history.database = "test_db"
            mock_settings.mongo_history.enable_feedback = True
            mock_settings.chat_history = None  # CosmosDB désactivé

            with patch('backend.history.history_factory.MongoConversationClient') as mock_mongo:
                mock_client = AsyncMock()
                mock_client.ensure.return_value = (True, "MongoDB ready")
                mock_mongo.return_value = mock_client

                result = await HistoryProviderFactory.create_history_client()

                assert isinstance(result, type(mock_client))
                assert HistoryProviderFactory.get_provider_name() == "MONGODB"
                assert HistoryProviderFactory.is_mongodb_enabled() is True
                assert HistoryProviderFactory.is_cosmosdb_enabled() is False