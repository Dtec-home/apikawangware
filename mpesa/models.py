from django.db import models
from django.core.validators import RegexValidator
from core.models import TimeStampedModel


class MpesaTransaction(TimeStampedModel):
    """
    Stores M-Pesa transaction records initiated by the system.
    Following SRP: Only responsible for transaction data storage.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    phone_validator = RegexValidator(
        regex=r'^254\d{9}$',
        message="Phone number must be in format 254XXXXXXXXX"
    )

    # Transaction identification
    merchant_request_id = models.CharField(max_length=100, unique=True)
    checkout_request_id = models.CharField(max_length=100, unique=True)

    # Transaction details
    phone_number = models.CharField(
        max_length=12,
        validators=[phone_validator],
        db_index=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    account_reference = models.CharField(max_length=100)  # Category code
    transaction_desc = models.CharField(max_length=255)

    # M-Pesa response
    mpesa_receipt_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        db_index=True
    )
    transaction_date = models.DateTimeField(null=True, blank=True)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    result_desc = models.TextField(blank=True, null=True)
    result_code = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'status']),
            models.Index(fields=['phone_number', '-created_at']),
        ]
        verbose_name = 'M-Pesa Transaction'
        verbose_name_plural = 'M-Pesa Transactions'

    def __str__(self):
        return f"{self.phone_number} - KES {self.amount} - {self.status}"

    @property
    def is_successful(self):
        """Check if transaction completed successfully"""
        return self.status == 'completed' and self.result_code == '0'


class MpesaCallback(TimeStampedModel):
    """
    Stores raw M-Pesa callback data for audit and debugging.
    Following SRP: Only responsible for callback data storage.
    """

    merchant_request_id = models.CharField(max_length=100, db_index=True)
    checkout_request_id = models.CharField(max_length=100, db_index=True)
    result_code = models.CharField(max_length=10)
    result_desc = models.TextField()

    # Raw callback data (for debugging and audit)
    raw_data = models.JSONField()

    # Link to transaction
    transaction = models.ForeignKey(
        MpesaTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='callbacks'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'M-Pesa Callback'
        verbose_name_plural = 'M-Pesa Callbacks'

    def __str__(self):
        return f"Callback - {self.checkout_request_id} - {self.result_code}"


class C2BTransaction(TimeStampedModel):
    """
    Stores M-Pesa C2B (Customer to Business) transaction records.
    These originate from customers paying via the M-Pesa menu directly
    (Pay Bill), not from STK Push initiated by the system.
    """

    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processed', 'Processed'),
        ('unmatched', 'Unmatched'),
        ('failed', 'Failed'),
    ]

    MATCH_METHOD_CHOICES = [
        ('exact', 'Exact'),
        ('fuzzy', 'Fuzzy'),
        ('manual', 'Manual'),
    ]

    phone_validator = RegexValidator(
        regex=r'^254\d{9}$',
        message="Phone number must be in format 254XXXXXXXXX"
    )

    # M-Pesa transaction ID (unique receipt number from Safaricom)
    trans_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="M-Pesa transaction ID (e.g., RKTQDM7W6S)"
    )
    trans_time = models.DateTimeField(
        help_text="Transaction timestamp from M-Pesa"
    )
    trans_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount paid by customer"
    )
    business_short_code = models.CharField(
        max_length=20,
        help_text="Business short code (Pay Bill number)"
    )
    bill_ref_number = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Account reference entered by customer (maps to category code)"
    )
    msisdn = models.CharField(
        max_length=12,
        validators=[phone_validator],
        db_index=True,
        help_text="Customer phone number in 254XXXXXXXXX format"
    )

    # Customer name from M-Pesa
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    # Organization balance after transaction
    org_account_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Organization account balance after transaction"
    )

    # Processing status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='received',
        db_index=True
    )
    validation_result = models.CharField(
        max_length=20,
        blank=True,
        help_text="Result of validation: accepted or rejected"
    )
    matched_category_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Category code that was actually matched (useful for fuzzy matches)"
    )
    match_method = models.CharField(
        max_length=10,
        choices=MATCH_METHOD_CHOICES,
        blank=True,
        help_text="How the category was matched: exact, fuzzy, or manual"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'status']),
            models.Index(fields=['msisdn', '-created_at']),
            models.Index(fields=['bill_ref_number', '-created_at']),
        ]
        verbose_name = 'C2B Transaction'
        verbose_name_plural = 'C2B Transactions'

    def __str__(self):
        return f"C2B {self.trans_id} - {self.msisdn} - KES {self.trans_amount} - {self.bill_ref_number}"


class C2BCallback(TimeStampedModel):
    """
    Stores raw C2B callback data for audit and debugging.
    Follows the same pattern as MpesaCallback for STK Push.
    """

    CALLBACK_TYPE_CHOICES = [
        ('validation', 'Validation'),
        ('confirmation', 'Confirmation'),
    ]

    callback_type = models.CharField(
        max_length=20,
        choices=CALLBACK_TYPE_CHOICES,
        db_index=True,
        help_text="Whether this was a validation or confirmation callback"
    )
    trans_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="M-Pesa transaction ID from callback"
    )
    raw_data = models.JSONField(
        help_text="Complete raw callback payload for audit"
    )
    processed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this callback has been fully processed"
    )

    # Link to C2B transaction
    transaction = models.ForeignKey(
        C2BTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='callbacks'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'C2B Callback'
        verbose_name_plural = 'C2B Callbacks'

    def __str__(self):
        return f"C2B {self.callback_type} - {self.trans_id}"
