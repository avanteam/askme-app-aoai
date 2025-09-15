"""
Search providers module.

This module provides a unified interface for different search providers,
enabling extensible and consistent search functionality across the application.

Supported providers:
- azure_search: Azure AI Search with advanced optimizations
- elasticsearch: Elasticsearch (future implementation)
- pinecone: Pinecone vector database (future implementation)
- weaviate: Weaviate vector database (future implementation)

Usage:
    from backend.search_providers import create_search_provider
    
    # Create provider using environment configuration
    provider = await create_search_provider()
    
    # Use provider for search
    query = SearchQuery(query="example search", top_k=5)
    results = await provider.search(query)
"""

import os
import logging
from typing import Any, Dict, Optional

from .base import SearchProvider, SearchQuery, SearchDocument, SearchProviderError
from .azure_search import AzureSearchProvider


# Registry of available search providers
SEARCH_PROVIDERS = {
    "azure_search": AzureSearchProvider,
    "azuresearch": AzureSearchProvider,  # Alternative name
    "azure_cognitive_search": AzureSearchProvider,  # Legacy name
    # Future providers can be added here
    # "elasticsearch": ElasticsearchProvider,
    # "pinecone": PineconeProvider,
    # "weaviate": WeaviateProvider,
}

# Default provider
DEFAULT_SEARCH_PROVIDER = "azure_search"

logger = logging.getLogger(__name__)


def get_configured_search_provider() -> str:
    """
    Get the configured search provider name.
    
    This function determines which search provider to use based on:
    1. SEARCH_PROVIDER environment variable (new)
    2. DATASOURCE_TYPE environment variable (legacy compatibility)
    3. Default provider if none specified
    
    Returns:
        Name of the search provider to use
    """
    # Check new environment variable first
    provider = os.environ.get("SEARCH_PROVIDER", "").lower()
    if provider and provider in SEARCH_PROVIDERS:
        logger.debug(f"Using search provider from SEARCH_PROVIDER: {provider}")
        return provider
    
    # Check legacy DATASOURCE_TYPE for backward compatibility
    datasource_type = os.environ.get("DATASOURCE_TYPE", "").lower()
    legacy_mapping = {
        "azurecognitivesearch": "azure_search",
        "azure_cognitive_search": "azure_search",
        "azuresearch": "azure_search",
        # Future mappings can be added here
        # "elasticsearch": "elasticsearch",
        # "pinecone": "pinecone",
    }
    
    if datasource_type in legacy_mapping:
        mapped_provider = legacy_mapping[datasource_type]
        logger.debug(f"Using search provider from legacy DATASOURCE_TYPE: {datasource_type} -> {mapped_provider}")
        return mapped_provider
    
    # Use default provider
    logger.debug(f"Using default search provider: {DEFAULT_SEARCH_PROVIDER}")
    return DEFAULT_SEARCH_PROVIDER


async def create_search_provider(
    provider_name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> SearchProvider:
    """
    Create and initialize a search provider.
    
    Factory function that creates the appropriate search provider based on
    configuration or explicit provider name.
    
    Args:
        provider_name: Name of the provider to create (optional)
        config: Provider-specific configuration (optional)
        
    Returns:
        Initialized SearchProvider instance
        
    Raises:
        SearchProviderError: If provider creation or initialization fails
    """
    # Determine provider name
    if provider_name is None:
        provider_name = get_configured_search_provider()
    
    provider_name = provider_name.lower()
    
    # Validate provider
    if provider_name not in SEARCH_PROVIDERS:
        available_providers = list(SEARCH_PROVIDERS.keys())
        raise SearchProviderError(
            f"Unknown search provider: {provider_name}. "
            f"Available providers: {available_providers}",
            provider_name
        )
    
    try:
        # Create provider instance
        provider_class = SEARCH_PROVIDERS[provider_name]
        provider = provider_class(config)
        
        # Initialize provider
        await provider.initialize()
        
        logger.info(f"Successfully created and initialized search provider: {provider_name}")
        return provider
        
    except Exception as e:
        if isinstance(e, SearchProviderError):
            raise
        raise SearchProviderError(
            f"Failed to create search provider {provider_name}: {e}",
            provider_name,
            e
        )


def list_available_providers() -> Dict[str, str]:
    """
    List all available search providers.
    
    Returns:
        Dictionary mapping provider names to their description
    """
    return {
        "azure_search": "Azure AI Search with advanced optimizations",
        # Future providers will be added here
        # "elasticsearch": "Elasticsearch full-text search",
        # "pinecone": "Pinecone vector database",
        # "weaviate": "Weaviate vector database",
    }


def validate_provider_config(provider_name: str) -> bool:
    """
    Validate configuration for a specific provider.
    
    Args:
        provider_name: Name of the provider to validate
        
    Returns:
        True if configuration is valid, False otherwise
    """
    provider_name = provider_name.lower()
    
    if provider_name not in SEARCH_PROVIDERS:
        return False
    
    try:
        # Create temporary provider instance to validate config
        provider_class = SEARCH_PROVIDERS[provider_name]
        provider = provider_class()
        return provider.validate_config()
    except Exception as e:
        logger.warning(f"Configuration validation failed for {provider_name}: {e}")
        return False


# Convenience exports for backward compatibility
__all__ = [
    # Main factory function
    "create_search_provider",
    
    # Base classes
    "SearchProvider",
    "SearchQuery", 
    "SearchDocument",
    "SearchProviderError",
    
    # Specific providers
    "AzureSearchProvider",
    
    # Utility functions
    "get_configured_search_provider",
    "list_available_providers",
    "validate_provider_config",
]