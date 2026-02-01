"""
YouTube API service for fetching and syncing videos.
"""
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from django.conf import settings
from django.utils import timezone as django_timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .models import YouTubeVideo

logger = logging.getLogger(__name__)


class YouTubeService:
    """Service class for interacting with YouTube Data API v3."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize YouTube service.

        Args:
            api_key: YouTube Data API v3 key. If not provided, uses settings.YOUTUBE_API_KEY
        """
        self.api_key = api_key or settings.YOUTUBE_API_KEY
        if not self.api_key:
            raise ValueError("YouTube API key is required. Set YOUTUBE_API_KEY in settings.")

        self.youtube = build('youtube', 'v3', developerKey=self.api_key)

    def fetch_channel_videos(self, channel_id: str, max_results: int = 50) -> List[Dict]:
        """
        Fetch latest videos from a YouTube channel.

        Args:
            channel_id: YouTube channel ID
            max_results: Maximum number of videos to fetch (default: 50, max: 50)

        Returns:
            List of video data dictionaries
        """
        try:
            # First, get the uploads playlist ID for the channel
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()

            if not channel_response.get('items'):
                logger.warning(f"Channel {channel_id} not found")
                return []

            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            # Fetch videos from the uploads playlist
            return self.fetch_playlist_videos(uploads_playlist_id, max_results)

        except HttpError as e:
            logger.error(f"Error fetching channel videos: {e}")
            raise

    def fetch_playlist_videos(self, playlist_id: str, max_results: int = 50) -> List[Dict]:
        """
        Fetch videos from a YouTube playlist.

        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum number of videos to fetch (default: 50, max: 50)

        Returns:
            List of video data dictionaries
        """
        try:
            videos = []
            next_page_token = None

            while len(videos) < max_results:
                # Fetch playlist items
                playlist_response = self.youtube.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=playlist_id,
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token
                ).execute()

                if not playlist_response.get('items'):
                    break

                # Extract video IDs
                video_ids = [item['contentDetails']['videoId'] for item in playlist_response['items']]

                # Fetch detailed video information
                video_details = self.get_video_details(video_ids)
                videos.extend(video_details)

                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token:
                    break

            return videos

        except HttpError as e:
            logger.error(f"Error fetching playlist videos: {e}")
            raise

    def get_video_details(self, video_ids: List[str]) -> List[Dict]:
        """
        Get detailed information for specific video IDs.

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            List of video data dictionaries with detailed information
        """
        try:
            if not video_ids:
                return []

            # Fetch video details
            video_response = self.youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=','.join(video_ids)
            ).execute()

            videos = []
            for item in video_response.get('items', []):
                video_data = self._parse_video_data(item)
                videos.append(video_data)

            return videos

        except HttpError as e:
            logger.error(f"Error fetching video details: {e}")
            raise

    def _parse_video_data(self, item: Dict) -> Dict:
        """
        Parse YouTube API video item into a standardized dictionary.

        Args:
            item: YouTube API video item

        Returns:
            Parsed video data dictionary
        """
        snippet = item['snippet']
        content_details = item.get('contentDetails', {})
        statistics = item.get('statistics', {})

        # Parse ISO 8601 duration (e.g., PT15M33S -> 933 seconds)
        duration_str = content_details.get('duration', 'PT0S')
        duration_seconds = self._parse_duration(duration_str)

        return {
            'video_id': item['id'],
            'title': snippet['title'],
            'description': snippet.get('description', ''),
            'channel_id': snippet['channelId'],
            'published_at': snippet['publishedAt'],
            'duration': duration_seconds,
            'view_count': int(statistics.get('viewCount', 0)),
            'like_count': int(statistics.get('likeCount', 0)),
        }

    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse ISO 8601 duration string to seconds.

        Args:
            duration_str: ISO 8601 duration string (e.g., PT15M33S)

        Returns:
            Duration in seconds
        """
        import re

        # Match hours, minutes, and seconds
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)

        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds

    def sync_video_to_db(
        self,
        video_data: Dict,
        source: str,
        channel_id: Optional[str] = None,
        playlist_id: Optional[str] = None,
        category: str = 'sermon'
    ) -> YouTubeVideo:
        """
        Save or update a video in the database.

        Args:
            video_data: Video data dictionary from YouTube API
            source: Video source ('channel' or 'playlist')
            channel_id: YouTube channel ID (optional)
            playlist_id: YouTube playlist ID (optional)
            category: Video category (default: 'sermon')

        Returns:
            YouTubeVideo instance
        """
        video_id = video_data['video_id']

        # Parse YouTube published date
        youtube_published_at = datetime.fromisoformat(
            video_data['published_at'].replace('Z', '+00:00')
        )

        # Check if video already exists
        video, created = YouTubeVideo.objects.update_or_create(
            video_id=video_id,
            defaults={
                'title': video_data['title'][:200],  # Truncate to max length
                'description': video_data['description'],
                'source': source,
                'channel_id': channel_id or video_data.get('channel_id', ''),
                'playlist_id': playlist_id or '',
                'youtube_published_at': youtube_published_at,
                'publish_date': youtube_published_at,  # Use YouTube publish date
                'duration': video_data.get('duration'),
                'view_count': video_data.get('view_count'),
                'like_count': video_data.get('like_count'),
                'last_synced_at': django_timezone.now(),
                'category': category,
            }
        )

        action = "Created" if created else "Updated"
        logger.info(f"{action} video: {video.title} ({video_id})")

        return video
