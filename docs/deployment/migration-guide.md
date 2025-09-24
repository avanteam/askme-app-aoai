# 📋 Guide de Migration CosmosDB vers MongoDB

Ce guide détaille la procédure complète de migration d'AskMe depuis CosmosDB vers MongoDB.

## 🎯 Vue d'ensemble

### Avantages de la migration
- ✅ **Indépendance Azure** : Plus de dépendance aux services Azure
- ✅ **Coût réduit** : Élimination des frais CosmosDB
- ✅ **Contrôle total** : Infrastructure sous votre contrôle
- ✅ **Performance** : Répartition de charge avec replica sets
- ✅ **Simplicité** : Une base de données partagée multi-tenant

### Architecture cible
```
┌─────────────────────────────────────────┐
│            KUBERNETES OVH                │
│                                         │
│  ┌─────────────┐    ┌─────────────┐    │
│  │ AskMe App 1 │────│             │    │
│  │ (Avanteam)  │    │             │    │
│  └─────────────┘    │   MongoDB   │    │
│                      │ Replica Set │    │
│  ┌─────────────┐    │             │    │
│  │ AskMe App 2 │────│  - Primary  │    │
│  │ (QSaaS)     │    │  - Secondary│    │
│  └─────────────┘    │  - Secondary│    │
│                      │             │    │
│                      └─────────────┘    │
└─────────────────────────────────────────┘
```

## 📅 Planning de Migration

### Phase 1 : Préparation (1-2 jours)
1. **Installation MongoDB** sur Kubernetes
2. **Configuration réseau** et sécurité
3. **Initialisation des databases** par client
4. **Tests de connectivité**

### Phase 2 : Migration des données (par client)
1. **Migration en mode dry-run** pour validation
2. **Migration production** hors heures d'affluence
3. **Vérification de l'intégrité** des données
4. **Tests fonctionnels** complets

### Phase 3 : Basculement (par client)
1. **Configuration** HISTORY_PROVIDER=MONGODB
2. **Redémarrage** des applications
3. **Tests de production**
4. **Surveillance** et monitoring

### Phase 4 : Nettoyage
1. **Validation** pendant quelques jours/semaines
2. **Désactivation** CosmosDB
3. **Nettoyage** des configurations

## 🛠️ Prérequis

### Technique
- [x] MongoDB déployé et opérationnel
- [x] Accès aux credentials CosmosDB
- [x] Python 3.7+ avec packages requis
- [x] Kubectl configuré pour le cluster

### Packages Python requis
```bash
pip install azure-cosmos motor pymongo httpx
```

## 📦 Installation MongoDB

### Étape 1 : Ajouter le repository Bitnami dans Rancher
```
Rancher UI → Apps & Marketplace → Repositories → Add Repository
Name: bitnami
URL: https://charts.bitnami.com/bitnami
```

### Étape 2 : Installer MongoDB
```
Apps & Marketplace → Charts → MongoDB (by Bitnami) → Install
```

**Configuration recommandée :**
```yaml
architecture: replicaset
replicaCount: 3
auth:
  enabled: true
  rootPassword: "AskMe-MongoDB-2024-Secure!"
persistence:
  enabled: true
  size: 20Gi
```

### Étape 3 : Configuration réseau
```bash
kubectl apply -f mongodb-external-service.yaml
```

### Étape 4 : Initialiser les databases
```powershell
# Windows uniquement (développement)
.\tools\data\scripts\init-mongodb-databases.ps1
```

## 🔄 Migration des Données

### Migration d'un client (exemple : Avanteam)

#### 1. Test en mode dry-run
```powershell
.\scripts\migrate-client-to-mongodb.ps1 -ClientId avanteam -DryRun
```

#### 2. Migration production
```powershell
.\scripts\migrate-client-to-mongodb.ps1 -ClientId avanteam
```

#### 3. Migration manuelle (si nécessaire)
```bash
python tools/data/scripts/migrate-cosmosdb-to-mongodb.py \
  --cosmos-endpoint "https://account.documents.azure.com:443/" \
  --cosmos-key "your-cosmos-key" \
  --cosmos-database "db_conversation_history" \
  --mongo-uri "mongodb://user:pass@mongodb-external:27017/?replicaSet=rs0" \
  --mongo-database "askme_avanteam" \
  --report migration-report.json
```

## ⚙️ Configuration des Applications

### Variables d'environnement par client

#### Client Avanteam
```env
# Basculer vers MongoDB
HISTORY_PROVIDER=MONGODB

# Configuration MongoDB
MONGODB_URI=mongodb://askme_avanteam_user:password@mongodb-external:27017/askme_avanteam?replicaSet=rs0&readPreference=secondaryPreferred
MONGODB_DATABASE=askme_avanteam
MONGODB_ENABLE_FEEDBACK=false

# Désactiver CosmosDB (optionnel)
# AZURE_COSMOSDB_ACCOUNT=
```

#### Client QSaaS
```env
# Basculer vers MongoDB
HISTORY_PROVIDER=MONGODB

# Configuration MongoDB
MONGODB_URI=mongodb://askme_qsaas_user:password@mongodb-external:27017/askme_qsaas?replicaSet=rs0&readPreference=secondaryPreferred
MONGODB_DATABASE=askme_qsaas
MONGODB_ENABLE_FEEDBACK=false
```

### Mise à jour Helm Values

```yaml
# Configuration client via Rancher Catalog
env:
  HISTORY_PROVIDER: "MONGODB"
  MONGODB_URI: "mongodb://askme_avanteam_user:password@mongodb-external:27017/askme_avanteam?replicaSet=rs0&readPreference=secondaryPreferred"
  MONGODB_DATABASE: "askme_avanteam"
```

## 🧪 Tests de Validation

### 1. Test de santé MongoDB
```bash
curl http://localhost:5007/history/ensure
```

### 2. Test API complet
```bash
python tools/data/scripts/test-mongodb-api.py --url http://localhost:5007
```

### 3. Tests fonctionnels
- ✅ Créer une nouvelle conversation
- ✅ Ajouter des messages
- ✅ Lister les conversations
- ✅ Rechercher dans l'historique
- ✅ Supprimer des conversations
- ✅ Tester avec différents utilisateurs

## 📊 Monitoring et Surveillance

### Métriques à surveiller
- **Performances MongoDB** : Latence, throughput
- **Réplication** : Lag entre Primary et Secondary
- **Stockage** : Utilisation disque et croissance
- **Erreurs application** : Logs d'erreur côté AskMe

### Commandes utiles
```bash
# Status MongoDB
kubectl logs -n askme-mongodb deployment/mongodb-shared

# Status replica set
kubectl exec -n askme-mongodb mongodb-shared-0 -- mongosh --eval "rs.status()"

# Métriques par database
kubectl exec -n askme-mongodb mongodb-shared-0 -- mongosh askme_avanteam --eval "db.stats()"
```

## 🚨 Résolution des Problèmes

### Erreurs courantes

#### 1. "Connection refused" MongoDB
**Cause** : Service MongoDB non accessible
**Solution** :
```bash
kubectl get services -n askme-mongodb
kubectl apply -f mongodb-external-service.yaml
```

#### 2. "Authentication failed"
**Cause** : Credentials MongoDB incorrects
**Solution** : Vérifier les users créés et leurs mots de passe

#### 3. "Document too large" (migration)
**Cause** : Documents avec images volumineuses
**Solution** : La compression d'images est automatique dans le code

#### 4. Performance dégradée
**Cause** : Index manquants ou répartition de charge
**Solution** :
```javascript
// Créer les index manuellement si nécessaire
db.conversations.createIndex({userId: 1, updatedAt: -1})
db.messages.createIndex({conversationId: 1, timestamp: 1})
```

## 📈 Rollback (si nécessaire)

En cas de problème majeur, rollback vers CosmosDB :

1. **Restaurer la configuration**
```env
HISTORY_PROVIDER=COSMOSDB
# Réactiver les variables AZURE_COSMOSDB_*
```

2. **Redémarrer l'application**
```bash
kubectl rollout restart deployment/askme-app -n askme-app
```

3. **Vérifier le bon fonctionnement**

## 🎯 Checklist de Migration

### Pré-migration
- [ ] MongoDB installé et opérationnel
- [ ] Databases et users créés pour tous les clients
- [ ] Scripts de migration testés en dry-run
- [ ] Backup des données CosmosDB (si nécessaire)
- [ ] Communication aux équipes

### Par client
- [ ] Migration dry-run réussie
- [ ] Migration production réussie
- [ ] Vérification intégrité des données
- [ ] Configuration HISTORY_PROVIDER=MONGODB
- [ ] Redémarrage application
- [ ] Tests fonctionnels complets
- [ ] Surveillance 24-48h

### Post-migration globale
- [ ] Tous les clients migrés et validés
- [ ] Performance MongoDB satisfaisante
- [ ] Désactivation CosmosDB
- [ ] Documentation mise à jour
- [ ] Formation équipes si nécessaire

## 📞 Support

En cas de problème pendant la migration :

1. **Consulter les logs** détaillés
2. **Vérifier la checklist** ci-dessus
3. **Utiliser les scripts de diagnostic** fournis
4. **Documenter le problème** pour analyse

---

**Note** : Cette migration est réversible. En cas de problème majeur, un rollback vers CosmosDB est possible en quelques minutes.