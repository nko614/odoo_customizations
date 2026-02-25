from odoo import api, fields, models


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    price_per_bf = fields.Float(string='Price / BF', digits=(12, 4))
    board_feet = fields.Float(
        string='Board Feet',
        related='product_tmpl_id.board_feet',
        readonly=True,
    )

    @api.onchange('price_per_bf')
    def _onchange_price_per_bf(self):
        if self.price_per_bf and self.board_feet:
            self.price = self.price_per_bf * self.board_feet
