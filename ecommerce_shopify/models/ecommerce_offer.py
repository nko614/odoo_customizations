# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ECommerceOffer(models.Model):
    _inherit = 'ecommerce.offer'

    shopify_inventory_item_id = fields.Char()
