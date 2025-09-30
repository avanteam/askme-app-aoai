"""
Factory pour créer les providers de logs d'usage selon HISTORY_PROVIDER.
Utilise la même configuration que les conversations pour la cohérence.
"""

import logging
from typing import Optional

from backend.settings import app_settings
from .base import UsageProvider
from .cosmosdb_service import CosmosUsageService
from .mongodb_service import MongoUsageService

logger = logging.getLogger(__name__)


class UsageProviderFactory:
    """
    Factory pour créer les providers de logs d'usage selon HISTORY_PROVIDER.

    Utilise le même provider que les conversations pour maintenir la cohérence.
    """

    @staticmethod
    async def create_usage_provider(cosmos_client=None) -> Optional[UsageProvider]:
        """
        Crée et initialise le provider de logs d'usage selon HISTORY_PROVIDER.

        Args:
            cosmos_client: Client CosmosDB (optionnel, pour compatibilité CosmosDB)

        Returns:
            Provider d'usage initialisé ou None si la configuration est invalide
        """
        provider = app_settings.base_settings.history_provider.upper()

        logger.info(f"Initializing usage provider: {provider} (same as history provider)")

        if provider == "MONGODB":
            return await UsageProviderFactory._create_mongodb_provider()
        elif provider == "COSMOSDB":
            return await UsageProviderFactory._create_cosmosdb_provider(cosmos_client)
        else:
            logger.error(f"Unknown history provider: {provider}")
            return None

    @staticmethod
    async def _create_mongodb_provider() -> Optional[MongoUsageService]:
        """Crée un provider MongoDB pour les logs d'usage"""
        try:
            if not app_settings.mongo_history:
                logger.error("MongoDB settings not configured for usage tracking")
                return None

            provider = MongoUsageService(
                connection_string=app_settings.mongo_history.uri,
                database_name=app_settings.mongo_history.database
            )

            # Test de connexion
            await provider.init_container()

            if not provider.enabled:
                logger.warning("MongoDB usage provider disabled or failed initialization")
                return provider  # Retourner quand même pour éviter les erreurs

            logger.info("MongoDB usage provider initialized successfully")
            return provider

        except Exception as e:
            logger.error(f"Failed to initialize MongoDB usage provider: {str(e)}")
            return None

    @staticmethod
    async def _create_cosmosdb_provider(cosmos_client=None) -> Optional[CosmosUsageService]:
        """Crée un provider CosmosDB pour les logs d'usage (logique existante)"""
        try:
            if not app_settings.chat_history:
                logger.error("CosmosDB settings not configured for usage tracking")
                return None

            provider = CosmosUsageService(cosmos_client)

            # Test de connexion
            await provider.init_container()

            if not provider.enabled:
                logger.warning("CosmosDB usage provider disabled or failed initialization")
                return provider  # Retourner quand même pour éviter les erreurs

            logger.info("CosmosDB usage provider initialized successfully")
            return provider

        except Exception as e:
            logger.error(f"Failed to initialize CosmosDB usage provider: {str(e)}")
            return None

    @staticmethod
    def get_provider_name() -> str:
        """Retourne le nom du provider configuré"""
        return app_settings.base_settings.history_provider.upper()

    @staticmethod
    def is_mongodb_enabled() -> bool:
        """Vérifie si MongoDB est configuré et activé pour les logs d'usage"""
        return (
            app_settings.base_settings.history_provider.upper() == "MONGODB" and
            app_settings.mongo_history is not None
        )

    @staticmethod
    def is_cosmosdb_enabled() -> bool:
        """Vérifie si CosmosDB est configuré et activé pour les logs d'usage"""
        return (
            app_settings.base_settings.history_provider.upper() == "COSMOSDB" and
            app_settings.chat_history is not None
        )


# Global instance - will be initialized by app.py
_usage_provider_instance: Optional[UsageProvider] = None


async def init_usage_service(cosmos_client=None) -> Optional[UsageProvider]:
    """
    Initialize the global usage tracking service.
    Remplace l'ancienne fonction du usage_service.py
    """
    global _usage_provider_instance
    _usage_provider_instance = await UsageProviderFactory.create_usage_provider(cosmos_client)
    return _usage_provider_instance


def get_usage_service() -> Optional[UsageProvider]:
    """
    Get the global usage tracking service instance.
    Remplace l'ancienne fonction du usage_service.py
    """
    return _usage_provider_instance