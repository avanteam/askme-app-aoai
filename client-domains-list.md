# 📋 Liste des 10 Clients AskMe à Déployer

## 🎯 Clients de Production

### Clients Confirmés
1. **askme.avanteam-online.com** ✅ (déjà configuré)
   - Namespace: `askme-avanteam-online-com`
   - Type: Client principal - Toutes fonctionnalités
   - Resources: 2 vCPUs, 4Gi RAM

2. **askme-qsaas.avanteam-online.com** ✅ (déjà configuré)  
   - Namespace: `askme-qsaas`
   - Type: QSaaS - Fonctionnalités limitées
   - Resources: 1 vCPU, 2Gi RAM

### Clients à Configurer (8 restants)

3. **client3.domain.com** ⏳
   - Namespace: `askme-client3-domain-com`
   - Type: [À définir]
   - Resources: [À définir]

4. **client4.domain.com** ⏳
   - Namespace: `askme-client4-domain-com`
   - Type: [À définir]
   - Resources: [À définir]

5. **client5.domain.com** ⏳
   - Namespace: `askme-client5-domain-com`
   - Type: [À définir]
   - Resources: [À définir]

6. **client6.domain.com** ⏳
   - Namespace: `askme-client6-domain-com`
   - Type: [À définir]
   - Resources: [À définir]

7. **client7.domain.com** ⏳
   - Namespace: `askme-client7-domain-com`
   - Type: [À définir]
   - Resources: [À définir]

8. **client8.domain.com** ⏳
   - Namespace: `askme-client8-domain-com`
   - Type: [À définir]
   - Resources: [À définir]

9. **client9.domain.com** ⏳
   - Namespace: `askme-client9-domain-com`
   - Type: [À définir]
   - Resources: [À définir]

10. **client10.domain.com** ⏳
    - Namespace: `askme-client10-domain-com`
    - Type: [À définir]
    - Resources: [À définir]

## 🏗️ Types de Clients Suggérés

### 🔥 Premium (2-3 clients)
- **LLM Providers**: Tous (Azure OpenAI, Claude, Gemini, Mistral, OpenAI Direct)
- **Features**: Voice, Image upload, Citations complètes
- **Resources**: 2 vCPUs, 4Gi RAM, 10Gi Storage
- **Price Tier**: Premium

### 💼 Business (3-4 clients)  
- **LLM Providers**: Azure OpenAI, Claude, OpenAI Direct
- **Features**: Voice, Citations limitées
- **Resources**: 1.5 vCPUs, 3Gi RAM, 5Gi Storage
- **Price Tier**: Business

### 🏃 QSaaS (3-4 clients)
- **LLM Providers**: Azure OpenAI uniquement  
- **Features**: Chat basique, pas de voice/images
- **Resources**: 1 vCPU, 2Gi RAM, 2Gi Storage
- **Price Tier**: QSaaS

## 📊 Estimation Resources Totales

### Par Type de Client
```
Premium (3):  6 vCPUs + 12Gi RAM + 30Gi Storage
Business (3): 4.5 vCPUs + 9Gi RAM + 15Gi Storage  
QSaaS (4):    4 vCPUs + 8Gi RAM + 8Gi Storage
Total:        14.5 vCPUs + 29Gi RAM + 53Gi Storage
```

### Clusters Recommandés
```
Production Cluster:
- 6 nœuds B3-16 (4 vCPUs, 16Gi chacun)
- Total: 24 vCPUs, 96Gi RAM
- Répartition: 60% apps, 40% système/overhead

Staging Cluster:  
- 3 nœuds B3-8 (2 vCPUs, 8Gi chacun)
- Total: 6 vCPUs, 24Gi RAM
```

## 🔧 Actions Required

### Prochaines Étapes
1. **Finaliser les domaines** des 8 clients restants
2. **Définir les types** (Premium/Business/QSaaS) par client
3. **Configurer DNS** pour tous les domaines
4. **Préparer certificats SSL** Let's Encrypt
5. **Adapter les Helm values** par type de client

### Template Helm Values par Type
```yaml
# values-premium.yaml
client:
  tier: "premium"
  features:
    voice: true
    images: true
    citations_full: true
  llm_providers: ["azure_openai", "claude", "gemini", "mistral", "openai_direct"]
  resources:
    cpu: "2000m"
    memory: "4Gi"
    storage: "10Gi"

# values-business.yaml  
client:
  tier: "business"
  features:
    voice: true
    citations_limited: true
  llm_providers: ["azure_openai", "claude", "openai_direct"]
  resources:
    cpu: "1500m"
    memory: "3Gi"
    storage: "5Gi"

# values-qsaas.yaml
client:
  tier: "qsaas"
  features:
    basic_chat: true
  llm_providers: ["azure_openai"]
  resources:
    cpu: "1000m"
    memory: "2Gi"
    storage: "2Gi"
```

---

**TODO**: Compléter cette liste avec les vrais domaines clients dès que disponibles.