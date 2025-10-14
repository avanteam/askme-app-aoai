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

    Use this model to perform semantic searches across your document index.
    The API supports advanced filtering, sorting, and metadata retrieval.

    **Key Features:**
    - Semantic search with Azure Cognitive Search
    - Advanced filtering by document attributes
    - Multiple sorting options (relevance, date, title)
    - Optional metadata inclusion for rich results

    **Rate Limits:**
    - 60 requests per minute
    - 1000 requests per hour
    - 10000 requests per day
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Comment configurer l'authentification Azure AD?",
                "max_results": 10,
                "include_metadata": True,
                "sort_by": "relevance",
                "use_semantic_search": True,
                "filters": {
                    "securityRights": ["QDMAdmin", "QDMLecteur"]
                }
            }
        }
    )

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="**Search query string**. Natural language queries are supported. Examples: 'configuration Azure AD', 'guide installation Office 365'",
        example="Comment configurer l'authentification Azure AD?"
    )

    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="**Maximum number of results** to return. Limited to 50 for performance. Default: 10",
        example=10
    )

    include_metadata: bool = Field(
        default=True,
        description="**Include document metadata** in response (filename, URL, dates, security rights, etc.). Recommended: true",
        example=True
    )

    sort_by: SearchSortBy = Field(
        default=SearchSortBy.RELEVANCE,
        description="""**Sort order** for results:
        - `relevance`: By search score (default, best match first)
        - `date_desc`: By modification date (newest first)
        - `date_asc`: By modification date (oldest first)
        - `title`: Alphabetically by document title""",
        example="relevance"
    )

    filters: Optional[Dict[str, Union[str, List[str]]]] = Field(
        default=None,
        description="""**OData filters** to refine search results.

**Available filterable fields:**
- `securityRights` (Collection): Filter by access rights (e.g., `["QDMAdmin", "QDMLecteur"]`)
- `metadata_storage_name` (String): Filter by exact filename (e.g., `"guide.pdf"`)
- `metadata_storage_path` (String): Filter by full Azure Blob URL
- `title` (String): Filter by document title
- `titreDocument` (String): Filter by document title (French version)
- `parent_id` (String): Filter by parent document ID

**Examples:**
- Filter by filename: `{"metadata_storage_name": "guide.pdf"}`
- Filter by security rights (OR): `{"securityRights": ["QDMAdmin", "QDMLecteur"]}`
- Filter by title: `{"titreDocument": "Manuel Utilisateur"}`
- Combined filters (AND): `{"securityRights": ["QDMAdmin"], "metadata_storage_name": "guide.pdf"}`

**Note:** Multiple values in a list create OR conditions. Multiple keys create AND conditions.""",
        example={"securityRights": ["QDMAdmin", "QDMLecteur"]}
    )

    use_semantic_search: Optional[bool] = Field(
        default=None,
        description="""**Enable semantic search** for better relevance using AI understanding.

- `true`: Force semantic search ON (AI-powered relevance ranking)
- `false`: Force semantic search OFF (basic keyword search)
- `null` or omit: Use server configuration default (from AZURE_SEARCH_USE_SEMANTIC_SEARCH)

Recommended: `true` for natural language queries, `false` for exact keyword matching.""",
        example=True
    )

    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class DocumentMetadata(BaseModel):
    """
    Document metadata providing rich information about the search result.

    **Available Fields:**
    - File information: filename, url, file_size
    - Timestamps: created_date, modified_date
    - Access control: security_rights
    - Custom metadata: custom_fields (JSON string with business-specific data)

    All fields are optional and depend on the document's indexed metadata.
    """

    filename: Optional[str] = Field(
        None,
        description="**Original filename** of the document as stored in the system",
        example="Avanteam Process Suite.pdf"
    )

    url: Optional[str] = Field(
        None,
        description="**Direct access URL** to view/download the document. Uses Avanteam PageLoader format for secure access",
        example="https://poc-ng-lighton.avanteam-online.com/GED/PageLoader.ashx?Open&IdDoc=bbafb8c8-6613-40ed-9a77-8927b34c6681&ext=1"
    )

    created_date: Optional[datetime] = Field(
        None,
        description="**Document creation date** in ISO 8601 format (UTC)",
        example="2025-01-24T14:45:58Z"
    )

    modified_date: Optional[datetime] = Field(
        None,
        description="**Last modification date** in ISO 8601 format (UTC). Useful for sorting by recency",
        example="2025-10-07T09:42:50Z"
    )

    custom_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""**Custom business metadata** stored as JSON string. May contain fields like:
- Type: Document type classification
- Categorie: Business category
- Secteur d'application: Application area

Parse the JSON string to access individual fields.""",
        example={"Type": "DOCUMENT TEST", "Categorie": "CATEGORIE TEST", "Secteur d'application": "Produits"}
    )

    security_rights: Optional[List[str]] = Field(
        default=None,
        description="""**Access rights/permissions** required to view this document.

Users must have at least one of these rights to access the document.
Common values: QDMAdmin, QDMLecteur, etc.

Use this field to implement client-side access control.""",
        example=["QDMAdmin", "QDMLecteur"]
    )


class SearchResult(BaseModel):
    """
    Individual search result representing a relevant document chunk.

    Each result contains:
    - The matched content excerpt
    - Relevance score (0.0-1.0)
    - Optional metadata with file info, dates, and access rights

    Results are ordered by relevance (or custom sort order).
    """

    content: str = Field(
        ...,
        description="""**Content excerpt** from the matched document.

This is the actual text content that matched your search query.
Typically a paragraph or section from the source document.""",
        example="Pour configurer l'authentification Azure AD, vous devez d'abord créer une application dans le portail Azure. Accédez à Azure Active Directory > Inscriptions d'applications > Nouvelle inscription..."
    )

    title: Optional[str] = Field(
        None,
        description="**Document title** or filename. Useful for displaying result headers",
        example="Avanteam Process Suite.pdf"
    )

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="""**Relevance score** from 0.0 (low) to 1.0 (perfect match).

Higher scores indicate better relevance to your query.
Scores above 0.7 are typically excellent matches.
Scores below 0.3 may be tangentially related.""",
        example=0.85
    )

    chunk_id: str = Field(
        ...,
        description="**Unique identifier** for this content chunk. Format: `chunk_{number}_{request_id}`",
        example="chunk_1_req_1759842804_9583"
    )

    metadata: Optional[DocumentMetadata] = Field(
        None,
        description="""**Document metadata** containing file info, dates, and access rights.

Only included when `include_metadata=true` in the request.
Provides rich information for displaying results and implementing access control."""
    )


class SearchResponse(BaseModel):
    """
    Complete search response containing results and metadata.

    **Response Structure:**
    - `results`: Array of matching documents
    - `total_results`: Number of results returned
    - `query`: Your original query (for confirmation)
    - `response_time_ms`: Query execution time
    - `search_provider`: Backend search engine used
    - `api_version`: API version (currently v1)

    **Success Response:** HTTP 200 with this model
    **Error Responses:** HTTP 4xx/5xx with APIError model
    """

    results: List[SearchResult] = Field(
        ...,
        description="""**Array of search results** ordered by relevance (or custom sort).

Empty array if no matches found.
Maximum length: 50 (as specified by max_results)"""
    )

    total_results: int = Field(
        ...,
        ge=0,
        description="""**Number of results returned** in this response.

This is the count of results actually returned (length of results array), not the total number of
matching documents in the index. The value will be at most equal to max_results from your request.""",
        example=10
    )

    query: str = Field(
        ...,
        description="**Original search query** echoed back for verification",
        example="Comment configurer l'authentification Azure AD?"
    )

    response_time_ms: float = Field(
        ...,
        ge=0,
        description="""**Query execution time** in milliseconds.

Typical response times:
- Simple queries: 100-300ms
- Complex queries with filters: 300-800ms
- Semantic search: 400-1000ms""",
        example=245.67
    )

    search_provider: str = Field(
        ...,
        description="**Search backend** used to execute the query. Currently: `azuresearchprovider`",
        example="azuresearchprovider"
    )

    api_version: str = Field(
        default="v1",
        description="**API version** used for this request. Current stable version: `v1`",
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
    """
    Standard API error response for all error conditions.

    **Common Error Codes:**
    - `VALIDATION_ERROR`: Invalid request parameters
    - `AUTHENTICATION_FAILED`: Missing or invalid API key
    - `RATE_LIMIT_EXCEEDED`: Too many requests
    - `SEARCH_PROVIDER_UNAVAILABLE`: Search backend unavailable
    - `INTERNAL_ERROR`: Server error

    **HTTP Status Codes:**
    - 400: Validation errors
    - 401: Authentication failures
    - 429: Rate limit exceeded
    - 503: Service unavailable
    - 500: Internal server error
    """

    error_code: str = Field(
        ...,
        description="**Machine-readable error code** for programmatic error handling",
        example="VALIDATION_ERROR"
    )

    error_message: str = Field(
        ...,
        description="**Human-readable error message** explaining what went wrong",
        example="Request validation failed: query field is required"
    )

    details: Optional[Dict[str, Any]] = Field(
        None,
        description="**Additional context** about the error (validation errors, affected fields, etc.)",
        example={"validation_errors": [{"field": "query", "message": "Field required"}]}
    )

    timestamp: datetime = Field(
        ...,
        description="**Error timestamp** in ISO 8601 format (UTC)",
        example="2025-10-07T14:30:00Z"
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