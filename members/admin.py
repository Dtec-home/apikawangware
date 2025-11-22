from django.contrib import admin
from .models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = [
        'member_number',
        'full_name',
        'phone_number',
        'email',
        'is_active',
        'created_at'
    ]
    list_filter = ['is_active', 'is_deleted', 'created_at']
    search_fields = [
        'first_name',
        'last_name',
        'phone_number',
        'member_number',
        'email'
    ]
    readonly_fields = ['member_number', 'created_at', 'updated_at']
    ordering = ['last_name', 'first_name']

    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'member_number')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'email')
        }),
        ('Status', {
            'fields': ('is_active', 'is_deleted', 'deleted_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
