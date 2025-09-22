"""
Module d'authentification pour les tests AskMe
"""

import hashlib
from datetime import datetime


def generate_auth_token(base_token="@v@nt€m-Q@litYs@AS-d€v31"):
    """
    Génère le token d'authentification pour la date actuelle

    Args:
        base_token: Token de base depuis le fichier .env

    Returns:
        str: Token d'authentification SHA256 avec salt de la date du jour
    """
    salt = datetime.now().strftime("%d%m%Y")
    fullchain = base_token + salt
    return hashlib.sha256(fullchain.encode('utf-8')).hexdigest()


def get_auth_headers(base_token="@v@nt€m-Q@litYs@AS-d€v31"):
    """
    Retourne les headers d'authentification pour les requêtes API

    Args:
        base_token: Token de base depuis le fichier .env

    Returns:
        dict: Headers HTTP avec AuthToken
    """
    return {
        "Content-Type": "application/json",
        "AuthToken": generate_auth_token(base_token)
    }