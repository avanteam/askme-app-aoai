"""
MongoDB Usage Tracking Service for token counting and usage analytics.

This service manages the storage and retrieval of token usage data in MongoDB.
Inherits from the abstract UsageProvider interface.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReadPreference
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from backend.settings import app_settings
from backend.token_counter import TokenCountResult
from .base import UsageProvider


class UsageRecord:
    """Represents a single usage record for token tracking."""

    def __init__(
        self,
        user_id: str,
        conversation_id: str,
        message_id: str,
        provider: str,
        input_tokens: Dict[str, Any],
        output_tokens: int,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.provider = provider
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = input_tokens.get('total', 0) + output_tokens
        self.timestamp = timestamp or datetime.utcnow()
        self.metadata = metadata or {}

        # Ensure metadata includes configuration used
        if 'settings_snapshot' not in self.metadata:
            self.metadata['settings_snapshot'] = self._get_settings_snapshot()

    def _get_settings_snapshot(self) -> Dict[str, Any]:
        """Capture current usage tracker settings for audit purposes."""
        if hasattr(app_settings, 'usage_tracker'):
            settings = app_settings.usage_tracker
            return {
                'image_tokens_per_byte': settings.image_tokens_per_byte
            }
        return {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert the usage record to a dictionary for MongoDB storage."""
        return {
            '_id': self.id,  # MongoDB utilise _id
            'id': self.id,   # Compatibilité
            'user_id': self.user_id,
            'conversation_id': self.conversation_id,
            'message_id': self.message_id,
            'provider': self.provider,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'timestamp': self.timestamp.isoformat(),  # ISO string pour compatibilité
            'metadata': self.metadata
        }


class UsageAnalytics:
    """Provides analytics and summary calculations for usage data."""

    @staticmethod
    def calculate_daily_summary(records: List[Dict]) -> Dict[str, Any]:
        """Calculate daily usage summary from records."""
        if not records:
            return {}

        total_tokens = sum(record.get('total_tokens', 0) for record in records)
        total_input = sum(record.get('input_tokens', {}).get('total', 0) for record in records)
        total_output = sum(record.get('output_tokens', 0) for record in records)

        # Break down input tokens
        total_text_tokens = sum(record.get('input_tokens', {}).get('text', 0) for record in records)
        total_image_tokens = sum(record.get('input_tokens', {}).get('images', 0) for record in records)
        total_search_tokens = sum(record.get('input_tokens', {}).get('search_context', 0) for record in records)

        # Provider breakdown
        provider_stats = {}
        for record in records:
            provider = record.get('provider', 'unknown')
            if provider not in provider_stats:
                provider_stats[provider] = {
                    'count': 0,
                    'total_tokens': 0,
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            provider_stats[provider]['count'] += 1
            provider_stats[provider]['total_tokens'] += record.get('total_tokens', 0)
            provider_stats[provider]['input_tokens'] += record.get('input_tokens', {}).get('total', 0)
            provider_stats[provider]['output_tokens'] += record.get('output_tokens', 0)

        # Image usage stats
        image_count = 0
        for record in records:
            metadata = record.get('input_tokens', {}).get('metadata', {})
            messages_metadata = metadata.get('messages_metadata', {})
            if isinstance(messages_metadata, dict):
                image_count += messages_metadata.get('image_count', 0)

        return {
            'record_count': len(records),
            'total_tokens': total_tokens,
            'input_tokens': {
                'total': total_input,
                'text': total_text_tokens,
                'images': total_image_tokens,
                'search_context': total_search_tokens
            },
            'output_tokens': total_output,
            'provider_breakdown': provider_stats,
            'image_usage': {
                'total_images': image_count,
                'image_tokens': total_image_tokens
            }
        }


class MongoUsageService(UsageProvider):
    """
    MongoDB implementation of UsageProvider.

    This service handles:
    - Recording usage data to MongoDB
    - Retrieving usage statistics and analytics
    - Managing the usage collection
    - Providing usage summaries and reports
    """

    def __init__(self, connection_string: str, database_name: str):
        """Initialize the MongoDB usage tracking service."""
        self.logger = logging.getLogger("MongoUsageService")
        self.connection_string = connection_string
        self.database_name = database_name

        # Load configuration
        if hasattr(app_settings, 'usage_tracker'):
            self.settings = app_settings.usage_tracker
            self._enabled = self.settings.enabled
            self.container_name = self.settings.cosmos_container_name or "token_usage"
            self.store_detailed_metrics = self.settings.store_detailed_metrics
        else:
            # Fallback configuration
            self._enabled = False
            self.container_name = "token_usage"
            self.store_detailed_metrics = True
            self.logger.warning("Usage tracker settings not found, using defaults")

        # MongoDB client configuration
        self.client = AsyncIOMotorClient(
            connection_string,
            read_preference=ReadPreference.SECONDARY_PREFERRED,
            maxPoolSize=50,
            retryWrites=True,
            serverSelectionTimeoutMS=5000
        )

        self.database = self.client[database_name]
        self.collection = self.database[self.container_name]
        self.initialized = False

        self.logger.info(f"MongoUsageService initialized - enabled: {self._enabled}, collection: {self.container_name}")

    async def init_container(self):
        """Initialize the MongoDB collection for usage tracking."""
        if not self._enabled:
            self.logger.warning("Usage tracking not enabled")
            return

        if self.initialized:
            return

        try:
            # Test de connexion basique
            await self.client.admin.command('ismaster')

            # Test d'écriture/lecture
            test_doc = {'_id': 'health_check_usage', 'timestamp': datetime.utcnow()}
            await self.collection.replace_one(
                {'_id': 'health_check_usage'},
                test_doc,
                upsert=True
            )

            # Nettoyage
            await self.collection.delete_one({'_id': 'health_check_usage'})

            # Créer un index sur user_id pour performance
            await self.collection.create_index("user_id")
            await self.collection.create_index("timestamp")
            await self.collection.create_index("conversation_id")

            self.initialized = True
            self.logger.info(f"MongoDB usage tracking collection '{self.container_name}' initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize usage tracking collection: {e}")
            self._enabled = False

    async def record_usage(
        self,
        user_id: str,
        conversation_id: str,
        message_id: str,
        provider: str,
        input_tokens: Dict[str, Any],
        output_tokens: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record a usage event asynchronously.
        """
        self.logger.info(f"[MONGO_USAGE] record_usage called: user={user_id[:8] if user_id else 'None'}, provider={provider}, total_tokens={input_tokens.get('total', 0) + output_tokens}")

        if not self._enabled:
            self.logger.warning("[MONGO_USAGE] Usage tracking is DISABLED")
            return False

        try:
            # Ensure collection is initialized
            await self.init_container()

            if not self.initialized:
                return False

            # Create usage record
            usage_record = UsageRecord(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                provider=provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                metadata=metadata
            )

            # Store in MongoDB
            await self.collection.insert_one(usage_record.to_dict())

            self.logger.debug(f"Recorded usage: {usage_record.total_tokens} tokens for user {user_id[:8]}...")
            return True

        except Exception as e:
            self.logger.error(f"Failed to record usage: {e}")
            return False

    async def get_user_usage(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get usage records for a specific user.
        """
        if not self._enabled:
            await self.init_container()
            if not self.initialized:
                return []

        try:
            # Build query filter
            query_filter = {"user_id": user_id}

            if start_date:
                if "timestamp" not in query_filter:
                    query_filter["timestamp"] = {}
                query_filter["timestamp"]["$gte"] = start_date.isoformat()

            if end_date:
                if "timestamp" not in query_filter:
                    query_filter["timestamp"] = {}
                query_filter["timestamp"]["$lte"] = end_date.isoformat()

            if provider:
                query_filter["provider"] = provider

            # Execute query with sort
            cursor = self.collection.find(query_filter).sort("timestamp", -1)
            items = await cursor.to_list(length=None)

            # Assurer compatibilité avec l'interface
            for item in items:
                if '_id' in item and 'id' not in item:
                    item['id'] = item['_id']

            return items

        except Exception as e:
            self.logger.error(f"Failed to get user usage: {e}")
            return []

    async def get_usage_summary(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage summary for a user.
        """
        if not self._enabled:
            return {"enabled": False}

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        records = await self.get_user_usage(user_id, start_date, end_date)

        if not records:
            return {
                "period_days": days,
                "record_count": 0,
                "total_tokens": 0,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }

        # Calculate analytics
        summary = UsageAnalytics.calculate_daily_summary(records)
        summary.update({
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "user_id": user_id
        })

        return summary

    async def get_conversation_usage(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get usage summary for a specific conversation.
        """
        if not self._enabled:
            await self.init_container()
            if not self.initialized:
                return {}

        try:
            # Query for conversation
            cursor = self.collection.find({"conversation_id": conversation_id}).sort("timestamp", 1)
            items = await cursor.to_list(length=None)

            if not items:
                return {"conversation_id": conversation_id, "total_tokens": 0}

            # Assurer compatibilité
            for item in items:
                if '_id' in item and 'id' not in item:
                    item['id'] = item['_id']

            # Calculate summary
            summary = UsageAnalytics.calculate_daily_summary(items)
            summary["conversation_id"] = conversation_id
            summary["message_count"] = len(items)

            return summary

        except Exception as e:
            self.logger.error(f"Failed to get conversation usage: {e}")
            return {"error": str(e)}

    async def get_system_usage_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get system-wide usage statistics (admin function).
        """
        if not self._enabled:
            await self.init_container()
            if not self.initialized:
                return {}

        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get all records in period
            query_filter = {
                "timestamp": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }

            cursor = self.collection.find(query_filter)
            items = await cursor.to_list(length=None)

            # Assurer compatibilité
            for item in items:
                if '_id' in item and 'id' not in item:
                    item['id'] = item['_id']

            # Calculate system-wide stats
            summary = UsageAnalytics.calculate_daily_summary(items)

            # Add user count
            unique_users = set(item.get('user_id') for item in items)
            summary['unique_users'] = len(unique_users)
            summary['period_days'] = days
            summary['start_date'] = start_date.isoformat()
            summary['end_date'] = end_date.isoformat()

            return summary

        except Exception as e:
            self.logger.error(f"Failed to get system usage stats: {e}")
            return {"error": str(e)}

    @property
    def enabled(self) -> bool:
        """Indique si le provider d'usage est activé."""
        return self._enabled

    @property
    def provider_name(self) -> str:
        """Retourne le nom du provider."""
        return "MongoDB"

    async def close(self):
        """Ferme les connexions MongoDB."""
        if self.client:
            self.client.close()
            self.logger.info("MongoDB usage client connections closed")