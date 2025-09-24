# 📚 Guide Complet de Déploiement Kubernetes sur OVH

## 🎯 Objectif de ce Document

Ce document fournit un **guide pédagogique complet** pour comprendre, déployer et maintenir des applications sur l'infrastructure Kubernetes OVH. Il s'adresse aux informaticiens souhaitant maîtriser les concepts fondamentaux de Docker et Kubernetes sans connaissances préalables.

---

## 📋 Table des Matières

1. [🏗️ Architecture Générale](#️-architecture-générale)
2. [🔧 Concepts Fondamentaux](#-concepts-fondamentaux)
3. [🚀 Infrastructure OVH Mise en Place](#-infrastructure-ovh-mise-en-place)
4. [📁 Structure du Projet AskMe](#-structure-du-projet-askme)
5. [⚙️ Configuration et Variables d'Environnement](#️-configuration-et-variables-denvironnement)
6. [🐳 Déploiement d'une Nouvelle Application](#-déploiement-dune-nouvelle-application)
7. [🔄 Mise à Jour d'une Application Existante](#-mise-à-jour-dune-application-existante)
8. [🔒 Gestion SSL avec Let's Encrypt](#-gestion-ssl-avec-lets-encrypt)
9. [🔍 Surveillance et Troubleshooting](#-surveillance-et-troubleshooting)
10. [📚 Ressources et Bonnes Pratiques](#-ressources-et-bonnes-pratiques)

---

## 🏗️ Architecture Générale

### Vue d'Ensemble de l'Écosystème

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNET                                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │
              ┌───────▼────────┐
              │   CLOUDFLARE   │ (DNS + CDN)
              │askme.avanteam- │
              │  online.com    │
              └───────┬────────┘
                      │
        ┌─────────────▼──────────────┐
        │      OVH KUBERNETES        │
        │     MANAGED CLUSTER        │
        │   (65espx.c1.gra9.k8s...)  │
        └─────────────┬──────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │            INGRESS                 │
    │    NGINX Ingress Controller        │
    │  + Let's Encrypt (cert-manager)    │
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────▼──────────────────┐
    │         KUBERNETES PODs            │
    │    ┌──────────┐  ┌──────────┐     │
    │    │ AskMe    │  │ AskMe    │     │
    │    │ App #1   │  │ App #2   │     │
    │    └──────────┘  └──────────┘     │
    └────────────────────────────────────┘
              │                  │
    ┌─────────▼─────────┐ ┌─────▼──────┐
    │   HARBOR REGISTRY │ │   AZURE    │
    │  (Images Docker)  │ │ SERVICES   │
    │ 7wpjr0wh.c1.gra9  │ │(OpenAI,    │
    │.container-        │ │ Search,    │
    │registry.ovh.net   │ │ CosmosDB)  │
    └───────────────────┘ └────────────┘
```

### Composants Principaux

#### 1. **Cluster Kubernetes OVH**
- **Rôle** : Orchestrateur de conteneurs qui gère automatiquement le déploiement, la mise à l'échelle et la surveillance des applications
- **Avantages** : Haute disponibilité, auto-guérison, équilibrage de charge automatique
- **URL d'accès** : `65espx.c1.gra9.k8s.ovh.net`

#### 2. **Harbor Registry OVH**
- **Rôle** : Entrepôt privé et sécurisé pour stocker les images Docker
- **URL** : `7wpjr0wh.c1.gra9.container-registry.ovh.net`
- **Avantages** : Contrôle d'accès, scan de vulnérabilités, versioning des images

#### 3. **NGINX Ingress Controller**
- **Rôle** : Point d'entrée HTTP/HTTPS qui route le trafic vers les applications
- **Fonctionnalités** : Terminaison SSL, équilibrage de charge, gestion des domaines

#### 4. **cert-manager + Let's Encrypt**
- **Rôle** : Génération et renouvellement automatique des certificats SSL
- **Avantages** : HTTPS gratuit, renouvellement automatique, sécurité renforcée

---

## 🔧 Concepts Fondamentaux

### Docker : La Conteneurisation

#### Qu'est-ce qu'un Container ?
Un **container** est comme une "boîte" légère qui contient :
- ✅ Votre application (code source)
- ✅ Toutes ses dépendances (bibliothèques, runtime)
- ✅ Le système d'exploitation minimal nécessaire
- ✅ La configuration d'exécution

#### Analogie Simple
```
🏠 Serveur Traditionnel          📦 Container Docker
┌─────────────────────────┐      ┌──────────────────────┐
│  OS Complet (Ubuntu)    │      │  Application AskMe   │
│  ├── Java               │  VS  │  ├── Python 3.11     │
│  ├── Python             │      │  ├── Dependencies    │
│  ├── Node.js            │      │  └── OS Minimal      │
│  ├── App1               │      └──────────────────────┘
│  ├── App2               │      
│  └── App3               │      📦 Container Nginx
└─────────────────────────┘      ┌──────────────────────┐
                                 │  Nginx Web Server    │
Ressources partagées             │  ├── Configuration   │
Conflits possibles               │  └── OS Minimal      │
                                 └──────────────────────┘
                                 
                                 Isolés, légers, portables
```

### Kubernetes : L'Orchestrateur

#### Qu'est-ce que Kubernetes ?
Kubernetes est un **chef d'orchestre** qui gère automatiquement :
- 🔄 **Déploiement** : Lance vos containers sur les serveurs disponibles
- 📈 **Mise à l'échelle** : Augmente/diminue le nombre de containers selon la charge
- 🔧 **Auto-guérison** : Redémarre automatiquement les containers défaillants
- 🌐 **Réseau** : Gère les communications entre containers
- 💾 **Stockage** : Gère les volumes de données persistantes

#### Architecture Kubernetes Simplifiée

```
┌──────────────────────────────────────────────────────┐
│                 CLUSTER KUBERNETES                   │
│                                                      │
│  ┌─────────────────┐    ┌─────────────────┐         │
│  │     NODE 1      │    │     NODE 2      │         │
│  │  ┌───────────┐  │    │  ┌───────────┐  │         │
│  │  │    POD    │  │    │  │    POD    │  │         │
│  │  │ ┌───────┐ │  │    │  │ ┌───────┐ │  │         │
│  │  │ │App#1  │ │  │    │  │ │App#2  │ │  │         │
│  │  │ └───────┘ │  │    │  │ └───────┘ │  │         │
│  │  └───────────┘  │    │  └───────────┘  │         │
│  └─────────────────┘    └─────────────────┘         │
│                                                      │
│  ┌──────────────────────────────────────────────────┤
│  │              CONTROL PLANE                       │
│  │  • API Server (point d'entrée des commandes)     │
│  │  • Scheduler (décide où placer les containers)   │
│  │  • Controller Manager (surveille l'état)         │
│  │  • etcd (base de données de configuration)       │
│  └──────────────────────────────────────────────────│
└──────────────────────────────────────────────────────┘
```

### Objets Kubernetes Essentiels

#### 1. **Namespace** 🏠
```yaml
# Comme une "maison" qui isole vos applications
apiVersion: v1
kind: Namespace
metadata:
  name: askme-app
```
**Rôle** : Sépare logiquement les ressources (dev, test, prod)

#### 2. **ConfigMap** ⚙️
```yaml
# Stocke la configuration non-sensible
apiVersion: v1
kind: ConfigMap
metadata:
  name: askme-config
data:
  DEBUG: "true"
  UI_TITLE: "Avanteam AskMe"
```
**Rôle** : Variables d'environnement publiques

#### 3. **Secret** 🔐
```yaml
# Stocke les données sensibles (mots de passe, clés API)
apiVersion: v1
kind: Secret
metadata:
  name: askme-secrets
stringData:
  AZURE_OPENAI_KEY: "[VOTRE_AZURE_OPENAI_KEY]"
```
**Rôle** : Variables d'environnement sécurisées

#### 4. **Deployment** 🚀
```yaml
# Définit comment déployer votre application
apiVersion: apps/v1
kind: Deployment
metadata:
  name: askme-app
spec:
  replicas: 2  # Nombre de copies de l'app
  template:
    spec:
      containers:
      - name: askme-app
        image: harbor.ovh.net/askme/app:latest
```
**Rôle** : Gère le cycle de vie de l'application

#### 5. **Service** 🌐
```yaml
# Expose votre application à l'intérieur du cluster
apiVersion: v1
kind: Service
metadata:
  name: askme-service
spec:
  ports:
  - port: 80
    targetPort: 80
  selector:
    app: askme-app
```
**Rôle** : Point de communication interne

#### 6. **Ingress** 🚪
```yaml
# Expose votre application sur Internet
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: askme-ingress
spec:
  rules:
  - host: askme.avanteam-online.com
    http:
      paths:
      - path: /
        backend:
          service:
            name: askme-service
```
**Rôle** : Point d'entrée depuis Internet

---

## 🚀 Infrastructure OVH Mise en Place

### Configuration du Cluster Kubernetes

#### Informations de Connexion
```bash
# URL du cluster OVH
CLUSTER_URL="65espx.c1.gra9.k8s.ovh.net"

# Fichier de configuration kubectl
KUBECONFIG_PATH="/mnt/c/Users/Richard Garcia/Downloads/kubeconfig (1).yml"
```

#### Vérification de la Connectivité
```bash
# Test de connexion au cluster
kubectl cluster-info

# Affichage des nodes disponibles
kubectl get nodes

# Vérification des namespaces
kubectl get namespaces
```

### Configuration du Registry Harbor

#### Accès Harbor OVH
```bash
# URL du registry
HARBOR_URL="7wpjr0wh.c1.gra9.container-registry.ovh.net"

# Identifiants de connexion
USERNAME="[VOTRE_USERNAME_HARBOR]"
PASSWORD="[VOTRE_PASSWORD_HARBOR]"

# Interface web
WEB_URL="https://7wpjr0wh.c1.gra9.container-registry.ovh.net/"
```

#### Connexion Docker au Registry
```bash
# Connexion Docker
docker login 7wpjr0wh.c1.gra9.container-registry.ovh.net \
  --username [VOTRE_USERNAME_HARBOR] \
  --password [VOTRE_PASSWORD_HARBOR]

# Vérification de la connexion
docker info | grep Registry
```

### Configuration DNS

#### Enregistrement DNS Configuré
```
Domaine: askme.avanteam-online.com
Type: A
Valeur: 57.128.59.187 (IP du LoadBalancer Kubernetes)
TTL: 3600 secondes
```

#### Vérification DNS
```bash
# Test de résolution DNS
nslookup askme.avanteam-online.com

# Test de connectivité
ping askme.avanteam-online.com

# Vérification du certificat SSL
curl -I https://askme.avanteam-online.com
```

---

## 📁 Structure du Projet AskMe

### Architecture du Code Source

```
askme-app-aoai/
├── 📁 backend/                    # Code Python (API)
│   ├── 🐍 app.py                 # Point d'entrée principal
│   ├── ⚙️ settings.py            # Configuration globale
│   ├── 🤖 llm_providers/         # Intégrations IA
│   ├── 🔊 speech_services.py     # Services vocaux
│   └── 🛡️ security/              # Modules de sécurité
├── 📁 frontend/                   # Code React/TypeScript
│   ├── 📦 package.json           # Dépendances Node.js
│   ├── ⚛️ src/                   # Code source React
│   ├── 🎨 public/                # Assets statiques
│   └── ⚙️ vite.config.ts         # Configuration build
├── 📁 k8s/                       # Configuration Kubernetes
│   ├── 🏠 namespace.yaml         # Isolation des ressources
│   ├── ⚙️ configmap.yaml         # Configuration publique
│   ├── 🔐 secret.yaml            # Configuration secrète
│   ├── 🚀 deployment.yaml        # Définition de l'app
│   ├── 🌐 service.yaml           # Exposition interne
│   ├── 🚪 ingress.yaml           # Exposition Internet
│   ├── 🔒 letsencrypt-issuer.yaml # Générateur SSL
│   └── 📜 deploy.sh              # Script d'automatisation
├── 🐳 WebApp.Dockerfile          # Instructions de build
├── ⚙️ .env                       # Variables d'environnement
├── 📋 requirements*.txt          # Dépendances Python hiérarchisées (prod, dev, test)
└── 📚 README.md                  # Documentation
```

### Détail des Composants Clés

#### Backend Python (Quart Framework)
```python
# app.py - Structure principale
from quart import Quart, request, jsonify
from backend.llm_providers import LLMProviderFactory
from backend.settings import app_settings

app = Quart(__name__)

@app.route('/conversation', methods=['POST'])
async def conversation():
    """Endpoint principal pour le chat avec streaming"""
    # Logique de traitement des messages
    # Intégration avec les LLM providers
    # Gestion des citations et références
```

#### Frontend React/TypeScript
```typescript
// Chat.tsx - Interface principale
import { useVoiceRecognition } from '../hooks/useVoiceRecognition';
import { Answer } from '../components/Answer';
import { QuestionInput } from '../components/QuestionInput';

export const Chat: React.FC = () => {
    // Gestion des messages
    // Intégration vocale
    // Streaming des réponses
    // Upload d'images
};
```

#### Configuration Docker Multi-Stage

```dockerfile
# WebApp.Dockerfile - Build en 2 étapes
FROM node:20-alpine AS frontend
# Build du frontend React

FROM python:3.11-alpine
# Build du backend Python + intégration frontend
```

---

## ⚙️ Configuration et Variables d'Environnement

### Fichier .env Source

Le fichier `.env` contient **toute la configuration** de l'application :

#### 1. **Configuration UI**
```env
UI_TITLE=Avanteam AskMe
UI_LOGO=https://aimanager-dev.avanteam-online.com/app/custom/ai/shareddata/logoavanteamai.png
UI_CHAT_TITLE=Commencer une discussion
UI_SHOW_EXPORT_BUTTON=True
```

#### 2. **Providers LLM Supportés**
```env
# Provider par défaut
LLM_PROVIDER=AZURE_OPENAI

# Providers disponibles dans l'interface
AVAILABLE_LLM_PROVIDERS=AZURE_OPENAI,CLAUDE,OPENAI_DIRECT,MISTRAL,GEMINI
```

#### 3. **Azure OpenAI**
```env
AZURE_OPENAI_ENDPOINT=https://askmeopenai.openai.azure.com/
AZURE_OPENAI_KEY=[VOTRE_AZURE_OPENAI_KEY]
AZURE_OPENAI_MODEL=Avanteam-QualitySaaS
AZURE_OPENAI_MODEL_NAME=gpt-4o
```

#### 4. **Claude AI**
```env
CLAUDE_API_KEY=[VOTRE_CLAUDE_API_KEY]
CLAUDE_MODEL=claude-3-7-sonnet-latest
CLAUDE_TEMPERATURE=0
```

#### 5. **Services Azure**
```env
# Azure Search (pour la recherche documentaire)
AZURE_SEARCH_SERVICE=askmesearchprod
AZURE_SEARCH_INDEX=idx-v-avanteam-qualitysaas-dev
AZURE_SEARCH_KEY=[VOTRE_AZURE_SEARCH_KEY]

# CosmosDB (pour l'historique des conversations)
AZURE_COSMOSDB_ACCOUNT=db-askme-avanteam-qualitysaas-dev-historique
AZURE_COSMOSDB_DATABASE=db_conversation_history
AZURE_COSMOSDB_ACCOUNT_KEY=[VOTRE_COSMOSDB_KEY]

# Azure Speech Services (pour les fonctionnalités vocales)
AZURE_SPEECH_KEY=[VOTRE_AZURE_SPEECH_KEY]
AZURE_SPEECH_REGION=francecentral
```

#### 6. **Fonctionnalités Vocales**
```env
VOICE_INPUT_ENABLED=true
WAKE_WORD_ENABLED=true
WAKE_WORD_PHRASES=Sarah,Richard,Patrick,Mérade
AZURE_SPEECH_VOICE_FR=fr-FR-HenriNeural
AZURE_SPEECH_VOICE_EN=en-US-GuyNeural
```

### Mapping .env → Kubernetes

#### ConfigMap (configuration publique)
```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: askme-config
data:
  DEBUG: "True"
  UI_TITLE: "Avanteam AskMe"
  LLM_PROVIDER: "AZURE_OPENAI"
  AVAILABLE_LLM_PROVIDERS: "AZURE_OPENAI,CLAUDE,OPENAI_DIRECT,MISTRAL,GEMINI"
  VOICE_INPUT_ENABLED: "true"
  WAKE_WORD_ENABLED: "true"
  AZURE_SPEECH_ENABLED: "true"
  IMAGE_MAX_SIZE_MB: "12.0"
```

#### Secret (configuration sensible)
```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: askme-secrets
stringData:
  # Clés API et mots de passe
  AZURE_OPENAI_KEY: "[VOTRE_AZURE_OPENAI_KEY]"
  CLAUDE_API_KEY: "[VOTRE_CLAUDE_API_KEY]"
  AZURE_SEARCH_KEY: "[VOTRE_AZURE_SEARCH_KEY]"
  AZURE_COSMOSDB_ACCOUNT_KEY: "[VOTRE_COSMOSDB_KEY]"
```

---

## 🐳 Déploiement d'une Nouvelle Application

### Prérequis Techniques

#### 1. **Outils Nécessaires**
```bash
# Installation des outils
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Vérification
docker --version
kubectl version --client
```

#### 2. **Configuration kubectl**
```bash
# Copier le fichier de configuration OVH
cp "/mnt/c/Users/Richard Garcia/Downloads/kubeconfig (1).yml" ~/.kube/config

# Tester la connexion
kubectl cluster-info

# Vérifier l'accès aux nodes
kubectl get nodes
```

#### 3. **Connexion au Registry Harbor**
```bash
# Connexion Docker
docker login 7wpjr0wh.c1.gra9.container-registry.ovh.net \
  --username [VOTRE_USERNAME_HARBOR] \
  --password [VOTRE_PASSWORD_HARBOR]

# Créer le secret Kubernetes pour Harbor
kubectl create secret docker-registry harbor-secret \
  --docker-server=7wpjr0wh.c1.gra9.container-registry.ovh.net \
  --docker-username=[VOTRE_USERNAME_HARBOR] \
  --docker-password=[VOTRE_PASSWORD_HARBOR] \
  --namespace=askme-app
```

### Procédure de Déploiement Complète

#### Étape 1 : Préparation du Projet

```bash
# 1. Cloner ou préparer votre projet
cd /votre/projet

# 2. Vérifier la structure des fichiers
ls -la
# Doit contenir : WebApp.Dockerfile, .env, k8s/*, frontend/, backend/

# 3. Créer le dossier k8s s'il n'existe pas
mkdir -p k8s
```

#### Étape 2 : Configuration des Manifestes Kubernetes

##### A. Namespace
```bash
# k8s/namespace.yaml
cat > k8s/namespace.yaml << 'EOF'
apiVersion: v1
kind: Namespace
metadata:
  name: votre-app
EOF
```

##### B. ConfigMap
```bash
# k8s/configmap.yaml - Adapter selon votre .env
cat > k8s/configmap.yaml << 'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: votre-app-config
  namespace: votre-app
data:
  DEBUG: "True"
  UI_TITLE: "Votre Application"
  # Ajouter toutes vos variables non-sensibles
EOF
```

##### C. Secret
```bash
# k8s/secret.yaml - Variables sensibles de votre .env
cat > k8s/secret.yaml << 'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: votre-app-secrets
  namespace: votre-app
stringData:
  # Ajouter toutes vos clés API et mots de passe
  API_KEY: "votre-clé-api"
  DB_PASSWORD: "mot-de-passe-db"
EOF
```

##### D. Deployment
```bash
# k8s/deployment.yaml
cat > k8s/deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: votre-app
  namespace: votre-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: votre-app
  template:
    metadata:
      labels:
        app: votre-app
    spec:
      containers:
      - name: votre-app
        image: 7wpjr0wh.c1.gra9.container-registry.ovh.net/votre-projet/votre-app:latest
        ports:
        - containerPort: 80
        env:
        # Référencer vos ConfigMap et Secrets
        - name: DEBUG
          valueFrom:
            configMapKeyRef:
              name: votre-app-config
              key: DEBUG
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
      imagePullSecrets:
      - name: harbor-secret
EOF
```

##### E. Service
```bash
# k8s/service.yaml
cat > k8s/service.yaml << 'EOF'
apiVersion: v1
kind: Service
metadata:
  name: votre-app-service
  namespace: votre-app
spec:
  selector:
    app: votre-app
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
EOF
```

##### F. Ingress
```bash
# k8s/ingress.yaml
cat > k8s/ingress.yaml << 'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: votre-app-ingress
  namespace: votre-app
  annotations:
    kubernetes.io/ingress.class: "nginx"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - votre-domaine.com
    secretName: votre-app-tls
  rules:
  - host: votre-domaine.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: votre-app-service
            port:
              number: 80
EOF
```

#### Étape 3 : Build et Push de l'Image Docker

```bash
# 1. Build de l'image Docker
docker build -f WebApp.Dockerfile \
  -t 7wpjr0wh.c1.gra9.container-registry.ovh.net/votre-projet/votre-app:latest .

# 2. Push vers Harbor
docker push 7wpjr0wh.c1.gra9.container-registry.ovh.net/votre-projet/votre-app:latest

# 3. Vérification sur Harbor
# Aller sur https://7wpjr0wh.c1.gra9.container-registry.ovh.net/
# Vérifier que votre image est bien présente
```

#### Étape 4 : Déploiement sur Kubernetes

```bash
# 1. Appliquer les manifestes dans l'ordre
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 2. Vérifier le déploiement
kubectl get all -n votre-app

# 3. Attendre que les pods soient prêts
kubectl wait --for=condition=available --timeout=300s deployment/votre-app -n votre-app

# 4. Vérifier les logs
kubectl logs -f deployment/votre-app -n votre-app
```

#### Étape 5 : Configuration DNS et SSL

```bash
# 1. Récupérer l'IP du LoadBalancer
kubectl get ingress votre-app-ingress -n votre-app

# 2. Configurer l'enregistrement DNS
# Créer un enregistrement A : votre-domaine.com → IP_LOADBALANCER

# 3. Vérifier le certificat SSL (peut prendre quelques minutes)
kubectl get certificates -n votre-app
kubectl describe certificate votre-app-tls -n votre-app
```

### Script d'Automatisation

#### Script de Déploiement Complet

```bash
#!/bin/bash
# deploy-new-app.sh

set -e

# Configuration
REGISTRY_URL="7wpjr0wh.c1.gra9.container-registry.ovh.net"
PROJECT_NAME="${1:-votre-projet}"
APP_NAME="${2:-votre-app}"
DOMAIN="${3:-votre-domaine.com}"
NAMESPACE="${4:-$APP_NAME}"

echo "🚀 Déploiement de $APP_NAME sur Kubernetes OVH"

# Vérifications préalables
echo "📋 Vérification des prérequis..."
command -v docker >/dev/null 2>&1 || { echo "Docker requis"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl requis"; exit 1; }
kubectl cluster-info >/dev/null 2>&1 || { echo "Cluster non accessible"; exit 1; }

# Build et push de l'image
echo "🐳 Build de l'image Docker..."
docker build -f WebApp.Dockerfile -t $REGISTRY_URL/$PROJECT_NAME/$APP_NAME:latest .

echo "📤 Push vers Harbor..."
docker push $REGISTRY_URL/$PROJECT_NAME/$APP_NAME:latest

# Déploiement Kubernetes
echo "☸️ Déploiement sur Kubernetes..."
kubectl apply -f k8s/

# Attente du déploiement
echo "⏳ Attente de la disponibilité..."
kubectl wait --for=condition=available --timeout=300s deployment/$APP_NAME -n $NAMESPACE

# Affichage du statut
echo "✅ Déploiement terminé!"
kubectl get all -n $NAMESPACE
kubectl get ingress -n $NAMESPACE

echo "🌐 URL d'accès : https://$DOMAIN"
echo "📊 Logs : kubectl logs -f deployment/$APP_NAME -n $NAMESPACE"
```

#### Utilisation du Script
```bash
# Rendre le script exécutable
chmod +x deploy-new-app.sh

# Lancer le déploiement
./deploy-new-app.sh mon-projet mon-app mon-domaine.com
```

---

## 🔄 Mise à Jour d'une Application Existante

### Types de Mises à Jour

#### 1. **Mise à Jour du Code (Rolling Update)**
```bash
# 1. Modifier votre code source
# 2. Build nouvelle version
docker build -f WebApp.Dockerfile \
  -t 7wpjr0wh.c1.gra9.container-registry.ovh.net/askme/askme-app:v1.2.0 .

# 3. Push vers Harbor
docker push 7wpjr0wh.c1.gra9.container-registry.ovh.net/askme/askme-app:v1.2.0

# 4. Mise à jour du deployment
kubectl set image deployment/askme-app \
  askme-app=7wpjr0wh.c1.gra9.container-registry.ovh.net/askme/askme-app:v1.2.0 \
  -n askme-app

# 5. Suivre le déploiement
kubectl rollout status deployment/askme-app -n askme-app
```

#### 2. **Mise à Jour de Configuration**
```bash
# 1. Modifier k8s/configmap.yaml ou k8s/secret.yaml
# 2. Appliquer les changements
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 3. Redémarrer les pods pour prendre en compte la config
kubectl rollout restart deployment/askme-app -n askme-app
```

#### 3. **Mise à Jour de l'Infrastructure**
```bash
# Modifier k8s/deployment.yaml (ex: augmenter les ressources)
# Appliquer les changements
kubectl apply -f k8s/deployment.yaml
```

### Stratégies de Déploiement

#### Rolling Update (Par Défaut)
```yaml
# Dans deployment.yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # 1 pod supplémentaire pendant l'update
      maxUnavailable: 0  # Aucun pod indisponible
```

**Avantages** :
- ✅ Zéro downtime
- ✅ Rollback automatique en cas d'erreur
- ✅ Progressif et sécurisé

#### Blue-Green Deployment
```bash
# 1. Déployer la nouvelle version avec un nom différent
sed 's/askme-app/askme-app-green/g' k8s/deployment.yaml > k8s/deployment-green.yaml
kubectl apply -f k8s/deployment-green.yaml

# 2. Tester la nouvelle version
kubectl port-forward deployment/askme-app-green 8080:80 -n askme-app

# 3. Basculer le service vers la nouvelle version
kubectl patch service askme-service -n askme-app \
  -p '{"spec":{"selector":{"version":"green"}}}'

# 4. Supprimer l'ancienne version
kubectl delete deployment askme-app -n askme-app
```

### Procédures de Rollback

#### Rollback Automatique
```bash
# Voir l'historique des déploiements
kubectl rollout history deployment/askme-app -n askme-app

# Rollback vers la version précédente
kubectl rollout undo deployment/askme-app -n askme-app

# Rollback vers une version spécifique
kubectl rollout undo deployment/askme-app --to-revision=2 -n askme-app
```

#### Rollback Manuel
```bash
# Revenir à une image précédente
kubectl set image deployment/askme-app \
  askme-app=7wpjr0wh.c1.gra9.container-registry.ovh.net/askme/askme-app:v1.1.0 \
  -n askme-app
```

### Script de Mise à Jour Automatisé

```bash
#!/bin/bash
# update-app.sh

set -e

APP_NAME="${1:-askme-app}"
NAMESPACE="${2:-askme-app}"
NEW_VERSION="${3:-latest}"
REGISTRY_URL="7wpjr0wh.c1.gra9.container-registry.ovh.net"

echo "🔄 Mise à jour de $APP_NAME vers $NEW_VERSION"

# Backup de l'état actuel
echo "💾 Sauvegarde de l'état actuel..."
kubectl get deployment $APP_NAME -n $NAMESPACE -o yaml > backup-$APP_NAME-$(date +%Y%m%d-%H%M%S).yaml

# Build et push
echo "🐳 Build de la nouvelle version..."
docker build -f WebApp.Dockerfile -t $REGISTRY_URL/askme/$APP_NAME:$NEW_VERSION .
docker push $REGISTRY_URL/askme/$APP_NAME:$NEW_VERSION

# Mise à jour
echo "🚀 Déploiement de la mise à jour..."
kubectl set image deployment/$APP_NAME \
  $APP_NAME=$REGISTRY_URL/askme/$APP_NAME:$NEW_VERSION \
  -n $NAMESPACE

# Attente et vérification
echo "⏳ Attente du déploiement..."
kubectl rollout status deployment/$APP_NAME -n $NAMESPACE --timeout=300s

# Vérification de santé
echo "🔍 Vérification de santé..."
sleep 30
if kubectl get pods -n $NAMESPACE | grep $APP_NAME | grep -q Running; then
    echo "✅ Mise à jour réussie!"
    kubectl get pods -n $NAMESPACE
else
    echo "❌ Problème détecté, rollback..."
    kubectl rollout undo deployment/$APP_NAME -n $NAMESPACE
    exit 1
fi
```

#### Utilisation
```bash
chmod +x update-app.sh
./update-app.sh askme-app askme-app v1.3.0
```

---

## 🔒 Gestion SSL avec Let's Encrypt

### Architecture cert-manager

```
┌─────────────────────────────────────────────────────────────┐
│                    CERT-MANAGER                             │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   ISSUER     │    │ CERTIFICATE  │    │   CHALLENGE  │  │
│  │              │    │              │    │              │  │
│  │ Let's Encrypt│────│ SSL Request  │────│ HTTP-01      │  │
│  │ Production   │    │              │    │ Validation   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                      │                            │
                      ▼                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 KUBERNETES SECRET                           │
│            (Certificat SSL + Clé Privée)                   │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  NGINX INGRESS                              │
│            (Terminaison SSL + Routage)                     │
└─────────────────────────────────────────────────────────────┘
```

### Installation cert-manager

#### Méthode Helm (Recommandée)
```bash
# 1. Ajouter le repository Helm
helm repo add jetstack https://charts.jetstack.io
helm repo update

# 2. Créer le namespace
kubectl create namespace cert-manager

# 3. Installer cert-manager
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --version v1.13.0 \
  --set installCRDs=true

# 4. Vérifier l'installation
kubectl get pods -n cert-manager
```

#### Méthode kubectl (Alternative)
```bash
# Installation directe via kubectl
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Vérification
kubectl get pods -n cert-manager
```

### Configuration du ClusterIssuer

#### Production Let's Encrypt
```yaml
# k8s/letsencrypt-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    # Email pour les notifications Let's Encrypt
    email: admin@avanteam-online.com
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-prod
    # Challenge HTTP-01 via Ingress
    solvers:
    - http01:
        ingress:
          class: nginx
          podTemplate:
            spec:
              nodeSelector:
                "kubernetes.io/os": linux
```

#### Staging Let's Encrypt (Tests)
```yaml
# k8s/letsencrypt-staging.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    email: admin@avanteam-online.com
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-staging
    solvers:
    - http01:
        ingress:
          class: nginx
```

### Configuration de l'Ingress pour SSL

#### Ingress avec SSL Automatique
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: askme-ingress
  namespace: askme-app
  annotations:
    kubernetes.io/ingress.class: "nginx"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    # Annotation cert-manager pour SSL automatique
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  # Configuration TLS
  tls:
  - hosts:
    - askme.avanteam-online.com
    secretName: askme-tls  # Secret généré automatiquement
  rules:
  - host: askme.avanteam-online.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: askme-service
            port:
              number: 80
```

### Processus d'Obtention du Certificat

#### 1. **Déploiement des Manifestes**
```bash
# Appliquer le ClusterIssuer
kubectl apply -f k8s/letsencrypt-issuer.yaml

# Appliquer l'Ingress
kubectl apply -f k8s/ingress.yaml
```

#### 2. **Suivi du Processus**
```bash
# Vérifier la création du certificat
kubectl get certificates -n askme-app

# Voir les détails
kubectl describe certificate askme-tls -n askme-app

# Suivre les challenges ACME
kubectl get challenges -n askme-app
kubectl describe challenge [challenge-name] -n askme-app
```

#### 3. **Vérification Finale**
```bash
# Test HTTPS
curl -I https://askme.avanteam-online.com

# Vérification du certificat
echo | openssl s_client -servername askme.avanteam-online.com \
  -connect askme.avanteam-online.com:443 2>/dev/null | \
  openssl x509 -noout -dates -issuer
```

### Renouvellement Automatique

#### Configuration du Renouvellement
cert-manager gère automatiquement le renouvellement :
- **Contrôle** : Tous les jours
- **Renouvellement** : 30 jours avant expiration
- **Notification** : Email en cas de problème

#### Monitoring du Renouvellement
```bash
# Vérifier l'état des certificats
kubectl get certificates --all-namespaces

# Logs de cert-manager
kubectl logs -n cert-manager deployment/cert-manager

# Forcer un renouvellement (test)
kubectl annotate certificate askme-tls -n askme-app \
  cert-manager.io/issue-temporary-certificate="true"
```

### Gestion Multi-Domaines

#### Certificat Wildcard
```yaml
# Pour *.avanteam-online.com
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-tls
  namespace: askme-app
spec:
  secretName: wildcard-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - "*.avanteam-online.com"
  - "avanteam-online.com"
```

#### Certificat Multi-Domaines
```yaml
# Ingress avec plusieurs domaines
spec:
  tls:
  - hosts:
    - app1.avanteam-online.com
    - app2.avanteam-online.com
    secretName: multi-domain-tls
  rules:
  - host: app1.avanteam-online.com
    # ...
  - host: app2.avanteam-online.com
    # ...
```

---

## 🔍 Surveillance et Troubleshooting

### Commandes de Diagnostic Essentielles

#### État Général du Cluster
```bash
# Vue d'ensemble du cluster
kubectl cluster-info

# État des nodes
kubectl get nodes -o wide

# Ressources globales
kubectl top nodes
kubectl top pods --all-namespaces
```

#### Diagnostic d'Application
```bash
# État des ressources dans le namespace
kubectl get all -n askme-app

# Détails des pods
kubectl describe pods -n askme-app

# Logs des applications
kubectl logs -f deployment/askme-app -n askme-app

# Logs des containers précédents (en cas de crash)
kubectl logs deployment/askme-app --previous -n askme-app
```

#### Diagnostic Réseau
```bash
# État des services
kubectl get svc -n askme-app -o wide

# État de l'Ingress
kubectl get ingress -n askme-app
kubectl describe ingress askme-ingress -n askme-app

# Test de connectivité interne
kubectl run -it --rm debug --image=busybox --restart=Never -- sh
# Puis dans le container :
# nslookup askme-service.askme-app.svc.cluster.local
# wget -O- http://askme-service.askme-app.svc.cluster.local
```

### Problèmes Fréquents et Solutions

#### 1. **ImagePullBackOff**
```
Symptôme : Les pods ne démarrent pas
Erreur : "ImagePullBackOff" ou "ErrImagePull"
```

**Diagnostic :**
```bash
kubectl describe pod [pod-name] -n askme-app
```

**Solutions :**
```bash
# 1. Vérifier l'accès au registry
docker login 7wpjr0wh.c1.gra9.container-registry.ovh.net

# 2. Vérifier le secret Harbor
kubectl get secret harbor-secret -n askme-app
kubectl describe secret harbor-secret -n askme-app

# 3. Re-créer le secret si nécessaire
kubectl delete secret harbor-secret -n askme-app
kubectl create secret docker-registry harbor-secret \
  --docker-server=7wpjr0wh.c1.gra9.container-registry.ovh.net \
  --docker-username=[VOTRE_USERNAME_HARBOR] \
  --docker-password=[VOTRE_PASSWORD_HARBOR] \
  --namespace=askme-app

# 4. Vérifier l'image dans Harbor
# Aller sur https://7wpjr0wh.c1.gra9.container-registry.ovh.net/
```

#### 2. **CrashLoopBackOff**
```
Symptôme : Les pods redémarrent en boucle
```

**Diagnostic :**
```bash
# Voir les logs du container qui crash
kubectl logs [pod-name] -n askme-app

# Voir les événements
kubectl describe pod [pod-name] -n askme-app

# Examiner la configuration
kubectl get deployment askme-app -n askme-app -o yaml
```

**Solutions courantes :**
```bash
# 1. Vérifier les variables d'environnement manquantes
kubectl describe configmap askme-config -n askme-app
kubectl describe secret askme-secrets -n askme-app

# 2. Vérifier les ressources (CPU/RAM)
kubectl top pods -n askme-app

# 3. Augmenter les limites si nécessaire
kubectl patch deployment askme-app -n askme-app -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"askme-app","resources":{"limits":{"memory":"2Gi","cpu":"1"}}}]}}}}'
```

#### 3. **Service Unavailable (503)**
```
Symptôme : L'application répond 503 via l'Ingress
```

**Diagnostic :**
```bash
# Vérifier l'état des pods
kubectl get pods -n askme-app

# Vérifier le service
kubectl describe svc askme-service -n askme-app

# Tester la connectivité directe
kubectl port-forward deployment/askme-app 8080:80 -n askme-app
# Puis : curl http://localhost:8080
```

**Solutions :**
```bash
# 1. Vérifier les endpoints du service
kubectl get endpoints askme-service -n askme-app

# 2. Vérifier les labels
kubectl get pods -n askme-app --show-labels
kubectl get svc askme-service -n askme-app -o yaml

# 3. Corriger les sélecteurs si nécessaire
kubectl patch svc askme-service -n askme-app -p \
  '{"spec":{"selector":{"app":"askme-app"}}}'
```

#### 4. **Problèmes SSL/Certificats**
```
Symptôme : Certificats non générés ou expirés
```

**Diagnostic :**
```bash
# État des certificats
kubectl get certificates -n askme-app
kubectl describe certificate askme-tls -n askme-app

# État des challenges
kubectl get challenges -n askme-app
kubectl describe challenge [challenge-name] -n askme-app

# Logs cert-manager
kubectl logs -n cert-manager deployment/cert-manager
```

**Solutions :**
```bash
# 1. Vérifier le ClusterIssuer
kubectl get clusterissuer letsencrypt-prod
kubectl describe clusterissuer letsencrypt-prod

# 2. Forcer un nouveau certificat
kubectl delete certificate askme-tls -n askme-app
kubectl apply -f k8s/ingress.yaml

# 3. Vérifier la résolution DNS
nslookup askme.avanteam-online.com

# 4. Test manuel du challenge
curl http://askme.avanteam-online.com/.well-known/acme-challenge/test
```

### Scripts de Monitoring

#### Script de Santé Globale
```bash
#!/bin/bash
# health-check.sh

NAMESPACE="${1:-askme-app}"

echo "🏥 Vérification de santé pour $NAMESPACE"
echo "=====================================\n"

# État des pods
echo "📦 État des Pods :"
kubectl get pods -n $NAMESPACE

# État des services
echo "\n🌐 État des Services :"
kubectl get svc -n $NAMESPACE

# État de l'Ingress
echo "\n🚪 État de l'Ingress :"
kubectl get ingress -n $NAMESPACE

# État des certificats
echo "\n🔒 État des Certificats :"
kubectl get certificates -n $NAMESPACE

# Utilisation des ressources
echo "\n📊 Utilisation des Ressources :"
kubectl top pods -n $NAMESPACE 2>/dev/null || echo "Metrics server non disponible"

# Test HTTP
echo "\n🌍 Test de Connectivité :"
DOMAIN=$(kubectl get ingress -n $NAMESPACE -o jsonpath='{.items[0].spec.rules[0].host}' 2>/dev/null)
if [ ! -z "$DOMAIN" ]; then
    curl -s -o /dev/null -w "HTTP Status: %{http_code}\nTempo de réponse: %{time_total}s\n" https://$DOMAIN || echo "Échec de connexion"
else
    echo "Aucun domaine configuré"
fi
```

#### Script de Logs Centralisés
```bash
#!/bin/bash
# collect-logs.sh

NAMESPACE="${1:-askme-app}"
OUTPUT_DIR="logs-$(date +%Y%m%d-%H%M%S)"

mkdir -p $OUTPUT_DIR

echo "📝 Collecte des logs pour $NAMESPACE dans $OUTPUT_DIR"

# Logs des pods
kubectl get pods -n $NAMESPACE --no-headers | while read pod rest; do
    echo "Collecte des logs de $pod..."
    kubectl logs $pod -n $NAMESPACE > "$OUTPUT_DIR/$pod.log" 2>&1
done

# Descriptions des ressources
kubectl describe all -n $NAMESPACE > "$OUTPUT_DIR/describe-all.txt"

# Configuration actuelle
kubectl get all -n $NAMESPACE -o yaml > "$OUTPUT_DIR/current-config.yaml"

# Événements récents
kubectl get events -n $NAMESPACE > "$OUTPUT_DIR/events.txt"

echo "✅ Logs collectés dans $OUTPUT_DIR"
```

### Alerting et Monitoring Avancé

#### Prometheus + Grafana (Optionnel)
```bash
# Installation via Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Installation Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace

# Accès Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# User: admin / Password: prom-operator
```

#### Métriques Kubernetes Natives
```bash
# Installation du metrics server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Vérification
kubectl top nodes
kubectl top pods --all-namespaces
```

---

## 📚 Ressources et Bonnes Pratiques

### Bonnes Pratiques de Déploiement

#### 1. **Gestion des Versions**
```bash
# Toujours utiliser des tags spécifiques
# ❌ Mauvais
image: askme-app:latest

# ✅ Bon
image: askme-app:v1.2.3
```

#### 2. **Séparation des Environnements**
```yaml
# Utiliser des namespaces séparés
# dev, staging, production
apiVersion: v1
kind: Namespace
metadata:
  name: askme-prod
  labels:
    environment: production
```

#### 3. **Limitation des Ressources**
```yaml
# Toujours définir des limites
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

#### 4. **Secrets et Configuration**
```bash
# ❌ Ne jamais mettre de secrets dans le code
# ✅ Utiliser les Secrets Kubernetes
# ✅ Utiliser des outils comme Sealed Secrets pour prod
```

#### 5. **Surveillance et Logs**
```yaml
# Configurer des health checks
livenessProbe:
  httpGet:
    path: /health
    port: 80
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Architecture de Production

#### Haute Disponibilité
```yaml
# Multi-réplicas avec anti-affinité
spec:
  replicas: 3
  template:
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - askme-app
              topologyKey: kubernetes.io/hostname
```

#### Stratégie de Sauvegarde
```bash
# Sauvegarde des configurations
kubectl get all -n askme-app -o yaml > backup-$(date +%Y%m%d).yaml

# Sauvegarde des secrets (chiffrée)
kubectl get secrets -n askme-app -o yaml | gpg -c > secrets-backup-$(date +%Y%m%d).yaml.gpg

# Script de sauvegarde automatique
#!/bin/bash
# backup-k8s.sh
NAMESPACE="${1:-askme-app}"
BACKUP_DIR="/backups/k8s"
DATE=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR/$DATE"

kubectl get all -n $NAMESPACE -o yaml > "$BACKUP_DIR/$DATE/resources.yaml"
kubectl get configmap -n $NAMESPACE -o yaml > "$BACKUP_DIR/$DATE/configmaps.yaml"
kubectl get secrets -n $NAMESPACE -o yaml > "$BACKUP_DIR/$DATE/secrets.yaml"

echo "Sauvegarde créée : $BACKUP_DIR/$DATE"
```

### Liens et Documentation

#### Documentation Officielle
- **Kubernetes** : https://kubernetes.io/docs/
- **Docker** : https://docs.docker.com/
- **cert-manager** : https://cert-manager.io/docs/
- **NGINX Ingress** : https://kubernetes.github.io/ingress-nginx/

#### Outils Utiles
- **k9s** : Interface terminal pour Kubernetes
- **kubectl-neat** : Nettoyage des manifests YAML
- **kustomize** : Gestion des configurations
- **Helm** : Gestionnaire de packages Kubernetes

#### Formation et Certification
- **CKAD** : Certified Kubernetes Application Developer
- **CKA** : Certified Kubernetes Administrator
- **Kubernetes Academy** : Formation gratuite Linux Foundation

---

## 🎯 Résumé Exécutif

### Ce que vous avez maintenant

✅ **Infrastructure Kubernetes OVH** complètement opérationnelle  
✅ **Registry Harbor privé** pour vos images Docker  
✅ **SSL automatique** avec Let's Encrypt et cert-manager  
✅ **Monitoring et surveillance** avec des outils intégrés  
✅ **Scripts d'automatisation** pour déploiements et mises à jour  
✅ **Documentation complète** pour votre équipe  

### Prochaines étapes recommandées

1. **Formation de l'équipe** sur les concepts Kubernetes
2. **Mise en place d'un pipeline CI/CD** (GitLab CI, GitHub Actions)
3. **Monitoring avancé** avec Prometheus/Grafana
4. **Tests automatisés** d'intégration et de performance
5. **Plan de disaster recovery** et procédures de restauration

### Contact et Support

Pour toute question ou assistance :
- 📧 Support OVH Kubernetes
- 📚 Documentation projet dans `/k8s/README.md`
- 🛠️ Scripts d'automatisation dans `/k8s/deploy.sh`

---

**🎉 Félicitations ! Votre infrastructure Kubernetes est prête pour la production !**