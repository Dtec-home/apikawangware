
import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'church_BE.settings')
django.setup()

from contributions.models import Contribution

def sync_contributions():
    print("Checking for stuck contributions...")

    stuck_contributions = Contribution.objects.filter(
        status='pending',
        mpesa_transaction__status='completed'
    )

    count = stuck_contributions.count()
    print(f"Found {count} stuck contributions.")

    for contribution in stuck_contributions:
        print(f"Fixing Contribution {contribution.id}:")
        print(f"  - Member: {contribution.member.full_name}")
        print(f"  - Amount: {contribution.amount}")
        print(f"  - Transaction: {contribution.mpesa_transaction.mpesa_receipt_number}")

        contribution.status = 'completed'
        # Also sync date if missing
        if contribution.mpesa_transaction.transaction_date:
            contribution.transaction_date = contribution.mpesa_transaction.transaction_date

        contribution.save()
        print("  -> Fixed.")

if __name__ == "__main__":
    sync_contributions()
