from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    prevent_duplicate_sku = fields.Boolean(
        string="Prevent Duplicate SKUs",
        config_parameter="duplicate_prevention.prevent_duplicate_sku",
        help="Block creation of products with an internal reference (SKU) that already exists.",
    )
    prevent_duplicate_customer = fields.Boolean(
        string="Prevent Duplicate Customers",
        config_parameter="duplicate_prevention.prevent_duplicate_customer",
        help="Block creation of company contacts with an email address that already exists.",
    )
