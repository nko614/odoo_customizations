from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    board_feet = fields.Float(
        string='BF / Unit',
        related='product_id.board_feet',
        readonly=True,
    )
    total_board_feet = fields.Float(
        string='On Hand (BF)',
        compute='_compute_board_feet_totals',
        store=True,
        digits=(12, 4),
    )
    reserved_board_feet = fields.Float(
        string='Reserved (BF)',
        compute='_compute_board_feet_totals',
        store=True,
        digits=(12, 4),
    )
    available_board_feet = fields.Float(
        string='Available (BF)',
        compute='_compute_board_feet_totals',
        digits=(12, 4),
    )
    bf_cost = fields.Float(
        string='BF Cost',
        compute='_compute_bf_cost',
        digits=(12, 4),
    )

    @api.depends('quantity', 'reserved_quantity', 'product_id.board_feet')
    def _compute_board_feet_totals(self):
        for quant in self:
            bf = quant.product_id.board_feet or 0.0
            quant.total_board_feet = quant.quantity * bf
            quant.reserved_board_feet = quant.reserved_quantity * bf
            quant.available_board_feet = (quant.quantity - quant.reserved_quantity) * bf

    @api.depends('product_id.board_feet', 'product_id.standard_price')
    def _compute_bf_cost(self):
        for quant in self:
            bf = quant.product_id.board_feet
            quant.bf_cost = quant.product_id.standard_price / bf if bf else 0.0
