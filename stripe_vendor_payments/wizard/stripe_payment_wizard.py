# -*- coding: utf-8 -*-

from odoo import models, fields, api
try:
    import stripe
except ImportError:
    stripe = None
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class StripePaymentWizard(models.TransientModel):
    _name = 'stripe.payment.wizard'
    _description = 'Stripe Payment Wizard'
    
    invoice_id = fields.Many2one('account.move', string='Invoice', required=True)
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True)
    stripe_account_id = fields.Char(string='Stripe Account ID', required=True)
    amount = fields.Monetary(string='Amount to Pay', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    payment_description = fields.Char(string='Payment Description', 
                                     default='Payment for vendor bill')
    
    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            self.partner_id = self.invoice_id.partner_id
            self.amount = self.invoice_id.amount_residual
            self.currency_id = self.invoice_id.currency_id
            self.payment_description = f'Payment for {self.invoice_id.name}'
    
    def action_send_payment(self):
        """Send payment to vendor via Stripe"""
        self.ensure_one()
        
        # Validate
        if self.amount <= 0:
            raise UserError('Payment amount must be greater than zero.')
        
        if not self.partner_id.stripe_payouts_enabled:
            raise UserError('Vendor has not completed Stripe onboarding. Payouts are not enabled.')
        
        # Check if payment was already made for this invoice
        if self.invoice_id.stripe_payment_id:
            # Check if the transfer actually exists in Stripe
            stripe_config = self.env['stripe.config'].get_stripe_config()
            stripe_api = stripe_config.init_stripe()
            try:
                existing_transfer = stripe_api.Transfer.retrieve(self.invoice_id.stripe_payment_id)
                if existing_transfer and existing_transfer.id:
                    raise UserError(f'Payment already sent for this invoice. Transfer ID: {existing_transfer.id}')
            except stripe.error.StripeError:
                # Transfer doesn't exist in Stripe, clear the field and continue
                self.invoice_id.stripe_payment_id = False
        
        # Get Stripe configuration
        stripe_config = self.env['stripe.config'].get_stripe_config()
        stripe_api = stripe_config.init_stripe()
        
        try:
            # Amount is in cents for USD
            amount_cents = int(self.amount * 100)
            
            # Use invoice ID and amount as idempotency key to prevent duplicates
            idempotency_key = f"odoo_invoice_{self.invoice_id.id}_amount_{amount_cents}"
            
            # For ACH: Use transfer which will automatically trigger a payout to their bank
            # Stripe Connect handles the ACH transfer to their bank account
            try:
                # Create a transfer to the connected account
                # This adds funds to their Stripe balance
                transfer = stripe_api.Transfer.create(
                    amount=amount_cents,
                    currency=self.currency_id.name.lower(),
                    destination=self.stripe_account_id,
                    description=self.payment_description,
                    metadata={
                        'odoo_invoice_id': str(self.invoice_id.id),
                        'odoo_invoice_name': self.invoice_id.name,
                        'odoo_partner_id': str(self.partner_id.id),
                        'odoo_partner_name': self.partner_id.name,
                    },
                    idempotency_key=idempotency_key
                )
                
                transfer_or_payout_id = transfer.id
                _logger.info(f"Created transfer: {transfer.id} for ${self.amount:.2f}")
                
                # Stripe will automatically create an ACH payout to their bank account
                # if they have automatic payouts enabled (which is the default)
                _logger.info("Note: Stripe will automatically send an ACH payout to vendor's bank account")
                
            except stripe.error.StripeError as e:
                _logger.error(f"Transfer failed: {str(e)}")
                raise UserError(f"Failed to send payment: {str(e)}")
            
            # Update invoice with payment info
            self.invoice_id.write({
                'stripe_payment_id': transfer_or_payout_id,
                'stripe_payment_status': 'succeeded',
                'stripe_payment_amount': self.amount,
            })
            
            # Create payment record in Odoo (register payment)
            # Pass a dict with the ID since we might have either a payout or transfer
            payment_info = {'id': transfer_or_payout_id}
            self._create_payment_record(payment_info)
            
            # Show success message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Payment Sent Successfully',
                    'message': f'Payment of {self.currency_id.symbol}{self.amount:.2f} sent to {self.partner_id.name}. Transaction ID: {transfer_or_payout_id}',
                    'type': 'success',
                    'sticky': True,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
            
        except stripe.error.StripeError as e:
            _logger.error(f"Stripe error sending payment: {str(e)}")
            
            # Update invoice status
            self.invoice_id.write({
                'stripe_payment_status': 'failed',
            })
            
            raise UserError(f'Failed to send payment: {str(e)}')
    
    def _create_payment_record(self, payment_info):
        """Create an Odoo payment record for the Stripe transfer or payout"""
        # Find or create payment journal
        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('name', 'ilike', 'stripe')
        ], limit=1)
        
        if not journal:
            # Create a Stripe journal if it doesn't exist
            journal = self.env['account.journal'].create({
                'name': 'Stripe Payments',
                'type': 'bank',
                'code': 'STRP',
            })
            _logger.info(f"Created new Stripe payment journal: {journal.name}")
        
        # Create payment using the register payment wizard approach
        # This ensures proper reconciliation
        payment_register = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=self.invoice_id.ids
        ).create({
            'payment_date': fields.Date.today(),
            'journal_id': journal.id,
            'payment_method_line_id': journal.inbound_payment_method_line_ids[0].id if self.invoice_id.move_type == 'out_invoice' else journal.outbound_payment_method_line_ids[0].id,
            'amount': self.amount,
            'communication': f'Stripe Payment: {payment_info["id"]}',  # Use 'communication' instead of 'payment_reference'
        })
        
        # Create and post the payment
        payment = payment_register._create_payments()
        
        _logger.info(f"Payment created and reconciled: {payment.id}, State: {payment.state}, Invoice: {self.invoice_id.payment_state}")
        
        return payment
    
    def action_check_vendor_status(self):
        """Check if vendor is ready to receive payments"""
        self.ensure_one()
        
        if not self.partner_id:
            raise UserError('Please select a vendor first.')
        
        # Trigger status check on partner
        return self.partner_id.action_check_stripe_status()