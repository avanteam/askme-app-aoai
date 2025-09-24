# External API pour Recherche Documentaire

## Vue d'ensemble

L'API REST externe permet à des applications tierces (comme LightOn AI) de rechercher dans votre base documentaire via les mêmes moteurs de recherche que l'application AskMe principale.

## Fonctionnalités

### ✅ Implémentées (V1)
- **Authentification API Key** avec whitelisting IP
- **Rate limiting adaptatif** par client
- **Validation et sanitisation** des requêtes
- **Audit logging complet** pour sécurité et compliance
- **Documentation Swagger/OpenAPI** automatique
- **Recherche sémantique** via Azure AI Search
- **Métadonnées complètes** dans les réponses
- **Gestion d'erreurs unifiée** avec codes standardisés
- **Health checks** et monitoring

### 🚧 Prévues (V2+)
- **Authentification JWT/OAuth2** pour clients enterprise
- **Cache Redis** pour optimisation des performances
- **Recherche en batch** pour multiple requêtes simultanées
- **Filtres avancés** par type de document, date, etc.
- **Analytics dashboard** pour les clients
- **Support multi-providers** (Elasticsearch, Pinecone, Weaviate)

## Architecture

```
backend/api/
├── __init__.py          # Module API externe
├── models.py            # Modèles Pydantic avec OpenAPI
├── auth.py              # Authentification et sécurité
├── routes.py            # Routes REST avec Swagger
└── README.md            # Cette documentation

Configuration:
├── .env.example.external-api  # Exemple de configuration
└── requirements.txt           # Dépendances ajoutées
```

## Installation

1. **Installer les dépendances**:
```bash
# Installation selon l'environnement
pip install -r requirements.txt          # Production uniquement
pip install -r requirements-dev.txt      # Développement avec tests
pip install -r requirements-test.txt     # Tests complets (E2E, performance)
```

2. **Configurer l'API** dans votre `.env`:
```env
# Activer l'API externe
EXTERNAL_API_ENABLED=true

# Configurer les clés API (format: "client:key:ips")
EXTERNAL_API_KEYS="lighton:sk-ext-lighton-12345:*|partner:sk-ext-partner-67890:192.168.1.100"

# Limites par défaut
EXTERNAL_API_RATE_LIMIT_PER_MINUTE=60
EXTERNAL_API_RATE_LIMIT_PER_HOUR=1000
EXTERNAL_API_MAX_RESULTS=50
```

3. **Démarrer l'application**:
```bash
python -m uvicorn app:app --port 5007 --reload
```

## Endpoints API

### 🔍 `POST /api/v1/search`
Recherche dans les documents indexés.

**Authentification**: API Key requis
**Rate Limit**: 60/min, 1000/heure par défaut

**Exemple**:
```bash
curl -X POST "http://localhost:5007/api/v1/search" \
  -H "Authorization: Bearer sk-ext-lighton-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Comment configurer Azure AD?",
    "max_results": 10,
    "include_metadata": true,
    "sort_by": "relevance",
    "use_semantic_search": true
  }'
```

**Réponse**:
```json
{
  "results": [
    {
      "content": "Pour configurer Azure AD...",
      "title": "Guide Azure AD",
      "score": 0.95,
      "chunk_id": "chunk_1_req_123",
      "metadata": {
        "filename": "azure_guide.pdf",
        "url": "https://docs.microsoft.com/azure-ad",
        "document_type": "pdf",
        "language": "fr",
        "created_date": "2024-01-15T10:30:00Z"
      }
    }
  ],
  "total_results": 1,
  "query": "Comment configurer Azure AD?",
  "response_time_ms": 245.67,
  "search_provider": "azuresearchprovider",
  "api_version": "v1"
}
```

### 🏥 `GET /api/v1/health`
Vérification de l'état de l'API et des services.

**Authentification**: Aucune
**Exemple**:
```bash
curl http://localhost:5007/api/v1/health
```

### 📋 `GET /api/v1/capabilities`
Informations sur les fonctionnalités disponibles.

**Authentification**: Aucune
**Exemple**:
```bash
curl http://localhost:5007/api/v1/capabilities
```

### 📚 `GET /openapi.json`
Documentation OpenAPI/Swagger complète.

**Interface Swagger**: `/docs` (si configuré)

## Sécurité

### Authentification
- **API Keys** uniques par client
- **Rotation planifiée** (90 jours recommandés)
- **IP Whitelisting** configurable
- **Logging d'audit** complet

### Protection
- **Rate limiting** adaptatif par client
- **Validation stricte** des requêtes
- **Détection d'patterns suspects** (XSS, SQL injection)
- **Sanitisation** automatique des réponses
- **HTTPS obligatoire** en production

### Monitoring
- **Logs d'audit** : authentification, requêtes, erreurs
- **Métriques** : latence, taux de succès, usage par client
- **Alertes** : tentatives d'intrusion, dépassement de quotas

## Configuration Avancée

### Limites par Client
Modifiez `backend/api/auth.py` dans `get_rate_limit_for_client()`:
```python
client_limits = {
    'lighton': ["120 per minute", "2000 per hour"],
    'premium_client': ["300 per minute", "5000 per hour"]
}
```

### Custom Search Provider
L'API utilise le même search provider que votre app principale:
```env
SEARCH_PROVIDER=azure_search
# ou
DATASOURCE_TYPE=AzureCognitiveSearch  # format legacy
```

### Configuration IP Avancée
```env
# Exemples de configuration IP
EXTERNAL_API_KEYS="client1:key1:*|client2:key2:192.168.1.0/24|client3:key3:10.0.0.50,10.0.0.51"
```

## Tests

Lancer les tests unitaires:
```bash
pytest tests/test_external_api.py -v
```

Tests couverts:
- Authentification API Key
- Rate limiting
- Validation des requêtes
- Sécurité et sanitisation
- Intégration search provider
- Gestion d'erreurs

## Dépannage

### Problèmes Courants

1. **"API key is required"**
   - Vérifiez le header `Authorization: Bearer your-api-key`

2. **"IP address not authorized"**
   - Vérifiez la configuration IP dans `EXTERNAL_API_KEYS`

3. **"Search service is temporarily unavailable"**
   - Vérifiez la configuration du search provider (Azure Search, etc.)

4. **Rate limiting**
   - Attendez la fenêtre de temps ou augmentez les limites

### Logs de Débogage

Activez les logs détaillés:
```env
LOG_LEVEL=DEBUG
```

Cherchez dans les logs:
```
INFO:[API] API auth success - Client: lighton
ERROR:[API] Search provider unavailable
WARNING:[API] Rate limit exceeded for IP: x.x.x.x
```

## Exemples d'Intégration

### LightOn AI Integration
```python
import httpx

async def search_documents(query: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://your-askme-api.com/api/v1/search",
            headers={"Authorization": "Bearer sk-ext-lighton-xyz123"},
            json={
                "query": query,
                "max_results": 10,
                "include_metadata": True,
                "use_semantic_search": True
            }
        )
        return response.json()
```

### JavaScript/Node.js
```javascript
const axios = require('axios');

async function searchDocuments(query) {
  const response = await axios.post(
    'https://your-askme-api.com/api/v1/search',
    {
      query: query,
      max_results: 10,
      include_metadata: true
    },
    {
      headers: {
        'Authorization': 'Bearer sk-ext-lighton-xyz123',
        'Content-Type': 'application/json'
      }
    }
  );
  return response.data;
}
```

## Roadmap

### V1.1 (Q2 2024)
- [ ] Recherche en batch
- [ ] Filtres par type de document
- [ ] Métriques client en temps réel

### V1.2 (Q3 2024)
- [ ] Authentification JWT
- [ ] Cache Redis pour performance
- [ ] Dashboard analytics clients

### V2.0 (Q4 2024)
- [ ] Support multi-search-providers
- [ ] WebSocket pour recherche temps réel
- [ ] API GraphQL en complément REST

## Support

- **Documentation**: Ce fichier + Swagger UI
- **Logs**: Vérifiez les logs applicatifs
- **Tests**: `pytest tests/test_external_api.py`
- **Configuration**: `.env.example.external-api`

## Contribution

Pour étendre l'API:
1. Ajoutez des modèles dans `models.py`
2. Implémentez les routes dans `routes.py`
3. Ajoutez l'authentification si nécessaire dans `auth.py`
4. Écrivez des tests dans `tests/test_external_api.py`
5. Mettez à jour cette documentation