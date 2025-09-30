"""
Interface abstraite pour les providers de logs d'usage.
Permet de supporter CosmosDB et MongoDB avec une interface unifiée.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class UsageProvider(ABC):
    """
    Interface abstraite pour les providers de logs d'usage.

    Cette interface définit les méthodes communes que tous les providers
    d'usage doivent implémenter (CosmosDB, MongoDB, etc.).
    """

    @abstractmethod
    async def init_container(self) -> None:
        """
        Initialise le container/collection pour stocker les logs d'usage.
        """
        pass

    @abstractmethod
    async def record_usage(
        self,
        user_id: str,
        conversation_id: str,
        message_id: str,
        provider: str,
        input_tokens: Dict[str, Any],
        output_tokens: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Enregistre un événement d'usage.

        Args:
            user_id: Identifiant utilisateur
            conversation_id: Identifiant conversation
            message_id: Identifiant message
            provider: Nom du provider LLM
            input_tokens: Détail des tokens d'entrée
            output_tokens: Nombre de tokens de sortie
            metadata: Métadonnées supplémentaires

        Returns:
            True si enregistré avec succès, False sinon
        """
        pass

    @abstractmethod
    async def get_user_usage(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère les logs d'usage d'un utilisateur.

        Args:
            user_id: Identifiant utilisateur
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)
            provider: Filtre par provider (optionnel)

        Returns:
            Liste des logs d'usage
        """
        pass

    @abstractmethod
    async def get_usage_summary(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Génère un résumé d'usage pour un utilisateur.

        Args:
            user_id: Identifiant utilisateur
            days: Nombre de jours à inclure

        Returns:
            Résumé d'usage
        """
        pass

    @abstractmethod
    async def get_conversation_usage(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Récupère le résumé d'usage d'une conversation.

        Args:
            conversation_id: Identifiant conversation

        Returns:
            Résumé d'usage de la conversation
        """
        pass

    @abstractmethod
    async def get_system_usage_stats(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques d'usage système (fonction admin).

        Args:
            days: Nombre de jours à inclure

        Returns:
            Statistiques d'usage système
        """
        pass

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """
        Indique si le provider d'usage est activé.
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Retourne le nom du provider (ex: "CosmosDB", "MongoDB").
        """
        pass