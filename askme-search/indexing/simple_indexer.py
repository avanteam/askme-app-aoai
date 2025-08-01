#!/usr/bin/env python3
"""
Indexeur simple avec support optionnel des droits d'accès
Les droits sont ajoutés seulement si fournis, sinon le document reste sans restriction
"""

import json
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import requests
import io

# Imports optionnels pour le traitement de documents
try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    import openpyxl
    HAS_EXCEL = True
except ImportError:
    HAS_EXCEL = False

try:
    from pptx import Presentation
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False


class DocumentProcessor:
    """Processeur pour extraire le texte de différents formats"""
    
    def extract_text(self, file_path: Path) -> str:
        """Extraire le texte selon le type de fichier"""
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == '.txt':
                return self._extract_text_file(file_path)
            elif suffix == '.pdf':
                return self._extract_pdf(file_path)
            elif suffix in ['.docx', '.doc']:
                return self._extract_docx(file_path)
            elif suffix in ['.xlsx', '.xls']:
                return self._extract_excel(file_path)
            elif suffix in ['.pptx', '.ppt']:
                return self._extract_powerpoint(file_path)
            else:
                # Essayer comme fichier texte
                return self._extract_text_file(file_path)
                
        except Exception as e:
            print(f"Erreur extraction {file_path.name}: {e}")
            return ""
    
    def _extract_text_file(self, file_path: Path) -> str:
        """Extraire texte d'un fichier txt"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Essayer avec d'autres encodages
            for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            return ""
    
    def _extract_pdf(self, file_path: Path) -> str:
        """Extraire texte d'un PDF"""
        if not HAS_PDF:
            print(f"⚠️ PyPDF2 non installé, impossible de traiter {file_path.name}")
            return ""
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception:
            return ""
    
    def _extract_docx(self, file_path: Path) -> str:
        """Extraire texte d'un document Word"""
        if not HAS_DOCX:
            print(f"⚠️ python-docx non installé, impossible de traiter {file_path.name}")
            return ""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception:
            return ""
    
    def _extract_excel(self, file_path: Path) -> str:
        """Extraire texte d'un fichier Excel"""
        if not HAS_EXCEL:
            print(f"⚠️ openpyxl non installé, impossible de traiter {file_path.name}")
            return ""
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            text = ""
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                text += f"Feuille: {sheet_name}\n"
                
                for row in sheet.iter_rows(values_only=True):
                    row_text = [str(cell) if cell is not None else "" for cell in row]
                    text += " ".join(row_text) + "\n"
                
                text += "\n"
            
            return text
        except Exception:
            return ""
    
    def _extract_powerpoint(self, file_path: Path) -> str:
        """Extraire texte d'une présentation PowerPoint"""
        if not HAS_PPTX:
            print(f"⚠️ python-pptx non installé, impossible de traiter {file_path.name}")
            return ""
        try:
            prs = Presentation(file_path)
            text = ""
            
            for i, slide in enumerate(prs.slides, 1):
                text += f"Diapositive {i}:\n"
                
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
                
                text += "\n"
            
            return text
        except Exception:
            return ""


class TextSplitter:
    """Diviseur de texte en chunks"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_text(self, text: str) -> List[str]:
        """Diviser le texte en chunks avec chevauchement"""
        if not text or len(text.strip()) < 10:
            return []
        
        # Nettoyer le texte
        text = self._clean_text(text)
        
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Fin du chunk
            end = start + self.chunk_size
            
            if end >= len(text):
                # Dernier chunk
                chunks.append(text[start:].strip())
                break
            
            # Essayer de couper à un point d'arrêt naturel
            chunk_text = text[start:end]
            
            # Chercher le dernier point, retour à la ligne ou espace
            for delimiter in ['.\n', '. ', '\n\n', '\n', ' ']:
                last_delimiter = chunk_text.rfind(delimiter)
                if last_delimiter > len(chunk_text) * 0.7:  # Au moins 70% du chunk
                    end = start + last_delimiter + len(delimiter)
                    break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Prochain chunk avec chevauchement
            start = end - self.chunk_overlap
        
        return [chunk for chunk in chunks if len(chunk.strip()) > 10]
    
    def _clean_text(self, text: str) -> str:
        """Nettoyer le texte"""
        # Supprimer les espaces multiples
        text = ' '.join(text.split())
        
        # Supprimer les lignes vides multiples
        text = '\n'.join(line for line in text.split('\n') if line.strip())
        
        return text.strip()


class SimpleIndexer:
    """Indexeur simple avec droits optionnels"""
    
    def __init__(self, opensearch_url: str = "http://localhost:9200", 
                 index_name: str = "askme-documents"):
        self.opensearch_url = opensearch_url
        self.index_name = index_name
        self.processor = DocumentProcessor()
        self.splitter = TextSplitter()
    
    def index_document(self, file_path: Path, access_rights: List[str] = None) -> bool:
        """
        Indexer un document avec droits d'accès optionnels
        
        Args:
            file_path: Chemin du fichier
            access_rights: Liste optionnelle des droits (ex: ["finance", "user:john.doe"])
        """
        try:
            print(f"📄 Indexation: {file_path.name}")
            
            # Extraire le contenu
            content = self.processor.extract_text(file_path)
            if not content or len(content.strip()) < 10:
                print(f"⚠️ Contenu vide ou trop court: {file_path.name}")
                return False
            
            # Découper en chunks
            chunks = self.splitter.split_text(content)
            if not chunks:
                print(f"⚠️ Aucun chunk généré: {file_path.name}")
                return False
            
            # Indexer chaque chunk
            indexed_chunks = 0
            for i, chunk in enumerate(chunks):
                doc = {
                    "title": file_path.name,
                    "content": chunk,
                    "filepath": str(file_path),
                    "chunk_id": i,
                    "chunk_size": len(chunk),
                    "file_type": file_path.suffix.lower(),
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                # Ajouter les droits seulement s'ils sont fournis
                if access_rights:
                    doc["accessRights"] = access_rights
                    print(f"🔐 Droits: {access_rights}")
                else:
                    print("🌐 Pas de restriction d'accès")
                
                # Indexer dans OpenSearch
                doc_id = f"{file_path.name}_chunk_{i}"
                response = requests.post(
                    f"{self.opensearch_url}/{self.index_name}/_doc/{doc_id}",
                    headers={"Content-Type": "application/json"},
                    json=doc
                )
                
                if response.status_code in [200, 201]:
                    indexed_chunks += 1
                else:
                    print(f"❌ Erreur indexation chunk {i}: {response.status_code}")
            
            print(f"✅ {file_path.name}: {indexed_chunks}/{len(chunks)} chunks indexés")
            return indexed_chunks > 0
            
        except Exception as e:
            print(f"❌ Erreur indexation {file_path.name}: {e}")
            return False
    
    def search(self, query: str, user_rights: List[str] = None, size: int = 10, search_mode: str = "hybrid") -> Dict:
        """
        Recherche avec différents modes disponibles
        
        Args:
            query: Terme de recherche
            user_rights: Droits de l'utilisateur (optionnel)
            size: Nombre de résultats
            search_mode: Mode de recherche ("text", "vector", "hybrid")
                - "text": Recherche textuelle uniquement
                - "vector": Recherche vectorielle uniquement (KNN)
                - "hybrid": Recherche hybride avec fallback automatique
        """
        # Construire la requête selon le mode demandé
        if search_mode == "text":
            search_body = self._build_text_search_query(query, size)
            print(f"🔤 Mode textuel pour: {query}")
        elif search_mode == "vector":
            search_body = self._build_vector_search_query(query, size)
            print(f"🧠 Mode vectoriel pour: {query}")
        elif search_mode == "hybrid":
            search_body = self._build_hybrid_search_query(query, size)
            print(f"🔀 Mode hybride pour: {query}")
        else:
            print(f"⚠️ Mode '{search_mode}' inconnu, fallback vers textuel")
            search_body = self._build_text_search_query(query, size)
            search_mode = "text"
        
        # Ajouter le filtrage par droits SI l'utilisateur a des droits spécifiés
        if user_rights:
            search_body["query"] = {
                "bool": {
                    "must": search_body["query"],
                    "should": [
                        # Documents sans restriction d'accès
                        {"bool": {"must_not": {"exists": {"field": "accessRights"}}}},
                        # OU documents avec droits correspondants
                        {"terms": {"accessRights": user_rights}}
                    ],
                    "minimum_should_match": 1
                }
            }
        
        try:
            response = requests.post(
                f"{self.opensearch_url}/{self.index_name}/_search",
                headers={"Content-Type": "application/json"},
                json=search_body
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Gérer le fallback selon le mode
                if search_mode == "hybrid" and "knn" in str(search_body.get("query", {})):
                    hits = result.get('hits', {}).get('hits', [])
                    total = result.get('hits', {}).get('total', {})
                    total_value = total.get('value', total) if isinstance(total, dict) else total
                    
                    if total_value == 0:
                        print(f"⚠️ Recherche vectorielle retourne 0 résultats")
                        print(f"🔄 Fallback automatique vers recherche textuelle pour: {query}")
                        try:
                            text_search_body = self._build_text_search_query(query, size)
                            
                            # Réappliquer le filtrage par droits si nécessaire
                            if user_rights:
                                text_search_body["query"] = {
                                    "bool": {
                                        "must": text_search_body["query"],
                                        "should": [
                                            {"bool": {"must_not": {"exists": {"field": "accessRights"}}}},
                                            {"terms": {"accessRights": user_rights}}
                                        ],
                                        "minimum_should_match": 1
                                    }
                                }
                            
                            fallback_response = requests.post(
                                f"{self.opensearch_url}/{self.index_name}/_search",
                                headers={"Content-Type": "application/json"},
                                json=text_search_body
                            )
                            
                            if fallback_response.status_code == 200:
                                fallback_result = fallback_response.json()
                                fallback_hits = fallback_result.get('hits', {}).get('hits', [])
                                fallback_total = fallback_result.get('hits', {}).get('total', {})
                                fallback_total_value = fallback_total.get('value', fallback_total) if isinstance(fallback_total, dict) else fallback_total
                                
                                if fallback_total_value > 0:
                                    print(f"✅ Fallback textuel réussi: {fallback_total_value} résultats")
                                    return fallback_result
                                else:
                                    print(f"⚠️ Fallback textuel aussi 0 résultat")
                            
                        except Exception as fallback_error:
                            print(f"❌ Erreur fallback: {fallback_error}")
                
                return result
            else:
                print(f"❌ Erreur recherche: {response.status_code}")
                
                # Si c'était une recherche hybride qui a échoué, essayer fallback textuel
                if search_mode == "hybrid" and "knn" in str(search_body.get("query", {})):
                    print(f"🔄 Fallback vers recherche textuelle après erreur pour: {query}")
                    try:
                        text_search_body = self._build_text_search_query(query, size)
                        
                        # Réappliquer le filtrage par droits si nécessaire
                        if user_rights:
                            text_search_body["query"] = {
                                "bool": {
                                    "must": text_search_body["query"],
                                    "should": [
                                        {"bool": {"must_not": {"exists": {"field": "accessRights"}}}},
                                        {"terms": {"accessRights": user_rights}}
                                    ],
                                    "minimum_should_match": 1
                                }
                            }
                        
                        fallback_response = requests.post(
                            f"{self.opensearch_url}/{self.index_name}/_search",
                            headers={"Content-Type": "application/json"},
                            json=text_search_body
                        )
                        
                        if fallback_response.status_code == 200:
                            print(f"✅ Fallback textuel réussi")
                            return fallback_response.json()
                        
                    except Exception as fallback_error:
                        print(f"❌ Erreur fallback: {fallback_error}")
                
                return {}
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return {}
    
    def _build_text_search_query(self, query: str, size: int) -> Dict:
        """Construire une requête de recherche textuelle classique"""
        return {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^2", "chunk^1.5", "titreDocument^2"],
                    "type": "best_fields"
                }
            },
            "size": size,
            "_source": ["title", "chunk", "titreDocument", "parent_id", "chunk_id", "securityRights", "fieldMetadata", "metadata_storage_name"],
            "highlight": {
                "fields": {
                    "chunk": {
                        "fragment_size": 300,
                        "number_of_fragments": 2
                    }
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            }
        }
    
    def _build_vector_search_query(self, query: str, size: int) -> Dict:
        """Construire une requête de recherche vectorielle pure (KNN uniquement)"""
        
        # Essayer de générer l'embedding de la requête
        try:
            import sys
            import os
            from pathlib import Path
            
            # Ajouter le chemin vers le module app
            app_path = Path(__file__).parent.parent / 'app'
            if str(app_path) not in sys.path:
                sys.path.insert(0, str(app_path))
                
            from embedding_service import create_embedding_service
            embedding_service = create_embedding_service()
            
            if embedding_service:
                query_vector = embedding_service.generate_embedding(query)
                
                # Requête vectorielle KNN pure
                knn_query = {
                    "size": size,
                    "query": {
                        "knn": {
                            "chunk_vector": {
                                "vector": query_vector,
                                "k": size
                            }
                        }
                    },
                    "_source": ["title", "chunk", "titreDocument", "parent_id", "chunk_id", "securityRights", "fieldMetadata", "metadata_storage_name"]
                }
                
                return knn_query
            
        except Exception as e:
            print(f"⚠️ Recherche vectorielle indisponible: {e}")
        
        # Si pas d'embedding disponible, retourner requête vide (pas de fallback pour mode vector pur)
        print(f"❌ Mode vectoriel impossible, service d'embeddings indisponible")
        return {
            "query": {"match_none": {}},
            "size": 0
        }
    
    def _build_hybrid_search_query(self, query: str, size: int) -> Dict:
        """Construire une requête de recherche hybride (vectorielle + textuelle)"""
        
        # Essayer de générer l'embedding de la requête
        try:
            import sys
            import os
            from pathlib import Path
            
            # Ajouter le chemin vers le module app
            app_path = Path(__file__).parent.parent / 'app'
            if str(app_path) not in sys.path:
                sys.path.insert(0, str(app_path))
                
            from embedding_service import create_embedding_service
            embedding_service = create_embedding_service()
            
            if embedding_service:
                query_vector = embedding_service.generate_embedding(query)
                
                # Recherche hybride: d'abord vectorielle, puis textuelle
                # Faire 2 requêtes séparées et combiner les résultats
                
                # 1. Requête vectorielle KNN (syntaxe pour OpenSearch avec plugin k-NN)
                knn_query = {
                    "size": size,
                    "query": {
                        "knn": {
                            "chunk_vector": {
                                "vector": query_vector,
                                "k": size
                            }
                        }
                    },
                    "_source": ["title", "chunk", "titreDocument", "parent_id", "chunk_id", "securityRights", "fieldMetadata", "metadata_storage_name"]
                }
                
                # Pour l'instant, utilisons d'abord la recherche KNN pure
                return knn_query
            
        except Exception as e:
            print(f"⚠️ Recherche hybride indisponible: {e}")
        
        # Fallback vers recherche textuelle
        print(f"🔄 Fallback vers recherche textuelle pour: {query}")
        return self._build_text_search_query(query, size)
    
    def list_indexes(self) -> List[str]:
        """Lister tous les index OpenSearch"""
        try:
            response = requests.get(f"{self.opensearch_url}/_cat/indices?format=json")
            if response.status_code == 200:
                indexes = response.json()
                return [idx['index'] for idx in indexes if not idx['index'].startswith('.')]
            return []
        except Exception as e:
            print(f"❌ Erreur listing indexes: {e}")
            return []
    
    def list_documents(self, size: int = 100) -> Dict:
        """Lister les documents d'un index"""
        try:
            search_body = {
                "query": {"match_all": {}},
                "size": size,
                "_source": ["title", "filepath", "accessRights", "chunk_id", "created_at"]
            }
            
            response = requests.post(
                f"{self.opensearch_url}/{self.index_name}/_search",
                headers={"Content-Type": "application/json"},
                json=search_body
            )
            
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            print(f"❌ Erreur listing documents: {e}")
            return {}
    
    def delete_document_by_filepath(self, filepath: str) -> bool:
        """Supprimer tous les chunks d'un document par son chemin"""
        try:
            # Rechercher tous les chunks de ce fichier
            search_body = {
                "query": {"term": {"filepath": filepath}},
                "size": 1000
            }
            
            response = requests.post(
                f"{self.opensearch_url}/{self.index_name}/_search",
                headers={"Content-Type": "application/json"},
                json=search_body
            )
            
            if response.status_code == 200:
                hits = response.json().get('hits', {}).get('hits', [])
                deleted_count = 0
                
                for hit in hits:
                    doc_id = hit['_id']
                    del_response = requests.delete(
                        f"{self.opensearch_url}/{self.index_name}/_doc/{doc_id}"
                    )
                    if del_response.status_code == 200:
                        deleted_count += 1
                
                print(f"✅ {deleted_count} chunks supprimés pour {filepath}")
                return deleted_count > 0
            return False
        except Exception as e:
            print(f"❌ Erreur suppression: {e}")
            return False
    
    def get_index_stats(self) -> Dict:
        """Obtenir les statistiques d'un index"""
        try:
            response = requests.get(f"{self.opensearch_url}/{self.index_name}/_stats")
            if response.status_code == 200:
                stats = response.json()
                index_stats = stats['indices'][self.index_name]['total']
                return {
                    'documents_count': index_stats['docs']['count'],
                    'size_bytes': index_stats['store']['size_in_bytes'],
                    'size_mb': round(index_stats['store']['size_in_bytes'] / (1024*1024), 2)
                }
            return {}
        except Exception as e:
            print(f"❌ Erreur stats: {e}")
            return {}
    
    def delete_index(self) -> bool:
        """Supprimer complètement un index"""
        try:
            response = requests.delete(f"{self.opensearch_url}/{self.index_name}")
            if response.status_code == 200:
                print(f"✅ Index {self.index_name} supprimé")
                return True
            return False
        except Exception as e:
            print(f"❌ Erreur suppression index: {e}")
            return False
    
    @staticmethod
    def create_client_index(client_id: str, opensearch_url: str = "http://localhost:9200") -> bool:
        """Créer un index dédié pour un client"""
        index_name = f"askme-{client_id}"
        
        print(f"🏢 Création de l'index client: {index_name}")
        
        # Utiliser la fonction existante
        success = create_simple_index(opensearch_url, index_name)
        
        if success:
            print(f"✅ Index client créé: {index_name}")
            print(f"💡 Utilisation: SimpleIndexer(index_name='{index_name}')")
        
        return success
    
    @staticmethod
    def delete_client_index(client_id: str, opensearch_url: str = "http://localhost:9200") -> bool:
        """Supprimer complètement l'index d'un client"""
        index_name = f"askme-{client_id}"
        
        try:
            response = requests.delete(f"{opensearch_url}/{index_name}")
            if response.status_code == 200:
                print(f"✅ Index client supprimé: {index_name}")
                return True
            else:
                print(f"❌ Erreur suppression: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erreur suppression client: {e}")
            return False


def create_simple_index(opensearch_url: str = "http://localhost:9200", 
                       index_name: str = "askme-documents"):
    """Créer un index simple avec mapping pour droits optionnels"""
    
    # Mapping compatible avec le code de synchronisation actuel
    index_mapping = {
        "mappings": {
            "properties": {
                # Champs du mapping original (SimpleIndexer)
                "title": {"type": "text", "analyzer": "standard"},
                "content": {"type": "text", "analyzer": "standard"},
                "filepath": {"type": "keyword"},
                "chunk_size": {"type": "integer"},
                "file_type": {"type": "keyword"},
                "accessRights": {"type": "keyword"},  # ← Optionnel
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                
                # Champs requis par sync_incremental.py
                "chunk_id": {"type": "keyword"},  # STRING, pas integer!
                "parent_id": {"type": "keyword"},
                "chunk": {"type": "text", "analyzer": "standard"},
                "chunk_vector": {
                    "type": "knn_vector",
                    "dimension": 1536,  # Dimension pour OpenAI embeddings text-embedding-ada-002
                    "method": {
                        "name": "hnsw",  
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 24
                        }
                    }
                },
                "metadata_storage_last_modified": {"type": "date"},
                "metadata_storage_name": {"type": "keyword"},
                "metadata_storage_path": {"type": "keyword"},
                "securityRights": {"type": "keyword"},
                "titreDocument": {"type": "text", "analyzer": "standard"},
                "fieldMetadata": {"type": "text", "analyzer": "standard"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 200,
                "knn.space_type": "cosinesimil"
            }
        }
    }
    
    try:
        # Supprimer l'index s'il existe
        requests.delete(f"{opensearch_url}/{index_name}")
        
        # Créer le nouvel index
        response = requests.put(
            f"{opensearch_url}/{index_name}",
            headers={"Content-Type": "application/json"},
            json=index_mapping
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Index {index_name} créé")
            return True
        else:
            print(f"❌ Erreur création index: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Test Indexeur Simple avec Droits Optionnels")
    print("=" * 60)
    
    # Créer l'index
    create_simple_index()
    
    # Initialiser l'indexeur
    indexer = SimpleIndexer()
    
    # Exemples d'indexation
    print("\n📄 Exemples d'indexation:")
    
    # 1. Document sans restriction
    print("\n1. Document public (pas de droits):")
    # indexer.index_document(Path("mes-documents/guide.pdf"))  # Pas de droits
    
    # 2. Document avec droits
    print("\n2. Document avec droits spécifiques:")
    # indexer.index_document(
    #     Path("mes-documents/rapport.pdf"), 
    #     access_rights=["finance", "direction", "user:john.doe"]
    # )
    
    print("\n✅ Système prêt à utiliser !")