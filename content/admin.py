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
    list_display = [
        'title', 'category', 'source', 'publish_date',
        'is_featured', 'video_id', 'last_synced_at', 'created_at'
    ]
    list_filter = [
        'is_featured', 'is_deleted', 'category',
        'source', 'publish_date', 'last_synced_at'
    ]
    search_fields = ['title', 'description', 'video_id', 'channel_id', 'playlist_id']
    readonly_fields = [
        'created_at', 'updated_at', 'embed_url', 'watch_url',
        'thumbnail_url', 'last_synced_at', 'youtube_published_at',
        'duration', 'view_count', 'like_count'
    ]
    ordering = ['-publish_date']
    date_hierarchy = 'publish_date'
    actions = ['sync_from_youtube']

    fieldsets = (
        ('Video Details', {
            'fields': ('title', 'video_id', 'description', 'category')
        }),
        ('Publishing', {
            'fields': ('publish_date', 'is_featured')
        }),
        ('Sync Information', {
            'fields': (
                'source', 'channel_id', 'playlist_id',
                'last_synced_at', 'youtube_published_at'
            ),
            'classes': ('collapse',)
        }),
        ('Statistics (Read-only)', {
            'fields': ('duration', 'view_count', 'like_count'),
            'classes': ('collapse',)
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

    def sync_from_youtube(self, request, queryset):
        """Admin action to sync selected videos from YouTube."""
        from content.youtube_service import YouTubeService
        from django.contrib import messages

        try:
            youtube_service = YouTubeService()
            updated_count = 0
            error_count = 0

            for video in queryset:
                try:
                    # Fetch video details
                    video_details = youtube_service.get_video_details([video.video_id])

                    if video_details:
                        # Update the video
                        youtube_service.sync_video_to_db(
                            video_details[0],
                            source=video.source,
                            channel_id=video.channel_id,
                            playlist_id=video.playlist_id,
                            category=video.category
                        )
                        updated_count += 1
                    else:
                        error_count += 1

                except Exception as e:
                    error_count += 1
                    self.message_user(
                        request,
                        f"Error syncing {video.title}: {str(e)}",
                        level=messages.ERROR
                    )

            if updated_count > 0:
                self.message_user(
                    request,
                    f"Successfully synced {updated_count} video(s)",
                    level=messages.SUCCESS
                )

            if error_count > 0:
                self.message_user(
                    request,
                    f"Failed to sync {error_count} video(s)",
                    level=messages.WARNING
                )

        except Exception as e:
            self.message_user(
                request,
                f"Error initializing YouTube service: {str(e)}",
                level=messages.ERROR
            )

    sync_from_youtube.short_description = "Sync selected videos from YouTube"

