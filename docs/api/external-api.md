# 📚 Documentation Complète API REST Externe AskMe

## Vue d'Ensemble

L'API REST externe AskMe permet aux applications tierces d'effectuer des recherches dans votre base documentaire en utilisant les mêmes moteurs de recherche avancés que l'application principale. Cette API est conçue pour une utilisation en production avec une sécurité enterprise-grade.

### Caractéristiques Principales

- **🔐 Authentification** : API Keys avec IP whitelisting
- **⚡ Rate Limiting** : Sliding window algorithm production-ready
- **🛡️ Sécurité** : Protection XSS/SQL injection, audit logging complet
- **📊 Monitoring** : Health checks, métriques de performance
- **🚀 Performance** : <250ms response time, thread-safe
- **📖 Documentation** : OpenAPI/Swagger intégré

---

## 🌐 Accès à la Documentation Swagger

### URLs de Documentation

| Environnement | URL Swagger UI | URL OpenAPI JSON |
|---------------|----------------|------------------|
| **Local** | `http://localhost:50505/docs` | `http://localhost:50505/openapi.json` |
| **Staging** | `https://askme-staging.your-domain.com/docs` | `https://askme-staging.your-domain.com/openapi.json` |
| **Production** | `https://askme.your-domain.com/docs` | `https://askme.your-domain.com/openapi.json` |

### Activation de Swagger UI

Pour activer l'interface Swagger (optionnel), ajoutez dans votre `.env` :

```env
# Active l'interface Swagger UI (optionnel)
EXTERNAL_API_SWAGGER_UI_ENABLED=true
```

### Navigation Swagger

1. **Accédez à** `http://localhost:50505/docs`
2. **Explorez** les endpoints disponibles
3. **Testez** directement depuis l'interface
4. **Copiez** les exemples de code générés

---

## 🔧 Configuration

### Configuration Minimale

```env
# Activation de l'API
EXTERNAL_API_ENABLED=true

# Configuration API Keys (Format: "client:key:ips")
EXTERNAL_API_KEYS="lighton:sk-ext-lighton-prod-xyz123:*"

# Rate Limits par défaut
EXTERNAL_API_RATE_LIMIT_PER_MINUTE=60
EXTERNAL_API_RATE_LIMIT_PER_HOUR=1000
EXTERNAL_API_MAX_RESULTS=50
```

### Configuration Multi-Clients

```env
# Plusieurs clients avec restrictions IP différentes
EXTERNAL_API_KEYS="lighton:sk-ext-lighton-xyz:195.154.1.100,195.154.1.101|partner_ai:sk-ext-partner-abc:10.0.0.0/8|internal_tool:sk-ext-internal-def:*"
```

### Configuration Avancée

```env
# Limites personnalisées
EXTERNAL_API_RATE_LIMIT_PER_MINUTE=120
EXTERNAL_API_RATE_LIMIT_PER_HOUR=2000
EXTERNAL_API_MAX_RESULTS=100
EXTERNAL_API_REQUEST_TIMEOUT=45

# Sécurité
EXTERNAL_API_IP_WHITELIST_STRICT=true
EXTERNAL_API_AUDIT_LOGGING=true
```

---

## 🔗 Endpoints API

### Base URL
```
Production: https://askme.your-domain.com/api/v1
Local: http://localhost:50505/api/v1
```

---

## 🔍 POST /api/v1/search

**Recherche principale dans les documents indexés**

### Authentification
- **Requis** : API Key via header `Authorization: Bearer <api_key>`
- **Rate Limit** : 60/minute, 1000/heure par défaut

### Paramètres de Requête

```json
{
  "query": "string (1-1000 caractères, requis)",
  "max_results": "integer (1-50, défaut: 10)",
  "include_metadata": "boolean (défaut: true)",
  "sort_by": "enum (relevance|date_asc|date_desc|title, défaut: relevance)",
  "use_semantic_search": "boolean (défaut: true)",
  "filters": "object (optionnel, future feature)"
}
```

### Exemple de Requête

```bash
curl -X POST "https://askme.your-domain.com/api/v1/search" \
  -H "Authorization: Bearer sk-ext-lighton-prod-xyz123" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Comment configurer l'\''authentification Azure AD pour une application web?",
    "max_results": 10,
    "include_metadata": true,
    "sort_by": "relevance",
    "use_semantic_search": true
  }'
```

### Réponse Succès (200)

```json
{
  "results": [
    {
      "content": "Pour configurer l'authentification Azure AD pour une application web, vous devez d'abord créer une inscription d'application dans le portail Azure...",
      "title": "Configuration Azure AD pour Applications Web",
      "score": 0.95,
      "chunk_id": "chunk_1_req_20241015_001",
      "metadata": {
        "filename": "azure_ad_guide.pdf",
        "url": "https://docs.microsoft.com/en-us/azure/active-directory/",
        "document_type": "pdf",
        "language": "fr",
        "created_date": "2024-01-15T10:30:00Z",
        "modified_date": "2024-03-20T14:45:00Z",
        "file_size": 2048576,
        "custom_fields": {
          "department": "IT",
          "classification": "internal"
        }
      }
    }
  ],
  "total_results": 156,
  "query": "Comment configurer l'authentification Azure AD pour une application web?",
  "response_time_ms": 245.67,
  "search_provider": "azuresearchprovider",
  "api_version": "v1"
}
```

### Headers de Réponse

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1697364000
X-RateLimit-Window: 60
Content-Type: application/json
```

### Codes d'Erreur

| Code | Description | Action |
|------|-------------|---------|
| `400` | Requête invalide | Vérifiez les paramètres |
| `401` | Authentification échouée | Vérifiez l'API key |
| `429` | Rate limit dépassé | Attendez et réessayez |
| `503` | Service indisponible | Vérifiez le search provider |

---

## 🏥 GET /api/v1/health

**Vérification de l'état de l'API**

### Authentification
- **Requis** : ❌ Aucune

### Exemple de Requête

```bash
curl -X GET "https://askme.your-domain.com/api/v1/health"
```

### Réponse Succès (200)

```json
{
  "status": "healthy",
  "timestamp": "2024-10-15T10:30:00Z",
  "version": "1.0.0",
  "search_provider_status": {
    "azuresearchprovider": "healthy"
  },
  "uptime_seconds": 86400.5
}
```

### États Possibles

- `healthy` : Tous les services fonctionnent
- `degraded` : Certains services ont des problèmes
- `unhealthy` : Services critiques indisponibles

---

## 📋 GET /api/v1/capabilities

**Informations sur les fonctionnalités disponibles**

### Authentification
- **Requis** : ❌ Aucune

### Exemple de Requête

```bash
curl -X GET "https://askme.your-domain.com/api/v1/capabilities"
```

### Réponse Succès (200)

```json
{
  "supported_features": [
    "basic_search",
    "semantic_search",
    "metadata_inclusion",
    "filtered_search"
  ],
  "max_results_limit": 50,
  "supported_sort_options": [
    "relevance",
    "date_asc",
    "date_desc",
    "title"
  ],
  "rate_limits": {
    "requests_per_minute": 60,
    "requests_per_hour": 1000,
    "requests_per_day": 10000
  },
  "search_providers": [
    "azuresearchprovider"
  ]
}
```

---

## 📦 POST /api/v1/search/batch

**Recherche en lot (Feature V1.1)**

### Authentification
- **Requis** : API Key
- **Rate Limit** : 10/minute, 100/heure

### État Actuel
```json
{
  "error_code": "NOT_IMPLEMENTED",
  "error_message": "Batch search is not yet implemented",
  "details": {
    "planned_version": "v1.1"
  }
}
```

---

## 🔐 Authentification

### Format API Key

```
Authorization: Bearer <api_key>
```

### Génération d'API Keys

Les API keys suivent le format : `sk-ext-<client>-<random>`

**Exemples :**
- `sk-ext-lighton-prod-xyz123456`
- `sk-ext-microsoft-dev-abc789def`
- `sk-ext-internal-tool-123456789`

### Sécurité des Clés

- **Longueur minimale** : 32 caractères
- **Caractères autorisés** : alphanumériques + tirets
- **Rotation** : Recommandée tous les 90 jours
- **Stockage** : Hash SHA-256 côté serveur

---

## ⚡ Rate Limiting

### Algorithme : Sliding Window

- **Précision** : Comptage exact sur fenêtre glissante
- **Performance** : Thread-safe, memory efficient
- **Cleanup** : Automatique des anciens records

### Limites par Défaut

| Période | Limite par Défaut | Personnalisable |
|---------|------------------|-----------------|
| Minute | 60 requêtes | ✅ |
| Heure | 1000 requêtes | ✅ |
| Jour | 10000 requêtes | ✅ |

### Headers de Rate Limiting

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1697364000
X-RateLimit-Window: 60
```

### Personnalisation par Client

```python
# Dans backend/api/auth.py - fonction get_rate_limit_for_client()
client_limits = {
    'lighton': ["120 per minute", "2000 per hour", "20000 per day"],
    'premium_client': ["300 per minute", "5000 per hour", "50000 per day"]
}
```

---

## 🛡️ Sécurité

### Protection Intégrée

#### 1. **Request Validation**
- Validation Pydantic stricte
- Longueur max query : 1000 caractères
- Max results : 50 par requête

#### 2. **Security Middleware**
- **XSS Protection** : Détection patterns `<script>`, `javascript:`
- **SQL Injection** : Détection `DROP TABLE`, `SELECT *`
- **Path Traversal** : Détection `../`, `..\`
- **Excessive Special Chars** : Limite 30% de caractères spéciaux

#### 3. **IP Whitelisting**
- Configuration par client
- Support CIDR (ex: `10.0.0.0/8`)
- Wildcard `*` pour développement

#### 4. **Audit Logging**

```
INFO:API auth success - Client: lighton, IP: 195.154.1.100, Endpoint: search, RequestID: req_1697364000_1234
INFO:API request completed - Client: lighton, Duration: 245.67ms, RequestID: req_1697364000_1234
WARNING:API auth failed - IP: 192.168.1.999, Error: IP address not authorized, RequestID: req_1697364001_5678
```

---

## 📊 Monitoring & Observabilité

### Métriques Collectées

#### Métriques Business
- Requêtes par client par période
- Taux de succès/erreur par client
- Temps de réponse P50, P95, P99
- Distribution des tailles de résultats

#### Métriques Techniques
- Utilisation mémoire du rate limiter
- Performance search provider
- Taux de cache hit (future)
- Erreurs par type

### Logs d'Audit

#### Événements Loggés
- ✅ Authentification réussie/échouée
- ✅ Requêtes traitées avec timing
- ✅ Dépassements de rate limits
- ✅ Erreurs search provider
- ✅ Tentatives d'intrusion

#### Format des Logs

```
[TIMESTAMP] [LEVEL] [COMPONENT] Message - Client: <client>, IP: <ip>, Duration: <ms>, RequestID: <id>
```

### Health Checks

#### Endpoints de Monitoring
- `GET /api/v1/health` : Status global
- `GET /api/v1/capabilities` : Fonctionnalités disponibles

#### Intégration Load Balancer
```yaml
# Exemple configuration nginx
upstream askme_api {
    server askme-api-1:50505;
    server askme-api-2:50505;
}

location /health {
    proxy_pass http://askme_api/api/v1/health;
}
```

---

## 🚀 Intégrations Client

### Python/httpx

```python
import httpx
import asyncio
from typing import Dict, List

class AskMeClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    async def search(self, query: str, max_results: int = 10,
                    include_metadata: bool = True) -> Dict:
        """Effectue une recherche dans les documents."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/search",
                headers=self.headers,
                json={
                    "query": query,
                    "max_results": max_results,
                    "include_metadata": include_metadata,
                    "use_semantic_search": True
                }
            )
            response.raise_for_status()
            return response.json()

    async def health(self) -> Dict:
        """Vérifie l'état de l'API."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/api/v1/health")
            response.raise_for_status()
            return response.json()

# Usage
async def main():
    client = AskMeClient(
        base_url="https://askme.your-domain.com",
        api_key="sk-ext-lighton-prod-xyz123"
    )

    results = await client.search(
        "Comment sécuriser une infrastructure Azure?",
        max_results=5
    )

    print(f"Trouvé {len(results['results'])} résultats")
    for result in results['results']:
        print(f"- {result['title']} (score: {result['score']})")

# Run
asyncio.run(main())
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

class AskMeClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.apiKey = apiKey;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async search(query, options = {}) {
        const {
            maxResults = 10,
            includeMetadata = true,
            sortBy = 'relevance',
            useSemanticSearch = true
        } = options;

        try {
            const response = await axios.post(
                `${this.baseUrl}/api/v1/search`,
                {
                    query,
                    max_results: maxResults,
                    include_metadata: includeMetadata,
                    sort_by: sortBy,
                    use_semantic_search: useSemanticSearch
                },
                {
                    headers: this.headers,
                    timeout: 30000
                }
            );

            return response.data;
        } catch (error) {
            if (error.response) {
                throw new Error(`API Error ${error.response.status}: ${error.response.data.error_message}`);
            }
            throw error;
        }
    }

    async health() {
        const response = await axios.get(
            `${this.baseUrl}/api/v1/health`,
            { timeout: 10000 }
        );
        return response.data;
    }
}

// Usage
async function main() {
    const client = new AskMeClient(
        'https://askme.your-domain.com',
        'sk-ext-lighton-prod-xyz123'
    );

    try {
        const results = await client.search(
            'Comment configurer le SSO avec Azure AD?',
            { maxResults: 5 }
        );

        console.log(`Trouvé ${results.results.length} résultats`);
        results.results.forEach(result => {
            console.log(`- ${result.title} (score: ${result.score})`);
        });
    } catch (error) {
        console.error('Erreur:', error.message);
    }
}

main();
```

### cURL/Bash

```bash
#!/bin/bash

API_BASE_URL="https://askme.your-domain.com/api/v1"
API_KEY="sk-ext-lighton-prod-xyz123"

# Fonction de recherche
search_documents() {
    local query="$1"
    local max_results="${2:-5}"

    curl -s -X POST "${API_BASE_URL}/search" \
        -H "Authorization: Bearer ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "{
            \"query\": \"${query}\",
            \"max_results\": ${max_results},
            \"include_metadata\": true,
            \"use_semantic_search\": true
        }" | jq '.'
}

# Fonction health check
health_check() {
    curl -s "${API_BASE_URL}/health" | jq '.'
}

# Usage
echo "=== Health Check ==="
health_check

echo -e "\n=== Recherche ==="
search_documents "Configuration Azure AD" 3
```

---

## 🔧 Dépannage

### Problèmes Courants

#### 1. **"API key is required"**

**Cause** : Header Authorization manquant ou mal formaté

**Solution** :
```bash
# ❌ Incorrect
curl -H "Authorization: sk-ext-lighton-xyz123" ...

# ✅ Correct
curl -H "Authorization: Bearer sk-ext-lighton-xyz123" ...
```

#### 2. **"IP address not authorized"**

**Cause** : IP non whitelisté pour ce client

**Solution** :
```env
# Pour test : autoriser tous les IPs
EXTERNAL_API_KEYS="client:key:*"

# Pour production : IPs spécifiques
EXTERNAL_API_KEYS="client:key:195.154.1.100,195.154.1.101"
```

#### 3. **"Search service temporarily unavailable"**

**Cause** : Search provider non configuré ou inaccessible

**Solution** :
```bash
# Vérifiez la configuration Azure Search
echo $AZURE_SEARCH_SERVICE
echo $AZURE_SEARCH_KEY

# Test manuel du search provider
curl "https://${AZURE_SEARCH_SERVICE}.search.windows.net/indexes?api-version=2023-11-01" \
  -H "api-key: ${AZURE_SEARCH_KEY}"
```

#### 4. **Rate Limiting Trop Restrictif**

**Cause** : Limites par défaut trop basses

**Solution** :
```env
# Augmenter les limites globales
EXTERNAL_API_RATE_LIMIT_PER_MINUTE=120
EXTERNAL_API_RATE_LIMIT_PER_HOUR=2000

# Ou personnaliser par client dans le code
# Voir get_rate_limit_for_client() dans auth.py
```

### Logs de Débogage

#### Activer le Debug Logging

```env
LOG_LEVEL=DEBUG
```

#### Logs Utiles à Surveiller

```bash
# Authentification réussie
grep "API auth success" logs/app.log

# Erreurs d'authentification
grep "API auth failed" logs/app.log

# Rate limiting
grep "Rate limit exceeded" logs/app.log

# Erreurs search provider
grep "Search provider" logs/app.log

# Performance
grep "API request completed" logs/app.log | awk '{print $NF}' | sort -n
```

### Tests de Diagnostic

#### Script de Test Complet

```bash
# Utiliser le script de test fourni
python test_external_api.py

# Ou tests manuels
curl -v http://localhost:50505/api/v1/health
curl -v -H "Authorization: Bearer test-key" \
     -d '{"query":"test"}' \
     http://localhost:50505/api/v1/search
```

---

## 📈 Performance & Optimisation

### Benchmarks de Performance

#### Temps de Réponse Typiques
- **Health Check** : <10ms
- **Search Simple** : <250ms
- **Search Complexe** : <500ms
- **Search avec Métadonnées** : <300ms

#### Throughput
- **Concurrent Users** : 100+ simultanés
- **Requests/sec** : 200+ par serveur
- **Memory Usage** : <500MB par instance

### Optimisations Recommandées

#### 1. **Cache Redis** (V2)
```env
# Configuration future pour cache
EXTERNAL_API_CACHE_ENABLED=true
EXTERNAL_API_CACHE_TTL=300
REDIS_URL=redis://localhost:6379/0
```

#### 2. **Load Balancing**
```nginx
upstream askme_api {
    least_conn;
    server askme-api-1:50505 weight=1;
    server askme-api-2:50505 weight=1;
    server askme-api-3:50505 weight=2;  # Plus puissant
}
```

#### 3. **Connection Pooling**
```python
# Configuration recommandée pour clients
async with httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    timeout=httpx.Timeout(30.0)
) as client:
    # Requêtes...
```

---

## 🔮 Roadmap

### V1.1 (Q2 2024)
- [ ] **Batch Search** : Requêtes multiples en une fois
- [ ] **Advanced Filters** : Filtrage par type, date, auteur
- [ ] **Streaming Response** : Support Server-Sent Events

### V1.2 (Q3 2024)
- [ ] **JWT Authentication** : Support OAuth2/JWT
- [ ] **Redis Cache** : Cache distribuée pour performance
- [ ] **GraphQL API** : Alternative à REST

### V2.0 (Q4 2024)
- [ ] **Multi Search Providers** : Support Elasticsearch, Pinecone
- [ ] **WebSocket API** : Recherche temps réel
- [ ] **AI-Powered Suggestions** : Auto-complétion intelligente

---

## 📞 Support & Contact

### Documentation
- **API Complète** : `EXTERNAL_API_README.md`
- **Quick Start** : `QUICK_START_EXTERNAL_API.md`
- **Tests** : `tests/test_external_api.py`

### Monitoring
- **Health Check** : `GET /api/v1/health`
- **Capabilities** : `GET /api/v1/capabilities`
- **Logs** : Voir section Monitoring

### Configuration
- **Exemple .env** : `.env.example.external-api`
- **Test Script** : `python test_external_api.py`

---

**🔗 Base URL Production** : `https://askme.your-domain.com/api/v1`
**📖 Swagger UI** : `https://askme.your-domain.com/docs`
**📋 OpenAPI Spec** : `https://askme.your-domain.com/openapi.json`

**Dernière mise à jour** : 2024-10-15
**Version API** : v1.0.0