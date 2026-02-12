from odoo import api, fields, models


class NadaReceiptLine(models.Model):
    _name = 'nada.receipt.line'
    _description = 'Receipt Automation Line'
    _order = 'sequence, id'

    run_id = fields.Many2one('nada.receipt.run', string='Run', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)

    # User enters these
    product_id = fields.Many2one('product.product', string='Product', required=True)
    forecasted_qty = fields.Float(string='Forecasted Sales')

    # Auto-populated
    on_hand_qty = fields.Float(
        string='On Hand', compute='_compute_on_hand_qty', store=True,
    )
    needed_qty = fields.Float(
        string='Needed Qty', compute='_compute_needed_qty', store=True,
    )

    # Blanket order matching (set by processing)
    allocated_qty = fields.Float(string='Allocated Qty')
    blanket_order_id = fields.Many2one('purchase.requisition', string='Blanket Order')
    blanket_line_id = fields.Many2one('purchase.requisition.line', string='Blanket Order Line')
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    price_unit = fields.Float(string='Unit Price', digits='Product Price')

    # Status
    status = fields.Selection([
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('partial', 'Partial Match'),
        ('no_blanket', 'No Blanket Order'),
    ], string='Status', default='pending')
    note = fields.Char(string='Note')

    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for line in self:
            line.on_hand_qty = line.product_id.qty_available if line.product_id else 0.0

    @api.depends('forecasted_qty', 'on_hand_qty')
    def _compute_needed_qty(self):
        for line in self:
            diff = line.forecasted_qty - line.on_hand_qty
            line.needed_qty = diff if diff > 0 else 0.0
