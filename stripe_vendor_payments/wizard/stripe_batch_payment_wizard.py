# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class StripeBatchPaymentWizard(models.TransientModel):
    _name = 'stripe.batch.payment.wizard'
    _description = 'Stripe Batch Payment Wizard'
    
    batch_payment_id = fields.Many2one('account.batch.payment', string='Batch Payment')
    payment_ids = fields.Many2many('account.payment', string='Payments to Send')
    
    # Summary fields
    total_payments = fields.Integer(string='Total Payments', compute='_compute_summary')
    total_amount = fields.Monetary(string='Total Amount', compute='_compute_summary')
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_summary')
    
    # Vendor validation
    vendors_without_stripe = fields.Text(string='Vendors without Stripe', compute='_compute_vendor_status')
    vendors_not_ready = fields.Text(string='Vendors not ready', compute='_compute_vendor_status')
    all_vendors_ready = fields.Boolean(compute='_compute_vendor_status')
    
    @api.depends('payment_ids')
    def _compute_summary(self):
        for wizard in self:
            wizard.total_payments = len(wizard.payment_ids)
            wizard.total_amount = sum(wizard.payment_ids.mapped('amount'))
            wizard.currency_id = wizard.payment_ids[0].currency_id if wizard.payment_ids else False
    
    @api.depends('payment_ids')
    def _compute_vendor_status(self):
        for wizard in self:
            vendors_without = []
            vendors_not_ready = []
            
            for payment in wizard.payment_ids:
                partner = payment.partner_id
                if not partner.stripe_account_id:
                    vendors_without.append(partner.name)
                elif not partner.stripe_payouts_enabled:
                    vendors_not_ready.append(partner.name)
            
            wizard.vendors_without_stripe = ', '.join(set(vendors_without)) if vendors_without else False
            wizard.vendors_not_ready = ', '.join(set(vendors_not_ready)) if vendors_not_ready else False
            wizard.all_vendors_ready = not vendors_without and not vendors_not_ready
    
    def action_send_batch(self):
        """Send all payments in the batch via Stripe"""
        self.ensure_one()
        
        if not self.all_vendors_ready:
            raise UserError('Some vendors are not ready for Stripe payments. Please check the vendor status.')
        
        success_count = 0
        failed_count = 0
        total_sent = 0.0
        errors = []
        
        for payment in self.payment_ids:
            try:
                # Send individual payment
                payment.send_via_stripe()
                success_count += 1
                total_sent += payment.amount
                _logger.info(f"Successfully sent payment {payment.name} via Stripe")
                
            except Exception as e:
                failed_count += 1
                error_msg = f"{payment.partner_id.name} - {payment.name}: {str(e)}"
                errors.append(error_msg)
                _logger.error(f"Failed to send payment {payment.name}: {str(e)}")
        
        # Update batch status
        if self.batch_payment_id:
            self.batch_payment_id.write({
                'stripe_batch_status': 'sent' if failed_count == 0 else 'partial',
                'stripe_batch_sent_count': success_count,
                'stripe_batch_total_amount': total_sent,
            })
        
        # Prepare result message
        message = f"Batch Processing Complete:\n"
        message += f"✓ Successfully sent: {success_count} payments (${total_sent:.2f})\n"
        if failed_count > 0:
            message += f"✗ Failed: {failed_count} payments\n"
            if errors:
                message += "\nErrors:\n" + "\n".join(errors[:5])  # Show first 5 errors
                if len(errors) > 5:
                    message += f"\n... and {len(errors) - 5} more errors"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Stripe Batch Payment',
                'message': message,
                'type': 'success' if failed_count == 0 else 'warning',
                'sticky': True,
            }
        }