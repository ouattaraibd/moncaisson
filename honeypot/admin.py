from django.contrib import admin
from .models import BlockedIP

# Utilisez soit @admin.register() soit admin.site.register() mais pas les deux
@admin.register(BlockedIP)  # <-- Méthode recommandée
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'created_at', 'reason')
    search_fields = ('ip_address',)