# 🚀 Configuration Kubernetes AskMe

Ce dossier contient tous les manifestes Kubernetes nécessaires pour déployer l'application AskMe sur OVH Kubernetes.

## 📁 Fichiers de Configuration

### Configuration de Base
- **`namespace.yaml`** : Namespace isolé pour l'application
- **`configmap.yaml`** : Variables d'environnement publiques
- **`secret.yaml.sample`** : Template pour les variables sensibles
- **`deployment.yaml`** : Déploiement de l'application
- **`service.yaml`** : Service interne Kubernetes
- **`ingress.yaml`** : Exposition HTTP/HTTPS

### SSL et Sécurité
- **`letsencrypt-issuer.yaml`** : Générateur de certificats SSL automatiques

### Outils
- **`deploy.sh`** : Script d'automatisation du déploiement
- **`kustomization.yaml`** : Configuration Kustomize

## ⚙️ Configuration des Secrets

### 1. Créer le fichier secret.yaml réel
```bash
# Copier le template
cp secret.yaml.sample secret.yaml

# Éditer avec vos vraies clés API
nano secret.yaml
```

### 2. Variables à configurer
Remplacez les placeholders suivants dans `secret.yaml` :

```yaml
# Clés API principales
AZURE_OPENAI_KEY: "YOUR_AZURE_OPENAI_KEY_HERE"
CLAUDE_API_KEY: "YOUR_CLAUDE_API_KEY_HERE"
AZURE_SEARCH_KEY: "YOUR_AZURE_SEARCH_KEY_HERE"
AZURE_COSMOSDB_ACCOUNT_KEY: "YOUR_COSMOSDB_KEY_HERE"
AZURE_SPEECH_KEY: "YOUR_AZURE_SPEECH_KEY_HERE"

# Autres providers (optionnels)
OPENAI_DIRECT_API_KEY: "YOUR_OPENAI_API_KEY_HERE"
MISTRAL_API_KEY: "YOUR_MISTRAL_API_KEY_HERE"
GEMINI_API_KEY: "YOUR_GEMINI_API_KEY_HERE"
```

## 🚀 Déploiement

### Déploiement Rapide
```bash
# Avec le script automatisé
./deploy.sh

# Ou manuellement
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
```

### Vérification
```bash
# État des pods
kubectl get pods -n askme-app

# État des services
kubectl get svc -n askme-app

# État de l'ingress
kubectl get ingress -n askme-app

# Logs de l'application
kubectl logs -f deployment/askme-app -n askme-app
```

## 🔒 Sécurité

⚠️ **IMPORTANT** : Le fichier `secret.yaml` contient vos clés API réelles et est exclu du versioning Git par le `.gitignore`.

- ✅ `secret.yaml.sample` : Template versioned (sans secrets)
- ❌ `secret.yaml` : Fichier local avec vraies clés (non-versioned)

## 📚 Documentation Complète

Consultez `DOCUMENTATION_DEPLOYMENT_KUBERNETES_OVH.md` pour un guide complet de déploiement et maintenance.