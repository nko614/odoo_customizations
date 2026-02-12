# Stripe Vendor Payments Module for Odoo

## Overview
This MVP Odoo module allows you to send payments to vendors via Stripe Connect. It extends the vendor bill functionality to enable direct payments to vendor bank accounts through Stripe.

## Features
✅ **Send payments to vendors via Stripe**
✅ **KYC onboarding directly from Odoo**
✅ **Extend vendor bill 'Pay' functionality**
✅ **Track payment status**
✅ **Automatic payment reconciliation**

## Installation

### 1. Install Python Dependencies
```bash
pip install stripe
```

### 2. Add Module to Odoo
1. Copy the `stripe_vendor_payments` folder to your Odoo addons directory
2. Update the addons path in your Odoo configuration file to include:
   ```
   /Users/nicholaskosinski/Desktop/2024_reporting/odoo_dev/custom_addons
   ```
3. Restart Odoo server
4. Go to Apps → Update Apps List
5. Search for "Stripe Vendor Payments"
6. Click Install

## Configuration

### Stripe API Keys
The module comes pre-configured with your test API keys:
- **Publishable Key**: pk_test_51S1ojFRK33XhtUdI...
- **Secret Key**: sk_test_51S1ojFRK33XhtUdI...

These are configured in Settings → Technical → Stripe Configuration

## Usage

### 1. Setting Up a Vendor for Stripe Payments

1. Go to **Contacts** → Select a vendor
2. Navigate to the **Stripe** tab
3. Click **"Create Stripe Account"** - This creates a Stripe Connect account
4. Click **"Complete KYC Onboarding"** - Opens Stripe's KYC flow in a new tab
5. Vendor completes the onboarding process
6. Click **"Check Status"** to verify onboarding is complete

### 2. Sending Payment to Vendor

1. Go to **Accounting** → **Vendor Bills**
2. Open a posted vendor bill
3. Click **"Send via Stripe"** button (next to Register Payment)
4. Review payment details in the wizard
5. Click **"Send Payment"**

The payment will be:
- Sent to the vendor's Stripe account
- Automatically recorded in Odoo
- Reconciled with the vendor bill

### 3. Monitoring Payment Status

Each vendor bill shows:
- Stripe Payment ID
- Payment Status (Pending/Processing/Succeeded/Failed)
- Payment Amount

## How It Works

### KYC Onboarding Flow
1. **Create Account**: Creates a Stripe Express Connect account for the vendor
2. **Generate Link**: Creates a unique onboarding link for KYC
3. **Vendor Completes**: Vendor provides required information to Stripe
4. **Status Check**: Odoo verifies account is ready for payouts

### Payment Flow
1. **Initiate**: Click "Send via Stripe" on vendor bill
2. **Transfer**: Creates a Stripe transfer to vendor's connected account
3. **Record**: Automatically creates payment record in Odoo
4. **Reconcile**: Links payment with vendor bill

## Module Structure
```
stripe_vendor_payments/
├── __init__.py
├── __manifest__.py
├── requirements.txt
├── models/
│   ├── __init__.py
│   ├── stripe_config.py       # Stripe configuration
│   ├── res_partner.py         # Vendor Stripe fields
│   └── account_move.py        # Bill payment extension
├── wizard/
│   ├── __init__.py
│   └── stripe_payment_wizard.py  # Payment wizard
├── views/
│   ├── res_partner_views.xml     # Vendor form additions
│   ├── account_move_views.xml    # Bill form additions
│   └── stripe_payment_wizard_views.xml
├── data/
│   └── stripe_config.xml         # Default configuration
└── security/
    └── ir.model.access.csv       # Access rights
```

## Security Considerations
- API keys are stored in Odoo configuration (ensure proper access controls)
- Only users with accounting permissions can send payments
- Test mode is enabled by default
- All transfers are logged with metadata

## Testing

### Test Workflow
1. Create a test vendor
2. Set up Stripe account for vendor
3. Use Stripe's test onboarding (any test data works)
4. Create and post a vendor bill
5. Send test payment

### Stripe Test Mode
The module is configured in test mode. Use Stripe's test data:
- Test account numbers
- Test routing numbers
- No real money is transferred

## Limitations (MVP)
- Only supports Express accounts (simplest onboarding)
- US vendors only (can be extended)
- Basic payment flow (no refunds yet)
- Single currency per payment

## Troubleshooting

### "Vendor has not completed onboarding"
→ Click "Check Status" to update vendor's Stripe status

### "Failed to create Stripe account"
→ Check internet connection and API keys

### Payment fails
→ Verify vendor's Stripe account is active and can receive payouts

## Future Enhancements
- [ ] Support for multiple currencies
- [ ] Refund functionality
- [ ] Batch payments
- [ ] Payment scheduling
- [ ] Webhook integration for real-time status
- [ ] Support for international vendors
- [ ] Custom account types (Standard/Custom)
- [ ] Payment method selection

## Support
For issues or questions about this module, check:
1. Odoo logs for detailed error messages
2. Stripe Dashboard for payment status
3. This README for common solutions