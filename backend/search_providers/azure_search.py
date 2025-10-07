"""
Azure Search provider implementation.

This module implements an optimized Azure Search provider that aims to match
the performance of Azure OpenAI's native "On Your Data" functionality.

Key optimizations:
- Advanced semantic and vector search support
- Intelligent result ranking and scoring
- Enhanced context building for better RAG performance
- Permission-based filtering
- Hybrid search capabilities
"""

import logging
from typing import Any, Dict, List, Optional

from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity.aio import DefaultAzureCredential
import httpx

from backend.settings import app_settings
from backend.utils import generateFilterStringFromFullDef
from .base import (
    SearchProvider,
    SearchDocument,
    SearchQuery,
    SearchProviderError,
    SearchConfigurationError,
    SearchConnectionError,
    SearchQueryError
)


class AzureSearchProvider(SearchProvider):
    """
    Optimized Azure Search provider.
    
    This provider implements advanced search capabilities to match the performance
    of Azure OpenAI's native "On Your Data" functionality:
    
    Features:
    - Semantic search with configurable models
    - Vector search and hybrid search modes
    - Intelligent result ranking and score normalization
    - Permission-based document filtering
    - Advanced query preprocessing and optimization
    - Result post-processing for enhanced relevance
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Azure Search provider."""
        super().__init__(config)
        self.search_client = None
        self.provider_name = "azure_search"
        
        # Extract configuration from app_settings
        if app_settings.datasource:
            self._extract_datasource_config()
        else:
            raise SearchConfigurationError("No datasource configured", self.provider_name)
    
    def _extract_datasource_config(self):
        """Extract configuration from app_settings datasource."""
        datasource = app_settings.datasource
        
        self.service_name = datasource.service
        self.index_name = datasource.index
        self.api_key = datasource.key
        self.endpoint = f"https://{self.service_name}.search.windows.net"
        
        # Search configuration
        self.default_top_k = getattr(datasource, 'top_k', 5)
        self.use_semantic_search = getattr(datasource, 'use_semantic_search', False)
        self.semantic_config = getattr(datasource, 'semantic_search_config', '')
        self.query_type = getattr(datasource, 'query_type', 'simple')
        
        # Field mappings
        self.content_columns = getattr(datasource, 'content_columns', None) or ["content", "merged_content"]
        self.title_column = getattr(datasource, 'title_column', None)
        self.url_column = getattr(datasource, 'url_column', None)
        self.filename_column = getattr(datasource, 'filename_column', None)
        self.vector_columns = getattr(datasource, 'vector_columns', None)
        self.permitted_groups_column = getattr(datasource, 'permitted_groups_column', None)
        
        # Advanced settings
        self.strictness = getattr(datasource, 'strictness', 3)
        self.enable_in_domain = getattr(datasource, 'enable_in_domain', True)
        
        # Log configuration for debugging
        vector_config = f"vector_columns={self.vector_columns}" if self.vector_columns else "no vector search"
        semantic_config = f"semantic_config={self.semantic_config}" if self.semantic_config else "no semantic search"
        self.logger.info(f"Azure Search configured: service={self.service_name}, index={self.index_name}, {vector_config}, {semantic_config}")

        # Check embedding configuration
        if self.vector_columns:
            if hasattr(app_settings, 'azure_openai') and app_settings.azure_openai:
                azure_openai = app_settings.azure_openai
                embedding_deployment = (
                    getattr(azure_openai, 'embedding_deployment', None) or
                    getattr(azure_openai, 'embedding_name', None) or
                    getattr(azure_openai, 'embedding_model', None)
                )
                if embedding_deployment:
                    self.logger.info(f"[HYBRID SEARCH] Embedding deployment available: {embedding_deployment}")
                else:
                    self.logger.warning(f"[HYBRID SEARCH] Vector columns configured but no embedding deployment found")
            else:
                self.logger.warning(f"[HYBRID SEARCH] Vector columns configured but Azure OpenAI not available")
    
    async def initialize(self) -> None:
        """Initialize Azure Search client and validate configuration."""
        if self.initialized:
            return
        
        try:
            # Validate configuration
            if not self.service_name or not self.index_name:
                raise SearchConfigurationError(
                    "Azure Search service name and index name are required",
                    self.provider_name
                )
            
            # Set up authentication
            if self.api_key:
                credential = AzureKeyCredential(self.api_key)
                self.logger.debug("Using API key authentication")
            else:
                credential = DefaultAzureCredential()
                self.logger.debug("Using managed identity authentication")
            
            # Create search client for validation with latest API version
            test_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=credential,
                api_version="2025-08-01-preview"
            )
            
            # Test connection
            try:
                # Simple test query to validate connectivity
                results = await test_client.search(
                    search_text="*",
                    top=1,
                    include_total_count=True
                )
                
                # Consume the first result to test the connection
                async for _ in results:
                    break
                    
                self.logger.info("Azure Search connection validated successfully")
                
            except Exception as e:
                raise SearchConnectionError(
                    f"Failed to connect to Azure Search: {e}",
                    self.provider_name,
                    e
                )
            finally:
                await test_client.close()
            
            self.initialized = True

        except Exception as e:
            if isinstance(e, SearchProviderError):
                raise
            raise SearchConfigurationError(
                f"Azure Search initialization failed: {e}",
                self.provider_name,
                e
            )

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for query text using Azure OpenAI.

        This enables vector search capabilities for better relevance matching.

        Args:
            text: The query text to generate embeddings for

        Returns:
            List of embedding values or None if generation fails
        """
        try:
            # Only generate embeddings if Azure OpenAI is configured
            if not hasattr(app_settings, 'azure_openai') or not app_settings.azure_openai:
                self.logger.debug("Azure OpenAI not configured, skipping embedding generation")
                return None

            azure_openai = app_settings.azure_openai
            # Try different possible key attribute names
            api_key = getattr(azure_openai, 'api_key', None) or getattr(azure_openai, 'key', None)
            if not azure_openai.endpoint or not api_key:
                self.logger.debug("Azure OpenAI endpoint/key not configured, skipping embedding generation")
                return None

            # Use the configured embedding deployment (check multiple possible names)
            embedding_deployment = (
                getattr(azure_openai, 'embedding_deployment', None) or
                getattr(azure_openai, 'embedding_name', None) or
                getattr(azure_openai, 'embedding_model', None)
            )
            if not embedding_deployment:
                self.logger.debug("No embedding deployment configured (tried embedding_deployment, embedding_name, embedding_model), skipping embedding generation")
                return None

            # Build request to Azure OpenAI embeddings API
            url = f"{azure_openai.endpoint}/openai/deployments/{embedding_deployment}/embeddings"
            headers = {
                "api-key": api_key,
                "Content-Type": "application/json"
            }

            data = {
                "input": text,
                "encoding_format": "float"
            }

            # Use Azure OpenAI API version
            params = {"api-version": getattr(azure_openai, 'api_version', '2024-05-01-preview')}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data, headers=headers, params=params)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("data") and len(result["data"]) > 0:
                        embedding = result["data"][0].get("embedding")
                        if embedding:
                            self.logger.debug(f"Generated embedding with {len(embedding)} dimensions")
                            return embedding
                else:
                    self.logger.warning(f"Embedding generation failed with status {response.status_code}: {response.text}")

        except Exception as e:
            self.logger.warning(f"Failed to generate embedding: {e}")

        return None
    
    async def search(self, search_query: SearchQuery) -> List[SearchDocument]:
        """
        Perform optimized Azure Search query.
        
        This method implements advanced search techniques to improve relevance:
        - Query preprocessing and optimization
        - Intelligent search mode selection
        - Result ranking and score normalization
        - Post-processing for enhanced quality
        """
        await self.initialize()
        
        search_client = None
        try:
            # Create search client for this request
            if self.api_key:
                credential = AzureKeyCredential(self.api_key)
            else:
                credential = DefaultAzureCredential()
            
            search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=credential,
                api_version="2025-08-01-preview"
            )
            
            # Generate embedding for vector search if applicable
            query_embedding = None
            if self._should_use_vector_search(search_query) and self.vector_columns:
                query_embedding = await self._generate_embedding(search_query.query)
                if query_embedding:
                    self.logger.info("[VECTOR SEARCH] Generated query embedding for hybrid search")
                else:
                    self.logger.warning("[VECTOR SEARCH] Failed to generate embedding, falling back to text-only search")

            # Build optimized search parameters
            search_params = self._build_search_parameters(search_query, query_embedding)

            self.logger.info(f"[AZURE SEARCH ENHANCED] Processing query: '{search_query.query}' with advanced optimizations")
            self.logger.debug(f"Azure Search query: '{search_query.query}' with params: {search_params}")
            
            # DEBUG: Final parameters being sent to Azure Search (commented to reduce log noise)
            # print(f"[FINAL DEBUG] Final search_params being sent to Azure Search API: {search_params}")
            
            # DIRECT COMPARISON TEST: Execute the exact same search that Azure OpenAI would do
            # Test if the issue is in our parameter mapping
            if "dérogation" in search_query.query.lower() and "manex" in search_query.query.lower():
                print("[COMPARISON TEST] Testing direct search for FLT-PROC-2311...")
                direct_test_params = {
                    "search_text": "FLT-PROC-2311",
                    "top": search_params.get("top", 5),  # Utilise le même top que la vraie requête
                    "query_type": "semantic",
                    "semantic_configuration_name": search_params.get("semantic_configuration_name")
                }
                direct_results = await search_client.search(**direct_test_params)
                direct_count = 0
                async for result in direct_results:
                    direct_count += 1
                    print(f"[DIRECT TEST] Found: {result.get('titreDocument', result.get('title', 'No title'))} (Score: {result.get('@search.score', 0)})")
                print(f"[DIRECT TEST] Direct search for FLT-PROC-2311 returned {direct_count} results")
            
            # Execute search with professional error handling
            try:
                self.logger.info("[AZURE SEARCH] About to execute search with parameters:")
                for key, value in search_params.items():
                    self.logger.info(f"  {key}: {value}")

                results = await search_client.search(**search_params)

            except Exception as search_error:
                self.logger.error(f"[AZURE SEARCH ERROR] Search failed: {search_error}")
                self.logger.error(f"[AZURE SEARCH ERROR] Error type: {type(search_error)}")

                # If search_fields is the problem, retry without it
                if "search_fields" in search_params and "field" in str(search_error).lower():
                    self.logger.warning("[AZURE SEARCH] Retrying without search_fields parameter...")
                    retry_params = search_params.copy()
                    del retry_params["search_fields"]

                    self.logger.info("[AZURE SEARCH] Retry parameters:")
                    for key, value in retry_params.items():
                        self.logger.info(f"  {key}: {value}")

                    results = await search_client.search(**retry_params)
                    self.logger.info("[AZURE SEARCH] Retry successful - search_fields was the problem")
                else:
                    raise
            
            # Process and optimize results
            documents = await self._process_search_results(results, search_query)
            
            self.logger.info(f"[AZURE SEARCH ENHANCED] Applied advanced ranking to {len(documents)} documents")
            self.logger.debug(f"Azure Search returned {len(documents)} documents")
            
            return documents
            
        except Exception as e:
            # Handle Azure OpenAI proprietary query_type errors with intelligent fallback
            error_message = str(e)
            if "vector_semantic_hybrid" in error_message or "vector_simple_hybrid" in error_message:
                self.logger.warning(f"Azure OpenAI proprietary query_type detected, falling back to compatible search")
                print(f"[FALLBACK] Azure OpenAI proprietary query_type detected: {error_message}")
                
                # Retry with semantic search as fallback
                try:
                    fallback_params = search_params.copy()
                    if "vector_semantic_hybrid" in error_message:
                        fallback_params["query_type"] = "semantic"
                        print("[FALLBACK] Retrying with query_type='semantic'")
                    elif "vector_simple_hybrid" in error_message:
                        fallback_params["query_type"] = "simple"  
                        print("[FALLBACK] Retrying with query_type='simple'")
                    
                    print(f"[FALLBACK] Fallback search_params: {fallback_params}")
                    results = await search_client.search(**fallback_params)
                    
                    # Process and optimize results
                    documents = await self._process_search_results(results, search_query)
                    
                    print(f"[FALLBACK SUCCESS] Successfully recovered with {len(documents)} documents")
                    self.logger.info(f"[FALLBACK SUCCESS] Azure OpenAI compatibility fallback returned {len(documents)} documents")
                    
                    return documents
                    
                except Exception as fallback_error:
                    self.logger.error(f"Fallback search also failed: {fallback_error}")
                    print(f"[FALLBACK FAILED] Fallback search failed: {fallback_error}")
                    # Continue to original error handling
            
            if isinstance(e, SearchProviderError):
                raise
            raise SearchQueryError(
                f"Azure Search query failed: {e}",
                self.provider_name,
                e
            )
        finally:
            if search_client:
                try:
                    await search_client.close()
                except Exception as e:
                    self.logger.warning(f"Error closing search client: {e}")
    
    def _build_search_parameters(self, search_query: SearchQuery, query_embedding: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Build optimized search parameters.
        
        This method applies intelligent parameter selection to maximize search relevance.
        """
        # Preprocess query for better results
        processed_query = self._preprocess_query(search_query.query)
        
        # Only log query processing for debugging when needed
        # print(f"[QUERY DEBUG] Original query: {search_query.query}")
        # print(f"[QUERY DEBUG] Processed query: {processed_query}")
        
        # Base parameters with title field boosting
        top_k = search_query.top_k or self.default_top_k
        search_params = {
            "search_text": processed_query,
            "top": top_k,
            "include_total_count": search_query.include_total_count
        }

        # Log the top_k being used only if it's different from default
        if top_k != self.default_top_k:
            print(f"[TOP_K] Using top_k={top_k} (default={self.default_top_k})")
        
        # Use EXACTLY the same parameters that Azure OpenAI uses
        # Get the Azure OpenAI configuration from app_settings
        from backend.settings import app_settings
        if app_settings.datasource:
            # Extract the same configuration Azure OpenAI would use
            azure_config = app_settings.datasource.construct_payload_configuration(
                documents_count=search_query.top_k,
                user_permissions=search_query.user_permissions
            )
            azure_params = azure_config.get("parameters", {})
            
            print(f"[AZURE COMPATIBILITY] Using Azure OpenAI parameters: {list(azure_params.keys())}")
            
            # Map Azure OpenAI query_type to public API supported values
            if "query_type" in azure_params:
                azure_query_type = azure_params["query_type"]
                mapped_query_type = self._map_azure_openai_query_type(azure_query_type)

                if mapped_query_type:
                    search_params["query_type"] = mapped_query_type
                    print(f"[SEARCH MODE] Mapped Azure OpenAI query_type '{azure_query_type}' -> '{mapped_query_type}'")
                else:
                    print(f"[SEARCH MODE] Azure OpenAI query_type '{azure_query_type}' not supported, using default")
                    # Don't set query_type if mapping failed
            else:
                # No query type found - using default
                pass

            # Override with explicit use_semantic_search parameter from External API
            if hasattr(search_query, 'use_semantic_search') and search_query.use_semantic_search is not None:
                if search_query.use_semantic_search is False:
                    # Explicitly disable semantic search
                    search_params["query_type"] = "simple"
                    print(f"[SEARCH MODE] Overriding to 'simple' (use_semantic_search=False)")
                elif search_query.use_semantic_search is True:
                    # Explicitly enable semantic search
                    if self.semantic_config:
                        search_params["query_type"] = "semantic"
                        print(f"[SEARCH MODE] Overriding to 'semantic' (use_semantic_search=True)")
                    else:
                        print(f"[SEARCH MODE] Cannot enable semantic search: no semantic_config available")
            else:
                # use_semantic_search is None or not provided - use configuration from Azure OpenAI/settings
                print(f"[SEARCH MODE] Using default from config (use_semantic_search=None, config query_type='{search_params.get('query_type', 'not set')}')")
            
            # Apply semantic configuration if present
            if "semantic_configuration" in azure_params and azure_params["semantic_configuration"]:
                search_params["semantic_configuration_name"] = azure_params["semantic_configuration"]
                print(f"[SEMANTIC SEARCH] Using Azure OpenAI semantic config: {azure_params['semantic_configuration']}")
            
            # Check for other critical Azure OpenAI parameters that might affect ranking
            if "strictness" in azure_params:
                print(f"[AZURE PARAM] strictness: {azure_params['strictness']}")
                # Note: strictness is not directly applicable to public Azure Search API
            
            if "in_scope" in azure_params:
                print(f"[AZURE PARAM] in_scope: {azure_params['in_scope']}")
                # Note: in_scope is Azure OpenAI specific, not available in public API
        else:
            # Fallback to basic configuration
            search_mode = self._determine_optimal_search_mode(search_query)
            if search_mode != "simple":
                search_params["query_type"] = search_mode
        
        # Add enhanced vector search parameters (2025-08-01-preview features)
        if query_embedding and self.vector_columns:
            # Build vector queries for hybrid search
            vector_queries = []
            for vector_column in self.vector_columns:
                vector_query = {
                    "kind": "vector",  # Required by Azure Search API 2025
                    "vector": query_embedding,
                    "fields": vector_column,
                    "k": top_k
                }
                vector_queries.append(vector_query)

            search_params["vector_queries"] = vector_queries
            self.logger.info(f"[HYBRID SEARCH] Added vector search for {len(self.vector_columns)} vector columns")

            # Use strict postfiltering for improved precision (2025-08-01-preview)
            if hasattr(search_query, 'enable_strict_filtering') and search_query.enable_strict_filtering:
                search_params["vector_filter_mode"] = "strictPostFilter"
                self.logger.info("[2025-API] Using strict postfiltering for enhanced vector search precision")
            else:
                # Default to preFilter for better recall
                search_params["vector_filter_mode"] = "preFilter"
        
        # Build and apply filters
        combined_filter = self._build_filters(search_query)
        if combined_filter:
            search_params["filter"] = combined_filter
            self.logger.debug(f"Applied filter: {combined_filter}")
        
        # Add score threshold if specified
        if search_query.min_score_threshold:
            search_params["minimum_coverage"] = search_query.min_score_threshold
        
        # Add custom parameters
        if search_query.custom_parameters:
            search_params.update(search_query.custom_parameters)
        
        return search_params
    
    def _preprocess_query(self, query: str) -> str:
        """
        Preprocess query to improve search relevance.
        
        This method applies query optimization techniques to match
        Azure OpenAI's "On Your Data" behavior as closely as possible.
        """
        if not query or len(query.strip()) == 0:
            return "*"
        
        # Clean and normalize query
        processed_query = query.strip()
        
        # Apply contextual query expansion to match Azure OpenAI's behavior
        # Azure OpenAI seems to automatically enrich queries for process-oriented searches
        query_lower = processed_query.lower()
        
        # Use the original query without any hardcoded modifications
        # The difference in results must come from other search parameters
        
        return processed_query
    
    def _map_azure_openai_query_type(self, azure_query_type: str) -> Optional[str]:
        """
        Map Azure OpenAI's internal query_type to public Azure Search API supported values.
        
        Azure OpenAI uses proprietary query types that aren't available in the public API.
        This method provides the best equivalent mapping.
        
        Args:
            azure_query_type: The query type from Azure OpenAI configuration
            
        Returns:
            Mapped query type supported by public API, or None if no good mapping exists
        """
        mapping = {
            # Azure OpenAI proprietary -> Public API equivalent
            "vector_semantic_hybrid": "semantic",  # Use semantic as closest equivalent
            "vector_simple_hybrid": "simple",      # Fallback to simple search
            "vectorSimpleHybrid": "simple",        # Alternative naming
            "vectorSemanticHybrid": "semantic",    # Alternative naming
            "semantic": "semantic",                # Direct mapping
            "simple": "simple",                    # Direct mapping
            "vector": None,                        # Vector search might not be configured
        }
        
        mapped = mapping.get(azure_query_type)
        return mapped
    
    def _determine_optimal_search_mode(self, search_query: SearchQuery) -> str:
        """
        Determine the optimal search mode based on query and configuration.

        Returns the best search mode (simple, semantic, vector) for the public Azure Search API.
        Note: Hybrid search is implemented via vector_queries parameter, not query_type.
        """
        # Explicit hybrid search - use semantic if available since we'll add vector_queries separately
        if hasattr(search_query, 'use_hybrid_search') and search_query.use_hybrid_search:
            if self.use_semantic_search and self.semantic_config:
                self.logger.debug("[HYBRID] Using semantic query_type with vector_queries for hybrid search")
                return "semantic"
            else:
                self.logger.debug("[HYBRID] Using simple query_type with vector_queries for hybrid search")
                return "simple"

        # Explicit semantic search control from query parameter
        if hasattr(search_query, 'use_semantic_search') and search_query.use_semantic_search is not None:
            if search_query.use_semantic_search is True:
                if self.semantic_config:
                    self.logger.debug("[2025-API] Using enhanced semantic search capabilities (parameter=true)")
                    return "semantic"
            elif search_query.use_semantic_search is False:
                # Explicitly disabled - use simple search even if global setting is enabled
                self.logger.debug("[2025-API] Semantic search explicitly disabled (parameter=false)")
                return "simple"

        # Global semantic search setting (only if parameter not provided or None)
        if self.use_semantic_search and self.semantic_config:
            self.logger.debug("[2025-API] Using enhanced semantic search capabilities (global setting)")
            return "semantic"

        # Pure vector search (rare case, usually we want hybrid)
        if hasattr(search_query, 'use_vector_search') and search_query.use_vector_search and not search_query.query:
            return "simple"  # No text query, just vector

        # Default to configured mode
        return self.query_type
    
    def _should_use_semantic_search(self, search_query: SearchQuery) -> bool:
        """Determine if semantic search should be used."""
        return (
            (search_query.use_semantic_search or self.use_semantic_search) and
            bool(self.semantic_config)
        )
    
    def _should_use_vector_search(self, search_query: SearchQuery) -> bool:
        """
        Determine if vector search should be used.

        Vector search is enabled when:
        1. Explicitly requested via search_query.use_vector_search, OR
        2. Hybrid search is requested, OR
        3. Vector columns are configured and Azure OpenAI embeddings are available
        """
        # Explicit vector search request
        if hasattr(search_query, 'use_vector_search') and search_query.use_vector_search:
            return bool(self.vector_columns)

        # Hybrid search request
        if hasattr(search_query, 'use_hybrid_search') and search_query.use_hybrid_search:
            return bool(self.vector_columns)

        # Auto-enable vector search if vector columns are configured and embeddings are available
        if self.vector_columns:
            # Check if we can generate embeddings
            if hasattr(app_settings, 'azure_openai') and app_settings.azure_openai:
                azure_openai = app_settings.azure_openai
                embedding_deployment = (
                    getattr(azure_openai, 'embedding_deployment', None) or
                    getattr(azure_openai, 'embedding_name', None) or
                    getattr(azure_openai, 'embedding_model', None)
                )
                return bool(embedding_deployment)

        return False
    
    def _build_filters(self, search_query: SearchQuery) -> Optional[str]:
        """
        Build combined OData filter from query filters and permissions.
        """
        filters = []
        
        # Add permission-based filter
        if search_query.user_permissions and self.permitted_groups_column:
            try:
                permission_filter = generateFilterStringFromFullDef(search_query.user_permissions)
                if permission_filter:
                    filters.append(f"({permission_filter})")
                    self.logger.debug(f"Added permission filter: {permission_filter}")
            except Exception as e:
                self.logger.warning(f"Failed to generate permission filter: {e}")
        
        # Add custom filters
        if search_query.filters:
            filters.append(f"({search_query.filters})")
        
        # Combine filters with AND logic
        return " and ".join(filters) if filters else None
    
    async def _process_search_results(
        self, 
        results, 
        search_query: SearchQuery
    ) -> List[SearchDocument]:
        """
        Process and optimize search results.
        
        This method applies post-processing techniques to improve result quality:
        - Score normalization and ranking
        - Content extraction and optimization
        - Metadata enrichment
        """
        documents = []
        
        async for result in results:
            try:
                # Extract content from configured columns
                content = self._extract_content(result)
                if not content:
                    continue  # Skip documents without content
                
                # Extract metadata fields
                title = self._extract_field(result, self.title_column)
                blob_url = self._extract_field(result, self.url_column)
                # Transform blob URL to Avanteam URL
                url = self._transform_blob_url_to_avanteam(blob_url)
                filename = self._extract_field(result, self.filename_column)
                
                # Get and normalize search score with hybrid support
                raw_score = result.get("@search.score", 0.0)
                reranker_score = result.get("@search.reranker_score")

                # Use reranker score for semantic search if available, otherwise use regular score
                final_score = reranker_score if reranker_score is not None else raw_score
                normalized_score = self._normalize_hybrid_score(final_score, raw_score, reranker_score, search_query)

                # DEBUG: Log score processing
                if len(documents) < 5:  # Only log first 5 to avoid spam
                    reranker_info = f", reranker={reranker_score:.6f}" if reranker_score is not None else ""
                    print(f"[SCORE DEBUG] Document {len(documents)+1}: raw={raw_score:.6f}{reranker_info}, normalized={normalized_score:.6f}, title={title[:30] if title else 'N/A'}...")

                # Store additional scoring metadata
                scoring_metadata = {
                    "raw_score": raw_score,
                    "reranker_score": reranker_score,
                    "final_score": final_score
                }

                # Extract Azure Search metadata fields
                azure_metadata = {
                    "id": result.get("id", ""),
                    "source": filename or "Document",
                    "search_highlights": result.get("@search.highlights", {}),
                    "created_date": result.get("metadata_creation_date"),
                    "modified_date": result.get("metadata_storage_last_modified"),
                    "file_size": result.get("metadata_storage_size"),
                    "security_rights": result.get("securityRights"),
                    **scoring_metadata
                }

                # Add custom fields if present
                if "fieldMetadata" in result:
                    azure_metadata["custom_fields"] = result["fieldMetadata"]

                # Create SearchDocument
                doc = SearchDocument(
                    content=content,
                    title=title,
                    url=url,
                    filename=filename,
                    score=normalized_score,
                    metadata=azure_metadata
                )
                
                documents.append(doc)
                
            except Exception as e:
                self.logger.warning(f"Error processing search result: {e}")
                continue
        
        # Apply post-processing optimizations
        optimized_documents = self._optimize_result_ranking(documents, search_query)
        
        optimization_count = len(documents) - len(optimized_documents)
        if optimization_count > 0:
            self.logger.info(f"[RANKING OPTIMIZATION] Applied diversity filtering, removed {optimization_count} similar documents")
        
        if optimized_documents:
            avg_score = sum(doc.score for doc in optimized_documents) / len(optimized_documents)
            self.logger.info(f"[QUALITY METRICS] Average relevance score: {avg_score:.3f}, Top result score: {optimized_documents[0].score:.3f}")
            
            # Detailed logging for quality comparison with Azure OpenAI
            print(f"[SEARCH QUALITY] ENHANCED System returned {len(optimized_documents)} documents:")
            for i, doc in enumerate(optimized_documents[:5]):  # Top 5 for readability
                print(f"  [{i+1}] Score: {doc.score:.3f}, Title: {doc.title[:60] if doc.title else 'N/A'}...")
                print(f"      Content preview: {doc.content[:100].replace(chr(10), ' ').replace(chr(13), ' ')}...")
            
            if len(optimized_documents) > 5:
                print(f"  ... and {len(optimized_documents) - 5} more documents")
        
        return optimized_documents
    
    def _extract_content(self, result: Dict[str, Any]) -> str:
        """Extract content from search result using configured columns."""
        for column in self.content_columns:
            if column in result:
                content = result[column]
                if isinstance(content, list):
                    return " ".join(str(item) for item in content)
                if content:
                    return str(content)
        
        # Fallback: find any text field that looks like content
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 50:
                return value
        
        return ""
    
    def _extract_field(self, result: Dict[str, Any], field_name: Optional[str]) -> Optional[str]:
        """Extract a specific field from search result."""
        if not field_name or field_name not in result:
            return None

        value = result[field_name]
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value) if value else None

    def _transform_blob_url_to_avanteam(self, blob_url: Optional[str]) -> Optional[str]:
        """
        Transform Azure Blob Storage URL to Avanteam PageLoader URL.

        Example:
        From: https://askmestorageprod.blob.core.windows.net/askme-navalgroup-poclighton-dev/bbafb8c8-6613-40ed-9a77-8927b34c6681/Avanteam%20Process%20Suite.pdf
        To: https://poc-ng-lighton.avanteam-online.com/GED/PageLoader.ashx?Open&IdDoc=bbafb8c8-6613-40ed-9a77-8927b34c6681&ext=1

        Args:
            blob_url: Azure Blob Storage URL

        Returns:
            Avanteam PageLoader URL or original URL if transformation fails
        """
        if not blob_url:
            return None

        # Check if Avanteam URL base is configured
        if not hasattr(app_settings, 'custom_avanteam_settings') or not app_settings.custom_avanteam_settings or not app_settings.custom_avanteam_settings.url_base:
            return blob_url  # Return original if not configured

        try:
            import re
            # Extract GUID from blob URL
            # Pattern: /container-name/GUID/filename
            guid_pattern = r'/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/'
            match = re.search(guid_pattern, blob_url, re.IGNORECASE)

            if match:
                guid = match.group(1)
                # Construct Avanteam URL
                base_url = app_settings.custom_avanteam_settings.url_base.rstrip('/')
                avanteam_url = f"{base_url}/PageLoader.ashx?Open&IdDoc={guid}&ext=1"
                return avanteam_url
            else:
                self.logger.warning(f"Could not extract GUID from blob URL: {blob_url}")
                return blob_url  # Return original if GUID not found

        except Exception as e:
            self.logger.warning(f"Error transforming blob URL to Avanteam URL: {e}")
            return blob_url  # Return original on error
    
    def _normalize_score(self, raw_score: float, search_query: SearchQuery) -> float:
        """
        Legacy score normalization method - kept for compatibility.
        Use _normalize_hybrid_score for better hybrid search support.
        """
        return self._normalize_hybrid_score(raw_score, raw_score, None, search_query)

    def _normalize_hybrid_score(
        self,
        final_score: float,
        raw_score: float,
        reranker_score: Optional[float],
        search_query: SearchQuery
    ) -> float:
        """
        Normalize search score for hybrid search (vector + semantic) with proper weighting.

        This method handles different score types from Azure Search:
        - Raw scores: from text search
        - Reranker scores: from semantic search (typically 0-4 range)
        - Vector scores: from vector similarity (normalized automatically by Azure)

        Args:
            final_score: The score to normalize (could be raw or reranker)
            raw_score: The original text search score
            reranker_score: The semantic reranker score if available
            search_query: The search query for context

        Returns:
            Normalized score in 0-1 range with proper hybrid weighting
        """
        # Use reranker score when available (semantic search)
        if reranker_score is not None:
            # Reranker scores are typically in 0-4 range, normalize to 0-1
            normalized_semantic = min(reranker_score / 4.0, 1.0)

            # If we have vector search too, apply hybrid weighting
            if self._should_use_vector_search(search_query) and self.vector_columns:
                # Hybrid scoring: 50% semantic, 30% vector (implicit in Azure), 20% text
                normalized_text = min(raw_score / 10.0, 1.0)  # Rough text normalization
                # Vector score is already included in Azure's hybrid calculation
                return (normalized_semantic * 0.7) + (normalized_text * 0.3)
            else:
                # Pure semantic search
                return normalized_semantic
        else:
            # Pure text or vector search
            if self._should_use_vector_search(search_query) and self.vector_columns:
                # Vector search scores are typically pre-normalized by Azure
                return min(final_score, 1.0)
            else:
                # Pure text search - apply log normalization for better distribution
                import math
                normalized = math.log(final_score + 1) / 10.0
                return min(normalized, 1.0)
    
    def _optimize_result_ranking(
        self, 
        documents: List[SearchDocument], 
        search_query: SearchQuery
    ) -> List[SearchDocument]:
        """
        Apply additional ranking optimizations to improve result quality.
        
        This method implements ranking improvements similar to those
        used in Azure OpenAI's "On Your Data" functionality.
        """
        if not documents:
            return documents
        
        # Apply boost factors if specified
        if search_query.boost_fields:
            documents = self._apply_field_boosting(documents, search_query.boost_fields)
        
        # Apply content quality scoring
        for doc in documents:
            quality_score = self._calculate_content_quality_score(doc)
            # Combine original score with quality score
            doc.score = (doc.score * 0.7) + (quality_score * 0.3)
        
        # Re-sort by optimized scores
        documents.sort(key=lambda x: x.score, reverse=True)
        
        # Apply diversity filtering to avoid too similar results
        documents = self._apply_diversity_filtering(documents)
        
        return documents
    
    def _apply_field_boosting(
        self, 
        documents: List[SearchDocument], 
        boost_fields: Dict[str, float]
    ) -> List[SearchDocument]:
        """Apply field-based boosting to improve relevance."""
        for doc in documents:
            boost_multiplier = 1.0
            
            # Check if document matches boost criteria
            if "title" in boost_fields and doc.title:
                # Title boost - can be enhanced with keyword matching
                boost_multiplier *= boost_fields["title"]
            
            if "content" in boost_fields and doc.content:
                # Content boost - can be enhanced with content analysis
                boost_multiplier *= boost_fields["content"]
            
            # Apply boost
            doc.score *= boost_multiplier
        
        return documents
    
    def _calculate_content_quality_score(self, doc: SearchDocument) -> float:
        """
        Calculate content quality score based on various factors.
        
        This helps prioritize higher-quality documents in results.
        """
        if not doc.content:
            return 0.0
        
        content_length = len(doc.content)
        quality_score = 0.0
        
        # Length quality (optimal range: 100-2000 characters)
        if 100 <= content_length <= 2000:
            quality_score += 0.3
        elif content_length > 50:
            quality_score += 0.1
        
        # Structure quality (presence of title, URL, etc.)
        if doc.title:
            quality_score += 0.2
        if doc.url:
            quality_score += 0.1
        if doc.filename:
            quality_score += 0.1
        
        # Content characteristics
        if doc.content.count('\n') > 2:  # Well-structured content
            quality_score += 0.1
        
        # Normalize to 0-1 range
        return min(quality_score, 1.0)
    
    def _apply_diversity_filtering(self, documents: List[SearchDocument]) -> List[SearchDocument]:
        """
        Apply diversity filtering to reduce redundant results.
        
        This helps ensure variety in search results.
        """
        if len(documents) <= 1:
            return documents
        
        filtered_docs = [documents[0]]  # Always include the top result
        
        for doc in documents[1:]:
            # Check similarity with already selected documents
            is_diverse = True
            for selected_doc in filtered_docs:
                if self._calculate_similarity(doc, selected_doc) > 0.8:
                    is_diverse = False
                    break
            
            if is_diverse:
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def _calculate_similarity(self, doc1: SearchDocument, doc2: SearchDocument) -> float:
        """
        Calculate similarity between two documents.
        
        Simple similarity calculation - can be enhanced with more sophisticated methods.
        """
        if not doc1.content or not doc2.content:
            return 0.0
        
        # Simple approach: check for common words
        words1 = set(doc1.content.lower().split())
        words2 = set(doc2.content.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    async def close(self) -> None:
        """Clean up Azure Search resources."""
        # No persistent connections to close in current implementation
        # Search clients are created per-request and closed immediately
        self.initialized = False
        self.logger.debug("Azure Search provider closed")
    
    def get_supported_features(self) -> List[str]:
        """Get list of features supported by Azure Search provider."""
        features = super().get_supported_features()
        features.extend([
            "semantic_search",
            "content_ranking",
            "score_normalization",
            "diversity_filtering",
            "field_boosting"
        ])
        
        if self.vector_columns:
            features.append("vector_search")
            features.append("hybrid_search")
        
        return features
    
    def validate_config(self) -> bool:
        """Validate Azure Search provider configuration."""
        if not self.service_name or not self.index_name:
            return False
        
        if not self.content_columns:
            return False
        
        return True
    
    def _build_vector_queries(self, search_query: SearchQuery) -> Optional[List[Dict[str, Any]]]:
        """
        Build vector queries for enhanced vector search (2025-08-01-preview).
        
        This method constructs vector queries using the latest API capabilities
        to improve vector search performance and precision.
        
        Args:
            search_query: The search query containing vector search parameters
            
        Returns:
            List of vector query configurations or None if vector search not applicable
        """
        if not self.vector_columns or not hasattr(search_query, 'vectors'):
            return None
            
        vector_queries = []
        
        # Build vector queries for each configured vector column
        for i, vector_column in enumerate(self.vector_columns):
            if hasattr(search_query, 'vectors') and i < len(search_query.vectors):
                vector_query = {
                    "kind": "vector",  # Required by Azure Search API 2025
                    "vector": search_query.vectors[i],
                    "fields": vector_column,
                    "k": search_query.top_k or self.default_top_k
                }
                
                # Apply vector-specific filters if available
                if hasattr(search_query, 'vector_filters') and search_query.vector_filters:
                    vector_query["filter"] = search_query.vector_filters.get(vector_column)
                
                # Set exhaustive search for better accuracy (if enabled)
                if hasattr(search_query, 'exhaustive_vector_search') and search_query.exhaustive_vector_search:
                    vector_query["exhaustive"] = True
                    self.logger.debug(f"[2025-API] Enabled exhaustive vector search for column: {vector_column}")
                
                vector_queries.append(vector_query)
                self.logger.debug(f"[2025-API] Built vector query for column: {vector_column}")
        
        return vector_queries if vector_queries else None
    
