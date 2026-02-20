# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    ecommerce_line_identifier = fields.Char(
        string="E-commerce order line ID",
        readonly=True, copy=False)

    ecommerce_account_id = fields.Many2one(
        related="order_id.ecommerce_account_id",
        store=True,
    )

    _unique_ecommerce_account_ecommerce_line_identifier = models.Constraint(
        "UNIQUE(ecommerce_account_id, ecommerce_line_identifier)",
        "E-commerce order line identifier should be unique per ecommerce account."
    )
