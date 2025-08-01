# 📁 Notebooks AskMe Search

Collection de notebooks Jupyter spécialisés pour gérer efficacement le système OpenSearch d'AskMe.

## 🎯 Vue d'Ensemble

Ces notebooks couvrent tous les aspects de gestion du système de recherche :

| Notebook | Use Case | Niveau | Durée |
|----------|----------|--------|-------|
| **01_gestion_clients** | 🏢 Créer/gérer les clients et leurs index | Débutant | 10 min |
| **02_gestion_documents** | 📄 Indexer/gérer documents avec droits | Intermédiaire | 15 min |
| **03_recherche_avancee** | 🔍 Tests et optimisation recherche | Avancé | 20 min |
| **04_maintenance_monitoring** | 🔧 Maintenance et surveillance système | Expert | 30 min |

## 🚀 Démarrage Rapide

### Prérequis
1. **OpenSearch en marche** : `docker-compose up -d`
2. **Python 3.8+** avec Jupyter
3. **Modules requis** : `pip install -r requirements.txt`

### Lancement
```bash
cd notebooks/
jupyter notebook
```

## 📚 Guide d'Utilisation

### 🆕 Nouveau sur le Système ?
**Commencez par :**
1. **01_gestion_clients** - Créer votre premier client
2. **02_gestion_documents** - Indexer vos premiers documents
3. **03_recherche_avancee** - Tester les recherches

### 🔧 Administration Quotidienne ?
**Utilisez :**
- **04_maintenance_monitoring** - Contrôles de santé
- **02_gestion_documents** - Ajouter/supprimer des documents
- **03_recherche_avancee** - Diagnostiquer les problèmes

### 🚨 Problème Urgent ?
**Actions immédiates :**
1. **04_maintenance_monitoring** → `quick_system_check()`
2. **04_maintenance_monitoring** → `diagnose_search_issues()`
3. **04_maintenance_monitoring** → Plan de récupération d'urgence

## 📖 Détail des Notebooks

### 🏢 01 - Gestion des Clients
**Objectif :** Gérer les clients avec isolation complète des données

**Fonctionnalités principales :**
- ✅ Créer un nouveau client (`create_new_client()`)
- 📋 Lister tous les clients avec statistiques
- 🔧 Opérations sur un client spécifique
- 🔄 Vider/réinitialiser un client
- 🗑️ Suppression définitive (sécurisée)

**Cas d'usage typiques :**
- Nouveau client : créer son index dédié
- Audit : voir l'utilisation par client
- Maintenance : nettoyer les clients inactifs

### 📄 02 - Gestion des Documents
**Objectif :** Indexer et gérer les documents avec droits optionnels

**Fonctionnalités principales :**
- 📁 Indexation simple et en lot
- 🔐 Gestion flexible des droits d'accès
- 📋 Liste et analyse des documents
- 🗑️ Suppression sécurisée
- 🔄 Mise à jour des droits

**Système de droits :**
- **Optionnel** : Pas de droits = accessible à tous
- **Flexible** : `["finance", "user:marie.doe", "projet:alpha"]`
- **Évolutif** : Ajout/suppression de droits à tout moment

### 🔍 03 - Recherche Avancée
**Objectif :** Optimiser et analyser les performances de recherche

**Fonctionnalités principales :**
- 🔍 Tests de recherche avec/sans droits
- 👥 Simulation de différents profils utilisateur
- 📊 Analyse de patterns de recherche
- 🎮 Interface interactive complète
- ⚡ Benchmarks de performance

**Métriques analysées :**
- Temps de réponse moyen
- Scores de pertinence
- Impact du filtrage par droits
- Couverture des documents

### 🔧 04 - Maintenance et Monitoring
**Objectif :** Surveiller et maintenir le système en production

**Fonctionnalités principales :**
- 🏥 Contrôle de santé complet
- 📊 Monitoring continu avec alertes
- 🧹 Maintenance et nettoyage
- 💾 Sauvegarde et récupération
- 🔍 Diagnostic approfondi

**Surveillance :**
- **Cluster** : Status, nœuds, shards
- **Performance** : Recherche, CPU, mémoire
- **Stockage** : Taille, croissance, optimisation
- **Alertes** : Seuils configurables

## 🔄 Workflows Recommandés

### 🆕 Nouveau Déploiement
1. **Contrôle initial** (04) → `comprehensive_health_check()`
2. **Créer client** (01) → `create_new_client("mon-client")`
3. **Indexer documents** (02) → `batch_index_directory()`
4. **Tester recherche** (03) → `search_and_display()`

### 📅 Maintenance Quotidienne
1. **Vérification rapide** (04) → `quick_system_check()`
2. **Ajouter documents** (02) → `index_document_with_rights()`
3. **Analyser utilisation** (03) → `analyze_search_patterns()`

### 🔧 Maintenance Hebdomadaire
1. **Santé complète** (04) → `comprehensive_health_check()`
2. **Analyse stockage** (04) → `analyze_storage_usage()`
3. **Nettoyage** (04) → `cleanup_empty_indices()`
4. **Performance** (03) → `benchmark_search_performance()`

### 🚨 Résolution d'Incident
1. **Diagnostic** (04) → `diagnose_search_issues()`
2. **Problèmes courants** (04) → `check_common_issues()`
3. **Plan récupération** (04) → `disaster_recovery_plan()`
4. **Validation** (03) → Tests de recherche

## 🛡️ Sécurité et Bonnes Pratiques

### 🔒 Sécurité
- **Suppressions protégées** : Code commenté par défaut
- **Confirmation requise** : Pour toutes les actions destructives
- **Sauvegarde avant** : Toujours recommandée
- **Logs détaillés** : Traçabilité complète

### 💡 Bonnes Pratiques
- **Tests d'abord** : Utilisez les environnements de test
- **Sauvegarde régulière** : Métadonnées et procédures
- **Monitoring proactif** : Alertes et seuils
- **Documentation** : Plans et historique des changements

### ⚠️ Attention
- **Index vides** : Vérifiez avant suppression
- **Droits complexes** : Testez les scénarios utilisateur
- **Performance** : Surveillez l'impact des modifications
- **Espace disque** : Monitoring continu recommandé

## 🆘 Support et Dépannage

### 🔍 Problèmes Courants

**"Aucun résultat de recherche"**
- Vérifiez l'indexation (02)
- Contrôlez les droits utilisateur (03)
- Analysez les termes de recherche (03)

**"Recherche lente"**
- Benchmark de performance (03)
- Contrôle de santé (04)
- Optimisation des index (04)

**"Erreur de connexion"**
- `docker-compose up -d`
- Vérifiez les ports (9200)
- Contrôle de santé (04)

### 📞 Escalade
1. **Notebook 04** : Diagnostic complet
2. **Logs Docker** : `docker-compose logs opensearch`
3. **Plan récupération** : Procédures d'urgence
4. **Support technique** : Documentation détaillée

## 🎓 Formation et Ressources

### 📚 Apprentissage
- **Débutant** : Notebooks 01 et 02
- **Intermédiaire** : Notebook 03
- **Expert** : Notebook 04

### 🔗 Ressources Externes
- [Documentation OpenSearch](https://opensearch.org/docs/)
- [Guide Elasticsearch/OpenSearch](https://www.elastic.co/guide/)
- [Bonnes pratiques de recherche](https://opendistro.github.io/for-elasticsearch-docs/)

---

## 🎉 Conclusion

Ces notebooks constituent une boîte à outils complète pour gérer efficacement votre système AskMe Search. Ils sont conçus pour évoluer avec vos besoins et s'adapter à votre environnement de production.

**🚀 Prêt à commencer ?** Lancez le notebook 01 et créez votre premier client !

**❓ Questions ?** Consultez la section dépannage ou utilisez les diagnostics intégrés du notebook 04.