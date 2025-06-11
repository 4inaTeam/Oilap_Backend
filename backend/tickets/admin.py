from django.contrib import admin
from .models import Ticket
from django.utils import timezone


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('product', 'client', 'tunisian_date')

    def tunisian_date(self, obj):
        return timezone.localtime(obj.date).strftime('%Y-%m-%d %H:%M %Z')
    tunisian_date.short_description = 'Date (Tunisia Time)'