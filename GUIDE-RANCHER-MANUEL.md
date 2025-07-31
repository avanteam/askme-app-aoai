# 🐄 Guide Configuration Manuelle Rancher OVH

Ce guide explique comment configurer manuellement les projets Rancher via l'interface web, car l'API Token ne fonctionne pas directement avec l'installation OVH.

## 🎯 Méthode Hybride : kubectl + Interface Rancher

Notre approche utilise :
- ✅ **kubectl** pour déployer les applications avec templates Rancher
- ✅ **Interface Rancher** pour créer les projets et gérer les permissions
- ✅ **Labels automatiques** pour l'intégration Rancher complète

## 🚀 Workflow de Déploiement

### 1. Setup Initial (Automatique)

```bash
# Le script applique automatiquement :
./deploy-rancher-client.sh askme.avanteam-online.com setup
```

**Ce que fait le script :**
- ✅ Crée le namespace `askme-app`
- ✅ Applique les labels Rancher : `field.cattle.io/projectId=c-m-g8b9wrhd:askme-avanteam-online-com`
- ✅ Applique les annotations Rancher nécessaires
- ✅ Génère le fichier `rancher-values.yaml`
- ✅ Affiche les instructions manuelles pour l'UI

### 2. Création Projet dans Rancher UI (Manuel)

**Après le setup, suivez ces étapes dans https://jg8s67.9r1m.rancher.ovh.net :**

#### Étape 1 : Navigation
1. Se connecter à l'interface Rancher OVH
2. Cliquer sur le cluster **"avanteam-mks-cluster"**
3. Aller dans **"Projects/Namespaces"**

#### Étape 2 : Création Projet
1. Cliquer **"Create Project"**
2. **Nom** : `askme-avanteam-online-com` (affiché par le script)
3. **Description** : `Projet AskMe pour askme.avanteam-online.com`

#### Étape 3 : Configuration Quotas
**Pour le client principal :**
```
Resource Quotas:
├── CPU Limit: 2000m
├── Memory Limit: 4Gi
└── Storage: 10Gi
```

**Pour le client QSaaS :**
```
Resource Quotas:
├── CPU Limit: 1000m
├── Memory Limit: 2Gi
└── Storage: 5Gi
```

#### Étape 4 : Assignment Namespace
1. Dans la section **"Member"** ou **"Namespaces"**
2. Assigner le namespace : **`askme-app`** (ou `askme-qsaas`)
3. Cliquer **"Create"**

### 3. Déploiement Application (Automatique)

```bash
# Une fois le projet créé dans l'UI
./deploy-rancher-client.sh askme.avanteam-online.com deploy
```

**Ce que fait le script :**
- ✅ Déploie l'application avec Helm + templates Rancher
- ✅ Configure tous les labels et annotations
- ✅ Applique les quotas et permissions
- ✅ Intègre parfaitement avec Rancher UI

## 📋 Configuration des Clients

### Client Principal : askme.avanteam-online.com

```bash
# Setup + Instructions UI
./deploy-rancher-client.sh askme.avanteam-online.com setup

# Créer le projet "askme-avanteam-online-com" dans l'UI avec quotas normaux

# Déploiement
./deploy-rancher-client.sh askme.avanteam-online.com deploy
```

### Client QSaaS : askme-qsaas.avanteam-online.com

```bash
# Setup + Instructions UI
./deploy-rancher-client.sh askme-qsaas.avanteam-online.com setup

# Créer le projet "askme-qsaas" dans l'UI avec quotas réduits

# Déploiement
./deploy-rancher-client.sh askme-qsaas.avanteam-online.com deploy
```

## 🔧 Vérification de l'Intégration

### Dans l'Interface Rancher

Après déploiement, vérifiez dans Rancher UI :

1. **Projects/Namespaces** → Votre projet est visible
2. **Workloads** → Applications AskMe listées dans le bon projet
3. **Resources** → Utilisation CPU/RAM visible par projet
4. **Monitoring** → Métriques par projet disponibles

### Via kubectl

```bash
# Vérifier les labels Rancher
kubectl get namespace askme-app --show-labels

# Vérifier les pods avec labels
kubectl get pods -n askme-app --show-labels

# Vérifier les quotas appliqués
kubectl describe resourcequota -n askme-app

# Vérifier le déploiement
kubectl get all -n askme-app
```

## 🎛️ Gestion Continue

### Mise à Jour Applications

```bash
# Mise à jour normale (sans toucher à Rancher)
./deploy-rancher-client.sh askme.avanteam-online.com upgrade v1.2.0

# Le script maintient automatiquement tous les labels Rancher
```

### Ajout de Nouveaux Clients

```bash
# 1. Créer la configuration client
mkdir -p deployments/clients/nouveau-client.com
cp deployments/clients/askme.avanteam-online.com/values.yaml deployments/clients/nouveau-client.com/
# Éditer les valeurs spécifiques

# 2. Setup automatique
./deploy-rancher-client.sh nouveau-client.com setup

# 3. Créer le projet dans l'UI Rancher (suivre les instructions)

# 4. Déployer
./deploy-rancher-client.sh nouveau-client.com deploy
```

### Surveillance et Monitoring

**Dans Rancher UI :**
- **Dashboard** → Métriques globales par projet
- **Monitoring** → Grafana intégré avec dashboards par projet
- **Alerting** → Configuration d'alertes par projet
- **Logging** → Logs centralisés par projet

## 🔍 Troubleshooting

### Problème : Namespace non assigné au projet

**Symptôme :** Le namespace existe mais n'apparaît pas dans le projet Rancher

**Solution :**
```bash
# Réappliquer les labels manuellement
kubectl label namespace askme-app \
  field.cattle.io/projectId="c-m-g8b9wrhd:askme-avanteam-online-com" \
  --overwrite

# Re-assigner dans l'UI Rancher
# Projects/Namespaces → Edit Project → Assign Namespace
```

### Problème : Quotas non appliqués

**Solution :**
```bash
# Vérifier les quotas
kubectl get resourcequota -n askme-app

# Si absents, re-créer le projet dans l'UI avec les bons quotas
```

### Problème : Applications non visibles dans Rancher

**Solution :**
```bash
# Réappliquer les labels sur les ressources
./deploy-rancher-client.sh askme.avanteam-online.com deploy
```

## 📊 Avantages de cette Approche

✅ **Fiabilité** : Pas de dépendance API problématique  
✅ **Compatibilité** : Fonctionne avec tous les setups OVH Rancher  
✅ **Flexibilité** : Combine automation kubectl + gestion UI  
✅ **Évolutivité** : Support multi-client intégral  
✅ **Monitoring** : Intégration complète dashboards Rancher  
✅ **Sécurité** : Isolation et RBAC par projet  

## 🎯 Résultat Final

Après configuration :
- **Interface Rancher** : Projets organisés, monitoring, alerting
- **Applications** : Déployées automatiquement avec bons labels
- **Isolation** : Quotas et permissions par client
- **Maintenance** : Scripts automatisés pour mises à jour
- **Visibilité** : Dashboards et métriques par projet

---

🐄 **Configuration Rancher Hybride Terminée - Ready for Production !**