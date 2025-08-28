from django.contrib import admin
from .models import Bill, Item, Bilan

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ['owner', 'category', 'amount', 'payment_date', 'created_at']
    list_filter = ['category', 'payment_date', 'created_at']
    search_fields = ['owner', 'category']
    ordering = ['-created_at']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'quantity', 'unit_price', 'bill']
    list_filter = ['bill__category']
    search_fields = ['title', 'bill__owner']


@admin.register(Bilan)
class BilanAdmin(admin.ModelAdmin):
    list_display = ['description', 'montant_actif', 'montant_passif', 'date_entree', 'date_sortie', 'has_image', 'has_pdf', 'created_by', 'created_at']
    list_filter = ['date_entree', 'date_sortie', 'created_by', 'created_at']
    search_fields = ['description', 'created_by__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    fields = ['description', 'montant_actif', 'montant_passif', 'date_entree', 'date_sortie', 'original_image', 'pdf_file', 'created_by', 'created_at', 'updated_at']
    
    def has_image(self, obj):
        return bool(obj.original_image)
    has_image.boolean = True
    has_image.short_description = 'Image'
    
    def has_pdf(self, obj):
        return bool(obj.pdf_file)
    has_pdf.boolean = True
    has_pdf.short_description = 'PDF'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)
