#!/usr/bin/env python3
"""
Script pour mettre à jour facilement le contenu d'aide.
Ce script permet d'ajouter, modifier ou supprimer des sections, prompts ou traductions
dans le fichier help_content.json sans avoir à éditer manuellement le JSON.
"""

import os
import json
import argparse
import sys
from datetime import datetime

HELP_CONTENT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "help_content.json")

def load_help_content():
    """Charge le contenu d'aide à partir du fichier JSON."""
    try:
        with open(HELP_CONTENT_PATH, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Le fichier {HELP_CONTENT_PATH} n'existe pas.")
        return None
    except json.JSONDecodeError:
        print(f"Le fichier {HELP_CONTENT_PATH} n'est pas un JSON valide.")
        return None

def save_help_content(content):
    """Sauvegarde le contenu d'aide dans le fichier JSON."""
    # Créer une sauvegarde avant de modifier le fichier
    if os.path.exists(HELP_CONTENT_PATH):
        backup_path = f"{HELP_CONTENT_PATH}.backup.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        os.rename(HELP_CONTENT_PATH, backup_path)
        print(f"Sauvegarde créée: {backup_path}")
    
    # Créer le dossier data s'il n'existe pas
    os.makedirs(os.path.dirname(HELP_CONTENT_PATH), exist_ok=True)
    
    # Enregistrer le nouveau contenu
    with open(HELP_CONTENT_PATH, 'w', encoding='utf-8') as file:
        json.dump(content, file, ensure_ascii=False, indent=2)
    
    print(f"Contenu d'aide mis à jour avec succès dans {HELP_CONTENT_PATH}")

def add_guide_section(content, section_id, title_fr, title_en, content_fr, content_en, icon):
    """Ajoute une nouvelle section au guide."""
    if not content:
        return False
    
    # Vérifier si la section existe déjà
    for section in content['guideContent']:
        if section['id'] == section_id:
            print(f"La section '{section_id}' existe déjà. Utilisez --update-guide pour la modifier.")
            return False
    
    # Créer la nouvelle section
    new_section = {
        "id": section_id,
        "title": {
            "FR": title_fr,
            "EN": title_en
        },
        "content": {
            "FR": content_fr,
            "EN": content_en
        },
        "icon": icon
    }
    
    content['guideContent'].append(new_section)
    return True

def update_guide_section(content, section_id, title_fr=None, title_en=None, content_fr=None, content_en=None, icon=None):
    """Met à jour une section existante du guide."""
    if not content:
        return False
    
    # Trouver la section à mettre à jour
    section_found = False
    for section in content['guideContent']:
        if section['id'] == section_id:
            section_found = True
            if title_fr:
                section['title']['FR'] = title_fr
            if title_en:
                section['title']['EN'] = title_en
            if content_fr:
                section['content']['FR'] = content_fr
            if content_en:
                section['content']['EN'] = content_en
            if icon:
                section['icon'] = icon
            break
    
    if not section_found:
        print(f"La section '{section_id}' n'existe pas. Utilisez --add-guide pour l'ajouter.")
        return False
    
    return True

def add_prompt(content, category, title_fr, title_en, description_fr, description_en, prompt_fr, prompt_en):
    """Ajoute un nouveau prompt d'exemple."""
    if not content:
        return False
    
    # Vérifier si la catégorie existe
    category_exists = False
    for cat in content['categories']:
        if cat['key'] == category:
            category_exists = True
            break
    
    if not category_exists:
        print(f"La catégorie '{category}' n'existe pas. Choisissez parmi: {', '.join([cat['key'] for cat in content['categories']])}")
        return False
    
    # Générer un nouvel ID
    new_id = max([prompt['id'] for prompt in content['predefinedPrompts']], default=0) + 1
    
    # Créer le nouveau prompt
    new_prompt = {
        "id": new_id,
        "category": category,
        "title": {
            "FR": title_fr,
            "EN": title_en
        },
        "description": {
            "FR": description_fr,
            "EN": description_en
        },
        "prompt": {
            "FR": prompt_fr,
            "EN": prompt_en
        }
    }
    
    content['predefinedPrompts'].append(new_prompt)
    return True

def main():
    parser = argparse.ArgumentParser(description="Outil de gestion du contenu d'aide")
    
    # Actions
    actions = parser.add_argument_group('Actions')
    actions.add_argument('--add-guide', action='store_true', help="Ajouter une nouvelle section au guide")
    actions.add_argument('--update-guide', action='store_true', help="Mettre à jour une section existante du guide")
    actions.add_argument('--add-prompt', action='store_true', help="Ajouter un nouveau prompt d'exemple")
    
    # Paramètres pour les sections du guide
    guide_params = parser.add_argument_group('Paramètres des sections du guide')
    guide_params.add_argument('--section-id', help="ID unique de la section (ex: getting-started)")
    guide_params.add_argument('--title-fr', help="Titre de la section en français")
    guide_params.add_argument('--title-en', help="Titre de la section en anglais")
    guide_params.add_argument('--content-fr-file', help="Chemin vers un fichier contenant le contenu en français (format Markdown)")
    guide_params.add_argument('--content-en-file', help="Chemin vers un fichier contenant le contenu en anglais (format Markdown)")
    guide_params.add_argument('--icon', help="Nom de l'icône (FluentUI)")
    
    # Paramètres pour les prompts
    prompt_params = parser.add_argument_group('Paramètres des prompts')
    prompt_params.add_argument('--category', help="Catégorie du prompt (ex: general, documents)")
    prompt_params.add_argument('--prompt-title-fr', help="Titre du prompt en français")
    prompt_params.add_argument('--prompt-title-en', help="Titre du prompt en anglais")
    prompt_params.add_argument('--prompt-desc-fr', help="Description du prompt en français")
    prompt_params.add_argument('--prompt-desc-en', help="Description du prompt en anglais")
    prompt_params.add_argument('--prompt-fr', help="Texte du prompt en français")
    prompt_params.add_argument('--prompt-en', help="Texte du prompt en anglais")
    
    args = parser.parse_args()
    
    # Vérifier qu'une action est spécifiée
    if not (args.add_guide or args.update_guide or args.add_prompt):
        parser.print_help()
        sys.exit(1)
    
    content = load_help_content()
    if not content:
        print("Création d'un nouveau fichier de contenu d'aide...")
        content = {
            "translations": {
                "FR": {},
                "EN": {}
            },
            "categories": [
                { "key": "general", "name": { "FR": "Général", "EN": "General" }, "icon": "Info" },
                { "key": "documents", "name": { "FR": "Documents", "EN": "Documents" }, "icon": "Document" }
            ],
            "guideContent": [],
            "predefinedPrompts": []
        }
    
    success = False
    
    # Ajouter une section au guide
    if args.add_guide:
        if not all([args.section_id, args.title_fr, args.title_en, args.content_fr_file, args.content_en_file, args.icon]):
            print("Erreur: Tous les paramètres sont requis pour ajouter une section au guide.")
            sys.exit(1)
        
        try:
            with open(args.content_fr_file, 'r', encoding='utf-8') as file:
                content_fr = file.read()
            with open(args.content_en_file, 'r', encoding='utf-8') as file:
                content_en = file.read()
            
            success = add_guide_section(content, args.section_id, args.title_fr, args.title_en, content_fr, content_en, args.icon)
        except Exception as e:
            print(f"Erreur lors de la lecture des fichiers de contenu: {e}")
            sys.exit(1)
    
    # Mettre à jour une section du guide
    elif args.update_guide:
        if not args.section_id:
            print("Erreur: L'ID de la section est requis pour la mise à jour.")
            sys.exit(1)
        
        content_fr = None
        content_en = None
        
        if args.content_fr_file:
            try:
                with open(args.content_fr_file, 'r', encoding='utf-8') as file:
                    content_fr = file.read()
            except Exception as e:
                print(f"Erreur lors de la lecture du fichier de contenu français: {e}")
                sys.exit(1)
        
        if args.content_en_file:
            try:
                with open(args.content_en_file, 'r', encoding='utf-8') as file:
                    content_en = file.read()
            except Exception as e:
                print(f"Erreur lors de la lecture du fichier de contenu anglais: {e}")
                sys.exit(1)
        
        success = update_guide_section(
            content, 
            args.section_id, 
            args.title_fr, 
            args.title_en, 
            content_fr, 
            content_en, 
            args.icon
        )
    
    # Ajouter un prompt
    elif args.add_prompt:
        if not all([args.category, args.prompt_title_fr, args.prompt_title_en, args.prompt_desc_fr, 
                   args.prompt_desc_en, args.prompt_fr, args.prompt_en]):
            print("Erreur: Tous les paramètres sont requis pour ajouter un prompt.")
            sys.exit(1)
        
        success = add_prompt(
            content, 
            args.category, 
            args.prompt_title_fr, 
            args.prompt_title_en, 
            args.prompt_desc_fr, 
            args.prompt_desc_en, 
            args.prompt_fr, 
            args.prompt_en
        )
    
    if success:
        save_help_content(content)
    else:
        print("Opération annulée. Aucune modification n'a été apportée.")
        sys.exit(1)

if __name__ == "__main__":
    main()