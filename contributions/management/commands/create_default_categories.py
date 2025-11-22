"""
Management command to create default contribution categories.
Following DRY: Reusable command for setting up initial data.
"""

from django.core.management.base import BaseCommand
from contributions.models import ContributionCategory


class Command(BaseCommand):
    help = 'Creates default contribution categories'

    def handle(self, *args, **options):
        """Create default contribution categories"""

        default_categories = [
            {
                'name': 'Tithe',
                'code': 'TITHE',
                'description': 'Regular tithe contributions (10% of income)'
            },
            {
                'name': 'Offering',
                'code': 'OFFER',
                'description': 'General offerings and donations'
            },
            {
                'name': 'Building Fund',
                'code': 'BUILD',
                'description': 'Contributions towards building projects'
            },
            {
                'name': 'Missions',
                'code': 'MISSION',
                'description': 'Support for missionary work'
            },
            {
                'name': 'Welfare',
                'code': 'WELFARE',
                'description': 'Helping members in need'
            },
            {
                'name': 'Special Events',
                'code': 'EVENT',
                'description': 'Special church events and activities'
            },
        ]

        created_count = 0
        skipped_count = 0

        for category_data in default_categories:
            category, created = ContributionCategory.objects.get_or_create(
                code=category_data['code'],
                defaults={
                    'name': category_data['name'],
                    'description': category_data['description'],
                    'is_active': True
                }
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f' Created category: {category.name} ({category.code})'
                    )
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'- Category already exists: {category.name} ({category.code})'
                    )
                )
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {created_count} created, {skipped_count} skipped'
            )
        )