import uvicorn
import subprocess
import sys
import time
import os

def check_port_in_use(port):
    """Vérifie si un port est déjà utilisé en état LISTENING"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(["netstat", "-an"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            # Chercher spécifiquement le port en écoute (LISTENING)
            # Format Windows: "  TCP    0.0.0.0:27017          0.0.0.0:0              LISTENING"
            # ou              "  TCP    127.0.0.1:27017        0.0.0.0:0              LISTENING"
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    # Vérifier que c'est bien le port local (pas distant)
                    parts = line.split()
                    if len(parts) >= 2 and f":{port}" in parts[1]:
                        return True
            return False
        else:  # Linux/Mac
            result = subprocess.run(["lsof", f"-i:{port}"], capture_output=True, text=True)
            return result.returncode == 0
    except:
        return False

def start_mongodb_tunnel():
    """Démarre le tunnel MongoDB vers Kubernetes"""
    print("\n[MongoDB] Démarrage du tunnel Kubernetes en arrière-plan...")

    try:
        # Vérifier si le port 27017 est déjà utilisé
        if check_port_in_use(27017):
            print("[MongoDB] Port 27017 déjà utilisé - tunnel probablement actif")
            print("[MongoDB] Tunnel MongoDB disponible sur localhost:27017")
            return True

        # Vérifier si kubectl est disponible
        result = subprocess.run(["kubectl", "version", "--client"],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("[AVERTISSEMENT] kubectl non disponible. Tunnel MongoDB ignoré.")
            return False

        # Démarrer le tunnel MongoDB dans une nouvelle fenêtre (Windows)
        if os.name == 'nt':  # Windows
            subprocess.Popen([
                "cmd", "/c", "start", "MongoDB Tunnel", "cmd", "/k",
                "kubectl port-forward -n askme-mongodb mongodb-0 27017:27017"
            ], shell=True)
        else:  # Linux/Mac
            subprocess.Popen(["kubectl", "port-forward", "-n", "askme-mongodb",
                            "mongodb-0", "27017:27017"])

        print("[MongoDB] Tunnel lancé dans une nouvelle fenêtre.")
        print("[MongoDB] Attente de l'établissement du tunnel...")
        time.sleep(5)  # Attendre l'établissement du tunnel

        # Vérifier si le tunnel est établi
        if check_port_in_use(27017):
            print("[MongoDB] Tunnel MongoDB disponible sur localhost:27017")
        else:
            print("[MongoDB] Tunnel en cours d'établissement... (vérifiez la fenêtre MongoDB Tunnel)")

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
    print("[Debug Server] Serveur disponible sur http://localhost:5007")
    print("[Debug Server] MongoDB tunnel sur localhost:27017 (si disponible)")

    # Lancer exactement comme start.cmd (sans spécifier le host explicitement)
    uvicorn.run("app:app", port=5007, reload=True)