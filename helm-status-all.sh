#!/bin/bash

# Script de monitoring de tous les clients AskMe déployés avec Helm
# Usage: ./helm-status-all.sh

set -e

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

log_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

log_client() {
    echo -e "${CYAN}🏢 Client: $1${NC}"
}

# Vérifier que Helm est installé
if ! command -v helm &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Helm n'est pas installé"
    exit 1
fi

log_header "AskMe Multi-Client Status Dashboard"

# Lister toutes les releases AskMe
echo ""
log_info "📋 Toutes les releases AskMe:"
helm list --all-namespaces | grep "askme-" | while read -r line; do
    echo "  $line"
done

echo ""
log_info "📊 Status détaillé par client:"
echo ""

# Parcourir tous les clients configurés
if [[ -d "deployments/clients" ]]; then
    for client_dir in deployments/clients/*/; do
        if [[ -d "$client_dir" ]]; then
            client_domain=$(basename "$client_dir")
            values_file="$client_dir/values.yaml"
            
            if [[ -f "$values_file" ]]; then
                # Extraire les informations du client
                client_name=$(yq eval '.client.name' "$values_file" 2>/dev/null || echo "unknown")
                namespace=$(yq eval '.client.namespace' "$values_file" 2>/dev/null || echo "unknown")
                ingress_host=$(yq eval '.ingress.host' "$values_file" 2>/dev/null || echo "unknown")
                release_name="askme-$client_name"
                
                log_client "$client_domain"
                echo "   Release: $release_name"
                echo "   Namespace: $namespace"
                echo "   URL: https://$ingress_host"
                
                # Status Helm
                if helm status "$release_name" --namespace "$namespace" &> /dev/null; then
                    status=$(helm status "$release_name" --namespace "$namespace" -o json 2>/dev/null | jq -r '.info.status' 2>/dev/null || echo "unknown")
                    revision=$(helm status "$release_name" --namespace "$namespace" -o json 2>/dev/null | jq -r '.version' 2>/dev/null || echo "unknown")
                    echo -e "   Status: ${GREEN}$status${NC} (revision: $revision)"
                    
                    # Pods status
                    pod_status=$(kubectl get pods -n "$namespace" -l "app.kubernetes.io/instance=$release_name" --no-headers 2>/dev/null | awk '{
                        if ($3 == "Running") running++; 
                        else if ($3 == "Pending") pending++; 
                        else error++; 
                        total++
                    } END {
                        if (total == 0) print "No pods"
                        else printf "%d Running, %d Pending, %d Error", running+0, pending+0, error+0
                    }')
                    echo "   Pods: $pod_status"
                    
                    # Version de l'image
                    image_version=$(kubectl get deployment -n "$namespace" -l "app.kubernetes.io/instance=$release_name" -o jsonpath='{.items[0].spec.template.spec.containers[0].image}' 2>/dev/null | cut -d':' -f2 || echo "unknown")
                    echo "   Version: $image_version"
                    
                    # Dernière mise à jour
                    last_deployed=$(helm status "$release_name" --namespace "$namespace" -o json 2>/dev/null | jq -r '.info.last_deployed' 2>/dev/null || echo "unknown")
                    if [[ "$last_deployed" != "unknown" && "$last_deployed" != "null" ]]; then
                        last_deployed_formatted=$(date -d "$last_deployed" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$last_deployed")
                        echo "   Déployé: $last_deployed_formatted"
                    fi
                    
                else
                    echo -e "   Status: ${RED}NOT DEPLOYED${NC}"
                fi
                
                echo ""
            fi
        fi
    done
else
    echo "Aucun client configuré dans deployments/clients/"
fi

# Résumé global
echo ""
log_header "Résumé Global"

total_clients=$(find deployments/clients -maxdepth 1 -type d | wc -l)
total_clients=$((total_clients - 1))  # Exclure le répertoire parent

deployed_clients=$(helm list --all-namespaces | grep -c "askme-" || echo 0)

echo "📈 Clients configurés: $total_clients"
echo "🚀 Clients déployés: $deployed_clients"

if [[ $deployed_clients -eq $total_clients ]]; then
    echo -e "${GREEN}✅ Tous les clients sont déployés${NC}"
elif [[ $deployed_clients -gt 0 ]]; then
    echo -e "${YELLOW}⚠️  Certains clients ne sont pas déployés${NC}"
else
    echo -e "${RED}❌ Aucun client déployé${NC}"
fi

echo ""
log_info "Pour déployer un client: ./deploy-helm-client.sh <client-domain>"
log_info "Pour voir le status d'un client: ./deploy-helm-client.sh <client-domain> status"