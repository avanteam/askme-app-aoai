# 🚀 QuickStart - AskMe Rancher Multi-Client

Guide de démarrage rapide pour déployer AskMe avec Rancher OVH en mode hybride (kubectl + UI manuelle).

## ✅ Prérequis Installés

- ✅ **Rancher CLI** : `rancher` (local)
- ✅ **kubectl** : Configuré avec votre cluster OVH
- ✅ **Helm** : Pour déploiement des charts
- ✅ **yq** : Pour parsing YAML (local)
- ✅ **jq** : Pour parsing JSON (local)

## 🎯 Déploiement en 3 Étapes

### 1. Setup Automatique

```bash
# Client principal
./deploy-rancher-client.sh askme.avanteam-online.com setup

# Client QSaaS  
./deploy-rancher-client.sh askme-qsaas.avanteam-online.com setup
```

**Résultat :**
- ✅ Namespace créé avec labels Rancher
- ✅ Annotations Rancher appliquées
- ✅ Fichier `rancher-values.yaml` généré
- ✅ Instructions UI affichées

### 2. Création Projets Rancher UI

**Interface:** https://jg8s67.9r1m.rancher.ovh.net

**Pour chaque client, créer le projet :**

#### Client Principal
```
Cluster: avanteam-mks-cluster → Projects/Namespaces → Create Project
├── Nom: askme-askme
├── Description: Projet AskMe pour askme.avanteam-online.com
├── CPU Limit: 2000m
├── Memory Limit: 4Gi
├── Storage: 10Gi
└── Namespace: askme-app
```

#### Client QSaaS
```
Cluster: avanteam-mks-cluster → Projects/Namespaces → Create Project
├── Nom: askme-qsaas
├── Description: Projet AskMe pour askme-qsaas.avanteam-online.com
├── CPU Limit: 1000m
├── Memory Limit: 2Gi
├── Storage: 5Gi
└── Namespace: askme-qsaas
```

### 3. Déploiement Applications

```bash
# Client principal
./deploy-rancher-client.sh askme.avanteam-online.com deploy

# Client QSaaS
./deploy-rancher-client.sh askme-qsaas.avanteam-online.com deploy
```

**Résultat :**
- ✅ Applications déployées avec Helm
- ✅ Templates Rancher activés
- ✅ Labels automatiques sur toutes les ressources
- ✅ Intégration complète dans Rancher UI

## 🔧 Commandes Utiles

### Gestion Applications

```bash
# Status détaillé
./deploy-rancher-client.sh askme.avanteam-online.com status

# Mise à jour version
./deploy-rancher-client.sh askme.avanteam-online.com upgrade v1.2.0

# Rollback
./deploy-rancher-client.sh askme.avanteam-online.com rollback

# Désinstallation complète
./deploy-rancher-client.sh askme.avanteam-online.com uninstall
```

### Vérifications kubectl

```bash
# Namespaces avec labels Rancher
kubectl get namespaces --show-labels | grep askme

# Pods dans les projets
kubectl get pods -n askme-app --show-labels
kubectl get pods -n askme-qsaas --show-labels

# Resources quotas
kubectl describe resourcequota -n askme-app
```

### Monitoring Rancher

**Interface :** https://jg8s67.9r1m.rancher.ovh.net
- **Dashboard** → Vue globale par projet
- **Workloads** → Applications par projet
- **Resources** → Utilisation CPU/RAM/Storage
- **Monitoring** → Grafana intégré

## 🌐 URLs d'Accès

- **Client Principal** : https://askme.avanteam-online.com
- **Client QSaaS** : https://askme-qsaas.avanteam-online.com
- **Rancher UI** : https://jg8s67.9r1m.rancher.ovh.net

## 🎛️ Configuration Avancée

### Ajouter un Nouveau Client

```bash
# 1. Créer la configuration
mkdir -p deployments/clients/nouveau-client.com
cp deployments/clients/askme.avanteam-online.com/values.yaml \
   deployments/clients/nouveau-client.com/

# 2. Éditer les valeurs spécifiques
nano deployments/clients/nouveau-client.com/values.yaml

# 3. Setup
./deploy-rancher-client.sh nouveau-client.com setup

# 4. Créer le projet dans Rancher UI (suivre instructions)

# 5. Déployer
./deploy-rancher-client.sh nouveau-client.com deploy
```

### Personnalisation par Client

Modifiez les fichiers `values.yaml` de chaque client :

```yaml
# deployments/clients/[client]/values.yaml
client:
  name: "nom-client"
  namespace: "askme-nom-client"
  domain: "client.domain.com"

# Resources personnalisées
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"

# Configuration spécifique
config:
  LLM_PROVIDER: "CLAUDE"  # ou autre provider
  # ... autres configs
```

## ✅ Validation Complète

Après déploiement, vérifiez :

1. **Rancher UI** : Projets visibles avec applications
2. **Monitoring** : Métriques par projet disponibles
3. **Applications** : URLs fonctionnelles
4. **Ressources** : Quotas appliqués et respectés
5. **Logs** : Disponibles par projet dans Rancher

## 🔍 Troubleshooting

### Problème : Labels Rancher non appliqués

```bash
# Vérifier les labels
kubectl get namespace askme-app --show-labels

# Réappliquer manuellement
kubectl label namespace askme-app \
  field.cattle.io/projectId="c-m-g8b9wrhd:askme-askme" --overwrite
```

### Problème : Application non visible dans Rancher

```bash
# Re-déployer avec labels
./deploy-rancher-client.sh askme.avanteam-online.com deploy
```

### Problème : Quotas non appliqués

1. Re-créer le projet dans Rancher UI avec les bons quotas
2. Réassigner le namespace au projet

## 📊 Architecture Finale

```
OVH Rancher (https://jg8s67.9r1m.rancher.ovh.net)
├── Cluster: avanteam-mks-cluster
│   ├── Project: askme-askme
│   │   ├── Namespace: askme-app
│   │   ├── Quotas: 2 CPU, 4Gi RAM, 10Gi Storage
│   │   └── URL: https://askme.avanteam-online.com
│   └── Project: askme-qsaas
│       ├── Namespace: askme-qsaas
│       ├── Quotas: 1 CPU, 2Gi RAM, 5Gi Storage
│       └── URL: https://askme-qsaas.avanteam-online.com
├── Monitoring: Grafana intégré par projet
├── Alerting: Notifications par email configurables
└── RBAC: Permissions isolées par projet
```

---

🐄 **AskMe Multi-Client avec Rancher OVH - Ready to Go !**