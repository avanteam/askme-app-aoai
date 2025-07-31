#!/bin/bash

# Script de diagnostic Rancher API OVH
# Usage: ./test-rancher-api.sh

RANCHER_URL="https://jg8s67.9r1m.rancher.ovh.net/v3"
ACCESS_KEY="token-h9xml"
SECRET_KEY="c92zjjfmw8g58jj6kc86qxr5bx8nk6589pf4wln9rj48tsntmtpxzj"
BEARER_TOKEN="token-h9xml:c92zjjfmw8g58jj6kc86qxr5bx8nk6589pf4wln9rj48tsntmtpxzj"

echo "🔍 Diagnostic Rancher API OVH"
echo "URL: $RANCHER_URL"
echo "Cluster ID connu: c-m-g8b9wrhd"
echo ""

echo "🧪 Test 1: Format OVH recommandé"
response1=$(curl -X GET "$RANCHER_URL/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" 2>/dev/null)
echo "Response: $response1"
echo ""

echo "🧪 Test 2: Test endpoint principal"
response2=$(curl -X GET "$RANCHER_URL" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" 2>/dev/null)
echo "Response: $response2"
echo ""

echo "🧪 Test 3: Test avec Basic Auth"
response3=$(curl -X GET "$RANCHER_URL/clusters" \
  -u "$ACCESS_KEY:$SECRET_KEY" \
  -H "Accept: application/json" 2>/dev/null)
echo "Response: $response3"
echo ""

echo "🧪 Test 4: Test authentification (sans SSL check)"
response4=$(curl -s -k -X GET "$RANCHER_URL/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" 2>/dev/null)
echo "Response: $response4"
echo ""

echo "🧪 Test 5: Vérification token actuel"
echo "Token utilisé: $BEARER_TOKEN"
echo "Access Key: $ACCESS_KEY"
echo "Secret Key: ${SECRET_KEY:0:10}..." 
echo ""

# Test si le token est expiré ou invalide
echo "🔍 Informations diagnostic:"
echo "- Vérifiez que le token n'est pas expiré dans Rancher UI"
echo "- Vérifiez les permissions du token (doit avoir accès API)"
echo "- Le token a peut-être besoin d'un scope spécifique"
echo ""
echo "📝 Pour régénérer un token:"
echo "1. Aller sur: https://jg8s67.9r1m.rancher.ovh.net"
echo "2. Avatar → Account & API Keys"
echo "3. Supprimer l'ancien token si nécessaire"
echo "4. Create API Key avec scope 'No Scope' ou permissions appropriées"