from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    board_feet = fields.Float(
        string='BF / Unit',
        related='product_id.board_feet',
        readonly=True,
    )
    total_board_feet = fields.Float(
        string='Total BF',
        compute='_compute_total_board_feet',
        store=True,
        digits=(12, 4),
    )
    price_per_bf = fields.Float(string='Price / BF', digits=(12, 4))
    bf_cost = fields.Float(
        string='BF Cost',
        compute='_compute_bf_cost',
        store=True,
        digits=(12, 4),
    )

    @api.depends('product_uom_qty', 'product_id.board_feet')
    def _compute_total_board_feet(self):
        for line in self:
            line.total_board_feet = line.product_uom_qty * (line.product_id.board_feet or 0.0)

    @api.depends('price_unit', 'product_id.board_feet')
    def _compute_bf_cost(self):
        for line in self:
            bf = line.product_id.board_feet
            line.bf_cost = line.price_unit / bf if bf else 0.0

    @api.onchange('price_per_bf')
    def _onchange_price_per_bf(self):
        if self.price_per_bf and self.product_id.board_feet:
            self.price_unit = self.price_per_bf * self.product_id.board_feet
