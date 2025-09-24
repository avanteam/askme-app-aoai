"""
Usage Tracking Service for token counting and usage analytics.

This service manages the storage and retrieval of token usage data in CosmosDB.
It provides comprehensive tracking of LLM usage with detailed breakdown by:
- User and session
- Provider and model
- Token types (text, images, search context)
- Time periods
- Conversation context

Key Features:
- Asynchronous recording of usage data
- Detailed usage analytics and summaries
- Configurable via USAGE_TRACKER_* settings
- Integration with CosmosDB for persistence
- User privacy considerations
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import asdict

from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey, exceptions

from backend.settings import app_settings
from backend.token_counter import TokenCountResult


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
        """Convert the usage record to a dictionary for CosmosDB storage."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'conversation_id': self.conversation_id,
            'message_id': self.message_id,
            'provider': self.provider,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
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


class UsageTrackingService:
    """
    Main service for tracking and managing token usage data.

    This service handles:
    - Recording usage data to CosmosDB
    - Retrieving usage statistics and analytics
    - Managing the usage database container
    - Providing usage summaries and reports
    """

    def __init__(self, cosmos_client=None):
        """Initialize the usage tracking service."""
        self.logger = logging.getLogger("UsageTrackingService")
        self.cosmos_client = cosmos_client

        # Load configuration
        if hasattr(app_settings, 'usage_tracker'):
            self.settings = app_settings.usage_tracker
            self.enabled = self.settings.enabled
            self.container_name = self.settings.cosmos_container_name
            self.store_detailed_metrics = self.settings.store_detailed_metrics
        else:
            # Fallback configuration
            self.enabled = False
            self.container_name = "token_usage"
            self.store_detailed_metrics = True
            self.logger.warning("Usage tracker settings not found, using defaults")

        # CosmosDB connection details - use same as chat history
        if hasattr(app_settings, 'chat_history') and app_settings.chat_history:
            self.database_name = app_settings.chat_history.database
        else:
            self.database_name = None
            self.enabled = False
            self.logger.warning("CosmosDB not configured, usage tracking disabled")

        self.container = None
        self.initialized = False

        self.logger.info(f"UsageTrackingService initialized - enabled: {self.enabled}, container: {self.container_name}")

    async def init_container(self):
        """Initialize the CosmosDB container for usage tracking."""
        if not self.enabled or not self.cosmos_client or not self.database_name:
            self.logger.warning("Usage tracking not enabled or CosmosDB not available")
            return

        if self.initialized:
            return

        try:
            # Get database
            database = self.cosmos_client.get_database_client(self.database_name)

            # Create container if it doesn't exist
            try:
                self.container = database.get_container_client(self.container_name)
                # Test if container exists
                await self.container.read()
                self.logger.info(f"Connected to existing usage tracking container: {self.container_name}")
            except exceptions.CosmosResourceNotFoundError:
                # Create the container (without throughput for serverless accounts)
                self.container = await database.create_container(
                    id=self.container_name,
                    partition_key=PartitionKey(path="/user_id")
                    # Note: No offer_throughput for serverless accounts
                )
                self.logger.info(f"Created new usage tracking container: {self.container_name}")

                # Verify the container was created successfully by doing a test read
                try:
                    await self.container.read()
                    self.logger.info(f"Container {self.container_name} creation verified successfully")
                except Exception as verify_error:
                    self.logger.error(f"Failed to verify container creation: {verify_error}")
                    self.enabled = False
                    return

            self.initialized = True

        except Exception as e:
            self.logger.error(f"Failed to initialize usage tracking container: {e}")
            self.enabled = False

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

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier
            message_id: Message identifier
            provider: LLM provider name
            input_tokens: Input token breakdown
            output_tokens: Output token count
            metadata: Additional metadata

        Returns:
            True if recorded successfully, False otherwise
        """
        self.logger.info(f"[USAGE_SERVICE] record_usage called: user={user_id[:8] if user_id else 'None'}, provider={provider}, total_tokens={input_tokens.get('total', 0) + output_tokens}")

        if not self.enabled:
            self.logger.warning("[USAGE_SERVICE] Usage tracking is DISABLED")
            return False

        try:
            # Ensure container is initialized
            await self.init_container()

            if not self.container:
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

            # Store in CosmosDB
            await self.container.create_item(body=usage_record.to_dict())

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

        Args:
            user_id: User identifier
            start_date: Start date filter
            end_date: End date filter
            provider: Provider filter

        Returns:
            List of usage records
        """
        if not self.enabled or not self.container:
            await self.init_container()
            if not self.container:
                return []

        try:
            # Build query
            query = "SELECT * FROM c WHERE c.user_id = @user_id"
            parameters = [{"name": "@user_id", "value": user_id}]

            if start_date:
                query += " AND c.timestamp >= @start_date"
                parameters.append({"name": "@start_date", "value": start_date.isoformat()})

            if end_date:
                query += " AND c.timestamp <= @end_date"
                parameters.append({"name": "@end_date", "value": end_date.isoformat()})

            if provider:
                query += " AND c.provider = @provider"
                parameters.append({"name": "@provider", "value": provider})

            query += " ORDER BY c.timestamp DESC"

            # Execute query
            items = []
            async for item in self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id
            ):
                items.append(item)

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

        Args:
            user_id: User identifier
            days: Number of days to include in summary

        Returns:
            Usage summary dictionary
        """
        if not self.enabled:
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

        Args:
            conversation_id: Conversation identifier

        Returns:
            Conversation usage summary
        """
        if not self.enabled or not self.container:
            await self.init_container()
            if not self.container:
                return {}

        try:
            # Query for conversation
            query = "SELECT * FROM c WHERE c.conversation_id = @conversation_id ORDER BY c.timestamp ASC"
            parameters = [{"name": "@conversation_id", "value": conversation_id}]

            items = []
            async for item in self.container.query_items(
                query=query,
                parameters=parameters
            ):
                items.append(item)

            if not items:
                return {"conversation_id": conversation_id, "total_tokens": 0}

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

        Args:
            days: Number of days to include

        Returns:
            System usage statistics
        """
        if not self.enabled or not self.container:
            await self.init_container()
            if not self.container:
                return {}

        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get all records in period
            query = "SELECT * FROM c WHERE c.timestamp >= @start_date AND c.timestamp <= @end_date"
            parameters = [
                {"name": "@start_date", "value": start_date.isoformat()},
                {"name": "@end_date", "value": end_date.isoformat()}
            ]

            items = []
            async for item in self.container.query_items(query=query, parameters=parameters):
                items.append(item)

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


# Global instance - will be initialized by app.py with proper CosmosDB client
usage_tracking_service: Optional[UsageTrackingService] = None


def get_usage_service() -> Optional[UsageTrackingService]:
    """Get the global usage tracking service instance."""
    return usage_tracking_service


def init_usage_service(cosmos_client=None) -> UsageTrackingService:
    """Initialize the global usage tracking service."""
    global usage_tracking_service
    usage_tracking_service = UsageTrackingService(cosmos_client)
    return usage_tracking_service