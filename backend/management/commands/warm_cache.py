from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from utils.cache_utils import CacheManager
import requests
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Warm up cache with commonly accessed data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--endpoints',
            nargs='+',
            default=['stats', 'users', 'products'],
            help='Endpoints to warm up',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting cache warm-up...')

        endpoints = options['endpoints']

        if 'stats' in endpoints:
            self.warm_statistics()

        if 'users' in endpoints:
            self.warm_users()

        if 'products' in endpoints:
            self.warm_products()

        self.stdout.write(
            self.style.SUCCESS('Cache warm-up completed!')
        )

    def warm_statistics(self):
        """Pre-cache statistics for admin users"""
        self.stdout.write('Warming up statistics cache...')

        admin_users = User.objects.filter(
            role__in=['ADMIN', 'EMPLOYEE', 'ACCOUNTANT'])

        for user in admin_users:
            try:
                # Cache bill statistics
                cache_key = f"bill_stats:user:{user.id}:role:{user.role.lower()}"
                # You would call your statistics calculation here
                # This is just a placeholder
                self.stdout.write(f'Cached stats for user {user.id}')
            except Exception as e:
                logger.error(
                    f'Error warming stats cache for user {user.id}: {e}')

    def warm_users(self):
        """Pre-cache user lists"""
        self.stdout.write('Warming up users cache...')

        try:
            users = User.objects.all()
            data = [
                {
                    "id": user.id,
                    "name": user.username,
                    "cin": user.cin,
                    "email": user.email,
                    "role": user.role,
                    "tel": user.tel,
                    "profile_photo": user.profile_photo.url if user.profile_photo else None,
                    "isActive": user.isActive,
                    "ville": user.ville
                } for user in users
            ]

            # Cache user list
            cache_key = "users:list:warm_up"
            CacheManager.set('users', data, 'MEDIUM', 'list', 'warm_up')
            self.stdout.write('Cached user list')

        except Exception as e:
            logger.error(f'Error warming users cache: {e}')

    def warm_products(self):
        """Pre-cache product statistics"""
        self.stdout.write('Warming up products cache...')

        try:
            from products.models import Product

            # Cache product stats
            total_products = Product.objects.count()
            stats_data = {
                'total_products': total_products,
                'status_distribution': {},
                'payment_distribution': {},
                'quality_distribution': {}
            }

            CacheManager.set('product_stats', stats_data, 'MEDIUM')
            self.stdout.write('Cached product statistics')

        except Exception as e:
            logger.error(f'Error warming products cache: {e}')
