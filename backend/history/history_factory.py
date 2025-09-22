"""
Factory pour créer les clients d'historique selon le provider configuré.
Supporte CosmosDB et MongoDB avec interface unifiée.
"""
import os
import logging
from typing import Union, Optional
from azure.identity.aio import DefaultAzureCredential

from backend.settings import app_settings
from backend.history.cosmosdbservice import CosmosConversationClient
from backend.history.mongodbservice import MongoConversationClient

logger = logging.getLogger(__name__)

# Type union pour les clients supportés
HistoryClient = Union[CosmosConversationClient, MongoConversationClient]

class HistoryProviderFactory:
    """
    Factory pour créer les clients d'historique selon la configuration.
    """

    @staticmethod
    async def create_history_client() -> Optional[HistoryClient]:
        """
        Crée et initialise le client d'historique selon HISTORY_PROVIDER.

        Returns:
            Client d'historique initialisé ou None si la configuration est invalide
        """
        provider = app_settings.base_settings.history_provider.upper()

        logger.info(f"Initializing history provider: {provider}")

        if provider == "MONGODB":
            return await HistoryProviderFactory._create_mongodb_client()
        elif provider == "COSMOSDB":
            return await HistoryProviderFactory._create_cosmosdb_client()
        else:
            logger.error(f"Unknown history provider: {provider}")
            return None

    @staticmethod
    async def _create_mongodb_client() -> Optional[MongoConversationClient]:
        """Crée un client MongoDB"""
        try:
            if not app_settings.mongo_history:
                logger.error("MongoDB settings not configured")
                return None

            client = MongoConversationClient(
                connection_string=app_settings.mongo_history.uri,
                database_name=app_settings.mongo_history.database,
                enable_message_feedback=app_settings.mongo_history.enable_feedback
            )

            # Test de connexion
            success, message = await client.ensure()
            if not success:
                logger.error(f"MongoDB connection test failed: {message}")
                return None

            logger.info("MongoDB client initialized successfully")
            return client

        except Exception as e:
            logger.error(f"Failed to initialize MongoDB client: {str(e)}")
            return None

    @staticmethod
    async def _create_cosmosdb_client() -> Optional[CosmosConversationClient]:
        """Crée un client CosmosDB (logic existante)"""
        try:
            if not app_settings.chat_history:
                logger.error("CosmosDB settings not configured")
                return None

            cosmos_endpoint = (
                f"https://{app_settings.chat_history.account}.documents.azure.com:443/"
            )

            if not app_settings.chat_history.account_key:
                # Utiliser la clé CosmosDB depuis le secret global
                cosmos_db_key = os.getenv('AZURE_COSMOSDB_ACCOUNT_KEY')
                if not cosmos_db_key:
                    logger.error("Neither AZURE_COSMOSDB_ACCOUNT_KEY nor account_key is set")
                    return None
                credential = cosmos_db_key
            else:
                credential = app_settings.chat_history.account_key

            client = CosmosConversationClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=credential,
                database_name=app_settings.chat_history.database,
                container_name=app_settings.chat_history.conversations_container,
                enable_message_feedback=app_settings.chat_history.enable_feedback
            )

            # Test de connexion
            success, message = await client.ensure()
            if not success:
                logger.error(f"CosmosDB connection test failed: {message}")
                return None

            logger.info("CosmosDB client initialized successfully")
            return client

        except Exception as e:
            logger.error(f"Failed to initialize CosmosDB client: {str(e)}")
            return None

    @staticmethod
    def get_provider_name() -> str:
        """Retourne le nom du provider configuré"""
        return app_settings.base_settings.history_provider.upper()

    @staticmethod
    def is_mongodb_enabled() -> bool:
        """Vérifie si MongoDB est configuré et activé"""
        return (
            app_settings.base_settings.history_provider.upper() == "MONGODB" and
            app_settings.mongo_history is not None
        )

    @staticmethod
    def is_cosmosdb_enabled() -> bool:
        """Vérifie si CosmosDB est configuré et activé"""
        return (
            app_settings.base_settings.history_provider.upper() == "COSMOSDB" and
            app_settings.chat_history is not None
        )