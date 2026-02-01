from django.db import models
from django.core.validators import URLValidator
from core.models import TimeStampedModel, SoftDeleteModel


class Announcement(TimeStampedModel, SoftDeleteModel):
    """
    Church announcements for the landing page.
    Following SRP: Only responsible for announcement data storage.
    """

    title = models.CharField(
        max_length=200,
        help_text="Announcement title"
    )
    content = models.TextField(
        help_text="Announcement content/description"
    )
    publish_date = models.DateTimeField(
        db_index=True,
        help_text="When this announcement should be published"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this announcement is currently active"
    )
    priority = models.IntegerField(
        default=0,
        help_text="Higher priority announcements appear first (0 is lowest)"
    )

    class Meta:
        ordering = ['-priority', '-publish_date']
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
        indexes = [
            models.Index(fields=['-priority', '-publish_date']),
            models.Index(fields=['is_active', '-publish_date']),
        ]

    def __str__(self):
        return self.title


class Devotional(TimeStampedModel, SoftDeleteModel):
    """
    Daily devotionals/blog posts for the church website.
    Following SRP: Only responsible for devotional data storage.
    """

    title = models.CharField(
        max_length=200,
        help_text="Devotional title"
    )
    content = models.TextField(
        help_text="Devotional content (supports markdown)"
    )
    author = models.CharField(
        max_length=100,
        help_text="Author name"
    )
    scripture_reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="Bible scripture reference (e.g., John 3:16)"
    )
    publish_date = models.DateTimeField(
        db_index=True,
        help_text="Publication date"
    )
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this devotional is published"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured devotionals appear prominently on the landing page"
    )
    featured_image_url = models.URLField(
        blank=True,
        validators=[URLValidator()],
        help_text="Optional featured image URL"
    )

    class Meta:
        ordering = ['-publish_date']
        verbose_name = 'Devotional'
        verbose_name_plural = 'Devotionals'
        indexes = [
            models.Index(fields=['is_published', '-publish_date']),
            models.Index(fields=['is_featured', '-publish_date']),
        ]

    def __str__(self):
        return f"{self.title} - {self.author}"


class Event(TimeStampedModel, SoftDeleteModel):
    """
    Church events for the landing page.
    Following SRP: Only responsible for event data storage.
    """

    title = models.CharField(
        max_length=200,
        help_text="Event title"
    )
    description = models.TextField(
        help_text="Event description"
    )
    event_date = models.DateField(
        db_index=True,
        help_text="Event date"
    )
    event_time = models.TimeField(
        help_text="Event time"
    )
    location = models.CharField(
        max_length=300,
        help_text="Event location/venue"
    )
    registration_link = models.URLField(
        blank=True,
        validators=[URLValidator()],
        help_text="Optional registration/RSVP link"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this event is currently active"
    )
    featured_image_url = models.URLField(
        blank=True,
        validators=[URLValidator()],
        help_text="Optional featured image URL"
    )

    class Meta:
        ordering = ['event_date', 'event_time']
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        indexes = [
            models.Index(fields=['is_active', 'event_date']),
            models.Index(fields=['event_date', 'event_time']),
        ]

    def __str__(self):
        return f"{self.title} - {self.event_date}"


class YouTubeVideo(TimeStampedModel, SoftDeleteModel):
    """
    YouTube videos from the church's channel.
    Following SRP: Only responsible for video data storage.
    """

    CATEGORY_CHOICES = [
        ('sermon', 'Sermon'),
        ('worship', 'Worship'),
        ('testimony', 'Testimony'),
        ('teaching', 'Teaching'),
        ('event', 'Event'),
        ('other', 'Other'),
    ]

    SOURCE_CHOICES = [
        ('manual', 'Manual Entry'),
        ('channel', 'YouTube Channel'),
        ('playlist', 'YouTube Playlist'),
    ]

    title = models.CharField(
        max_length=200,
        help_text="Video title"
    )
    video_id = models.CharField(
        max_length=20,
        unique=True,
        help_text="YouTube video ID (e.g., dQw4w9WgXcQ from youtube.com/watch?v=dQw4w9WgXcQ)"
    )
    description = models.TextField(
        blank=True,
        help_text="Video description"
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other',
        help_text="Video category"
    )
    publish_date = models.DateTimeField(
        db_index=True,
        help_text="Publication date"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured videos appear prominently on the landing page"
    )

    # YouTube API sync fields
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='manual',
        db_index=True,
        help_text="Source of the video (manual entry, channel sync, or playlist sync)"
    )
    channel_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="YouTube channel ID (populated for synced videos)"
    )
    playlist_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="YouTube playlist ID (populated for playlist-synced videos)"
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this video was synced from YouTube API"
    )
    youtube_published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Original YouTube publication date"
    )
    duration = models.IntegerField(
        null=True,
        blank=True,
        help_text="Video duration in seconds"
    )
    view_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="YouTube view count (updated on sync)"
    )
    like_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="YouTube like count (updated on sync)"
    )

    class Meta:
        ordering = ['-publish_date']
        verbose_name = 'YouTube Video'
        verbose_name_plural = 'YouTube Videos'
        indexes = [
            models.Index(fields=['-publish_date']),
            models.Index(fields=['is_featured', '-publish_date']),
            models.Index(fields=['category', '-publish_date']),
            models.Index(fields=['source', '-publish_date']),
        ]

    def __str__(self):
        return self.title

    @property
    def embed_url(self):
        """Get YouTube embed URL"""
        return f"https://www.youtube.com/embed/{self.video_id}"

    @property
    def watch_url(self):
        """Get YouTube watch URL"""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def thumbnail_url(self):
        """Get YouTube thumbnail URL"""
        return f"https://img.youtube.com/vi/{self.video_id}/maxresdefault.jpg"

