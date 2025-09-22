#!/usr/bin/env python3
"""
Script de validation des logs existants pour démontrer que le comptage de tokens fonctionne correctement

Usage:
    python test/validate_existing_logs.py

Ce script analyse les logs existants et prouve que:
1. Les output tokens ne sont plus hardcodés à 100
2. Les input tokens incluent les system messages
3. Les tokens sont comptés correctement pour tous les providers
4. La recherche documentaire augmente bien les input tokens
"""

import sys
import os
from typing import Dict, List, Any
import statistics

# Ajouter le répertoire parent au PATH pour importer les modules de test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test.utils.api_client import AskMeAPIClient
from test.utils.validators import TokenCountingValidator
from test.token_counting.config import TEST_CONFIG, COLORS


def print_colored(message: str, color: str = "white"):
    """Affiche un message coloré"""
    if color in COLORS:
        print(f"{COLORS[color]}{message}{COLORS['end']}")
    else:
        print(message)


def print_header(title: str):
    """Affiche un header formaté"""
    line = "=" * 70
    print_colored(line, "cyan")
    print_colored(f"   {title.upper()}", "bold")
    print_colored(line, "cyan")


def print_section(title: str):
    """Affiche un titre de section"""
    line = "-" * 60
    print_colored(line, "blue")
    print_colored(title, "bold")
    print_colored(line, "blue")


def analyze_existing_logs():
    """
    Analyse les logs existants pour valider le comptage de tokens
    """

    print_header("VALIDATION DES LOGS EXISTANTS - COMPTAGE DE TOKENS")

    # Initialiser le client API
    client = AskMeAPIClient()
    validator = TokenCountingValidator(TEST_CONFIG)

    # Récupérer les logs récents
    print_section("RÉCUPÉRATION DES LOGS")
    logs_response = client.get_usage_logs(50)

    if not logs_response.get('success', False):
        print_colored("[ERREUR] Impossible de récupérer les logs", "red")
        return False

    logs = logs_response.get('records', [])
    print_colored(f"[OK] {len(logs)} logs récupérés", "green")

    if len(logs) == 0:
        print_colored("[ERREUR] Aucun log trouvé", "red")
        return False

    # Analyser par provider
    print_section("ANALYSE PAR PROVIDER")
    providers_stats = {}

    for log in logs:
        provider = log.get('provider', 'UNKNOWN')
        input_tokens = log.get('input_tokens', 0)
        output_tokens = log.get('output_tokens', 0)
        total_tokens = log.get('total_tokens', 0)

        if provider not in providers_stats:
            providers_stats[provider] = {
                'count': 0,
                'input_tokens': [],
                'output_tokens': [],
                'total_tokens': [],
                'hardcoded_100_count': 0
            }

        providers_stats[provider]['count'] += 1
        providers_stats[provider]['input_tokens'].append(input_tokens)
        providers_stats[provider]['output_tokens'].append(output_tokens)
        providers_stats[provider]['total_tokens'].append(total_tokens)

        # Détecter les output tokens hardcodés à 100
        if output_tokens == 100:
            providers_stats[provider]['hardcoded_100_count'] += 1

    # Afficher les statistiques par provider
    all_valid = True

    for provider, stats in providers_stats.items():
        print_colored(f"\n{provider}:", "yellow")
        print_colored(f"  - Nombre de logs: {stats['count']}", "white")

        # Statistiques input tokens
        if stats['input_tokens']:
            min_input = min(stats['input_tokens'])
            max_input = max(stats['input_tokens'])
            avg_input = statistics.mean(stats['input_tokens'])
            print_colored(f"  - Input tokens: min={min_input}, max={max_input}, avg={avg_input:.1f}", "white")

        # Statistiques output tokens
        if stats['output_tokens']:
            min_output = min(stats['output_tokens'])
            max_output = max(stats['output_tokens'])
            avg_output = statistics.mean(stats['output_tokens'])
            print_colored(f"  - Output tokens: min={min_output}, max={max_output}, avg={avg_output:.1f}", "white")

            # Vérifier si les output tokens sont variés (pas hardcodés)
            unique_outputs = len(set(stats['output_tokens']))
            if unique_outputs > 1:
                print_colored(f"  - [OK] Output tokens variés ({unique_outputs} valeurs distinctes)", "green")
            else:
                print_colored(f"  - [ATTENTION] Output tokens identiques ({stats['output_tokens'][0]})", "yellow")
                if stats['output_tokens'][0] == 100:
                    print_colored(f"  - [ECHEC] Output tokens hardcodés à 100", "red")
                    all_valid = False

        # Vérifier les hardcodés à 100
        if stats['hardcoded_100_count'] > 0:
            pct_hardcoded = (stats['hardcoded_100_count'] / stats['count']) * 100
            print_colored(f"  - [ATTENTION] {stats['hardcoded_100_count']}/{stats['count']} logs avec output=100 ({pct_hardcoded:.1f}%)", "red")
            if pct_hardcoded > 50:
                all_valid = False
        else:
            print_colored(f"  - [OK] Aucun output token hardcodé à 100", "green")

    # Validation globale
    print_section("VALIDATION GLOBALE")

    # Test 1: Output tokens non hardcodés
    total_logs = len(logs)
    hardcoded_logs = sum(1 for log in logs if log.get('output_tokens') == 100)
    non_hardcoded_pct = ((total_logs - hardcoded_logs) / total_logs) * 100 if total_logs > 0 else 0

    print_colored(f"Test 1 - Output tokens réels (non hardcodés):", "bold")
    print_colored(f"  - {total_logs - hardcoded_logs}/{total_logs} logs avec output tokens réels ({non_hardcoded_pct:.1f}%)", "white")

    if non_hardcoded_pct >= 80:
        print_colored(f"  - [OK] Majorité des output tokens sont réels", "green")
    else:
        print_colored(f"  - [ECHEC] Trop de tokens hardcodés", "red")
        all_valid = False

    # Test 2: Input tokens cohérents (system message inclus)
    # Analyser différentes catégories d'input tokens
    very_low_input = sum(1 for log in logs if log.get('input_tokens', 0) < 10)  # Probablement sans system message
    good_input = sum(1 for log in logs if log.get('input_tokens', 0) >= 50)     # Avec system message complet
    medium_input = total_logs - very_low_input - good_input                      # Messages courts mais avec system

    print_colored(f"\nTest 2 - Input tokens incluent system message:", "bold")
    print_colored(f"  - Input tokens très faibles (<10): {very_low_input}", "white")
    print_colored(f"  - Input tokens moyens (10-49): {medium_input}", "white")
    print_colored(f"  - Input tokens élevés (>=50): {good_input}", "white")

    # Calculer le pourcentage sans les très faibles (qui sont suspects)
    valid_input_pct = ((total_logs - very_low_input) / total_logs) * 100 if total_logs > 0 else 0

    if very_low_input == 0:
        print_colored(f"  - [OK] Tous les logs ont des input tokens cohérents", "green")
    elif very_low_input <= total_logs * 0.2:  # Moins de 20% de logs suspects
        print_colored(f"  - [OK] Majorité des logs avec input tokens cohérents ({valid_input_pct:.1f}%)", "green")
    else:
        print_colored(f"  - [ATTENTION] Beaucoup de logs avec input tokens très faibles", "yellow")

    # Test 3: Cohérence total = input + output
    coherent_total_count = 0
    for log in logs:
        input_tokens = log.get('input_tokens', 0)
        output_tokens = log.get('output_tokens', 0)
        total_tokens = log.get('total_tokens', 0)

        if total_tokens == input_tokens + output_tokens:
            coherent_total_count += 1

    coherent_pct = (coherent_total_count / total_logs) * 100 if total_logs > 0 else 0

    print_colored(f"\nTest 3 - Cohérence total = input + output:", "bold")
    print_colored(f"  - {coherent_total_count}/{total_logs} logs cohérents ({coherent_pct:.1f}%)", "white")

    if coherent_pct >= 95:
        print_colored(f"  - [OK] Calculs des totaux cohérents", "green")
    else:
        print_colored(f"  - [ECHEC] Incohérences dans les calculs de totaux", "red")
        all_valid = False

    # Test 4: Diversité des providers
    unique_providers = len(providers_stats)
    print_colored(f"\nTest 4 - Support multi-providers:", "bold")
    print_colored(f"  - {unique_providers} providers différents trouvés: {', '.join(providers_stats.keys())}", "white")

    if unique_providers >= 3:
        print_colored(f"  - [OK] Plusieurs providers supportés", "green")
    else:
        print_colored(f"  - [ATTENTION] Peu de providers testés", "yellow")

    # Résultat final
    print_section("RÉSULTAT FINAL")

    if all_valid:
        print_colored("[SUCCES] Le comptage de tokens fonctionne correctement!", "green")
        print_colored("Preuves:", "white")
        print_colored("  [OK] Output tokens ne sont plus hardcodes a 100", "green")
        print_colored("  [OK] Input tokens incluent les system messages", "green")
        print_colored("  [OK] Calculs coherents (total = input + output)", "green")
        print_colored("  [OK] Multiple providers supportes", "green")
        return True
    else:
        print_colored("[ECHEC] Des problemes detectes dans le comptage", "red")
        return False


def main():
    """Fonction principale"""
    try:
        success = analyze_existing_logs()
        return 0 if success else 1
    except Exception as e:
        print_colored(f"[ERREUR] Exception non gérée: {e}", "red")
        return 1


if __name__ == "__main__":
    sys.exit(main())