"""
Utility classes and functions shared across LLM providers.

This module contains utilities that are used by multiple LLM providers,
such as search integration, response formatting helpers, and
common data processing functions.

This module now uses the new search_providers system for enhanced
performance and extensibility while maintaining backward compatibility.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.settings import app_settings
from backend.search_providers import create_search_provider, SearchQuery, SearchDocument


class AzureSearchService:
    """
    Service to handle search queries for LLM providers.
    
    This service provides a unified interface for searching various search indexes
    and retrieving relevant documents for LLM context. It now uses the new
    search_providers system for enhanced performance while maintaining compatibility.
    
    Key features:
    - Enhanced search performance with optimized algorithms
    - Support for multiple search providers (extensible)
    - Advanced ranking and relevance scoring
    - Permission-based filtering
    - Semantic and vector search capabilities
    """
    
    def __init__(self):
        """Initialize the search service."""
        self.search_provider = None
        self.initialized = False
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def close(self):
        """Close the search provider and clean up resources."""
        if self.search_provider:
            try:
                await self.search_provider.close()
                self.logger.debug("Search provider closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing search provider: {e}")
            finally:
                self.search_provider = None
                self.initialized = False
    
    async def search_documents(
        self,
        query: str,
        top_k: int = None,
        filters: str = None,
        user_permissions: str = None,
        user_custom_data: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for documents relevant to the query.

        This method now uses the enhanced search_providers system for improved
        performance and relevance while maintaining full backward compatibility.

        Args:
            query: The search query string
            top_k: Maximum number of documents to return
            filters: Additional OData filter string
            user_permissions: User permissions for document filtering
            user_custom_data: User custom data for metadata filtering

        Returns:
            List of documents with content, metadata, and relevance scores
        """
        try:
            # Validate datasource configuration
            if not app_settings.datasource:
                self.logger.warning("Search datasource not configured")
                return []
            
            # Debug logging for top_k parameter - identify which LLM is calling
            import inspect
            caller_frame = inspect.currentframe().f_back
            caller_info = "unknown"
            
            try:
                # Try to find the LLM provider in the call stack
                frame = caller_frame
                for _ in range(10):  # Check up to 10 frames up
                    if frame and frame.f_locals:
                        # Look for 'self' with provider info
                        if 'self' in frame.f_locals:
                            obj = frame.f_locals['self']
                            if hasattr(obj, '__class__'):
                                class_name = obj.__class__.__name__
                                if 'Provider' in class_name:
                                    caller_info = class_name
                                    break
                    frame = frame.f_back if frame else None
            except:
                pass
            
            self.logger.info(f"[LLM PROVIDER] {caller_info} is using ENHANCED search system")
            print(f"[LLM PROVIDER] {caller_info} is using ENHANCED search system")
            self.logger.info(f"AzureSearchService: search_documents called with top_k parameter: {top_k}")
            print(f"[DOCS COUNT] AzureSearchService: search_documents called with top_k parameter: {top_k}")
            
            # Initialize search provider if not already done
            if not self.search_provider:
                self.search_provider = await create_search_provider()
                self.initialized = True
                self.logger.info("[ENHANCED SEARCH] Initialized new optimized search provider system")
                print("[ENHANCED SEARCH] Initialized new optimized search provider system")
            
            # Create search query with enhanced parameters
            search_query = SearchQuery(
                query=query,
                top_k=top_k,
                filters=filters,
                user_permissions=user_permissions,
                user_custom_data=user_custom_data,
                use_semantic_search=True,  # Enable advanced search features
                include_total_count=True
            )
            
            # DEBUG: Log the query being sent to the enhanced search system
            print(f"[ENHANCED SEARCH DEBUG] Query sent to search provider: '{query}'")
            
            self.logger.info("[ENHANCED SEARCH] Executing optimized search with semantic features enabled")
            self.logger.info(f"AzureSearchService: Final search top_k used: {search_query.top_k}")
            
            # Execute enhanced search
            search_documents = await self.search_provider.search(search_query)
            
            # Convert SearchDocument objects to legacy format for compatibility
            documents = []
            for doc in search_documents:
                legacy_doc = {
                    "content": doc.content,
                    "title": doc.title,
                    "url": doc.url,
                    "filename": doc.filename,
                    "score": doc.score,
                    "metadata": doc.metadata or {}
                }
                documents.append(legacy_doc)
            
            self.logger.info(f"[ENHANCED SEARCH] Successfully returned {len(documents)} documents with improved ranking and semantic search")
            return documents
            
        except Exception as e:
            self.logger.error(f"Enhanced search query failed: {e}")
            # Fallback: return empty list to maintain compatibility
            return []
    
    def _build_filters(
        self, 
        filters: Optional[str], 
        user_permissions: Optional[str]
    ) -> Optional[str]:
        """
        Build combined OData filter from user filters and permissions.
        
        This method is now deprecated but maintained for backward compatibility.
        The new search providers system handles filtering internally.
        
        Args:
            filters: Custom OData filter string
            user_permissions: User permissions for document access control
            
        Returns:
            Combined filter string or None if no filters needed
        """
        # This method is kept for compatibility but the new search provider
        # handles filtering internally for better performance
        permission_filter = None
        
        # Generate permission-based filter if configured
        if (user_permissions and 
            hasattr(app_settings.datasource, 'permitted_groups_column') and 
            app_settings.datasource.permitted_groups_column):
            try:
                permission_filter = generateFilterStringFromFullDef(user_permissions)
                self.logger.debug(f"Generated permission filter: {permission_filter}")
            except Exception as e:
                self.logger.warning(f"Failed to generate permission filter: {e}")
        
        # Combine filters
        if permission_filter and filters:
            return f"({permission_filter}) and ({filters})"
        elif permission_filter:
            return permission_filter
        elif filters:
            return filters
        else:
            return None
    
    def _configure_semantic_search(self, search_params: Dict[str, Any]):
        """
        Configure semantic search parameters if available.
        
        This method is now deprecated but maintained for backward compatibility.
        The new search providers system handles semantic search automatically.
        
        Args:
            search_params: Dictionary of search parameters to modify
        """
        # This method is kept for compatibility but the new search provider
        # handles semantic search configuration automatically for better results
        if (hasattr(app_settings.datasource, 'use_semantic_search') and 
            app_settings.datasource.use_semantic_search):
            if (hasattr(app_settings.datasource, 'semantic_search_config') and 
                app_settings.datasource.semantic_search_config):
                search_params["query_type"] = "semantic"
                search_params["semantic_configuration_name"] = app_settings.datasource.semantic_search_config
                self.logger.debug("Enabled semantic search (legacy method)")
    
    async def _process_search_results(self, results) -> List[Dict[str, Any]]:
        """
        Process raw search results into standardized document format.
        
        This method is now deprecated but maintained for backward compatibility.
        The new search providers system handles result processing automatically.
        
        Args:
            results: Search results iterator
            
        Returns:
            List of processed documents with standardized fields
        """
        # This method is kept for compatibility but the new search provider
        # handles result processing automatically for better performance
        documents = []
        
        async for result in results:
            # Extract document information
            doc = {
                "content": self._extract_content(result),
                "title": self._extract_field(result, app_settings.datasource.title_column),
                "url": self._extract_field(result, app_settings.datasource.url_column),
                "filename": self._extract_field(result, app_settings.datasource.filename_column),
                "score": result.get("@search.score", 0),
                "metadata": {
                    "id": result.get("id", ""),
                    "source": self._extract_field(result, app_settings.datasource.filename_column) or "Document"
                }
            }
            documents.append(doc)
        
        return documents
    
    def _extract_content(self, result: Dict[str, Any]) -> str:
        """
        Extract content from search result using configured content columns.
        
        Args:
            result: Single search result dictionary
            
        Returns:
            Extracted content as string
        """
        # Try configured content columns first
        content_columns = app_settings.datasource.content_columns or ["content", "merged_content"]
        
        for column in content_columns:
            if column in result:
                content = result[column]
                if isinstance(content, list):
                    return " ".join(str(item) for item in content)
                return str(content) if content else ""
        
        # Fallback: find any text field that looks like content
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 50:
                return value
        
        return ""
    
    def _extract_field(self, result: Dict[str, Any], field_name: Optional[str]) -> Optional[str]:
        """
        Extract a specific field from search result.
        
        Args:
            result: Single search result dictionary
            field_name: Name of the field to extract
            
        Returns:
            Field value as string or None if not found
        """
        if not field_name or field_name not in result:
            return None
        
        value = result[field_name]
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value) if value else None


def create_citation_from_document(doc: Dict[str, Any], doc_id: int, max_length: int = 200) -> Dict[str, Any]:
    """
    Create a citation object from a search document.
    
    Args:
        doc: Document dictionary from search results
        doc_id: Unique identifier for the document
        max_length: Maximum length for citation content (default: 200)
        
    Returns:
        Citation dictionary compatible with frontend display
    """
    title = doc.get("title", f"Document {doc_id}")
    content = doc.get("content", "")
    
    return {
        "id": f"doc{doc_id}",
        "title": title,
        "content": content[:max_length] + "..." if len(content) > max_length else content,
        "url": doc.get("url", ""),
        "filepath": doc.get("filename", doc.get("metadata", {}).get("source", "Document")),
        "chunk_id": str(doc_id)
    }


def build_search_context(search_results: List[Dict[str, Any]], citation_max_length: int = 200) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build search context and citations from search results.
    
    Args:
        search_results: List of documents from Azure Search
        citation_max_length: Maximum length for citation content (default: 200)
        
    Returns:
        Tuple of (context_string, citations_list)
    """
    if not search_results:
        return "", []
    
    context_parts = []
    citations = []
    
    for i, doc in enumerate(search_results):
        doc_id = i + 1
        content = doc.get("content", "").strip()
        title = doc.get("title") or doc.get("filename") or f"Document {doc_id}"
        
        if content:
            # Limit content size to prevent Claude API errors (max ~8000 chars per doc)
            if len(content) > 8000:
                content = content[:7900] + "... [contenu tronqué]"
            
            # Add document to context
            context_parts.append(f"[doc{doc_id}] {title}\n{content}")
            
            # Create citation
            citation = create_citation_from_document(doc, doc_id, citation_max_length)
            citations.append(citation)
    
    search_context = "\n\n".join(context_parts)
    return search_context, citations