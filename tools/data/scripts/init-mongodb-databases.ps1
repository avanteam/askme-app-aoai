#Requires -Version 5.1

<#
.SYNOPSIS
    Initialise les bases de données MongoDB pour AskMe
.DESCRIPTION
    Ce script exécute l'initialisation des databases et users MongoDB pour tous les clients AskMe.
    Il utilise kubectl pour se connecter au cluster MongoDB et exécuter le script JavaScript.
.PARAMETER MongoRootPassword
    Mot de passe root MongoDB (optionnel, sera demandé si non fourni)
.PARAMETER Namespace
    Namespace Kubernetes où MongoDB est déployé (défaut: askme-mongodb)
.PARAMETER ServiceName
    Nom du service MongoDB (défaut: mongodb-shared)
.EXAMPLE
    .\init-mongodb-databases.ps1
.EXAMPLE
    .\init-mongodb-databases.ps1 -MongoRootPassword "MySecurePassword" -Namespace askme-mongodb
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$MongoRootPassword,

    [Parameter(Mandatory=$false)]
    [string]$Namespace = "askme-mongodb",

    [Parameter(Mandatory=$false)]
    [string]$ServiceName = "mongodb-shared"
)

# Couleurs pour l'affichage
$ErrorColor = "Red"
$SuccessColor = "Green"
$InfoColor = "Cyan"
$WarningColor = "Yellow"

function Write-ColoredText {
    param($Text, $Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

function Test-Prerequisites {
    Write-ColoredText "🔍 Vérification des prérequis..." $InfoColor

    # Vérifier kubectl
    try {
        $null = kubectl version --client --short 2>$null
        Write-ColoredText "  ✅ kubectl trouvé" $SuccessColor
    } catch {
        Write-ColoredText "  ❌ kubectl non trouvé. Assurez-vous qu'il est installé et dans le PATH." $ErrorColor
        return $false
    }

    # Vérifier la connexion au cluster
    try {
        $null = kubectl get namespaces 2>$null
        Write-ColoredText "  ✅ Connexion au cluster Kubernetes OK" $SuccessColor
    } catch {
        Write-ColoredText "  ❌ Impossible de se connecter au cluster Kubernetes" $ErrorColor
        return $false
    }

    # Vérifier l'existence du namespace
    $namespaceExists = kubectl get namespace $Namespace 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-ColoredText "  ✅ Namespace '$Namespace' trouvé" $SuccessColor
    } else {
        Write-ColoredText "  ❌ Namespace '$Namespace' non trouvé" $ErrorColor
        return $false
    }

    # Vérifier l'existence du service MongoDB
    $serviceExists = kubectl get service $ServiceName -n $Namespace 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-ColoredText "  ✅ Service MongoDB '$ServiceName' trouvé" $SuccessColor
    } else {
        Write-ColoredText "  ❌ Service MongoDB '$ServiceName' non trouvé dans le namespace '$Namespace'" $ErrorColor
        return $false
    }

    # Vérifier que les pods MongoDB sont running
    $mongodbPods = kubectl get pods -n $Namespace -l app.kubernetes.io/name=mongodb --no-headers 2>$null
    $runningPods = ($mongodbPods | Where-Object { $_ -match "Running" }).Count

    if ($runningPods -gt 0) {
        Write-ColoredText "  ✅ $runningPods pod(s) MongoDB en cours d'exécution" $SuccessColor
    } else {
        Write-ColoredText "  ❌ Aucun pod MongoDB en cours d'exécution" $ErrorColor
        return $false
    }

    return $true
}

function Get-MongoRootPassword {
    if (-not $MongoRootPassword) {
        $securePassword = Read-Host "Entrez le mot de passe root MongoDB" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        $MongoRootPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    }
    return $MongoRootPassword
}

function Copy-ScriptToPod {
    param($PodName)

    Write-ColoredText "📋 Copie du script d'initialisation vers le pod $PodName..." $InfoColor

    $scriptPath = Join-Path $PSScriptRoot "init-mongodb-databases.js"

    if (-not (Test-Path $scriptPath)) {
        Write-ColoredText "❌ Script JavaScript non trouvé: $scriptPath" $ErrorColor
        return $false
    }

    try {
        kubectl cp $scriptPath "$Namespace/${PodName}:/tmp/init-mongodb-databases.js"
        if ($LASTEXITCODE -eq 0) {
            Write-ColoredText "  ✅ Script copié avec succès" $SuccessColor
            return $true
        } else {
            Write-ColoredText "  ❌ Échec de la copie du script" $ErrorColor
            return $false
        }
    } catch {
        Write-ColoredText "  ❌ Erreur lors de la copie: $($_.Exception.Message)" $ErrorColor
        return $false
    }
}

function Execute-InitializationScript {
    param($PodName, $Password)

    Write-ColoredText "🚀 Exécution du script d'initialisation..." $InfoColor

    $connectionString = "mongodb://root:$Password@localhost:27017/?replicaSet=rs0"

    try {
        $output = kubectl exec -n $Namespace $PodName -- mongosh "$connectionString" --file /tmp/init-mongodb-databases.js

        if ($LASTEXITCODE -eq 0) {
            Write-ColoredText "✅ Script d'initialisation exécuté avec succès" $SuccessColor

            # Afficher la sortie avec couleurs
            foreach ($line in $output) {
                if ($line -match "✅|🔑|🔗") {
                    Write-ColoredText $line $SuccessColor
                } elseif ($line -match "❌") {
                    Write-ColoredText $line $ErrorColor
                } elseif ($line -match "⚠️|🚀|📋|🔍") {
                    Write-ColoredText $line $WarningColor
                } else {
                    Write-Host $line
                }
            }
            return $true
        } else {
            Write-ColoredText "❌ Échec de l'exécution du script d'initialisation" $ErrorColor
            Write-Host $output
            return $false
        }
    } catch {
        Write-ColoredText "❌ Erreur lors de l'exécution: $($_.Exception.Message)" $ErrorColor
        return $false
    }
}

function Cleanup-TempFiles {
    param($PodName)

    Write-ColoredText "🧹 Nettoyage des fichiers temporaires..." $InfoColor

    try {
        kubectl exec -n $Namespace $PodName -- rm -f /tmp/init-mongodb-databases.js
        Write-ColoredText "  ✅ Fichiers temporaires supprimés" $SuccessColor
    } catch {
        Write-ColoredText "  ⚠️  Impossible de supprimer les fichiers temporaires" $WarningColor
    }
}

# Script principal
function Main {
    Write-ColoredText @"
🎯 INITIALISATION MONGODB POUR ASKME
===================================
"@ $InfoColor

    # Vérifier les prérequis
    if (-not (Test-Prerequisites)) {
        Write-ColoredText "❌ Échec de la vérification des prérequis. Arrêt." $ErrorColor
        exit 1
    }

    # Obtenir le mot de passe root MongoDB
    $MongoRootPassword = Get-MongoRootPassword

    # Trouver le pod MongoDB primary
    Write-ColoredText "🔍 Recherche du pod MongoDB primary..." $InfoColor

    try {
        $pods = kubectl get pods -n $Namespace -l app.kubernetes.io/name=mongodb -o name
        if (-not $pods) {
            Write-ColoredText "❌ Aucun pod MongoDB trouvé" $ErrorColor
            exit 1
        }

        # Prendre le premier pod (dans un replica set, n'importe lequel peut exécuter le script)
        $primaryPod = ($pods[0] -split '/')[1]
        Write-ColoredText "  ✅ Utilisation du pod: $primaryPod" $SuccessColor

    } catch {
        Write-ColoredText "❌ Erreur lors de la recherche des pods: $($_.Exception.Message)" $ErrorColor
        exit 1
    }

    # Copier le script vers le pod
    if (-not (Copy-ScriptToPod -PodName $primaryPod)) {
        exit 1
    }

    # Exécuter le script d'initialisation
    if (-not (Execute-InitializationScript -PodName $primaryPod -Password $MongoRootPassword)) {
        exit 1
    }

    # Nettoyer les fichiers temporaires
    Cleanup-TempFiles -PodName $primaryPod

    Write-ColoredText @"

🎉 INITIALISATION TERMINÉE AVEC SUCCÈS !
=======================================

Prochaines étapes:
1. Sauvegardez les mots de passe générés dans votre gestionnaire de secrets
2. Configurez HISTORY_PROVIDER=MONGODB dans vos fichiers .env clients
3. Redémarrez vos applications AskMe

"@ $SuccessColor

    Write-ColoredText "💡 Astuce: Utilisez 'kubectl logs -n $Namespace deployment/mongodb-shared' pour voir les logs MongoDB" $InfoColor
}

# Exécuter le script principal
Main