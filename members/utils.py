"""
Utility functions for members app.
"""

import re


def normalize_phone_number(phone: str) -> str:
    """
    Normalize Kenyan phone numbers to the format 254XXXXXXXXX.

    Accepts various formats:
    - +254 797 030 300
    - +254797030300
    - 254797030300
    - 0797030300
    - 797030300

    Args:
        phone: Phone number in any common format

    Returns:
        Normalized phone number in format 254XXXXXXXXX

    Raises:
        ValueError: If phone number is invalid
    """
    if not phone:
        raise ValueError("Phone number is required")

    # Remove all spaces, dashes, parentheses, and other non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)

    # Remove leading + if present
    if cleaned.startswith('+'):
        cleaned = cleaned[1:]

    # Handle different formats
    if cleaned.startswith('254'):
        # Already in correct format (254XXXXXXXXX)
        normalized = cleaned
    elif cleaned.startswith('0'):
        # Local format (0797030300) -> remove leading 0 and add 254
        normalized = '254' + cleaned[1:]
    elif len(cleaned) == 9:
        # Just the 9 digits without country code (797030300)
        normalized = '254' + cleaned
    else:
        # Unknown format
        raise ValueError(f"Invalid phone number format: {phone}")

    # Validate final format: must be exactly 12 digits (254 + 9 digits)
    if not re.match(r'^254\d{9}$', normalized):
        raise ValueError(
            f"Invalid Kenyan phone number: {phone}. "
            "Must be a valid Kenyan number (e.g., +254 797 030 300, 0797030300)"
        )

    return normalized
