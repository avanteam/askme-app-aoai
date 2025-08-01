#!/usr/bin/env python3
"""
Script de démarrage pour l'interface web AskMe Search
Vérifie les dépendances et démarre l'interface
"""

import sys
import subprocess
from pathlib import Path

def check_and_install_requirements():
    """Vérifier et installer les dépendances"""
    print("🔍 Vérification des dépendances...")
    
    # Vérifier Flask
    try:
        import flask
        print("✅ Flask disponible")
    except ImportError:
        print("📦 Installation de Flask...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'Flask>=2.3.0'], 
                         check=True, capture_output=True)
            print("✅ Flask installé")
        except subprocess.CalledProcessError as e:
            print(f"❌ Échec installation Flask: {e}")
            print("💡 Essayez manuellement: pip install Flask")
            return False
    
    # Vérifier requests
    try:
        import requests
        print("✅ Requests disponible")
    except ImportError:
        print("📦 Installation de requests...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'], 
                         check=True, capture_output=True)
            print("✅ Requests installé")
        except subprocess.CalledProcessError:
            print("❌ Échec installation requests")
            return False
    
    return True

def check_opensearch():
    """Vérifier si OpenSearch est accessible"""
    try:
        import requests
        response = requests.get("http://localhost:9200", timeout=2)
        if response.status_code == 200:
            print("✅ OpenSearch accessible")
            return True
        else:
            print("⚠️ OpenSearch non accessible (sera affiché dans l'interface)")
            return True  # Pas bloquant
    except:
        print("⚠️ OpenSearch non accessible - Démarrez avec: docker-compose up -d")
        return True  # Pas bloquant

def main():
    """Fonction principale"""
    print("🌐 AskMe Search - Interface Web")
    print("=" * 50)
    
    # Vérifier les dépendances
    if not check_and_install_requirements():
        print("\n❌ Échec de l'installation des dépendances")
        print("💡 Installez manuellement: pip install Flask requests")
        return 1
    
    # Vérifier OpenSearch
    check_opensearch()
    
    # Vérifier les templates
    templates_dir = Path("templates")
    if not templates_dir.exists():
        print("❌ Dossier templates manquant")
        return 1
    
    required_templates = ['base.html', 'index.html', 'clients.html']
    missing_templates = []
    for template in required_templates:
        if not (templates_dir / template).exists():
            missing_templates.append(template)
    
    if missing_templates:
        print(f"❌ Templates manquants: {missing_templates}")
        return 1
    
    print("✅ Tous les templates présents")
    
    # Créer les dossiers nécessaires
    Path("clients-data").mkdir(exist_ok=True)
    Path("temp_uploads").mkdir(exist_ok=True)
    
    print("\n🚀 Démarrage de l'interface web...")
    print("📡 Disponible sur: http://localhost:5000")
    print("🔄 Redémarrez avec Ctrl+C puis relancez le script")
    print("=" * 50)
    
    # Importer et démarrer l'interface
    try:
        sys.path.insert(0, str(Path(__file__).parent / "app"))
        from web_interface import app, socketio
        socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n\n👋 Interface arrêtée")
        return 0
    except Exception as e:
        print(f"\n❌ Erreur démarrage: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())