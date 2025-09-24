"""
Production-ready rate limiting for Quart applications.

Implements sliding window rate limiting with Redis-like functionality
using in-memory storage with automatic cleanup.
"""

import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from threading import Lock
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    """Rate limit rule definition."""
    limit: int
    window_seconds: int
    name: str

    @classmethod
    def from_string(cls, rule_string: str) -> 'RateLimitRule':
        """Parse rule from string like '60 per minute' or '1000 per hour'."""
        parts = rule_string.lower().strip().split()
        if len(parts) != 3 or parts[1] != 'per':
            raise ValueError(f"Invalid rate limit format: {rule_string}")

        limit = int(parts[0])
        period = parts[2]

        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }

        if period not in period_seconds:
            raise ValueError(f"Unknown period: {period}")

        return cls(
            limit=limit,
            window_seconds=period_seconds[period],
            name=rule_string
        )


class SlidingWindowRateLimiter:
    """
    Production-ready sliding window rate limiter.

    Features:
    - Precise sliding window counting
    - Automatic cleanup of old entries
    - Thread-safe operations
    - Memory efficient
    - Per-client rule customization
    """

    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.rules: Dict[str, List[RateLimitRule]] = {}
        self.default_rules: List[RateLimitRule] = [
            RateLimitRule.from_string("60 per minute"),
            RateLimitRule.from_string("1000 per hour")
        ]
        self.lock = Lock()
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # Cleanup every 5 minutes

    def set_rules_for_client(self, client_id: str, rules: List[str]):
        """Set custom rate limit rules for a specific client."""
        parsed_rules = [RateLimitRule.from_string(rule) for rule in rules]
        with self.lock:
            self.rules[client_id] = parsed_rules
        logger.info(f"Set custom rate limits for client {client_id}: {rules}")

    def get_rules_for_client(self, client_id: str) -> List[RateLimitRule]:
        """Get rate limit rules for a client (custom or default)."""
        with self.lock:
            return self.rules.get(client_id, self.default_rules)

    def _cleanup_old_requests(self, current_time: float):
        """Clean up old request records to prevent memory leaks."""
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        with self.lock:
            # Find the maximum window we need to keep
            max_window = max(rule.window_seconds for rule in self.default_rules)
            for client_rules in self.rules.values():
                if client_rules:
                    max_window = max(max_window, max(rule.window_seconds for rule in client_rules))

            cutoff_time = current_time - max_window

            # Clean up old entries
            for client_id, requests in list(self.requests.items()):
                # Remove old requests
                self.requests[client_id] = [
                    req_time for req_time in requests
                    if req_time > cutoff_time
                ]

                # Remove empty client records
                if not self.requests[client_id]:
                    del self.requests[client_id]

            self.last_cleanup = current_time

        logger.debug(f"Rate limiter cleanup completed. Active clients: {len(self.requests)}")

    def is_allowed(self, client_id: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if a request is allowed for the given client.

        Returns:
            (is_allowed, rate_limit_info)

        rate_limit_info contains:
            - remaining: requests remaining in current window
            - reset_time: when the limit resets
            - limit: current limit
            - window: window size in seconds
        """
        current_time = time.time()

        # Cleanup old requests periodically
        self._cleanup_old_requests(current_time)

        rules = self.get_rules_for_client(client_id)

        with self.lock:
            client_requests = self.requests[client_id]

            # Check each rule
            for rule in rules:
                window_start = current_time - rule.window_seconds

                # Count requests in current window
                requests_in_window = sum(1 for req_time in client_requests if req_time > window_start)

                if requests_in_window >= rule.limit:
                    # Find when the oldest request in window will expire
                    oldest_in_window = min(
                        req_time for req_time in client_requests
                        if req_time > window_start
                    ) if client_requests else current_time

                    reset_time = oldest_in_window + rule.window_seconds

                    rate_limit_info = {
                        'remaining': 0,
                        'reset_time': reset_time,
                        'limit': rule.limit,
                        'window': rule.window_seconds,
                        'rule_name': rule.name,
                        'requests_in_window': requests_in_window
                    }

                    logger.warning(
                        f"Rate limit exceeded for client {client_id}: "
                        f"{requests_in_window}/{rule.limit} in {rule.name}"
                    )
                    return False, rate_limit_info

            # All rules passed, record this request
            self.requests[client_id].append(current_time)

            # Return info for the most restrictive rule
            most_restrictive_rule = min(rules, key=lambda r: r.window_seconds)
            window_start = current_time - most_restrictive_rule.window_seconds
            requests_in_window = sum(1 for req_time in client_requests if req_time > window_start)

            rate_limit_info = {
                'remaining': most_restrictive_rule.limit - requests_in_window,
                'reset_time': current_time + most_restrictive_rule.window_seconds,
                'limit': most_restrictive_rule.limit,
                'window': most_restrictive_rule.window_seconds,
                'rule_name': most_restrictive_rule.name,
                'requests_in_window': requests_in_window
            }

            return True, rate_limit_info

    def get_client_stats(self, client_id: str) -> Dict:
        """Get current statistics for a client."""
        current_time = time.time()
        rules = self.get_rules_for_client(client_id)

        with self.lock:
            client_requests = self.requests.get(client_id, [])

            stats = {
                'client_id': client_id,
                'total_requests': len(client_requests),
                'rules': []
            }

            for rule in rules:
                window_start = current_time - rule.window_seconds
                requests_in_window = sum(1 for req_time in client_requests if req_time > window_start)

                stats['rules'].append({
                    'rule_name': rule.name,
                    'limit': rule.limit,
                    'window_seconds': rule.window_seconds,
                    'requests_in_window': requests_in_window,
                    'remaining': rule.limit - requests_in_window,
                    'utilization_percent': (requests_in_window / rule.limit) * 100
                })

            return stats

    def get_all_stats(self) -> Dict:
        """Get statistics for all clients."""
        with self.lock:
            active_clients = list(self.requests.keys())

        return {
            'active_clients': len(active_clients),
            'total_requests': sum(len(reqs) for reqs in self.requests.values()),
            'clients': [self.get_client_stats(client_id) for client_id in active_clients]
        }


# Global rate limiter instance
rate_limiter = SlidingWindowRateLimiter()


def get_client_ip() -> str:
    """Get client IP address from request headers."""
    from quart import request

    # Check for forwarded headers first (behind proxy/load balancer)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take the first IP (client IP)
        return forwarded_for.split(',')[0].strip()

    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip

    # Fallback to remote address
    return request.remote_addr or 'unknown'


def rate_limit(*rules: str):
    """
    Decorator to apply rate limiting to Quart routes.

    Args:
        *rules: Rate limit rules like "60 per minute", "1000 per hour"

    Usage:
        @rate_limit("60 per minute", "1000 per hour")
        async def my_endpoint():
            pass
    """
    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            from quart import request, jsonify
            from backend.api.auth import api_key_manager

            # Determine client identifier
            client_id = get_client_ip()  # Default to IP

            # Try to get more specific client ID from API key
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                api_key = auth_header[7:]
                client_info = api_key_manager.get_client_info(api_key)
                if client_info:
                    client_id = f"client_{client_info['client_name']}"

            # Apply custom rules if specified
            if rules:
                rate_limiter.set_rules_for_client(client_id, list(rules))

            # Check rate limit
            is_allowed, rate_info = rate_limiter.is_allowed(client_id)

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for {client_id}: "
                    f"{rate_info['requests_in_window']}/{rate_info['limit']} "
                    f"in {rate_info['rule_name']}"
                )

                retry_after = max(1, int(rate_info['reset_time'] - time.time()))

                return jsonify({
                    'error_code': 'RATE_LIMIT_EXCEEDED',
                    'error_message': 'Too many requests. Please slow down.',
                    'retry_after_seconds': retry_after,
                    'limit': rate_info['limit'],
                    'window_seconds': rate_info['window'],
                    'requests_in_window': rate_info['requests_in_window'],
                    'timestamp': datetime.utcnow().isoformat()
                }), 429

            # Add rate limit headers to response
            response = await f(*args, **kwargs)

            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(rate_info['limit'])
                response.headers['X-RateLimit-Remaining'] = str(rate_info['remaining'])
                response.headers['X-RateLimit-Reset'] = str(int(rate_info['reset_time']))
                response.headers['X-RateLimit-Window'] = str(rate_info['window'])

            return response

        return decorated_function
    return decorator


# Compatibility functions for existing code
class CompatibilityLimiter:
    """Compatibility wrapper to maintain existing interface."""

    def __init__(self):
        pass

    def init_app(self, app):
        """Initialize with Quart app (no-op for compatibility)."""
        logger.info("Rate limiter initialized with Quart app")

    def limit(self, rule: str):
        """Apply rate limit rule to endpoint."""
        return rate_limit(rule)


# Global compatibility instance
limiter = CompatibilityLimiter()