# 🚀 AskMe Multi-Client Helm Deployment

Ce guide vous explique comment utiliser la nouvelle architecture Helm multi-client pour déployer et gérer plusieurs instances d'AskMe sur votre infrastructure OVH Kubernetes.

## 📁 Structure du Projet

```
askme-app-aoai/
├── helm-chart/                    # Chart Helm principal
│   ├── Chart.yaml
│   ├── values.yaml               # Valeurs par défaut
│   └── templates/                # Templates Kubernetes
├── deployments/
│   └── clients/                  # Configurations spécifiques clients
│       ├── askme.avanteam-online.com/
│       │   └── values.yaml       # Config client principal
│       └── askme-qsaas.avanteam-online.com/
│           └── values.yaml       # Config client QSaaS
├── deploy-helm-client.sh         # Script déploiement Linux/WSL
├── deploy-helm-client.ps1        # Script déploiement Windows
└── helm-status-all.sh           # Monitoring tous clients
```

## 🛠️ Prérequis

### Installation des Outils
```bash
# Helm (requis)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# yq (pour scripts bash)
sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
sudo chmod +x /usr/local/bin/yq

# PowerShell-Yaml (pour scripts PowerShell)
Install-Module powershell-yaml -Force
```

### Configuration kubectl
Assurez-vous que kubectl est configuré pour votre cluster OVH :
```bash
kubectl cluster-info
kubectl get nodes
```

## 🎯 Déploiement des Clients

### 1. Configurer les Secrets Clients

Avant le déploiement, vous devez configurer les secrets spécifiques à chaque client dans les fichiers `values.yaml`.

#### Client Principal (askme.avanteam-online.com)
```bash
# Éditer le fichier de configuration
nano deployments/clients/askme.avanteam-online.com/values.yaml

# Mettre à jour les secrets avec vos vraies valeurs :
# - AZURE_OPENAI_ENDPOINT
# - AZURE_OPENAI_KEY  
# - AZURE_SEARCH_SERVICE
# - etc.
```

#### Client QSaaS (askme-qsaas.avanteam-online.com)
```bash
# Éditer le fichier de configuration
nano deployments/clients/askme-qsaas.avanteam-online.com/values.yaml

# Configurer les secrets spécifiques au client QSaaS
```

### 2. Déployer les Clients

#### Linux/WSL
```bash
# Déployer le client principal
./deploy-helm-client.sh askme.avanteam-online.com deploy

# Déployer le client QSaaS
./deploy-helm-client.sh askme-qsaas.avanteam-online.com deploy
```

#### Windows PowerShell
```powershell
# Déployer le client principal
.\deploy-helm-client.ps1 askme.avanteam-online.com deploy

# Déployer le client QSaaS  
.\deploy-helm-client.ps1 askme-qsaas.avanteam-online.com deploy
```

## 🔄 Gestion des Déploiements

### Commandes Disponibles

#### Déploiement et Mise à Jour
```bash
# Déploiement initial
./deploy-helm-client.sh <client-domain> deploy

# Mise à jour vers une nouvelle version
./deploy-helm-client.sh <client-domain> upgrade v1.2.1

# Mise à jour avec version spécifique
./deploy-helm-client.sh <client-domain> upgrade v1.2.0-client-specific
```

#### Monitoring et Status
```bash
# Status d'un client spécifique
./deploy-helm-client.sh <client-domain> status

# Status de tous les clients
./helm-status-all.sh

# Historique des déploiements
./deploy-helm-client.sh <client-domain> history
```

#### Rollback et Maintenance
```bash
# Rollback vers version précédente
./deploy-helm-client.sh <client-domain> rollback

# Rollback vers revision spécifique
./deploy-helm-client.sh <client-domain> rollback 3

# Désinstaller un client
./deploy-helm-client.sh <client-domain> uninstall
```

## 🌍 URLs d'Accès

Après déploiement réussi, vos clients seront accessibles sur :

- **Client Principal** : https://askme.avanteam-online.com
- **Client QSaaS** : https://askme-qsaas.avanteam-online.com

## 📊 Monitoring Multi-Client

### Dashboard Global
```bash
# Voir le status de tous les clients
./helm-status-all.sh
```

Cet affichage vous montre :
- ✅ Status de chaque client (deployed/not deployed)
- 🏢 Namespaces et releases Helm
- 🌐 URLs d'accès
- 📈 Versions déployées
- ⏱️ Dates de dernière mise à jour

### Monitoring Kubernetes Natif
```bash
# Voir tous les namespaces AskMe
kubectl get namespaces | grep askme

# Voir tous les pods clients
kubectl get pods --all-namespaces | grep askme

# Voir tous les ingress
kubectl get ingress --all-namespaces | grep askme
```

## 🔧 Gestion des Versions

### Tagging des Versions
```bash
# Créer une version client-spécifique
git tag -a v1.2.0-askme-client -m "Version spéciale client principal"
git push origin v1.2.0-askme-client

# Créer une version QSaaS
git tag -a v1.2.0-qsaas -m "Version adaptée QSaaS" 
git push origin v1.2.0-qsaas
```

### Déploiement de Versions Spécifiques
```bash
# Déployer version spécifique sur client
./deploy-helm-client.sh askme.avanteam-online.com upgrade v1.2.0-askme-client

# Déployer version QSaaS
./deploy-helm-client.sh askme-qsaas.avanteam-online.com upgrade v1.2.0-qsaas
```

## 🆘 Dépannage

### Problèmes Courants

#### 1. Release Already Exists
```bash
# Si vous avez une erreur "release already exists"
helm uninstall askme-<client-name> -n <namespace>
# Puis redéployer
./deploy-helm-client.sh <client-domain> deploy
```

#### 2. Namespace Stuck in Terminating
```bash
# Forcer la suppression d'un namespace bloqué
kubectl patch namespace <namespace> -p '{"spec":{"finalizers":null}}'
```

#### 3. Secrets Non Trouvés
```bash
# Vérifier les secrets dans le namespace
kubectl get secrets -n <namespace>

# Debug du deployment
kubectl describe deployment askme-<client> -n <namespace>
```

#### 4. Problèmes DNS/Ingress
```bash
# Vérifier les ingress
kubectl get ingress -n <namespace>
kubectl describe ingress askme-<client> -n <namespace>

# Vérifier les certificats SSL
kubectl get certificates -n <namespace>
```

### Logs de Debug
```bash
# Logs des pods
kubectl logs -f deployment/askme-<client> -n <namespace>

# Logs des événements
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Status détaillé Helm
helm status askme-<client> -n <namespace>
```

## 🚀 Prochaines Étapes

### Ajouter un Nouveau Client
1. Créer un nouveau répertoire : `deployments/clients/nouveau-client.com/`
2. Copier et adapter un fichier `values.yaml` existant
3. Configurer les secrets spécifiques au client
4. Déployer : `./deploy-helm-client.sh nouveau-client.com deploy`

### Intégration CI/CD
Cette architecture est prête pour l'intégration avec :
- GitHub Actions (workflows automatisés)
- ArgoCD (GitOps)
- Jenkins (pipelines personnalisés)

### Scaling Avancé
- Ajout de HPA (Horizontal Pod Autoscaler)
- Configuration de monitoring Prometheus/Grafana
- Intégration avec ArgoCD pour GitOps complet

---

## 📞 Support

Pour toute question ou problème :
1. Vérifiez d'abord la section Dépannage
2. Utilisez `./helm-status-all.sh` pour diagnostiquer
3. Consultez les logs Kubernetes avec `kubectl logs`

**Commandes utiles de diagnostic :**
```bash
# Vérification complète d'un client
kubectl get all -n <namespace>
helm status askme-<client> -n <namespace>
kubectl describe ingress askme-<client> -n <namespace>
```