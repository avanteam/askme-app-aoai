import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReadPreference
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError

from backend.utils import process_message_content_for_storage

logger = logging.getLogger(__name__)

class MongoConversationClient:
    """
    Client MongoDB pour gérer les conversations et messages AskMe.
    Compatible avec l'interface CosmosConversationClient.
    Utilise readPreference=secondaryPreferred pour optimiser les performances.
    """

    def __init__(
        self,
        connection_string: str,
        database_name: str,
        enable_message_feedback: bool = False
    ):
        self.connection_string = connection_string
        self.database_name = database_name
        self.enable_message_feedback = enable_message_feedback

        # Configuration client MongoDB avec optimisations
        self.client = AsyncIOMotorClient(
            connection_string,
            read_preference=ReadPreference.SECONDARY_PREFERRED,  # Répartition de charge
            maxPoolSize=50,  # Pool de connexions
            retryWrites=True,  # Retry automatique des écritures
            serverSelectionTimeoutMS=5000  # Timeout connexion
        )

        self.database = self.client[database_name]
        self.conversations_collection = self.database.conversations
        self.messages_collection = self.database.messages

        logger.info(f"MongoDB client initialized for database '{database_name}' with secondary preferred reads")

    async def ensure(self) -> tuple[bool, str]:
        """
        Vérifie la connectivité MongoDB et l'état du replica set
        """
        try:
            # Test de connexion basique
            await self.client.admin.command('ismaster')

            # Vérifier l'existence de la database
            db_list = await self.client.list_database_names()

            # Test d'écriture/lecture
            test_doc = {'_id': 'health_check', 'timestamp': datetime.utcnow()}
            await self.database.health_check.replace_one(
                {'_id': 'health_check'},
                test_doc,
                upsert=True
            )

            # Nettoyage
            await self.database.health_check.delete_one({'_id': 'health_check'})

            logger.info("MongoDB health check successful")
            return True, "MongoDB client initialized successfully"

        except ConnectionFailure as e:
            error_msg = f"MongoDB connection failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except ServerSelectionTimeoutError as e:
            error_msg = f"MongoDB server selection timeout: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"MongoDB health check failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def create_conversation(self, user_id: str, title: str = '') -> Dict[str, Any]:
        """
        Crée une nouvelle conversation
        """
        conversation_id = str(uuid.uuid4())
        current_time = datetime.utcnow()

        conversation = {
            '_id': conversation_id,  # MongoDB utilise _id au lieu de id
            'id': conversation_id,   # Compatibilité avec l'interface existante
            'type': 'conversation',
            'createdAt': current_time,  # datetime object pour MongoDB
            'updatedAt': current_time,  # datetime object pour MongoDB
            'userId': user_id,
            'title': title
        }

        try:
            result = await self.conversations_collection.insert_one(conversation)
            if result.inserted_id:
                # Retourner le document avec l'id pour compatibilité
                conversation['id'] = conversation_id
                logger.info(f"Created conversation {conversation_id} for user {user_id}")
                return conversation
            else:
                logger.error(f"Failed to create conversation for user {user_id}")
                return False
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            return False

    async def upsert_conversation(self, conversation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Met à jour ou insère une conversation
        """
        try:
            conversation_id = conversation.get('id') or conversation.get('_id')
            result = await self.conversations_collection.replace_one(
                {'_id': conversation_id},
                conversation,
                upsert=True
            )
            if result.modified_count > 0 or result.upserted_id:
                logger.info(f"Upserted conversation {conversation_id}")
                return conversation
            else:
                return False
        except Exception as e:
            logger.error(f"Error upserting conversation: {str(e)}")
            return False

    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Supprime une conversation et tous ses messages
        """
        try:
            # Vérifier que la conversation appartient à l'utilisateur
            conversation = await self.conversations_collection.find_one({
                '_id': conversation_id,
                'userId': user_id
            })

            if conversation:
                # Supprimer tous les messages de la conversation
                await self.messages_collection.delete_many({
                    'conversationId': conversation_id,
                    'userId': user_id
                })

                # Supprimer la conversation
                result = await self.conversations_collection.delete_one({
                    '_id': conversation_id,
                    'userId': user_id
                })

                if result.deleted_count > 0:
                    logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
                    return True

            return True  # Retourne True même si la conversation n'existait pas (idempotence)
        except Exception as e:
            logger.error(f"Error deleting conversation: {str(e)}")
            return False

    async def delete_messages(self, conversation_id: str, user_id: str) -> List[Any]:
        """
        Supprime tous les messages d'une conversation
        """
        try:
            result = await self.messages_collection.delete_many({
                'conversationId': conversation_id,
                'userId': user_id
            })
            logger.info(f"Deleted {result.deleted_count} messages from conversation {conversation_id}")
            return [f"Deleted {result.deleted_count} messages"]
        except Exception as e:
            logger.error(f"Error deleting messages: {str(e)}")
            return []

    async def get_conversations(
        self,
        user_id: str,
        limit: Optional[int],
        sort_order: str = 'DESC',
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Récupère les conversations d'un utilisateur
        """
        try:
            query = {'userId': user_id, 'type': 'conversation'}

            # Désactiver le tri MongoDB à cause des types mixtes, utiliser le tri Python
            cursor = self.conversations_collection.find(query)

            if offset > 0:
                cursor = cursor.skip(offset)

            if limit is not None:
                cursor = cursor.limit(limit)

            conversations = await cursor.to_list(length=None)

            # Assurer compatibilité avec l'interface existante
            for conv in conversations:
                if '_id' in conv and 'id' not in conv:
                    conv['id'] = conv['_id']

            # Tri côté Python avec support datetime et string
            def get_sort_key(conv):
                created_at = conv.get('createdAt', '')
                # Convertir datetime en string pour tri uniforme
                if hasattr(created_at, 'isoformat'):
                    return created_at.isoformat()
                return created_at or ''

            if conversations and sort_order.upper() == 'DESC':
                conversations.sort(key=get_sort_key, reverse=True)
            elif conversations and sort_order.upper() == 'ASC':
                conversations.sort(key=get_sort_key)

            logger.info(f"Retrieved {len(conversations)} conversations for user {user_id}")
            return conversations
        except Exception as e:
            logger.error(f"Error getting conversations: {str(e)}")
            return []

    async def get_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une conversation spécifique
        """
        try:
            conversation = await self.conversations_collection.find_one(
                {
                    '_id': conversation_id,
                    'userId': user_id,
                    'type': 'conversation'
                }
            )

            if conversation:
                # Assurer compatibilité
                if '_id' in conversation and 'id' not in conversation:
                    conversation['id'] = conversation['_id']
                logger.info(f"Retrieved conversation {conversation_id} for user {user_id}")
                return conversation
            else:
                logger.info(f"Conversation {conversation_id} not found for user {user_id}")
                return None
        except Exception as e:
            logger.error(f"Error getting conversation: {str(e)}")
            return None

    async def create_message(
        self,
        uuid: str,
        conversation_id: str,
        user_id: str,
        input_message: Dict[str, Any]
    ) -> Any:
        """
        Crée un nouveau message dans une conversation
        """
        try:
            # Traitement du contenu pour le stockage (compression images si nécessaire)
            processed_content = process_message_content_for_storage(input_message['content'])

            current_time = datetime.utcnow()

            message = {
                '_id': uuid,
                'id': uuid,  # Compatibilité
                'type': 'message',
                'userId': user_id,
                'createdAt': current_time,  # datetime object pour MongoDB
                'updatedAt': current_time,  # datetime object pour MongoDB
                'conversationId': conversation_id,
                'role': input_message['role'],
                'content': processed_content,
                'timestamp': current_time  # datetime object pour tri par date
            }

            if self.enable_message_feedback:
                message['feedback'] = ''

            # Insérer le message
            result = await self.messages_collection.insert_one(message)

            if result.inserted_id:
                # Mettre à jour le timestamp de la conversation parent
                await self.conversations_collection.update_one(
                    {'_id': conversation_id, 'userId': user_id},
                    {'$set': {'updatedAt': current_time}}
                )

                logger.info(f"Created message {uuid} in conversation {conversation_id}")
                return message
            else:
                logger.error(f"Failed to create message {uuid}")
                return False
        except Exception as e:
            logger.error(f"Error creating message: {str(e)}")
            return False

    async def update_message_feedback(self, user_id: str, message_id: str, feedback: str) -> Any:
        """
        Met à jour le feedback d'un message
        """
        try:
            result = await self.messages_collection.update_one(
                {'_id': message_id, 'userId': user_id},
                {'$set': {'feedback': feedback, 'updatedAt': datetime.utcnow()}}
            )

            if result.modified_count > 0:
                # Récupérer le message mis à jour
                updated_message = await self.messages_collection.find_one({'_id': message_id})
                if updated_message and '_id' in updated_message:
                    updated_message['id'] = updated_message['_id']
                logger.info(f"Updated feedback for message {message_id}")
                return updated_message
            else:
                logger.warning(f"Message {message_id} not found for user {user_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating message feedback: {str(e)}")
            return False

    async def get_messages(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Récupère tous les messages d'une conversation
        """
        try:
            cursor = self.messages_collection.find(
                {
                    'conversationId': conversation_id,
                    'userId': user_id,
                    'type': 'message'
                }
            ).sort('timestamp', 1)  # Tri chronologique

            messages = await cursor.to_list(length=None)

            # Assurer compatibilité
            for msg in messages:
                if '_id' in msg and 'id' not in msg:
                    msg['id'] = msg['_id']

            logger.info(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
            return messages
        except Exception as e:
            logger.error(f"Error getting messages: {str(e)}")
            return []

    async def close(self):
        """
        Ferme les connexions MongoDB
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB client connections closed")