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
