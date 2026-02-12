from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    target_margin_percent = fields.Float(
        string="Margin %",
        compute='_compute_target_margin_percent',
        inverse='_inverse_target_margin_percent',
        store=True,
        readonly=False,
        digits=(5, 2),
    )

    @api.depends('purchase_price', 'price_unit')
    def _compute_target_margin_percent(self):
        for line in self:
            if line.purchase_price:
                line.target_margin_percent = (
                    (line.price_unit - line.purchase_price) / line.purchase_price * 100.0
                )
            else:
                line.target_margin_percent = 0.0

    def _inverse_target_margin_percent(self):
        for line in self:
            line.price_unit = line.purchase_price * (
                1.0 + line.target_margin_percent / 100.0
            )

    @api.onchange('target_margin_percent')
    def _onchange_target_margin_percent(self):
        self.price_unit = self.purchase_price * (
            1.0 + self.target_margin_percent / 100.0
        )
