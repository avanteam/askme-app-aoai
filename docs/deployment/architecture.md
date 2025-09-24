# 🏗️ Architecture Technique AskMe

## Vue d'Ensemble

AskMe est un assistant virtuel d'entreprise conçu avec une architecture moderne et scalable, supportant plusieurs fournisseurs LLM et déployable sur infrastructure Kubernetes via Rancher Catalog.

## 🎯 Principes de Conception

### Production-Ready
- **Séparation des responsabilités** : Code, configuration, documentation et tests clairement séparés
- **Configuration par environnement** : Variables d'environnement pour tous les paramètres
- **Gestion d'erreur unifiée** : Messages utilisateur cohérents en français
- **Logging structuré** : Traçabilité complète des opérations

### Multi-Client
- **Isolation par namespace** Kubernetes
- **Configuration personnalisée** par client via Rancher UI
- **Scaling indépendant** : Ressources dédiées par déploiement
- **DNS automatique** : Gestion des domaines OVH intégrée

## 🏗️ Architecture Applicative

### Backend - Python/Quart (Asynchrone)

```
backend/
├── llm_providers/              # Abstraction Multi-LLM
│   ├── base.py                 # Interface commune
│   ├── errors.py               # Gestion d'erreur unifiée
│   ├── azure_openai.py         # Provider Azure OpenAI
│   ├── claude.py               # Provider Anthropic Claude
│   ├── openai_direct.py        # Provider OpenAI Direct
│   ├── mistral.py              # Provider Mistral AI
│   └── gemini.py               # Provider Google Gemini
├── search_providers/           # Système RAG Unifié (Sept 2025)
│   ├── base.py                 # Interface SearchProvider
│   ├── azure_search.py         # Provider Azure AI Search optimisé
│   └── __init__.py             # Factory pattern extensible
├── auth/                       # Authentification Microsoft Entra ID
├── history/                    # Gestion historique conversations
│   ├── cosmosdb/               # Provider CosmosDB
│   └── mongodb/                # Provider MongoDB
├── security/                   # Sécurité & compliance
└── settings.py                 # Configuration centralisée
```

#### Caractéristiques Backend
- **Framework** : Quart (Flask asynchrone) pour performance
- **Streaming** : Support des réponses en temps réel via Server-Sent Events
- **Multi-LLM** : Architecture plugin pour ajout facile de nouveaux providers
- **RAG Unifié** : Système de recherche optimisé pour tous les LLM
- **Authentification** : Microsoft Entra ID avec support multi-tenant

### Frontend - React/TypeScript

```
frontend/src/
├── components/                 # Composants React réutilisables
│   ├── Answer/                 # Affichage réponses avec streaming
│   ├── QuestionInput/          # Interface saisie avec vocal
│   ├── ChatHistory/            # Panneau historique
│   └── Customization/          # Panneau personnalisation
├── hooks/                      # Hooks personnalisés
│   ├── useVoiceRecognition.ts  # Reconnaissance vocale
│   ├── useStreamingResponse.ts # Gestion streaming
│   └── useAPI.ts               # Client API
├── state/                      # Gestion d'état globale
│   ├── AppProvider.tsx         # Context principal
│   └── AppReducer.tsx          # Logic state management
└── api/                        # Client API avec types
    ├── api.ts                  # Client HTTP
    └── models.ts               # Types TypeScript
```

#### Caractéristiques Frontend
- **Framework** : React 18 avec TypeScript strict
- **Build Tool** : Vite pour développement rapide
- **State Management** : Context API + useReducer pattern
- **Voice Features** : WebRTC + Azure Speech Services
- **Responsive** : Design adaptatif mobile-first

## 🔄 Flux de Données

### Conversation Standard
```
User Input → Frontend → Backend API → LLM Provider → RAG Search → Response Stream → Frontend Display
```

### Conversation avec Images
```
User Input + Image → Compression → LLM Provider (Vision) → Response Stream → Storage (Compressed) → Display
```

### Reconnaissance Vocale
```
Audio Input → WebRTC → Azure Speech → Text → Standard Conversation Flow
```

## 🗄️ Persistence et Stockage

### Base de Données
- **Historique Conversations** : CosmosDB (principal) ou MongoDB
- **Configuration Utilisateur** : Session en mémoire serveur
- **Images** : Compression automatique < 300KB pour CosmosDB

### Cache et Performance
- **Images** : Version originale pour LLM, compressée pour stockage
- **Réponses** : Pas de cache (conversations temps réel)
- **Configuration** : Cache session utilisateur

## 🔐 Sécurité et Authentification

### Authentification
- **Microsoft Entra ID** : SSO entreprise
- **Multi-tenant** : Support plusieurs organisations
- **Headers sécurisés** : Transmission user info via headers HTTP

### Sécurité Données
- **Chiffrement transit** : HTTPS/TLS obligatoire
- **Validation input** : Sanitisation côté backend
- **Content filtering** : Filtres de contenu LLM providers
- **Secrets management** : Variables d'environnement uniquement

## 🎛️ Configuration et Personnalisation

### Variables d'Environnement Principales
```env
# LLM Configuration
LLM_PROVIDER=CLAUDE
AVAILABLE_LLM_PROVIDERS=AZURE_OPENAI,CLAUDE,OPENAI_DIRECT,MISTRAL,GEMINI

# Authentication
AZURE_USE_AUTHENTICATION=true
AZURE_CLIENT_ID=your-client-id

# Data Sources
DATASOURCE_TYPE=AzureCognitiveSearch
AZURE_SEARCH_SERVICE=your-search-service

# Features
VOICE_INPUT_ENABLED=true
AZURE_SPEECH_ENABLED=true
IMAGE_MAX_SIZE_MB=10.0
```

### Personnalisation Utilisateur
- **Interface dynamique** : Changement provider LLM en temps réel
- **Paramètres conversation** : Longueur réponse, nombre documents
- **Commandes chat** : Modification config via langage naturel
- **Reconnaissance vocale** : Wake words configurables

## 🚀 Déploiement et Infrastructure

### Architecture Kubernetes
```
OVH Kubernetes Cluster
├── Namespace par client (askme-client1, askme-client2)
├── Harbor Registry (7wpjr0wh.c1.gra9.container-registry.ovh.net)
├── Ingress avec certificats Let's Encrypt
└── Rancher UI pour management
```

### Workflow CI/CD
```
Development → test-rg2 → GitHub Actions (tests) → prod branch →
Git Tag v1.x.x → Build & Push Harbor → Sync Rancher Catalog → Deploy via Rancher UI
```

### Composants Déployés
- **Backend** : Pod Python/Quart avec auto-scaling
- **Frontend** : Assets statiques servis par backend
- **Ingress** : SSL termination et routing domaines
- **ConfigMaps** : Configuration par environnement
- **Secrets** : Clés API et certificats

## 📊 Monitoring et Observabilité

### Logs Applicatifs
- **Structured logging** : Format JSON avec contexte
- **Provider identification** : Logs spécifiques par LLM
- **Error tracking** : Traçabilité complète des erreurs
- **Performance metrics** : Temps de réponse par provider

### Health Checks
- **Kubernetes probes** : Liveness et readiness
- **Provider health** : Vérification API LLM disponibles
- **Database connectivity** : Tests connexion périodiques

## 🔄 Evolutivité et Extensions

### Nouveaux Providers LLM
1. Créer classe héritant de `BaseLLMProvider`
2. Implémenter méthodes requises (`send_message`, `send_message_stream`)
3. Ajouter configuration environnement
4. Tests et documentation

### Nouveaux Search Providers
1. Créer classe héritant de `SearchProvider`
2. Implémenter logique de recherche
3. Ajouter au factory pattern
4. Configuration et tests

### Multi-Region
- **Kubernetes federation** : Déploiement multi-cluster
- **DNS géolocalisé** : Routing intelligent OVH
- **Réplication données** : Synchronisation CosmosDB global

Cette architecture garantit une base solide pour l'évolution continue d'AskMe tout en maintenant performance, sécurité et facilité de maintenance.