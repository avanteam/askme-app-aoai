#!/bin/bash

# Script de déploiement AskMe sur Kubernetes OVH
# Usage: ./deploy.sh [build|deploy|update|delete]

set -e

# Configuration
DOCKER_REGISTRY="7wpjr0wh.c1.gra9.container-registry.ovh.net"  # Registry OVH Harbor
APP_NAME="askme-app"
IMAGE_TAG=${IMAGE_TAG:-"latest"}
NAMESPACE="askme-app"

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Vérifier que kubectl est configuré
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl n'est pas installé"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl n'est pas configuré ou le cluster n'est pas accessible"
        exit 1
    fi
    
    log_info "Connexion au cluster Kubernetes OK"
}

# Build et push de l'image Docker
build_and_push() {
    log_info "Construction de l'image Docker..."
    
    # Construction de l'image
    docker build -f WebApp.Dockerfile -t ${DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG} .
    
    log_info "Push de l'image vers le registry..."
    docker push ${DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG}
    
    log_info "Image ${DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG} construite et poussée avec succès"
}

# Déploiement initial
deploy() {
    log_info "Déploiement de AskMe sur Kubernetes..."
    
    # Vérifier que tous les fichiers existent
    required_files=("namespace.yaml" "configmap.yaml" "secret.yaml" "deployment.yaml" "service.yaml" "ingress.yaml")
    for file in "${required_files[@]}"; do
        if [[ ! -f "k8s/$file" ]]; then
            log_error "Fichier k8s/$file introuvable"
            exit 1
        fi
    done
    
    # Mettre à jour l'image dans le deployment
    sed -i "s|your-registry/askme-app:latest|${DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG}|g" k8s/deployment.yaml
    
    # Appliquer les manifestes
    log_info "Création du namespace..."
    kubectl apply -f k8s/namespace.yaml
    
    log_info "Application de la configuration..."
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/secret.yaml
    
    log_info "Déploiement de l'application..."
    kubectl apply -f k8s/deployment.yaml
    kubectl apply -f k8s/service.yaml
    kubectl apply -f k8s/ingress.yaml
    
    log_info "Attente du déploiement..."
    kubectl wait --for=condition=available --timeout=300s deployment/${APP_NAME} -n ${NAMESPACE}
    
    log_info "Déploiement terminé avec succès!"
    show_status
}

# Mise à jour du déploiement
update() {
    log_info "Mise à jour du déploiement..."
    
    # Mettre à jour l'image
    kubectl set image deployment/${APP_NAME} ${APP_NAME}=${DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG} -n ${NAMESPACE}
    
    # Attendre le rollout
    kubectl rollout status deployment/${APP_NAME} -n ${NAMESPACE}
    
    log_info "Mise à jour terminée avec succès!"
    show_status
}

# Afficher le statut
show_status() {
    log_info "Statut du déploiement:"
    kubectl get pods -n ${NAMESPACE}
    kubectl get services -n ${NAMESPACE}
    kubectl get ingress -n ${NAMESPACE}
    
    # Afficher l'URL d'accès
    INGRESS_HOST=$(kubectl get ingress askme-ingress -n ${NAMESPACE} -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "non-configuré")
    log_info "URL d'accès: https://${INGRESS_HOST}"
}

# Supprimer le déploiement
delete() {
    log_warn "Suppression du déploiement AskMe..."
    read -p "Êtes-vous sûr de vouloir supprimer le déploiement? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete -f k8s/ || true
        log_info "Déploiement supprimé"
    else
        log_info "Suppression annulée"
    fi
}

# Logs de l'application
logs() {
    log_info "Logs de l'application:"
    kubectl logs -f -l app=${APP_NAME} -n ${NAMESPACE}
}

# Fonction principale
main() {
    check_kubectl
    
    case "${1:-deploy}" in
        "build")
            build_and_push
            ;;
        "deploy")
            build_and_push
            deploy
            ;;
        "update")
            build_and_push
            update
            ;;
        "status")
            show_status
            ;;
        "logs")
            logs
            ;;
        "delete")
            delete
            ;;
        *)
            echo "Usage: $0 [build|deploy|update|status|logs|delete]"
            echo ""
            echo "Commands:"
            echo "  build   - Construire et pousser l'image Docker"
            echo "  deploy  - Déploiement complet (build + deploy)"
            echo "  update  - Mise à jour avec nouvelle image"
            echo "  status  - Afficher le statut du déploiement"
            echo "  logs    - Afficher les logs de l'application"
            echo "  delete  - Supprimer le déploiement"
            exit 1
            ;;
    esac
}

main "$@"