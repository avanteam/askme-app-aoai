#!/bin/bash

# Script de déploiement Rancher multi-client pour AskMe
# Usage: ./deploy-rancher-client.sh <client-domain> [action] [version]
# 
# Actions disponibles:
# - deploy: Déploiement complet via Rancher (défaut)
# - upgrade: Mise à jour via Rancher
# - rollback: Rollback via Rancher
# - uninstall: Désinstaller le client
# - status: Afficher le statut
# - setup: Setup initial Rancher (import cluster, création projets)

set -e

CLIENT_DOMAIN=$1
ACTION=${2:-"deploy"}
VERSION=${3:-"latest"}

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_rancher() {
    echo -e "${CYAN}[RANCHER]${NC} $1"
}

# Validation des paramètres
if [[ -z "$CLIENT_DOMAIN" ]]; then
    log_error "Usage: $0 <client-domain> [action] [version]"
    echo ""
    echo "Clients disponibles:"
    ls -1 deployments/clients/ 2>/dev/null || echo "  Aucun client configuré"
    echo ""
    echo "Actions: deploy, upgrade, rollback, uninstall, status, setup"
    exit 1
fi

# Configuration
CLIENT_DIR="deployments/clients/$CLIENT_DOMAIN"
VALUES_FILE="$CLIENT_DIR/values.yaml"
RANCHER_VALUES_FILE="$CLIENT_DIR/rancher-values.yaml"
CHART_DIR="helm-chart"

# Configuration Rancher OVH
RANCHER_URL=${RANCHER_URL:-"https://jg8s67.9r1m.rancher.ovh.net/v3"}
RANCHER_TOKEN=${RANCHER_TOKEN:-"token-7gqvn:pr4lxdgqj6cl7wspv5pqn7x894x2vgcd2sv2p7fthxrfp9qq8lvc59"}
RANCHER_CLUSTER_ID=${RANCHER_CLUSTER_ID:-"c-m-g8b9wrhd"}
RANCHER_PROJECT_PREFIX="askme"

if [[ ! -f "$VALUES_FILE" ]]; then
    log_error "Client $CLIENT_DOMAIN non trouvé dans $CLIENT_DIR"
    echo "Clients disponibles:"
    ls -1 deployments/clients/ 2>/dev/null
    exit 1
fi

# Vérifier yq disponible (local ou global)
YQ_CMD="yq"
if [[ -f "./yq" ]]; then
    YQ_CMD="./yq"
elif ! command -v yq &> /dev/null; then
    log_error "yq n'est pas installé. Installez yq ou utilisez ./yq local"
    exit 1
fi

# Extraire les informations du client
CLIENT_NAME=$($YQ_CMD eval '.client.name' "$VALUES_FILE")
NAMESPACE=$($YQ_CMD eval '.client.namespace' "$VALUES_FILE")
RELEASE_NAME="askme-$CLIENT_NAME"
PROJECT_NAME="$RANCHER_PROJECT_PREFIX-$CLIENT_NAME"

log_header "AskMe Rancher Deployment - Client: $CLIENT_DOMAIN"
log_info "Release: $RELEASE_NAME"
log_info "Namespace: $NAMESPACE"
log_info "Project: $PROJECT_NAME"
log_info "Action: $ACTION"

# Vérifier les prérequis
check_prerequisites() {
    local missing_tools=()
    
    command -v helm &> /dev/null || missing_tools+=("helm")
    # yq sera vérifié plus haut
    command -v kubectl &> /dev/null || missing_tools+=("kubectl")
    command -v curl &> /dev/null || missing_tools+=("curl")
    if [[ ! -f "./jq" ]] && ! command -v jq &> /dev/null; then
        missing_tools+=("jq")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Outils manquants: ${missing_tools[*]}"
        echo "Installez ces outils avant de continuer."
        exit 1
    fi
    
    if [[ -z "$RANCHER_TOKEN" ]]; then
        log_warn "RANCHER_TOKEN non défini. Certaines opérations Rancher ne fonctionneront pas."
        log_info "Pour l'obtenir: Rancher UI → User Avatar → Account & API Keys → Create API Key"
    fi
}

# Créer les valeurs Rancher spécifiques
create_rancher_values() {
    log_info "Création du fichier values Rancher..."
    
    cat > "$RANCHER_VALUES_FILE" << EOF
# Configuration Rancher activée pour $CLIENT_DOMAIN
rancher:
  enabled: true
  clusterName: "askme-prod-cluster"
  managementNamespace: "cattle-system"
  
  # Quotas adaptés au type de client
  resourceQuota:
$(if [[ "$CLIENT_NAME" == *"qsaas"* ]]; then
cat << 'EOFQSAAS'
    cpu: "1000m"
    memory: "2Gi"
    storage: "5Gi"
EOFQSAAS
else
cat << 'EOFPROD'
    cpu: "2000m"
    memory: "4Gi"
    storage: "10Gi"
EOFPROD
fi)
  
  rbac:
    enabled: true
    annotations:
      field.cattle.io/projectId: "$RANCHER_CLUSTER_ID:$PROJECT_NAME"
    additionalUsers:
      - name: "admin@avanteam.com"
      - name: "devops@avanteam.com"
  
  monitoring:
    enabled: true
    projectId: "$RANCHER_CLUSTER_ID:$PROJECT_NAME"
  
  alerting:
    enabled: true
    recipients:
      - email: "admin@avanteam.com"
EOF

    log_info "✅ Fichier $RANCHER_VALUES_FILE créé"
}

# Setup initial Rancher (mode kubectl pur)
setup_rancher() {
    log_header "Setup Initial Rancher (Mode kubectl)"
    
    log_info "🐄 Configuration Rancher sans API - Mode kubectl pur"
    log_info "Cluster: $RANCHER_CLUSTER_ID (avanteam-mks-cluster)"
    log_info "Projet: $PROJECT_NAME"
    
    # 1. Créer le namespace s'il n'existe pas
    setup_namespace
    
    # 2. Appliquer les labels et annotations Rancher
    apply_rancher_labels
    
    # 3. Créer les valeurs Rancher pour Helm
    create_rancher_values
    
    # 4. Instructions pour la création manuelle du projet
    show_manual_project_instructions
    
    log_info "✅ Setup Rancher kubectl terminé"
}

# Créer et configurer le namespace
setup_namespace() {
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Création du namespace $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
    else
        log_info "Namespace $NAMESPACE existe déjà"
    fi
}

# Appliquer les labels et annotations Rancher
apply_rancher_labels() {
    log_info "Application des labels et annotations Rancher..."
    
    # Labels Rancher pour le namespace
    kubectl label namespace "$NAMESPACE" \
        field.cattle.io/projectId="$RANCHER_CLUSTER_ID:$PROJECT_NAME" \
        --overwrite 2>/dev/null || log_warn "Label projectId non appliqué"
    
    kubectl label namespace "$NAMESPACE" \
        cattle.io/creator="principal://local://$PROJECT_NAME" \
        --overwrite 2>/dev/null || log_warn "Label creator non appliqué"
    
    # Annotations Rancher pour le namespace
    kubectl annotate namespace "$NAMESPACE" \
        field.cattle.io/projectId="$RANCHER_CLUSTER_ID:$PROJECT_NAME" \
        --overwrite 2>/dev/null || log_warn "Annotation projectId non appliquée"
    
    kubectl annotate namespace "$NAMESPACE" \
        lifecycle.cattle.io/create.namespace-auth="true" \
        --overwrite 2>/dev/null || log_warn "Annotation auth non appliquée"
    
    log_info "✅ Labels et annotations Rancher appliqués"
}

# Instructions pour la création manuelle du projet
show_manual_project_instructions() {
    log_warn "📋 INSTRUCTIONS MANUELLES REQUISES"
    echo ""
    log_info "🎯 Créez le projet '$PROJECT_NAME' dans Rancher UI :"
    log_info "   1. Aller sur: https://jg8s67.9r1m.rancher.ovh.net"
    log_info "   2. Cliquer sur le cluster 'avanteam-mks-cluster'"
    log_info "   3. Aller dans 'Projects/Namespaces'"
    log_info "   4. Cliquer 'Create Project'"
    log_info "   5. Nom du projet: $PROJECT_NAME"
    log_info "   6. Description: Projet AskMe pour $CLIENT_DOMAIN"
    
    # Quotas selon le type de client
    local cpu_quota="2000m"
    local mem_quota="4Gi"
    local storage_quota="10Gi"
    
    if [[ "$CLIENT_NAME" == *"qsaas"* ]]; then
        cpu_quota="1000m"
        mem_quota="2Gi"
        storage_quota="5Gi"
    fi
    
    log_info "   7. Resource Quotas:"
    log_info "      - CPU Limit: $cpu_quota"
    log_info "      - Memory Limit: $mem_quota"
    log_info "      - Storage: $storage_quota"
    log_info "   8. Assigner le namespace: $NAMESPACE"
    log_info "   9. Cliquer 'Create'"
    echo ""
    log_info "⚠️  Une fois le projet créé, le déploiement fonctionnera normalement"
}

# Créer un projet Rancher via API
create_rancher_project() {
    log_rancher "Création du projet Rancher '$PROJECT_NAME'..."
    
    local project_data=$(cat << EOF
{
  "type": "project",
  "clusterId": "$RANCHER_CLUSTER_ID",
  "name": "$PROJECT_NAME",
  "displayName": "AskMe - ${CLIENT_NAME^}",
  "description": "Projet AskMe pour le client $CLIENT_DOMAIN",
  "resourceQuota": {
    "limit": {
      "limitsCpu": "2000m",
      "limitsMemory": "4Gi",
      "persistentVolumeClaims": "10"
    }
  },
  "namespaceDefaultResourceQuota": {
    "limit": {
      "limitsCpu": "2000m",
      "limitsMemory": "4Gi"
    }
  }
}
EOF
)
    
    local response=$(curl -s -k -X POST \
        -H "Authorization: Bearer $RANCHER_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$project_data" \
        "$RANCHER_URL/v3/projects")
    
    if echo "$response" | jq -e '.id' > /dev/null 2>&1; then
        log_info "✅ Projet Rancher créé avec succès"
        
        # Assigner le namespace au projet
        assign_namespace_to_project
    else
        log_warn "⚠️  Projet existe déjà ou erreur lors de la création"
        log_info "Réponse: $(echo "$response" | jq -r '.message // "Aucun message"')"
    fi
}

# Assigner le namespace au projet Rancher
assign_namespace_to_project() {
    log_rancher "Attribution du namespace au projet..."
    
    kubectl annotate namespace "$NAMESPACE" \
        field.cattle.io/projectId="$RANCHER_CLUSTER_ID:$PROJECT_NAME" \
        --overwrite || true
    
    kubectl label namespace "$NAMESPACE" \
        field.cattle.io/projectId="$RANCHER_CLUSTER_ID:$PROJECT_NAME" \
        --overwrite || true
}

# Déploiement via Rancher (mode kubectl)
deploy_client() {
    log_info "Déploiement du client $CLIENT_DOMAIN via Rancher (kubectl)..."
    
    # S'assurer que le setup Rancher est fait
    setup_rancher
    
    # Version args
    VERSION_ARGS=""
    if [[ "$VERSION" != "latest" ]]; then
        VERSION_ARGS="--set image.tag=$VERSION"
    fi
    
    # Déploiement Helm avec configuration Rancher
    log_info "Déploiement Helm avec templates Rancher..."
    helm upgrade --install "$RELEASE_NAME" "$CHART_DIR" \
        --namespace "$NAMESPACE" \
        --values "$VALUES_FILE" \
        --values "$RANCHER_VALUES_FILE" \
        $VERSION_ARGS \
        --wait --timeout=10m
    
    # Post-déploiement: réappliquer les labels Rancher sur les ressources
    post_deployment_rancher_setup
    
    log_info "✅ Déploiement terminé avec succès!"
    show_status
}

# Configuration post-déploiement Rancher
post_deployment_rancher_setup() {
    log_info "Configuration post-déploiement Rancher..."
    
    # Réappliquer les labels sur le namespace (au cas où Helm les aurait modifiés)
    apply_rancher_labels
    
    # Labeller les ressources principales avec les annotations Rancher
    kubectl label deployment "$RELEASE_NAME" \
        field.cattle.io/projectId="$RANCHER_CLUSTER_ID:$PROJECT_NAME" \
        -n "$NAMESPACE" --overwrite 2>/dev/null || true
    
    kubectl label service "$RELEASE_NAME" \
        field.cattle.io/projectId="$RANCHER_CLUSTER_ID:$PROJECT_NAME" \
        -n "$NAMESPACE" --overwrite 2>/dev/null || true
    
    # Vérifier que les pods sont correctement étiquetés
    sleep 5  # Attendre que les pods démarrent
    kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/instance=$RELEASE_NAME" \
        --no-headers 2>/dev/null | while read pod_name rest; do
        kubectl label pod "$pod_name" \
            field.cattle.io/projectId="$RANCHER_CLUSTER_ID:$PROJECT_NAME" \
            -n "$NAMESPACE" --overwrite 2>/dev/null || true
    done
    
    log_info "✅ Configuration Rancher post-déploiement terminée"
}

# Mise à jour via Rancher
upgrade_client() {
    log_info "Mise à jour du client $CLIENT_DOMAIN via Rancher vers $VERSION..."
    
    VERSION_ARGS=""
    if [[ "$VERSION" != "latest" ]]; then
        VERSION_ARGS="--set image.tag=$VERSION"
    fi
    
    # Utiliser les valeurs Rancher si elles existent
    RANCHER_VALUES_ARG=""
    if [[ -f "$RANCHER_VALUES_FILE" ]]; then
        RANCHER_VALUES_ARG="--values $RANCHER_VALUES_FILE"
    fi
    
    helm upgrade "$RELEASE_NAME" "$CHART_DIR" \
        --namespace "$NAMESPACE" \
        --values "$VALUES_FILE" \
        $RANCHER_VALUES_ARG \
        $VERSION_ARGS \
        --wait --timeout=10m
    
    log_info "✅ Mise à jour terminée avec succès!"
    show_status
}

# Rollback via Rancher
rollback_client() {
    local revision=${VERSION:-"0"}
    
    log_info "Rollback du client $CLIENT_DOMAIN vers revision $revision via Rancher..."
    
    helm rollback "$RELEASE_NAME" "$revision" --namespace "$NAMESPACE" --wait
    
    log_info "✅ Rollback terminé avec succès!"
    show_status
}

# Désinstallation (inclut nettoyage Rancher)
uninstall_client() {
    log_warn "⚠️  Désinstallation du client $CLIENT_DOMAIN..."
    read -p "Êtes-vous sûr de vouloir désinstaller ce client? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Désinstaller Helm
        helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE" 2>/dev/null || log_warn "Release Helm non trouvée"
        
        # Supprimer le namespace
        read -p "Supprimer le namespace $NAMESPACE? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kubectl delete namespace "$NAMESPACE" 2>/dev/null || log_warn "Namespace non trouvé"
            log_info "Namespace supprimé"
        fi
        
        # Supprimer le projet Rancher (si token disponible)
        if [[ -n "$RANCHER_TOKEN" ]]; then
            delete_rancher_project
        else
            log_warn "Supprimez manuellement le projet '$PROJECT_NAME' dans Rancher UI"
        fi
        
        # Nettoyer les fichiers locaux
        rm -f "$RANCHER_VALUES_FILE"
        
        log_info "✅ Client désinstallé avec succès!"
    else
        log_info "Désinstallation annulée"
    fi
}

# Supprimer le projet Rancher
delete_rancher_project() {
    log_rancher "Suppression du projet Rancher '$PROJECT_NAME'..."
    
    # Trouver l'ID du projet
    local project_id=$(curl -s -k -H "Authorization: Bearer $RANCHER_TOKEN" \
        "$RANCHER_URL/v3/projects?clusterId=$RANCHER_CLUSTER_ID&name=$PROJECT_NAME" | \
        jq -r '.data[0].id // empty')
    
    if [[ -n "$project_id" ]]; then
        curl -s -k -X DELETE \
            -H "Authorization: Bearer $RANCHER_TOKEN" \
            "$RANCHER_URL/v3/projects/$project_id"
        log_info "✅ Projet Rancher supprimé"
    else
        log_warn "Projet Rancher non trouvé"
    fi
}

# Statut avec informations Rancher
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
    
    # Informations Rancher
    log_rancher "Informations Rancher:"
    echo "  Projet: $PROJECT_NAME"
    echo "  Cluster ID: $RANCHER_CLUSTER_ID"
    if [[ -f "$RANCHER_VALUES_FILE" ]]; then
        echo "  Configuration Rancher: ✅ Activée"
    else
        echo "  Configuration Rancher: ❌ Non configurée"
    fi
    echo ""
    
    # URL d'accès
    INGRESS_HOST=$($YQ_CMD eval '.ingress.host' "$VALUES_FILE")
    log_info "🌐 URL d'accès: https://$INGRESS_HOST"
    log_info "🔗 Rancher UI: $RANCHER_URL/c/$RANCHER_CLUSTER_ID/explorer"
}

# Validation des prérequis
check_prerequisites

# Exécution selon l'action
case "$ACTION" in
    "setup")
        setup_rancher
        ;;
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
    *)
        log_error "Action non reconnue: $ACTION"
        echo "Actions disponibles: setup, deploy, upgrade, rollback, uninstall, status"
        exit 1
        ;;
esac