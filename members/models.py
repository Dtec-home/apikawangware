from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, EmailValidator
from core.models import TimeStampedModel, SoftDeleteModel


class Member(TimeStampedModel, SoftDeleteModel):
    """
    Member model for church members.
    Following SRP: Only responsible for member data storage.
    Inherits timestamp and soft delete functionality from base models (DRY).
    """

    phone_validator = RegexValidator(
        regex=r'^254\d{9}$',
        message="Phone number must be in format 254XXXXXXXXX"
    )

    # Authentication - link to Django User
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='member',
        help_text="Linked Django user account for authentication"
    )

    # Personal information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    # Contact information
    phone_number = models.CharField(
        max_length=12,
        unique=True,
        validators=[phone_validator],
        db_index=True,
        help_text="Phone number in format 254XXXXXXXXX (for M-Pesa)"
    )
    email = models.EmailField(
        blank=True,
        null=True,
        validators=[EmailValidator()],
        help_text="Optional email address"
    )

    # Member identification
    member_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique member identification number"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether the member is currently active"
    )

    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['is_active', '-created_at']),
        ]
        verbose_name = 'Member'
        verbose_name_plural = 'Members'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.member_number})"

    @property
    def full_name(self):
        """Get member's full name"""
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        """Override save to auto-generate member number if not provided"""
        if not self.member_number:
            # Generate member number based on last member + 1
            last_member = Member.objects.order_by('-id').first()
            if last_member and last_member.member_number.isdigit():
                self.member_number = str(int(last_member.member_number) + 1).zfill(6)
            else:
                self.member_number = '000001'
        super().save(*args, **kwargs)


# Import OTP and UserRole models to make them available for migrations
from .otp import OTP
from .roles import UserRole
