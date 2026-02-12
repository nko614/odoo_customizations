from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    split_shipping = fields.Boolean(
        string='Split Shipping',
        default=False,
        help='Enable to set different shipment dates for each order line. '
             'Each unique date will create a separate delivery order.'
    )

    @api.onchange('split_shipping')
    def _onchange_split_shipping(self):
        """Clear shipment dates when split shipping is disabled"""
        if not self.split_shipping:
            for line in self.order_line:
                line.shipment_date = False
