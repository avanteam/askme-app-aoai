"""
Tests de comptage de tokens pour AskMe
"""

import time
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Tuple

from ..utils.api_client import AskMeAPIClient
from ..utils.validators import TokenCountingValidator
from .config import TEST_CONFIG, TEST_DESCRIPTIONS, COLORS


class TokenCountingTests:
    """Classe principale pour les tests de comptage de tokens"""

    def __init__(self, config: Dict[str, Any] = None, verbose: bool = False):
        """
        Initialise les tests

        Args:
            config: Configuration personnalisée (utilise TEST_CONFIG par défaut)
            verbose: Mode verbose pour plus de détails
        """
        self.config = config or TEST_CONFIG
        self.verbose = verbose
        self.client = AskMeAPIClient(
            base_url=self.config['server']['base_url'],
            auth_token=self.config['server']['auth_token']
        )
        self.validator = TokenCountingValidator(self.config)
        self.results = []
        self.start_time = None

    def _print_colored(self, message: str, color: str = "white"):
        """Affiche un message coloré"""
        if color in COLORS:
            print(f"{COLORS[color]}{message}{COLORS['end']}")
        else:
            print(message)

    def _print_header(self, title: str):
        """Affiche un header formaté"""
        line = "=" * 60
        self._print_colored(line, "cyan")
        self._print_colored(f"   {title.upper()}", "bold")
        self._print_colored(line, "cyan")

    def _print_section(self, title: str):
        """Affiche un titre de section"""
        line = "-" * 50
        self._print_colored(line, "blue")
        self._print_colored(title, "bold")
        self._print_colored(line, "blue")

    def check_server_health(self) -> bool:
        """
        Vérifie que le serveur AskMe répond correctement

        Returns:
            bool: True si le serveur est opérationnel
        """
        self._print_section("VÉRIFICATION DU SERVEUR")

        health = self.client.verify_server_health()

        if health.get('healthy', False):
            self._print_colored(f"[OK] Serveur operationnel: {health['message']}", "green")
            return True
        else:
            self._print_colored(f"[ERREUR] Serveur indisponible: {health.get('message', 'Unknown error')}", "red")
            return False

    def test_simple_message_all_providers(self) -> List[Dict[str, Any]]:
        """
        Test de message simple pour tous les providers

        Returns:
            List[Dict]: Résultats des tests
        """
        self._print_section("TEST 1: MESSAGE SIMPLE - TOUS PROVIDERS")
        message = self.config['test_messages']['simple']

        results = []

        for provider in self.config['providers']:
            if self.verbose:
                self._print_colored(f"\nTest {provider} avec message: '{message}'", "yellow")

            # Enregistrer le timestamp avant le test
            test_start_time = datetime.now().isoformat()

            # Envoyer le message
            response = self.client.send_message(
                message=message,
                provider=provider,
                with_search=False
            )

            # Attendre que les logs apparaissent
            time.sleep(self.config['timeouts']['wait_for_logs'])

            # Récupérer les logs récents pour ce provider
            conversation_id = response.get('conversation_id')
            logs = self.client.find_recent_logs_by_provider(provider, test_start_time, limit=3)

            # Valider les résultats
            if logs:
                log_record = logs[0]  # Le plus récent
                is_valid, errors = self.validator.validate_simple_message(log_record, provider)

                result = {
                    'test_type': 'simple_message',
                    'provider': provider,
                    'message': message,
                    'conversation_id': conversation_id,
                    'success': is_valid,
                    'errors': errors,
                    'log_record': log_record,
                    'response': response
                }

                if is_valid:
                    self._print_colored(f"[OK] {provider}: Input={log_record.get('input_tokens', 0)} Output={log_record.get('output_tokens', 0)}", "green")
                else:
                    self._print_colored(f"[ECHEC] {provider}: {'; '.join(errors)}", "red")

            else:
                result = {
                    'test_type': 'simple_message',
                    'provider': provider,
                    'message': message,
                    'conversation_id': conversation_id,
                    'success': False,
                    'errors': ['Aucun log trouvé pour ce provider depuis le timestamp du test'],
                    'log_record': None,
                    'response': response
                }
                self._print_colored(f"[ECHEC] {provider}: Aucun log trouve", "red")

            results.append(result)

            # Délai entre providers
            time.sleep(self.config['timeouts']['between_providers'])

        return results

    def test_search_message_all_providers(self) -> List[Dict[str, Any]]:
        """
        Test de message avec recherche pour tous les providers

        Returns:
            List[Dict]: Résultats des tests
        """
        self._print_section("TEST 2: AVEC RECHERCHE DOCUMENTAIRE - TOUS PROVIDERS")
        message = self.config['test_messages']['with_search']

        results = []

        for provider in self.config['providers']:
            if self.verbose:
                self._print_colored(f"\nTest {provider} avec recherche: '{message}'", "yellow")

            # Enregistrer le timestamp avant le test
            test_start_time = datetime.now().isoformat()

            # Envoyer le message avec recherche
            response = self.client.send_message(
                message=message,
                provider=provider,
                with_search=True
            )

            # Attendre que les logs apparaissent
            time.sleep(self.config['timeouts']['wait_for_logs'])

            # Récupérer les logs récents pour ce provider
            conversation_id = response.get('conversation_id')
            logs = self.client.find_recent_logs_by_provider(provider, test_start_time, limit=3)

            # Valider les résultats
            if logs:
                log_record = logs[0]  # Le plus récent
                is_valid, errors = self.validator.validate_search_message(log_record, provider)

                result = {
                    'test_type': 'search_message',
                    'provider': provider,
                    'message': message,
                    'conversation_id': conversation_id,
                    'success': is_valid,
                    'errors': errors,
                    'log_record': log_record,
                    'response': response
                }

                if is_valid:
                    input_tokens = log_record.get('input_tokens', 0)
                    output_tokens = log_record.get('output_tokens', 0)
                    self._print_colored(f"[OK] {provider}: Input={input_tokens} Output={output_tokens}", "green")
                else:
                    self._print_colored(f"[ECHEC] {provider}: {'; '.join(errors)}", "red")
                    if self.verbose:
                        for error in errors:
                            self._print_colored(f"   -> {error}", "red")

            else:
                result = {
                    'test_type': 'search_message',
                    'provider': provider,
                    'message': message,
                    'conversation_id': conversation_id,
                    'success': False,
                    'errors': ['Aucun log trouvé pour ce provider depuis le timestamp du test'],
                    'log_record': None,
                    'response': response
                }
                self._print_colored(f"[ECHEC] {provider}: Aucun log trouve", "red")

            results.append(result)

            # Délai entre providers
            time.sleep(self.config['timeouts']['between_providers'])

        return results

    def run_all_tests(self) -> Dict[str, Any]:
        """
        Lance tous les tests de comptage de tokens

        Returns:
            Dict: Résultats complets des tests
        """
        self.start_time = datetime.now()

        self._print_header("TESTS DE COMPTAGE DE TOKENS ASKME")
        self._print_colored(f"Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}", "white")
        self._print_colored(f"Serveur: {self.config['server']['base_url']}", "white")
        print()

        # Vérifier le serveur
        if not self.check_server_health():
            return {
                'success': False,
                'error': 'Serveur indisponible',
                'tests_run': 0,
                'start_time': self.start_time.isoformat()
            }

        all_results = []

        # Test 1: Messages simples
        try:
            simple_results = self.test_simple_message_all_providers()
            all_results.extend(simple_results)
        except Exception as e:
            self._print_colored(f"❌ Erreur lors des tests simples: {e}", "red")

        # Test 2: Messages avec recherche
        try:
            search_results = self.test_search_message_all_providers()
            all_results.extend(search_results)
        except Exception as e:
            self._print_colored(f"❌ Erreur lors des tests avec recherche: {e}", "red")

        # Générer le résumé
        summary = self.validator.generate_summary(all_results)

        # Afficher le résumé
        self._print_section("RÉSUMÉ")
        self._print_colored(f"Tests réussis: {summary['passed_tests']}/{summary['total_tests']}", "green" if summary['passed_tests'] == summary['total_tests'] else "yellow")
        self._print_colored(f"Tests échoués: {summary['failed_tests']}", "red" if summary['failed_tests'] > 0 else "green")
        self._print_colored(f"Taux de succès: {summary['success_rate']}%", "green" if summary['success_rate'] == 100 else "yellow")

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        self._print_colored(f"Temps total: {duration:.1f}s", "white")

        if summary['overall_success']:
            self._print_colored("\n[SUCCES] Tous les tests ont reussi", "green")
        else:
            self._print_colored("\n[ECHEC] Certains tests ont echoue", "red")
            if summary.get('error_categories'):
                self._print_colored("Catégories d'erreurs:", "yellow")
                for category, count in summary['error_categories'].items():
                    self._print_colored(f"  - {category}: {count}", "red")

        # Résultats complets
        final_results = {
            'success': summary['overall_success'],
            'summary': summary,
            'all_results': all_results,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'config': self.config
        }

        self.results = final_results
        return final_results

    def save_results(self, filename: str = None) -> str:
        """
        Sauvegarde les résultats en JSON

        Args:
            filename: Nom du fichier (auto-généré si None)

        Returns:
            str: Nom du fichier sauvegardé
        """
        if not self.results:
            raise ValueError("Aucun résultat à sauvegarder. Lancez d'abord les tests.")

        if filename is None:
            timestamp = datetime.now().strftime(self.config['reporting']['timestamp_format'])
            filename = f"test_results_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)

        self._print_colored(f"Resultats sauvegardes: {filename}", "cyan")
        return filename