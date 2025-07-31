#!/bin/bash

# Script pour récupérer l'ID du cluster Rancher
# Usage: ./get-cluster-id.sh

RANCHER_URL="https://jg8s67.9r1m.rancher.ovh.net"
CLUSTER_NAME="avanteam-mks-cluster"

# Valeurs par défaut pour ce setup OVH
DEFAULT_TOKEN="token-h9xml:c92zjjfmw8g58jj6kc86qxr5bx8nk6589pf4wln9rj48tsntmtpxzj"
DEFAULT_CLUSTER_ID="c-m-g8b9wrhd"

echo "🔍 Configuration Rancher OVH pour '$CLUSTER_NAME'..."
echo "URL Rancher: $RANCHER_URL"
echo ""

# Utiliser le token par défaut s'il n'est pas défini
RANCHER_TOKEN=${RANCHER_TOKEN:-$DEFAULT_TOKEN}

echo "🔗 Test de connexion Rancher..."

# Test avec Bearer Token
bearer_test=$(curl -s -k -H "Authorization: Bearer $RANCHER_TOKEN" "$RANCHER_URL/v3/clusters" 2>/dev/null)

if echo "$bearer_test" | grep -q '"type":"error"'; then
    echo "⚠️  Bearer Token failed, trying Basic Auth..."
    
    # Extraire Access Key et Secret Key
    ACCESS_KEY=$(echo "$RANCHER_TOKEN" | cut -d':' -f1)
    SECRET_KEY=$(echo "$RANCHER_TOKEN" | cut -d':' -f2)
    
    # Test avec Basic Auth
    basic_test=$(curl -s -k -u "$ACCESS_KEY:$SECRET_KEY" "$RANCHER_URL/v3/clusters" 2>/dev/null)
    
    if echo "$basic_test" | grep -q '"type":"error"'; then
        echo "❌ Erreur de connexion Rancher"
        echo "Response: $basic_test"
        echo ""
        echo "Vérifications:"
        echo "1. Token correct: $RANCHER_TOKEN"
        echo "2. URL accessible: $RANCHER_URL"
        echo "3. Permissions API suffisantes"
        exit 1
    else
        echo "✅ Connexion Rancher OK (Basic Auth)"
        clusters_json="$basic_test"
        AUTH_METHOD="basic"
    fi
else
    echo "✅ Connexion Rancher OK (Bearer Token)"
    clusters_json="$bearer_test"
    AUTH_METHOD="bearer"
fi

echo ""
echo "📋 Liste des clusters disponibles:"

# Récupérer et afficher les clusters
clusters_json=$(curl -s -k -H "Authorization: Bearer $RANCHER_TOKEN" "$RANCHER_URL/v3/clusters")

echo "$clusters_json" | jq -r '.data[] | "- Nom: \(.name) | ID: \(.id) | État: \(.state)"'

echo ""
echo "🎯 Recherche du cluster '$CLUSTER_NAME':"

# Chercher le cluster spécifique
cluster_id=$(echo "$clusters_json" | jq -r ".data[] | select(.name==\"$CLUSTER_NAME\") | .id")

if [[ -n "$cluster_id" && "$cluster_id" != "null" ]]; then
    echo "✅ Cluster trouvé!"
    echo ""
    echo "📝 Configuration à utiliser:"
    echo "export RANCHER_URL=\"$RANCHER_URL\""
    echo "export RANCHER_TOKEN=\"$RANCHER_TOKEN\""
    echo "export RANCHER_CLUSTER_ID=\"$cluster_id\""
    echo ""
    echo "🚀 Commandes de test:"
    echo "./deploy-rancher-client.sh askme.avanteam-online.com setup"
else
    echo "❌ Cluster '$CLUSTER_NAME' non trouvé"
    echo ""
    echo "Clusters disponibles:"
    echo "$clusters_json" | jq -r '.data[].name'
fi