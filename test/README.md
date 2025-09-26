# 🧪 Tests Automatisés AskMe

Suite de tests complète pour valider le comptage des tokens dans l'application AskMe.

## 📋 Vue d'ensemble

Cette suite de tests vérifie que le comptage des tokens fonctionne correctement pour tous les providers LLM supportés :

- ✅ **AZURE_OPENAI** - Azure OpenAI avec "On Your Data"
- ✅ **CLAUDE** - Anthropic Claude AI
- ✅ **MISTRAL** - Mistral AI
- ✅ **GEMINI** - Google Gemini
- ✅ **OPENAI_DIRECT** - OpenAI API directe

## 🚀 Installation

### Prérequis

- Python 3.8+
- Serveur AskMe en fonctionnement sur `localhost:50505`
- Variables d'environnement configurées (`.env`)

### Installation des dépendances

```bash
cd test
pip install -r requirements.txt
```

## 📖 Utilisation

### Lancer tous les tests

```bash
# Depuis le répertoire racine d'AskMe
python test/run_tests.py
```

### Options avancées

```bash
# Mode verbose avec détails supplémentaires
python test/run_tests.py --verbose

# Tester un seul provider
python test/run_tests.py --provider CLAUDE

# Sauvegarder les résultats en JSON
python test/run_tests.py --output results.json

# Combiner les options
python test/run_tests.py --verbose --provider MISTRAL --output mistral_test.json
```

## 🔍 Types de Tests

### Test 1 : Messages Simples
- **Message** : "Bonjour"
- **Objectif** : Vérifier le comptage de base (system message + output réel)
- **Validation** :
  - Input tokens > 100 (system message compris)
  - Output tokens ≠ 100 (pas hardcodé)
  - Total = Input + Output

### Test 2 : Messages avec Recherche Documentaire
- **Message** : "fiche de poste directeur r&d"
- **Objectif** : Vérifier l'inclusion du search context
- **Validation** :
  - Input tokens > 500 (system + documents)
  - Search context compté
  - Réponse basée sur les documents

## 📊 Interprétation des Résultats

### Codes de Status

- ✅ **SUCCÈS** - Test réussi
- ❌ **ÉCHEC** - Test échoué avec détails
- ⚠️ **ATTENTION** - Résultat inattendu

### Exemple de Sortie

```
========================================
   TESTS DE COMPTAGE DE TOKENS ASKME
========================================
Date: 2025-09-22 12:00:00
Serveur: http://localhost:50505

--------------------------------------------------
VÉRIFICATION DU SERVEUR
--------------------------------------------------
✅ Serveur opérationnel: Server responding correctly

--------------------------------------------------
TEST 1: MESSAGE SIMPLE - TOUS PROVIDERS
--------------------------------------------------
✅ AZURE_OPENAI: Input=338 Output=46
✅ CLAUDE: Input=357 Output=617
✅ MISTRAL: Input=250 Output=253
✅ GEMINI: Input=180 Output=48
✅ OPENAI_DIRECT: Input=85 Output=516

--------------------------------------------------
TEST 2: AVEC RECHERCHE DOCUMENTAIRE - TOUS PROVIDERS
--------------------------------------------------
✅ AZURE_OPENAI: Input=2450 Output=450
✅ CLAUDE: Input=2680 Output=780
❌ MISTRAL: Input tokens trop faible pour une recherche (244), search context probablement non compté (minimum: 600)
✅ GEMINI: Input=2200 Output=280
✅ OPENAI_DIRECT: Input=2300 Output=680

--------------------------------------------------
RÉSUMÉ
--------------------------------------------------
Tests réussis: 9/10
Tests échoués: 1
Taux de succès: 90.0%
Temps total: 45.3s

❌ ÉCHEC: Certains tests ont échoué
Catégories d'erreurs:
  - search_context: 1

💾 Résultats sauvegardés: test_results_20250922_120000.json
```

## 🔧 Configuration

### Configuration par Défaut

La configuration se trouve dans `test/token_counting/config.py` :

```python
TEST_CONFIG = {
    "providers": ["AZURE_OPENAI", "CLAUDE", "MISTRAL", "GEMINI", "OPENAI_DIRECT"],
    "validation": {
        "min_system_tokens": 100,
        "min_search_context_chars": 1000,
        "output_tolerance_percent": 20
    },
    "timeouts": {
        "request": 45,
        "wait_for_logs": 15
    }
}
```

### Configuration Personnalisée

Créez un fichier JSON avec vos paramètres :

```json
{
    "providers": ["CLAUDE", "MISTRAL"],
    "validation": {
        "min_system_tokens": 150
    },
    "timeouts": {
        "request": 60
    }
}
```

Puis lancez avec :

```bash
python test/run_tests.py --config custom_config.json
```

## 🐛 Résolution des Problèmes

### Erreurs Communes

#### "Serveur indisponible"
```bash
# Vérifier que le serveur tourne
curl http://localhost:50505/api/usage/logs

# Si nécessaire, relancer le serveur
python -m uvicorn app:app --port 50505 --reload
```

#### "Unauthorized"
- Vérifier que `AUTH_ENABLED=true` dans `.env`
- Vérifier que `AVANTEAM_AUTH_TOKEN` est correct

#### "Aucun log trouvé"
- Le container CosmosDB `token_usage` doit exister
- Augmenter `wait_for_logs` dans la config

#### "Search context non compté"
- Vérifier que `DATASOURCE_TYPE=AzureCognitiveSearch`
- Vérifier la configuration Azure Search

### Mode Debug

Pour plus de détails :

```bash
# Mode verbose
python test/run_tests.py --verbose

# Tester un seul provider
python test/run_tests.py --provider CLAUDE --verbose
```

## 📁 Structure des Fichiers

```
test/
├── run_tests.py                    # Script principal
├── requirements.txt                # Dépendances Python
├── README.md                       # Cette documentation
│
├── token_counting/
│   ├── __init__.py
│   ├── config.py                   # Configuration des tests
│   └── test_token_counting.py      # Tests principaux
│
└── utils/
    ├── __init__.py
    ├── auth.py                     # Authentification automatique
    ├── api_client.py              # Client API réutilisable
    └── validators.py              # Validateurs de résultats
```

## 🔄 Intégration CI/CD

### Script de Build

```bash
#!/bin/bash
# Lancer les tests automatiquement
cd /path/to/askme
python test/run_tests.py --output ci_results.json

# Vérifier le code de sortie
if [ $? -eq 0 ]; then
    echo "✅ Tests réussis"
else
    echo "❌ Tests échoués"
    exit 1
fi
```

### GitHub Actions

```yaml
- name: Test Token Counting
  run: |
    python test/run_tests.py --output test_results.json

- name: Upload Results
  uses: actions/upload-artifact@v2
  with:
    name: test-results
    path: test_results.json
```

## 🤝 Contribution

Pour ajouter de nouveaux tests :

1. Créer une nouvelle méthode dans `TokenCountingTests`
2. Ajouter la validation correspondante dans `TokenCountingValidator`
3. Mettre à jour la configuration si nécessaire
4. Tester avec `python test/run_tests.py --verbose`

## 📞 Support

En cas de problème :

1. Vérifier les logs du serveur AskMe
2. Lancer en mode verbose : `--verbose`
3. Vérifier la configuration dans `config.py`
4. Consulter les résultats JSON pour plus de détails