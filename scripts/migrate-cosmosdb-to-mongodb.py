#!/usr/bin/env python3
"""
Script de migration CosmosDB vers MongoDB pour AskMe
Migre toutes les conversations et messages d'un client depuis CosmosDB vers MongoDB
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import des clients AskMe
from azure.cosmos.aio import CosmosClient
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReadPreference


class CosmosToMongoMigrator:
    """Migrateur de données CosmosDB vers MongoDB"""

    def __init__(
        self,
        # CosmosDB Source
        cosmos_endpoint: str,
        cosmos_key: str,
        cosmos_database: str,
        cosmos_container: str,
        # MongoDB Target
        mongo_uri: str,
        mongo_database: str,
        # Options
        batch_size: int = 100,
        dry_run: bool = False
    ):
        self.cosmos_endpoint = cosmos_endpoint
        self.cosmos_key = cosmos_key
        self.cosmos_database = cosmos_database
        self.cosmos_container = cosmos_container

        self.mongo_uri = mongo_uri
        self.mongo_database = mongo_database

        self.batch_size = batch_size
        self.dry_run = dry_run

        # Clients
        self.cosmos_client = None
        self.mongo_client = None

        # Statistiques
        self.stats = {
            'conversations_found': 0,
            'conversations_migrated': 0,
            'conversations_errors': 0,
            'messages_found': 0,
            'messages_migrated': 0,
            'messages_errors': 0,
            'users_processed': set(),
            'errors': []
        }

    async def initialize(self):
        """Initialiser les clients"""
        print(f"🔌 Initialisation des connexions...")

        # Client CosmosDB
        try:
            self.cosmos_client = CosmosClient(self.cosmos_endpoint, self.cosmos_key)
            self.cosmos_database_client = self.cosmos_client.get_database_client(self.cosmos_database)
            self.cosmos_container_client = self.cosmos_database_client.get_container_client(self.cosmos_container)

            # Test de connexion
            await self.cosmos_database_client.read()
            await self.cosmos_container_client.read()

            print(f"  ✅ CosmosDB connecté: {self.cosmos_endpoint}")

        except Exception as e:
            print(f"  ❌ Échec connexion CosmosDB: {str(e)}")
            raise

        # Client MongoDB
        try:
            self.mongo_client = AsyncIOMotorClient(
                self.mongo_uri,
                readPreference=ReadPreference.PRIMARY  # Force écriture sur Primary
            )

            self.mongo_db = self.mongo_client[self.mongo_database]
            self.conversations_collection = self.mongo_db.conversations
            self.messages_collection = self.mongo_db.messages

            # Test de connexion
            await self.mongo_client.admin.command('ismaster')

            print(f"  ✅ MongoDB connecté: {self.mongo_database}")

        except Exception as e:
            print(f"  ❌ Échec connexion MongoDB: {str(e)}")
            raise

    async def get_cosmos_conversations(self) -> List[Dict[str, Any]]:
        """Récupérer toutes les conversations depuis CosmosDB"""
        print("📋 Récupération des conversations depuis CosmosDB...")

        query = "SELECT * FROM c WHERE c.type = 'conversation' ORDER BY c.createdAt"
        conversations = []

        try:
            async for item in self.cosmos_container_client.query_items(
                query=query,
                enable_cross_partition_query=True
            ):
                conversations.append(item)
                self.stats['users_processed'].add(item.get('userId', 'unknown'))

            self.stats['conversations_found'] = len(conversations)
            print(f"  📊 {len(conversations)} conversations trouvées")
            print(f"  👥 {len(self.stats['users_processed'])} utilisateurs uniques")

            return conversations

        except Exception as e:
            error_msg = f"Erreur lors de la récupération des conversations: {str(e)}"
            print(f"  ❌ {error_msg}")
            self.stats['errors'].append(error_msg)
            return []

    async def get_cosmos_messages(self, conversation_id: str = None) -> List[Dict[str, Any]]:
        """Récupérer tous les messages depuis CosmosDB"""
        if conversation_id:
            query = "SELECT * FROM c WHERE c.type = 'message' AND c.conversationId = @conversationId ORDER BY c.createdAt"
            parameters = [{'name': '@conversationId', 'value': conversation_id}]
            print(f"    📨 Récupération messages pour conversation {conversation_id}...")
        else:
            query = "SELECT * FROM c WHERE c.type = 'message' ORDER BY c.createdAt"
            parameters = None
            print("📨 Récupération de tous les messages depuis CosmosDB...")

        messages = []

        try:
            async for item in self.cosmos_container_client.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ):
                messages.append(item)

            if not conversation_id:
                self.stats['messages_found'] = len(messages)
                print(f"  📊 {len(messages)} messages trouvés")

            return messages

        except Exception as e:
            error_msg = f"Erreur lors de la récupération des messages: {str(e)}"
            print(f"    ❌ {error_msg}")
            self.stats['errors'].append(error_msg)
            return []

    def transform_cosmos_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Transformer un document CosmosDB pour MongoDB"""
        # Copier le document
        mongo_doc = doc.copy()

        # MongoDB utilise _id au lieu de id
        if 'id' in mongo_doc:
            mongo_doc['_id'] = mongo_doc['id']

        # Ajouter timestamp pour les messages si manquant
        if doc.get('type') == 'message' and 'timestamp' not in mongo_doc:
            if 'createdAt' in mongo_doc:
                try:
                    mongo_doc['timestamp'] = datetime.fromisoformat(mongo_doc['createdAt'].replace('Z', '+00:00'))
                except:
                    mongo_doc['timestamp'] = datetime.utcnow()
            else:
                mongo_doc['timestamp'] = datetime.utcnow()

        # Nettoyer les champs spécifiques à CosmosDB
        cosmos_fields = ['_rid', '_self', '_etag', '_attachments', '_ts']
        for field in cosmos_fields:
            mongo_doc.pop(field, None)

        return mongo_doc

    async def migrate_conversations(self, conversations: List[Dict[str, Any]]) -> bool:
        """Migrer les conversations vers MongoDB"""
        if not conversations:
            print("⏭️ Aucune conversation à migrer")
            return True

        print(f"🔄 Migration de {len(conversations)} conversations...")

        if self.dry_run:
            print("  🧪 MODE DRY-RUN: Simulation uniquement")
            self.stats['conversations_migrated'] = len(conversations)
            return True

        # Traiter par lots
        for i in range(0, len(conversations), self.batch_size):
            batch = conversations[i:i + self.batch_size]
            print(f"  📦 Lot {i//self.batch_size + 1}: {len(batch)} conversations")

            try:
                # Transformer les documents
                mongo_docs = [self.transform_cosmos_document(conv) for conv in batch]

                # Insérer avec gestion des doublons
                for doc in mongo_docs:
                    try:
                        await self.conversations_collection.replace_one(
                            {'_id': doc['_id']},
                            doc,
                            upsert=True
                        )
                        self.stats['conversations_migrated'] += 1

                    except Exception as e:
                        error_msg = f"Erreur conversation {doc.get('_id', 'unknown')}: {str(e)}"
                        print(f"    ⚠️ {error_msg}")
                        self.stats['conversations_errors'] += 1
                        self.stats['errors'].append(error_msg)

                print(f"    ✅ Lot traité")

            except Exception as e:
                error_msg = f"Erreur traitement lot conversations: {str(e)}"
                print(f"    ❌ {error_msg}")
                self.stats['errors'].append(error_msg)
                return False

        print(f"  ✅ {self.stats['conversations_migrated']} conversations migrées")
        return True

    async def migrate_messages(self, messages: List[Dict[str, Any]]) -> bool:
        """Migrer les messages vers MongoDB"""
        if not messages:
            print("⏭️ Aucun message à migrer")
            return True

        print(f"🔄 Migration de {len(messages)} messages...")

        if self.dry_run:
            print("  🧪 MODE DRY-RUN: Simulation uniquement")
            self.stats['messages_migrated'] = len(messages)
            return True

        # Traiter par lots
        for i in range(0, len(messages), self.batch_size):
            batch = messages[i:i + self.batch_size]
            print(f"  📦 Lot {i//self.batch_size + 1}: {len(batch)} messages")

            try:
                # Transformer les documents
                mongo_docs = [self.transform_cosmos_document(msg) for msg in batch]

                # Insérer avec gestion des doublons
                for doc in mongo_docs:
                    try:
                        await self.messages_collection.replace_one(
                            {'_id': doc['_id']},
                            doc,
                            upsert=True
                        )
                        self.stats['messages_migrated'] += 1

                    except Exception as e:
                        error_msg = f"Erreur message {doc.get('_id', 'unknown')}: {str(e)}"
                        print(f"    ⚠️ {error_msg}")
                        self.stats['messages_errors'] += 1
                        self.stats['errors'].append(error_msg)

                print(f"    ✅ Lot traité")

            except Exception as e:
                error_msg = f"Erreur traitement lot messages: {str(e)}"
                print(f"    ❌ {error_msg}")
                self.stats['errors'].append(error_msg)
                return False

        print(f"  ✅ {self.stats['messages_migrated']} messages migrés")
        return True

    async def verify_migration(self) -> bool:
        """Vérifier l'intégrité de la migration"""
        if self.dry_run:
            print("⏭️ Vérification ignorée en mode dry-run")
            return True

        print("🔍 Vérification de l'intégrité...")

        try:
            # Compter les documents dans MongoDB
            mongo_conversations = await self.conversations_collection.count_documents({})
            mongo_messages = await self.messages_collection.count_documents({})

            print(f"  📊 MongoDB: {mongo_conversations} conversations, {mongo_messages} messages")
            print(f"  📊 Migré: {self.stats['conversations_migrated']} conversations, {self.stats['messages_migrated']} messages")

            # Vérification basique
            conv_ok = mongo_conversations >= self.stats['conversations_migrated']
            msg_ok = mongo_messages >= self.stats['messages_migrated']

            if conv_ok and msg_ok:
                print("  ✅ Vérification réussie")
                return True
            else:
                print("  ❌ Problème détecté lors de la vérification")
                return False

        except Exception as e:
            print(f"  ❌ Erreur lors de la vérification: {str(e)}")
            return False

    async def create_mongodb_indexes(self):
        """Créer les index MongoDB pour les performances"""
        if self.dry_run:
            print("⏭️ Création d'index ignorée en mode dry-run")
            return

        print("📊 Création des index MongoDB...")

        try:
            # Index sur conversations
            await self.conversations_collection.create_index([("userId", 1), ("type", 1)])
            await self.conversations_collection.create_index([("userId", 1), ("updatedAt", -1)])

            # Index sur messages
            await self.messages_collection.create_index([("userId", 1), ("conversationId", 1), ("type", 1)])
            await self.messages_collection.create_index([("conversationId", 1), ("timestamp", 1)])
            await self.messages_collection.create_index([("userId", 1), ("type", 1)])

            print("  ✅ Index créés")

        except Exception as e:
            print(f"  ⚠️ Erreur création index: {str(e)}")

    def print_summary(self):
        """Afficher le résumé de la migration"""
        print()
        print("📊 RÉSUMÉ DE LA MIGRATION")
        print("=" * 40)
        print(f"Mode: {'DRY-RUN (simulation)' if self.dry_run else 'PRODUCTION'}")
        print()
        print(f"👥 Utilisateurs traités: {len(self.stats['users_processed'])}")
        print()
        print("Conversations:")
        print(f"  📋 Trouvées: {self.stats['conversations_found']}")
        print(f"  ✅ Migrées: {self.stats['conversations_migrated']}")
        print(f"  ❌ Erreurs: {self.stats['conversations_errors']}")
        print()
        print("Messages:")
        print(f"  📨 Trouvés: {self.stats['messages_found']}")
        print(f"  ✅ Migrés: {self.stats['messages_migrated']}")
        print(f"  ❌ Erreurs: {self.stats['messages_errors']}")
        print()

        total_errors = len(self.stats['errors'])
        if total_errors > 0:
            print(f"⚠️ {total_errors} erreurs total:")
            for i, error in enumerate(self.stats['errors'][:10], 1):  # Afficher max 10 erreurs
                print(f"  {i}. {error}")
            if total_errors > 10:
                print(f"  ... et {total_errors - 10} autres erreurs")
        else:
            print("🎉 Aucune erreur détectée !")

    async def run_migration(self) -> bool:
        """Exécuter la migration complète"""
        print("🚀 MIGRATION COSMOSDB → MONGODB")
        print("=" * 50)
        print(f"Source: {self.cosmos_endpoint} ({self.cosmos_database}.{self.cosmos_container})")
        print(f"Target: {self.mongo_database}")
        print(f"Mode: {'DRY-RUN' if self.dry_run else 'PRODUCTION'}")
        print()

        try:
            # 1. Initialiser les connexions
            await self.initialize()

            # 2. Récupérer les données CosmosDB
            conversations = await self.get_cosmos_conversations()
            messages = await self.get_cosmos_messages()

            if not conversations and not messages:
                print("⚠️ Aucune donnée trouvée dans CosmosDB")
                return True

            # 3. Créer les index MongoDB
            await self.create_mongodb_indexes()

            # 4. Migrer les conversations
            conv_success = await self.migrate_conversations(conversations)

            # 5. Migrer les messages
            msg_success = await self.migrate_messages(messages)

            # 6. Vérifier l'intégrité
            verify_success = await self.verify_migration()

            # 7. Résumé
            self.print_summary()

            success = conv_success and msg_success and verify_success

            if success:
                print()
                if self.dry_run:
                    print("🎯 SIMULATION RÉUSSIE - Prêt pour la migration réelle")
                else:
                    print("🎉 MIGRATION TERMINÉE AVEC SUCCÈS !")
            else:
                print()
                print("❌ MIGRATION ÉCHOUÉE - Voir les erreurs ci-dessus")

            return success

        except Exception as e:
            print(f"💥 ERREUR CRITIQUE: {str(e)}")
            return False

        finally:
            # Fermer les connexions
            if self.cosmos_client:
                await self.cosmos_client.close()
            if self.mongo_client:
                self.mongo_client.close()

    def save_report(self, report_file: str):
        """Sauvegarder un rapport de migration"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'source': {
                'cosmos_endpoint': self.cosmos_endpoint,
                'cosmos_database': self.cosmos_database,
                'cosmos_container': self.cosmos_container
            },
            'target': {
                'mongo_database': self.mongo_database
            },
            'options': {
                'batch_size': self.batch_size,
                'dry_run': self.dry_run
            },
            'statistics': {
                'conversations_found': self.stats['conversations_found'],
                'conversations_migrated': self.stats['conversations_migrated'],
                'conversations_errors': self.stats['conversations_errors'],
                'messages_found': self.stats['messages_found'],
                'messages_migrated': self.stats['messages_migrated'],
                'messages_errors': self.stats['messages_errors'],
                'users_processed': list(self.stats['users_processed']),
                'total_errors': len(self.stats['errors'])
            },
            'errors': self.stats['errors']
        }

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📄 Rapport sauvegardé: {report_file}")


async def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Migration CosmosDB vers MongoDB pour AskMe")

    # Source CosmosDB
    parser.add_argument("--cosmos-endpoint", required=True, help="Endpoint CosmosDB (ex: https://account.documents.azure.com:443/)")
    parser.add_argument("--cosmos-key", required=True, help="Clé d'accès CosmosDB")
    parser.add_argument("--cosmos-database", required=True, help="Nom de la database CosmosDB")
    parser.add_argument("--cosmos-container", default="conversations", help="Nom du container CosmosDB")

    # Target MongoDB
    parser.add_argument("--mongo-uri", required=True, help="URI de connexion MongoDB")
    parser.add_argument("--mongo-database", required=True, help="Nom de la database MongoDB")

    # Options
    parser.add_argument("--batch-size", type=int, default=100, help="Taille des lots de migration")
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation (pas d'écriture)")
    parser.add_argument("--report", help="Fichier de rapport JSON")

    args = parser.parse_args()

    # Créer le migrateur
    migrator = CosmosToMongoMigrator(
        cosmos_endpoint=args.cosmos_endpoint,
        cosmos_key=args.cosmos_key,
        cosmos_database=args.cosmos_database,
        cosmos_container=args.cosmos_container,
        mongo_uri=args.mongo_uri,
        mongo_database=args.mongo_database,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    # Exécuter la migration
    success = await migrator.run_migration()

    # Sauvegarder le rapport si demandé
    if args.report:
        migrator.save_report(args.report)

    # Code de sortie
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())