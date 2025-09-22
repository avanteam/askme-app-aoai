"""
Validateurs pour les tests de comptage de tokens
"""

from typing import Dict, List, Any, Optional, Tuple


class TokenCountingValidator:
    """Validateur pour les résultats de comptage de tokens"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le validateur avec la configuration

        Args:
            config: Configuration de validation
        """
        self.config = config

    def validate_simple_message(self, log_record: Dict[str, Any], provider: str) -> Tuple[bool, List[str]]:
        """
        Valide le comptage de tokens pour un message simple (sans recherche)

        Args:
            log_record: Enregistrement de log à valider
            provider: Provider utilisé

        Returns:
            Tuple[bool, List[str]]: (is_valid, errors)
        """
        errors = []
        is_valid = True

        # Vérifier les champs obligatoires
        required_fields = ['input_tokens', 'output_tokens', 'total_tokens', 'provider']
        for field in required_fields:
            if field not in log_record:
                errors.append(f"Champ manquant: {field}")
                is_valid = False

        if not is_valid:
            return is_valid, errors

        input_tokens = log_record['input_tokens']
        output_tokens = log_record['output_tokens']
        total_tokens = log_record['total_tokens']

        # Vérifier le provider
        if log_record['provider'] != provider:
            errors.append(f"Provider incorrect: attendu {provider}, obtenu {log_record['provider']}")
            is_valid = False

        # Vérifier les tokens d'input (doit inclure le system message)
        min_system_tokens = self.config.get('validation', {}).get('min_system_tokens', 50)
        if input_tokens < min_system_tokens:
            errors.append(f"Input tokens trop faible ({input_tokens}), system message probablement non compté (minimum: {min_system_tokens})")
            is_valid = False

        # Vérifier les tokens d'output (ne doit pas être hardcodé à 100)
        if output_tokens == 100:
            errors.append(f"Output tokens semble hardcodé à 100, pas de vrai comptage")
            is_valid = False

        if output_tokens < 10:
            errors.append(f"Output tokens trop faible ({output_tokens}), problème de comptage probable")
            is_valid = False

        # Vérifier la cohérence du total
        if total_tokens != input_tokens + output_tokens:
            errors.append(f"Total incohérent: {total_tokens} != {input_tokens} + {output_tokens}")
            is_valid = False

        return is_valid, errors

    def validate_search_message(self, log_record: Dict[str, Any], provider: str) -> Tuple[bool, List[str]]:
        """
        Valide le comptage de tokens pour un message avec recherche documentaire

        Args:
            log_record: Enregistrement de log à valider
            provider: Provider utilisé

        Returns:
            Tuple[bool, List[str]]: (is_valid, errors)
        """
        errors = []
        is_valid = True

        # D'abord valider comme un message simple
        simple_valid, simple_errors = self.validate_simple_message(log_record, provider)
        if not simple_valid:
            errors.extend(simple_errors)
            is_valid = False

        if not is_valid:
            return is_valid, errors

        input_tokens = log_record['input_tokens']

        # Pour les messages avec recherche, les input tokens doivent être significativement plus élevés
        min_search_tokens = self.config.get('validation', {}).get('min_system_tokens', 50) + 500
        if input_tokens < min_search_tokens:
            errors.append(f"Input tokens trop faible pour une recherche ({input_tokens}), search context probablement non compté (minimum: {min_search_tokens})")
            is_valid = False

        # Vérifier la présence de métadonnées sur le search context si disponibles
        if isinstance(input_tokens, dict):
            search_context_tokens = input_tokens.get('search_context', 0)
            if search_context_tokens == 0:
                errors.append("Search context tokens = 0, les documents ne sont pas comptés")
                is_valid = False

        return is_valid, errors

    def validate_provider_consistency(self, logs: List[Dict[str, Any]], provider: str) -> Tuple[bool, List[str]]:
        """
        Valide la cohérence des résultats pour un provider

        Args:
            logs: Liste des logs pour ce provider
            provider: Provider à valider

        Returns:
            Tuple[bool, List[str]]: (is_valid, errors)
        """
        errors = []
        is_valid = True

        if len(logs) == 0:
            errors.append(f"Aucun log trouvé pour le provider {provider}")
            return False, errors

        # Vérifier que tous les logs ont le même provider
        for log in logs:
            if log.get('provider') != provider:
                errors.append(f"Log avec provider incorrect: attendu {provider}, obtenu {log.get('provider')}")
                is_valid = False

        # Vérifier les variations de tokens (ne doivent pas être tous identiques)
        input_tokens = [log.get('input_tokens', 0) for log in logs]
        output_tokens = [log.get('output_tokens', 0) for log in logs]

        if len(set(input_tokens)) == 1 and len(logs) > 1:
            errors.append(f"Tous les input_tokens sont identiques ({input_tokens[0]}), possible problème de comptage")
            is_valid = False

        if len(set(output_tokens)) == 1 and len(logs) > 1:
            if output_tokens[0] == 100:
                errors.append("Tous les output_tokens sont à 100, comptage hardcodé détecté")
                is_valid = False

        return is_valid, errors

    def generate_summary(self, all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Génère un résumé des résultats de validation

        Args:
            all_results: Liste de tous les résultats de test

        Returns:
            dict: Résumé des tests
        """
        total_tests = len(all_results)
        passed_tests = sum(1 for result in all_results if result.get('success', False))
        failed_tests = total_tests - passed_tests

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        summary = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': round(success_rate, 1),
            'overall_success': failed_tests == 0
        }

        # Analyser les erreurs par catégorie
        error_categories = {}
        for result in all_results:
            if not result.get('success', False):
                for error in result.get('errors', []):
                    if 'system message' in error.lower():
                        error_categories['system_message'] = error_categories.get('system_message', 0) + 1
                    elif 'search context' in error.lower():
                        error_categories['search_context'] = error_categories.get('search_context', 0) + 1
                    elif 'hardcodé' in error.lower():
                        error_categories['hardcoded_output'] = error_categories.get('hardcoded_output', 0) + 1
                    else:
                        error_categories['other'] = error_categories.get('other', 0) + 1

        summary['error_categories'] = error_categories

        return summary