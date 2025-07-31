#!/bin/bash

# Tests d'authentification supplémentaires pour Rancher OVH
# Token confirmé actif avec bonnes permissions

RANCHER_BASE_URL="https://jg8s67.9r1m.rancher.ovh.net"
ACCESS_KEY="token-7gqvn"
SECRET_KEY="pr4lxdgqj6cl7wspv5pqn7x894x2vgcd2sv2p7fthxrfp9qq8lvc59"
BEARER_TOKEN="token-7gqvn:pr4lxdgqj6cl7wspv5pqn7x894x2vgcd2sv2p7fthxrfp9qq8lvc59"

echo "🔍 Tests d'authentification avancés - Token confirmé actif"
echo ""

# Test 1: Espace dans l'Authorization header
echo "🧪 Test 1: Bearer avec espace après 'Bearer '"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json"
echo ""

# Test 2: Sans espace après Bearer
echo "🧪 Test 2: Bearer sans espace"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization:Bearer $BEARER_TOKEN" \
  -H "Accept: application/json"
echo ""

# Test 3: Token en majuscules
echo "🧪 Test 3: BEARER en majuscules"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: BEARER $BEARER_TOKEN" \
  -H "Accept: application/json"
echo ""

# Test 4: Format token différent (sans "token-" prefix)
TOKEN_WITHOUT_PREFIX="7gqvn:pr4lxdgqj6cl7wspv5pqn7x894x2vgcd2sv2p7fthxrfp9qq8lvc59"
echo "🧪 Test 4: Token sans préfixe 'token-'"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $TOKEN_WITHOUT_PREFIX" \
  -H "Accept: application/json"
echo ""

# Test 5: Header X-API-Key (parfois utilisé par OVH)
echo "🧪 Test 5: Header X-API-Key"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "X-API-Key: $BEARER_TOKEN" \
  -H "Accept: application/json"
echo ""

# Test 6: Cookie auth (après login hypothétique)
echo "🧪 Test 6: Test avec session cookie"
cookie_jar=$(mktemp)
# Essayer de récupérer des cookies
curl -s -c "$cookie_jar" "$RANCHER_BASE_URL" > /dev/null
# Utiliser les cookies pour l'auth
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -b "$cookie_jar" \
  -H "Accept: application/json"
rm -f "$cookie_jar"
echo ""

# Test 7: Query parameter auth
echo "🧪 Test 7: Token en query parameter"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters?token=$BEARER_TOKEN" \
  -H "Accept: application/json"
echo ""

# Test 8: Rancher-specific headers
echo "🧪 Test 8: Headers spécifiques Rancher"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" \
  -H "X-API-Bearer-Token: $BEARER_TOKEN" \
  -H "Rancher-Token: $BEARER_TOKEN"
echo ""

# Test 9: Content-Type requis même pour GET
echo "🧪 Test 9: Avec Content-Type même en GET"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json"
echo ""

# Test 10: Endpoint utilisateur pour vérifier le token
echo "🧪 Test 10: Endpoint utilisateurs"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/users" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json"
echo ""

# Test 11: Endpoint token pour vérifier si notre token est listé
echo "🧪 Test 11: Endpoint tokens (liste)"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/tokens" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json"
echo ""

# Test 12: Test avec curl-impersonate (si disponible) ou headers navigateur
echo "🧪 Test 12: Headers navigateur complets"
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json, text/plain, */*" \
  -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
  -H "Referer: https://jg8s67.9r1m.rancher.ovh.net/dashboard/" \
  -H "X-Requested-With: XMLHttpRequest"
echo ""

echo "🔍 Si tous les tests échouent encore avec un token confirmé actif,"
echo "le problème peut être :"
echo "1. Délai d'activation du token (attendre quelques minutes)"
echo "2. Configuration OVH spécifique nécessitant une autre méthode"
echo "3. Token créé mais pas pour le bon cluster/context"
echo "4. Besoin d'authentification web préalable"