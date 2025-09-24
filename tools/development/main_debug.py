import uvicorn
import subprocess
import sys
import time
import os

def check_port_in_use(port):
    """Vérifie si un port est déjà utilisé"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(["netstat", "-an"], capture_output=True, text=True)
            return f":{port}" in result.stdout
        else:  # Linux/Mac
            result = subprocess.run(["lsof", f"-i:{port}"], capture_output=True, text=True)
            return result.returncode == 0
    except:
        return False

def start_mongodb_tunnel():
    """Démarre le tunnel MongoDB vers Kubernetes"""
    print("\n[MongoDB] Démarrage du tunnel Kubernetes...")

    try:
        # Vérifier si le port 27017 est déjà utilisé
        if check_port_in_use(27017):
            print("[MongoDB] Port 27017 déjà utilisé - tunnel probablement actif")
            print("[MongoDB] Connexion MongoDB disponible sur localhost:27017")
            return True

        # Vérifier si kubectl est disponible
        result = subprocess.run(["kubectl", "version", "--client"],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("[AVERTISSEMENT] kubectl non disponible. Tunnel MongoDB ignoré.")
            return False

        # Démarrer le tunnel MongoDB
        if os.name == 'nt':  # Windows
            # Utiliser le script mongodb-tunnel.cmd sur Windows
            subprocess.Popen(["mongodb-tunnel.cmd", "start"], shell=True)
        else:  # Linux/Mac
            # Commande directe sur Linux
            subprocess.Popen(["kubectl", "port-forward", "-n", "askme-mongodb",
                            "service/mongodb-shared", "27017:27017"])

        print("[MongoDB] Tunnel démarré en arrière-plan sur localhost:27017")
        time.sleep(2)  # Attendre l'établissement du tunnel
        return True

    except subprocess.TimeoutExpired:
        print("[AVERTISSEMENT] Timeout lors de la vérification kubectl")
        return False
    except Exception as e:
        print(f"[AVERTISSEMENT] Erreur lors du démarrage du tunnel MongoDB: {e}")
        return False

if __name__ == "__main__":
    # Démarrer le tunnel MongoDB automatiquement
    start_mongodb_tunnel()

    print("\n[Debug Server] Démarrage du serveur de développement...")
    print("[Debug Server] Serveur disponible sur http://localhost:50505")
    print("[Debug Server] MongoDB tunnel sur localhost:27017 (si disponible)")

    uvicorn.run("app:app", host="0.0.0.0", port=50505, reload=True)