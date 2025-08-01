#!/usr/bin/env python3
"""
Service de génération d'embeddings pour la recherche hybride
Supporte OpenAI et Azure OpenAI
"""

import os
import openai
import requests
import json
from typing import List, Dict, Optional
from pathlib import Path

# Charger les variables d'environnement depuis .env.local si disponible
def load_env_file():
    """Charger les variables depuis .env.local puis .env"""
    env_files = ['.env.local', '.env']
    
    for env_file in env_files:
        if Path(env_file).exists():
            print(f"📝 Chargement des variables depuis {env_file}")
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Ne pas écraser si déjà défini dans l'environnement
                        if key not in os.environ:
                            os.environ[key] = value
            return True
    return False

# Charger au démarrage du module
load_env_file()

class EmbeddingService:
    """Service pour générer des embeddings vectoriels"""
    
    def __init__(self, provider: str = "openai", model: str = "text-embedding-ada-002"):
        """
        Initialiser le service d'embeddings
        
        Args:
            provider: "openai" ou "azure_openai"  
            model: Modèle d'embedding à utiliser
        """
        self.provider = provider
        self.model = model
        self.client = None
        
        # Configuration selon le provider
        if provider == "openai":
            self._setup_openai()
        elif provider == "azure_openai":
            self._setup_azure_openai()
        else:
            raise ValueError(f"Provider non supporté: {provider}")
    
    def _setup_openai(self):
        """Configuration OpenAI Direct"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY non trouvée dans les variables d'environnement")
        
        self.client = openai.OpenAI(api_key=api_key)
        print(f"✅ EmbeddingService configuré pour OpenAI Direct")
    
    def _setup_azure_openai(self):
        """Configuration Azure OpenAI"""
        api_key = os.getenv("AZURE_OPENAI_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        
        if not api_key or not endpoint:
            raise ValueError("AZURE_OPENAI_KEY et AZURE_OPENAI_ENDPOINT requis")
        
        self.client = openai.AzureOpenAI(
            api_key=api_key,
            api_version="2024-02-01",
            azure_endpoint=endpoint
        )
        print(f"✅ EmbeddingService configuré pour Azure OpenAI")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Générer un embedding pour un texte
        
        Args:
            text: Texte à vectoriser
            
        Returns:
            Liste de float représentant le vecteur
        """
        try:
            # Nettoyer le texte
            text = text.strip().replace('\n', ' ')[:8000]  # Limite OpenAI
            
            if not text:
                return [0.0] * 1536  # Vecteur zéro si texte vide
            
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            print(f"❌ Erreur génération embedding: {e}")
            return [0.0] * 1536  # Fallback vers vecteur zéro
    
    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """
        Générer des embeddings par batch pour optimiser les performances
        
        Args:
            texts: Liste de textes à vectoriser
            batch_size: Taille des batches (max 2048 pour OpenAI)
            
        Returns:
            Liste de vecteurs
        """
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            # Nettoyer les textes du batch
            cleaned_batch = []
            for text in batch:
                cleaned = text.strip().replace('\n', ' ')[:8000]
                cleaned_batch.append(cleaned if cleaned else " ")  # Éviter le texte vide
            
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=cleaned_batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
                
                print(f"📊 Batch {i//batch_size + 1}: {len(batch_embeddings)} embeddings générés")
                
            except Exception as e:
                print(f"❌ Erreur batch {i//batch_size + 1}: {e}")
                # Fallback individuel pour ce batch
                for text in batch:
                    embeddings.append(self.generate_embedding(text))
        
        return embeddings
    
    def test_service(self) -> bool:
        """Tester le service d'embeddings"""
        try:
            test_text = "Ceci est un test de génération d'embeddings."
            embedding = self.generate_embedding(test_text)
            
            if len(embedding) == 1536 and any(x != 0 for x in embedding):
                print(f"✅ Test réussi - Embedding généré: {len(embedding)} dimensions")
                return True
            else:
                print(f"❌ Test échoué - Embedding invalide")
                return False
                
        except Exception as e:
            print(f"❌ Test échoué: {e}")
            return False

def create_embedding_service() -> Optional[EmbeddingService]:
    """
    Factory pour créer un service d'embeddings basé sur les variables d'environnement
    """
    
    # Essayer Azure OpenAI en premier
    if os.getenv("AZURE_OPENAI_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
        try:
            service = EmbeddingService("azure_openai")
            if service.test_service():
                return service
        except Exception as e:
            print(f"⚠️ Azure OpenAI non disponible: {e}")
    
    # Fallback vers OpenAI Direct
    if os.getenv("OPENAI_API_KEY"):
        try:
            service = EmbeddingService("openai")
            if service.test_service():
                return service
        except Exception as e:
            print(f"⚠️ OpenAI Direct non disponible: {e}")
    
    print("❌ Aucun service d'embeddings disponible")
    print("💡 Configurez AZURE_OPENAI_KEY+AZURE_OPENAI_ENDPOINT ou OPENAI_API_KEY")
    return None

if __name__ == "__main__":
    print("🧪 Test du service d'embeddings")
    print("=" * 50)
    
    service = create_embedding_service()
    
    if service:
        print("\n🔍 Test avec plusieurs textes:")
        
        test_texts = [
            "Le droit du travail français",
            "Les congés payés en entreprise", 
            "La durée légale du travail"
        ]
        
        embeddings = service.generate_embeddings_batch(test_texts, batch_size=2)
        
        for i, (text, embedding) in enumerate(zip(test_texts, embeddings)):
            print(f"  {i+1}. '{text}' → {len(embedding)} dimensions")
        
        print(f"\n✅ Service d'embeddings opérationnel !")
    else:
        print(f"\n❌ Impossible d'initialiser le service d'embeddings")