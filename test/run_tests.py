#!/usr/bin/env python3
"""
Script principal pour lancer les tests de comptage de tokens AskMe

Usage:
    python run_tests.py [options]

Options:
    --verbose, -v           Mode verbose avec détails supplémentaires
    --provider PROVIDER     Tester un seul provider spécifique
    --output FILE           Sauvegarder les résultats dans un fichier JSON
    --help, -h             Afficher cette aide

Exemples:
    python run_tests.py                        # Lancer tous les tests
    python run_tests.py --verbose              # Mode verbose
    python run_tests.py --provider CLAUDE      # Tester seulement Claude
    python run_tests.py --output results.json  # Sauvegarder les résultats
"""

import sys
import os
import argparse
from typing import Optional

# Ajouter le répertoire parent au PATH pour importer les modules de test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test.token_counting.test_token_counting import TokenCountingTests
from test.token_counting.config import TEST_CONFIG, COLORS


def print_colored(message: str, color: str = "white"):
    """Affiche un message coloré"""
    if color in COLORS:
        print(f"{COLORS[color]}{message}{COLORS['end']}")
    else:
        print(message)


def print_usage():
    """Affiche les instructions d'utilisation"""
    print(__doc__)


def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(
        description="Tests de comptage de tokens pour AskMe",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mode verbose avec détails supplémentaires"
    )

    parser.add_argument(
        "--provider",
        type=str,
        choices=TEST_CONFIG['providers'],
        help="Tester un seul provider spécifique"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Sauvegarder les résultats dans un fichier JSON"
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Fichier de configuration personnalisé (JSON)"
    )

    args = parser.parse_args()

    # Charger la configuration
    config = TEST_CONFIG
    if args.config:
        try:
            import json
            with open(args.config, 'r', encoding='utf-8') as f:
                custom_config = json.load(f)
            # Fusionner avec la configuration par défaut
            config.update(custom_config)
            print_colored(f"[OK] Configuration personnalisee chargee: {args.config}", "green")
        except Exception as e:
            print_colored(f"[ERREUR] Erreur lors du chargement de la configuration: {e}", "red")
            return 1

    # Modifier la configuration si un provider spécifique est demandé
    if args.provider:
        config['providers'] = [args.provider.upper()]
        print_colored(f"Test limite au provider: {args.provider}", "yellow")

    # Initialiser les tests
    try:
        tester = TokenCountingTests(config=config, verbose=args.verbose)
    except Exception as e:
        print_colored(f"[ERREUR] Erreur d'initialisation des tests: {e}", "red")
        return 1

    # Lancer les tests
    try:
        results = tester.run_all_tests()
    except KeyboardInterrupt:
        print_colored("\n[ATTENTION] Tests interrompus par l'utilisateur", "yellow")
        return 1
    except Exception as e:
        print_colored(f"[ERREUR] Erreur lors de l'execution des tests: {e}", "red")
        return 1

    # Sauvegarder les résultats si demandé
    if args.output:
        try:
            tester.save_results(args.output)
        except Exception as e:
            print_colored(f"[ERREUR] Erreur lors de la sauvegarde: {e}", "red")
            return 1

    # Code de sortie basé sur le succès des tests
    return 0 if results.get('success', False) else 1


if __name__ == "__main__":
    sys.exit(main())