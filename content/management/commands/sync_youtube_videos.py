"""
Django management command to sync YouTube videos from channel and playlists.
"""
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from content.youtube_service import YouTubeService
from content.models import YouTubeVideo

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync YouTube videos from channel and/or playlists'

    def add_arguments(self, parser):
        parser.add_argument(
            '--channel',
            action='store_true',
            help='Sync videos from the configured YouTube channel'
        )
        parser.add_argument(
            '--playlist',
            type=str,
            help='Sync videos from a specific playlist ID'
        )
        parser.add_argument(
            '--video-id',
            type=str,
            help='Sync a specific video by its ID'
        )
        parser.add_argument(
            '--max-results',
            type=int,
            default=50,
            help='Maximum number of videos to fetch (default: 50)'
        )
        parser.add_argument(
            '--category',
            type=str,
            default='sermon',
            choices=['sermon', 'worship', 'testimony', 'teaching', 'event', 'other'],
            help='Category to assign to synced videos (default: sermon)'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        try:
            # Initialize YouTube service
            youtube_service = YouTubeService()

            stats = {
                'created': 0,
                'updated': 0,
                'errors': 0
            }

            # Sync from channel
            if options['channel']:
                self._sync_from_channel(youtube_service, options, stats)

            # Sync from specific playlist
            elif options['playlist']:
                self._sync_from_playlist(
                    youtube_service,
                    options['playlist'],
                    options,
                    stats
                )

            # Sync specific video
            elif options['video_id']:
                self._sync_specific_video(
                    youtube_service,
                    options['video_id'],
                    options,
                    stats
                )

            # Default: sync from configured channel and playlists
            else:
                self._sync_default(youtube_service, options, stats)

            # Print summary
            self.stdout.write(self.style.SUCCESS(
                f"\nSync completed: {stats['created']} created, "
                f"{stats['updated']} updated, {stats['errors']} errors"
            ))

        except Exception as e:
            raise CommandError(f"Error syncing videos: {e}")

    def _sync_from_channel(self, youtube_service, options, stats):
        """Sync videos from the configured channel."""
        channel_id = settings.YOUTUBE_CHANNEL_ID

        if not channel_id:
            self.stdout.write(self.style.WARNING(
                'No channel ID configured in settings. Set YOUTUBE_CHANNEL_ID.'
            ))
            return

        self.stdout.write(f"Fetching videos from channel: {channel_id}")

        try:
            videos = youtube_service.fetch_channel_videos(
                channel_id,
                max_results=options['max_results']
            )

            self.stdout.write(f"Found {len(videos)} videos")

            for video_data in videos:
                self._sync_video(
                    youtube_service,
                    video_data,
                    'channel',
                    channel_id,
                    None,
                    options['category'],
                    stats
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching channel videos: {e}"))
            stats['errors'] += 1

    def _sync_from_playlist(self, youtube_service, playlist_id, options, stats):
        """Sync videos from a specific playlist."""
        self.stdout.write(f"Fetching videos from playlist: {playlist_id}")

        try:
            videos = youtube_service.fetch_playlist_videos(
                playlist_id,
                max_results=options['max_results']
            )

            self.stdout.write(f"Found {len(videos)} videos")

            for video_data in videos:
                self._sync_video(
                    youtube_service,
                    video_data,
                    'playlist',
                    None,
                    playlist_id,
                    options['category'],
                    stats
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching playlist videos: {e}"))
            stats['errors'] += 1

    def _sync_specific_video(self, youtube_service, video_id, options, stats):
        """Sync a specific video by ID."""
        self.stdout.write(f"Fetching video: {video_id}")

        try:
            videos = youtube_service.get_video_details([video_id])

            if not videos:
                self.stdout.write(self.style.WARNING(f"Video {video_id} not found"))
                return

            video_data = videos[0]
            self._sync_video(
                youtube_service,
                video_data,
                'manual',
                None,
                None,
                options['category'],
                stats
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching video: {e}"))
            stats['errors'] += 1

    def _sync_default(self, youtube_service, options, stats):
        """Sync from configured channel and playlists."""
        # Sync from channel
        if settings.YOUTUBE_CHANNEL_ID:
            self._sync_from_channel(youtube_service, options, stats)

        # Sync from configured playlists
        for playlist_id in settings.YOUTUBE_PLAYLIST_IDS:
            if playlist_id:
                self._sync_from_playlist(youtube_service, playlist_id, options, stats)

        if not settings.YOUTUBE_CHANNEL_ID and not settings.YOUTUBE_PLAYLIST_IDS:
            self.stdout.write(self.style.WARNING(
                'No channel or playlists configured. Set YOUTUBE_CHANNEL_ID '
                'and/or YOUTUBE_PLAYLIST_IDS in settings.'
            ))

    def _sync_video(self, youtube_service, video_data, source, channel_id, playlist_id, category, stats):
        """Sync a single video to the database."""
        try:
            # Check if video already exists
            existing = YouTubeVideo.objects.filter(video_id=video_data['video_id']).first()

            video = youtube_service.sync_video_to_db(
                video_data,
                source=source,
                channel_id=channel_id,
                playlist_id=playlist_id,
                category=category
            )

            if existing:
                stats['updated'] += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Updated: {video.title}"))
            else:
                stats['created'] += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Created: {video.title}"))

        except Exception as e:
            stats['errors'] += 1
            self.stdout.write(self.style.ERROR(
                f"✗ Error syncing {video_data.get('title', 'unknown')}: {e}"
            ))
