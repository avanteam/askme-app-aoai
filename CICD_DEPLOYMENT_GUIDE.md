# 🚀 Guide CI/CD : GitHub → Kubernetes OVH

Ce guide explique comment automatiser le déploiement de votre application AskMe depuis GitHub vers votre infrastructure Kubernetes OVH.

## 🎯 Objectif

Automatiser le processus de déploiement pour que chaque `git push` déclenche automatiquement :
1. ✅ **Tests** automatiques (Python + Frontend)
2. ✅ **Build** de l'image Docker
3. ✅ **Push** vers Harbor Registry OVH
4. ✅ **Déploiement** sur Kubernetes OVH
5. ✅ **Tests** de santé de l'application

## 🏗️ Architecture du Pipeline

```
┌─────────────────┐  git push   ┌──────────────────┐  trigger   ┌─────────────────┐
│   DÉVELOPPEUR   │─────────────▶│  GITHUB ACTIONS  │───────────▶│    PIPELINE     │
│                 │              │                  │            │                 │
│ • Code changes  │              │ • Webhook        │            │ 1. 🧪 Tests     │
│ • Git commit    │              │ • Triggers       │            │ 2. 🐳 Build     │
│ • Git push      │              │ • Secrets        │            │ 3. 📤 Push      │
└─────────────────┘              └──────────────────┘            │ 4. ☸️  Deploy   │
                                                                 │ 5. ✅ Verify   │
                                                                 └─────────────────┘
                                                                          │
                                ┌─────────────────┐                      │
                                │  HARBOR REGISTRY│◀─────────────────────┘
                                │      OVH        │
                                └─────────────────┘
                                          │
                                          ▼
                                ┌─────────────────┐
                                │  KUBERNETES     │
                                │     CLUSTER     │
                                │      OVH        │
                                └─────────────────┘
```

## 📋 Prérequis

### 1. Repository GitHub
- ✅ Code source dans un repository GitHub
- ✅ Accès administrateur au repository
- ✅ Branches `main` (production) et `test-rg2` (staging)

### 2. Infrastructure OVH
- ✅ Cluster Kubernetes OVH opérationnel
- ✅ Harbor Registry OVH configuré
- ✅ Domaine DNS pointant vers l'IP du LoadBalancer

### 3. Accès et Credentials
- ✅ Fichier `kubeconfig` pour accès Kubernetes
- ✅ Identifiants Harbor Registry
- ✅ Permissions pour créer des secrets GitHub

## ⚙️ Configuration Étape par Étape

### Étape 1 : Ajout des Fichiers CI/CD

Les fichiers suivants ont été créés dans votre repository :

```
.github/
└── workflows/
    └── deploy.yml          # Pipeline GitHub Actions principal
GITHUB_SECRETS_SETUP.md     # Guide de configuration des secrets
CICD_DEPLOYMENT_GUIDE.md    # Ce guide (documentation complète)
```

### Étape 2 : Configuration des Secrets GitHub

#### 🔐 Accès aux Secrets
1. Allez sur GitHub → **Your Repository** → **Settings**
2. **Secrets and variables** → **Actions**
3. **New repository secret**

#### 📝 Secrets à Configurer

| Secret Name | Description | Comment l'obtenir |
|-------------|-------------|-------------------|
| `HARBOR_USERNAME` | Username Harbor Registry | `[VOTRE_USERNAME_HARBOR]` |
| `HARBOR_PASSWORD` | Password Harbor Registry | `[VOTRE_PASSWORD_HARBOR]` |
| `KUBE_CONFIG` | Configuration Kubernetes | Voir section ci-dessous |

#### 🔧 Génération de KUBE_CONFIG

```bash
# 1. Encoder votre fichier kubeconfig en base64
cat "/mnt/c/Users/Richard Garcia/Downloads/kubeconfig (1).yml" | base64 -w 0

# 2. Copier le résultat complet dans le secret KUBE_CONFIG
```

### Étape 3 : Structure du Workflow

Le pipeline GitHub Actions comprend **4 jobs** :

#### Job 1: Tests 🧪
```yaml
- Checkout du code
- Setup Python 3.11
- Installation des dépendances
- Tests Python (pytest)
- Setup Node.js 20
- Tests Frontend (npm test)
- Linting (ESLint)
```

#### Job 2: Build 🐳
```yaml
- Checkout du code
- Génération des tags d'image
- Connexion au Harbor Registry
- Build de l'image Docker multi-stage
- Push vers Harbor OVH
```

#### Job 3: Deploy ☸️
```yaml
- Checkout du code
- Configuration de kubectl
- Connexion au cluster Kubernetes
- Application des manifestes K8s
- Mise à jour de l'image
- Tests de santé
```

#### Job 4: Notify 📢
```yaml
- Notifications de succès/échec
- Résumé du déploiement
- Liens vers l'application
```

## 🚦 Déclencheurs du Pipeline

### Déclenchement Automatique

| Événement | Branche | Action |
|-----------|---------|---------|
| `git push` | `main` | Tests + Build + Deploy Production |
| `git push` | `test-rg2` | Tests + Build + Deploy Staging |
| `Pull Request` | vers `main` | Tests uniquement |

### Déclenchement Manuel
- GitHub → **Actions** → **Deploy AskMe to OVH Kubernetes** → **Run workflow**

## 🔄 Workflow de Développement

### Développement Standard
```bash
# 1. Développement local
git checkout test-rg2
# ... modifications du code ...

# 2. Commit et push
git add .
git commit -m "feat: nouvelle fonctionnalité"
git push origin test-rg2
# → Déclenchement automatique du pipeline

# 3. Le pipeline exécute :
# - Tests automatiques
# - Build de l'image Docker
# - Déploiement sur l'environnement de staging

# 4. Vérification sur https://askme.avanteam-online.com
```

### Mise en Production
```bash
# 1. Merge vers main (après validation en staging)
git checkout main
git merge test-rg2
git push origin main
# → Déclenchement automatique du pipeline de production

# 2. Le pipeline exécute le même processus
# mais avec des protections supplémentaires (environments)
```

## 🔍 Monitoring et Debugging

### Visualisation des Pipelines
1. GitHub → **Your Repository** → **Actions**
2. Sélectionner un workflow run
3. Voir le détail de chaque job et étape

### Logs Détaillés
```bash
# Logs GitHub Actions
# Disponibles directement dans l'interface GitHub

# Logs Kubernetes (si nécessaire)
kubectl logs deployment/askme-app -n askme-app --tail=50

# Status du déploiement
kubectl get pods -n askme-app
kubectl get services -n askme-app
kubectl get ingress -n askme-app
```

### Debug des Échecs

#### 🔴 Tests Échouent
```bash
# Reproduire localement
python -m pytest tests/ -v
cd frontend && npm test
```

#### 🔴 Build Docker Échoue
```bash
# Tester le build localement
docker build -f WebApp.Dockerfile -t test-image .
```

#### 🔴 Déploiement Kubernetes Échoue
```bash
# Vérifier les manifestes Helm
helm template askme-client ./helm-chart --values deployments/clients/<client-domain>/values.yaml --dry-run
```

## 🛡️ Sécurité et Bonnes Pratiques

### 🔐 Gestion des Secrets
- ✅ **Secrets stockés** uniquement dans GitHub Secrets
- ✅ **secret.yaml** exclu du versioning (`.gitignore`)
- ✅ **Rotation régulière** des clés d'accès
- ✅ **Accès limité** aux collaborateurs nécessaires

### 🌍 Environments GitHub
```yaml
# Configuration recommandée
environments:
  staging:    # branche test-rg2
    - Protection: Aucune
    - URL: https://askme.avanteam-online.com
  
  production: # branche main
    - Protection: Required reviewers
    - Wait timer: 5 minutes
    - URL: https://askme.avanteam-online.com
```

### 🔄 Rollback Strategy
```bash
# Rollback automatique via Kubernetes
kubectl rollout undo deployment/askme-app -n askme-app

# Rollback vers une version spécifique
kubectl rollout undo deployment/askme-app --to-revision=2 -n askme-app

# Rollback via redéploiement d'un commit précédent
git checkout [previous-commit]
git push origin main  # Redéploie la version précédente
```

## 🚀 Extensions Possibles

### 📊 Monitoring Avancé
- **Prometheus + Grafana** : Métriques applicatives
- **ELK Stack** : Logs centralisés
- **Slack/Teams** : Notifications avancées

### 🧪 Tests Avancés
- **Tests d'intégration** : Tests E2E avec Playwright
- **Tests de charge** : k6 ou Artillery
- **Tests de sécurité** : Scan des images Docker

### 🏗️ Infrastructure as Code
- **Terraform** : Gestion de l'infrastructure OVH
- **Helm Charts** : Templates Kubernetes réutilisables
- **GitOps** : ArgoCD pour le déploiement continu

## 📞 Support et Dépannage

### 🔧 Commandes Utiles
```bash
# Vérifier l'état du cluster
kubectl cluster-info

# Redémarrer un déploiement
kubectl rollout restart deployment/askme-app -n askme-app

# Forcer une nouvelle image
kubectl set image deployment/askme-app askme-app=NEW_IMAGE -n askme-app

# Debug des pods
kubectl describe pod POD_NAME -n askme-app
```

### 📚 Ressources
- **GitHub Actions** : https://docs.github.com/actions
- **Kubernetes** : https://kubernetes.io/docs/
- **Harbor** : https://goharbor.io/docs/
- **OVH Kubernetes** : https://docs.ovh.com/gb/en/kubernetes/

---

## ✅ Résumé de Configuration

Une fois que vous avez :
1. ✅ **Configuré les secrets GitHub** (HARBOR_USERNAME, HARBOR_PASSWORD, KUBE_CONFIG)
2. ✅ **Poussé les fichiers CI/CD** sur votre repository
3. ✅ **Testé avec un push** sur test-rg2

Votre pipeline sera **complètement automatisé** ! 🎉

Chaque `git push` déclenchera automatiquement le déploiement sur votre infrastructure Kubernetes OVH.