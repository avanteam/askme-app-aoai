# 🤖 AskMe - Assistant AI Multi-Client

[![GitHub release](https://img.shields.io/github/v/release/avanteam/askme-app-aoai)](https://github.com/avanteam/askme-app-aoai/releases)
[![Docker](https://img.shields.io/badge/docker-Harbor%20OVH-blue)](https://7wpjr0wh.c1.gra9.container-registry.ovh.net)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.21+-green)](https://kubernetes.io)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](./tests/)

AskMe est un assistant virtuel d'entreprise multi-client qui supporte plusieurs fournisseurs LLM et se déploie facilement via Kubernetes/Rancher.

## 🎯 Fonctionnalités

### 🧠 Multi-LLM Support
- **Azure OpenAI** - Service Azure avec intégration native
- **Claude** - Anthropic Claude 4 Sonnet pour des réponses précises
- **OpenAI Direct** - API OpenAI directe (GPT-4o)
- **Mistral** - Modèles Mistral AI open-source
- **Gemini** - Google Gemini pour la diversité des réponses

### 🏢 Architecture Multi-Client
- **Isolation complète** par namespace Kubernetes
- **Configuration personnalisée** par client via Rancher UI
- **DNS automatique** avec gestion OVH intégrée
- **Scaling indépendant** par déploiement

### 🎤 Fonctionnalités Avancées
- **Reconnaissance vocale** avec mots-clés d'activation
- **Synthèse vocale** Azure Speech Services
- **Upload d'images** avec analyse multimodale
- **Historique conversations** stocké en CosmosDB
- **Citations automatiques** depuis Azure Search

## 🚀 Démarrage Rapide

### Prérequis
- **Windows 10/11** - Environnement de développement principal
- **Docker** & **Docker Compose** pour les tests locaux
- **Node.js 20+** pour le développement frontend
- **Python 3.11+** pour le backend
- **kubectl** configuré pour accès au cluster Kubernetes
- **Kubernetes** cluster pour la production (OVH via Rancher Catalog)

### Installation Locale

```bash
# 1. Cloner le repository
git clone https://github.com/avanteam/askme-app-aoai.git
cd askme-app-aoai

# 2. Configuration
cp deployment/config/.env.sample .env
# Éditer .env avec vos clés API

# 3. Démarrage (build frontend + backend) - Windows uniquement
tools\local\start.cmd
```

L'application sera disponible sur http://localhost:5007

### Déploiement Production

Le déploiement se fait exclusivement via **askme-rancher-catalog** :

1. **Push des modifications** vers `test-rg2` pour tests
2. **Merge vers `prod`** quand prêt pour release
3. **Créer un tag** `v1.x.x` qui déclenche automatiquement :
   - GitHub Actions build et push vers Harbor Registry OVH
   - Synchronisation du catalog Rancher
4. **Déployer via Rancher UI** avec la nouvelle version disponible

Voir [`docs/deployment/workflow-release.md`](docs/deployment/workflow-release.md) pour le processus détaillé.

## ⚙️ Configuration

### Variables d'Environnement Principales

```env
# Provider LLM par défaut
LLM_PROVIDER=CLAUDE
AVAILABLE_LLM_PROVIDERS=AZURE_OPENAI,CLAUDE,OPENAI_DIRECT,MISTRAL,GEMINI

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_KEY=your_azure_key
AZURE_OPENAI_MODEL=gpt-4o

# Claude AI
CLAUDE_API_KEY=your_claude_key
CLAUDE_MODEL=claude-sonnet-4-20250514

# OpenAI Direct
OPENAI_DIRECT_API_KEY=your_openai_key
OPENAI_DIRECT_MODEL=gpt-4o

# Azure Search (données contextuelles)
AZURE_SEARCH_SERVICE=your-search-service
AZURE_SEARCH_INDEX=your-index
AZURE_SEARCH_KEY=your_search_key
```

Voir `deployment/config/.env.sample` pour la configuration complète.

### Interface de Personnalisation

L'application propose une interface graphique permettant aux utilisateurs de :
- **Changer de provider LLM** en temps réel
- **Ajuster la longueur des réponses** (courtes, normales, détaillées)
- **Modifier le nombre de documents** de référence
- **Configurer la reconnaissance vocale**

## 🏗️ Architecture du Projet

### Structure Réorganisée (Production-Ready)
```
askme-app-aoai/
├── 📋 README.md, CLAUDE.md, LICENSE        # Documentation principale
├── 🏗️ app.py, backend/, frontend/         # Code application
├── 📚 docs/                                # Documentation organisée
│   ├── deployment/                         # Guides K8s et CI/CD
│   ├── api/                               # Documentation API
│   ├── features/                          # Fonctionnalités avancées
│   └── ovh/                              # Configuration OVH
├── 🧪 tests/                              # Tests structurés
│   ├── unit_tests/                        # Tests unitaires
│   ├── integration_tests/                 # Tests d'intégration
│   ├── functional_tests/                  # Tests fonctionnels
│   └── api/                              # Tests API
├── 🔧 tools/                              # Scripts utilitaires
│   ├── local/                            # Développement local (Windows)
│   ├── data/                             # Scripts préparation données
│   └── development/                      # Outils debug et tunnel
├── 📦 deployment/                         # Configuration déploiement
│   ├── docker/                           # Dockerfiles
│   ├── config/                           # Configurations env
│   └── ci-cd/                           # Backup CI/CD
└── 📝 requirements*.txt                   # Dépendances Python
```

### Backend (Python/Quart)
```
backend/
├── llm_providers/          # Abstraction multi-LLM avec gestion d'erreur unifiée
├── search_providers/       # Système RAG unifié (Sept 2025)
├── auth/                   # Authentification Microsoft Entra ID
├── history/                # Gestion historique CosmosDB/MongoDB
└── settings.py             # Configuration centralisée via environnement
```

### Frontend (React/TypeScript)
```
frontend/src/
├── components/             # Composants React réutilisables
├── hooks/                  # Hooks personnalisés (voice, API)
├── state/                  # Gestion d'état globale
└── api/                    # Client API avec types TypeScript
```

### Déploiement
- **Local** : Scripts Windows dans `tools/local/`
- **Production** : Exclusivement via `askme-rancher-catalog`
- **CI/CD** : GitHub Actions → Harbor Registry → Rancher UI

## 🧪 Tests

### Structure des Dépendances de Test

```bash
# Installation selon l'environnement
pip install -r requirements.txt          # Production uniquement
pip install -r requirements-dev.txt      # Développement (inclut pytest, coverage)
pip install -r requirements-test.txt     # Tests avancés (E2E, performance)
```

### Exécution des Tests

```bash
# Tests backend
pytest tests/unit_tests/           # Tests unitaires
pytest tests/functional_tests/    # Tests fonctionnels (LLM providers)
pytest tests/integration_tests/   # Tests d'intégration
pytest tests/api/                 # Tests API externes

# Tests frontend
cd frontend && npm test

# Tests E2E
cd tests/e2e && npx playwright test
```

## 🔧 Développement Local

### Scripts de Développement (Windows)

```cmd
REM Démarrage complet (tunnel MongoDB + frontend + backend)
tools\local\start.cmd

REM Build Docker local pour tests
tools\local\deploy-local.ps1 build
tools\local\deploy-local.ps1 run

REM Tunnel MongoDB Kubernetes pour développement
tools\development\mongodb-tunnel.cmd start
```

### Outils de Debug

```cmd
REM Script de debug Python avec logs détaillés
python tools\development\main_debug.py

REM Configuration pronunciation personnalisée
edit tools\development\pronunciation_custom.json
```

## 🔧 Développement

### Architecture des Providers LLM

Chaque provider implémente l'interface `LLMProvider` :

```python
class LLMProvider(ABC):
    @abstractmethod
    async def send_request(self, messages: List[Dict], stream: bool = True, **kwargs):
        """Envoyer une requête au provider"""
        pass
    
    @abstractmethod  
    def format_response(self, raw_response: Any, stream: bool = True):
        """Formater la réponse en format standard"""
        pass
```

### Ajout d'un Nouveau Provider

1. Créer `backend/llm_providers/nouveau_provider.py`
2. Implémenter la classe `NouveauProvider(LLMProvider)`
3. Ajouter dans `backend/llm_providers/__init__.py`
4. Ajouter la configuration dans `backend/settings.py`

### Commandes de Développement

```bash
# Frontend
cd frontend
npm run dev                 # Serveur de développement
npm run build              # Build production
npm run lint               # Vérification code

# Backend  
python -m uvicorn app:app --port 50505 --reload
python -m pytest --cov    # Tests avec couverture
```

## 📊 Monitoring

### Surveillance des Déploiements

```bash
# Dashboard en temps réel
./scripts/monitor-clients.sh

# Status d'un client spécifique
kubectl get pods -n askme-client-name
kubectl logs deployment/askme-app -n askme-client-name
```

### Métriques Disponibles

- **Performance** : Temps de réponse LLM par provider
- **Utilisation** : Nombre de conversations par client
- **Ressources** : CPU, RAM, stockage par déploiement
- **Santé** : Status des pods et services

## 🔄 Workflow de Release

### 1. Développement
```bash
git checkout test-rg2
# ... développement ...
git commit -m "feat: nouvelle fonctionnalité"
git push origin test-rg2
```

### 2. Release
```bash
# Synchronisation des versions entre repositories
./scripts/release-sync.sh
# Choisir version (ex: v1.2.0)
# Tags automatiquement les deux repos
```

### 3. Déploiement
- **Automatique** : Pipeline CI/CD build l'image Docker et package Helm
- **Manuel** : Interface Rancher ou script CLI

### 4. Mise à Jour Client
- Sélection de version dans Rancher UI
- Rolling update sans interruption
- Rollback 1-clic en cas de problème

## 🤝 Contribution

### Standards de Code

- **Python** : PEP 8, type hints obligatoires
- **TypeScript** : Airbnb config, composants fonctionnels
- **Git** : Conventional commits, rebase workflow
- **Documentation** : Inline + README mis à jour

### Pull Request

1. Fork du repository
2. Feature branch depuis `test-rg2`
3. Tests passants requis
4. Documentation mise à jour
5. Review avant merge

## 📄 Licence

Copyright © 2025 Avanteam. Tous droits réservés.

## 🆘 Support

- **Documentation** : Voir `/docs` et guides spécialisés
- **Issues** : [GitHub Issues](https://github.com/avanteam/askme-app-aoai/issues)
- **Support** : Équipe DevOps Avanteam

---

<div align="center">

**[Rancher Catalog](https://github.com/avanteam/askme-rancher-catalog)** • **[Documentation Complète](./CLAUDE.md)** • **[Guide Workflow](./WORKFLOW_RELEASE.md)**

</div>