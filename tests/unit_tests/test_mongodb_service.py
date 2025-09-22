"""
Tests unitaires pour MongoConversationClient
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from backend.history.mongodbservice import MongoConversationClient


class TestMongoConversationClient:
    """Tests pour la classe MongoConversationClient"""

    @pytest.fixture
    def mock_motor_client(self):
        """Mock du client Motor MongoDB"""
        with patch('backend.history.mongodbservice.AsyncIOMotorClient') as mock:
            client = AsyncMock()
            mock.return_value = client

            # Mock de la database et collections
            database = AsyncMock()
            client.__getitem__.return_value = database

            conversations_collection = AsyncMock()
            messages_collection = AsyncMock()

            database.conversations = conversations_collection
            database.messages = messages_collection
            database.health_check = AsyncMock()

            # Mock des méthodes admin
            client.admin.command = AsyncMock()
            client.list_database_names = AsyncMock()

            yield {
                'client': client,
                'database': database,
                'conversations': conversations_collection,
                'messages': messages_collection
            }

    @pytest.fixture
    def mongo_client(self, mock_motor_client):
        """Instance de MongoConversationClient avec mocks"""
        return MongoConversationClient(
            connection_string="mongodb://test:test@localhost:27017/?replicaSet=rs0",
            database_name="test_database",
            enable_message_feedback=True
        )

    @pytest.mark.asyncio
    async def test_init_success(self, mock_motor_client):
        """Test d'initialisation réussie"""
        client = MongoConversationClient(
            connection_string="mongodb://test:test@localhost:27017/?replicaSet=rs0",
            database_name="test_database"
        )

        assert client.connection_string is not None
        assert client.database_name == "test_database"
        assert client.enable_message_feedback is False

    @pytest.mark.asyncio
    async def test_ensure_success(self, mongo_client, mock_motor_client):
        """Test de la méthode ensure - succès"""
        # Mock des réponses
        mock_motor_client['client'].admin.command.return_value = {'ismaster': True}
        mock_motor_client['client'].list_database_names.return_value = ['test_database']

        # Mock des opérations de santé
        mock_motor_client['database'].health_check.replace_one = AsyncMock()
        mock_motor_client['database'].health_check.delete_one = AsyncMock()

        success, message = await mongo_client.ensure()

        assert success is True
        assert "successfully" in message

    @pytest.mark.asyncio
    async def test_ensure_connection_failure(self, mongo_client, mock_motor_client):
        """Test de la méthode ensure - échec de connexion"""
        # Mock d'une erreur de connexion
        from pymongo.errors import ConnectionFailure
        mock_motor_client['client'].admin.command.side_effect = ConnectionFailure("Connection failed")

        success, message = await mongo_client.ensure()

        assert success is False
        assert "connection failed" in message.lower()

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, mongo_client, mock_motor_client):
        """Test de création de conversation - succès"""
        # Mock de la réponse d'insertion
        mock_result = MagicMock()
        mock_result.inserted_id = "test-conversation-id"
        mock_motor_client['conversations'].insert_one.return_value = mock_result

        result = await mongo_client.create_conversation("user123", "Test Conversation")

        assert result is not False
        assert result['userId'] == "user123"
        assert result['title'] == "Test Conversation"
        assert result['type'] == "conversation"
        assert 'createdAt' in result
        assert 'updatedAt' in result

    @pytest.mark.asyncio
    async def test_create_conversation_failure(self, mongo_client, mock_motor_client):
        """Test de création de conversation - échec"""
        # Mock d'un échec d'insertion
        mock_result = MagicMock()
        mock_result.inserted_id = None
        mock_motor_client['conversations'].insert_one.return_value = mock_result

        result = await mongo_client.create_conversation("user123", "Test Conversation")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_conversations_success(self, mongo_client, mock_motor_client):
        """Test de récupération des conversations - succès"""
        # Mock des données de conversation
        mock_conversations = [
            {
                '_id': 'conv1',
                'userId': 'user123',
                'title': 'Conversation 1',
                'type': 'conversation',
                'createdAt': '2024-01-01T10:00:00',
                'updatedAt': '2024-01-01T10:00:00'
            },
            {
                '_id': 'conv2',
                'userId': 'user123',
                'title': 'Conversation 2',
                'type': 'conversation',
                'createdAt': '2024-01-01T11:00:00',
                'updatedAt': '2024-01-01T11:00:00'
            }
        ]

        # Mock du cursor
        mock_cursor = AsyncMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list.return_value = mock_conversations

        mock_motor_client['conversations'].find.return_value = mock_cursor

        result = await mongo_client.get_conversations("user123", limit=10)

        assert len(result) == 2
        assert all('id' in conv for conv in result)  # Vérifier compatibilité 'id'
        assert result[0]['userId'] == 'user123'

    @pytest.mark.asyncio
    async def test_get_conversation_found(self, mongo_client, mock_motor_client):
        """Test de récupération d'une conversation - trouvée"""
        mock_conversation = {
            '_id': 'conv1',
            'userId': 'user123',
            'title': 'Test Conversation',
            'type': 'conversation',
            'createdAt': '2024-01-01T10:00:00',
            'updatedAt': '2024-01-01T10:00:00'
        }

        mock_motor_client['conversations'].find_one.return_value = mock_conversation

        result = await mongo_client.get_conversation("user123", "conv1")

        assert result is not None
        assert result['_id'] == 'conv1'
        assert result['id'] == 'conv1'  # Vérifier compatibilité 'id'
        assert result['userId'] == 'user123'

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, mongo_client, mock_motor_client):
        """Test de récupération d'une conversation - non trouvée"""
        mock_motor_client['conversations'].find_one.return_value = None

        result = await mongo_client.get_conversation("user123", "nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_message_success(self, mongo_client, mock_motor_client):
        """Test de création de message - succès"""
        # Mock de l'insertion du message
        mock_result = MagicMock()
        mock_result.inserted_id = "message-id"
        mock_motor_client['messages'].insert_one.return_value = mock_result

        # Mock de la mise à jour de la conversation
        mock_motor_client['conversations'].update_one = AsyncMock()

        input_message = {
            'role': 'user',
            'content': 'Hello, world!'
        }

        result = await mongo_client.create_message(
            "message-id", "conv1", "user123", input_message
        )

        assert result is not False
        assert result['role'] == 'user'
        assert result['content'] == 'Hello, world!'
        assert result['conversationId'] == 'conv1'
        assert result['userId'] == 'user123'
        assert 'feedback' in result  # Car enable_message_feedback=True

    @pytest.mark.asyncio
    async def test_create_message_with_image_content(self, mongo_client, mock_motor_client):
        """Test de création de message avec contenu image"""
        # Mock de l'insertion du message
        mock_result = MagicMock()
        mock_result.inserted_id = "message-id"
        mock_motor_client['messages'].insert_one.return_value = mock_result
        mock_motor_client['conversations'].update_one = AsyncMock()

        # Contenu avec image (format multimodal)
        input_message = {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': 'Voici une image'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='}}
            ]
        }

        result = await mongo_client.create_message(
            "message-id", "conv1", "user123", input_message
        )

        assert result is not False
        # Le contenu devrait être traité par process_message_content_for_storage
        assert isinstance(result['content'], list)

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, mongo_client, mock_motor_client):
        """Test de suppression de conversation - succès"""
        # Mock: conversation existe
        mock_motor_client['conversations'].find_one.return_value = {'_id': 'conv1', 'userId': 'user123'}

        # Mock: suppression des messages
        mock_delete_result = MagicMock()
        mock_delete_result.deleted_count = 3
        mock_motor_client['messages'].delete_many.return_value = mock_delete_result

        # Mock: suppression de la conversation
        mock_conv_delete_result = MagicMock()
        mock_conv_delete_result.deleted_count = 1
        mock_motor_client['conversations'].delete_one.return_value = mock_conv_delete_result

        result = await mongo_client.delete_conversation("user123", "conv1")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, mongo_client, mock_motor_client):
        """Test de suppression de conversation - non trouvée"""
        # Mock: conversation n'existe pas
        mock_motor_client['conversations'].find_one.return_value = None

        result = await mongo_client.delete_conversation("user123", "nonexistent")

        assert result is True  # Idempotence

    @pytest.mark.asyncio
    async def test_get_messages_success(self, mongo_client, mock_motor_client):
        """Test de récupération des messages - succès"""
        mock_messages = [
            {
                '_id': 'msg1',
                'userId': 'user123',
                'conversationId': 'conv1',
                'role': 'user',
                'content': 'Hello',
                'type': 'message',
                'timestamp': datetime.utcnow()
            },
            {
                '_id': 'msg2',
                'userId': 'user123',
                'conversationId': 'conv1',
                'role': 'assistant',
                'content': 'Hi there!',
                'type': 'message',
                'timestamp': datetime.utcnow()
            }
        ]

        # Mock du cursor
        mock_cursor = AsyncMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.to_list.return_value = mock_messages

        mock_motor_client['messages'].find.return_value = mock_cursor

        result = await mongo_client.get_messages("user123", "conv1")

        assert len(result) == 2
        assert all('id' in msg for msg in result)  # Vérifier compatibilité 'id'
        assert result[0]['role'] == 'user'
        assert result[1]['role'] == 'assistant'

    @pytest.mark.asyncio
    async def test_update_message_feedback_success(self, mongo_client, mock_motor_client):
        """Test de mise à jour du feedback - succès"""
        # Mock de la mise à jour
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_motor_client['messages'].update_one.return_value = mock_result

        # Mock du message mis à jour
        updated_message = {
            '_id': 'msg1',
            'userId': 'user123',
            'feedback': 'positive',
            'updatedAt': datetime.utcnow().isoformat()
        }
        mock_motor_client['messages'].find_one.return_value = updated_message

        result = await mongo_client.update_message_feedback("user123", "msg1", "positive")

        assert result is not False
        assert result['feedback'] == 'positive'
        assert 'id' in result  # Vérifier compatibilité 'id'

    @pytest.mark.asyncio
    async def test_update_message_feedback_not_found(self, mongo_client, mock_motor_client):
        """Test de mise à jour du feedback - message non trouvé"""
        # Mock: pas de modification
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_motor_client['messages'].update_one.return_value = mock_result

        result = await mongo_client.update_message_feedback("user123", "nonexistent", "positive")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_messages_success(self, mongo_client, mock_motor_client):
        """Test de suppression de messages - succès"""
        # Mock de la suppression
        mock_result = MagicMock()
        mock_result.deleted_count = 5
        mock_motor_client['messages'].delete_many.return_value = mock_result

        result = await mongo_client.delete_messages("conv1", "user123")

        assert len(result) > 0
        assert "5 messages" in result[0]

    @pytest.mark.asyncio
    async def test_close(self, mongo_client, mock_motor_client):
        """Test de fermeture du client"""
        await mongo_client.close()

        mock_motor_client['client'].close.assert_called_once()


@pytest.mark.integration
class TestMongoConversationClientIntegration:
    """Tests d'intégration nécessitant une vraie instance MongoDB"""

    @pytest.fixture(scope="class")
    def mongo_uri(self):
        """URI MongoDB pour les tests d'intégration"""
        return "mongodb://localhost:27017/?replicaSet=rs0"

    @pytest.fixture(scope="class")
    def test_database(self):
        """Nom de la database de test"""
        return "askme_test"

    @pytest.fixture
    async def mongo_client(self, mongo_uri, test_database):
        """Client MongoDB réel pour les tests d'intégration"""
        client = MongoConversationClient(
            connection_string=mongo_uri,
            database_name=test_database,
            enable_message_feedback=True
        )

        # Nettoyage avant le test
        await client.conversations_collection.delete_many({})
        await client.messages_collection.delete_many({})

        yield client

        # Nettoyage après le test
        await client.conversations_collection.delete_many({})
        await client.messages_collection.delete_many({})
        await client.close()

    @pytest.mark.asyncio
    async def test_full_conversation_workflow(self, mongo_client):
        """Test du workflow complet d'une conversation"""
        # 1. Créer une conversation
        conversation = await mongo_client.create_conversation("user123", "Test Integration")
        assert conversation is not False
        conv_id = conversation['id']

        # 2. Créer des messages
        user_message = {
            'role': 'user',
            'content': 'Hello, this is a test message'
        }

        msg1 = await mongo_client.create_message("msg1", conv_id, "user123", user_message)
        assert msg1 is not False

        assistant_message = {
            'role': 'assistant',
            'content': 'Hello! How can I help you today?'
        }

        msg2 = await mongo_client.create_message("msg2", conv_id, "user123", assistant_message)
        assert msg2 is not False

        # 3. Récupérer les messages
        messages = await mongo_client.get_messages("user123", conv_id)
        assert len(messages) == 2
        assert messages[0]['role'] == 'user'
        assert messages[1]['role'] == 'assistant'

        # 4. Récupérer les conversations
        conversations = await mongo_client.get_conversations("user123", limit=10)
        assert len(conversations) == 1
        assert conversations[0]['title'] == "Test Integration"

        # 5. Ajouter du feedback
        feedback_result = await mongo_client.update_message_feedback("user123", "msg2", "positive")
        assert feedback_result is not False
        assert feedback_result['feedback'] == 'positive'

        # 6. Supprimer la conversation
        delete_result = await mongo_client.delete_conversation("user123", conv_id)
        assert delete_result is True

        # 7. Vérifier que tout est supprimé
        conversations_after = await mongo_client.get_conversations("user123", limit=10)
        assert len(conversations_after) == 0

        messages_after = await mongo_client.get_messages("user123", conv_id)
        assert len(messages_after) == 0