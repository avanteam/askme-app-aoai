# 🐄 AskMe Rancher Integration Guide

Ce guide présente l'intégration complète de AskMe avec Rancher pour la gestion multi-client.

## 🎯 Vue d'Ensemble

L'intégration Rancher apporte :
- **Gestion centralisée** des clusters Kubernetes
- **Isolation par projet** pour chaque client
- **Monitoring unifié** avec Grafana/Prometheus intégré
- **RBAC avancé** avec permissions granulaires
- **Interface graphique** intuitive pour l'équipe

## 🔧 Architecture Rancher

```
OVH Managed Rancher
├── Cluster: askme-prod-cluster
│   ├── Project: askme-avanteam-online-com
│   │   └── Namespace: askme-app (client principal)
│   ├── Project: askme-qsaas
│   │   └── Namespace: askme-qsaas (client QSaaS)
│   └── Project: askme-client-N
│       └── Namespace: askme-client-N
├── Monitoring: Rancher Monitoring (Prometheus + Grafana)
├── Alerting: Rancher Alerting Manager
└── RBAC: Projets isolés avec permissions par équipe
```

## 🚀 Déploiement Rapide

### 1. Prérequis

```bash
# Outils requis
helm version          # v3.x
kubectl version       # v1.25+
yq --version         # v4.x
curl --version       # Pour API Rancher
jq --version         # Pour parsing JSON

# Variables d'environnement Rancher
export RANCHER_URL="https://rancher-askme-production.xxx.ovh.net"
export RANCHER_TOKEN="token-xxxxx:xxxxxxx"  # API Key Rancher
export RANCHER_CLUSTER_ID="c-xxxxx"         # ID cluster importé
```

### 2. Setup Initial (une seule fois)

```bash
# Import du cluster existant dans Rancher
./deploy-rancher-client.sh askme.avanteam-online.com setup
```

Cette commande :
- ✅ Teste la connexion Rancher
- ✅ Crée le namespace avec labels Rancher
- ✅ Crée le projet Rancher via API
- ✅ Configure les quotas de ressources
- ✅ Génère les valeurs Rancher spécifiques

### 3. Déploiement Client

```bash
# Déploiement via Rancher
./deploy-rancher-client.sh askme.avanteam-online.com deploy

# Autres clients
./deploy-rancher-client.sh askme-qsaas.avanteam-online.com deploy
```

## 📋 Commandes Disponibles

### Script Principal : `deploy-rancher-client.sh`

```bash
# Setup initial Rancher
./deploy-rancher-client.sh <client-domain> setup

# Déploiement complet
./deploy-rancher-client.sh <client-domain> deploy [version]

# Mise à jour
./deploy-rancher-client.sh <client-domain> upgrade v1.2.0

# Rollback
./deploy-rancher-client.sh <client-domain> rollback [revision]

# Statut avec infos Rancher
./deploy-rancher-client.sh <client-domain> status

# Désinstallation (inclut nettoyage Rancher)
./deploy-rancher-client.sh <client-domain> uninstall
```

### Comparaison avec le mode classique

| Action | Mode Classique | Mode Rancher |
|--------|---------------|--------------|
| Déploiement | `./deploy-helm-client.sh` | `./deploy-rancher-client.sh` |
| Monitoring | Externe | Intégré Rancher |
| RBAC | Manuel kubectl | Interface Rancher |
| Projets | Namespaces seuls | Projets Rancher + quotas |
| API Management | kubectl CLI | Rancher API + UI |

## 🏗️ Configuration Helm Chart

### Templates Rancher Ajoutés

1. **`helm-chart/templates/rancher-project.yaml`**
   - Création automatique des projets Rancher
   - Configuration des quotas par client
   - Labels et métadonnées

2. **`helm-chart/templates/rancher-rbac.yaml`**
   - ServiceAccount par client
   - Roles et RoleBindings avec permissions Rancher
   - Support utilisateurs additionnels

### Configuration values.yaml

```yaml
# Configuration Rancher (dans helm-chart/values.yaml)
rancher:
  enabled: false  # Activé automatiquement par le script
  clusterName: "askme-prod-cluster"
  managementNamespace: "cattle-system"
  
  resourceQuota:
    cpu: "2000m"     # Quota CPU par projet
    memory: "4Gi"    # Quota RAM par projet  
    storage: "10Gi"  # Quota stockage par projet
  
  rbac:
    enabled: true
    additionalUsers:
      - name: "admin@avanteam.com"
      - name: "devops@avanteam.com"
  
  monitoring:
    enabled: true
    projectId: ""    # Auto-généré
  
  alerting:
    enabled: true
    recipients:
      - email: "admin@avanteam.com"
```

### Valeurs par Client

Le script génère automatiquement un fichier `rancher-values.yaml` par client avec :

```yaml
# deployments/clients/askme.avanteam-online.com/rancher-values.yaml
rancher:
  enabled: true
  resourceQuota:
    cpu: "2000m"    # Client principal
    memory: "4Gi"   
    storage: "10Gi"

# OU pour QSaaS
rancher:
  enabled: true  
  resourceQuota:
    cpu: "1000m"    # Client QSaaS (ressources réduites)
    memory: "2Gi"
    storage: "5Gi"
```

## 🔐 Gestion RBAC

### Permissions par Projet

Chaque client obtient :
- **Namespace dédié** avec isolation complète
- **Projet Rancher** avec quotas configurés
- **ServiceAccount** avec permissions limitées au namespace
- **Utilisateurs additionnels** configurables via values

### Exemple de permissions

```yaml
# Permissions auto-générées par le template
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "secrets", "persistentvolumeclaims"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["networking.k8s.io"]
  resources: ["ingresses"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

## 📊 Monitoring et Alerting

### Activation Monitoring Rancher

```bash
# Dans Rancher UI
Apps & Marketplace → Charts → Rancher Monitoring → Install

# Configuration recommandée
prometheus:
  retention: 30d
  storage: 50Gi
grafana:
  persistence:
    enabled: true
    size: 10Gi
```

### Dashboards Intégrés

- **Cluster Overview** : Vue globale du cluster
- **Project Metrics** : Métriques par projet/client
- **Workload Dashboard** : Performance applications
- **Resource Usage** : Utilisation CPU/RAM/Storage

### Alerting Par Client

Le script configure automatiquement :
- **Alerts critiques** : Pod crash, haute utilisation mémoire
- **Recipients** : Email par client configuré
- **Escalation** : Notification équipe support

## 🔄 Workflow de Développement

### Développement Standard avec Rancher

```bash
# 1. Développement local (inchangé)
git checkout test-rg2
# ... modifications code ...

# 2. Test local Docker (optionnel)
.\deploy-local.ps1 build && .\deploy-local.ps1 run

# 3. Déploiement staging via Rancher
./deploy-rancher-client.sh askme.avanteam-online.com deploy

# 4. Monitoring dans Rancher UI
# → Cluster → Projects → AskMe-Client → Workloads

# 5. Production après validation
git checkout main && git merge test-rg2 && git push
```

### Migration Progressive

1. **Phase 1** : Import cluster dans Rancher (✅ Fait)
2. **Phase 2** : Déploiement clients via script Rancher
3. **Phase 3** : Migration monitoring vers Rancher
4. **Phase 4** : Formation équipe sur interface Rancher

## 🛠️ Troubleshooting

### Problèmes Courants

**1. Erreur de connexion Rancher**
```bash
# Vérifier les variables
echo $RANCHER_URL $RANCHER_TOKEN $RANCHER_CLUSTER_ID

# Test manuel API
curl -k -H "Authorization: Bearer $RANCHER_TOKEN" "$RANCHER_URL/v3/clusters"
```

**2. Projet non créé**
```bash
# Création manuelle dans Rancher UI
Cluster Management → Projects/Namespaces → Create Project
```

**3. Namespace pas assigné au projet**
```bash
# Réassigner manuellement
kubectl annotate namespace askme-app field.cattle.io/projectId="c-xxxxx:askme-avanteam-online-com" --overwrite
```

### Logs et Debug

```bash
# Logs script Rancher
./deploy-rancher-client.sh askme.avanteam-online.com status

# Logs Rancher agents
kubectl logs -n cattle-system -l app=rancher-agent

# Vérifier projets Rancher
curl -k -H "Authorization: Bearer $RANCHER_TOKEN" "$RANCHER_URL/v3/projects"
```

## 📚 Documentation Complémentaire

- **[rancher-setup-guide.md](./rancher-setup-guide.md)** : Guide complet setup OVH Rancher
- **[CICD_DEPLOYMENT_GUIDE.md](./CICD_DEPLOYMENT_GUIDE.md)** : Pipeline CI/CD avec Rancher
- **[Rancher Documentation](https://rancher.com/docs/rancher/v2.x/en/)** : Documentation officielle

## 🎯 Prochaines Étapes

- [ ] Formation équipe interface Rancher
- [ ] Migration monitoring existant vers Rancher
- [ ] Configuration backup automatique Rancher
- [ ] Intégration alerting Slack/Teams
- [ ] Documentation utilisateur final Rancher UI

---

*🐄 Integration Rancher complétée pour AskMe Multi-Client - Infrastructure OVH*