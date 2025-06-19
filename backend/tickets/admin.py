from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Ticket, Notification
import json


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'get_user_email',
        'get_facture_number',
        'get_client_name',
        'get_product_info',
        'ticket_type',
        'is_sent',
        'created_at'
    )
    list_filter = ('ticket_type', 'is_sent', 'created_at')
    search_fields = ('user__email', 'user__username',
                     'facture__facture_number')
    readonly_fields = ('created_at', 'sent_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'facture', 'ticket_type', 'message')
        }),
        ('Status', {
            'fields': ('is_sent', 'created_at', 'sent_at')
        }),
    )

    def get_user_email(self, obj):
        return obj.user.email if obj.user else '-'
    get_user_email.short_description = 'User Email'
    get_user_email.admin_order_field = 'user__email'

    def get_facture_number(self, obj):
        if obj.facture:
            return obj.facture.facture_number
        return '-'
    get_facture_number.short_description = 'Facture Number'
    get_facture_number.admin_order_field = 'facture__facture_number'

    def get_client_name(self, obj):
        if obj.facture and obj.facture.client:
            return f"{obj.facture.client.first_name} {obj.facture.client.last_name}"
        return '-'
    get_client_name.short_description = 'Client Name'
    get_client_name.admin_order_field = 'facture__client__first_name'

    def get_product_info(self, obj):
        if obj.facture:
            # Get first product from facture items if available
            try:
                items = obj.facture.items.all()[:1]
                if items:
                    return f"{items[0].product.name} (+{obj.facture.items.count()-1 if obj.facture.items.count() > 1 else 0} more)"
                return "No items"
            except:
                return "N/A"
        return '-'
    get_product_info.short_description = 'Product Info'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'facture', 'facture__client'
        ).prefetch_related('facture__items__product')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'get_user_email',
        'type',
        'is_read',
        'get_facture_link',
        'created_at',
        'read_at'
    )
    list_filter = (
        'type',
        'is_read',
        'created_at',
        'read_at'
    )
    search_fields = (
        'title',
        'body',
        'user__email',
        'user__username',
        'facture__facture_number'
    )
    readonly_fields = (
        'created_at',
        'read_at',
        'formatted_data'
    )
    ordering = ('-created_at',)

    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'title', 'body', 'type')
        }),
        ('Relations', {
            'fields': ('facture',)
        }),
        ('Status', {
            'fields': ('is_read', 'created_at', 'read_at')
        }),
        ('Additional Data', {
            'fields': ('formatted_data',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_read', 'mark_as_unread']

    def get_user_email(self, obj):
        return obj.user.email if obj.user else '-'
    get_user_email.short_description = 'User Email'
    get_user_email.admin_order_field = 'user__email'

    def get_facture_link(self, obj):
        if obj.facture:
            try:
                url = reverse('admin:factures_facture_change',
                              args=[obj.facture.id])
                return format_html(
                    '<a href="{}">{}</a>',
                    url,
                    obj.facture.facture_number
                )
            except:
                return obj.facture.facture_number
        return '-'
    get_facture_link.short_description = 'Facture'
    get_facture_link.admin_order_field = 'facture__facture_number'

    def formatted_data(self, obj):
        if obj.data:
            try:
                formatted_json = json.dumps(
                    obj.data, indent=2, ensure_ascii=False)
                return format_html('<pre>{}</pre>', formatted_json)
            except:
                return str(obj.data)
        return 'No additional data'
    formatted_data.short_description = 'Data (JSON)'

    def mark_as_read(self, request, queryset):
        updated = 0
        for notification in queryset:
            if not notification.is_read:
                notification.mark_as_read()
                updated += 1

        self.message_user(
            request,
            f'{updated} notification(s) marked as read.'
        )
    mark_as_read.short_description = 'Mark selected notifications as read'

    def mark_as_unread(self, request, queryset):
        updated = queryset.filter(is_read=True).update(
            is_read=False,
            read_at=None
        )
        self.message_user(
            request,
            f'{updated} notification(s) marked as unread.'
        )
    mark_as_unread.short_description = 'Mark selected notifications as unread'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'facture'
        )

