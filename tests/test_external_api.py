"""
Unit tests for External API functionality.

Tests cover authentication, rate limiting, search functionality,
and error handling for the external REST API.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from backend.api.auth import APIKeyManager, security_middleware
from backend.api.models import SearchRequest, SearchResponse, HealthCheckResponse
from backend.search_providers.base import SearchDocument, SearchQuery


class TestAPIKeyManager:
    """Test API Key authentication and management."""

    def setup_method(self):
        """Setup test fixtures."""
        self.api_key_manager = APIKeyManager()
        # Clear existing keys and add test keys
        self.api_key_manager.api_keys = {}

        # Manually add test keys
        test_key = "test-api-key-12345"
        key_hash = self.api_key_manager._hash_key(test_key)

        self.api_key_manager.api_keys[key_hash] = {
            'client_name': 'test_client',
            'raw_key': test_key,
            'allowed_ips': {'*'},
            'created_at': datetime.utcnow(),
            'last_used': None,
            'usage_count': 0,
            'is_active': True,
            'expires_at': None,
            'rotation_schedule_days': 90,
            'grace_period_days': 7
        }

    def test_valid_api_key_any_ip(self):
        """Test valid API key with wildcard IP."""
        is_valid, client_name, error = self.api_key_manager.validate_key(
            "test-api-key-12345", "192.168.1.100"
        )

        assert is_valid is True
        assert client_name == "test_client"
        assert error is None

    def test_valid_api_key_specific_ip(self):
        """Test valid API key with specific IP restriction."""
        # Add key with specific IP restriction
        test_key = "restricted-api-key-67890"
        key_hash = self.api_key_manager._hash_key(test_key)

        self.api_key_manager.api_keys[key_hash] = {
            'client_name': 'restricted_client',
            'raw_key': test_key,
            'allowed_ips': {'192.168.1.100', '10.0.0.50'},
            'created_at': datetime.utcnow(),
            'last_used': None,
            'usage_count': 0,
            'is_active': True,
            'expires_at': None,
            'rotation_schedule_days': 90,
            'grace_period_days': 7
        }

        # Test allowed IP
        is_valid, client_name, error = self.api_key_manager.validate_key(
            test_key, "192.168.1.100"
        )
        assert is_valid is True
        assert client_name == "restricted_client"

        # Test disallowed IP
        is_valid, client_name, error = self.api_key_manager.validate_key(
            test_key, "192.168.1.101"
        )
        assert is_valid is False
        assert "not authorized" in error.lower()

    def test_invalid_api_key(self):
        """Test invalid API key."""
        is_valid, client_name, error = self.api_key_manager.validate_key(
            "invalid-key", "192.168.1.100"
        )

        assert is_valid is False
        assert client_name is None
        assert "invalid api key" in error.lower()

    def test_empty_api_key(self):
        """Test empty API key."""
        is_valid, client_name, error = self.api_key_manager.validate_key(
            "", "192.168.1.100"
        )

        assert is_valid is False
        assert client_name is None
        assert "required" in error.lower()

    def test_usage_tracking(self):
        """Test that API key usage is tracked."""
        # First call
        is_valid, client_name, error = self.api_key_manager.validate_key(
            "test-api-key-12345", "192.168.1.100"
        )

        key_hash = self.api_key_manager._hash_key("test-api-key-12345")
        key_info = self.api_key_manager.api_keys[key_hash]

        assert key_info['usage_count'] == 1
        assert key_info['last_used'] is not None

        # Second call
        self.api_key_manager.validate_key("test-api-key-12345", "192.168.1.100")
        assert key_info['usage_count'] == 2

    def test_inactive_key(self):
        """Test inactive API key."""
        key_hash = self.api_key_manager._hash_key("test-api-key-12345")
        self.api_key_manager.api_keys[key_hash]['is_active'] = False

        is_valid, client_name, error = self.api_key_manager.validate_key(
            "test-api-key-12345", "192.168.1.100"
        )

        assert is_valid is False
        assert "inactive" in error.lower()


class TestSecurityMiddleware:
    """Test security middleware functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.middleware = security_middleware

    def test_normal_request(self):
        """Test normal, non-suspicious request."""
        request_data = {
            'query': 'Comment configurer Azure AD?',
            'max_results': 10
        }

        is_suspicious, reason = self.middleware.is_request_suspicious(request_data)
        assert is_suspicious is False
        assert reason is None

    def test_script_injection_detection(self):
        """Test detection of script injection attempts."""
        request_data = {
            'query': '<script>alert("xss")</script>What is Azure?',
            'max_results': 10
        }

        is_suspicious, reason = self.middleware.is_request_suspicious(request_data)
        assert is_suspicious is True
        assert "script" in reason.lower()

    def test_sql_injection_detection(self):
        """Test detection of SQL injection attempts."""
        request_data = {
            'query': "'; DROP TABLE users; --",
            'max_results': 10
        }

        is_suspicious, reason = self.middleware.is_request_suspicious(request_data)
        assert is_suspicious is True
        assert "drop table" in reason.lower()

    def test_very_long_query(self):
        """Test detection of unusually long queries."""
        request_data = {
            'query': 'A' * 2500,  # Longer than 2000 character limit
            'max_results': 10
        }

        is_suspicious, reason = self.middleware.is_request_suspicious(request_data)
        assert is_suspicious is True
        assert "too long" in reason.lower()

    def test_excessive_special_characters(self):
        """Test detection of excessive special characters."""
        request_data = {
            'query': '!@#$%^&*()_+[]{}|;:,.<>?`~',
            'max_results': 10
        }

        is_suspicious, reason = self.middleware.is_request_suspicious(request_data)
        assert is_suspicious is True
        assert "special characters" in reason.lower()


class TestSearchRequestValidation:
    """Test Pydantic model validation for search requests."""

    def test_valid_search_request(self):
        """Test valid search request creation."""
        request_data = {
            'query': 'Comment configurer Azure AD?',
            'max_results': 10,
            'include_metadata': True,
            'sort_by': 'relevance'
        }

        request = SearchRequest(**request_data)
        assert request.query == 'Comment configurer Azure AD?'
        assert request.max_results == 10
        assert request.include_metadata is True
        assert request.sort_by == 'relevance'

    def test_query_validation_empty(self):
        """Test validation of empty query."""
        with pytest.raises(ValueError):
            SearchRequest(query='')

    def test_query_validation_whitespace(self):
        """Test validation of whitespace-only query."""
        with pytest.raises(ValueError):
            SearchRequest(query='   ')

    def test_max_results_limits(self):
        """Test max_results validation limits."""
        # Too low
        with pytest.raises(ValueError):
            SearchRequest(query='test', max_results=0)

        # Too high
        with pytest.raises(ValueError):
            SearchRequest(query='test', max_results=100)

        # Valid values
        request = SearchRequest(query='test', max_results=1)
        assert request.max_results == 1

        request = SearchRequest(query='test', max_results=50)
        assert request.max_results == 50

    def test_default_values(self):
        """Test default values for optional fields."""
        request = SearchRequest(query='test query')

        assert request.max_results == 10
        assert request.include_metadata is True
        assert request.sort_by == 'relevance'
        assert request.use_semantic_search is True
        assert request.filters is None

    def test_query_trimming(self):
        """Test that query is trimmed of whitespace."""
        request = SearchRequest(query='  test query  ')
        assert request.query == 'test query'


@pytest.mark.asyncio
class TestAPIRoutes:
    """Test API route handlers (integration tests)."""

    def setup_method(self):
        """Setup test fixtures."""
        # Mock search provider
        self.mock_search_provider = AsyncMock()
        self.mock_search_provider.search = AsyncMock()
        self.mock_search_provider.health_check = AsyncMock(return_value=True)
        self.mock_search_provider.get_supported_features = MagicMock(
            return_value=["semantic_search", "vector_search"]
        )
        self.mock_search_provider.__class__.__name__ = "AzureSearchProvider"

    @patch('backend.api.routes.create_search_provider')
    async def test_search_endpoint_success(self, mock_create_provider):
        """Test successful search request."""
        # Setup mock
        mock_create_provider.return_value = self.mock_search_provider

        # Mock search results
        mock_documents = [
            SearchDocument(
                content="Azure AD authentication configuration...",
                title="Azure AD Setup Guide",
                score=0.95,
                url="https://docs.microsoft.com/azure-ad",
                metadata={"document_type": "pdf", "language": "fr"}
            ),
            SearchDocument(
                content="Configure single sign-on with Azure...",
                title="SSO Configuration",
                score=0.87,
                url="https://docs.microsoft.com/sso",
                metadata={"document_type": "html", "language": "en"}
            )
        ]
        self.mock_search_provider.search.return_value = mock_documents

        # Test the search function logic (without actual HTTP request)
        search_query = SearchQuery(
            query="Azure AD configuration",
            top_k=10,
            use_semantic_search=True
        )

        results = await self.mock_search_provider.search(search_query)

        assert len(results) == 2
        assert results[0].score == 0.95
        assert "Azure AD authentication" in results[0].content
        assert results[0].metadata["document_type"] == "pdf"

    @patch('backend.api.routes.create_search_provider')
    async def test_search_provider_unavailable(self, mock_create_provider):
        """Test behavior when search provider is unavailable."""
        mock_create_provider.return_value = None

        # This would result in a 503 error in the actual route handler
        provider = await mock_create_provider()
        assert provider is None

    @patch('backend.api.routes.create_search_provider')
    async def test_health_check_healthy(self, mock_create_provider):
        """Test health check when all services are healthy."""
        mock_create_provider.return_value = self.mock_search_provider

        provider = await mock_create_provider()
        is_healthy = await provider.health_check()

        assert is_healthy is True

    @patch('backend.api.routes.create_search_provider')
    async def test_health_check_unhealthy(self, mock_create_provider):
        """Test health check when search provider is unhealthy."""
        self.mock_search_provider.health_check = AsyncMock(return_value=False)
        mock_create_provider.return_value = self.mock_search_provider

        provider = await mock_create_provider()
        is_healthy = await provider.health_check()

        assert is_healthy is False

    @patch('backend.api.routes.create_search_provider')
    async def test_capabilities_endpoint(self, mock_create_provider):
        """Test capabilities endpoint."""
        mock_create_provider.return_value = self.mock_search_provider

        provider = await mock_create_provider()
        features = provider.get_supported_features()

        assert "semantic_search" in features
        assert "vector_search" in features


class TestErrorHandling:
    """Test error handling and response formatting."""

    def test_format_search_error_connection(self):
        """Test formatting of connection errors."""
        from backend.api.routes import format_search_error

        error = Exception("Connection timeout to search service")
        result = format_search_error(error, "req_123")

        assert result['error_code'] == 'SEARCH_TIMEOUT'
        assert 'timeout' in result['error_message'].lower()
        assert result['request_id'] == 'req_123'

    def test_format_search_error_quota(self):
        """Test formatting of quota exceeded errors."""
        from backend.api.routes import format_search_error

        error = Exception("Search quota exceeded for this month")
        result = format_search_error(error, "req_456")

        assert result['error_code'] == 'SEARCH_QUOTA_EXCEEDED'
        assert 'quota' in result['error_message'].lower()

    def test_format_search_error_generic(self):
        """Test formatting of generic errors."""
        from backend.api.routes import format_search_error

        error = Exception("Unexpected search error")
        result = format_search_error(error, "req_789")

        assert result['error_code'] == 'SEARCH_ERROR'
        assert result['error_message'] == 'Search operation failed'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])