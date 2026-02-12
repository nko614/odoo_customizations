from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    total_invoiced_amount = fields.Float(
        string='Total Invoiced (Computed)',
        compute='_compute_total_invoiced_amount',
        store=True,
        help='Total amount from posted customer invoices (with fallback to parent company)'
    )

    @api.depends('invoice_ids.amount_total', 'invoice_ids.state', 'invoice_ids.move_type',
                 'parent_id.invoice_ids.amount_total', 'parent_id.invoice_ids.state', 'parent_id.invoice_ids.move_type')
    def _compute_total_invoiced_amount(self):
        """Calculate total invoice amount for partner, with fallback to parent"""
        # Only compute if accounting is installed
        if 'account.move' not in self.env:
            for partner in self:
                partner.total_invoiced_amount = 0.0
            return

        for partner in self:
            # Get posted customer invoices for this partner using the relationship
            invoices = partner.invoice_ids.filtered(
                lambda inv: inv.move_type in ('out_invoice', 'out_refund') and inv.state == 'posted'
            )
            total = sum(invoices.mapped('amount_total'))

            # If no invoices and has parent, check parent
            if total == 0 and partner.parent_id:
                parent_invoices = partner.parent_id.invoice_ids.filtered(
                    lambda inv: inv.move_type in ('out_invoice', 'out_refund') and inv.state == 'posted'
                )
                total = sum(parent_invoices.mapped('amount_total'))

            partner.total_invoiced_amount = total
