# Script de build local pour développement
param(
    [string]$Action = "build"
)

# Configuration
$LOCAL_TAG = "askme-app:latest"
$LOCAL_TAG_TIMESTAMP = "askme-app:$(Get-Date -Format 'yyyyMMdd-HHmmss')"

Write-Host "🐳 AskMe Local Build Script" -ForegroundColor Cyan
Write-Host "Action: $Action" -ForegroundColor Yellow

switch ($Action) {
    "build" {
        Write-Host "🔨 Building local Docker image..." -ForegroundColor Green
        docker build -f deployment/docker/WebApp.Dockerfile -t $LOCAL_TAG .
        
        Write-Host "✅ Local build completed!" -ForegroundColor Green
        Write-Host "Images created:" -ForegroundColor Yellow
        Write-Host "  - $LOCAL_TAG" -ForegroundColor White
        Write-Host "  - $LOCAL_TAG_TIMESTAMP" -ForegroundColor White
        
        docker images | Select-String "askme-app"
    }
    
    "run" {
        Write-Host "🏃 Running local container..." -ForegroundColor Green
        docker run -d -p 50505:80 --env-file .env --name askme-local $LOCAL_TAG
        Write-Host "🌐 Application available at: http://localhost:50505" -ForegroundColor Cyan
    }
    
    "stop" {
        Write-Host "🛑 Stopping local container..." -ForegroundColor Yellow
        docker stop askme-local
        docker rm askme-local
    }
    
    default {
        Write-Host "Usage: .\deploy-local.ps1 [build|run|stop]" -ForegroundColor Red
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor Yellow
        Write-Host "  build - Build local Docker image only" -ForegroundColor White
        Write-Host "  run   - Run local container on port 50505" -ForegroundColor White
        Write-Host "  stop  - Stop and remove local container" -ForegroundColor White
    }
}