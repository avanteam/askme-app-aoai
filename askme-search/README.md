# 🔍 AskMe Search - Interface Web avec Recherche Vectorielle

Interface web complète pour la recherche documentaire avec support de la recherche vectorielle hybride.

## 🚀 Démarrage Ultra-Rapide

```powershell
# Une seule commande pour tout !
python start.py
```

**Interface** : http://localhost:5000

## ⚙️ Configuration (pour recherche vectorielle)

Créez un fichier `.env` avec votre configuration Azure OpenAI :

```env
# Azure OpenAI (obligatoire pour recherche vectorielle)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-ada-002

# OpenSearch
OPENSEARCH_URL=http://localhost:9200
```

## 📁 Architecture Propre

```
askme-search/
├── 📄 start.py                     ← Script de démarrage UNIQUE
├── 📄 README.md                    ← Ce fichier
├── 📄 requirements.txt             ← Dépendances Python
├── 📄 docker-compose.yml           ← OpenSearch
├── 📁 app/                         ← Application principale
│   ├── web_interface.py            ← Interface web Flask
│   ├── sync_engine.py              ← Moteur de synchronisation
│   └── embedding_service.py        ← Service embeddings Azure
├── 📁 indexing/                    ← Indexation et recherche
│   └── simple_indexer.py           ← Indexeur avec recherche hybride
├── 📁 templates/                   ← Templates HTML
├── 📁 clients-data/                ← Données clients
├── 📁 temp_uploads/                ← Uploads temporaires
└── 📁 docs/                        ← Documentation (notebooks)
```

## 🧠 Test de Recherche Vectorielle

### 1. Créer un Client
- Interface → Clients → Créer → ID: `test-vectoriel`

### 2. Ajouter Documents  
- Client → Upload → Sélectionner PDFs

### 3. Synchroniser avec Embeddings
- Client → Synchronisation → Démarrer
- **Attendre** génération embeddings (essentiel !)

### 4. Tester Recherche Sémantique
- Client → Recherche → Mode "Hybride" ✅
- Test : `travail à distance` doit trouver docs `télétravail`

## ✅ Validation

**Recherche vectorielle fonctionne SI** :
- ✅ Synchronisation génère embeddings
- ✅ `travail à distance` trouve docs `télétravail`  
- ✅ Badge "Hybride" dans résultats
- ✅ Plus de résultats pertinents qu'en textuel

## 🔧 Dépannage

### Pas d'embeddings ?
- Vérifier `.env` et clé Azure OpenAI valide
- Refaire synchronisation complète

### Interface inaccessible ?
- Vérifier OpenSearch : `docker-compose up -d`
- Port 9200 libre : http://localhost:9200

### Import errors ?
- Dépendances : `pip install -r requirements.txt`

## 📞 Support

**Logs importants** :
- Console Python : Erreurs sync/embeddings
- Navigateur F12 : Erreurs interface  
- OpenSearch : http://localhost:9200/_cluster/health

**Un seul script, une architecture claire, recherche vectorielle fonctionnelle !** 🎉