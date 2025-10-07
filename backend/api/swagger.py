"""
OpenAPI/Swagger documentation generation and serving.

Provides OpenAPI JSON schema and Swagger UI interface for the External API.
"""

import json
from typing import Dict, Any
from quart import Blueprint, jsonify, request, Response

from backend.api.models import (
    SearchRequest, SearchResponse, HealthCheckResponse,
    CapabilitiesResponse, APIError, BatchSearchRequest, BatchSearchResponse
)
from backend.settings import app_settings

# Create blueprint for documentation endpoints
docs_bp = Blueprint('api_docs', __name__)


def generate_openapi_spec() -> Dict[str, Any]:
    """Generate OpenAPI 3.0 specification for the External API."""

    settings = app_settings.base_settings

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": settings.external_api_title,
            "description": settings.external_api_description,
            "version": settings.external_api_version,
            "contact": {
                "name": "AskMe API Support",
                "url": "https://github.com/avanteam/askme-app-aoai"
            },
            "license": {
                "name": "Proprietary",
                "url": "https://avanteam.fr"
            }
        },
        "servers": [
            {
                "url": "/api/v1",
                "description": "External API v1"
            }
        ],
        "paths": {
            "/search": {
                "post": {
                    "summary": "Search documents",
                    "description": """**Perform semantic search** across your document index.

**Features:**
- Natural language query support
- Semantic search for better relevance
- Advanced filtering by metadata fields
- Multiple sorting options (relevance, date, title)
- Rich metadata including security rights and custom fields

**Authentication:**
Required - Use Bearer token with your API key

**Rate Limits:**
- 60 requests/minute
- 1000 requests/hour
- 10000 requests/day

**Best Practices:**
1. Use `include_metadata=true` to get file URLs and access rights
2. Filter by `securityRights` to implement access control
3. Sort by `date_desc` for recent documents
4. Keep queries concise and specific for best results""",
                    "operationId": "searchDocuments",
                    "tags": ["Search"],
                    "security": [{"ApiKeyAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SearchRequest"},
                                "examples": {
                                    "basic_search": {
                                        "summary": "Basic search example",
                                        "value": {
                                            "query": "Comment configurer Azure AD?",
                                            "max_results": 10,
                                            "include_metadata": True
                                        }
                                    },
                                    "advanced_search": {
                                        "summary": "Advanced search with filters",
                                        "value": {
                                            "query": "Configuration authentification SSO Azure Active Directory",
                                            "max_results": 20,
                                            "include_metadata": True,
                                            "sort_by": "date_desc",
                                            "use_semantic_search": True,
                                            "filters": {
                                                "securityRights": ["QDMAdmin", "QDMLecteur"]
                                            }
                                        }
                                    },
                                    "filtered_search": {
                                        "summary": "Search with security filter",
                                        "value": {
                                            "query": "guide installation",
                                            "max_results": 10,
                                            "include_metadata": True,
                                            "filters": {
                                                "securityRights": ["QDMAdmin"]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful search response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SearchResponse"},
                                    "examples": {
                                        "search_results": {
                                            "summary": "Example search results",
                                            "value": {
                                                "results": [
                                                    {
                                                        "content": "Pour configurer Azure AD...",
                                                        "title": "Guide Azure AD",
                                                        "score": 0.95,
                                                        "chunk_id": "chunk_1_req_123",
                                                        "metadata": {
                                                            "filename": "azure_guide.pdf",
                                                            "url": "https://docs.microsoft.com/azure-ad"
                                                        }
                                                    }
                                                ],
                                                "total_results": 156,
                                                "query": "Comment configurer Azure AD?",
                                                "response_time_ms": 245.67,
                                                "search_provider": "azuresearchprovider",
                                                "api_version": "v1"
                                            }
                                        }
                                    }
                                }
                            },
                            "headers": {
                                "X-RateLimit-Limit": {
                                    "description": "Rate limit per window",
                                    "schema": {"type": "integer"}
                                },
                                "X-RateLimit-Remaining": {
                                    "description": "Remaining requests in current window",
                                    "schema": {"type": "integer"}
                                },
                                "X-RateLimit-Reset": {
                                    "description": "Unix timestamp when rate limit resets",
                                    "schema": {"type": "integer"}
                                }
                            }
                        },
                        "400": {
                            "description": "Bad request - invalid parameters",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/APIError"}
                                }
                            }
                        },
                        "401": {
                            "description": "Unauthorized - invalid or missing API key",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/APIError"}
                                }
                            }
                        },
                        "429": {
                            "description": "Too many requests - rate limit exceeded",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/APIError"}
                                }
                            }
                        },
                        "503": {
                            "description": "Service unavailable - search provider error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/APIError"}
                                }
                            }
                        }
                    }
                }
            },
            "/health": {
                "get": {
                    "summary": "Health check",
                    "description": "Check API and search provider health status",
                    "operationId": "healthCheck",
                    "tags": ["Monitoring"],
                    "responses": {
                        "200": {
                            "description": "Health status",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/HealthCheckResponse"}
                                }
                            }
                        },
                        "503": {
                            "description": "Service unhealthy",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/APIError"}
                                }
                            }
                        }
                    }
                }
            },
            "/capabilities": {
                "get": {
                    "summary": "Get API capabilities",
                    "description": "Retrieve information about supported features and limits",
                    "operationId": "getCapabilities",
                    "tags": ["Monitoring"],
                    "responses": {
                        "200": {
                            "description": "API capabilities",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/CapabilitiesResponse"}
                                }
                            }
                        }
                    }
                }
            },
            "/search/batch": {
                "post": {
                    "summary": "Batch search (Future feature)",
                    "description": "Execute multiple search queries in a single request",
                    "operationId": "batchSearch",
                    "tags": ["Search"],
                    "security": [{"ApiKeyAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/BatchSearchRequest"}
                            }
                        }
                    },
                    "responses": {
                        "501": {
                            "description": "Not implemented yet",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/APIError"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "API Key",
                    "description": "API Key authentication. Format: `Bearer sk-ext-client-xxxxx`"
                }
            },
            "schemas": _generate_schemas()
        },
        "tags": [
            {
                "name": "Search",
                "description": "Document search operations"
            },
            {
                "name": "Monitoring",
                "description": "Health checks and API information"
            }
        ]
    }

    return spec


def _generate_schemas() -> Dict[str, Any]:
    """Generate OpenAPI schemas from Pydantic models."""

    try:
        # Get schemas from Pydantic models with safe handling
        schemas = {}
        all_defs = {}  # Collect all $defs from all models

        # Basic schemas
        models = {
            "SearchRequest": SearchRequest,
            "SearchResponse": SearchResponse,
            "HealthCheckResponse": HealthCheckResponse,
            "CapabilitiesResponse": CapabilitiesResponse,
            "APIError": APIError,
            "BatchSearchRequest": BatchSearchRequest,
            "BatchSearchResponse": BatchSearchResponse
        }

        # First pass: collect all schemas and their $defs
        for schema_name, model_class in models.items():
            try:
                schema = model_class.model_json_schema()
                schemas[schema_name] = schema

                # Collect $defs from this schema
                if '$defs' in schema:
                    all_defs.update(schema['$defs'])

            except Exception as e:
                # Fallback to basic schema
                schemas[schema_name] = {
                    "type": "object",
                    "description": f"Schema for {schema_name} (generation failed: {e})"
                }

        # Second pass: add all collected $defs to schemas and update references
        for def_name, def_schema in all_defs.items():
            schemas[def_name] = def_schema

        # Third pass: clean up schemas and update references
        for schema_name, schema in schemas.items():
            if isinstance(schema, dict):
                # Remove $defs from individual schemas since we moved them to top level
                if '$defs' in schema:
                    del schema['$defs']

                # Update references recursively
                updated_schema = _update_refs_recursive(schema)
                schemas[schema_name] = updated_schema

        return schemas

    except Exception as e:
        # Emergency fallback with comprehensive schemas
        return {
            "SearchSortBy": {
                "type": "string",
                "enum": ["relevance", "date_asc", "date_desc", "title"],
                "description": "Sort options for search results"
            },
            "DocumentMetadata": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "nullable": True},
                    "url": {"type": "string", "nullable": True},
                    "created_date": {"type": "string", "format": "date-time", "nullable": True},
                    "modified_date": {"type": "string", "format": "date-time", "nullable": True},
                    "custom_fields": {"type": "object", "nullable": True},
                    "security_rights": {"type": "array", "items": {"type": "string"}, "nullable": True}
                }
            },
            "SearchResult": {
                "type": "object",
                "required": ["content", "score", "chunk_id"],
                "properties": {
                    "content": {"type": "string", "description": "Document content excerpt"},
                    "title": {"type": "string", "nullable": True, "description": "Document title"},
                    "score": {"type": "number", "minimum": 0, "maximum": 1, "description": "Relevance score"},
                    "chunk_id": {"type": "string", "description": "Unique chunk identifier"},
                    "metadata": {"$ref": "#/components/schemas/DocumentMetadata"}
                }
            },
            "SearchRequest": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 1000, "description": "Search query"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                    "include_metadata": {"type": "boolean", "default": True},
                    "sort_by": {"$ref": "#/components/schemas/SearchSortBy"},
                    "use_semantic_search": {"type": "boolean", "default": True},
                    "filters": {"type": "object", "nullable": True}
                }
            },
            "SearchResponse": {
                "type": "object",
                "required": ["results", "total_results", "query", "response_time_ms", "search_provider", "api_version"],
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/SearchResult"}
                    },
                    "total_results": {"type": "integer", "minimum": 0},
                    "query": {"type": "string"},
                    "response_time_ms": {"type": "number", "minimum": 0},
                    "search_provider": {"type": "string"},
                    "api_version": {"type": "string"}
                }
            },
            "HealthCheckResponse": {
                "type": "object",
                "required": ["status", "timestamp", "version"],
                "properties": {
                    "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "version": {"type": "string"},
                    "search_provider_status": {"type": "object"},
                    "uptime_seconds": {"type": "number", "minimum": 0}
                }
            },
            "CapabilitiesResponse": {
                "type": "object",
                "required": ["supported_features", "max_results_limit", "rate_limits"],
                "properties": {
                    "supported_features": {"type": "array", "items": {"type": "string"}},
                    "max_results_limit": {"type": "integer"},
                    "supported_sort_options": {"type": "array", "items": {"type": "string"}},
                    "rate_limits": {"type": "object"},
                    "search_providers": {"type": "array", "items": {"type": "string"}}
                }
            },
            "APIError": {
                "type": "object",
                "required": ["error_code", "error_message", "timestamp"],
                "properties": {
                    "error_code": {"type": "string"},
                    "error_message": {"type": "string"},
                    "details": {"type": "object", "nullable": True},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "request_id": {"type": "string", "nullable": True}
                }
            },
            "BatchSearchRequest": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/SearchRequest"}
                    }
                }
            },
            "BatchSearchResponse": {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/SearchResponse"}
                    }
                }
            }
        }


def _update_refs_recursive(obj):
    """Recursively update $ref paths in a schema object and fix oneOf/anyOf for nullable types."""
    if isinstance(obj, dict):
        result = {}

        # Fix oneOf/anyOf patterns for nullable types
        # Pydantic v2 generates: {"anyOf": [{"type": "string"}, {"type": "null"}]}
        # OpenAPI 3.0 prefers: {"type": "string", "nullable": true}
        if 'anyOf' in obj or 'oneOf' in obj:
            variants_key = 'anyOf' if 'anyOf' in obj else 'oneOf'
            variants = obj[variants_key]

            # Check if this is a simple nullable pattern
            if len(variants) == 2:
                type_schema = None
                has_null = False

                for variant in variants:
                    if isinstance(variant, dict):
                        if variant.get('type') == 'null':
                            has_null = True
                        else:
                            type_schema = variant

                # If it's a simple nullable type, convert it
                if has_null and type_schema:
                    result = _update_refs_recursive(type_schema)
                    result['nullable'] = True
                    return result

            # Otherwise keep the anyOf/oneOf structure
            result[variants_key] = [_update_refs_recursive(v) for v in variants]

        for key, value in obj.items():
            if key in ('anyOf', 'oneOf'):
                # Already handled above
                continue
            elif key == '$ref' and isinstance(value, str):
                # Update reference from #/$defs/... to #/components/schemas/...
                if value.startswith('#/$defs/'):
                    result[key] = value.replace('#/$defs/', '#/components/schemas/')
                else:
                    result[key] = value
            else:
                result[key] = _update_refs_recursive(value)
        return result
    elif isinstance(obj, list):
        return [_update_refs_recursive(item) for item in obj]
    else:
        return obj


@docs_bp.route('/openapi.json', methods=['GET'])
async def openapi_json():
    """Serve OpenAPI specification as JSON."""
    spec = generate_openapi_spec()
    return jsonify(spec)


@docs_bp.route('/docs', methods=['GET'])
async def swagger_ui():
    """Serve Swagger UI interface."""

    settings = app_settings.base_settings

    if not settings.external_api_swagger_enabled:
        return jsonify({
            "error": "Swagger UI is disabled",
            "message": "Set EXTERNAL_API_SWAGGER_ENABLED=true to enable"
        }), 404

    # Get the base URL for the OpenAPI spec
    base_url = request.url_root.rstrip('/')
    openapi_url = f"{base_url}/openapi.json"
    api_title = settings.external_api_title

    swagger_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{api_title} - Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css" />
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        *, *:before, *:after {{
            box-sizing: inherit;
        }}
        body {{
            margin: 0;
            background: #fafafa;
        }}
        .swagger-ui .topbar {{
            background-color: #2c5aa0;
        }}
        .swagger-ui .topbar .download-url-wrapper {{
            display: none;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            const ui = SwaggerUIBundle({{
                url: '{openapi_url}',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                tryItOutEnabled: true,
                requestInterceptor: function(request) {{
                    console.log('Request:', request);
                    return request;
                }},
                responseInterceptor: function(response) {{
                    console.log('Response:', response);
                    return response;
                }}
            }});
        }}
    </script>
</body>
</html>"""

    return Response(swagger_html, content_type='text/html')


@docs_bp.route('/redoc', methods=['GET'])
async def redoc_ui():
    """Serve ReDoc UI interface (alternative to Swagger UI)."""

    settings = app_settings.base_settings

    if not settings.external_api_swagger_enabled:
        return jsonify({
            "error": "Documentation UI is disabled",
            "message": "Set EXTERNAL_API_SWAGGER_ENABLED=true to enable"
        }), 404

    # Get the base URL for the OpenAPI spec
    base_url = request.url_root.rstrip('/')
    openapi_url = f"{base_url}/openapi.json"
    api_title = settings.external_api_title

    redoc_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{api_title} - Documentation</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <redoc spec-url="{openapi_url}"></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
</body>
</html>"""

    return Response(redoc_html, content_type='text/html')