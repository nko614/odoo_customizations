from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

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

    @api.depends('quantity', 'product_id.board_feet')
    def _compute_total_board_feet(self):
        for move in self:
            move.total_board_feet = move.quantity * (move.product_id.board_feet or 0.0)
