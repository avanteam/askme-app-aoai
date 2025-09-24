# 🔐 Configuration des Secrets GitHub

Pour configurer le pipeline CI/CD, vous devez ajouter les secrets suivants dans votre repository GitHub.

## 📍 Accès aux Secrets GitHub

1. Allez sur votre repository GitHub
2. **Settings** → **Secrets and variables** → **Actions**
3. Cliquez sur **New repository secret**

## 🔑 Secrets à Configurer

### 1. **HARBOR_USERNAME**
```
Nom: HARBOR_USERNAME
Valeur: [VOTRE_USERNAME_HARBOR]
```
**Description**: Username pour se connecter au Harbor Registry OVH

### 2. **HARBOR_PASSWORD**
```
Nom: HARBOR_PASSWORD
Valeur: [VOTRE_PASSWORD_HARBOR]
```
**Description**: Mot de passe pour Harbor Registry OVH

### 3. **KUBE_CONFIG**
```
Nom: KUBE_CONFIG
Valeur: [CONTENU_DU_FICHIER_KUBECONFIG_EN_BASE64]
```
**Description**: Configuration kubectl encodée en base64

#### Comment obtenir KUBE_CONFIG :

```bash
# 1. Encoder votre fichier kubeconfig en base64
cat "/mnt/c/Users/Richard Garcia/Downloads/kubeconfig (1).yml" | base64 -w 0

# 2. Copier le résultat dans le secret KUBE_CONFIG
```

## 🌐 Environments GitHub (Optionnel)

Pour une meilleure sécurité, configurez des environments :

### Environment "staging" (branche test-rg2)
- **Protection rules**: Aucune
- **Environment secrets**: Mêmes secrets que ci-dessus

### Environment "production" (branche main)
- **Protection rules**: 
  - ✅ Required reviewers: Vous-même
  - ✅ Wait timer: 5 minutes
- **Environment secrets**: Secrets de production si différents

## 🔍 Vérification des Secrets

Après configuration, vérifiez que tous les secrets sont présents :

```
Repository secrets:
├── HARBOR_USERNAME ✅
├── HARBOR_PASSWORD ✅
└── KUBE_CONFIG ✅
```

## ⚠️ Sécurité

- ❌ **Ne jamais** commiter les vraies valeurs dans le code
- ✅ **Toujours** utiliser les secrets GitHub pour les informations sensibles
- ✅ **Renouveler** régulièrement les clés d'accès
- ✅ **Limiter** l'accès aux secrets aux collaborateurs nécessaires

## 🧪 Test des Secrets

Une fois configurés, testez en poussant du code sur la branche `test-rg2` :

```bash
git push origin test-rg2
```

Le workflow GitHub Actions devrait se déclencher automatiquement.