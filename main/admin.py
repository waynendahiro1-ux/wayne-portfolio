from django.contrib import admin
from .models import ContactMessage, Game


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('date', 'opponent', 'points', 'rebounds', 'assists')