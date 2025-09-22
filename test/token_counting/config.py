"""
Configuration pour les tests de comptage de tokens
"""

# Configuration principale des tests
TEST_CONFIG = {
    # Providers LLM à tester
    "providers": [
        "AZURE_OPENAI",
        "CLAUDE",
        "MISTRAL",
        "GEMINI",
        "OPENAI_DIRECT"
    ],

    # Messages de test standardisés
    "test_messages": {
        # Message simple sans recherche documentaire
        "simple": "Bonjour",

        # Message avec recherche documentaire
        "with_search": "fiche de poste directeur r&d",

        # Message complexe avec recherche
        "complex": "Explique-moi la procédure de recrutement complète avec toutes les étapes"
    },

    # Critères de validation
    "validation": {
        # Minimum de tokens d'input pour considérer que le system message est compté
        "min_system_tokens": 100,

        # Minimum de caractères dans le search context pour les recherches
        "min_search_context_chars": 1000,

        # Tolérance en pourcentage pour la validation des output tokens
        "output_tolerance_percent": 20,

        # Tokens minimum d'output pour considérer une réponse valide
        "min_output_tokens": 10,

        # Tokens maximum d'input pour détecter des problèmes
        "max_input_tokens": 10000
    },

    # Timeouts et délais
    "timeouts": {
        # Timeout pour les requêtes individuelles (secondes)
        "request": 45,

        # Délai entre les tests pour éviter la surcharge
        "between_tests": 3,

        # Temps d'attente pour que les logs apparaissent
        "wait_for_logs": 15,

        # Délai entre providers pour éviter les limits rates
        "between_providers": 2
    },

    # Configuration du serveur
    "server": {
        # URL de base du serveur AskMe
        "base_url": "http://localhost:50505",

        # Token d'authentification (depuis .env)
        "auth_token": "@v@nt€m-Q@litYs@AS-d€v31",

        # Endpoint pour les logs d'usage
        "usage_logs_endpoint": "/api/usage/logs",

        # Endpoint de conversation
        "conversation_endpoint": "/conversation"
    },

    # Configuration des rapports
    "reporting": {
        # Afficher les détails des tokens dans le rapport
        "show_token_details": True,

        # Afficher les erreurs complètes
        "show_full_errors": True,

        # Sauvegarder les résultats en JSON
        "save_json_results": True,

        # Dossier pour les résultats de test
        "results_dir": "./test_results",

        # Format de timestamp pour les fichiers
        "timestamp_format": "%Y%m%d_%H%M%S"
    }
}

# Messages d'explication pour les utilisateurs
TEST_DESCRIPTIONS = {
    "simple": {
        "description": "Test de message simple sans recherche documentaire",
        "expected": "Input tokens faibles (system message uniquement), output tokens variables selon provider"
    },

    "with_search": {
        "description": "Test de message avec recherche documentaire active",
        "expected": "Input tokens élevés (system message + documents trouvés), output tokens plus importants"
    },

    "complex": {
        "description": "Test de message complexe avec recherche approfondie",
        "expected": "Input tokens très élevés, réponse structurée et détaillée"
    }
}

# Couleurs pour l'affichage console
COLORS = {
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "purple": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    "bold": "\033[1m",
    "end": "\033[0m"
}