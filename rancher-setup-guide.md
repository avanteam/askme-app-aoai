# 🐄 Guide Setup OVH Rancher pour AskMe Multi-Client

## 📋 Checklist Commande OVH Rancher

### ✅ Étapes OVH Interface
1. **Se connecter** : https://www.ovh.com/manager/#/
2. **Naviguer** : Public Cloud → Projet ASKME → Containers & Orchestration
3. **Cliquer** : Managed Rancher Service → Nouvelle instance
4. **Configurer** :
   - Plan : **OVHcloud Edition** (pour clusters OVH uniquement)
   - Région : **GRA** (même que vos clusters Kubernetes)
   - Nom : `rancher-askme-production`
5. **Commander** (activation sous 5-10 minutes)

## 🔧 Configuration Post-Installation

### 1. Accès Initial Rancher
```bash
# OVH vous fournira après activation :
URL: https://rancher-askme-production.xxx.ovh.net
Username: admin
Password: [généré automatiquement par OVH]
```

### 2. Import du Cluster Kubernetes Existant

#### Dans l'interface Rancher :
1. **Cluster Management** → **Import Existing**
2. **Cluster Name** : `askme-prod-cluster`
3. **Choisir** : Generic (existing Kubernetes cluster)
4. **Copier** la commande kubectl fournie

#### Sur votre machine locale :
```bash
# 1. Utiliser votre kubeconfig existant
export KUBECONFIG="/mnt/c/Users/Richard Garcia/Downloads/kubeconfig (1).yml"

# 2. Exécuter la commande d'import Rancher (exemple)
kubectl apply -f https://rancher-askme-production.xxx.ovh.net/v3/import/xxx.yaml

# 3. Vérifier l'import
kubectl get pods -n cattle-system
```

### 3. Configuration Namespaces Multi-Client

#### Créer la structure pour 10 clients :
```bash
# Liste de vos 10 clients (à adapter selon vos domaines)
CLIENTS=(
  "askme.avanteam-online.com"
  "askme-qsaas.avanteam-online.com"
  "client3.domain.com"
  "client4.domain.com"
  "client5.domain.com"
  "client6.domain.com"
  "client7.domain.com"
  "client8.domain.com"
  "client9.domain.com"
  "client10.domain.com"
)

# Créer les namespaces
for client in "${CLIENTS[@]}"; do
  CLIENT_NAME=$(echo $client | sed 's/\./-/g')
  kubectl create namespace "askme-$CLIENT_NAME"
done
```

### 4. Configuration RBAC par Client

#### Template de permissions par client :
```yaml
# rbac-template.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ${CLIENT_NAME}-sa
  namespace: askme-${CLIENT_NAME}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: askme-${CLIENT_NAME}
  name: ${CLIENT_NAME}-role
rules:
- apiGroups: ["", "apps", "extensions"]
  resources: ["*"]
  verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ${CLIENT_NAME}-binding
  namespace: askme-${CLIENT_NAME}
roleRef:
  kind: Role
  name: ${CLIENT_NAME}-role
  apiGroup: rbac.authorization.k8s.io
subjects:
- kind: ServiceAccount
  name: ${CLIENT_NAME}-sa
  namespace: askme-${CLIENT_NAME}
```

## 🎯 Configuration Rancher Projects

### Créer des Projects par Client dans Rancher UI :

1. **Cluster Management** → Votre cluster → **Projects/Namespaces**
2. **Create Project** pour chaque client :
   ```
   Project Name: AskMe-Client1
   Description: Client askme.avanteam-online.com
   Assigned Namespaces: askme-avanteam-online-com
   Resource Quotas: 
     - CPU Limit: 2000m
     - Memory Limit: 4Gi
     - Storage: 10Gi
   ```

### Resource Quotas Suggérées par Client :
```yaml
Production Client:
  CPU Request: 500m
  CPU Limit: 2000m
  Memory Request: 1Gi  
  Memory Limit: 4Gi
  Storage: 10Gi
  
QSaaS Client:
  CPU Request: 250m
  CPU Limit: 1000m
  Memory Request: 512Mi
  Memory Limit: 2Gi
  Storage: 5Gi
```

## 📊 Configuration Monitoring Centralisé

### 1. Activer Rancher Monitoring
Dans Rancher UI :
1. **Apps & Marketplace** → **Charts**
2. **Rancher Monitoring** → Install
3. Configuration :
   ```yaml
   # Values de base pour monitoring
   prometheus:
     retention: 30d
     storage: 50Gi
   grafana:
     persistence:
       enabled: true
       size: 10Gi
   ```

### 2. Dashboards Multi-Client
Dashboards Grafana à importer :
- **Kubernetes Cluster Overview** (ID: 7249)
- **Kubernetes Pod Overview** (ID: 6417)
- **Node Exporter Full** (ID: 1860)

## 🔔 Configuration Alerting

### Alerts critiques par client :
```yaml
alerts:
- name: PodCrashLooping
  expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
  for: 5m
  labels:
    severity: critical
    client: "{{ $labels.namespace }}"
  annotations:
    summary: "Pod {{ $labels.pod }} is crash looping"

- name: HighMemoryUsage  
  expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
  for: 5m
  labels:
    severity: warning
    client: "{{ $labels.namespace }}"
```

## 🚀 Migration des Déploiements Existants

### Script de déploiement automatisé Rancher :

Le projet inclut maintenant un script automatisé `deploy-rancher-client.sh` qui gère l'intégration complète avec Rancher :

```bash
# Setup initial Rancher (à faire une seule fois)
./deploy-rancher-client.sh askme.avanteam-online.com setup

# Déploiement via Rancher
./deploy-rancher-client.sh askme.avanteam-online.com deploy

# Autres actions disponibles
./deploy-rancher-client.sh askme.avanteam-online.com upgrade v1.2.0
./deploy-rancher-client.sh askme.avanteam-online.com status
./deploy-rancher-client.sh askme.avanteam-online.com rollback
./deploy-rancher-client.sh askme.avanteam-online.com uninstall
```

### Configuration des variables d'environnement :
```bash
# Configuration Rancher (obligatoire)
export RANCHER_URL="https://rancher-askme-production.xxx.ovh.net"
export RANCHER_TOKEN="token-xxxxx:xxxxxxx"  # API Key depuis Rancher UI
export RANCHER_CLUSTER_ID="c-xxxxx"         # ID du cluster importé

# Utilisation
./deploy-rancher-client.sh askme.avanteam-online.com deploy
```

### Nouvelles fonctionnalités Helm Chart :

Le chart Helm a été enrichi avec :

1. **Templates Rancher spécifiques** :
   - `rancher-project.yaml` : Création automatique des projets Rancher
   - `rancher-rbac.yaml` : Configuration RBAC par client

2. **Configuration Rancher dans values.yaml** :
   ```yaml
   rancher:
     enabled: true
     clusterName: "askme-prod-cluster"
     resourceQuota:
       cpu: "2000m"
       memory: "4Gi"
       storage: "10Gi"
     rbac:
       additionalUsers:
         - name: "admin@avanteam.com"
   ```

3. **Déploiement multi-mode** :
   - Mode classique : `./deploy-helm-client.sh` (kubectl direct)
   - Mode Rancher : `./deploy-rancher-client.sh` (avec intégration Rancher)

## 📚 Documentation Équipe

### Accès Rancher pour l'équipe :
1. **Global** → **Security** → **Users & Authentication**
2. **Create User** pour chaque membre équipe
3. **Assign Permissions** :
   - Admin : Accès complet
   - Developer : Accès lecture/écriture projets assignés
   - Viewer : Accès lecture uniquement

### Guide Rapide Rancher UI :
```
Navigation principale :
├── Cluster Management : Gestion clusters, nœuds, monitoring
├── Apps & Marketplace : Installation applications (Helm charts)
├── Projects/Namespaces : Gestion projets et permissions
└── Global : Configuration utilisateurs, authentification
```

## ✅ Validation Post-Setup

### Tests à effectuer :
```bash
# 1. Vérifier cluster importé
kubectl get nodes

# 2. Vérifier agents Rancher
kubectl get pods -n cattle-system

# 3. Test déploiement via Rancher
# (Via l'interface ou Rancher CLI)

# 4. Vérifier monitoring
curl -s http://localhost:3000/api/health  # Grafana

# 5. Test alerting  
# (Simuler une panne pour vérifier notifications)
```

## 🔄 Maintenance Rancher

### Tâches régulières :
- **Backup configurations** : Export des projects/RBAC
- **Monitor ressources** : Utilisation CPU/RAM Rancher
- **Update agents** : Mise à jour automatique via OVH
- **Review permissions** : Audit accès utilisateurs

---

## 📞 Support

En cas de problème :
1. **Logs Rancher** : Interface → Troubleshooting
2. **Support OVH** : Ticket via interface OVH
3. **Support SUSE** : Via OVH (inclus dans l'abonnement)
4. **Documentation** : https://rancher.com/docs/rancher/v2.x/en/

---
*Guide créé pour le déploiement multi-client AskMe via OVH Rancher*