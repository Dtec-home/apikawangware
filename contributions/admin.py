from django.contrib import admin
from .models import ContributionCategory, Contribution


@admin.register(ContributionCategory)
class ContributionCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_deleted', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_date',
        'member',
        'category',
        'amount',
        'status',
        'mpesa_receipt_number'
    ]
    list_filter = ['status', 'category', 'transaction_date']
    search_fields = [
        'member__first_name',
        'member__last_name',
        'member__phone_number',
        'mpesa_transaction__mpesa_receipt_number'
    ]
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-transaction_date']
    date_hierarchy = 'transaction_date'

    def mpesa_receipt_number(self, obj):
        """Display M-Pesa receipt number"""
        if obj.mpesa_transaction:
            return obj.mpesa_transaction.mpesa_receipt_number
        return '-'
    mpesa_receipt_number.short_description = 'M-Pesa Receipt'
