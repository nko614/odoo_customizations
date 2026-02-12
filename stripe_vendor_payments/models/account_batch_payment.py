# -*- coding: utf-8 -*-

from odoo import models, fields, api
try:
    import stripe
except ImportError:
    stripe = None
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'
    
    # Stripe batch payment fields
    stripe_batch_status = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('partial', 'Partially Sent'),
        ('sent', 'Sent'),
        ('failed', 'Failed')
    ], string='Stripe Status', default='draft')
    
    stripe_batch_sent_count = fields.Integer(
        string='Payments Sent via Stripe',
        default=0
    )
    
    stripe_batch_total_amount = fields.Monetary(
        string='Total Sent via Stripe',
        currency_field='currency_id'
    )
    
    def _get_methods_generating_files(self):
        """Override to add Stripe to methods that generate files"""
        res = super()._get_methods_generating_files()
        res.append('stripe_transfer')
        return res
    
    def validate_batch(self):
        """Override to handle Stripe payments"""
        # Check if this is a Stripe batch
        stripe_method = self.env.ref('stripe_vendor_payments.account_payment_method_stripe', raise_if_not_found=False)
        if stripe_method and self.payment_method_id == stripe_method:
            return self.validate_batch_stripe()
        return super().validate_batch()
    
    def validate_batch_stripe(self):
        """Process Stripe batch payments"""
        self.ensure_one()
        
        # Open the Stripe batch wizard
        return {
            'name': 'Send Batch via Stripe',
            'type': 'ir.actions.act_window',
            'res_model': 'stripe.batch.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_batch_payment_id': self.id,
                'default_payment_ids': [(6, 0, self.payment_ids.ids)],
            }
        }
    
    def action_send_stripe_batch(self):
        """Send all payments in this batch via Stripe"""
        self.ensure_one()
        
        if not self.payment_ids:
            raise UserError('No payments in this batch.')
        
        # Open wizard for batch processing
        return {
            'name': 'Send Batch via Stripe',
            'type': 'ir.actions.act_window',
            'res_model': 'stripe.batch.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_batch_payment_id': self.id,
                'default_payment_ids': [(6, 0, self.payment_ids.ids)],
            }
        }

class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    # Link to Stripe transfer
    stripe_transfer_id = fields.Char(
        string='Stripe Transfer ID',
        help='Stripe transfer ID for this payment'
    )
    
    stripe_transfer_status = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed')
    ], string='Stripe Status')
    
    def action_send_stripe_batch_payment(self):
        """Send selected payments via Stripe"""
        
        # Get selected payment IDs from context
        active_ids = self.env.context.get('active_ids', [])
        payments = self.browse(active_ids)
        
        # Validate all are vendor payments
        if any(p.payment_type != 'outbound' or p.partner_type != 'supplier' for p in payments):
            raise UserError('Only vendor payments can be sent via Stripe.')
        
        # Open wizard
        return {
            'name': 'Send Payments via Stripe',
            'type': 'ir.actions.act_window',
            'res_model': 'stripe.batch.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payment_ids': [(6, 0, payments.ids)],
            }
        }
    
    def send_via_stripe(self):
        """Send individual payment via Stripe"""
        self.ensure_one()
        
        if not self.partner_id.stripe_account_id:
            raise UserError(f'Vendor {self.partner_id.name} does not have a Stripe account.')
        
        if not self.partner_id.stripe_payouts_enabled:
            raise UserError(f'Vendor {self.partner_id.name} has not completed Stripe onboarding.')
        
        # Get Stripe configuration
        stripe_config = self.env['stripe.config'].get_stripe_config()
        stripe_api = stripe_config.init_stripe()
        
        try:
            # Create transfer
            amount_cents = int(self.amount * 100)
            idempotency_key = f"odoo_payment_{self.id}_amount_{amount_cents}"
            
            transfer = stripe_api.Transfer.create(
                amount=amount_cents,
                currency=self.currency_id.name.lower(),
                destination=self.partner_id.stripe_account_id,
                description=f'Payment {self.name}',
                metadata={
                    'odoo_payment_id': str(self.id),
                    'odoo_payment_name': self.name,
                    'odoo_partner_id': str(self.partner_id.id),
                    'odoo_partner_name': self.partner_id.name,
                },
                idempotency_key=idempotency_key
            )
            
            # Update payment record
            self.write({
                'stripe_transfer_id': transfer.id,
                'stripe_transfer_status': 'succeeded',
            })
            
            _logger.info(f"Stripe transfer created: {transfer.id} for payment {self.name}")
            
            return True
            
        except stripe.error.StripeError as e:
            _logger.error(f"Stripe error for payment {self.name}: {str(e)}")
            self.stripe_transfer_status = 'failed'
            raise UserError(f'Failed to send payment: {str(e)}')