from django.contrib import admin
from .models import ContactMessage, Game, Wallet, Transfer, PaymentRequest, Budget, BudgetEntry, BudgetLimit


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


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'code', 'wallet', 'amount', 'status', 'paid_by')
    list_filter = ('status',)


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(BudgetEntry)
class BudgetEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'budget', 'kind', 'category', 'label', 'amount')
    list_filter = ('kind', 'category')


@admin.register(BudgetLimit)
class BudgetLimitAdmin(admin.ModelAdmin):
    list_display = ('budget', 'category', 'amount')
    list_filter = ('category',)