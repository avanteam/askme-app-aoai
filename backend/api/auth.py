"""
Authentication and security for External API.

Provides API Key authentication with IP whitelisting and rate limiting.
Designed for future extension with JWT/OAuth2 support.
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from functools import wraps
from collections import defaultdict

from quart import request, jsonify, current_app

from backend.settings import app_settings


logger = logging.getLogger(__name__)


class APIKeyManager:
    """
    Manages API keys with rotation support and metadata tracking.

    Features:
    - Secure API key generation and validation
    - Key rotation with grace periods
    - IP whitelisting per key
    - Usage tracking and analytics
    - Audit logging for security compliance
    """

    def __init__(self):
        self.api_keys: Dict[str, Dict] = {}
        self._load_api_keys()

    def _load_api_keys(self):
        """Load API keys from environment configuration."""
        # V1: Load from environment variables
        # V2: Will load from database/Redis for dynamic management

        if app_settings.base_settings is None:
            logger.warning("Base settings not initialized - cannot load API keys")
            return

        raw_keys = getattr(app_settings.base_settings, 'external_api_keys', '') or ''
        raw_keys = raw_keys.strip()
        if not raw_keys:
            logger.warning("No external API keys configured")
            return

        try:
            # Format: "client1:key1:ip1,ip2|client2:key2:*"
            for key_config in raw_keys.split('|'):
                if not key_config.strip():
                    continue

                parts = key_config.split(':')
                if len(parts) < 2:
                    logger.error(f"Invalid API key config format: {key_config}")
                    continue

                client_name = parts[0].strip()
                api_key = parts[1].strip()
                allowed_ips = parts[2].split(',') if len(parts) > 2 else ['*']
                allowed_ips = [ip.strip() for ip in allowed_ips]

                # Hash the key for secure storage
                key_hash = self._hash_key(api_key)

                self.api_keys[key_hash] = {
                    'client_name': client_name,
                    'raw_key': api_key,  # TODO: Remove in production, use only hash
                    'allowed_ips': set(allowed_ips),
                    'created_at': datetime.utcnow(),
                    'last_used': None,
                    'usage_count': 0,
                    'is_active': True,
                    # Future fields for rotation
                    'expires_at': None,
                    'rotation_schedule_days': 90,
                    'grace_period_days': 7
                }

                logger.info(f"Loaded API key for client: {client_name}")

        except Exception as e:
            logger.error(f"Error loading API keys: {e}")

    def _hash_key(self, api_key: str) -> str:
        """Generate secure hash of API key."""
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    def validate_key(self, api_key: str, client_ip: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate API key and IP address.

        Returns:
            (is_valid, client_name, error_message)
        """
        if not api_key:
            return False, None, "API key is required"

        key_hash = self._hash_key(api_key)
        key_info = self.api_keys.get(key_hash)

        if not key_info:
            logger.warning(f"Invalid API key attempt from IP: {client_ip}")
            return False, None, "Invalid API key"

        if not key_info['is_active']:
            logger.warning(f"Inactive API key used by client: {key_info['client_name']}")
            return False, None, "API key is inactive"

        # Check IP whitelist
        allowed_ips = key_info['allowed_ips']
        if '*' not in allowed_ips and client_ip not in allowed_ips:
            logger.warning(f"IP {client_ip} not whitelisted for client: {key_info['client_name']}")
            return False, None, "IP address not authorized"

        # Check expiration (future feature)
        if key_info.get('expires_at') and datetime.utcnow() > key_info['expires_at']:
            logger.warning(f"Expired API key used by client: {key_info['client_name']}")
            return False, None, "API key has expired"

        # Update usage statistics
        key_info['last_used'] = datetime.utcnow()
        key_info['usage_count'] += 1

        logger.info(f"Valid API request from client: {key_info['client_name']} (IP: {client_ip})")
        return True, key_info['client_name'], None

    def get_client_info(self, api_key: str) -> Optional[Dict]:
        """Get client information for valid API key."""
        key_hash = self._hash_key(api_key)
        return self.api_keys.get(key_hash)

    def get_usage_stats(self, client_name: Optional[str] = None) -> Dict:
        """Get usage statistics for monitoring."""
        stats = {}
        for key_hash, key_info in self.api_keys.items():
            if client_name is None or key_info['client_name'] == client_name:
                stats[key_info['client_name']] = {
                    'usage_count': key_info['usage_count'],
                    'last_used': key_info['last_used'],
                    'is_active': key_info['is_active'],
                    'allowed_ips_count': len(key_info['allowed_ips'])
                }
        return stats


# Global instances
api_key_manager = None  # Initialized lazily when needed

# Rate limiter will be imported when needed to avoid circular imports


def get_api_key_manager() -> APIKeyManager:
    """Get or initialize the global API key manager instance."""
    global api_key_manager
    if api_key_manager is None:
        api_key_manager = APIKeyManager()
    return api_key_manager


def require_api_key(f):
    """
    Decorator to require valid API key authentication.

    Also logs all API requests for security audit.
    """
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        start_time = time.time()
        client_ip = get_remote_address(request)
        request_id = f"req_{int(time.time())}_{hash(client_ip) % 10000:04d}"

        # Extract API key from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            logger.warning(f"Missing or invalid Authorization header from IP: {client_ip}")
            return jsonify({
                'error_code': 'MISSING_API_KEY',
                'error_message': 'Authorization header with Bearer token is required',
                'timestamp': datetime.utcnow().isoformat(),
                'request_id': request_id
            }), 401

        api_key = auth_header[7:]  # Remove 'Bearer ' prefix

        # Validate API key and IP
        manager = get_api_key_manager()
        is_valid, client_name, error_message = manager.validate_key(api_key, client_ip)

        if not is_valid:
            # Audit log for failed authentication
            logger.warning(
                f"API auth failed - IP: {client_ip}, Error: {error_message}, "
                f"RequestID: {request_id}, UserAgent: {request.headers.get('User-Agent', 'Unknown')}"
            )
            return jsonify({
                'error_code': 'AUTHENTICATION_FAILED',
                'error_message': error_message,
                'timestamp': datetime.utcnow().isoformat(),
                'request_id': request_id
            }), 401

        # Add client context to request for use in endpoint
        request.client_name = client_name
        request.request_id = request_id
        request.start_time = start_time

        # Audit log for successful authentication
        logger.info(
            f"API auth success - Client: {client_name}, IP: {client_ip}, "
            f"Endpoint: {request.endpoint}, RequestID: {request_id}"
        )

        try:
            # Execute the actual endpoint
            response = await f(*args, **kwargs)

            # Audit log for successful request
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"API request completed - Client: {client_name}, "
                f"Duration: {duration_ms:.2f}ms, RequestID: {request_id}"
            )

            return response

        except Exception as e:
            # Audit log for errors
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"API request failed - Client: {client_name}, "
                f"Error: {str(e)}, Duration: {duration_ms:.2f}ms, RequestID: {request_id}"
            )
            raise

    return decorated_function


def get_rate_limit_for_client(client_name: str) -> List[str]:
    """
    Get rate limits for specific client.

    V1: Static limits
    V2: Dynamic limits from database/config
    """
    # Default limits
    default_limits = ["60 per minute", "1000 per hour", "10000 per day"]

    # Client-specific limits (future feature)
    client_limits = {
        'lighton': ["120 per minute", "2000 per hour", "20000 per day"],
        'premium_client': ["300 per minute", "5000 per hour", "50000 per day"]
    }

    return client_limits.get(client_name.lower(), default_limits)


class SecurityMiddleware:
    """
    Security middleware for additional protection.

    Features:
    - Request sanitization
    - Suspicious pattern detection
    - Brute force protection
    - Request size limiting
    """

    def __init__(self):
        self.failed_attempts: Dict[str, List[datetime]] = defaultdict(list)
        self.blocked_ips: Set[str] = set()

    def is_request_suspicious(self, request_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check if request contains suspicious patterns."""

        # Check for common injection patterns
        suspicious_patterns = [
            '<script', 'javascript:', 'vbscript:',
            'onload=', 'onerror=', 'onclick=',
            'DROP TABLE', 'SELECT * FROM',
            '../', '..\\'
        ]

        query = request_data.get('query', '').lower()
        for pattern in suspicious_patterns:
            if pattern.lower() in query:
                return True, f"Suspicious pattern detected: {pattern}"

        # Check query length (extremely long queries might be attacks)
        if len(query) > 2000:
            return True, "Query too long"

        # Check for excessive special characters
        special_chars = sum(1 for char in query if not char.isalnum() and not char.isspace())
        if special_chars > len(query) * 0.3:
            return True, "Too many special characters"

        return False, None

    def record_failed_attempt(self, client_ip: str):
        """Record failed authentication attempt for brute force protection."""
        now = datetime.utcnow()

        # Clean old attempts (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self.failed_attempts[client_ip] = [
            attempt for attempt in self.failed_attempts[client_ip]
            if attempt > cutoff
        ]

        # Add current attempt
        self.failed_attempts[client_ip].append(now)

        # Block IP if too many failures
        if len(self.failed_attempts[client_ip]) > 10:
            self.blocked_ips.add(client_ip)
            logger.warning(f"IP {client_ip} blocked due to excessive failed attempts")

    def is_ip_blocked(self, client_ip: str) -> bool:
        """Check if IP is blocked due to security violations."""
        return client_ip in self.blocked_ips


# Global security middleware instance
security_middleware = SecurityMiddleware()


# Custom error handlers for rate limiting
def handle_rate_limit_exceeded(e):
    """Custom rate limit error handler."""
    client_ip = get_remote_address(request)
    logger.warning(f"Rate limit exceeded for IP: {client_ip}")

    return jsonify({
        'error_code': 'RATE_LIMIT_EXCEEDED',
        'error_message': 'Too many requests. Please slow down.',
        'retry_after_seconds': e.retry_after,
        'timestamp': datetime.utcnow().isoformat()
    }), 429


def get_remote_address(request) -> str:
    """
    Get the remote IP address from the request.

    Handles various proxy headers to get the real client IP.
    Based on Quart/Flask documentation.
    """
    try:
        # Check for forwarded headers first (proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the list (original client)
            return forwarded_for.split(',')[0].strip()

        # Check for other proxy headers
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip

        # Check HTTP_X_REAL_IP in environ (nginx proxy)
        if hasattr(request, 'environ'):
            real_ip_environ = request.environ.get('HTTP_X_REAL_IP')
            if real_ip_environ:
                return real_ip_environ

        # Fall back to remote address (standard Quart/Flask way)
        if request.remote_addr:
            return request.remote_addr

        # Last resort: check environ directly
        if hasattr(request, 'environ'):
            return request.environ.get('REMOTE_ADDR', 'unknown')

    except Exception as e:
        logger.warning(f"Error getting remote address: {e}")

    # Default fallback
    return 'unknown'