from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Member
from .roles import UserRole


class UserRoleInline(admin.TabularInline):
    """Inline admin for user roles"""
    model = UserRole
    extra = 1
    fields = ['role', 'is_active']
    verbose_name = "Role Assignment"
    verbose_name_plural = "Role Assignments"


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """Admin interface for UserRole"""
    list_display = ['user', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Role Assignment', {
            'fields': ('user', 'role', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Unregister the default User admin and register with our inline
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User admin with role management"""
    inlines = [UserRoleInline]

    list_display = ['username', 'email', 'first_name', 'last_name', 'get_roles', 'is_staff', 'is_active']

    def get_roles(self, obj):
        """Display user's roles"""
        roles = UserRole.objects.filter(user=obj, is_active=True).values_list('role', flat=True)
        return ', '.join(roles) if roles else 'No roles'
    get_roles.short_description = 'Roles'


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = [
        'member_number',
        'full_name',
        'phone_number',
        'email',
        'is_active',
        'get_user_roles',
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
        ('Authentication', {
            'fields': ('user',),
            'description': 'Link to Django user account for authentication and role assignment'
        }),
        ('Status', {
            'fields': ('is_active', 'is_deleted', 'deleted_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_user_roles(self, obj):
        """Display member's user roles"""
        if obj.user:
            roles = UserRole.objects.filter(user=obj.user, is_active=True).values_list('role', flat=True)
            return ', '.join(roles) if roles else 'No roles'
        return 'No user account'
    get_user_roles.short_description = 'User Roles'
