"""
Base abstract class for search providers.

This module defines the interface that all search providers must implement.
It provides a standard API for different search backends (Azure Search, Elasticsearch, 
Pinecone, Weaviate, etc.) to ensure consistency and extensibility.

Key features:
- Standardized search interface
- Support for advanced search parameters (semantic, vector, hybrid)
- Permission-based filtering
- Unified document format
- Extensible for future search providers
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class SearchDocument:
    """
    Standardized document format returned by search providers.
    
    This ensures all search providers return documents in the same format,
    regardless of the underlying search technology.
    """
    content: str
    title: Optional[str] = None
    url: Optional[str] = None
    filename: Optional[str] = None
    score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SearchQuery:
    """
    Standardized search query parameters.

    Encapsulates all search parameters to provide a clean interface
    and enable advanced search features across different providers.
    """
    query: str
    top_k: Optional[int] = None
    filters: Optional[str] = None
    user_permissions: Optional[str] = None
    use_semantic_search: Optional[bool] = None  # None = use config default, True/False = explicit
    use_vector_search: bool = False
    use_hybrid_search: bool = False
    semantic_configuration: Optional[str] = None
    vector_fields: Optional[List[str]] = None
    include_total_count: bool = True

    # Advanced search parameters
    min_score_threshold: Optional[float] = None
    boost_fields: Optional[Dict[str, float]] = None
    custom_parameters: Optional[Dict[str, Any]] = None

    # External API flag - when True, URLs are transformed to Avanteam PageLoader format
    for_external_api: bool = False


class SearchProvider(ABC):
    """
    Abstract base class for all search providers.
    
    This class defines the interface that all search providers must implement,
    ensuring consistent behavior across different search technologies.
    
    Features:
    - Standardized search API
    - Resource management (initialization/cleanup)
    - Configuration validation
    - Error handling standardization
    - Extensibility for new search backends
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the search provider.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config or {}
        self.initialized = False
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the search provider.
        
        This method should:
        - Validate configuration
        - Initialize connections
        - Set up authentication
        - Prepare any necessary resources
        
        Raises:
            SearchProviderError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def search(self, search_query: SearchQuery) -> List[SearchDocument]:
        """
        Perform a search query.
        
        Args:
            search_query: SearchQuery object containing all search parameters
            
        Returns:
            List of SearchDocument objects sorted by relevance (highest score first)
            
        Raises:
            SearchProviderError: If search fails
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        Clean up resources and close connections.
        
        This method should properly close all connections and clean up
        any resources to prevent memory leaks.
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if the search provider is healthy and available.
        
        Returns:
            True if the provider is healthy, False otherwise
        """
        try:
            # Perform a simple search to test connectivity
            test_query = SearchQuery(query="test", top_k=1)
            await self.search(test_query)
            return True
        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            return False
    
    def get_supported_features(self) -> List[str]:
        """
        Get list of features supported by this provider.
        
        Returns:
            List of supported feature names
        """
        return [
            "basic_search",
            "filtered_search", 
            "permission_filtering"
        ]
    
    def validate_config(self) -> bool:
        """
        Validate the provider configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        return True


class SearchProviderError(Exception):
    """
    Base exception for search provider errors.
    
    All search providers should raise this exception (or its subclasses)
    for consistent error handling across the application.
    """
    
    def __init__(self, message: str, provider: str = "unknown", original_error: Exception = None):
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error
    
    def __str__(self):
        base_msg = f"[{self.provider}] {super().__str__()}"
        if self.original_error:
            base_msg += f" (caused by: {self.original_error})"
        return base_msg


class SearchConfigurationError(SearchProviderError):
    """Exception raised for search provider configuration errors."""
    pass


class SearchConnectionError(SearchProviderError):
    """Exception raised for search provider connection errors.""" 
    pass


class SearchQueryError(SearchProviderError):
    """Exception raised for search query execution errors."""
    pass


def create_citation_from_document(doc: SearchDocument, doc_id: int, max_length: int = 200) -> Dict[str, Any]:
    """
    Create a citation object from a search document.
    
    This function maintains compatibility with the existing citation format
    used throughout the application.
    
    Args:
        doc: SearchDocument object
        doc_id: Unique identifier for the document
        max_length: Maximum length for citation content
        
    Returns:
        Citation dictionary compatible with frontend display
    """
    title = doc.title or f"Document {doc_id}"
    content = doc.content or ""
    
    return {
        "id": f"doc{doc_id}",
        "title": title,
        "content": content[:max_length] + "..." if len(content) > max_length else content,
        "url": doc.url or "",
        "filepath": doc.filename or doc.metadata.get("source", "Document") if doc.metadata else "Document",
        "chunk_id": str(doc_id)
    }


def build_search_context(search_documents: List[SearchDocument], citation_max_length: int = 200) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build search context and citations from search documents.
    
    This function maintains compatibility with the existing context building
    logic used by LLM providers.
    
    Args:
        search_documents: List of SearchDocument objects
        citation_max_length: Maximum length for citation content
        
    Returns:
        Tuple of (context_string, citations_list)
    """
    if not search_documents:
        return "", []
    
    context_parts = []
    citations = []
    
    for i, doc in enumerate(search_documents):
        doc_id = i + 1
        content = doc.content.strip() if doc.content else ""
        title = doc.title or doc.filename or f"Document {doc_id}"
        
        if content:
            # Limit content size to prevent token limit issues
            if len(content) > 8000:
                content = content[:7900] + "... [contenu tronqué]"
            
            # Add document to context
            context_parts.append(f"[doc{doc_id}] {title}\n{content}")
            
            # Create citation
            citation = create_citation_from_document(doc, doc_id, citation_max_length)
            citations.append(citation)
    
    search_context = "\n\n".join(context_parts)
    return search_context, citations