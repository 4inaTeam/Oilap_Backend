from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Centralized cache management"""

    # Cache prefixes for different data types
    PREFIXES = {
        'bills': 'bills',
        'factures': 'factures',
        'products': 'products',
        'users': 'users',
        'notifications': 'notifications',
        'statistics': 'stats',
        'payments': 'payments',
    }

    # Cache timeouts
    TIMEOUTS = {
        'SHORT': getattr(settings, 'CACHE_TTL', {}).get('SHORT', 300),
        'MEDIUM': getattr(settings, 'CACHE_TTL', {}).get('MEDIUM', 900),
        'LONG': getattr(settings, 'CACHE_TTL', {}).get('LONG', 3600),
        'VERY_LONG': getattr(settings, 'CACHE_TTL', {}).get('VERY_LONG', 86400),
    }

    @staticmethod
    def generate_cache_key(prefix, *args, **kwargs):
        """Generate a consistent cache key"""
        key_parts = [prefix]

        # Add args
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(hashlib.md5(json.dumps(
                    arg, sort_keys=True).encode()).hexdigest())
            else:
                key_parts.append(str(arg))

        # Add kwargs
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            kwargs_str = json.dumps(sorted_kwargs, sort_keys=True)
            key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest())

        return ':'.join(key_parts)

    @classmethod
    def get(cls, prefix, *args, **kwargs):
        """Get cached data"""
        try:
            key = cls.generate_cache_key(prefix, *args, **kwargs)
            return cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    @classmethod
    def set(cls, prefix, data, timeout='MEDIUM', *args, **kwargs):
        """Set cached data"""
        try:
            key = cls.generate_cache_key(prefix, *args, **kwargs)
            timeout_value = cls.TIMEOUTS.get(
                timeout, timeout) if isinstance(timeout, str) else timeout
            cache.set(key, data, timeout_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    @classmethod
    def delete(cls, prefix, *args, **kwargs):
        """Delete cached data"""
        try:
            key = cls.generate_cache_key(prefix, *args, **kwargs)
            cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    @classmethod
    def delete_pattern(cls, pattern):
        """Delete all keys matching a pattern"""
        try:
            from django_redis import get_redis_connection
            con = get_redis_connection("default")
            keys = con.keys(
                f"{settings.CACHES['default'].get('KEY_PREFIX', '')}:*{pattern}*")
            if keys:
                con.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return False

    @classmethod
    def clear_user_cache(cls, user_id):
        """Clear all cache for a specific user"""
        patterns = [
            f"bills:user:{user_id}",
            f"factures:user:{user_id}",
            f"products:user:{user_id}",
            f"users:{user_id}",
            f"notifications:user:{user_id}",
            f"stats:user:{user_id}",
        ]

        for pattern in patterns:
            cls.delete_pattern(pattern)


def cache_result(prefix, timeout='MEDIUM', key_args=None):
    """
    Decorator to cache function results

    Args:
        prefix: Cache key prefix
        timeout: Cache timeout (string from TIMEOUTS or integer seconds)
        key_args: List of argument names to include in cache key
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key based on function arguments
            cache_key_parts = []

            if key_args:
                # Use specific arguments for cache key
                for arg_name in key_args:
                    if arg_name in kwargs:
                        cache_key_parts.append(
                            f"{arg_name}:{kwargs[arg_name]}")
            else:
                # Use all arguments
                cache_key_parts.extend([str(arg) for arg in args])
                cache_key_parts.extend([f"{k}:{v}" for k, v in kwargs.items()])

            cache_key = CacheManager.generate_cache_key(
                prefix, *cache_key_parts)

            # Try to get from cache
            try:
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_result
            except Exception as e:
                logger.error(f"Cache get error: {e}")

            # Execute function and cache result
            result = func(*args, **kwargs)

            try:
                timeout_value = CacheManager.TIMEOUTS.get(
                    timeout, timeout) if isinstance(timeout, str) else timeout
                cache.set(cache_key, result, timeout_value)
                logger.debug(f"Cache set for {cache_key}")
            except Exception as e:
                logger.error(f"Cache set error: {e}")

            return result
        return wrapper
    return decorator


def invalidate_cache_on_save(sender, instance, **kwargs):
    """Signal handler to invalidate cache when models are saved"""
    model_name = sender.__name__.lower()

    if model_name == 'bill':
        CacheManager.delete_pattern(f"bills:user:{instance.user.id}")
        CacheManager.delete_pattern("stats")
    elif model_name == 'facture':
        CacheManager.delete_pattern(f"factures:user:{instance.client.id}")
        CacheManager.delete_pattern("stats")
    elif model_name == 'product':
        CacheManager.delete_pattern(f"products:user:{instance.client.id}")
        CacheManager.delete_pattern("stats")
    elif model_name == 'customuser':
        CacheManager.delete_pattern(f"users:{instance.id}")
    elif model_name == 'notification':
        CacheManager.delete_pattern(f"notifications:user:{instance.user.id}")


# Connect signals (add this to your apps.py or __init__.py)
def connect_cache_signals():
    from django.db.models.signals import post_save, post_delete
    from bills.models import Bill
    from factures.models import Facture
    from products.models import Product
    from users.models import CustomUser
    from tickets.models import Notification

    post_save.connect(invalidate_cache_on_save, sender=Bill)
    post_save.connect(invalidate_cache_on_save, sender=Facture)
    post_save.connect(invalidate_cache_on_save, sender=Product)
    post_save.connect(invalidate_cache_on_save, sender=CustomUser)
    post_save.connect(invalidate_cache_on_save, sender=Notification)

    post_delete.connect(invalidate_cache_on_save, sender=Bill)
    post_delete.connect(invalidate_cache_on_save, sender=Facture)
    post_delete.connect(invalidate_cache_on_save, sender=Product)
    post_delete.connect(invalidate_cache_on_save, sender=CustomUser)
    post_delete.connect(invalidate_cache_on_save, sender=Notification)
