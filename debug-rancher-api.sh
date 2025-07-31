#!/bin/bash

# Script de diagnostic complet pour l'API Rancher OVH
# Usage: ./debug-rancher-api.sh

# Configuration avec le nouveau token
RANCHER_BASE_URL="https://jg8s67.9r1m.rancher.ovh.net"
ACCESS_KEY="token-7gqvn"
SECRET_KEY="pr4lxdgqj6cl7wspv5pqn7x894x2vgcd2sv2p7fthxrfp9qq8lvc59"
BEARER_TOKEN="token-7gqvn:pr4lxdgqj6cl7wspv5pqn7x894x2vgcd2sv2p7fthxrfp9qq8lvc59"

echo "🔍 Diagnostic Complet API Rancher OVH"
echo "Base URL: $RANCHER_BASE_URL"
echo "Access Key: $ACCESS_KEY"
echo "Secret Key: ${SECRET_KEY:0:15}..."
echo ""

# Test 1: Endpoint racine sans authentification
echo "🧪 Test 1: Endpoint racine (sans auth)"
response1=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" "$RANCHER_BASE_URL" 2>/dev/null)
echo "Response: $response1"
echo ""

# Test 2: Endpoint /v3 sans authentification  
echo "🧪 Test 2: Endpoint /v3 (sans auth)"
response2=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" "$RANCHER_BASE_URL/v3" 2>/dev/null)
echo "Response: $response2"
echo ""

# Test 3: Bearer Token sur /v3
echo "🧪 Test 3: Bearer Token sur /v3"
response3=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" 2>/dev/null)
echo "Response: $response3"
echo ""

# Test 4: Bearer Token sur /v3/clusters
echo "🧪 Test 4: Bearer Token sur /v3/clusters"
response4=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" 2>/dev/null)
echo "Response: $response4"
echo ""

# Test 5: Basic Auth sur /v3/clusters
echo "🧪 Test 5: Basic Auth sur /v3/clusters"
response5=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -u "$ACCESS_KEY:$SECRET_KEY" \
  -H "Accept: application/json" 2>/dev/null)
echo "Response: $response5"
echo ""

# Test 6: Endpoint /api/v1 (Kubernetes API)
echo "🧪 Test 6: Test endpoint Kubernetes /api/v1"
response6=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/api/v1" \
  -H "Authorization: Bearer $BEARER_TOKEN" 2>/dev/null)
echo "Response: $response6"
echo ""

# Test 7: Endpoint login (si existe)
echo "🧪 Test 7: Test endpoint login"
response7=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST "$RANCHER_BASE_URL/v3-public/localProviders/local?action=login" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"username":"'$ACCESS_KEY'","password":"'$SECRET_KEY'"}' 2>/dev/null)
echo "Response: $response7"
echo ""

# Test 8: Headers détaillés avec verbose
echo "🧪 Test 8: Analyse headers détaillée"
echo "Commande: curl -v -X GET '$RANCHER_BASE_URL/v3/clusters' -H 'Authorization: Bearer $BEARER_TOKEN'"
curl -v -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" 2>&1 | head -20
echo ""

# Test 9: Différents User-Agent
echo "🧪 Test 9: Test avec User-Agent spécifique"
response9=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" \
  -H "User-Agent: rancher/v2.7.0" 2>/dev/null)
echo "Response: $response9"
echo ""

# Test 10: Content-Type différent
echo "🧪 Test 10: Test avec headers complets"
response10=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X GET "$RANCHER_BASE_URL/v3/clusters" \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: XMLHttpRequest" 2>/dev/null)
echo "Response: $response10"
echo ""

echo "🔍 Analyse des résultats:"
echo "- Si tous retournent 401: Problème d'authentification token"
echo "- Si certains retournent 200: Endpoint ou format incorrect"
echo "- Si 403: Token valide mais permissions insuffisantes"
echo "- Si 404: Endpoint n'existe pas"
echo "- Si 500: Erreur serveur"
echo ""
echo "💡 Solutions possibles:"
echo "1. Régénérer le token dans Rancher UI avec permissions complètes"
echo "2. Vérifier que le token n'est pas expiré"
echo "3. Essayer l'authentification via session web d'abord"
echo "4. Contacter support OVH si problème persiste"