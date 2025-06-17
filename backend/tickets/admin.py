from django.contrib import admin
from .models import Ticket

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
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'User Email'
    
    def get_facture_number(self, obj):
        return obj.facture.facture_number if obj.facture else '-'
    get_facture_number.short_description = 'Facture Number'
    
    def get_client_name(self, obj):
        return obj.user.username if obj.user else '-'
    get_client_name.short_description = 'Client'
    
    def get_product_info(self, obj):
        if obj.facture and obj.facture.products.exists():
            products = obj.facture.products.all()
            return ", ".join([f"Product #{p.id}" for p in products])
        return '-'
    get_product_info.short_description = 'Products'