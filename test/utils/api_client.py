"""
Client API réutilisable pour tester AskMe
"""

import requests
import json
import time
import uuid
from typing import Dict, List, Optional, Any
from .auth import get_auth_headers


class AskMeAPIClient:
    """Client pour tester l'API AskMe avec authentification automatique"""

    def __init__(self, base_url: str = "http://localhost:50505", auth_token: str = "@v@nt€m-Q@litYs@AS-d€v31"):
        """
        Initialise le client API

        Args:
            base_url: URL de base de l'API AskMe
            auth_token: Token d'authentification depuis le .env
        """
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.session = requests.Session()

        # Configuration de la session
        self.session.headers.update(get_auth_headers(auth_token))

    def send_message(self, message: str, provider: str = "CLAUDE", with_search: bool = True,
                    stream: bool = False, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envoie un message à l'API de conversation

        Args:
            message: Message à envoyer
            provider: Provider LLM à utiliser
            with_search: Si True, utilise la recherche documentaire
            stream: Si True, utilise le streaming
            conversation_id: ID de conversation (généré automatiquement si None)

        Returns:
            dict: Réponse complète de l'API ou None si erreur
        """
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        payload = {
            "approach": "rrr" if with_search else "rr",
            "messages": [
                {
                    "role": "user",
                    "content": message
                }
            ],
            "provider": provider.lower(),
            "stream": stream,
            "history_metadata": {
                "conversation_id": conversation_id,
                "title": f"Test {provider}",
                "date": int(time.time() * 1000)
            }
        }

        try:
            response = self.session.post(
                f"{self.base_url}/conversation",
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            return {
                "success": True,
                "data": response.json(),
                "status_code": response.status_code,
                "conversation_id": conversation_id,
                "provider": provider,
                "message": message,
                "with_search": with_search
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                "conversation_id": conversation_id,
                "provider": provider,
                "message": message,
                "with_search": with_search
            }

    def get_usage_logs(self, limit: int = 50) -> Dict[str, Any]:
        """
        Récupère les logs d'usage depuis l'API

        Args:
            limit: Nombre maximum de logs à récupérer

        Returns:
            dict: Réponse avec les logs d'usage
        """
        try:
            # Cette route n'a pas besoin d'authentification selon le code
            response = self.session.get(
                f"{self.base_url}/api/usage/logs",
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            if data.get("success", False):
                # Limiter le nombre de résultats
                records = data.get("records", [])[:limit]
                return {
                    "success": True,
                    "records": records,
                    "total_records": data.get("total_records", len(records))
                }
            else:
                return {
                    "success": False,
                    "error": "API returned success=False",
                    "data": data
                }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            }

    def wait_for_logs(self, initial_count: int, timeout: int = 30) -> bool:
        """
        Attend que de nouveaux logs apparaissent

        Args:
            initial_count: Nombre initial de logs
            timeout: Timeout en secondes

        Returns:
            bool: True si nouveaux logs détectés, False si timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            logs = self.get_usage_logs()
            if logs.get("success", False):
                current_count = len(logs.get("records", []))
                if current_count > initial_count:
                    return True

            time.sleep(1)

        return False

    def find_logs_by_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Trouve les logs pour un ID de conversation spécifique

        Args:
            conversation_id: ID de conversation à chercher

        Returns:
            list: Liste des logs trouvés
        """
        logs = self.get_usage_logs(100)  # Récupérer plus de logs pour la recherche

        if not logs.get("success", False):
            return []

        matching_logs = []
        for record in logs.get("records", []):
            if record.get("conversation_id") == conversation_id:
                matching_logs.append(record)

        return matching_logs

    def find_recent_logs_by_provider(self, provider: str, since_timestamp: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Trouve les logs récents pour un provider spécifique depuis un timestamp donné

        Args:
            provider: Provider à chercher (CLAUDE, AZURE_OPENAI, etc.)
            since_timestamp: Timestamp ISO format depuis lequel chercher
            limit: Nombre maximum de logs à retourner

        Returns:
            list: Liste des logs trouvés (triés par timestamp décroissant)
        """
        logs = self.get_usage_logs(200)  # Récupérer beaucoup de logs pour la recherche

        if not logs.get("success", False):
            return []

        from datetime import datetime
        import dateutil.parser

        try:
            since_dt = dateutil.parser.isoparse(since_timestamp)
        except:
            # Fallback: utiliser les plus récents si parsing échoue
            since_dt = datetime.min

        matching_logs = []
        for record in logs.get("records", []):
            if record.get("provider") == provider:
                try:
                    record_dt = dateutil.parser.isoparse(record.get("timestamp", ""))
                    if record_dt > since_dt:
                        matching_logs.append(record)
                except:
                    # Si pas de timestamp valide, inclure quand même
                    matching_logs.append(record)

        # Trier par timestamp décroissant et limiter
        matching_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return matching_logs[:limit]

    def verify_server_health(self) -> Dict[str, Any]:
        """
        Vérifie que le serveur AskMe répond correctement

        Returns:
            dict: Status de santé du serveur
        """
        try:
            # Test de l'endpoint des logs d'usage
            response = self.session.get(f"{self.base_url}/api/usage/logs", timeout=5)

            if response.status_code == 200:
                return {
                    "healthy": True,
                    "status_code": response.status_code,
                    "message": "Server responding correctly"
                }
            else:
                return {
                    "healthy": False,
                    "status_code": response.status_code,
                    "message": f"Server returned status {response.status_code}"
                }

        except requests.exceptions.RequestException as e:
            return {
                "healthy": False,
                "error": str(e),
                "message": "Server not responding"
            }