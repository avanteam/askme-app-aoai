"""
External API routes with OpenAPI/Swagger documentation.

Provides REST endpoints for external clients to search documents
using the configured search providers.
"""

import time
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any

from quart import Blueprint, request, jsonify
from pydantic import ValidationError

from backend.api.models import (
    SearchRequest, SearchResponse, SearchResult, DocumentMetadata,
    HealthCheckResponse, CapabilitiesResponse, APIError,
    BatchSearchRequest, BatchSearchResponse, AuthValidationResponse
)
from backend.api.auth import require_api_key, security_middleware
from backend.api.rate_limiter import rate_limit
from backend.search_providers import create_search_provider
from backend.search_providers.base import SearchQuery, SearchDocument
from backend.settings import app_settings


logger = logging.getLogger(__name__)

# Create blueprint for API v1
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')


@api_v1.route('/', methods=['GET'])
async def api_welcome():
    """
    API welcome endpoint with basic information.

    Provides links to documentation and API information.
    No authentication required.
    """
    base_url = request.url_root.rstrip('/')
    settings = app_settings.base_settings

    return jsonify({
        "message": "Welcome to AskMe External API",
        "version": settings.external_api_version,
        "documentation": {
            "swagger_ui": f"{base_url}/docs",
            "redoc_ui": f"{base_url}/redoc",
            "openapi_spec": f"{base_url}/openapi.json"
        },
        "endpoints": {
            "search": f"{base_url}/api/v1/search",
            "health": f"{base_url}/api/v1/health",
            "capabilities": f"{base_url}/api/v1/capabilities",
            "auth_validate": f"{base_url}/api/v1/auth/validate"
        },
        "authentication": {
            "type": "Bearer Token",
            "header": "Authorization: Bearer <api_key>",
            "note": "API key required for search endpoints"
        },
        "rate_limits": {
            "default_per_minute": settings.external_api_rate_limit_per_minute,
            "default_per_hour": settings.external_api_rate_limit_per_hour
        }
    })


# Test route removed - API is now production ready

@api_v1.route('/search', methods=['POST'])
@rate_limit("60 per minute", "1000 per hour")
@require_api_key
async def search_documents():
    """
    Search through documents using the configured search provider.

    This endpoint allows external clients to search through indexed documents
    and retrieve relevant content with metadata.
    """
    start_time = time.time()
    client_name = getattr(request, 'client_name', 'unknown')
    request_id = getattr(request, 'request_id', 'unknown')

    try:
        # Parse and validate JSON request
        json_data = await request.get_json()
        if not json_data:
            return jsonify(APIError(
                error_code='MISSING_REQUEST_DATA',
                error_message='Request body is required',
                timestamp=datetime.utcnow(),
                request_id=request_id
            ).dict()), 400

        try:
            data = SearchRequest(**json_data)
        except ValidationError as e:
            return jsonify(APIError(
                error_code='VALIDATION_ERROR',
                error_message='Request validation failed',
                details={'validation_errors': e.errors()},
                timestamp=datetime.utcnow(),
                request_id=request_id
            ).dict()), 400

        # Security validation
        request_data = data.dict()
        is_suspicious, reason = security_middleware.is_request_suspicious(request_data)
        if is_suspicious:
            logger.warning(
                f"Suspicious request blocked - Client: {client_name}, "
                f"Reason: {reason}, RequestID: {request_id}"
            )
            return jsonify(APIError(
                error_code='SUSPICIOUS_REQUEST',
                error_message=f'Request blocked for security: {reason}',
                timestamp=datetime.utcnow(),
                request_id=request_id
            ).dict()), 400

        # Try to use real search provider
        try:
            search_provider = await create_search_provider()

            # Build filters string from API filters
            filter_string = None
            if data.filters:
                filter_parts = []
                for key, value in data.filters.items():
                    # Sanitize filter key (allow only alphanumeric and underscore)
                    safe_key = ''.join(c for c in key if c.isalnum() or c == '_')

                    # Special handling for collection fields (like securityRights)
                    # These need search.in() function instead of eq operator
                    collection_fields = ['securityRights', 'securityrights']

                    if isinstance(value, list):
                        if safe_key in collection_fields:
                            # Use any() lambda for collection fields: field/any(r: r eq 'val1' or r eq 'val2')
                            escaped_values = [str(v).replace(chr(39), chr(39)+chr(39)) for v in value]
                            or_conditions = [f"r eq '{v}'" for v in escaped_values]
                            filter_parts.append(f"{safe_key}/any(r: {' or '.join(or_conditions)})")
                        else:
                            # Regular fields: (field eq 'value1' or field eq 'value2')
                            or_parts = [f"{safe_key} eq '{str(v).replace(chr(39), chr(39)+chr(39))}'" for v in value]
                            filter_parts.append(f"({' or '.join(or_parts)})")
                    else:
                        if safe_key in collection_fields:
                            # Single value for collection field: field/any(r: r eq 'value')
                            safe_value = str(value).replace(chr(39), chr(39)+chr(39))
                            filter_parts.append(f"{safe_key}/any(r: r eq '{safe_value}')")
                        else:
                            # Single value for regular field: field eq 'value'
                            safe_value = str(value).replace(chr(39), chr(39)+chr(39))
                            filter_parts.append(f"{safe_key} eq '{safe_value}'")
                filter_string = " and ".join(filter_parts) if filter_parts else None

            # Convert API request to internal search query
            search_query = SearchQuery(
                query=data.query,
                top_k=data.max_results,
                use_semantic_search=data.use_semantic_search,
                filters=filter_string,
            )

            # Safely truncate query for logging
            query_preview = data.query[:100] + '...' if len(data.query) > 100 else data.query
            logger.info(
                f"Search request - Client: {client_name}, Query: '{query_preview}', "
                f"MaxResults: {data.max_results}, RequestID: {request_id}"
            )

            # Execute search with timeout
            try:
                search_documents = await asyncio.wait_for(
                    search_provider.search(search_query),
                    timeout=app_settings.base_settings.external_api_request_timeout
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Search timeout - Client: {client_name}, RequestID: {request_id}"
                )
                return jsonify(APIError(
                    error_code='SEARCH_TIMEOUT',
                    error_message='Search operation timed out. Please try again with a more specific query.',
                    timestamp=datetime.utcnow(),
                    request_id=request_id
                ).dict()), 504

            # Convert internal documents to API response format
            api_results = []
            for i, doc in enumerate(search_documents):
                metadata = None
                if data.include_metadata and doc.metadata:
                    # Parse custom_fields if it's a JSON string
                    custom_fields_value = doc.metadata.get('custom_fields')
                    if isinstance(custom_fields_value, str) and custom_fields_value:
                        try:
                            custom_fields_value = json.loads(custom_fields_value)
                        except json.JSONDecodeError:
                            custom_fields_value = None

                    metadata = DocumentMetadata(
                        filename=doc.filename,
                        url=doc.url,
                        created_date=doc.metadata.get('created_date'),
                        modified_date=doc.metadata.get('modified_date'),
                        custom_fields=custom_fields_value,
                        security_rights=doc.metadata.get('security_rights')
                    )

                api_result = SearchResult(
                    content=doc.content,
                    title=doc.title,
                    score=doc.score,
                    chunk_id=f"chunk_{i+1}_{request_id}",
                    metadata=metadata
                )
                api_results.append(api_result)

            # Apply sorting if requested
            if data.sort_by != "relevance":
                api_results = sort_search_results(api_results, data.sort_by)

            # Build response
            response_time_ms = (time.time() - start_time) * 1000
            response = SearchResponse(
                results=api_results,
                total_results=len(api_results),
                query=data.query,
                response_time_ms=response_time_ms,
                search_provider=search_provider.__class__.__name__.lower(),
                api_version="v1"
            )

            logger.info(
                f"Search completed - Client: {client_name}, Results: {len(api_results)}, "
                f"Duration: {response_time_ms:.2f}ms, RequestID: {request_id}"
            )

            return jsonify(response.dict())

        except Exception as search_error:
            logger.error(
                f"Search provider error - Client: {client_name}, Error: {str(search_error)}, RequestID: {request_id}",
                exc_info=True
            )
            return jsonify(APIError(
                error_code='SEARCH_PROVIDER_UNAVAILABLE',
                error_message='Search service is temporarily unavailable',
                details={'error': str(search_error)},
                timestamp=datetime.utcnow(),
                request_id=request_id
            ).dict()), 503

    except Exception as e:
        logger.error(
            f"Search error - Client: {client_name}, Error: {str(e)}, RequestID: {request_id}",
            exc_info=True
        )
        return jsonify(APIError(
            error_code='INTERNAL_ERROR',
            error_message='An internal error occurred while processing the search',
            timestamp=datetime.utcnow(),
            request_id=request_id
        ).dict()), 500


@api_v1.route('/health', methods=['GET'])
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint to verify API and search provider status.

    This endpoint does not require authentication and can be used
    for monitoring and load balancer health checks.

    Returns:
    - 200: Service is healthy
    - 503: Service is unhealthy
    """
    try:
        start_time = time.time()

        # Check search provider health
        search_provider_status = {}
        try:
            search_provider = await create_search_provider()
            if search_provider:
                is_healthy = await search_provider.health_check()
                provider_name = search_provider.__class__.__name__.lower()
                search_provider_status[provider_name] = "healthy" if is_healthy else "unhealthy"
            else:
                search_provider_status['unknown'] = "unavailable"
        except Exception as e:
            logger.error(f"Health check error: {e}")
            search_provider_status['unknown'] = "error"

        # Determine overall status
        overall_status = "healthy"
        if any(status != "healthy" for status in search_provider_status.values()):
            overall_status = "degraded"

        response = HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version="1.0.0",
            search_provider_status=search_provider_status,
            uptime_seconds=time.time() - start_time  # Simplified for now
        )

        status_code = 200 if overall_status in ["healthy", "degraded"] else 503
        return jsonify(response.dict()), status_code

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        error_response = APIError(
            error_code='HEALTH_CHECK_FAILED',
            error_message='Health check could not be completed',
            timestamp=datetime.utcnow()
        )
        return jsonify(error_response.dict()), 503


@api_v1.route('/auth/validate', methods=['GET'])
@require_api_key
async def validate_auth() -> AuthValidationResponse:
    """
    Validate API key authentication.

    This endpoint allows clients to test their API key validity
    without performing actual operations. Useful for Swagger UI testing.

    Returns:
    - 200: Authentication successful with client details
    - 401: Authentication failed (handled by @require_api_key decorator)
    """
    client_name = getattr(request, 'client_name', 'unknown')
    request_id = getattr(request, 'request_id', 'unknown')

    response = AuthValidationResponse(
        status="authenticated",
        message="API key is valid",
        client_name=client_name,
        timestamp=datetime.utcnow().isoformat(),
        request_id=request_id
    )

    return jsonify(response.dict())


@api_v1.route('/capabilities', methods=['GET'])
async def get_capabilities() -> CapabilitiesResponse:
    """
    Get API capabilities and configuration information.

    This endpoint provides information about supported features,
    limits, and configuration to help clients use the API effectively.

    Returns:
    - 200: Capabilities information
    """
    try:
        # Features exposed via External API (user-controllable parameters)
        # These are the only features clients can directly control via API parameters
        supported_features = [
            "basic_search",              # Basic keyword search
            "semantic_search",           # Semantic/AI-powered search (use_semantic_search param)
            "filtered_search",           # OData filtering (filters param)
            "metadata_inclusion",        # Include document metadata (include_metadata param)
            "permission_filtering",      # Filter by security rights (via filters.securityRights)
        ]

        # Get available search providers
        search_providers = []
        try:
            search_provider = await create_search_provider()
            if search_provider:
                search_providers.append(search_provider.__class__.__name__.lower())
        except Exception as e:
            logger.warning(f"Could not get search provider capabilities: {e}")

        response = CapabilitiesResponse(
            supported_features=supported_features,
            max_results_limit=50,
            supported_sort_options=["relevance", "date_asc", "date_desc", "title"],
            rate_limits={
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "requests_per_day": 10000
            },
            search_providers=search_providers
        )

        return jsonify(response.dict())

    except Exception as e:
        logger.error(f"Capabilities endpoint error: {e}", exc_info=True)
        error_response = APIError(
            error_code='CAPABILITIES_ERROR',
            error_message='Could not retrieve API capabilities',
            timestamp=datetime.utcnow()
        )
        return jsonify(error_response.dict()), 500


@api_v1.route('/search/batch', methods=['POST'])
@rate_limit("10 per minute", "100 per hour")  # Lower limit for batch operations
@require_api_key
async def batch_search():
    """
    Execute multiple search queries in batch (Future feature).

    This endpoint allows clients to submit multiple search queries
    at once for more efficient processing.

    Note: This is a future feature and may have limited availability.

    Returns:
    - 200: Batch processing completed
    - 400: Invalid batch request
    - 401: Authentication failed
    - 429: Rate limit exceeded
    - 501: Feature not implemented
    """
    return jsonify(APIError(
        error_code='NOT_IMPLEMENTED',
        error_message='Batch search is not yet implemented',
        details={'planned_version': 'v1.1'},
        timestamp=datetime.utcnow()
    ).dict()), 501


# Error handlers for the API blueprint
@api_v1.errorhandler(ValidationError)
async def handle_validation_error(error):
    """Handle Pydantic validation errors."""
    return jsonify(APIError(
        error_code='VALIDATION_ERROR',
        error_message='Request validation failed',
        details={'validation_errors': error.errors()},
        timestamp=datetime.utcnow()
    ).dict()), 400


@api_v1.errorhandler(429)
async def handle_rate_limit_error(error):
    """Handle rate limit errors."""
    return jsonify(APIError(
        error_code='RATE_LIMIT_EXCEEDED',
        error_message='Too many requests. Please slow down.',
        details={'retry_after_seconds': getattr(error, 'retry_after', 60)},
        timestamp=datetime.utcnow()
    ).dict()), 429


@api_v1.errorhandler(500)
async def handle_internal_error(error):
    """Handle internal server errors."""
    logger.error(f"CRITICAL 500 ERROR: {error}", exc_info=True)
    print(f"CONSOLE 500 ERROR: {error}")  # Force console output
    print(f"CONSOLE ERROR TYPE: {type(error)}")
    return jsonify(APIError(
        error_code='INTERNAL_ERROR',
        error_message='An internal server error occurred',
        timestamp=datetime.utcnow()
    ).dict()), 500


# Utility functions for route handlers
def sort_search_results(results: List[SearchResult], sort_by: str) -> List[SearchResult]:
    """
    Sort search results based on the specified criteria.

    Args:
        results: List of SearchResult objects
        sort_by: Sort criteria ('relevance', 'date_asc', 'date_desc', 'title')

    Returns:
        Sorted list of SearchResult objects
    """
    if sort_by == "relevance":
        # Already sorted by score (default)
        return results
    elif sort_by == "date_desc":
        # Sort by modified_date descending (most recent first)
        return sorted(
            results,
            key=lambda x: x.metadata.modified_date if x.metadata and x.metadata.modified_date else "",
            reverse=True
        )
    elif sort_by == "date_asc":
        # Sort by modified_date ascending (oldest first)
        return sorted(
            results,
            key=lambda x: x.metadata.modified_date if x.metadata and x.metadata.modified_date else "",
            reverse=False
        )
    elif sort_by == "title":
        # Sort by title alphabetically
        return sorted(
            results,
            key=lambda x: x.title.lower() if x.title else "",
            reverse=False
        )
    else:
        # Unknown sort option, return as-is
        return results


# Utility functions removed - unused in current implementation
# The following functions were defined but never called:
# - get_search_provider(): Replaced by create_search_provider() factory
# - format_search_error(): Error formatting is done inline in route handlers