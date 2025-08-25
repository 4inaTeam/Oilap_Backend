# predict/admin.py

from django.contrib import admin
from django.core.cache import cache
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import path
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

from .ml_service import global_prediction_service


class PredictionServiceAdminConfig(admin.ModelAdmin):
    """
    Custom admin configuration for ML Prediction Service management
    Since we don't have actual models, we'll create a proxy admin interface
    """

    def has_module_permission(self, request):
        """Show the prediction service in admin if user is staff"""
        return request.user.is_staff

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return False


# Create a simple proxy model for admin interface
class PredictionService:
    """Proxy model for admin interface"""
    class Meta:
        app_label = 'predict'
        verbose_name = 'ML Prediction Service'
        verbose_name_plural = 'ML Prediction Services'


# Custom admin actions
def clear_prediction_cache_action(modeladmin, request, queryset):
    """Admin action to clear prediction cache"""
    try:
        cache.clear()
        messages.success(request, 'Prediction cache cleared successfully')
    except Exception as e:
        messages.error(request, f'Error clearing cache: {e}')


clear_prediction_cache_action.short_description = "Clear prediction cache"


def reload_ml_models_action(modeladmin, request, queryset):
    """Admin action to reload ML models"""
    try:
        global_prediction_service.__init__()
        if global_prediction_service.is_loaded:
            messages.success(request, 'ML models reloaded successfully')
        else:
            messages.error(
                request, 'Failed to reload ML models - check model files')
    except Exception as e:
        messages.error(request, f'Error reloading models: {e}')


reload_ml_models_action.short_description = "Reload ML models"


class PredictionServiceAdmin(admin.ModelAdmin):
    """
    Admin interface for ML Prediction Service
    """

    list_display = ['service_status', 'models_loaded',
                    'last_checked', 'action_links']
    actions = [clear_prediction_cache_action, reload_ml_models_action]

    def get_queryset(self, request):
        # Return empty queryset since we don't have real objects
        return self.model.objects.none()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def service_status(self, obj):
        """Display service status"""
        if global_prediction_service.is_loaded:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactive</span>')
    service_status.short_description = 'Service Status'

    def models_loaded(self, obj):
        """Display if models are loaded"""
        status = global_prediction_service.get_model_status()
        loaded_count = sum(1 for v in status['models_available'].values() if v)
        total_count = len(status['models_available'])
        return f"{loaded_count}/{total_count}"
    models_loaded.short_description = 'Models Loaded'

    def last_checked(self, obj):
        """Display last check time"""
        from django.utils import timezone
        return timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    last_checked.short_description = 'Last Checked'

    def action_links(self, obj):
        """Display action links"""
        return format_html(
            '<a href="/api/predict/status/" target="_blank">API Status</a> | '
            '<a href="/api/predict/health/" target="_blank">Health Check</a>'
        )
    action_links.short_description = 'Quick Links'

    def changelist_view(self, request, extra_context=None):
        """Custom changelist view to show prediction service info"""
        extra_context = extra_context or {}

        # Get service status
        service_status = global_prediction_service.get_model_status()

        extra_context.update({
            'title': 'ML Prediction Service Status',
            'service_info': service_status,
            'prediction_service_status': service_status,
            'has_add_permission': False,
            'has_change_permission': True,
            'has_delete_permission': False,
        })

        return super().changelist_view(request, extra_context)
