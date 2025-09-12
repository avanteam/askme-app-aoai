"""
Module pour récupérer la version de l'application.
"""
import json
import os
import logging
from typing import Dict, Any


def get_version_info() -> Dict[str, Any]:
    """
    Récupère les informations de version de l'application.
    
    Returns:
        Dict[str, Any]: Dictionnaire contenant les informations de version
    """
    version_file = "version.json"
    
    # Si le fichier version.json existe (créé par GitHub Actions)
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                version_info = json.load(f)
                logging.debug(f"Version info loaded from {version_file}: {version_info}")
                return version_info
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Error reading {version_file}: {e}")
    
    # Fallback pour le développement local
    return {
        "version": "dev",
        "buildDate": None,
        "buildNumber": None,
        "commitSha": None
    }


def get_display_version() -> str:
    """
    Récupère la version formatée pour l'affichage dans l'interface.
    
    Returns:
        str: Version formatée pour l'affichage (ex: "v1.0.12", "dev")
    """
    version_info = get_version_info()
    return version_info.get("version", "dev")