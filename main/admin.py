from django.contrib import admin
from .models import ContactMessage, Game, Wallet, Transfer


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('date', 'opponent', 'points', 'rebounds', 'assists')


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'wallet_number', 'balance', 'created_at')
    search_fields = ('nickname', 'wallet_number')


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'sender', 'receiver', 'amount', 'fee')