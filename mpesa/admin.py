from django.contrib import admin
from .models import MpesaTransaction, MpesaCallback


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'phone_number',
        'amount',
        'status',
        'mpesa_receipt_number',
        'account_reference',
        'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'phone_number',
        'mpesa_receipt_number',
        'merchant_request_id',
        'checkout_request_id'
    ]
    readonly_fields = [
        'merchant_request_id',
        'checkout_request_id',
        'mpesa_receipt_number',
        'transaction_date',
        'result_code',
        'result_desc',
        'created_at',
        'updated_at'
    ]
    ordering = ['-created_at']


@admin.register(MpesaCallback)
class MpesaCallbackAdmin(admin.ModelAdmin):
    list_display = [
        'checkout_request_id',
        'result_code',
        'result_desc',
        'created_at'
    ]
    list_filter = ['result_code', 'created_at']
    search_fields = ['checkout_request_id', 'merchant_request_id']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
