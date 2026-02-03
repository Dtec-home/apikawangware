from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from core.models import TimeStampedModel, SoftDeleteModel


class ContributionCategory(TimeStampedModel, SoftDeleteModel):
    """
    Categories for different types of contributions.
    Following SRP: Only responsible for category data storage.
    Examples: Tithe, Offering, Building Fund, Missions, etc.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name (e.g., Tithe, Offering, Building Fund)"
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Short code used as M-Pesa account reference (e.g., TITHE, OFFER)"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of this category"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this category is currently accepting contributions"
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Contribution Category'
        verbose_name_plural = 'Contribution Categories'

    def __str__(self):
        return f"{self.name} ({self.code})"


class Contribution(TimeStampedModel):
    """
    Individual contribution records.
    Following SRP: Only responsible for contribution data storage.
    Links members, M-Pesa transactions, and categories.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    # Relationships
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.PROTECT,
        related_name='contributions',
        help_text="Member who made this contribution"
    )
    category = models.ForeignKey(
        ContributionCategory,
        on_delete=models.PROTECT,
        related_name='contributions',
        help_text="Category of this contribution"
    )
    mpesa_transaction = models.ForeignKey(
        'mpesa.MpesaTransaction',
        on_delete=models.PROTECT,
        related_name='contributions',
        null=True,
        blank=True,
        help_text="Associated M-Pesa transaction (multiple contributions can share one transaction)"
    )

    # Contribution grouping
    contribution_group_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="Groups multiple contributions made in a single transaction"
    )

    # Entry type
    ENTRY_TYPE_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('manual', 'Manual Entry'),
        ('cash', 'Cash'),
        ('envelope', 'Envelope'),
    ]

    entry_type = models.CharField(
        max_length=20,
        choices=ENTRY_TYPE_CHOICES,
        default='mpesa',
        db_index=True,
        help_text="How this contribution was entered into the system"
    )

    # Manual entry fields
    manual_receipt_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Receipt number for manual/cash/envelope entries"
    )

    entered_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entered_contributions',
        help_text="Admin user who entered this contribution manually"
    )

    # Contribution details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text="Contribution amount in KES"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    # Dates
    transaction_date = models.DateTimeField(
        db_index=True,
        help_text="When the contribution was made"
    )

    # Additional information
    notes = models.TextField(
        blank=True,
        help_text="Optional notes about this contribution"
    )

    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['-transaction_date', 'status']),
            models.Index(fields=['member', '-transaction_date']),
            models.Index(fields=['category', '-transaction_date']),
            models.Index(fields=['contribution_group_id', '-transaction_date']),
        ]
        verbose_name = 'Contribution'
        verbose_name_plural = 'Contributions'

    def __str__(self):
        return f"{self.member.full_name} - {self.category.name} - KES {self.amount}"

    @property
    def is_completed(self):
        """Check if contribution is completed"""
        return self.status == 'completed'


# Import CategoryAdmin to make it available for migrations
from .category_admin import CategoryAdmin
