from django.core.management.base import BaseCommand
from django_redis import get_redis_connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Show Redis cache statistics'

    def handle(self, *args, **options):
        try:
            con = get_redis_connection("default")
            info = con.info()

            self.stdout.write(self.style.SUCCESS(
                '=== Redis Cache Statistics ==='))
            self.stdout.write(
                f"Redis Version: {info.get('redis_version', 'N/A')}")
            self.stdout.write(
                f"Used Memory: {info.get('used_memory_human', 'N/A')}")
            self.stdout.write(
                f"Connected Clients: {info.get('connected_clients', 'N/A')}")
            self.stdout.write(f"Total Keys: {con.dbsize()}")
            self.stdout.write(
                f"Keyspace Hits: {info.get('keyspace_hits', 'N/A')}")
            self.stdout.write(
                f"Keyspace Misses: {info.get('keyspace_misses', 'N/A')}")

            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            self.stdout.write(f"Hit Rate: {hit_rate:.2f}%")

            # Show key patterns
            key_prefix = settings.CACHES['default'].get('KEY_PREFIX', '')
            self.stdout.write(f"\n=== Key Patterns (prefix: {key_prefix}) ===")

            patterns = ['bills:*', 'factures:*', 'products:*',
                        'users:*', 'notifications:*', 'stats:*']
            for pattern in patterns:
                full_pattern = f"{key_prefix}:*{pattern}*" if key_prefix else pattern
                keys = con.keys(full_pattern)
                self.stdout.write(f"{pattern}: {len(keys)} keys")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error getting cache stats: {str(e)}')
            )
