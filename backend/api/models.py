"""
Pydantic models for External API with OpenAPI documentation.

These models define the request/response schemas for the external API
and automatically generate OpenAPI/Swagger documentation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator
from pydantic.config import ConfigDict


class SearchSortBy(str, Enum):
    """Available sorting options for search results."""
    RELEVANCE = "relevance"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"
    TITLE = "title"


class SearchRequest(BaseModel):
    """
    Search request model with comprehensive parameters.

    This model validates incoming search requests and provides
    OpenAPI documentation for API consumers.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "Comment configurer l'authentification Azure AD?",
                    "max_results": 10,
                    "include_metadata": True,
                    "sort_by": "relevance"
                },
                {
                    "query": "Guide installation Office 365 entreprise",
                    "max_results": 5,
                    "include_metadata": False,
                    "sort_by": "date_desc",
                    "use_semantic_search": False
                }
            ]
        }
    )

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query string",
        example="Comment configurer l'authentification Azure AD?"
    )

    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return (1-50)",
        example=10
    )

    include_metadata: bool = Field(
        default=True,
        description="Include document metadata in response",
        example=True
    )

    sort_by: SearchSortBy = Field(
        default=SearchSortBy.RELEVANCE,
        description="Sort results by specified criteria",
        example="relevance"
    )

    filters: Optional[Dict[str, Union[str, List[str]]]] = Field(
        default=None,
        description="Optional filters to apply (future feature)",
        example={"document_type": "pdf", "language": "fr"}
    )

    use_semantic_search: bool = Field(
        default=True,
        description="Use semantic search capabilities if available",
        example=True
    )

    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class DocumentMetadata(BaseModel):
    """Document metadata model."""

    filename: Optional[str] = Field(
        None,
        description="Original filename of the document",
        example="azure_ad_guide.pdf"
    )

    url: Optional[str] = Field(
        None,
        description="URL or link to the original document",
        example="https://docs.microsoft.com/azure-ad"
    )

    document_type: Optional[str] = Field(
        None,
        description="Type/format of the document",
        example="pdf"
    )

    language: Optional[str] = Field(
        None,
        description="Detected language of the content",
        example="fr"
    )

    created_date: Optional[datetime] = Field(
        None,
        description="Document creation date",
        example="2024-01-15T10:30:00Z"
    )

    modified_date: Optional[datetime] = Field(
        None,
        description="Document last modification date",
        example="2024-03-20T14:45:00Z"
    )

    file_size: Optional[int] = Field(
        None,
        description="File size in bytes",
        example=2048576
    )

    custom_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional custom metadata fields",
        example={"department": "IT", "classification": "internal"}
    )


class SearchResult(BaseModel):
    """Individual search result model."""

    content: str = Field(
        ...,
        description="Relevant content excerpt from the document",
        example="Pour configurer l'authentification Azure AD, vous devez d'abord créer une application dans le portail Azure..."
    )

    title: Optional[str] = Field(
        None,
        description="Document or section title",
        example="Configuration de l'authentification Azure AD"
    )

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0 to 1.0, higher is more relevant)",
        example=0.85
    )

    chunk_id: str = Field(
        ...,
        description="Unique identifier for this content chunk",
        example="doc_123_chunk_5"
    )

    metadata: Optional[DocumentMetadata] = Field(
        None,
        description="Document metadata (included if include_metadata=true)"
    )


class SearchResponse(BaseModel):
    """Complete search response model."""

    results: List[SearchResult] = Field(
        ...,
        description="List of search results ordered by relevance"
    )

    total_results: int = Field(
        ...,
        ge=0,
        description="Total number of results found",
        example=156
    )

    query: str = Field(
        ...,
        description="Original search query",
        example="Comment configurer l'authentification Azure AD?"
    )

    response_time_ms: float = Field(
        ...,
        ge=0,
        description="Response time in milliseconds",
        example=245.67
    )

    search_provider: str = Field(
        ...,
        description="Search provider used for this query",
        example="azure_search"
    )

    api_version: str = Field(
        default="v1",
        description="API version used",
        example="v1"
    )


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: str = Field(
        ...,
        description="Overall API status",
        example="healthy"
    )

    timestamp: datetime = Field(
        ...,
        description="Health check timestamp",
        example="2024-01-15T10:30:00Z"
    )

    version: str = Field(
        ...,
        description="API version",
        example="1.0.0"
    )

    search_provider_status: Dict[str, str] = Field(
        ...,
        description="Status of each search provider",
        example={"azure_search": "healthy", "elasticsearch": "unavailable"}
    )

    uptime_seconds: float = Field(
        ...,
        ge=0,
        description="API uptime in seconds",
        example=86400.5
    )


class CapabilitiesResponse(BaseModel):
    """API capabilities response model."""

    supported_features: List[str] = Field(
        ...,
        description="List of supported API features",
        example=["basic_search", "semantic_search", "metadata_filtering"]
    )

    max_results_limit: int = Field(
        ...,
        description="Maximum number of results per request",
        example=50
    )

    supported_sort_options: List[str] = Field(
        ...,
        description="Available sorting options",
        example=["relevance", "date_asc", "date_desc", "title"]
    )

    rate_limits: Dict[str, int] = Field(
        ...,
        description="Rate limiting information",
        example={"requests_per_minute": 60, "requests_per_hour": 1000}
    )

    search_providers: List[str] = Field(
        ...,
        description="Available search providers",
        example=["azure_search", "elasticsearch"]
    )


class AuthValidationResponse(BaseModel):
    """Authentication validation response model."""

    status: str = Field(
        ...,
        description="Authentication status",
        example="authenticated"
    )

    message: str = Field(
        ...,
        description="Human-readable status message",
        example="API key is valid"
    )

    client_name: str = Field(
        ...,
        description="Authenticated client name",
        example="lighton"
    )

    timestamp: str = Field(
        ...,
        description="Validation timestamp",
        example="2025-01-25T10:30:00.000Z"
    )

    request_id: str = Field(
        ...,
        description="Unique request identifier",
        example="req_1758815923_9134"
    )


class APIError(BaseModel):
    """Standard API error response model."""

    error_code: str = Field(
        ...,
        description="Machine-readable error code",
        example="INVALID_QUERY"
    )

    error_message: str = Field(
        ...,
        description="Human-readable error message",
        example="The search query is invalid or too short"
    )

    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details",
        example={"field": "query", "constraint": "min_length"}
    )

    timestamp: datetime = Field(
        ...,
        description="Error timestamp",
        example="2024-01-15T10:30:00Z"
    )

    request_id: Optional[str] = Field(
        None,
        description="Unique request identifier for debugging",
        example="req_123456789"
    )


class BatchSearchRequest(BaseModel):
    """Batch search request model (future feature)."""

    queries: List[SearchRequest] = Field(
        ...,
        min_items=1,
        max_items=10,
        description="List of search requests to process"
    )

    batch_id: Optional[str] = Field(
        None,
        description="Optional batch identifier",
        example="batch_20240115_001"
    )


class BatchSearchResponse(BaseModel):
    """Batch search response model (future feature)."""

    results: List[SearchResponse] = Field(
        ...,
        description="List of search responses corresponding to input queries"
    )

    batch_id: Optional[str] = Field(
        None,
        description="Batch identifier if provided",
        example="batch_20240115_001"
    )

    total_processing_time_ms: float = Field(
        ...,
        ge=0,
        description="Total batch processing time in milliseconds",
        example=1234.56
    )