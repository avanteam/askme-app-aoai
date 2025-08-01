#!/usr/bin/env python3
"""
Module de Synchronisation Incrémentale
Adapté du notebook 02 pour l'interface web
"""

import sys
import json
import hashlib
import requests
import shutil
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Charger les variables d'environnement depuis .env.local si disponible
def load_env_file():
    """Charger les variables depuis .env.local puis .env"""
    env_files = ['.env.local', '.env']
    
    for env_file in env_files:
        if Path(env_file).exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if key not in os.environ:
                            os.environ[key] = value
            return True
    return False

# Charger au démarrage
load_env_file()

# Ajouter le chemin des scripts
sys.path.append(str(Path(__file__).parent.parent / 'indexing'))
from simple_indexer import SimpleIndexer, create_simple_index
sys.path.append(str(Path(__file__).parent))
from embedding_service import create_embedding_service

def ensure_correct_mapping(opensearch_url: str, index_name: str) -> bool:
    """Vérifier et corriger le mapping OpenSearch si nécessaire"""
    
    try:
        # Vérifier si l'index existe et son mapping
        response = requests.get(f"{opensearch_url}/{index_name}/_mapping")
        
        if response.status_code == 404:
            # Index n'existe pas, le créer avec le bon mapping
            print(f"🔧 Création de l'index {index_name} avec mapping correct...")
            success = create_simple_index(opensearch_url, index_name)
            if success:
                print(f"✅ Index {index_name} créé")
                return True
            else:
                print(f"❌ Erreur création index {index_name}")
                return False
        
        elif response.status_code == 200:
            # Index existe, vérifier le mapping
            mapping = response.json()
            properties = mapping[index_name]["mappings"]["properties"]
            
            # Vérifier si chunk_id est défini comme integer (problématique)
            chunk_id_type = properties.get("chunk_id", {}).get("type", "")
            
            if chunk_id_type == "integer":
                print(f"⚠️  Mapping obsolète détecté dans {index_name} (chunk_id: integer)")
                print(f"🔧 Recréation de l'index avec mapping corrigé...")
                
                # Recréer l'index avec le bon mapping
                success = create_simple_index(opensearch_url, index_name)
                if success:
                    print(f"✅ Index {index_name} recréé avec mapping correct")
                    return True
                else:
                    print(f"❌ Erreur recréation index {index_name}")
                    return False
            
            elif chunk_id_type == "keyword":
                # Mapping correct, continuer
                return True
            
            else:
                print(f"⚠️  Mapping inattendu pour chunk_id: {chunk_id_type}")
                print(f"🔧 Recréation de l'index par sécurité...")
                success = create_simple_index(opensearch_url, index_name)
                return success
        
        else:
            print(f"❌ Erreur vérification mapping: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ Erreur ensure_correct_mapping: {e}")
        return False

def calculate_file_hash(file_path: Path) -> str:
    """Calculer le hash SHA256 d'un fichier"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception:
        return "error"

def calculate_document_signature(client_id: str, doc_id: str, doc_dir: Path) -> str:
    """Calculer signature unique d'un document (toutes PJ + métadonnées)"""
    
    # 1. Hash de toutes les PJ
    attachments_hash = []
    for pj_file in doc_dir.rglob('*'):
        if pj_file.is_file() and pj_file.name != 'metadata.json':
            file_hash = calculate_file_hash(pj_file)
            file_size = pj_file.stat().st_size
            file_mtime = pj_file.stat().st_mtime
            attachments_hash.append(f"{pj_file.name}:{file_hash}:{file_size}:{file_mtime}")
    
    # 2. Hash des métadonnées du document
    metadata_file = doc_dir / "metadata.json"
    metadata_hash = "no_metadata"
    
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_content = f.read()
            metadata_hash = hashlib.md5(metadata_content.encode()).hexdigest()
        except Exception:
            metadata_hash = "error"
    
    # 3. Signature combinée
    combined = "|".join(sorted(attachments_hash)) + f"|meta:{metadata_hash}"
    return hashlib.sha256(combined.encode()).hexdigest()

def load_index_state(state_file: Path) -> Dict:
    """Charger l'état d'indexation précédent"""
    try:
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}

def save_index_state(state_file: Path, new_state: Dict) -> bool:
    """Sauvegarder le nouvel état d'indexation"""
    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(new_state, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde état: {e}")
        return False

def detect_document_changes(client_id: str, data_dir: Path) -> Dict:
    """Détecter les changements au niveau document"""
    
    client_path = data_dir / client_id
    documents_path = client_path / "documents"
    state_file = client_path / ".index_state.json"
    
    if not documents_path.exists():
        return {'error': f'Répertoire documents inexistant: {documents_path}'}
    
    current_state = load_index_state(state_file)
    
    changes = {
        'new_documents': [],
        'modified_documents': [],
        'deleted_documents': [],
        'unchanged_documents': []
    }
    
    # Scanner chaque document (dossier UUID)
    current_docs = set()
    
    for doc_dir in documents_path.iterdir():
        if doc_dir.is_dir() and len(doc_dir.name) >= 32:  # UUID-like 
            doc_id = doc_dir.name
            current_docs.add(doc_id)
            
            # Compter les PJ
            attachments = [f for f in doc_dir.rglob('*') if f.is_file() and f.name != 'metadata.json']
            
            if not attachments:
                # Dossier vide, ignorer
                continue
            
            # Calculer signature du document
            doc_signature = calculate_document_signature(client_id, doc_id, doc_dir)
            
            if doc_id not in current_state:
                # Nouveau document
                changes['new_documents'].append({
                    'doc_id': doc_id,
                    'doc_dir': doc_dir,  # Garder l'objet Path pour usage interne
                    'doc_dir_str': str(doc_dir),  # Version string pour JSON
                    'signature': doc_signature,
                    'attachments_count': len(attachments)
                })
            else:
                old_signature = current_state[doc_id].get('signature', '')
                
                if old_signature != doc_signature:
                    # Document modifié
                    changes['modified_documents'].append({
                        'doc_id': doc_id,
                        'doc_dir': doc_dir,  # Garder l'objet Path pour usage interne
                        'doc_dir_str': str(doc_dir),  # Version string pour JSON
                        'signature': doc_signature,
                        'old_signature': old_signature,
                        'attachments_count': len(attachments)
                    })
                else:
                    # Document inchangé
                    changes['unchanged_documents'].append(doc_id)
    
    # Documents supprimés
    for doc_id in current_state:
        if doc_id not in current_docs:
            changes['deleted_documents'].append(doc_id)
    
    return changes

def get_pj_metadata(doc_dir: Path, pj_name: str) -> Dict:
    """Récupérer les métadonnées d'une pièce jointe spécifique"""
    try:
        metadata_file = doc_dir / "metadata.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                all_pj_metadata = json.load(f)
            return all_pj_metadata.get(pj_name, {})
        
        return {}
    except Exception as e:
        print(f"⚠️ Erreur lecture métadonnées {pj_name}: {e}")
        return {}

def index_document_with_attachments(client_id: str, doc_id: str, doc_dir: Path, opensearch_url: str, current_doc=1, total_docs=1, processed_files=0, total_files=1, progress_tracker=None, emit_progress=None) -> bool:
    """Indexer un document avec métadonnées par PJ et embeddings vectoriels"""
    
    print(f"📄 Indexation document: {doc_id[:8]}...")
    
    # Vérifier et corriger le mapping OpenSearch si nécessaire
    index_name = f"askme-{client_id}"
    if not ensure_correct_mapping(opensearch_url, index_name):
        print(f"❌ Impossible de corriger le mapping pour {index_name}")
        return False
    
    indexer = SimpleIndexer(opensearch_url=opensearch_url, index_name=index_name)
    
    # Initialiser le service d'embeddings (optionnel)
    embedding_service = create_embedding_service()
    if embedding_service:
        print(f"   🧠 Service d'embeddings disponible")
    else:
        print(f"   ⚠️ Embeddings non disponibles - recherche textuelle uniquement")
    
    indexed_count = 0
    processed_attachments = 0
    
    # Compter les pièces jointes d'abord
    attachments = [f for f in doc_dir.rglob('*') if f.is_file() and f.name != 'metadata.json']
    
    if progress_tracker:
        progress_tracker.start_document(doc_id, 0, len(attachments))  # doc_index sera mis à jour par l'appelant
    
    # Indexer chaque pièce jointe
    current_file_in_doc = 0
    for pj_index, pj_file in enumerate(attachments):
        pj_name = pj_file.name
        processed_attachments += 1
        
        # Calculer la progression globale basée sur tous les fichiers
        current_global_file = processed_files + current_file_in_doc
        file_progress = int((current_global_file / total_files) * 100) if total_files > 0 else 0
        
        if emit_progress:
            emit_progress(f"Traitement fichier: {pj_name}", 'file_start', file_progress, filename=pj_name)
        
        if progress_tracker:
            progress_tracker.start_file(pj_name)
        
        # Récupérer les métadonnées spécifiques de cette PJ
        pj_metadata = get_pj_metadata(doc_dir, pj_name)
        
        # Extraction des champs selon le schéma
        titre_document = pj_metadata.get('titreDocument', pj_name)
        field_metadata = pj_metadata.get('fieldMetadata', '')
        security_rights = pj_metadata.get('securityRights', None)
        metadata_storage_name = pj_metadata.get('metadata_storage_name', pj_name)
        metadata_storage_path = pj_metadata.get('metadata_storage_path', f'/documents/{doc_id}/{pj_name}')
        
        try:
            # Extraire contenu de la PJ
            print(f"      📄 Traitement {pj_name}...")
            if emit_progress:
                emit_progress(f"Extraction: {pj_name}", 'extraction', file_progress, filename=pj_name)
            
            content = indexer.processor.extract_text(pj_file)
            print(f"      📏 Contenu extrait: {len(content) if content else 0} caractères")
            if not content or len(content.strip()) < 10:
                print(f"      ⚠️ {pj_name}: Contenu vide ou trop court (<10 chars)")
                continue
            
            # Découper en chunks
            if emit_progress:
                emit_progress(f"Découpage: {pj_name}", 'chunking', file_progress, filename=pj_name)
            
            chunks = indexer.splitter.split_text(content)
            if not chunks:
                print(f"      ⚠️ {pj_name}: Aucun chunk généré")
                continue
            
            # Générer les embeddings pour tous les chunks si le service est disponible
            chunk_embeddings = []
            if embedding_service:
                print(f"      🧠 Génération embeddings pour {len(chunks)} chunks...")
                if emit_progress:
                    emit_progress(f"Embeddings: {pj_name} ({len(chunks)} chunks)", 'embeddings_start', file_progress, filename=pj_name)
                
                try:
                    chunk_embeddings = embedding_service.generate_embeddings_batch(chunks, batch_size=5)
                    print(f"      ✅ {len(chunk_embeddings)} embeddings générés")
                    if emit_progress:
                        emit_progress(f"Embeddings terminés: {pj_name}", 'embeddings_complete', file_progress, filename=pj_name)
                except Exception as e:
                    print(f"      ⚠️ Erreur embeddings: {e}")
                    chunk_embeddings = []
            
            # Indexer chaque chunk avec son embedding
            if emit_progress:
                emit_progress(f"Indexation: {pj_name} ({len(chunks)} chunks)", 'chunk_indexing', file_progress, filename=pj_name)
            
            for i, chunk in enumerate(chunks):
                # Génération des IDs
                chunk_id = f"{doc_id}_{pj_name}_chunk_{i}"
                parent_id = doc_id
                
                # Document avec les champs exacts du schéma
                doc = {
                    "chunk_id": chunk_id,
                    "parent_id": parent_id,
                    "chunk": chunk,
                    "title": titre_document,
                    "metadata_storage_last_modified": datetime.now().isoformat(),
                    "metadata_storage_name": metadata_storage_name,
                    "metadata_storage_path": metadata_storage_path,
                    "securityRights": security_rights if security_rights else [],
                    "titreDocument": titre_document,
                    "fieldMetadata": field_metadata
                }
                
                # Ajouter l'embedding si disponible
                if i < len(chunk_embeddings):
                    doc["chunk_vector"] = chunk_embeddings[i]
                
                # Indexer le chunk
                response = requests.post(
                    f"{indexer.opensearch_url}/{indexer.index_name}/_doc/{chunk_id}",
                    headers={"Content-Type": "application/json"},
                    json=doc
                )
                
                if response.status_code in [200, 201]:
                    indexed_count += 1
                else:
                    print(f"      ❌ Erreur indexation chunk {i}: {response.status_code}")
            
            print(f"      ✅ {pj_name}: {len(chunks)} chunks indexés")
            
            if emit_progress:
                # Progression après completion du fichier
                current_file_in_doc += 1
                current_global_file = processed_files + current_file_in_doc
                file_progress_complete = int((current_global_file / total_files) * 100) if total_files > 0 else 0
                emit_progress(f"Fichier terminé: {pj_name}", 'file_complete', file_progress_complete, filename=pj_name)
            
        except Exception as e:
            print(f"      ❌ Erreur PJ {pj_name}: {e}")
            current_file_in_doc += 1  # Compter même les fichiers en erreur
            continue
    
    print(f"   📊 Résultat: {indexed_count} chunks, {processed_attachments} PJ")
    
    if indexed_count == 0:
        if processed_attachments == 0:
            print(f"      ⚠️ Aucune PJ trouvée dans {doc_dir}")
        else:
            print(f"      ⚠️ {processed_attachments} PJ trouvées mais aucun chunk indexé")
    
    return indexed_count > 0

def delete_attachment_chunks(client_id: str, doc_id: str, filename: str, opensearch_url: str) -> int:
    """Supprimer tous les chunks d'une pièce jointe spécifique - VERSION OPTIMISÉE"""
    
    try:
        print(f"🗑️ Suppression rapide de la PJ {filename}...")
        
        # Delete by Query pour une pièce jointe spécifique
        delete_query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"parent_id": doc_id}},
                        {"wildcard": {"chunk_id": f"{doc_id}_{filename}_chunk_*"}}
                    ]
                }
            }
        }
        
        response = requests.post(
            f"{opensearch_url}/askme-{client_id}/_delete_by_query?refresh=true",
            headers={"Content-Type": "application/json"},
            json=delete_query
        )
        
        if response.status_code == 200:
            result = response.json()
            deleted_count = result.get('deleted', 0)
            took_ms = result.get('took', 0)
            print(f"✅ Suppression PJ terminée: {deleted_count} chunks en {took_ms}ms")
            return deleted_count
        else:
            print(f"⚠️ Delete by query PJ échoué ({response.status_code})")
            return 0
        
    except Exception as e:
        print(f"❌ Erreur suppression PJ {filename}: {e}")
        return 0

def bulk_delete_chunks(client_id: str, chunk_ids: list, opensearch_url: str) -> int:
    """Suppression en lot optimisée"""
    
    try:
        print(f"⚡ Suppression en lot de {len(chunk_ids)} chunks...")
        
        # Préparer le bulk request
        bulk_body = []
        for chunk_id in chunk_ids:
            bulk_body.append(json.dumps({"delete": {"_id": chunk_id}}))
        
        bulk_data = "\n".join(bulk_body) + "\n"
        
        response = requests.post(
            f"{opensearch_url}/askme-{client_id}/_bulk?refresh=true",
            headers={"Content-Type": "application/x-ndjson"},
            data=bulk_data
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Compter les suppressions réussies
            deleted_count = 0
            for item in result.get('items', []):
                if 'delete' in item:
                    status = item['delete'].get('status', 0)
                    if status in [200, 404]:  # 200 = supprimé, 404 = déjà absent
                        deleted_count += 1
            
            took_ms = result.get('took', 0)
            print(f"✅ Suppression en lot terminée: {deleted_count}/{len(chunk_ids)} chunks en {took_ms}ms")
            return deleted_count
        else:
            print(f"❌ Bulk delete échoué: {response.status_code}")
            return 0
        
    except Exception as e:
        print(f"❌ Erreur bulk delete: {e}")
        return 0

def delete_document_by_parent_id(client_id: str, doc_id: str, opensearch_url: str) -> int:
    """Supprimer tous les chunks d'un document par parent_id - VERSION OPTIMISÉE"""
    
    try:
        print(f"🗑️ Suppression rapide du document {doc_id[:8]}...")
        
        # MÉTHODE 1: Delete by Query (plus rapide pour gros volumes)
        delete_query = {
            "query": {
                "term": {"parent_id": doc_id}
            }
        }
        
        response = requests.post(
            f"{opensearch_url}/askme-{client_id}/_delete_by_query?refresh=true",
            headers={"Content-Type": "application/json"},
            json=delete_query
        )
        
        if response.status_code == 200:
            result = response.json()
            deleted_count = result.get('deleted', 0)
            took_ms = result.get('took', 0)
            print(f"✅ Suppression rapide terminée: {deleted_count} chunks en {took_ms}ms")
            return deleted_count
        else:
            print(f"⚠️ Delete by query échoué ({response.status_code}), fallback vers méthode classique")
            return delete_document_by_parent_id_fallback(client_id, doc_id, opensearch_url)
        
    except Exception as e:
        print(f"❌ Erreur suppression rapide {doc_id}: {e}")
        print(f"🔄 Fallback vers méthode classique...")
        return delete_document_by_parent_id_fallback(client_id, doc_id, opensearch_url)

def delete_document_by_parent_id_fallback(client_id: str, doc_id: str, opensearch_url: str) -> int:
    """Méthode de suppression classique (fallback)"""
    
    try:
        print(f"🐌 Suppression classique du document {doc_id[:8]}...")
        
        # Rechercher tous les chunks
        search_query = {
            "query": {"term": {"parent_id": doc_id}},
            "size": 10000,  # Augmenté pour gros documents
            "_source": False  # On veut juste les IDs
        }
        
        response = requests.post(
            f"{opensearch_url}/askme-{client_id}/_search",
            headers={"Content-Type": "application/json"},
            json=search_query
        )
        
        if response.status_code != 200:
            return 0
        
        search_results = response.json()
        chunks_to_delete = [hit['_id'] for hit in search_results.get('hits', {}).get('hits', [])]
        
        if not chunks_to_delete:
            print(f"ℹ️ Aucun chunk trouvé pour {doc_id}")
            return 0
        
        print(f"📊 {len(chunks_to_delete)} chunks à supprimer")
        
        # MÉTHODE 2: Bulk delete (beaucoup plus rapide que delete un par un)
        if len(chunks_to_delete) > 10:  # Si plus de 10 chunks, utiliser bulk
            return bulk_delete_chunks(client_id, chunks_to_delete, opensearch_url)
        else:
            # Pour les petits documents, delete individuel reste OK
            deleted_count = 0
            for chunk_id in chunks_to_delete:
                delete_response = requests.delete(
                    f"{opensearch_url}/askme-{client_id}/_doc/{chunk_id}"
                )
                if delete_response.status_code in [200, 404]:
                    deleted_count += 1
            return deleted_count
        
    except Exception as e:
        print(f"❌ Erreur suppression classique {doc_id}: {e}")
        return 0

def sync_client_incremental(client_id: str, data_dir: Path = None, opensearch_url: str = "http://localhost:9200", emit_progress=None) -> Dict:
    """Synchronisation incrémentale d'un client"""
    
    if data_dir is None:
        data_dir = Path("clients-data")
    
    print(f"🔄 Synchronisation incrémentale: {client_id}")
    start_time = datetime.now()
    
    # Émettre le début de synchronisation
    if emit_progress:
        emit_progress("Analyse des documents...", 'start', 0)
    
    # Détecter les changements
    changes = detect_document_changes(client_id, data_dir)
    
    if 'error' in changes:
        if emit_progress:
            emit_progress(f"Erreur: {changes['error']}", 'error', 0)
        return {'error': changes['error'], 'processed': 0, 'errors': [changes['error']], 'operations': []}
    
    sync_report = {
        'client_id': client_id,
        'timestamp': datetime.now().isoformat(),
        'processed': 0,
        'errors': [],
        'operations': []
    }
    
    # Résumé des changements
    total_documents = (len(changes['new_documents']) + 
                      len(changes['modified_documents']) + 
                      len(changes['deleted_documents']))
    
    # Calculer le nombre total de fichiers pour une progression plus fluide
    total_files = (len(changes['deleted_documents']) +  # docs supprimés = 1 opération chacun
                   sum(doc_info['attachments_count'] for doc_info in changes['new_documents']) +
                   sum(doc_info['attachments_count'] for doc_info in changes['modified_documents']))
    
    print(f"📊 Changements: {len(changes['new_documents'])} nouveaux, {len(changes['modified_documents'])} modifiés, {len(changes['deleted_documents'])} supprimés")
    print(f"📊 Total: {total_documents} documents, {total_files} fichiers à traiter")
    
    if total_documents == 0:
        sync_report['operations'].append("Aucun changement détecté")
        if emit_progress:
            emit_progress("Aucun changement détecté", 'complete', 100)
        return sync_report
    
    # Progress tracking
    current_doc = 0
    processed_docs = 0
    processed_files = 0  # Compteur de fichiers traités
    
    # 1. Supprimer les documents effacés
    for doc_id in changes['deleted_documents']:
        # Progression basée sur les fichiers traités
        progress_start = int((processed_files / total_files) * 100) if total_files > 0 else 0
        
        if emit_progress:
            emit_progress(f"Suppression: {doc_id[:8]}...", 'processing', progress_start)
        
        try:
            deleted_chunks = delete_document_by_parent_id(client_id, doc_id, opensearch_url)
            sync_report['operations'].append(f"DELETED: {doc_id[:8]}... ({deleted_chunks} chunks)")
            sync_report['processed'] += 1
            processed_docs += 1
            current_doc += 1
            processed_files += 1  # Une suppression = un fichier traité
            
            # Progression après completion du document (max 99% pour éviter le force à 100%)
            progress_complete = min(int((processed_files / total_files) * 100), 99) if total_files > 0 else 99
            if emit_progress:
                emit_progress(f"Document supprimé: {doc_id[:8]}...", 'document_complete', progress_complete,
                             current_doc=current_doc, total_docs=total_documents, 
                             completed_docs_count=processed_docs)
        except Exception as e:
            error_msg = f"Error deleting {doc_id}: {e}"
            sync_report['errors'].append(error_msg)
    
    # 2. Indexer nouveaux documents
    for i, doc_info in enumerate(changes['new_documents']):
        doc_id = doc_info['doc_id']
        doc_dir = doc_info['doc_dir']
        
        # Progression au début du document (basée sur les fichiers)
        progress_start = int((processed_files / total_files) * 100) if total_files > 0 else 0
        
        if emit_progress:
            emit_progress(f"Nouveau document: {doc_id[:8]}... ({doc_info['attachments_count']} PJ)", 'document_start', progress_start, 
                         current_doc=current_doc + 1, total_docs=total_documents, doc_id=doc_id, 
                         completed_docs_count=processed_docs)
        
        try:
            # Passer les compteurs de fichiers pour progression granulaire
            success = index_document_with_attachments(client_id, doc_id, doc_dir, opensearch_url, 
                                                     current_doc=current_doc + 1, total_docs=total_documents,
                                                     processed_files=processed_files, total_files=total_files,
                                                     emit_progress=emit_progress)
            
            if success:
                sync_report['operations'].append(f"ADDED: {doc_id[:8]}... ({doc_info['attachments_count']} PJ)")
                sync_report['processed'] += 1
                processed_docs += 1
                current_doc += 1
                processed_files += doc_info['attachments_count']  # Ajouter tous les fichiers du document
                
                # Progression après completion du document (max 99% pour éviter le force à 100%)
                progress_complete = min(int((processed_files / total_files) * 100), 99) if total_files > 0 else 99
                if emit_progress:
                    emit_progress(f"Document indexé: {doc_id[:8]}...", 'document_complete', progress_complete,
                                 current_doc=current_doc, total_docs=total_documents, doc_id=doc_id,
                                 completed_docs_count=processed_docs)
            else:
                sync_report['errors'].append(f"Failed to add {doc_id} - check document content and attachments")
                print(f"❌ Échec indexation {doc_id}: Vérifiez que le document contient des PJ valides")
        except Exception as e:
            error_msg = f"Error adding {doc_info['doc_id']}: {e}"
            sync_report['errors'].append(error_msg)
            print(f"❌ Exception indexation {doc_info['doc_id']}: {e}")
    
    # 3. Réindexer documents modifiés
    for i, doc_info in enumerate(changes['modified_documents']):
        doc_id = doc_info['doc_id']
        doc_dir = doc_info['doc_dir']
        
        # Progression au début du document (avant traitement)
        progress_start = int((current_doc / total_documents) * 100) if total_documents > 0 else 0
        
        if emit_progress:
            emit_progress(f"Modification: {doc_id[:8]}... ({doc_info['attachments_count']} PJ)", 'document_start', progress_start,
                         current_doc=current_doc + 1, total_docs=total_documents, doc_id=doc_id,
                         completed_docs_count=processed_docs)
        
        try:
            # Supprimer ancienne version
            deleted_chunks = delete_document_by_parent_id(client_id, doc_id, opensearch_url)
            
            # Réindexer nouvelle version
            success = index_document_with_attachments(client_id, doc_id, doc_dir, opensearch_url, 
                                                     current_doc=current_doc + 1, total_docs=total_documents, 
                                                     emit_progress=emit_progress)
            
            if success:
                sync_report['operations'].append(f"UPDATED: {doc_id[:8]}... ({doc_info['attachments_count']} PJ)")
                sync_report['processed'] += 1
                processed_docs += 1
                current_doc += 1
                
                # Progression après completion du document (max 99% pour éviter le force à 100%)
                progress_complete = min(int((current_doc / total_documents) * 100), 99) if total_documents > 0 else 99
                if emit_progress:
                    emit_progress(f"Document mis à jour: {doc_id[:8]}...", 'document_complete', progress_complete,
                                 current_doc=current_doc, total_docs=total_documents, doc_id=doc_id,
                                 completed_docs_count=processed_docs)
            else:
                sync_report['errors'].append(f"Failed to update {doc_id}")
        except Exception as e:
            error_msg = f"Error updating {doc_info['doc_id']}: {e}"
            sync_report['errors'].append(error_msg)
    
    # 4. Sauvegarder nouvel état (SEULEMENT pour les documents traités avec succès)
    client_path = data_dir / client_id
    state_file = client_path / ".index_state.json"
    
    # Charger l'état précédent
    current_state = load_index_state(state_file)
    
    # Mettre à jour seulement les documents traités avec succès
    successfully_processed = set()
    
    # Ajouter les nouveaux documents indexés avec succès
    for doc_info in changes['new_documents']:
        doc_id = doc_info['doc_id']
        if any(op.startswith(f"ADDED: {doc_id[:8]}") for op in sync_report['operations']):
            doc_dir = doc_info['doc_dir']
            signature = calculate_document_signature(client_id, doc_id, doc_dir)
            current_state[doc_id] = {
                'signature': signature,
                'last_sync': datetime.now().isoformat(),
                'attachments_count': doc_info['attachments_count']
            }
            successfully_processed.add(doc_id)
    
    # Ajouter les documents modifiés indexés avec succès
    for doc_info in changes['modified_documents']:
        doc_id = doc_info['doc_id']
        if any(op.startswith(f"UPDATED: {doc_id[:8]}") for op in sync_report['operations']):
            doc_dir = doc_info['doc_dir']
            signature = calculate_document_signature(client_id, doc_id, doc_dir)
            current_state[doc_id] = {
                'signature': signature,
                'last_sync': datetime.now().isoformat(),
                'attachments_count': doc_info['attachments_count']
            }
            successfully_processed.add(doc_id)
    
    # Supprimer les documents supprimés avec succès
    for doc_id in changes['deleted_documents']:
        if any(op.startswith(f"DELETED: {doc_id[:8]}") for op in sync_report['operations']):
            if doc_id in current_state:
                del current_state[doc_id]
                successfully_processed.add(doc_id)
    
    # Sauvegarder l'état mis à jour
    save_success = save_index_state(state_file, current_state)
    
    if save_success:
        sync_report['operations'].append(f"État sauvegardé ({len(successfully_processed)} documents traités)")
    else:
        sync_report['errors'].append("Erreur sauvegarde état")
    
    print(f"✅ Synchronisation terminée: {sync_report['processed']} opérations, {len(successfully_processed)} docs mis à jour, {len(sync_report['errors'])} erreurs")
    
    # Émettre la completion avec les statistiques finales
    elapsed_total = (datetime.now() - start_time).total_seconds()
    if emit_progress:
        emit_progress(f"Synchronisation terminée: {processed_docs}/{total_documents} documents traités en {elapsed_total:.1f}s", 'complete', 100)
    
    return sync_report