#!/bin/bash

# Script de déploiement Helm multi-client pour AskMe
# Usage: ./deploy-helm-client.sh <client-domain> [action] [version]
# 
# Actions disponibles:
# - deploy: Déploiement complet (défaut)
# - upgrade: Mise à jour
# - rollback: Rollback vers version précédente
# - uninstall: Désinstaller le client
# - status: Afficher le statut
# - history: Afficher l'historique des releases

set -e

CLIENT_DOMAIN=$1
ACTION=${2:-"deploy"}
VERSION=${3:-"latest"}

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Validation des paramètres
if [[ -z "$CLIENT_DOMAIN" ]]; then
    log_error "Usage: $0 <client-domain> [action] [version]"
    echo ""
    echo "Clients disponibles:"
    ls -1 deployments/clients/ 2>/dev/null || echo "  Aucun client configuré"
    echo ""
    echo "Actions: deploy, upgrade, rollback, uninstall, status, history"
    exit 1
fi

# Configuration
CLIENT_DIR="deployments/clients/$CLIENT_DOMAIN"
VALUES_FILE="$CLIENT_DIR/values.yaml"
CHART_DIR="helm-chart"

if [[ ! -f "$VALUES_FILE" ]]; then
    log_error "Client $CLIENT_DOMAIN non trouvé dans $CLIENT_DIR"
    echo "Clients disponibles:"
    ls -1 deployments/clients/ 2>/dev/null
    exit 1
fi

# Vérifier yq disponible (priorité au local v4)
YQ_CMD=""
if [[ -f "./yq" ]]; then
    YQ_CMD="./yq"
    log_info "Utilisation de yq local v4"
elif command -v yq &> /dev/null; then
    # Vérifier si c'est la bonne version (v4 mikefarah, pas v3 kislyuk)
    if yq --version 2>/dev/null | grep -q "mikefarah"; then
        YQ_CMD="yq"
    else
        log_error "Version yq incorrecte (besoin mikefarah/yq v4, trouvé kislyuk/yq v3)"
        log_info "Utilisez: wget -qO yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 && chmod +x yq"
        exit 1
    fi
else
    log_error "yq n'est pas installé. Installez yq v4 mikefarah"
    exit 1
fi

# Extraire les informations du client depuis values.yaml
CLIENT_NAME=$($YQ_CMD eval '.client.name' "$VALUES_FILE")
NAMESPACE=$($YQ_CMD eval '.client.namespace' "$VALUES_FILE")
RELEASE_NAME="askme-$CLIENT_NAME"

log_header "AskMe Helm Deployment - Client: $CLIENT_DOMAIN"
log_info "Release: $RELEASE_NAME"
log_info "Namespace: $NAMESPACE"
log_info "Action: $ACTION"

# Vérifier que Helm est installé
if ! command -v helm &> /dev/null; then
    log_error "Helm n'est pas installé. Installez Helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Vérifier que yq est installé
if ! command -v yq &> /dev/null; then
    log_error "yq n'est pas installé. Installez yq: https://github.com/mikefarah/yq#install"
    exit 1
fi

# Créer le namespace s'il n'existe pas
create_namespace() {
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Création du namespace $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
    fi
}

# Fonction de déploiement
deploy_client() {
    log_info "Déploiement du client $CLIENT_DOMAIN..."
    
    create_namespace
    
    # Mettre à jour l'image si version spécifiée
    VERSION_ARGS=""
    if [[ "$VERSION" != "latest" ]]; then
        VERSION_ARGS="--set image.tag=$VERSION"
    fi
    
    # Déploiement Helm
    helm upgrade --install "$RELEASE_NAME" "$CHART_DIR" \
        --namespace "$NAMESPACE" \
        --values "$VALUES_FILE" \
        $VERSION_ARGS \
        --wait --timeout=10m
    
    log_info "✅ Déploiement terminé avec succès!"
    show_status
}

# Fonction de mise à jour
upgrade_client() {
    log_info "Mise à jour du client $CLIENT_DOMAIN vers $VERSION..."
    
    VERSION_ARGS=""
    if [[ "$VERSION" != "latest" ]]; then
        VERSION_ARGS="--set image.tag=$VERSION"
    fi
    
    helm upgrade "$RELEASE_NAME" "$CHART_DIR" \
        --namespace "$NAMESPACE" \
        --values "$VALUES_FILE" \
        $VERSION_ARGS \
        --wait --timeout=10m
    
    log_info "✅ Mise à jour terminée avec succès!"
    show_status
}

# Fonction de rollback
rollback_client() {
    local revision=${VERSION:-"0"}  # 0 = version précédente
    
    log_info "Rollback du client $CLIENT_DOMAIN vers revision $revision..."
    
    helm rollback "$RELEASE_NAME" "$revision" --namespace "$NAMESPACE" --wait
    
    log_info "✅ Rollback terminé avec succès!"
    show_status
}

# Fonction de désinstallation
uninstall_client() {
    log_warn "⚠️  Désinstallation du client $CLIENT_DOMAIN..."
    read -p "Êtes-vous sûr de vouloir désinstaller ce client? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE"
        log_info "✅ Client désinstallé avec succès!"
        
        read -p "Supprimer le namespace $NAMESPACE? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kubectl delete namespace "$NAMESPACE"
            log_info "Namespace supprimé"
        fi
    else
        log_info "Désinstallation annulée"
    fi
}

# Fonction de statut
show_status() {
    log_info "📊 Statut du client $CLIENT_DOMAIN:"
    echo ""
    
    # Statut Helm
    helm status "$RELEASE_NAME" --namespace "$NAMESPACE" 2>/dev/null || log_warn "Release non trouvée"
    echo ""
    
    # Statut Kubernetes
    log_info "Pods:"
    kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/instance=$RELEASE_NAME" 2>/dev/null || log_warn "Aucun pod trouvé"
    echo ""
    
    log_info "Services:"
    kubectl get services -n "$NAMESPACE" 2>/dev/null || log_warn "Aucun service trouvé"
    echo ""
    
    log_info "Ingress:"
    kubectl get ingress -n "$NAMESPACE" 2>/dev/null || log_warn "Aucun ingress trouvé"
    echo ""
    
    # URL d'accès
    INGRESS_HOST=$($YQ_CMD eval '.ingress.host' "$VALUES_FILE")
    log_info "🌐 URL d'accès: https://$INGRESS_HOST"
}

# Fonction d'historique
show_history() {
    log_info "📜 Historique des releases pour $CLIENT_DOMAIN:"
    helm history "$RELEASE_NAME" --namespace "$NAMESPACE" 2>/dev/null || log_warn "Aucun historique trouvé"
}

# Exécution selon l'action
case "$ACTION" in
    "deploy")
        deploy_client
        ;;
    "upgrade")
        upgrade_client
        ;;
    "rollback")
        rollback_client
        ;;
    "uninstall")
        uninstall_client
        ;;
    "status")
        show_status
        ;;
    "history")
        show_history
        ;;
    *)
        log_error "Action non reconnue: $ACTION"
        echo "Actions disponibles: deploy, upgrade, rollback, uninstall, status, history"
        exit 1
        ;;
esac