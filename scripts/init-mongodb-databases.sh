#!/bin/bash

#
# Script d'initialisation MongoDB pour AskMe
# Initialise les databases et users MongoDB pour tous les clients
#
# Usage: ./init-mongodb-databases.sh [mongo-root-password] [namespace] [service-name]
#

set -e  # Arrêter en cas d'erreur

# Configuration par défaut
NAMESPACE="${2:-askme-mongodb}"
SERVICE_NAME="${3:-mongodb-shared}"
MONGO_ROOT_PASSWORD="${1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Fonctions d'affichage
print_info() {
    echo -e "${CYAN}$1${NC}"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

print_header() {
    echo -e "${CYAN}🎯 INITIALISATION MONGODB POUR ASKME${NC}"
    echo "==================================="
}

# Vérification des prérequis
check_prerequisites() {
    print_info "🔍 Vérification des prérequis..."

    # Vérifier kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "  ❌ kubectl non trouvé. Assurez-vous qu'il est installé et dans le PATH."
        return 1
    fi
    print_success "  ✅ kubectl trouvé"

    # Vérifier la connexion au cluster
    if ! kubectl get namespaces &> /dev/null; then
        print_error "  ❌ Impossible de se connecter au cluster Kubernetes"
        return 1
    fi
    print_success "  ✅ Connexion au cluster Kubernetes OK"

    # Vérifier l'existence du namespace
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_error "  ❌ Namespace '$NAMESPACE' non trouvé"
        return 1
    fi
    print_success "  ✅ Namespace '$NAMESPACE' trouvé"

    # Vérifier l'existence du service MongoDB
    if ! kubectl get service "$SERVICE_NAME" -n "$NAMESPACE" &> /dev/null; then
        print_error "  ❌ Service MongoDB '$SERVICE_NAME' non trouvé dans le namespace '$NAMESPACE'"
        return 1
    fi
    print_success "  ✅ Service MongoDB '$SERVICE_NAME' trouvé"

    # Vérifier que les pods MongoDB sont running
    local running_pods
    running_pods=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=mongodb --no-headers 2>/dev/null | grep -c "Running" || true)

    if [ "$running_pods" -gt 0 ]; then
        print_success "  ✅ $running_pods pod(s) MongoDB en cours d'exécution"
    else
        print_error "  ❌ Aucun pod MongoDB en cours d'exécution"
        return 1
    fi

    return 0
}

# Obtenir le mot de passe root MongoDB
get_mongo_root_password() {
    if [ -z "$MONGO_ROOT_PASSWORD" ]; then
        echo -n "Entrez le mot de passe root MongoDB: "
        read -rs MONGO_ROOT_PASSWORD
        echo
    fi
}

# Copier le script vers le pod
copy_script_to_pod() {
    local pod_name=$1

    print_info "📋 Copie du script d'initialisation vers le pod $pod_name..."

    local script_path="$SCRIPT_DIR/init-mongodb-databases.js"

    if [ ! -f "$script_path" ]; then
        print_error "❌ Script JavaScript non trouvé: $script_path"
        return 1
    fi

    if kubectl cp "$script_path" "$NAMESPACE/${pod_name}:/tmp/init-mongodb-databases.js"; then
        print_success "  ✅ Script copié avec succès"
        return 0
    else
        print_error "  ❌ Échec de la copie du script"
        return 1
    fi
}

# Exécuter le script d'initialisation
execute_initialization_script() {
    local pod_name=$1
    local password=$2

    print_info "🚀 Exécution du script d'initialisation..."

    local connection_string="mongodb://root:$password@localhost:27017/?replicaSet=rs0"

    if kubectl exec -n "$NAMESPACE" "$pod_name" -- mongosh "$connection_string" --file /tmp/init-mongodb-databases.js; then
        print_success "✅ Script d'initialisation exécuté avec succès"
        return 0
    else
        print_error "❌ Échec de l'exécution du script d'initialisation"
        return 1
    fi
}

# Nettoyage des fichiers temporaires
cleanup_temp_files() {
    local pod_name=$1

    print_info "🧹 Nettoyage des fichiers temporaires..."

    if kubectl exec -n "$NAMESPACE" "$pod_name" -- rm -f /tmp/init-mongodb-databases.js; then
        print_success "  ✅ Fichiers temporaires supprimés"
    else
        print_warning "  ⚠️  Impossible de supprimer les fichiers temporaires"
    fi
}

# Fonction principale
main() {
    print_header

    # Vérifier les prérequis
    if ! check_prerequisites; then
        print_error "❌ Échec de la vérification des prérequis. Arrêt."
        exit 1
    fi

    # Obtenir le mot de passe root MongoDB
    get_mongo_root_password

    # Trouver le pod MongoDB primary
    print_info "🔍 Recherche du pod MongoDB primary..."

    local pods
    pods=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=mongodb -o name 2>/dev/null)

    if [ -z "$pods" ]; then
        print_error "❌ Aucun pod MongoDB trouvé"
        exit 1
    fi

    # Prendre le premier pod (dans un replica set, n'importe lequel peut exécuter le script)
    local primary_pod
    primary_pod=$(echo "$pods" | head -n1 | cut -d'/' -f2)
    print_success "  ✅ Utilisation du pod: $primary_pod"

    # Copier le script vers le pod
    if ! copy_script_to_pod "$primary_pod"; then
        exit 1
    fi

    # Exécuter le script d'initialisation
    if ! execute_initialization_script "$primary_pod" "$MONGO_ROOT_PASSWORD"; then
        exit 1
    fi

    # Nettoyer les fichiers temporaires
    cleanup_temp_files "$primary_pod"

    print_success "

🎉 INITIALISATION TERMINÉE AVEC SUCCÈS !
=======================================

Prochaines étapes:
1. Sauvegardez les mots de passe générés dans votre gestionnaire de secrets
2. Configurez HISTORY_PROVIDER=MONGODB dans vos fichiers .env clients
3. Redémarrez vos applications AskMe
"

    print_info "💡 Astuce: Utilisez 'kubectl logs -n $NAMESPACE deployment/mongodb-shared' pour voir les logs MongoDB"
}

# Vérification que le script n'est pas sourcé
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi