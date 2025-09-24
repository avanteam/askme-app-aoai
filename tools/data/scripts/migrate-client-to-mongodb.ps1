#Requires -Version 5.1

<#
.SYNOPSIS
    Script d'aide à la migration d'un client AskMe vers MongoDB
.DESCRIPTION
    Ce script facilite la migration d'un client depuis CosmosDB vers MongoDB.
    Il gère la récupération des paramètres, l'exécution de la migration et la validation.
.PARAMETER ClientId
    ID du client à migrer (ex: avanteam, qsaas)
.PARAMETER DryRun
    Mode simulation (pas d'écriture réelle)
.PARAMETER BatchSize
    Taille des lots de migration (défaut: 100)
.EXAMPLE
    .\migrate-client-to-mongodb.ps1 -ClientId avanteam -DryRun
.EXAMPLE
    .\migrate-client-to-mongodb.ps1 -ClientId qsaas -BatchSize 50
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ClientId,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun,

    [Parameter(Mandatory=$false)]
    [int]$BatchSize = 100
)

# Configuration
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Couleurs
$Colors = @{
    Success = "Green"
    Error = "Red"
    Warning = "Yellow"
    Info = "Cyan"
}

function Write-ColoredText {
    param($Text, $Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

function Get-ClientConfiguration {
    param($ClientId)

    Write-ColoredText "📋 Configuration du client: $ClientId" $Colors.Info

    # Configurations prédéfinies
    $clientConfigs = @{
        "avanteam" = @{
            CosmosDatabase = "db_conversation_history"
            MongoDatabase = "askme_avanteam"
            Description = "Client principal Avanteam"
        }
        "qsaas" = @{
            CosmosDatabase = "db_conversation_history_qsaas"
            MongoDatabase = "askme_qsaas"
            Description = "Client QSaaS"
        }
    }

    if ($clientConfigs.ContainsKey($ClientId.ToLower())) {
        $config = $clientConfigs[$ClientId.ToLower()]
        Write-ColoredText "  ✅ Configuration trouvée: $($config.Description)" $Colors.Success
        return $config
    } else {
        Write-ColoredText "  ❌ Configuration non trouvée pour le client: $ClientId" $Colors.Error
        Write-ColoredText "  📋 Clients disponibles: $($clientConfigs.Keys -join ', ')" $Colors.Info
        return $null
    }
}

function Get-CosmosDBCredentials {
    Write-ColoredText "🔑 Récupération des credentials CosmosDB..." $Colors.Info

    # Récupérer depuis les variables d'environnement ou secrets Kubernetes
    $cosmosEndpoint = $env:AZURE_COSMOSDB_ENDPOINT
    $cosmosKey = $env:AZURE_COSMOSDB_ACCOUNT_KEY

    if (-not $cosmosEndpoint) {
        $cosmosAccount = Read-Host "Nom du compte CosmosDB"
        $cosmosEndpoint = "https://$cosmosAccount.documents.azure.com:443/"
    }

    if (-not $cosmosKey) {
        $cosmosKey = Read-Host "Clé d'accès CosmosDB" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($cosmosKey)
        $cosmosKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    }

    return @{
        Endpoint = $cosmosEndpoint
        Key = $cosmosKey
    }
}

function Get-MongoDBCredentials {
    param($ClientId)

    Write-ColoredText "🍃 Configuration MongoDB..." $Colors.Info

    # URI MongoDB avec authentification spécifique au client
    $mongoURI = Read-Host "URI MongoDB pour le client $ClientId (ou Entrée pour défaut)"

    if ([string]::IsNullOrEmpty($mongoURI)) {
        # URI par défaut vers le service Kubernetes
        $mongoURI = "mongodb://mongodb-external:27017/?replicaSet=rs0&readPreference=secondaryPreferred"
        Write-ColoredText "  🔧 Utilisation de l'URI par défaut: $mongoURI" $Colors.Info
    }

    return @{
        URI = $mongoURI
    }
}

function Test-Prerequisites {
    Write-ColoredText "🔍 Vérification des prérequis..." $Colors.Info

    # Vérifier Python
    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match "Python 3\.") {
            Write-ColoredText "  ✅ Python trouvé: $pythonVersion" $Colors.Success
        } else {
            Write-ColoredText "  ❌ Python 3.x requis" $Colors.Error
            return $false
        }
    } catch {
        Write-ColoredText "  ❌ Python non trouvé" $Colors.Error
        return $false
    }

    # Vérifier les dépendances Python
    $requiredPackages = @("azure-cosmos", "motor", "pymongo")
    foreach ($package in $requiredPackages) {
        try {
            $null = python -c "import $($package.Replace('-', '_'))" 2>&1
            Write-ColoredText "  ✅ Package Python: $package" $Colors.Success
        } catch {
            Write-ColoredText "  ❌ Package Python manquant: $package" $Colors.Error
            Write-ColoredText "    💡 Installez avec: pip install $package" $Colors.Info
            return $false
        }
    }

    # Vérifier le script de migration
    $migrationScript = Join-Path $ScriptDir "migrate-cosmosdb-to-mongodb.py"
    if (Test-Path $migrationScript) {
        Write-ColoredText "  ✅ Script de migration trouvé" $Colors.Success
    } else {
        Write-ColoredText "  ❌ Script de migration non trouvé: $migrationScript" $Colors.Error
        return $false
    }

    return $true
}

function Start-Migration {
    param(
        $ClientConfig,
        $CosmosCredentials,
        $MongoCredentials,
        [bool]$DryRun,
        [int]$BatchSize
    )

    Write-ColoredText "🚀 Démarrage de la migration..." $Colors.Info

    $migrationScript = Join-Path $ScriptDir "migrate-cosmosdb-to-mongodb.py"
    $reportFile = Join-Path $ScriptDir "migration-report-$ClientId-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"

    # Construire les arguments
    $args = @(
        $migrationScript,
        "--cosmos-endpoint", $CosmosCredentials.Endpoint,
        "--cosmos-key", $CosmosCredentials.Key,
        "--cosmos-database", $ClientConfig.CosmosDatabase,
        "--cosmos-container", "conversations",
        "--mongo-uri", $MongoCredentials.URI,
        "--mongo-database", $ClientConfig.MongoDatabase,
        "--batch-size", $BatchSize,
        "--report", $reportFile
    )

    if ($DryRun) {
        $args += "--dry-run"
        Write-ColoredText "  🧪 Mode DRY-RUN activé" $Colors.Warning
    }

    Write-ColoredText "  📄 Rapport sera sauvegardé dans: $reportFile" $Colors.Info
    Write-ColoredText "" # Ligne vide

    # Exécuter la migration
    try {
        $process = Start-Process -FilePath "python" -ArgumentList $args -Wait -PassThru -NoNewWindow

        if ($process.ExitCode -eq 0) {
            Write-ColoredText "✅ Migration terminée avec succès !" $Colors.Success

            # Afficher le contenu du rapport si disponible
            if (Test-Path $reportFile) {
                Write-ColoredText "📊 Résumé du rapport:" $Colors.Info
                $report = Get-Content $reportFile | ConvertFrom-Json
                $stats = $report.statistics

                Write-ColoredText "  Conversations: $($stats.conversations_migrated)/$($stats.conversations_found)" $Colors.Info
                Write-ColoredText "  Messages: $($stats.messages_migrated)/$($stats.messages_found)" $Colors.Info
                Write-ColoredText "  Utilisateurs: $($stats.users_processed.Count)" $Colors.Info

                if ($stats.total_errors -gt 0) {
                    Write-ColoredText "  ⚠️ Erreurs: $($stats.total_errors)" $Colors.Warning
                }
            }

            return $true
        } else {
            Write-ColoredText "❌ Migration échouée (code: $($process.ExitCode))" $Colors.Error
            return $false
        }
    } catch {
        Write-ColoredText "💥 Erreur lors de l'exécution: $($_.Exception.Message)" $Colors.Error
        return $false
    }
}

function Show-PostMigrationInstructions {
    param($ClientId, $ClientConfig, $DryRun)

    if ($DryRun) {
        Write-ColoredText @"

📋 PROCHAINES ÉTAPES (après DRY-RUN réussi):
==========================================
1. Relancer sans --DryRun pour la migration réelle
2. Configurer les variables d'environnement du client
3. Redémarrer l'application

"@ $Colors.Info
    } else {
        Write-ColoredText @"

📋 PROCHAINES ÉTAPES:
====================
1. Configurer les variables d'environnement:
   HISTORY_PROVIDER=MONGODB
   MONGODB_DATABASE=$($ClientConfig.MongoDatabase)

2. Redémarrer l'application AskMe pour le client $ClientId

3. Tester les fonctionnalités d'historique

4. Une fois validé, désactiver CosmosDB pour ce client

"@ $Colors.Success
    }
}

# Script principal
function Main {
    Write-ColoredText @"
🔄 MIGRATION CLIENT ASKME - COSMOSDB → MONGODB
==============================================
Client: $ClientId
Mode: $(if ($DryRun) { "DRY-RUN (simulation)" } else { "PRODUCTION" })
Batch Size: $BatchSize

"@ $Colors.Info

    # 1. Vérifier les prérequis
    if (-not (Test-Prerequisites)) {
        Write-ColoredText "❌ Prérequis non satisfaits. Arrêt." $Colors.Error
        exit 1
    }

    # 2. Récupérer la configuration client
    $clientConfig = Get-ClientConfiguration -ClientId $ClientId
    if (-not $clientConfig) {
        exit 1
    }

    # 3. Récupérer les credentials CosmosDB
    $cosmosCredentials = Get-CosmosDBCredentials
    if (-not $cosmosCredentials.Key) {
        Write-ColoredText "❌ Credentials CosmosDB invalides" $Colors.Error
        exit 1
    }

    # 4. Récupérer la configuration MongoDB
    $mongoCredentials = Get-MongoDBCredentials -ClientId $ClientId

    # 5. Confirmation avant migration (si pas DRY-RUN)
    if (-not $DryRun) {
        Write-ColoredText "⚠️ ATTENTION: Migration en mode PRODUCTION" $Colors.Warning
        Write-ColoredText "  Source: $($clientConfig.CosmosDatabase)" $Colors.Info
        Write-ColoredText "  Target: $($clientConfig.MongoDatabase)" $Colors.Info
        $confirmation = Read-Host "Continuer? (oui/non)"

        if ($confirmation.ToLower() -ne "oui") {
            Write-ColoredText "❌ Migration annulée par l'utilisateur" $Colors.Warning
            exit 0
        }
    }

    # 6. Exécuter la migration
    $success = Start-Migration -ClientConfig $clientConfig -CosmosCredentials $cosmosCredentials -MongoCredentials $mongoCredentials -DryRun $DryRun -BatchSize $BatchSize

    # 7. Instructions post-migration
    if ($success) {
        Show-PostMigrationInstructions -ClientId $ClientId -ClientConfig $clientConfig -DryRun $DryRun
    }

    exit $(if ($success) { 0 } else { 1 })
}

# Exécuter le script principal
Main