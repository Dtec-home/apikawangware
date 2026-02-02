# Environment Variables for Mobitech SMS Integration

## Required Environment Variables

Add these to your `.env` file or deployment environment:

```bash
# Mobitech SMS API Configuration
MOBITECH_API_KEY=your_64_character_api_key_here
MOBITECH_SENDER_NAME=FULL_CIRCLE
MOBITECH_SERVICE_ID=0
MOBITECH_API_URL=https://app.mobitechtechnologies.com//sms/sendsms
```

## Removed Environment Variables

The following variables are no longer needed and can be removed:

```bash
# ❌ Remove these - no longer used
AFRICASTALKING_USERNAME
AFRICASTALKING_API_KEY
AFRICASTALKING_SENDER_ID
```

## Configuration Details

### MOBITECH_API_KEY
- **Required**: Yes
- **Format**: 64-character hexadecimal string
- **Description**: Your Mobitech API authentication key
- **Example**: `f127ac77e0453830fe9f6188582ec38cb4bb2b08cc148f1dfd38152822262713`
- **Where to get it**: From your Mobitech account dashboard

### MOBITECH_SENDER_NAME
- **Required**: Yes
- **Format**: Alphanumeric string (max 11 characters)
- **Description**: The sender name that appears on SMS messages
- **Default**: `FULL_CIRCLE`
- **Example**: `FULL_CIRCLE`, `MOBI-TECH`, `CHURCH`

### MOBITECH_SERVICE_ID
- **Required**: Yes
- **Format**: Integer
- **Description**: Service identifier for bulk messaging
- **Default**: `0`
- **Note**: Always use `0` for bulk SMS messaging

### MOBITECH_API_URL
- **Required**: No (has default)
- **Format**: URL string
- **Description**: Mobitech SMS API endpoint
- **Default**: `https://app.mobitechtechnologies.com//sms/sendsms`
- **Note**: Only change if Mobitech updates their API endpoint

## Testing

To test the SMS integration:

1. Set up the environment variables in your `.env` file
2. Restart your Django server
3. Test OTP sending by requesting an OTP via the API
4. Test receipt sending by making a test M-Pesa contribution

## Development Mode

In development mode (when `DEBUG=True` and `MOBITECH_API_KEY` is not set), the system will:
- Print SMS messages to the console instead of sending them
- Still log all SMS attempts for debugging
- Return success responses for testing

This allows you to develop and test without consuming SMS credits.
