# 🚀 AskMe Rancher Catalog

Catalog Rancher officiel pour les déploiements AskMe multi-clients avec interface web.

[![Release](https://img.shields.io/github/v/release/avanteam/askme-rancher-catalog)](https://github.com/avanteam/askme-rancher-catalog/releases)
[![Docker](https://img.shields.io/badge/docker-Harbor%20OVH-blue)](https://7wpjr0wh.c1.gra9.container-registry.ovh.net)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.21+-green)](https://kubernetes.io)
[![Rancher](https://img.shields.io/badge/rancher-2.6+-orange)](https://rancher.com)

## 🎯 Fonctionnalités

- **🎛️ Interface Rancher** : Déploiement en 1 clic via formulaire web
- **🏷️ Versioning Git** : Sélection de version (latest, v1.0.0, v1.1.0, etc.)
- **⚙️ Configuration Multi-Client** : Variables d'environnement personnalisables
- **🏢 Multi-Tenant** : Isolation par namespace et projet Rancher
- **🔄 Mises à Jour** : Upgrade et rollback des clients existants
- **🏭 Production Ready** : Templates testés et validés

## 🚀 Installation

### 1. Ajouter le Catalog dans Rancher

**Via Interface Rancher :**
1. **Apps & Marketplace** → **Repositories** → **Create**
2. **Configuration** :
   ```
   Name: askme-catalog
   Target: Git repository containing Helm chart
   Git Repo URL: https://github.com/avanteam/askme-rancher-catalog
   Git Branch: main
   ```
3. **Create**

### 2. Déployer un Client AskMe

1. **Apps & Marketplace** → **Charts** → Chercher **"AskMe"**
2. **Sélectionner la version** souhaitée
3. **Configurer les variables** :
   - Nom et domaine du client
   - API keys (Azure OpenAI, Claude, etc.)
   - Services Azure (Search, Speech, CosmosDB)
   - Fonctionnalités vocales
4. **Install**

## 📋 Configuration

### Variables Principales

| Catégorie | Variable | Description | Exemple |
|-----------|----------|-------------|---------|
| **Client** | `client.name` | Nom du client | `askme-principal` |
| **Client** | `client.domain` | Domaine public | `askme.avanteam-online.com` |
| **LLM** | `llm.defaultProvider` | Provider par défaut | `CLAUDE` |
| **Azure OpenAI** | `azure.openai.key` | Clé API Azure OpenAI | `Ckt6vNVrM1RMG0z...` |
| **Claude** | `claude.apiKey` | Clé API Claude | `sk-ant-api03-GUzW...` |
| **Search** | `azure.search.service` | Service Azure Search | `askmesearchprod` |
| **CosmosDB** | `azure.cosmosdb.account` | Compte CosmosDB | `db-askme-avanteam...` |
| **Voice** | `voice.wakeWords` | Mots-clés vocaux | `Sarah,Richard,Patrick` |

## 🔄 Workflow de Release

### Développeur
```bash
# 1. Développement dans askme-app-aoai
cd askme-app-aoai/
git commit -m "feat: nouvelle fonctionnalité"
git tag v1.2.0
git push origin main --tags
```

### DevOps
```bash
# 2. Mise à jour du catalog
cd askme-rancher-catalog/
# Modifier Chart.yaml : version: 1.2.0
# Modifier values.yaml : image.tag: v1.2.0
git commit -m "feat: Update catalog to app v1.2.0"
git tag v1.2.0
git push origin main --tags
```

## 📁 Structure

```
askme-rancher-catalog/
├── 📦 charts/askme/              # Chart Helm principal
│   ├── Chart.yaml                # Métadonnées et version
│   ├── values.yaml               # Template configurable (200+ vars)
│   ├── questions.yaml            # Interface Rancher (40+ champs)
│   └── templates/                # Templates Kubernetes
├── 🤖 .github/workflows/         # Pipeline CI/CD
├── 📚 docs/                      # Documentation
├── 🧪 test-catalog.sh            # Tests automatisés
└── 📊 index.yaml                 # Index Helm
```

## 🆘 Support

- **GitHub Issues** : [Issues](https://github.com/avanteam/askme-rancher-catalog/issues)
- **Documentation** : [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Contact** : devops@avanteam.com

---

**🚀 Ready to deploy AskMe clients in 1-click via Rancher!** ✨