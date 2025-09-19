"""
Token counting service with advanced image support and configurable parameters.

This module provides comprehensive token counting for LLM requests including:
- Text token counting using tiktoken
- Image token estimation with configurable weights and tiers
- Multimodal content support
- Provider-specific optimizations
- Configurable parameters via USAGE_TRACKER_* environment variables

Key Features:
- Accurate text token counting for different model encodings
- Image token estimation based on size and detail level
- Configurable image weights and size tiers
- Support for base64 and URL-based images
- Memory-efficient caching of encodings
"""

import base64
import logging
import math
import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from dataclasses import dataclass

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logging.warning("tiktoken not available, using approximation for token counting")

from backend.settings import app_settings


@dataclass
class TokenCountResult:
    """Result of token counting with detailed breakdown."""
    text_tokens: int = 0
    image_tokens: int = 0
    search_context_tokens: int = 0
    total_tokens: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        self.total_tokens = self.text_tokens + self.image_tokens + self.search_context_tokens


class TokenCounter:
    """
    Advanced token counter with image support and configurable parameters.

    This class provides accurate token counting for both text and images,
    with support for different model encodings and configurable image weights.
    """

    def __init__(self):
        """Initialize the token counter with configurable settings."""
        self.logger = logging.getLogger("TokenCounter")

        # Cache for tiktoken encodings to avoid repeated initialization
        self._encoding_cache = {}

        # Load settings from USAGE_TRACKER_* environment variables
        if hasattr(app_settings, 'usage_tracker'):
            settings = app_settings.usage_tracker
            self.enabled = settings.enabled
            self.image_base_tokens = settings.image_base_tokens
            self.image_weight_multiplier = settings.image_weight_multiplier

            # Build size tiers from settings
            self.image_size_tiers = [
                {"max_kb": settings.image_size_tier_small_kb, "multiplier": settings.image_size_tier_small_multiplier, "name": "small"},
                {"max_kb": settings.image_size_tier_medium_kb, "multiplier": settings.image_size_tier_medium_multiplier, "name": "medium"},
                {"max_kb": settings.image_size_tier_large_kb, "multiplier": settings.image_size_tier_large_multiplier, "name": "large"},
                {"max_kb": settings.image_size_tier_xlarge_kb, "multiplier": settings.image_size_tier_xlarge_multiplier, "name": "xlarge"},
            ]
        else:
            # Fallback values if settings not available
            self.enabled = True
            self.image_base_tokens = 85
            self.image_weight_multiplier = 1.5
            self.image_size_tiers = [
                {"max_kb": 100, "multiplier": 1.0, "name": "small"},
                {"max_kb": 500, "multiplier": 2.0, "name": "medium"},
                {"max_kb": 2000, "multiplier": 3.0, "name": "large"},
                {"max_kb": 10000, "multiplier": 5.0, "name": "xlarge"},
            ]

        # Image detail level multipliers (following OpenAI's vision pricing)
        self.image_detail_multipliers = {
            'low': 1.0,     # Base tokens only
            'high': 10.0,   # Much higher for detailed analysis
            'auto': 3.0     # Reasonable default
        }

        self.logger.info(f"TokenCounter initialized - enabled: {self.enabled}, image_base_tokens: {self.image_base_tokens}, image_weight: {self.image_weight_multiplier}")

    def get_encoding_for_model(self, model_name: str) -> Optional[object]:
        """
        Get the appropriate tiktoken encoding for a model.

        Args:
            model_name: Name of the model (e.g., 'gpt-4', 'claude-3-opus')

        Returns:
            tiktoken encoding object or None if not available
        """
        if not TIKTOKEN_AVAILABLE:
            return None

        # Cache encodings to avoid repeated initialization
        if model_name in self._encoding_cache:
            return self._encoding_cache[model_name]

        try:
            # Map model names to tiktoken encodings
            if any(x in model_name.lower() for x in ['gpt-4', 'gpt-3.5', 'claude', 'gemini']):
                encoding = tiktoken.get_encoding("cl100k_base")  # Most modern models
            elif 'gpt2' in model_name.lower():
                encoding = tiktoken.get_encoding("gpt2")
            else:
                # Default to cl100k_base for unknown models
                encoding = tiktoken.get_encoding("cl100k_base")

            self._encoding_cache[model_name] = encoding
            return encoding

        except Exception as e:
            self.logger.warning(f"Failed to get encoding for model {model_name}: {e}")
            return None

    def count_text_tokens(self, text: str, model_name: str = "gpt-4") -> int:
        """
        Count tokens in text using the appropriate encoding.

        Args:
            text: Text to count tokens for
            model_name: Model name to determine encoding

        Returns:
            Number of tokens in the text
        """
        if not text or not isinstance(text, str):
            return 0

        encoding = self.get_encoding_for_model(model_name)

        if encoding:
            try:
                return len(encoding.encode(text, allowed_special="all"))
            except Exception as e:
                self.logger.warning(f"Failed to count tokens with tiktoken: {e}")

        # Fallback: rough estimation (4 characters per token)
        return max(1, len(text) // 4)

    def _estimate_image_size_kb(self, image_data: str) -> float:
        """
        Estimate image size in KB from base64 data.

        Args:
            image_data: Base64 encoded image data or URL

        Returns:
            Estimated size in KB
        """
        if not image_data:
            return 0

        if self._is_base64_image(image_data):
            # Extract base64 data after the header
            if ',' in image_data:
                base64_data = image_data.split(',', 1)[1]
            else:
                base64_data = image_data

            # Base64 encoded size is ~1.33x the actual size
            estimated_bytes = (len(base64_data) * 3) / 4
            return estimated_bytes / 1024  # Convert to KB

        # For URLs, we can't determine size, so use a reasonable default
        return 500  # Default to medium size

    def _is_base64_image(self, data: str) -> bool:
        """
        Check if the string is a base64 encoded image.

        Args:
            data: String to check

        Returns:
            True if it's a base64 image
        """
        if not isinstance(data, str):
            return False

        # Check for data URL format
        if data.startswith('data:image/'):
            return True

        # Check for base64 pattern (basic check)
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        if len(data) > 100 and base64_pattern.match(data):
            try:
                base64.b64decode(data[:100])  # Test decode a small part
                return True
            except:
                pass

        return False

    def _get_size_tier(self, size_kb: float) -> Dict[str, Any]:
        """
        Get the appropriate size tier for an image.

        Args:
            size_kb: Image size in KB

        Returns:
            Size tier configuration
        """
        for tier in self.image_size_tiers:
            if size_kb <= tier["max_kb"]:
                return tier

        # If larger than all tiers, use the largest one
        return self.image_size_tiers[-1]

    def count_image_tokens(self, image_data: str, detail_level: str = 'auto') -> Dict[str, Any]:
        """
        Count tokens for an image with configurable parameters.

        Args:
            image_data: Base64 encoded image data or URL
            detail_level: Processing detail level ('low', 'high', 'auto')

        Returns:
            Dictionary with token count and metadata
        """
        if not image_data:
            return {"tokens": 0, "metadata": {}}

        # Estimate image size
        size_kb = self._estimate_image_size_kb(image_data)
        size_tier = self._get_size_tier(size_kb)

        # Calculate base tokens
        base_tokens = self.image_base_tokens

        # Apply detail level multiplier
        detail_multiplier = self.image_detail_multipliers.get(detail_level, 1.0)

        # Apply size tier multiplier
        size_multiplier = size_tier["multiplier"]

        # Calculate final tokens with all multipliers
        tokens = base_tokens * detail_multiplier * size_multiplier * self.image_weight_multiplier

        # Round to nearest integer
        tokens = int(round(tokens))

        metadata = {
            "size_kb": round(size_kb, 2),
            "size_tier": size_tier["name"],
            "detail_level": detail_level,
            "base_tokens": base_tokens,
            "detail_multiplier": detail_multiplier,
            "size_multiplier": size_multiplier,
            "weight_multiplier": self.image_weight_multiplier,
            "is_base64": self._is_base64_image(image_data)
        }

        self.logger.debug(f"Image tokens: {tokens} (size: {size_kb:.1f}KB, tier: {size_tier['name']}, detail: {detail_level})")

        return {"tokens": tokens, "metadata": metadata}

    def count_multimodal_content(self, content: Union[str, List[Dict]], model_name: str = "gpt-4") -> TokenCountResult:
        """
        Count tokens for multimodal content (text + images).

        Args:
            content: Content to analyze (string or list of content parts)
            model_name: Model name for text token counting

        Returns:
            TokenCountResult with detailed breakdown
        """
        if isinstance(content, str):
            # Simple text content
            text_tokens = self.count_text_tokens(content, model_name)
            return TokenCountResult(
                text_tokens=text_tokens,
                metadata={"content_type": "text_only"}
            )

        if not isinstance(content, list):
            return TokenCountResult(metadata={"error": "Invalid content type"})

        text_tokens = 0
        image_tokens = 0
        image_metadata = []

        for part in content:
            if not isinstance(part, dict):
                continue

            content_type = part.get("type", "")

            if content_type == "text":
                text = part.get("text", "")
                text_tokens += self.count_text_tokens(text, model_name)

            elif content_type == "image_url":
                image_url_data = part.get("image_url", {})
                image_data = image_url_data.get("url", "")
                detail = image_url_data.get("detail", "auto")

                image_result = self.count_image_tokens(image_data, detail)
                image_tokens += image_result["tokens"]
                image_metadata.append(image_result["metadata"])

        return TokenCountResult(
            text_tokens=text_tokens,
            image_tokens=image_tokens,
            metadata={
                "content_type": "multimodal",
                "image_count": len(image_metadata),
                "images_metadata": image_metadata
            }
        )

    def count_messages_tokens(self, messages: List[Dict[str, Any]], model_name: str = "gpt-4") -> TokenCountResult:
        """
        Count tokens for a list of messages (chat format).

        Args:
            messages: List of messages in OpenAI chat format
            model_name: Model name for token counting

        Returns:
            TokenCountResult with detailed breakdown
        """
        if not messages:
            return TokenCountResult()

        total_text_tokens = 0
        total_image_tokens = 0
        message_metadata = []

        # Add overhead tokens for message formatting (estimated)
        # OpenAI models have some overhead per message
        message_overhead_tokens = len(messages) * 3  # Rough estimate

        for i, message in enumerate(messages):
            content = message.get("content", "")
            role = message.get("role", "")

            # Count role tokens
            role_tokens = self.count_text_tokens(role, model_name)

            # Count content tokens
            content_result = self.count_multimodal_content(content, model_name)

            total_text_tokens += role_tokens + content_result.text_tokens
            total_image_tokens += content_result.image_tokens

            message_metadata.append({
                "message_index": i,
                "role": role,
                "role_tokens": role_tokens,
                "content_tokens": content_result.text_tokens,
                "image_tokens": content_result.image_tokens,
                "content_metadata": content_result.metadata
            })

        # Add message overhead
        total_text_tokens += message_overhead_tokens

        return TokenCountResult(
            text_tokens=total_text_tokens,
            image_tokens=total_image_tokens,
            metadata={
                "message_count": len(messages),
                "message_overhead_tokens": message_overhead_tokens,
                "messages_metadata": message_metadata
            }
        )

    def analyze_input_tokens(self, messages: List[Dict], search_context: str = "", model_name: str = "gpt-4",
                           azure_role_information: str = "") -> Dict[str, Any]:
        """
        Comprehensive analysis of input tokens for an LLM request.

        Args:
            messages: Chat messages to analyze
            search_context: Additional search context
            model_name: Model name for token counting
            azure_role_information: Azure OpenAI role_information from data_sources (system message)

        Returns:
            Detailed breakdown of input tokens
        """
        if not self.enabled:
            return {"enabled": False}

        # Count message tokens
        messages_result = self.count_messages_tokens(messages, model_name)

        # Count search context tokens
        search_tokens = self.count_text_tokens(search_context, model_name) if search_context else 0

        # Count Azure OpenAI role_information tokens (system message)
        azure_role_tokens = self.count_text_tokens(azure_role_information, model_name) if azure_role_information else 0

        return {
            "text": messages_result.text_tokens,
            "images": messages_result.image_tokens,
            "search_context": search_tokens,
            "azure_role_information": azure_role_tokens,
            "total": messages_result.text_tokens + messages_result.image_tokens + search_tokens + azure_role_tokens,
            "metadata": {
                "model_name": model_name,
                "messages_metadata": messages_result.metadata,
                "search_context_length": len(search_context) if search_context else 0,
                "azure_role_information_length": len(azure_role_information) if azure_role_information else 0,
                "settings": {
                    "image_base_tokens": self.image_base_tokens,
                    "image_weight_multiplier": self.image_weight_multiplier,
                    "size_tiers": self.image_size_tiers
                }
            }
        }


# Global instance for use throughout the application
token_counter = TokenCounter()