from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
import time
import logging
import json

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """
    Middleware for additional security features including rate limiting
    and security headers
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Configure sensitive endpoints that need rate limiting
        self.sensitive_endpoints = getattr(settings, 'RATE_LIMIT_SENSITIVE_ENDPOINTS', [
            '/api/auth/login/',
            '/api/auth/password/reset/',
            '/api/users/create/',
            '/api/users/clients/create/',
        ])
        
        # Rate limiting configuration
        self.rate_limit_requests = getattr(settings, 'RATE_LIMIT_REQUESTS', 10)
        self.rate_limit_window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)  # seconds
        self.rate_limit_enabled = getattr(settings, 'RATELIMIT_ENABLE', True)
    
    def __call__(self, request):
        # Rate limiting for sensitive endpoints
        if self.rate_limit_enabled and self._is_sensitive_endpoint(request.path):
            rate_limit_response = self._check_rate_limit(request)
            if rate_limit_response:
                return rate_limit_response
        
        # Process the request
        response = self.get_response(request)
        
        # Add security headers
        self._add_security_headers(response)
        
        return response
    
    def _is_sensitive_endpoint(self, path):
        """Check if endpoint is sensitive and needs rate limiting"""
        return any(path.startswith(endpoint) for endpoint in self.sensitive_endpoints)
    
    def _check_rate_limit(self, request):
        """Check if request should be rate limited"""
        # Get client identifier (IP address)
        ip = self._get_client_ip(request)
        
        # Create cache key
        cache_key = f'rate_limit_{ip}_{request.path_info}'
        
        # Get current request count
        current_requests = cache.get(cache_key, 0)
        
        if current_requests >= self.rate_limit_requests:
            logger.warning(f'Rate limit exceeded for IP {ip} on endpoint {request.path}')
            
            # Return rate limit exceeded response
            return JsonResponse(
                {
                    'error': 'Too many requests',
                    'detail': f'Rate limit exceeded. Maximum {self.rate_limit_requests} requests per {self.rate_limit_window} seconds.',
                    'retry_after': self.rate_limit_window
                },
                status=429
            )
        
        # Increment request count
        cache.set(cache_key, current_requests + 1, self.rate_limit_window)
        
        # Log the request for monitoring
        if current_requests > self.rate_limit_requests * 0.8:  # Log when 80% of limit reached
            logger.info(f'Rate limit warning: {current_requests + 1}/{self.rate_limit_requests} requests for IP {ip} on {request.path}')
        
        return None
    
    def _get_client_ip(self, request):
        """Get the real client IP address"""
        # Check for forwarded IP (when behind proxy/load balancer)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the chain
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        return ip
    
    def _add_security_headers(self, response):
        """Add security headers to response"""
        # Only add headers if they're not already set
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'X-Permitted-Cross-Domain-Policies': 'none',
        }
        
        # Add Content Security Policy for HTML responses
        if response.get('Content-Type', '').startswith('text/html'):
            security_headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )
        
        # Add headers that aren't already present
        for header, value in security_headers.items():
            if header not in response:
                response[header] = value
        
        return response


class BruteForceProtectionMiddleware:
    """
    Additional middleware specifically for brute force protection
    Can be used alongside SecurityMiddleware
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check for brute force patterns before processing login requests
        if request.path.startswith('/api/auth/login/') and request.method == 'POST':
            if self._detect_brute_force(request):
                logger.critical(f'Potential brute force attack detected from IP: {self._get_client_ip(request)}')
                return JsonResponse(
                    {
                        'error': 'Suspicious activity detected',
                        'detail': 'Your IP has been temporarily blocked due to suspicious activity.'
                    },
                    status=429
                )
        
        response = self.get_response(request)
        return response
    
    def _detect_brute_force(self, request):
        """Detect potential brute force attacks"""
        ip = self._get_client_ip(request)
        
        # Check for rapid login attempts from same IP
        cache_key = f'brute_force_{ip}'
        attempts_data = cache.get(cache_key, {'count': 0, 'first_attempt': time.time()})
        
        current_time = time.time()
        time_window = 300  # 5 minutes
        max_attempts = 20  # Maximum attempts in time window
        
        # Reset counter if time window has passed
        if current_time - attempts_data['first_attempt'] > time_window:
            attempts_data = {'count': 1, 'first_attempt': current_time}
        else:
            attempts_data['count'] += 1
        
        # Update cache
        cache.set(cache_key, attempts_data, time_window)
        
        # Check if threshold exceeded
        if attempts_data['count'] > max_attempts:
            # Block IP for longer period
            block_key = f'blocked_ip_{ip}'
            cache.set(block_key, True, 3600)  # Block for 1 hour
            return True
        
        return False
    
    def _get_client_ip(self, request):
        """Get the real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class RequestLoggingMiddleware:
    """
    Optional middleware for logging security-related requests
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.logged_endpoints = [
            '/api/auth/login/',
            '/api/auth/password/reset/',
            '/api/users/create/',
            '/admin/',
        ]
    
    def __call__(self, request):
        # Log security-sensitive requests
        if any(request.path.startswith(endpoint) for endpoint in self.logged_endpoints):
            self._log_request(request)
        
        response = self.get_response(request)
        
        # Log responses for sensitive endpoints
        if any(request.path.startswith(endpoint) for endpoint in self.logged_endpoints):
            self._log_response(request, response)
        
        return response
    
    def _log_request(self, request):
        """Log incoming security-sensitive requests"""
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        
        logger.info(f'Security request: {request.method} {request.path} from {ip} - User-Agent: {user_agent[:100]}')
    
    def _log_response(self, request, response):
        """Log responses for security-sensitive requests"""
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        
        if response.status_code >= 400:
            logger.warning(f'Security response: {response.status_code} for {request.method} {request.path} from {ip}')
        else:
            logger.info(f'Security response: {response.status_code} for {request.method} {request.path} from {ip}')