# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    ecommerce_move_identifier = fields.Char(
        string="E-commerce Move Identifier", readonly=True, copy=False)

    @api.depends('sale_line_id.ecommerce_account_id.fulfilled_by')
    def _compute_reference(self):
        super()._compute_reference()
        for record in self:
            if (
                record.sale_line_id
                and record.sale_line_id.ecommerce_account_id
                and record.sale_line_id.ecommerce_account_id.fulfilled_by == 'ecommerce'
            ):
                record.reference = self.env._("%s move: %s", record.sale_line_id.ecommerce_account_id.ecommerce_channel_id.name, record.reference)
