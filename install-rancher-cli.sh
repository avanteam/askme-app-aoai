#!/bin/bash

# Installation et configuration de Rancher CLI pour OVH
# Usage: ./install-rancher-cli.sh

echo "🐄 Installation Rancher CLI pour OVH"
echo ""

# Configuration
RANCHER_CLI_VERSION="v2.7.0"
RANCHER_URL="https://jg8s67.9r1m.rancher.ovh.net"
ACCESS_KEY="token-7gqvn"
SECRET_KEY="pr4lxdgqj6cl7wspv5pqn7x894x2vgcd2sv2p7fthxrfp9qq8lvc59"
BEARER_TOKEN="token-7gqvn:pr4lxdgqj6cl7wspv5pqn7x894x2vgcd2sv2p7fthxrfp9qq8lvc59"

# Détection de l'OS
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case $ARCH in
    x86_64) ARCH="amd64" ;;
    arm64|aarch64) ARCH="arm64" ;;
    *) echo "❌ Architecture non supportée: $ARCH"; exit 1 ;;
esac

echo "🔍 Système détecté: $OS-$ARCH"

# URL de téléchargement
DOWNLOAD_URL="https://github.com/rancher/cli/releases/download/${RANCHER_CLI_VERSION}/rancher-${OS}-${ARCH}-${RANCHER_CLI_VERSION}.tar.gz"

echo "📥 Téléchargement Rancher CLI $RANCHER_CLI_VERSION..."
echo "URL: $DOWNLOAD_URL"

# Créer un répertoire temporaire
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Télécharger
if ! wget -q "$DOWNLOAD_URL" -O rancher-cli.tar.gz; then
    echo "❌ Échec du téléchargement. Essayons avec curl..."
    if ! curl -L -o rancher-cli.tar.gz "$DOWNLOAD_URL"; then
        echo "❌ Échec du téléchargement avec curl aussi"
        exit 1
    fi
fi

echo "📦 Extraction..."
tar -xzf rancher-cli.tar.gz

# Trouver le binaire
RANCHER_BINARY=$(find . -name "rancher" -type f | head -1)
if [[ -z "$RANCHER_BINARY" ]]; then
    echo "❌ Binaire rancher non trouvé dans l'archive"
    exit 1
fi

echo "📋 Installation..."
# Installation locale (dans le projet)
cp "$RANCHER_BINARY" "/mnt/c/Avanteam/dev/DevRG/askm-app-aoai-testrg2/askme-app-aoai/rancher"
chmod +x "/mnt/c/Avanteam/dev/DevRG/askm-app-aoai-testrg2/askme-app-aoai/rancher"

# Retour au répertoire original
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo "✅ Rancher CLI installé localement"
echo ""

# Test de la version
echo "🧪 Test de la version:"
./rancher --version
echo ""

# Configuration de l'authentification
echo "🔐 Configuration de l'authentification..."

# Méthode 1: Login avec token
echo "Tentative de login avec Bearer token:"
./rancher login "$RANCHER_URL" --token "$BEARER_TOKEN" --skip-verify

if [ $? -eq 0 ]; then
    echo "✅ Authentification réussie avec Bearer token"
else
    echo "⚠️  Échec avec Bearer token, essai avec Access Key/Secret Key:"
    ./rancher login "$RANCHER_URL" --username "$ACCESS_KEY" --password "$SECRET_KEY" --skip-verify
    
    if [ $? -eq 0 ]; then
        echo "✅ Authentification réussie avec Access Key/Secret Key"
    else
        echo "❌ Échec d'authentification"
        echo ""
        echo "💡 Solutions possibles:"
        echo "1. Vérifier que le token n'est pas expiré"
        echo "2. Regenerer un nouveau token avec toutes les permissions"
        echo "3. Essayer l'authentification interactive:"
        echo "   ./rancher login $RANCHER_URL --skip-verify"
        echo ""
        exit 1
    fi
fi

echo ""
echo "🎯 Test des commandes de base:"

# Test liste des clusters
echo "📋 Liste des clusters:"
./rancher clusters ls

echo ""
echo "📋 Liste des projets:"
./rancher projects ls

echo ""
echo "📋 Contexte actuel:"
./rancher context current

echo ""
echo "✅ Rancher CLI configuré et fonctionnel !"
echo ""
echo "🔧 Commandes utiles:"
echo "  ./rancher clusters ls                    # Lister les clusters"
echo "  ./rancher projects ls                    # Lister les projets" 
echo "  ./rancher context switch                 # Changer de contexte"
echo "  ./rancher kubectl get nodes             # Commandes kubectl via Rancher"
echo "  ./rancher apps ls                       # Lister les applications"