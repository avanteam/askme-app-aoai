#!/usr/bin/env python3
"""
Interface Web pour AskMe Search
Interface graphique user-friendly pour toutes les fonctionnalités
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename
import sys
import os
from pathlib import Path
import json
import uuid
from datetime import datetime
import requests
import tempfile
import shutil
import threading

# Ajouter le chemin des modules
sys.path.append(str(Path(__file__).parent.parent / 'indexing'))
sys.path.append(str(Path(__file__).parent))  # Pour sync_engine
from simple_indexer import SimpleIndexer, create_simple_index
from sync_engine import sync_client_incremental

# Configuration - Chemins relatifs au répertoire racine
OPENSEARCH_URL = "http://localhost:9200"
ROOT_DIR = Path(__file__).parent.parent
CLIENTS_DATA_DIR = str(ROOT_DIR / "clients-data")
UPLOAD_FOLDER = str(ROOT_DIR / "temp_uploads")
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB max par fichier
ALLOWED_EXTENSIONS = {
    'pdf', 'txt', 'docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 
    'csv', 'json', 'xml', 'html', 'rtf'
}

app = Flask(__name__, 
            template_folder=str(Path(__file__).parent.parent / 'templates'),
            static_folder=str(Path(__file__).parent.parent / 'static'))
app.secret_key = 'askme-search-interface-2024'
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Initialisation SocketIO pour temps réel
socketio = SocketIO(app, cors_allowed_origins="*")

# Créer les dossiers nécessaires
Path(CLIENTS_DATA_DIR).mkdir(exist_ok=True)
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

# Fonctions utilitaires
def get_file_icon_color(extension):
    """Retourner l'icône et la couleur pour un type de fichier"""
    ext_map = {
        'pdf': ('pdf', 'danger'),
        'doc': ('word', 'primary'), 'docx': ('word', 'primary'),
        'xls': ('excel', 'success'), 'xlsx': ('excel', 'success'),
        'ppt': ('powerpoint', 'warning'), 'pptx': ('powerpoint', 'warning'),
        'txt': ('text', 'secondary'),
        'csv': ('csv', 'info'),
        'json': ('code', 'dark'),
        'xml': ('code', 'dark'), 'html': ('code', 'dark'),
        'rtf': ('text', 'secondary')
    }
    return ext_map.get(extension, ('file', 'secondary'))

def format_file_size(size_bytes):
    """Formater la taille de fichier en format lisible"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

class SyncManager:
    """Gestionnaire de synchronisation stub pour compatibilité"""
    
    def get_tasks(self):
        return []
    
    def create_task(self, client_id, name, description="", schedule="manual"):
        return f"task_{client_id}_{int(datetime.now().timestamp())}"
    
    def update_task(self, task_id, data):
        return True
    
    def delete_task(self, task_id):
        return True
    
    def run_sync_task(self, task_id):
        return {"status": "completed", "message": "Utiliser la synchronisation directe"}
    
    def get_results(self, limit=100):
        return []
    
    def get_status(self):
        return {"active_tasks": 0, "total_tasks": 0}
    
    def start_scheduler(self):
        pass
    
    def stop_scheduler(self):
        pass

# Initialiser le gestionnaire de synchronisation
sync_manager = SyncManager()

class AskMeSearchManager:
    """Gestionnaire principal des fonctionnalités AskMe Search"""
    
    def __init__(self):
        self.opensearch_url = OPENSEARCH_URL
        self.clients_data_dir = Path(CLIENTS_DATA_DIR)
    
    def get_client_index_name(self, client_id: str) -> str:
        """Obtenir le nom de l'index pour un client donné"""
        # Exception spéciale pour le client 'askme' qui utilise l'index askme-documents
        if client_id == 'askme':
            return 'askme-documents'
        return f'askme-{client_id}'
    
    def test_opensearch_connection(self):
        """Tester la connexion OpenSearch"""
        try:
            response = requests.get(f"{self.opensearch_url}/_cluster/health")
            if response.status_code == 200:
                health = response.json()
                return {
                    'status': 'success',
                    'cluster_status': health.get('status', 'unknown'),
                    'nodes': health.get('number_of_nodes', 0)
                }
            return {'status': 'error', 'message': 'OpenSearch non accessible'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def list_clients(self):
        """Lister tous les clients"""
        try:
            indexer = SimpleIndexer()
            all_indexes = indexer.list_indexes()
            
            clients = []
            for idx in all_indexes:
                if idx.startswith('askme-'):
                    client_id = idx.replace('askme-', '')
                    client_indexer = SimpleIndexer(index_name=idx)
                    stats = client_indexer.get_index_stats()
                    
                    client_info = {
                        'id': client_id,
                        'index': idx,
                        'documents_count': stats.get('documents_count', 0) if stats else 0,
                        'size_mb': stats.get('size_mb', 0) if stats else 0
                    }
                    
                    # Compter les documents physiques
                    client_path = self.clients_data_dir / client_id
                    if client_path.exists():
                        documents_path = client_path / "documents"
                        if documents_path.exists():
                            physical_docs = len([d for d in documents_path.iterdir() if d.is_dir()])
                            client_info['physical_documents'] = physical_docs
                        else:
                            client_info['physical_documents'] = 0
                    else:
                        client_info['physical_documents'] = 0
                    
                    clients.append(client_info)
            
            return {'status': 'success', 'clients': clients}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def create_client(self, client_id):
        """Créer un nouveau client"""
        try:
            # Validation
            if not client_id or not client_id.replace('-', '').replace('_', '').isalnum():
                return {'status': 'error', 'message': 'ID client invalide. Utilisez lettres, chiffres, - et _'}
            
            # Vérifier si existe déjà
            existing = self.list_clients()
            if existing['status'] == 'success':
                if any(c['id'] == client_id for c in existing['clients']):
                    return {'status': 'error', 'message': f'Client "{client_id}" existe déjà'}
            
            # Créer l'arborescence
            client_path = self.clients_data_dir / client_id
            documents_path = client_path / "documents"
            
            client_path.mkdir(parents=True, exist_ok=True)
            documents_path.mkdir(exist_ok=True)
            
            # Créer l'index OpenSearch
            success = SimpleIndexer.create_client_index(client_id, self.opensearch_url)
            if not success:
                return {'status': 'error', 'message': 'Échec création index OpenSearch'}
            
            # Initialiser l'état d'indexation
            state_path = client_path / ".index_state.json"
            with open(state_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
            
            return {'status': 'success', 'message': f'Client "{client_id}" créé avec succès'}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def delete_client(self, client_id):
        """Supprimer un client complètement"""
        try:
            # Supprimer l'index OpenSearch
            success = SimpleIndexer.delete_client_index(client_id, self.opensearch_url)
            if not success:
                return {'status': 'error', 'message': 'Échec suppression index OpenSearch'}
            
            # Supprimer les données physiques
            client_path = self.clients_data_dir / client_id
            if client_path.exists():
                shutil.rmtree(client_path)
            
            return {'status': 'success', 'message': f'Client "{client_id}" supprimé définitivement'}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def get_client_documents(self, client_id):
        """Récupérer les documents d'un client"""
        try:
            client_path = self.clients_data_dir / client_id
            documents_path = client_path / "documents"
            
            if not documents_path.exists():
                return {'status': 'success', 'documents': []}
            
            documents = []
            for doc_dir in documents_path.iterdir():
                if doc_dir.is_dir() and len(doc_dir.name) >= 32:
                    doc_id = doc_dir.name
                    metadata_file = doc_dir / "metadata.json"
                    
                    # Compter les PJ
                    attachments = [f for f in doc_dir.rglob('*') if f.is_file() and f.name != 'metadata.json']
                    
                    doc_info = {
                        'id': doc_id,
                        'short_id': doc_id[:8] + '...',
                        'attachments_count': len(attachments),
                        'attachments': []
                    }
                    
                    # Lire les métadonnées si elles existent
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                pj_metadata = json.load(f)
                            
                            for pj_name, metadata in pj_metadata.items():
                                pj_info = {
                                    'name': pj_name,
                                    'title': metadata.get('titreDocument', pj_name),
                                    'field_metadata': metadata.get('fieldMetadata', ''),
                                    'security_rights': metadata.get('securityRights', []),
                                    'storage_path': metadata.get('metadata_storage_path', '')
                                }
                                doc_info['attachments'].append(pj_info)
                        except:
                            pass
                    else:
                        # Pas de métadonnées, lister les fichiers physiques
                        for attachment in attachments:
                            pj_info = {
                                'name': attachment.name,
                                'title': attachment.name,
                                'field_metadata': '',
                                'security_rights': [],
                                'storage_path': str(attachment)
                            }
                            doc_info['attachments'].append(pj_info)
                    
                    documents.append(doc_info)
            
            return {'status': 'success', 'documents': documents}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def search_documents(self, client_id, query, user_rights=None, size=10, search_mode="hybrid"):
        """Rechercher dans les documents d'un client"""
        try:
            indexer = SimpleIndexer(opensearch_url=self.opensearch_url, index_name=self.get_client_index_name(client_id))
            
            # Recherche avec le mode spécifié
            results = indexer.search(query, user_rights, size, search_mode)
            
            if not results or 'hits' not in results:
                return {'status': 'success', 'results': [], 'total': 0}
            
            # Formater les résultats
            formatted_results = []
            for hit in results['hits']['hits']:
                source = hit['_source']
                # Récupérer le contenu avec highlight si disponible
                content = source.get('chunk', '')
                highlight = hit.get('highlight', {})
                if 'chunk' in highlight and highlight['chunk']:
                    # Utiliser le highlight (avec balises <mark>)
                    content = ' ... '.join(highlight['chunk'])
                else:
                    # Utiliser le contenu normal, mais plus long
                    content = content[:500] + ('...' if len(content) > 500 else '')
                
                result = {
                    'score': hit['_score'],
                    'chunk_id': source.get('chunk_id', ''),
                    'parent_id': source.get('parent_id', ''),
                    'title': source.get('title', source.get('titreDocument', 'Sans titre')),
                    'titre_document': source.get('titreDocument', source.get('title', 'Sans titre')),
                    'content': content,
                    'field_metadata': source.get('fieldMetadata', ''),
                    'security_rights': source.get('securityRights', []),
                    'storage_name': source.get('metadata_storage_name', source.get('title', 'Fichier inconnu')),
                    'storage_path': source.get('metadata_storage_path', f"/documents/{source.get('parent_id', 'unknown')}/{source.get('metadata_storage_name', source.get('title', 'unknown'))}")
                }
                formatted_results.append(result)
            
            return {
                'status': 'success',
                'results': formatted_results,
                'total': len(formatted_results),
                'query': query,
                'user_rights': user_rights,
                'search_mode': search_mode
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def upload_documents(self, client_id, files, metadata_dict):
        """Upload et indexation de documents"""
        try:
            # Créer le dossier du client
            client_path = self.clients_data_dir / client_id
            client_path.mkdir(exist_ok=True)
            documents_path = client_path / "documents"
            documents_path.mkdir(exist_ok=True)
            
            # Générer un UUID pour ce lot de documents
            document_uuid = str(uuid.uuid4())
            doc_folder = documents_path / document_uuid
            doc_folder.mkdir()
            
            uploaded_files = []
            metadata_for_doc = {}
            
            # Sauvegarder chaque fichier
            for file in files:
                if file and hasattr(file, 'filename') and file.filename:
                    filename = secure_filename(file.filename)
                    if not self._allowed_file(filename):
                        return {'status': 'error', 'message': f'Type de fichier non autorisé: {filename}'}
                    
                    file_path = doc_folder / filename
                    file.save(str(file_path))
                    uploaded_files.append(filename)
                    
                    # Métadonnées pour ce fichier - essayer différentes clés
                    original_filename = file.filename
                    file_metadata = metadata_dict.get(original_filename, metadata_dict.get(filename, {}))
                    
                    print(f"Traitement fichier: {original_filename} -> {filename}")
                    print(f"Métadonnées trouvées: {file_metadata}")
                    
                    metadata_for_doc[filename] = {
                        'securityRights': file_metadata.get('securityRights', []),
                        'titreDocument': file_metadata.get('titreDocument', filename),
                        'fieldMetadata': file_metadata.get('fieldMetadata', ''),
                        'metadata_storage_name': filename,
                        'metadata_storage_path': f'/documents/{document_uuid}/{filename}'
                    }
            
            # Sauvegarder le fichier metadata.json
            metadata_file = doc_folder / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata_for_doc, f, ensure_ascii=False, indent=2)
            
            # Indexer les documents
            indexer = SimpleIndexer(opensearch_url=self.opensearch_url, index_name=self.get_client_index_name(client_id))
            
            # S'assurer que l'index existe
            try:
                indexer.get_index_stats()
            except:
                # Créer l'index s'il n'existe pas
                indexer.create_client_index(client_id)
            
            # Indexer le dossier
            try:
                results = indexer.index_document(str(doc_folder))
                indexing_success = True
                indexing_message = "Indexation réussie"
            except Exception as e:
                print(f"Erreur indexation: {e}")
                results = str(e)
                indexing_success = False
                indexing_message = f"Erreur indexation: {e}"
            
            return {
                'status': 'success',
                'message': f'{len(uploaded_files)} fichier(s) uploadé(s) et indexé(s)',
                'document_uuid': document_uuid,
                'files': uploaded_files,
                'indexing_success': indexing_success,
                'indexing_message': indexing_message,
                'indexing_results': results
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def delete_document(self, client_id, document_uuid):
        """Supprimer un document et ses données indexées"""
        try:
            print(f"🗑️ Suppression document {document_uuid} pour client {client_id}")
            
            # Chemin du document
            client_path = self.clients_data_dir / client_id
            documents_path = client_path / "documents"
            doc_folder = documents_path / document_uuid
            
            print(f"Chemin du document: {doc_folder}")
            print(f"Dossier existe: {doc_folder.exists()}")
            
            if not doc_folder.exists():
                return {'status': 'error', 'message': 'Document non trouvé'}
            
            # Lire le metadata.json pour connaître les fichiers
            metadata_file = doc_folder / "metadata.json"
            deleted_files = []
            
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                deleted_files = list(metadata.keys())
            
            # Supprimer les données indexées de OpenSearch
            indexer = SimpleIndexer(opensearch_url=self.opensearch_url, index_name=self.get_client_index_name(client_id))
            
            # Rechercher tous les chunks de ce document UUID pour les supprimer
            search_query = {
                "query": {
                    "bool": {
                        "should": [
                            {"wildcard": {"metadata_storage_path": f"*/documents/{document_uuid}/*"}},
                            {"term": {"parent_id": document_uuid}}
                        ]
                    }
                },
                "size": 1000  # Augmenter pour récupérer tous les chunks
            }
            
            try:
                response = requests.post(
                    f"{self.opensearch_url}/askme-{client_id}/_search",
                    headers={"Content-Type": "application/json"},
                    json=search_query
                )
                
                if response.status_code == 200:
                    search_results = response.json()
                    chunks_to_delete = []
                    
                    for hit in search_results.get('hits', {}).get('hits', []):
                        chunks_to_delete.append(hit['_id'])
                    
                    # Supprimer chaque chunk
                    deleted_chunks = 0
                    for chunk_id in chunks_to_delete:
                        delete_response = requests.delete(
                            f"{self.opensearch_url}/askme-{client_id}/_doc/{chunk_id}"
                        )
                        if delete_response.status_code in [200, 404]:  # 404 = déjà supprimé
                            deleted_chunks += 1
                    
                    print(f"🗑️ Supprimé {deleted_chunks} chunks de l'index")
                
            except Exception as e:
                print(f"⚠️ Erreur suppression index: {e}")
            
            # Supprimer le dossier physique
            import shutil
            shutil.rmtree(doc_folder)
            
            return {
                'status': 'success',
                'message': f'Document {document_uuid} supprimé avec succès',
                'document_uuid': document_uuid,
                'deleted_files': deleted_files,
                'deleted_chunks': deleted_chunks if 'deleted_chunks' in locals() else 0
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _allowed_file(self, filename):
        """Vérifier si l'extension du fichier est autorisée"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Fonctions utilitaires
def allowed_file(filename):
    """Vérifier si l'extension du fichier est autorisée"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Instance globale du gestionnaire
manager = AskMeSearchManager()

# Routes de l'interface web
@app.route('/')
def index():
    """Page d'accueil"""
    # Test de connexion OpenSearch
    connection_test = manager.test_opensearch_connection()
    return render_template('index.html', connection_test=connection_test)


@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def chrome_devtools():
    """Route silencieuse pour Chrome DevTools"""
    return '', 204  # Réponse vide, pas de contenu

@app.route('/clients')
def clients():
    """Page de gestion des clients"""
    clients_list = manager.list_clients()
    return render_template('clients.html', clients=clients_list)

@app.route('/api/clients', methods=['GET'])
def api_list_clients():
    """API: Lister les clients"""
    return jsonify(manager.list_clients())

@app.route('/api/clients', methods=['POST'])
def api_create_client():
    """API: Créer un client"""
    data = request.get_json()
    client_id = data.get('client_id', '').strip()
    return jsonify(manager.create_client(client_id))

@app.route('/api/clients/<client_id>', methods=['DELETE'])
def api_delete_client(client_id):
    """API: Supprimer un client"""
    return jsonify(manager.delete_client(client_id))

@app.route('/client/<client_id>')
def client_detail(client_id):
    """Page de détail d'un client"""
    documents = manager.get_client_documents(client_id)
    return render_template('client_detail.html', client_id=client_id, documents=documents)

@app.route('/client/<client_id>/document/<doc_id>/attachments')
def document_attachments(client_id, doc_id):
    """Page de gestion des pièces jointes d'un document"""
    try:
        # Vérifier que le document existe
        doc_path = Path(CLIENTS_DATA_DIR) / client_id / "documents" / doc_id
        if not doc_path.exists():
            flash(f'Document {doc_id} non trouvé', 'error')
            return redirect(url_for('client_detail', client_id=client_id))
        
        # Lister les pièces jointes
        attachments = []
        metadata_file = doc_path / "metadata.json"
        metadata = {}
        
        # Charger les métadonnées si elles existent
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except:
                pass
        
        # Lister les fichiers physiques
        for attachment_file in doc_path.rglob('*'):
            if attachment_file.is_file() and attachment_file.name != 'metadata.json':
                file_name = attachment_file.name
                file_stats = attachment_file.stat()
                
                # Icône et couleur selon l'extension
                extension = attachment_file.suffix.lower().lstrip('.')
                icon, color = get_file_icon_color(extension)
                
                attachment_info = {
                    'name': file_name,
                    'size_bytes': file_stats.st_size,
                    'size_human': format_file_size(file_stats.st_size),
                    'extension': extension,
                    'icon': icon,
                    'color': color,
                    'modified_date': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    'metadata': metadata.get(file_name, {}),
                    'path': str(attachment_file)
                }
                attachments.append(attachment_info)
        
        # Trier par nom
        attachments.sort(key=lambda x: x['name'])
        
        return render_template('document_attachments.html', 
                             client_id=client_id, 
                             doc_id=doc_id,
                             doc_path=str(doc_path),
                             attachments=attachments)
        
    except Exception as e:
        flash(f'Erreur lors du chargement des pièces jointes: {e}', 'error')
        return redirect(url_for('client_detail', client_id=client_id))

@app.route('/api/clients/<client_id>/documents')
def api_client_documents(client_id):
    """API: Documents d'un client"""
    return jsonify(manager.get_client_documents(client_id))

@app.route('/client/<client_id>/search')
def client_search(client_id):
    """Page de recherche pour un client"""
    return render_template('search.html', client_id=client_id)

@app.route('/client/<client_id>/sync')
def client_sync(client_id):
    """Page de synchronisation pour un client spécifique"""
    # Vérifier que le client existe
    clients_result = manager.list_clients()
    if clients_result['status'] != 'success':
        return redirect(url_for('clients'))
    
    client_exists = any(c['id'] == client_id for c in clients_result['clients'])
    if not client_exists:
        return redirect(url_for('clients'))
    
    return render_template('client_sync_simple.html', client_id=client_id)

@app.route('/api/clients/<client_id>/search', methods=['POST'])
def api_search(client_id):
    """API: Rechercher dans un client"""
    data = request.get_json()
    query = data.get('query', '').strip()
    user_rights = data.get('user_rights', [])
    size = data.get('size', 10)
    search_mode = data.get('search_mode', 'hybrid')  # "text", "vector", "hybrid"
    
    if not query:
        return jsonify({'status': 'error', 'message': 'Requête vide'})
    
    # Valider le mode de recherche
    valid_modes = ['text', 'vector', 'hybrid']
    if search_mode not in valid_modes:
        return jsonify({
            'status': 'error', 
            'message': f'Mode de recherche invalide. Modes supportés: {", ".join(valid_modes)}'
        })
    
    return jsonify(manager.search_documents(client_id, query, user_rights, size, search_mode))

@app.route('/upload/<client_id>')
def upload_page(client_id):
    """Page d'upload de documents"""
    return render_template('upload.html', client_id=client_id)

@app.route('/api/clients/<client_id>/upload', methods=['POST'])
def api_upload_documents(client_id):
    """API: Upload de documents avec métadonnées"""
    try:
        # Vérifier les fichiers
        if 'files' not in request.files:
            return jsonify({'status': 'error', 'message': 'Aucun fichier fourni'})
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'status': 'error', 'message': 'Aucun fichier sélectionné'})
        
        # Récupérer les métadonnées depuis le formulaire
        metadata_json = request.form.get('metadata', '{}')
        try:
            metadata_dict = json.loads(metadata_json)
        except json.JSONDecodeError:
            return jsonify({'status': 'error', 'message': 'Métadonnées JSON invalides'})
        
        # Valider les fichiers
        for file in files:
            if file.filename and not allowed_file(file.filename):
                return jsonify({
                    'status': 'error', 
                    'message': f'Type de fichier non autorisé: {file.filename}. Types autorisés: {", ".join(ALLOWED_EXTENSIONS)}'
                })
        
        # Debug: afficher les données reçues
        print(f"Fichiers reçus: {[f.filename for f in files]}")
        print(f"Métadonnées reçues: {metadata_dict}")
        
        # Upload et indexation
        result = manager.upload_documents(client_id, files, metadata_dict)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/documents/<doc_id>/inspect', methods=['GET'])
def api_inspect_document(client_id, doc_id):
    """API: Inspecter un document spécifique pour comprendre pourquoi l'indexation échoue"""
    try:
        from pathlib import Path
        import os
        
        data_dir = Path("clients-data")
        doc_path = data_dir / client_id / "documents" / doc_id
        
        if not doc_path.exists():
            return jsonify({'status': 'error', 'message': f'Document {doc_id} introuvable'})
        
        inspection = {
            'doc_id': doc_id,
            'doc_path': str(doc_path),
            'exists': doc_path.exists(),
            'is_directory': doc_path.is_dir(),
            'files': [],
            'metadata': {},
            'size_info': {},
            'permissions': {},
            'content_analysis': {}
        }
        
        # Lister tous les fichiers
        if doc_path.exists():
            for file_path in doc_path.rglob('*'):
                if file_path.is_file():
                    file_info = {
                        'name': file_path.name,
                        'relative_path': str(file_path.relative_to(doc_path)),
                        'absolute_path': str(file_path),  # Conversion explicite en string
                        'size_bytes': file_path.stat().st_size,
                        'extension': file_path.suffix.lower(),
                        'is_metadata': file_path.name == 'metadata.json',
                        'readable': os.access(file_path, os.R_OK)
                    }
                    
                    # Essayer de lire un peu du contenu pour les petits fichiers
                    if file_path.name == 'metadata.json':
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                import json
                                inspection['metadata'] = json.load(f)
                        except Exception as e:
                            inspection['metadata'] = {'error': str(e)}
                    elif file_info['size_bytes'] < 1000:  # Fichiers < 1KB
                        try:
                            with open(file_path, 'rb') as f:
                                first_bytes = f.read(100)
                                file_info['first_bytes_hex'] = first_bytes.hex()
                                file_info['first_bytes_text'] = first_bytes.decode('utf-8', errors='ignore')[:50]
                        except Exception as e:
                            file_info['read_error'] = str(e)
                    
                    inspection['files'].append(file_info)
        
        # Analyse des contenus
        non_metadata_files = [f for f in inspection['files'] if not f['is_metadata']]
        
        inspection['content_analysis'] = {
            'total_files': len(inspection['files']),
            'attachment_files': len(non_metadata_files),
            'has_metadata_json': any(f['is_metadata'] for f in inspection['files']),
            'total_size_bytes': sum(f['size_bytes'] for f in inspection['files']),
            'file_extensions': list(set(f['extension'] for f in non_metadata_files if f['extension'])),
            'empty_files': [f['name'] for f in non_metadata_files if f['size_bytes'] == 0],
            'unreadable_files': [f['name'] for f in inspection['files'] if not f.get('readable', True)]
        }
        
        # Vérification finale pour éviter les erreurs de sérialisation
        def ensure_json_serializable(obj):
            """Convertir récursivement tous les Path en string"""
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: ensure_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [ensure_json_serializable(item) for item in obj]
            else:
                return obj
        
        inspection_safe = ensure_json_serializable(inspection)
        
        return jsonify({
            'status': 'success',
            'inspection': inspection_safe
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/documents/<document_uuid>', methods=['DELETE'])
def api_delete_document(client_id, document_uuid):
    """API: Supprimer un document"""
    try:
        result = manager.delete_document(client_id, document_uuid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ROUTES DE SYNCHRONISATION
# ========================================

@app.route('/sync')
def sync_dashboard():
    """Page principale de gestion de la synchronisation"""
    return render_template('sync_dashboard.html')

@app.route('/monitoring')
def monitoring_dashboard():
    """Page de monitoring OpenSearch"""
    client_id = request.args.get('client_id', '')
    return render_template('index_monitoring.html', preselected_client=client_id)

@app.route('/api/sync/tasks', methods=['GET'])
def api_get_sync_tasks():
    """API: Récupérer toutes les tâches de synchronisation"""
    try:
        tasks = sync_manager.get_tasks()
        return jsonify({'status': 'success', 'tasks': tasks})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync/tasks', methods=['POST'])
def api_create_sync_task():
    """API: Créer une nouvelle tâche de synchronisation"""
    try:
        data = request.get_json()
        
        required_fields = ['client_id', 'name', 'schedule_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'message': f'Champ requis manquant: {field}'})
        
        task_id = sync_manager.create_task(
            client_id=data['client_id'],
            name=data['name'],
            schedule_type=data['schedule_type'],
            schedule_time=data.get('schedule_time', '02:00'),
            options=data.get('options', {})
        )
        
        return jsonify({
            'status': 'success', 
            'message': 'Tâche créée avec succès',
            'task_id': task_id
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync/tasks/<task_id>', methods=['PUT'])
def api_update_sync_task(task_id):
    """API: Modifier une tâche de synchronisation"""
    try:
        data = request.get_json()
        result = sync_manager.update_task(task_id, data)
        
        if result:
            return jsonify({'status': 'success', 'message': 'Tâche mise à jour'})
        else:
            return jsonify({'status': 'error', 'message': 'Tâche non trouvée'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync/tasks/<task_id>', methods=['DELETE'])
def api_delete_sync_task(task_id):
    """API: Supprimer une tâche de synchronisation"""
    try:
        result = sync_manager.delete_task(task_id)
        
        if result:
            return jsonify({'status': 'success', 'message': 'Tâche supprimée'})
        else:
            return jsonify({'status': 'error', 'message': 'Tâche non trouvée'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync/tasks/<task_id>/run', methods=['POST'])
def api_run_sync_task(task_id):
    """API: Exécuter une tâche manuellement"""
    try:
        result = sync_manager.run_sync_task(task_id)
        
        if result:
            return jsonify({'status': 'success', 'message': 'Synchronisation démarrée'})
        else:
            return jsonify({'status': 'error', 'message': 'Tâche non trouvée ou en cours'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync/results')
def api_get_sync_results():
    """API: Récupérer l'historique des synchronisations"""
    try:
        limit = request.args.get('limit', 100, type=int)
        results = sync_manager.get_results(limit=limit)
        return jsonify({'status': 'success', 'results': results})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync/status')
def api_get_sync_status():
    """API: Récupérer le statut global de synchronisation"""
    try:
        status = sync_manager.get_status()
        return jsonify({'status': 'success', **status})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# Routes de synchronisation spécifiques client
@app.route('/api/clients/<client_id>/sync', methods=['POST'])
def api_client_sync(client_id):
    """API: Lancer la synchronisation pour un client spécifique avec progression temps réel"""
    try:
        # Lancer la synchronisation avec progression dans un thread séparé
        def run_sync_with_progress():
            start_time = datetime.now()  # Définir start_time au début
            
            # Initialiser l'état de synchronisation
            sync_states[client_id] = {
                'in_progress': True,
                'cancelled': False,
                'current_data': None
            }
            
            try:
                # Émettre le début de synchronisation
                print(f"🔧 Émission sync_progress start pour room {client_id}")
                socketio.emit('sync_progress', {
                    'client_id': client_id,
                    'phase': 'start',
                    'progress_percent': 0,
                    'message': 'Démarrage de la synchronisation...',
                    'elapsed_time': 0,
                    'current_doc': 0,
                    'total_docs': 0,
                    'completed_docs_count': 0,
                    'processed_chunks': 0,
                    'total_chunks': 0
                }, room=client_id)
                
                # Petit délai pour s'assurer que l'événement est envoyé
                socketio.sleep(0.1)
            
                # Créer une fonction wrapper pour les événements SocketIO
                def emit_progress(message, phase='processing', progress=50, **kwargs):
                    elapsed = (datetime.now() - start_time).total_seconds()
                    print(f"🔧 Émission sync_progress {phase} pour room {client_id}: {message}")
                    
                    # Construire les données complètes attendues par le client
                    progress_data = {
                        'client_id': client_id,
                        'phase': phase,
                        'progress_percent': progress,
                        'message': message,
                        'elapsed_time': elapsed,
                        'current_doc': kwargs.get('current_doc', 0),
                        'total_docs': kwargs.get('total_docs', 0),
                        'completed_docs_count': kwargs.get('completed_docs_count', 0),
                        'processed_chunks': kwargs.get('processed_chunks', 0),
                        'total_chunks': kwargs.get('total_chunks', 0),
                        'doc_id': kwargs.get('doc_id', ''),
                        'filename': kwargs.get('filename', '')
                    }
                    
                    socketio.emit('sync_progress', progress_data, room=client_id)
                
                result = sync_client_incremental(
                    client_id=client_id,
                    data_dir=Path("clients-data"),
                    opensearch_url=OPENSEARCH_URL,
                    emit_progress=emit_progress
                )
                
                # Le message de completion sera émis par sync_engine.py
                print(f"🔧 Synchronisation terminée pour room {client_id}")
                # socketio.emit('sync_progress', {
                #     'client_id': client_id,
                #     'phase': 'complete',
                #     'progress_percent': 100,
                #     'message': 'Synchronisation terminée avec succès',
                #     'result': result
                # }, room=client_id)
                
            except Exception as e:
                # Émettre l'erreur de synchronisation
                print(f"🔧 Émission sync_progress error pour room {client_id}: {e}")
                socketio.emit('sync_progress', {
                    'client_id': client_id,
                    'phase': 'error',
                    'progress_percent': 0,
                    'message': f'Erreur de synchronisation: {str(e)}',
                    'error': str(e)
                }, room=client_id)
            finally:
                # Nettoyer l'état de synchronisation
                if client_id in sync_states:
                    sync_states[client_id]['in_progress'] = False
        
        # Lancer dans une tâche background SocketIO pour avoir le bon contexte
        socketio.start_background_task(run_sync_with_progress)
        
        return jsonify({
            'status': 'success',
            'message': 'Synchronisation démarrée - suivez la progression en temps réel',
            'progress_enabled': True
        })
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/sync/debug', methods=['GET'])
def api_client_sync_debug(client_id):
    """API: Diagnostiquer l'état de synchronisation d'un client"""
    try:
        from sync_engine import detect_document_changes
        from pathlib import Path
        
        data_dir = Path("clients-data")
        client_path = data_dir / client_id
        documents_path = client_path / "documents"
        state_file = client_path / ".index_state.json"
        
        # Détection des changements
        changes = detect_document_changes(client_id, data_dir)
        
        if 'error' in changes:
            return jsonify({'status': 'error', 'message': changes['error']})
        
        # Nettoyer les objets Path pour JSON serialization
        def clean_changes_for_json(changes_dict):
            cleaned = {}
            for key, value in changes_dict.items():
                if isinstance(value, list):
                    cleaned_list = []
                    for item in value:
                        if isinstance(item, dict):
                            # Supprimer les clés avec des objets Path
                            cleaned_item = {k: v for k, v in item.items() if k != 'doc_dir'}
                            cleaned_list.append(cleaned_item)
                        else:
                            cleaned_list.append(item)
                    cleaned[key] = cleaned_list
                else:
                    cleaned[key] = value
            return cleaned
        
        changes_cleaned = clean_changes_for_json(changes)
        
        # Informations sur les chemins
        debug_info = {
            'client_path_exists': client_path.exists(),
            'documents_path_exists': documents_path.exists(),
            'state_file_exists': state_file.exists(),
            'changes_detected': changes_cleaned,
            'documents_found': []
        }
        
        # Lister les documents physiques avec infos
        if documents_path.exists():
            for doc_dir in documents_path.iterdir():
                if doc_dir.is_dir():
                    doc_info = {
                        'doc_id': doc_dir.name,
                        'is_uuid_like': len(doc_dir.name) >= 32,
                        'attachments_count': len([f for f in doc_dir.rglob('*') if f.is_file() and f.name != 'metadata.json']),
                        'has_metadata': (doc_dir / "metadata.json").exists()
                    }
                    debug_info['documents_found'].append(doc_info)
        
        # État actuel d'indexation
        from sync_engine import load_index_state
        current_state = load_index_state(state_file)
        debug_info['current_state'] = current_state
        
        # Vérification finale pour s'assurer qu'il n'y a pas d'objets Path
        def ensure_json_serializable(obj):
            """Convertir récursivement tous les Path en string"""
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: ensure_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [ensure_json_serializable(item) for item in obj]
            else:
                return obj
        
        debug_info_safe = ensure_json_serializable(debug_info)
        
        return jsonify({
            'status': 'success',
            'debug_info': debug_info_safe
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/sync/reset', methods=['POST'])
def api_client_sync_reset(client_id):
    """API: Reset l'état de synchronisation d'un client"""
    try:
        from pathlib import Path
        
        data_dir = Path("clients-data")
        client_path = data_dir / client_id
        state_file = client_path / ".index_state.json"
        
        if not client_path.exists():
            return jsonify({'status': 'error', 'message': f'Client {client_id} inexistant'})
        
        # 1. Vider complètement l'index OpenSearch
        index_name = manager.get_client_index_name(client_id)
        deleted_count = 0
        
        try:
            # Supprimer tous les documents de l'index
            delete_response = requests.post(
                f"{OPENSEARCH_URL}/{index_name}/_delete_by_query?refresh=true",
                headers={"Content-Type": "application/json"},
                json={"query": {"match_all": {}}}
            )
            
            if delete_response.status_code == 200:
                result = delete_response.json()
                deleted_count = result.get('deleted', 0)
                
                # Forcer la fusion des segments pour libérer l'espace
                requests.post(f"{OPENSEARCH_URL}/{index_name}/_forcemerge?max_num_segments=1")
            else:
                return jsonify({
                    'status': 'error', 
                    'message': f'Erreur suppression index: {delete_response.status_code}'
                })
        
        except Exception as e:
            return jsonify({
                'status': 'error', 
                'message': f'Erreur accès OpenSearch: {str(e)}'
            })
        
        # 2. Supprimer le fichier d'état local
        if state_file.exists():
            state_file.unlink()
        
        # 3. Créer un nouvel état vide
        with open(state_file, 'w', encoding='utf-8') as f:
            import json
            json.dump({}, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': f'Reset complet effectué: {deleted_count} documents supprimés de l\'index OpenSearch',
            'deleted_docs': deleted_count
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/sync/verify', methods=['GET'])
def api_client_sync_verify(client_id):
    """API: Vérifier la cohérence entre l'état local et l'index OpenSearch"""
    try:
        from pathlib import Path
        from sync_engine import load_index_state
        import requests
        
        data_dir = Path("clients-data")
        client_path = data_dir / client_id
        state_file = client_path / ".index_state.json"
        
        # Charger l'état local
        local_state = load_index_state(state_file)
        local_documents = set(local_state.keys())
        
        # Requêter l'index OpenSearch
        search_query = {
            "aggs": {
                "unique_parents": {
                    "terms": {
                        "field": "parent_id",
                        "size": 10000
                    }
                }
            },
            "size": 0
        }
        
        response = requests.post(
            f"{OPENSEARCH_URL}/askme-{client_id}/_search",
            headers={"Content-Type": "application/json"},
            json=search_query
        )
        
        indexed_documents = set()
        total_chunks = 0
        
        if response.status_code == 200:
            search_results = response.json()
            total_chunks = search_results.get('hits', {}).get('total', {}).get('value', 0)
            
            buckets = search_results.get('aggregations', {}).get('unique_parents', {}).get('buckets', [])
            for bucket in buckets:
                indexed_documents.add(bucket['key'])
        
        # Comparer
        only_in_local = local_documents - indexed_documents
        only_in_index = indexed_documents - local_documents
        
        verification = {
            'index_name': f'askme-{client_id}',
            'total_chunks_in_index': total_chunks,
            'unique_documents_in_index': len(indexed_documents),
            'documents_in_local_state': len(local_documents),
            'discrepancies': [],
            'indexed_documents': [{'parent_id': doc_id, 'chunks_count': 'N/A'} for doc_id in indexed_documents],
            'local_state_documents': list(local_documents)
        }
        
        if only_in_local:
            verification['discrepancies'].append({
                'type': 'ONLY_IN_LOCAL',
                'message': f'{len(only_in_local)} documents dans l\'état local mais pas dans l\'index',
                'documents': list(only_in_local)
            })
        
        if only_in_index:
            verification['discrepancies'].append({
                'type': 'ONLY_IN_INDEX',
                'message': f'{len(only_in_index)} documents dans l\'index mais pas dans l\'état local',
                'documents': list(only_in_index)
            })
        
        return jsonify({
            'status': 'success',
            'verification': verification
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# API pour gestion des pièces jointes
@app.route('/api/clients/<client_id>/documents/<doc_id>/attachments/<filename>', methods=['DELETE'])
def api_delete_attachment(client_id, doc_id, filename):
    """API: Supprimer une pièce jointe spécifique"""
    try:
        from urllib.parse import unquote
        from sync_engine import delete_document_by_parent_id
        
        filename = unquote(filename)
        
        # Vérifier que le document existe
        doc_path = Path(CLIENTS_DATA_DIR) / client_id / "documents" / doc_id
        if not doc_path.exists():
            return jsonify({'status': 'error', 'message': 'Document non trouvé'})
        
        # Vérifier que le fichier existe
        attachment_path = None
        for file_path in doc_path.rglob('*'):
            if file_path.is_file() and file_path.name == filename:
                attachment_path = file_path
                break
        
        if not attachment_path:
            return jsonify({'status': 'error', 'message': f'Pièce jointe "{filename}" non trouvée'})
        
        # Supprimer les chunks de cette PJ de l'index OpenSearch - VERSION OPTIMISÉE
        from sync_engine import delete_attachment_chunks
        deleted_chunks = delete_attachment_chunks(client_id, doc_id, filename, OPENSEARCH_URL)
        
        # Supprimer le fichier physique
        attachment_path.unlink()
        
        # Mettre à jour les métadonnées si elles existent
        metadata_file = doc_path / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                if filename in metadata:
                    del metadata[filename]
                    
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
            except:
                pass
        
        return jsonify({
            'status': 'success',
            'message': f'Pièce jointe "{filename}" supprimée avec succès ({deleted_chunks} chunks supprimés de l\'index)',
            'deleted_chunks': deleted_chunks
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/documents/<doc_id>/attachments/<filename>/metadata', methods=['GET'])
def api_get_attachment_metadata(client_id, doc_id, filename):
    """API: Récupérer les métadonnées d'une pièce jointe"""
    try:
        from urllib.parse import unquote
        filename = unquote(filename)
        
        doc_path = Path(CLIENTS_DATA_DIR) / client_id / "documents" / doc_id
        metadata_file = doc_path / "metadata.json"
        
        if not metadata_file.exists():
            return jsonify({
                'status': 'success',
                'metadata': {},
                'message': 'Aucun fichier de métadonnées trouvé'
            })
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        attachment_metadata = metadata.get(filename, {})
        
        return jsonify({
            'status': 'success',
            'metadata': attachment_metadata
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/documents/<doc_id>/attachments/<filename>/preview', methods=['GET'])
def api_preview_attachment(client_id, doc_id, filename):
    """API: Aperçu du contenu d'une pièce jointe"""
    try:
        from urllib.parse import unquote
        filename = unquote(filename)
        
        # Trouver le fichier
        doc_path = Path(CLIENTS_DATA_DIR) / client_id / "documents" / doc_id
        attachment_path = None
        
        for file_path in doc_path.rglob('*'):
            if file_path.is_file() and file_path.name == filename:
                attachment_path = file_path
                break
        
        if not attachment_path:
            return jsonify({'status': 'error', 'message': 'Fichier non trouvé'})
        
        # Extraire le contenu
        index_name = 'askme-documents' if client_id == 'askme' else f'askme-{client_id}'
        indexer = SimpleIndexer(opensearch_url=OPENSEARCH_URL, index_name=index_name)
        content = indexer.processor.extract_text(attachment_path)
        
        return jsonify({
            'status': 'success',
            'content': content[:10000],  # Limiter à 10KB pour l'aperçu
            'content_length': len(content),
            'truncated': len(content) > 10000
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/documents/<doc_id>/attachments/<filename>/reindex', methods=['POST'])
def api_reindex_attachment(client_id, doc_id, filename):
    """API: Réindexer une pièce jointe spécifique"""
    try:
        from urllib.parse import unquote
        from sync_engine import get_pj_metadata
        
        filename = unquote(filename)
        
        # Trouver le fichier
        doc_path = Path(CLIENTS_DATA_DIR) / client_id / "documents" / doc_id
        attachment_path = None
        
        for file_path in doc_path.rglob('*'):
            if file_path.is_file() and file_path.name == filename:
                attachment_path = file_path
                break
        
        if not attachment_path:
            return jsonify({'status': 'error', 'message': 'Fichier non trouvé'})
        
        # Supprimer les anciens chunks de cette PJ - VERSION OPTIMISÉE
        from sync_engine import delete_attachment_chunks
        deleted_chunks = delete_attachment_chunks(client_id, doc_id, filename, OPENSEARCH_URL)
        
        # Réindexer le fichier
        index_name = 'askme-documents' if client_id == 'askme' else f'askme-{client_id}'
        indexer = SimpleIndexer(opensearch_url=OPENSEARCH_URL, index_name=index_name)
        
        # Récupérer les métadonnées
        pj_metadata = get_pj_metadata(doc_path, filename)
        titre_document = pj_metadata.get('titreDocument', filename)
        field_metadata = pj_metadata.get('fieldMetadata', '')
        security_rights = pj_metadata.get('securityRights', None)
        metadata_storage_name = pj_metadata.get('metadata_storage_name', filename)
        metadata_storage_path = pj_metadata.get('metadata_storage_path', f'/documents/{doc_id}/{filename}')
        
        # Extraire et indexer
        content = indexer.processor.extract_text(attachment_path)
        if not content or len(content.strip()) < 10:
            return jsonify({'status': 'error', 'message': 'Contenu vide ou trop court'})
        
        chunks = indexer.splitter.split_text(content)
        if not chunks:
            return jsonify({'status': 'error', 'message': 'Aucun chunk généré'})
        
        indexed_chunks = 0
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_{filename}_chunk_{i}"
            
            doc = {
                "chunk_id": chunk_id,
                "parent_id": doc_id,
                "chunk": chunk,
                "title": titre_document,
                "metadata_storage_last_modified": datetime.now().isoformat(),
                "metadata_storage_name": metadata_storage_name,
                "metadata_storage_path": metadata_storage_path,
                "securityRights": security_rights if security_rights else [],
                "titreDocument": titre_document,
                "fieldMetadata": field_metadata
            }
            
            response = requests.post(
                f"{indexer.opensearch_url}/{indexer.index_name}/_doc/{chunk_id}",
                headers={"Content-Type": "application/json"},
                json=doc
            )
            
            if response.status_code in [200, 201]:
                indexed_chunks += 1
        
        return jsonify({
            'status': 'success',
            'message': f'Pièce jointe "{filename}" réindexée: {indexed_chunks} chunks indexés ({deleted_chunks} anciens supprimés)',
            'indexed_chunks': indexed_chunks,
            'deleted_chunks': deleted_chunks
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/documents/<doc_id>/reindex', methods=['POST'])
def api_reindex_document(client_id, doc_id):
    """API: Réindexer un document complet"""
    try:
        from sync_engine import index_document_with_attachments, delete_document_by_parent_id
        
        doc_path = Path(CLIENTS_DATA_DIR) / client_id / "documents" / doc_id
        if not doc_path.exists():
            return jsonify({'status': 'error', 'message': 'Document non trouvé'})
        
        # Supprimer tous les anciens chunks de ce document
        deleted_chunks = delete_document_by_parent_id(client_id, doc_id, OPENSEARCH_URL)
        
        # Réindexer le document
        success = index_document_with_attachments(client_id, doc_id, doc_path, OPENSEARCH_URL)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Document réindexé avec succès ({deleted_chunks} anciens chunks supprimés)',
                'deleted_chunks': deleted_chunks
            })
        else:
            return jsonify({'status': 'error', 'message': 'Erreur lors de la réindexation'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/clients/<client_id>/documents/<doc_id>/verify', methods=['GET'])
def api_verify_document_indexing(client_id, doc_id):
    """API: Vérifier l'indexation d'un document"""
    try:
        # Compter les chunks dans l'index
        search_query = {
            "query": {"term": {"parent_id": doc_id}},
            "size": 0
        }
        
        response = requests.post(
            f"{OPENSEARCH_URL}/askme-{client_id}/_search",
            headers={"Content-Type": "application/json"},
            json=search_query
        )
        
        chunks_in_index = 0
        if response.status_code == 200:
            search_results = response.json()
            chunks_in_index = search_results.get('hits', {}).get('total', {}).get('value', 0)
        
        # Compter les pièces jointes physiques
        doc_path = Path(CLIENTS_DATA_DIR) / client_id / "documents" / doc_id
        attachments_count = 0
        if doc_path.exists():
            attachments_count = len([f for f in doc_path.rglob('*') if f.is_file() and f.name != 'metadata.json'])
        
        return jsonify({
            'status': 'success',
            'chunks_in_index': chunks_in_index,
            'attachments_count': attachments_count,
            'doc_exists': doc_path.exists()
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# WebSocket handlers pour la progression temps réel
@socketio.on('connect')
def handle_connect():
    print(f"🔌 Client connecté: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"🔌 Client déconnecté: {request.sid}")

# ============================================================================
# ENDPOINTS DE MONITORING OPENSEARCH
# ============================================================================

@app.route('/api/opensearch/cluster/health', methods=['GET'])
def api_opensearch_cluster_health():
    """API: État de santé du cluster OpenSearch"""
    try:
        response = requests.get(f"{OPENSEARCH_URL}/_cluster/health")
        
        if response.status_code == 200:
            health_data = response.json()
            return jsonify({
                'status': 'success',
                'health': health_data
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'OpenSearch inaccessible: {response.status_code}'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur connexion OpenSearch: {str(e)}'
        })

@app.route('/api/opensearch/indices/<index_name>/stats', methods=['GET'])
def api_opensearch_index_stats(index_name):
    """API: Statistiques d'un index"""
    try:
        # Stats de l'index
        stats_response = requests.get(f"{OPENSEARCH_URL}/{index_name}/_stats")
        
        if stats_response.status_code == 200:
            stats_data = stats_response.json()
            index_stats = stats_data['indices'][index_name]['total']
            
            return jsonify({
                'status': 'success',
                'stats': {
                    'total_docs': index_stats['docs']['count'],
                    'deleted_docs': index_stats['docs']['deleted'],
                    'store_size_bytes': index_stats['store']['size_in_bytes'],
                    'indexing_operations': index_stats['indexing']['index_total'],
                    'search_operations': index_stats['search']['query_total']
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Index {index_name} non trouvé'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur statistiques: {str(e)}'
        })

@app.route('/api/opensearch/indices/<index_name>/documents', methods=['GET'])
def api_opensearch_index_documents(index_name):
    """API: Liste des documents dans un index"""
    try:
        # Requête pour obtenir les documents groupés par parent_id
        search_query = {
            "size": 0,
            "aggs": {
                "documents": {
                    "terms": {
                        "field": "parent_id",
                        "size": 10000
                    },
                    "aggs": {
                        "chunks_count": {
                            "value_count": {"field": "chunk_id"}
                        },
                        "avg_chunk_size": {
                            "avg": {"script": "doc['chunk'].value.length()"}
                        },
                        "last_modified": {
                            "max": {"field": "metadata_storage_last_modified"}
                        }
                    }
                }
            }
        }
        
        response = requests.post(
            f"{OPENSEARCH_URL}/{index_name}/_search",
            headers={"Content-Type": "application/json"},
            json=search_query
        )
        
        if response.status_code == 200:
            search_data = response.json()
            documents = []
            
            for bucket in search_data['aggregations']['documents']['buckets']:
                documents.append({
                    'parent_id': bucket['key'],
                    'chunks_count': bucket['chunks_count']['value'],
                    'avg_chunk_size': bucket.get('avg_chunk_size', {}).get('value', 0),
                    'last_modified': bucket.get('last_modified', {}).get('value_as_string', 'N/A')
                })
            
            # Trier par date de modification
            documents.sort(key=lambda x: x['last_modified'], reverse=True)
            
            return jsonify({
                'status': 'success',
                'documents': documents
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Erreur recherche dans {index_name}'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur liste documents: {str(e)}'
        })

@app.route('/api/opensearch/indices/<index_name>/<endpoint>', methods=['POST'])
def api_opensearch_query_console(index_name, endpoint):
    """API: Console de requêtes OpenSearch"""
    try:
        query_data = request.get_json()
        
        # Vérifier que l'endpoint est autorisé
        allowed_endpoints = ['_search', '_count', '_stats', '_mapping']
        if endpoint not in allowed_endpoints:
            return jsonify({
                'status': 'error',
                'message': f'Endpoint non autorisé: {endpoint}'
            })
        
        # Traitement spécifique selon l'endpoint
        if endpoint == '_stats' or endpoint == '_mapping':
            # Ces endpoints n'acceptent pas de body
            response = requests.get(f"{OPENSEARCH_URL}/{index_name}/{endpoint}")
        
        elif endpoint == '_count':
            # L'endpoint _count ne supporte que la query, pas size/from/sort
            if query_data and 'query' in query_data:
                # Nettoyer la requête pour _count (garder seulement query)
                clean_query = {'query': query_data['query']}
            else:
                clean_query = query_data
            
            response = requests.post(
                f"{OPENSEARCH_URL}/{index_name}/{endpoint}",
                headers={"Content-Type": "application/json"},
                json=clean_query
            )
        
        else:  # _search
            # L'endpoint _search accepte tous les paramètres
            response = requests.post(
                f"{OPENSEARCH_URL}/{index_name}/{endpoint}",
                headers={"Content-Type": "application/json"},
                json=query_data
            )
        
        if response.status_code == 200:
            return jsonify({
                'status': 'success',
                'result': response.json()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Erreur OpenSearch: {response.status_code}',
                'detail': response.text
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur requête: {str(e)}'
        })

# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

# Dictionnaire pour stocker l'état des synchronisations
sync_states = {}

@socketio.on('join_sync_room')
def handle_join_sync_room(data):
    client_id = data.get('client_id')
    if client_id:
        join_room(client_id)
        print(f"🏠 Client {request.sid} rejoint la room {client_id}")
        # Confirmer la connexion à la room
        emit('room_joined', {'client_id': client_id, 'room': client_id})
        
        # Test immédiat pour vérifier que les événements arrivent (mode silencieux)
        # emit('sync_progress', {
        #     'client_id': client_id,
        #     'phase': 'test',
        #     'progress_percent': 0,
        #     'message': 'Test de connexion room - vous devriez voir ce message'
        # }, room=client_id)

@socketio.on('check_sync_status')
def handle_check_sync_status(data):
    client_id = data.get('client_id')
    if client_id and client_id in sync_states:
        socketio.emit('sync_status', {
            'in_progress': sync_states[client_id].get('in_progress', False),
            'current_data': sync_states[client_id].get('current_data', None)
        }, room=client_id)
    else:
        socketio.emit('sync_status', {'in_progress': False}, room=client_id)

@socketio.on('cancel_sync')
def handle_cancel_sync(data):
    client_id = data.get('client_id')
    if client_id in sync_states:
        sync_states[client_id]['cancelled'] = True
        print(f"❌ Annulation demandée pour {client_id}")

if __name__ == '__main__':
    print("🌐 Démarrage de l'interface web AskMe Search")
    print("=" * 50)
    print("📡 Interface disponible sur: http://localhost:5000")
    print("🔧 Fonctionnalités disponibles:")
    print("   • Gestion des clients")
    print("   • Visualisation des documents")
    print("   • Recherche avancée")
    print("   • Upload de documents")
    print("   • Synchronisation automatique")
    print("=" * 50)
    
    # Démarrer le gestionnaire de synchronisation
    try:
        sync_manager.start_scheduler()
        print("📅 Gestionnaire de synchronisation démarré")
    except ImportError as e:
        print("⚠️  Module 'schedule' manquant - synchronisation désactivée")
        print("   Installez avec: pip install schedule")
    
    try:
        print("🔌 WebSocket activé pour progression temps réel")
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    finally:
        # Arrêter proprement le gestionnaire
        sync_manager.stop_scheduler()