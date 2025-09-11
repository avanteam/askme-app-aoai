# Script de déploiement Helm multi-client pour AskMe (Windows PowerShell)
# Usage: .\deploy-helm-client.ps1 <client-domain> [action] [version]
# 
# Actions disponibles:
# - deploy: Déploiement complet (défaut)
# - upgrade: Mise à jour
# - rollback: Rollback vers version précédente
# - uninstall: Désinstaller le client
# - status: Afficher le statut
# - history: Afficher l'historique des releases

param(
    [Parameter(Mandatory=$true)]
    [string]$ClientDomain,
    
    [string]$Action = "deploy",
    
    [string]$Version = "latest"
)

# Fonctions de logging
function Write-Log {
    param(
        [string]$Message,
        [string]$Type = "Info"
    )
    
    switch ($Type) {
        "Info" { Write-Host "[INFO] $Message" -ForegroundColor Green }
        "Warn" { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
        "Error" { Write-Host "[ERROR] $Message" -ForegroundColor Red }
        "Header" { 
            Write-Host "========================================" -ForegroundColor Blue
            Write-Host " $Message" -ForegroundColor Blue
            Write-Host "========================================" -ForegroundColor Blue
        }
    }
}

# Configuration
$CLIENT_DIR = "deployments\clients\$ClientDomain"
$VALUES_FILE = "$CLIENT_DIR\values.yaml"
$CHART_DIR = "helm-chart"

# Validation des paramètres
if (!(Test-Path $VALUES_FILE)) {
    Write-Log "Client $ClientDomain non trouvé dans $CLIENT_DIR" "Error"
    Write-Host "Clients disponibles:"
    if (Test-Path "deployments\clients") {
        Get-ChildItem "deployments\clients" -Directory | ForEach-Object { Write-Host "  $($_.Name)" }
    } else {
        Write-Host "  Aucun client configuré"
    }
    exit 1
}

# Vérifier que Helm est installé
if (!(Get-Command helm -ErrorAction SilentlyContinue)) {
    Write-Log "Helm n'est pas installé. Installez Helm: https://helm.sh/docs/intro/install/" "Error"
    exit 1
}

# Extraire les informations du client depuis values.yaml
try {
    $valuesContent = Get-Content $VALUES_FILE -Raw | ConvertFrom-Yaml
    $CLIENT_NAME = $valuesContent.client.name
    $NAMESPACE = $valuesContent.client.namespace
    $RELEASE_NAME = "askme-$CLIENT_NAME"
} catch {
    Write-Log "Erreur lors de la lecture du fichier values.yaml. Installez le module PowerShell-Yaml si nécessaire." "Error"
    Write-Log "Install-Module powershell-yaml -Force" "Info"
    
    # Fallback: extraction manuelle basique
    $CLIENT_NAME = $ClientDomain -replace '\..*', ''
    $NAMESPACE = "askme-$CLIENT_NAME"
    $RELEASE_NAME = "askme-$CLIENT_NAME"
}

Write-Log "AskMe Helm Deployment - Client: $ClientDomain" "Header"
Write-Log "Release: $RELEASE_NAME"
Write-Log "Namespace: $NAMESPACE"
Write-Log "Action: $Action"

# Créer le namespace s'il n'existe pas
function Create-Namespace {
    try {
        kubectl get namespace $NAMESPACE 2>$null | Out-Null
    } catch {
        Write-Log "Création du namespace $NAMESPACE"
        kubectl create namespace $NAMESPACE
    }
}

# Fonction de déploiement
function Deploy-Client {
    Write-Log "Déploiement du client $ClientDomain..."
    
    Create-Namespace
    
    # Mettre à jour l'image si version spécifiée
    $versionArgs = @()
    if ($Version -ne "latest") {
        $versionArgs += "--set", "image.tag=$Version"
    }
    
    # Déploiement Helm
    $helmArgs = @(
        "upgrade", "--install", $RELEASE_NAME, $CHART_DIR,
        "--namespace", $NAMESPACE,
        "--values", $VALUES_FILE,
        "--wait", "--timeout=10m"
    ) + $versionArgs
    
    & helm $helmArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "✅ Déploiement terminé avec succès!"
        Show-Status
    } else {
        Write-Log "❌ Erreur lors du déploiement" "Error"
        exit 1
    }
}

# Fonction de mise à jour
function Upgrade-Client {
    Write-Log "Mise à jour du client $ClientDomain vers $Version..."
    
    $versionArgs = @()
    if ($Version -ne "latest") {
        $versionArgs += "--set", "image.tag=$Version"
    }
    
    $helmArgs = @(
        "upgrade", $RELEASE_NAME, $CHART_DIR,
        "--namespace", $NAMESPACE,
        "--values", $VALUES_FILE,
        "--wait", "--timeout=10m"
    ) + $versionArgs
    
    & helm $helmArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "✅ Mise à jour terminée avec succès!"
        Show-Status
    } else {
        Write-Log "❌ Erreur lors de la mise à jour" "Error"
        exit 1
    }
}

# Fonction de rollback
function Rollback-Client {
    $revision = if ($Version -eq "latest") { "0" } else { $Version }  # 0 = version précédente
    
    Write-Log "Rollback du client $ClientDomain vers revision $revision..."
    
    helm rollback $RELEASE_NAME $revision --namespace $NAMESPACE --wait
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "✅ Rollback terminé avec succès!"
        Show-Status
    } else {
        Write-Log "❌ Erreur lors du rollback" "Error"
        exit 1
    }
}

# Fonction de désinstallation
function Uninstall-Client {
    Write-Log "⚠️  Désinstallation du client $ClientDomain..." "Warn"
    $confirmation = Read-Host "Êtes-vous sûr de vouloir désinstaller ce client? (y/N)"
    
    if ($confirmation -eq "y" -or $confirmation -eq "Y") {
        helm uninstall $RELEASE_NAME --namespace $NAMESPACE
        
        if ($LASTEXITCODE -eq 0) {
            Write-Log "✅ Client désinstallé avec succès!"
            
            $nsConfirmation = Read-Host "Supprimer le namespace $NAMESPACE? (y/N)"
            if ($nsConfirmation -eq "y" -or $nsConfirmation -eq "Y") {
                kubectl delete namespace $NAMESPACE
                Write-Log "Namespace supprimé"
            }
        } else {
            Write-Log "❌ Erreur lors de la désinstallation" "Error"
        }
    } else {
        Write-Log "Désinstallation annulée"
    }
}

# Fonction de statut
function Show-Status {
    Write-Log "📊 Statut du client $ClientDomain:"
    Write-Host ""
    
    # Statut Helm
    try {
        helm status $RELEASE_NAME --namespace $NAMESPACE 2>$null
    } catch {
        Write-Log "Release non trouvée" "Warn"
    }
    Write-Host ""
    
    # Statut Kubernetes
    Write-Log "Pods:"
    try {
        kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/instance=$RELEASE_NAME" 2>$null
    } catch {
        Write-Log "Aucun pod trouvé" "Warn"
    }
    Write-Host ""
    
    Write-Log "Services:"
    try {
        kubectl get services -n $NAMESPACE 2>$null
    } catch {
        Write-Log "Aucun service trouvé" "Warn"
    }
    Write-Host ""
    
    Write-Log "Ingress:"
    try {
        kubectl get ingress -n $NAMESPACE 2>$null
    } catch {
        Write-Log "Aucun ingress trouvé" "Warn"
    }
    Write-Host ""
    
    # URL d'accès (extraction basique du values.yaml)
    try {
        $ingressHost = (Get-Content $VALUES_FILE | Select-String "host:" | Select-Object -First 1) -replace '.*host:\s*"?([^"]*)"?.*', '$1'
        Write-Log "🌐 URL d'accès: https://$ingressHost"
    } catch {
        Write-Log "🌐 URL d'accès: Voir configuration ingress"
    }
}

# Fonction d'historique
function Show-History {
    Write-Log "📜 Historique des releases pour $ClientDomain:"
    try {
        helm history $RELEASE_NAME --namespace $NAMESPACE 2>$null
    } catch {
        Write-Log "Aucun historique trouvé" "Warn"
    }
}

# Exécution selon l'action
switch ($Action.ToLower()) {
    "deploy" {
        Deploy-Client
    }
    "upgrade" {
        Upgrade-Client
    }
    "rollback" {
        Rollback-Client
    }
    "uninstall" {
        Uninstall-Client
    }
    "status" {
        Show-Status
    }
    "history" {
        Show-History
    }
    default {
        Write-Log "Action non reconnue: $Action" "Error"
        Write-Host "Actions disponibles: deploy, upgrade, rollback, uninstall, status, history"
        exit 1
    }
}