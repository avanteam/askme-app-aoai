# 🚀 Guide Setup Rancher OVH - AskMe Multi-Client

Ce guide détaille la configuration complète de votre Rancher OVH pour AskMe.

## 📋 Informations de votre Setup

- **URL Rancher** : `https://jg8s67.9r1m.rancher.ovh.net`
- **Cluster** : `avanteam-mks-cluster`
- **Scripts** : Configuration mise à jour automatiquement

## 🔑 Étape 1: Créer le Token API

### Dans l'interface Rancher OVH :

1. **Se connecter** à https://jg8s67.9r1m.rancher.ovh.net
2. **Cliquer** sur votre **avatar** (en haut à droite)
3. **Sélectionner** : `Account & API Keys`
4. **Cliquer** : `Create API Key`
5. **Configurer** :
   ```
   Name: askme-deployment-key
   Description: Token pour déploiement automatisé AskMe multi-client
   Scope: No Scope (accès global recommandé)
   Expires: Never (ou date de votre choix)
   ```
6. **Cliquer** : `Create`
7. **⚠️ COPIER LE TOKEN** immédiatement (il ne sera plus affiché)

Format attendu : `token-12345:abcdefghijklmnopqrstuvwxyz1234567890`

## 🆔 Étape 2: Récupérer l'ID du Cluster

### Option A - Interface Web (Plus Simple) :
1. **Menu** → `Cluster Management` 
2. **Trouver** : `avanteam-mks-cluster`
3. **Cliquer** sur le cluster
4. **Dans l'URL** du navigateur, noter l'ID : `.../c/c-xxxxx/...`
5. **L'ID cluster** = `c-xxxxx` (exemple: `c-m-12345678`)

### Option B - Script Automatique :
```bash
# 1. Définir le token
export RANCHER_TOKEN="token-xxxxx:xxxxxxxxxxxxxxxxx"  # Votre token créé

# 2. Exécuter le script
./get-cluster-id.sh

# 3. Le script affichera l'ID et la configuration à utiliser
```

## ⚙️ Étape 3: Configuration des Variables d'Environnement

```bash
# Configuration Rancher OVH
export RANCHER_URL="https://jg8s67.9r1m.rancher.ovh.net"
export RANCHER_TOKEN="token-xxxxx:xxxxxxxxxxxxxxxxx"  # Votre token
export RANCHER_CLUSTER_ID="c-xxxxx"                   # ID récupéré

# Vérification
echo "URL: $RANCHER_URL"
echo "Cluster: $RANCHER_CLUSTER_ID" 
echo "Token: ${RANCHER_TOKEN:0:20}..." # Affiche seulement le début
```

## 🧪 Étape 4: Test de Connexion

```bash
# Test manuel API Rancher
curl -s -k -H "Authorization: Bearer $RANCHER_TOKEN" \
  "$RANCHER_URL/v3/clusters" | jq '.data[].name'

# Doit afficher: "avanteam-mks-cluster"
```

## 🎯 Étape 5: Setup Initial AskMe

```bash
# Setup du premier client (création projet Rancher)
./deploy-rancher-client.sh askme.avanteam-online.com setup

# Résultat attendu:
# ✅ Connexion Rancher OK
# ✅ Namespace askme-app créé
# ✅ Projet Rancher 'askme-avanteam-online-com' créé
# ✅ Fichier rancher-values.yaml généré
```

## 🚀 Étape 6: Déploiement des Clients

```bash
# Déploiement client principal
./deploy-rancher-client.sh askme.avanteam-online.com deploy

# Déploiement client QSaaS
./deploy-rancher-client.sh askme-qsaas.avanteam-online.com deploy

# Vérification statut
./deploy-rancher-client.sh askme.avanteam-online.com status
```

## 📊 Étape 7: Vérification dans Rancher UI

### Dans https://jg8s67.9r1m.rancher.ovh.net :

1. **Cluster Management** → `avanteam-mks-cluster`
2. **Projects/Namespaces** → Vérifier les projets créés :
   - `askme-avanteam-online-com`
   - `askme-qsaas` 
3. **Workloads** → Vérifier les déploiements actifs
4. **Resources** → Quotas et utilisation par projet

## 🔧 Scripts Disponibles

| Script | Usage | Description |
|--------|-------|-------------|
| `get-cluster-id.sh` | `./get-cluster-id.sh` | Récupère l'ID du cluster automatiquement |
| `deploy-rancher-client.sh` | `./deploy-rancher-client.sh <client> <action>` | Déploiement via Rancher |
| `deploy-helm-client.sh` | `./deploy-helm-client.sh <client> <action>` | Déploiement kubectl direct |

### Actions Rancher disponibles :
```bash
# Configuration initiale (une seule fois)
./deploy-rancher-client.sh <client> setup

# Déploiement complet
./deploy-rancher-client.sh <client> deploy [version]

# Mise à jour
./deploy-rancher-client.sh <client> upgrade v1.2.0

# Statut avec infos Rancher
./deploy-rancher-client.sh <client> status

# Rollback
./deploy-rancher-client.sh <client> rollback [revision]

# Désinstallation complète
./deploy-rancher-client.sh <client> uninstall
```

## 🎛️ Configuration Avancée

### Quotas par Projet Rancher :
- **Client Principal** : 2 CPU, 4Gi RAM, 10Gi Storage
- **Client QSaaS** : 1 CPU, 2Gi RAM, 5Gi Storage

### RBAC Configuré :
- **Utilisateurs équipe** : admin@avanteam.com, devops@avanteam.com
- **Permissions** : Lecture/écriture limitée au namespace client
- **Isolation** : Projets séparés par client

### Monitoring Intégré :
- **Métriques** : CPU, RAM, Storage par projet
- **Dashboards** : Grafana intégré Rancher
- **Alerting** : Notifications par email configurables

## 🔍 Troubleshooting

### Erreur "Unauthorized" :
```bash
# Vérifier le token
echo $RANCHER_TOKEN
# Recréer un nouveau token si nécessaire
```

### Cluster non trouvé :
```bash
# Lister tous les clusters
curl -s -k -H "Authorization: Bearer $RANCHER_TOKEN" \
  "$RANCHER_URL/v3/clusters" | jq '.data[].name'
```

### Projet non créé :
```bash
# Création manuelle dans Rancher UI
# Cluster Management → Projects/Namespaces → Create Project
```

## 📚 Ressources

- **Rancher OVH** : https://jg8s67.9r1m.rancher.ovh.net
- **Documentation Rancher** : https://rancher.com/docs/rancher/v2.x/en/
- **Support OVH** : Interface OVH → Support → Ticket

## 🎯 Checklist de Validation

- [ ] Token API créé et fonctionnel
- [ ] ID cluster récupéré : `c-xxxxx`
- [ ] Variables d'environnement configurées
- [ ] Test connexion API réussi
- [ ] Setup client principal exécuté
- [ ] Projets visibles dans Rancher UI
- [ ] Déploiements fonctionnels
- [ ] Monitoring actif

---

🐄 **Setup Rancher OVH terminé pour AskMe Multi-Client !**