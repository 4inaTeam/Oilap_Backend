from django.core.management.base import BaseCommand
from django.core.cache import cache
from django_redis import get_redis_connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Clear Redis cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pattern',
            type=str,
            help='Clear cache keys matching pattern',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear all cache',
        )
        parser.add_argument(
            '--user',
            type=int,
            help='Clear cache for specific user ID',
        )

    def handle(self, *args, **options):
        if options['all']:
            cache.clear()
            self.stdout.write(
                self.style.SUCCESS('Successfully cleared all cache')
            )
        elif options['pattern']:
            try:
                con = get_redis_connection("default")
                key_prefix = settings.CACHES['default'].get('KEY_PREFIX', '')
                pattern = f"{key_prefix}:*{options['pattern']}*"
                keys = con.keys(pattern)
                if keys:
                    deleted_count = con.delete(*keys)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Successfully deleted {deleted_count} cache keys matching "{options["pattern"]}"')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'No cache keys found matching "{options["pattern"]}"')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error clearing cache: {str(e)}')
                )
        elif options['user']:
            from utils.cache_utils import CacheManager
            user_id = options['user']
            CacheManager.clear_user_cache(user_id)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully cleared cache for user {user_id}')
            )
        else:
            self.stdout.write(
                self.style.ERROR('Please specify --all, --pattern, or --user')
            )
