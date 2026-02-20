# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ECommerceOffer(models.Model):
    _name = 'ecommerce.offer'
    _description = "E-Commerce Offer/Listing/Product"

    name = fields.Char(string="Title")
    sku = fields.Char(string="SKU", required=True, readonly=True)
    ec_product_identifier = fields.Char(
        string="E-commerce Product ID",
        help="Unique id of the product in the ecommerce",
        readonly=True
    )
    ec_product_template_identifier = fields.Char(
        string="E-commerce Product Template ID",
        help="Unique id of the product template in the ecommerce",
        readonly=True
    )
    channel_code = fields.Char(
        related='ecommerce_account_id.channel_code',
    )

    ecommerce_account_id = fields.Many2one(
        comodel_name='ecommerce.account',
        string="E-commerce Account",
        ondelete='restrict',
    )
    matched_product_id = fields.Many2one(
        comodel_name='product.product',
        string="Matched Product",
        domain=[('sale_ok', '=', True)],
        required=True
    )
    matched_product_template_id = fields.Many2one(
        related="matched_product_id.product_tmpl_id", store=True, readonly=True
    )

    sync_stock = fields.Boolean(
        string="Stock Synchronization", compute='_compute_sync_stock', store=True, readonly=False,
    )

    _unique_ec_account_sku = models.Constraint(
        "UNIQUE(ecommerce_account_id, sku)",
        "The SKU must be unique among offers of same ecommerce account."
    )
    _unique_ec_account_ec_product_id_ec_product_template_id = models.Constraint(
        "UNIQUE(ecommerce_account_id, ec_product_template_identifier, ec_product_identifier)",
        "The combination of ecommerce product id and ecommerce product template id must be unique among offers of same ecommerce account."
    )

    @api.depends('ecommerce_account_id.update_inventory', 'matched_product_id.is_storable')
    def _compute_sync_stock(self):
        for offer in self:
            offer.sync_stock = (
                offer.ecommerce_account_id.update_inventory
                and offer.matched_product_id.is_storable
            )

    @api.constrains('sync_stock')
    def _check_product_is_storable(self):
        for offer in self.filtered('sync_stock'):
            if not offer.matched_product_id.is_storable:
                raise ValidationError(self.env._("Non-storable product cannot be synced."))

    def action_view_online(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.ecommerce_account_id._get_product_url(self),
            'target': 'new',
        }

    def auto_match_products(self):
        existing_product_default_codes = self.env['product.product'].search([]).mapped('default_code')
        for offer in self:
            if offer.sku and offer.sku in existing_product_default_codes:
                offer.matched_product_id = self.env['product.product'].search([('default_code', '=', offer.sku)], limit=1).id
