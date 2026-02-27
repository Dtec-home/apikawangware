"""
Management command to simulate a C2B payment in the Daraja sandbox.
Usage: python manage.py simulate_c2b --phone 254708374149 --amount 500 --ref TITHE
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from mpesa.services import MpesaC2BService


class Command(BaseCommand):
    help = 'Simulate a C2B (Pay Bill) payment in the M-Pesa sandbox'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            required=True,
            help='Customer phone number (254XXXXXXXXX format)'
        )
        parser.add_argument(
            '--amount',
            type=str,
            required=True,
            help='Payment amount in KES'
        )
        parser.add_argument(
            '--ref',
            type=str,
            required=True,
            help='Bill reference number (category code, e.g., TITHE, OFFER)'
        )

    def handle(self, *args, **options):
        phone_number = options['phone']
        amount = Decimal(options['amount'])
        bill_ref = options['ref']

        self.stdout.write(f'Simulating C2B payment...')
        self.stdout.write(f'  Phone:  {phone_number}')
        self.stdout.write(f'  Amount: KES {amount}')
        self.stdout.write(f'  Ref:    {bill_ref}')

        service = MpesaC2BService()
        result = service.simulate_c2b(phone_number, amount, bill_ref)

        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'Simulation successful: {result["message"]}'))
        else:
            self.stderr.write(self.style.ERROR(f'Simulation failed: {result["message"]}'))
