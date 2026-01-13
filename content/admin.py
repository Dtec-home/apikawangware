from django.contrib import admin
from .models import Announcement, Devotional, Event, YouTubeVideo


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'publish_date', 'priority', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_deleted', 'publish_date']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-priority', '-publish_date']
    date_hierarchy = 'publish_date'

    fieldsets = (
        ('Content', {
            'fields': ('title', 'content')
        }),
        ('Publishing', {
            'fields': ('publish_date', 'is_active', 'priority')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Devotional)
class DevotionalAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'publish_date', 'is_published', 'is_featured', 'created_at']
    list_filter = ['is_published', 'is_featured', 'is_deleted', 'publish_date', 'author']
    search_fields = ['title', 'content', 'author', 'scripture_reference']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-publish_date']
    date_hierarchy = 'publish_date'

    fieldsets = (
        ('Content', {
            'fields': ('title', 'content', 'author', 'scripture_reference')
        }),
        ('Media', {
            'fields': ('featured_image_url',)
        }),
        ('Publishing', {
            'fields': ('publish_date', 'is_published', 'is_featured')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_date', 'event_time', 'location', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_deleted', 'event_date']
    search_fields = ['title', 'description', 'location']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['event_date', 'event_time']
    date_hierarchy = 'event_date'

    fieldsets = (
        ('Event Details', {
            'fields': ('title', 'description', 'location')
        }),
        ('Date & Time', {
            'fields': ('event_date', 'event_time')
        }),
        ('Additional Info', {
            'fields': ('registration_link', 'featured_image_url', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(YouTubeVideo)
class YouTubeVideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'publish_date', 'is_featured', 'video_id', 'created_at']
    list_filter = ['is_featured', 'is_deleted', 'category', 'publish_date']
    search_fields = ['title', 'description', 'video_id']
    readonly_fields = ['created_at', 'updated_at', 'embed_url', 'watch_url', 'thumbnail_url']
    ordering = ['-publish_date']
    date_hierarchy = 'publish_date'

    fieldsets = (
        ('Video Details', {
            'fields': ('title', 'video_id', 'description', 'category')
        }),
        ('Publishing', {
            'fields': ('publish_date', 'is_featured')
        }),
        ('URLs (Read-only)', {
            'fields': ('embed_url', 'watch_url', 'thumbnail_url'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
