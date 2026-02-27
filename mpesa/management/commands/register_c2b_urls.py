"""
Management command to register C2B validation and confirmation URLs with Safaricom.
Usage: python manage.py register_c2b_urls
"""

from django.core.management.base import BaseCommand
from decouple import config

from mpesa.services import MpesaC2BService


class Command(BaseCommand):
    help = 'Register M-Pesa C2B validation and confirmation URLs with Safaricom'

    def add_arguments(self, parser):
        parser.add_argument(
            '--validation-url',
            type=str,
            help='Override the validation URL (default: from MPESA_C2B_VALIDATION_URL env var)'
        )
        parser.add_argument(
            '--confirmation-url',
            type=str,
            help='Override the confirmation URL (default: from MPESA_C2B_CONFIRMATION_URL env var)'
        )

    def handle(self, *args, **options):
        validation_url = options.get('validation_url') or config('MPESA_C2B_VALIDATION_URL', default='')
        confirmation_url = options.get('confirmation_url') or config('MPESA_C2B_CONFIRMATION_URL', default='')

        if not validation_url or not confirmation_url:
            self.stderr.write(self.style.ERROR(
                'Both MPESA_C2B_VALIDATION_URL and MPESA_C2B_CONFIRMATION_URL must be set.\n'
                'Set them in your .env file or pass --validation-url and --confirmation-url arguments.'
            ))
            return

        self.stdout.write(f'Registering C2B URLs...')
        self.stdout.write(f'  Validation:   {validation_url}')
        self.stdout.write(f'  Confirmation: {confirmation_url}')

        service = MpesaC2BService()
        result = service.register_urls(validation_url, confirmation_url)

        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'C2B URLs registered successfully: {result["message"]}'))
        else:
            self.stderr.write(self.style.ERROR(f'Failed to register C2B URLs: {result["message"]}'))
