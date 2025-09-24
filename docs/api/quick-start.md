# 🚀 Guide de Démarrage Rapide - API REST Externe

## Configuration Minimale (5 minutes)

### 1. **Activer l'API** dans votre `.env` :

```env
# Activer l'API REST externe
EXTERNAL_API_ENABLED=true

# Configuration minimale pour test (remplacez par vos vraies clés)
EXTERNAL_API_KEYS="lighton:sk-ext-lighton-prod-xyz123:*"
```

### 2. **Redémarrer l'application** :

```bash
python -m uvicorn app:app --port 5007 --reload
```

### 3. **Tester immédiatement** :

```bash
# Health check (sans auth)
curl http://localhost:5007/api/v1/health

# Recherche (avec auth)
curl -X POST "http://localhost:5007/api/v1/search" \
  -H "Authorization: Bearer sk-ext-lighton-prod-xyz123" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Comment configurer Azure AD?",
    "max_results": 5,
    "include_metadata": true
  }'
```

## Test Automatisé

Lancez le script de test complet :

```bash
python test_external_api.py
```

## Configuration Production

### Sécurité Renforcée

```env
# API Keys avec restrictions IP
EXTERNAL_API_KEYS="lighton:sk-ext-lighton-prod-xyz123:195.154.1.100,195.154.1.101|partner:sk-ext-partner-abc456:10.0.0.0/8"

# Rate limits personnalisés
EXTERNAL_API_RATE_LIMIT_PER_MINUTE=60
EXTERNAL_API_RATE_LIMIT_PER_HOUR=1000
```

### Multi-Clients

```env
# Format: "client1:key1:ips|client2:key2:ips|..."
EXTERNAL_API_KEYS="lighton:sk-ext-lighton-xyz:*|microsoft:sk-ext-msft-abc:192.168.1.0/24|internal:sk-ext-internal-def:127.0.0.1"
```

## Endpoints Disponibles

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/v1/health` | ❌ | Status de l'API |
| `GET /api/v1/capabilities` | ❌ | Fonctionnalités disponibles |
| `POST /api/v1/search` | ✅ | Recherche principale |
| `POST /api/v1/search/batch` | ✅ | Batch search (V1.1) |

## Monitoring & Logs

Les logs d'audit apparaissent automatiquement :

```
INFO:API auth success - Client: lighton, IP: 195.154.1.100
INFO:API request completed - Client: lighton, Duration: 245.67ms
WARNING:Rate limit exceeded for IP: 192.168.1.100
```

## Intégration LightOn

```python
import httpx

async def ask_documents(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://your-domain.com/api/v1/search",
            headers={
                "Authorization": "Bearer sk-ext-lighton-prod-xyz123"
            },
            json={
                "query": query,
                "max_results": 10,
                "include_metadata": True,
                "use_semantic_search": True
            }
        )
        return response.json()

# Usage
results = await ask_documents("Comment sécuriser Azure Active Directory?")
for result in results["results"]:
    print(f"Score: {result['score']}")
    print(f"Content: {result['content'][:100]}...")
    if result['metadata']:
        print(f"Source: {result['metadata']['filename']}")
        print(f"URL: {result['metadata']['url']}")
```

## Dépannage Rapide

### ❌ "API key is required"
```bash
# Vérifiez le header Authorization
curl -H "Authorization: Bearer YOUR_API_KEY" ...
```

### ❌ "IP address not authorized"
```bash
# Utilisez * pour tous les IPs en test
EXTERNAL_API_KEYS="client:key:*"
```

### ❌ "Search service temporarily unavailable"
```bash
# Vérifiez votre configuration Azure Search
echo $AZURE_SEARCH_SERVICE
echo $AZURE_SEARCH_KEY
```

### ✅ **Tout fonctionne !**

Votre API REST externe est maintenant prête pour LightOn et autres intégrations ! 🎉

## Performance & Sécurité

- ✅ **Rate Limiting** : 60 req/min, 1000 req/heure par défaut
- ✅ **IP Whitelisting** : Configurable par client
- ✅ **Audit Logging** : Toutes les requêtes tracées
- ✅ **Request Validation** : Protection XSS/SQL injection
- ✅ **Production Ready** : Threading safe, memory efficient

---

**📚 Documentation complète** : Voir `docs/api/external-api.md`
**🧪 Tests avancés** : Voir `tests/api/test_external_api.py`