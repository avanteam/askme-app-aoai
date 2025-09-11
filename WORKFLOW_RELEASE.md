# 🚀 AskMe Release Workflow

## 📋 Procédure de Release Complète

### **Architecture des Repositories**

- **`askme-app-aoai`** : Code source de l'application AskMe
- **`askme-rancher-catalog`** : Chart Helm pour déploiement via Rancher App Store

### **🔄 Workflow de Release Synchronisé**

#### **Étape 1 : Développement et Tests**
```bash
# Dans askme-app-aoai
git checkout test-rg2
# ... développement de nouvelles fonctionnalités ...
git add .
git commit -m "feat: nouvelle fonctionnalité"
git push origin test-rg2
# → Pipeline automatique : Tests + Deploy staging
```

#### **Étape 2 : Validation en Production**
```bash
# Merge vers main pour production
git checkout main
git merge test-rg2
git push origin main
# → Pipeline automatique : Deploy production
```

#### **Étape 3 : Tag de Version dans askme-app-aoai**
```bash
# Créer le tag de version dans le repo source
git tag v1.0.3
git push origin v1.0.3
```

#### **Étape 4 : Tag Synchronisé dans askme-rancher-catalog**
```bash
# Dans askme-rancher-catalog
git pull origin main
git tag v1.0.3  # ⚡ MÊME TAG que askme-app-aoai
git push origin v1.0.3
```

#### **Étape 5 : Pipeline Automatique askme-rancher-catalog**

Le pipeline s'exécute automatiquement et :

1. **🔍 Détecte le tag** `v1.0.3` dans askme-rancher-catalog
2. **📥 Récupère automatiquement** le tag `v1.0.3` depuis askme-app-aoai
3. **🐳 Build l'image Docker** depuis le code tagué
4. **📦 Push vers Harbor** avec le tag `v1.0.3`
5. **📊 Package le Chart Helm** avec la version `v1.0.3`
6. **🚀 Crée la GitHub Release** avec le chart
7. **📈 Met à jour l'index.yaml** pour GitHub Pages

### **🎯 Résultat Final**

Après le pipeline :
- ✅ **Image Docker** : `harbor.../askme-app:v1.0.3`
- ✅ **Chart Helm** : Version `v1.0.3` disponible dans Rancher
- ✅ **GitHub Pages** : https://avanteam.github.io/askme-rancher-catalog/
- ✅ **Rancher UI** : Nouvelle version `v1.0.3` dans App Store

### **💡 Avantages du Workflow Synchronisé**

1. **🔗 Cohérence** : Même version dans code source et chart
2. **📦 Traçabilité** : Lien direct entre version déployée et code source
3. **🎯 Simplicité** : Un seul tag à gérer pour chaque release
4. **🔄 Automatisation** : Pipeline entièrement automatisé
5. **🛡️ Sécurité** : Le chart utilise toujours le code source tagué

### **📋 Checklist de Release**

```
□ Développement terminé dans askme-app-aoai/test-rg2
□ Tests passés et validation OK
□ Merge vers main et déploiement prod validé
□ Tag créé dans askme-app-aoai (ex: v1.0.3)
□ Tag synchronisé dans askme-rancher-catalog (même version)
□ Pipeline réussi (vérifier GitHub Actions)
□ Image Docker disponible dans Harbor
□ Chart disponible dans Rancher UI
□ Test de déploiement via Rancher
```

### **🔧 Exemple Complet**

```bash
# === Développement ===
cd askme-app-aoai
git checkout test-rg2
echo "nouvelle fonctionnalité" >> features.txt
git add . && git commit -m "feat: ajout fonctionnalité X"
git push origin test-rg2

# === Validation ===
git checkout main
git merge test-rg2
git push origin main

# === Release ===
git tag v1.0.3
git push origin v1.0.3

# === Catalog Sync ===
cd ../askme-rancher-catalog
git pull origin main
git tag v1.0.3
git push origin v1.0.3

# === Attendre Pipeline ===
# → GitHub Actions s'exécute automatiquement
# → 5-10 minutes plus tard : version disponible dans Rancher UI
```

### **🎉 Déploiement Client**

```
Rancher UI → Apps & Marketplace → Charts → AskMe
→ Version: v1.0.3 ✨ (nouvelle version)
→ Configuration client spécifique
→ Install
```

**🚀 Le workflow est maintenant parfaitement synchronisé ! 🚀**