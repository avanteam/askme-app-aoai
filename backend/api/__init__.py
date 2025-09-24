"""
External API module for AskMe application.

This module provides REST API endpoints for external integrations,
allowing third-party applications to search through documents using
the configured search providers.

Features:
- Versioned API endpoints (/api/v1/)
- API Key authentication with IP whitelisting
- Rate limiting with adaptive policies
- Comprehensive audit logging
- OpenAPI/Swagger documentation
- Future-ready for OAuth2 and caching

Security:
- API Keys with rotation support
- IP-based access control
- Request sanitization
- Audit trails for compliance
"""