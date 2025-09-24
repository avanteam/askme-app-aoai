"""
External API routes with OpenAPI/Swagger documentation.

Provides REST endpoints for external clients to search documents
using the configured search providers.
"""

import time
import logging
from datetime import datetime
from typing import List, Dict, Any

from quart import Blueprint, request, jsonify
from pydantic import ValidationError

from backend.api.models import (
    SearchRequest, SearchResponse, SearchResult, DocumentMetadata,
    HealthCheckResponse, CapabilitiesResponse, APIError,
    BatchSearchRequest, BatchSearchResponse
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
            "capabilities": f"{base_url}/api/v1/capabilities"
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


@api_v1.route('/search', methods=['POST'])
@rate_limit("60 per minute", "1000 per hour")  # Base rate limit, can be overridden per client
@require_api_key
async def search_documents():
    """
    Search through documents using the configured search provider.

    This endpoint allows external clients to search through indexed documents
    and retrieve relevant content with metadata. The search uses the same
    advanced search capabilities as the main chat application.

    Security:
    - Requires valid API key authentication
    - Rate limited per client
    - Request validation and sanitization
    - Comprehensive audit logging

    Returns:
    - 200: Successful search with results
    - 400: Invalid request parameters
    - 401: Authentication failed
    - 429: Rate limit exceeded
    - 500: Internal server error
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

        # Initialize search provider
        search_provider = await create_search_provider()
        if not search_provider:
            logger.error(f"No search provider available - RequestID: {request_id}")
            return jsonify(APIError(
                error_code='SEARCH_PROVIDER_UNAVAILABLE',
                error_message='Search service is temporarily unavailable',
                timestamp=datetime.utcnow(),
                request_id=request_id
            ).dict()), 503

        # Convert API request to internal search query
        search_query = SearchQuery(
            query=data.query,
            top_k=data.max_results,
            use_semantic_search=data.use_semantic_search,
            # Future: Add filters support
            # filters=data.filters
        )

        logger.info(
            f"Search request - Client: {client_name}, Query: '{data.query[:100]}...', "
            f"MaxResults: {data.max_results}, RequestID: {request_id}"
        )

        # Execute search
        search_documents = await search_provider.search(search_query)

        # Convert internal documents to API response format
        api_results = []
        for i, doc in enumerate(search_documents):
            metadata = None
            if data.include_metadata and doc.metadata:
                metadata = DocumentMetadata(
                    filename=doc.filename,
                    url=doc.url,
                    document_type=doc.metadata.get('document_type'),
                    language=doc.metadata.get('language'),
                    created_date=doc.metadata.get('created_date'),
                    modified_date=doc.metadata.get('modified_date'),
                    file_size=doc.metadata.get('file_size'),
                    custom_fields=doc.metadata.get('custom_fields')
                )

            api_result = SearchResult(
                content=doc.content,
                title=doc.title,
                score=doc.score,
                chunk_id=f"chunk_{i+1}_{request_id}",
                metadata=metadata
            )
            api_results.append(api_result)

        # Sort results if requested (other than relevance)
        if data.sort_by != "relevance":
            if data.sort_by == "title":
                api_results.sort(key=lambda x: x.title or "")
            elif data.sort_by == "date_desc":
                api_results.sort(
                    key=lambda x: x.metadata.modified_date if x.metadata and x.metadata.modified_date else datetime.min,
                    reverse=True
                )
            elif data.sort_by == "date_asc":
                api_results.sort(
                    key=lambda x: x.metadata.modified_date if x.metadata and x.metadata.modified_date else datetime.max
                )

        # Build response
        response_time_ms = (time.time() - start_time) * 1000
        response = SearchResponse(
            results=api_results,
            total_results=len(api_results),  # For now, same as returned results
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

    except ValidationError as e:
        logger.warning(
            f"Validation error - Client: {client_name}, Error: {str(e)}, RequestID: {request_id}"
        )
        return jsonify(APIError(
            error_code='VALIDATION_ERROR',
            error_message='Request validation failed',
            details={'validation_errors': e.errors()},
            timestamp=datetime.utcnow(),
            request_id=request_id
        ).dict()), 400

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
        # Get search provider capabilities
        supported_features = ["basic_search", "metadata_inclusion"]
        search_providers = []

        try:
            search_provider = await create_search_provider()
            if search_provider:
                supported_features.extend(search_provider.get_supported_features())
                search_providers.append(search_provider.__class__.__name__.lower())
        except Exception as e:
            logger.warning(f"Could not get search provider capabilities: {e}")

        response = CapabilitiesResponse(
            supported_features=list(set(supported_features)),  # Remove duplicates
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
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify(APIError(
        error_code='INTERNAL_ERROR',
        error_message='An internal server error occurred',
        timestamp=datetime.utcnow()
    ).dict()), 500


# Utility functions for route handlers
async def get_search_provider():
    """
    Get the configured search provider.

    Returns the initialized search provider or None if unavailable.
    This function handles the connection to the search backend.
    """
    try:
        # Use the create_search_provider factory function
        provider = await create_search_provider()
        return provider

    except Exception as e:
        logger.error(f"Failed to initialize search provider: {e}")
        return None


def format_search_error(error: Exception, request_id: str) -> Dict[str, Any]:
    """Format search provider errors for API response."""
    error_message = "Search operation failed"

    # Map common search provider errors
    if "connection" in str(error).lower():
        error_code = "SEARCH_CONNECTION_ERROR"
        error_message = "Could not connect to search service"
    elif "timeout" in str(error).lower():
        error_code = "SEARCH_TIMEOUT"
        error_message = "Search operation timed out"
    elif "quota" in str(error).lower() or "limit" in str(error).lower():
        error_code = "SEARCH_QUOTA_EXCEEDED"
        error_message = "Search service quota exceeded"
    else:
        error_code = "SEARCH_ERROR"

    return {
        'error_code': error_code,
        'error_message': error_message,
        'timestamp': datetime.utcnow().isoformat(),
        'request_id': request_id
    }