from odoo import models, api, _
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.constrains("default_code")
    def _check_duplicate_sku(self):
        prevent = self.env["ir.config_parameter"].sudo().get_param(
            "duplicate_prevention.prevent_duplicate_sku"
        )
        if not prevent or prevent == "False":
            return
        for product in self:
            if not product.default_code:
                continue
            duplicate = self.search([
                ("default_code", "=", product.default_code),
                ("id", "!=", product.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _('SKU "%s" already exists on product "%s". Duplicate SKUs are not allowed.')
                    % (product.default_code, duplicate.display_name)
                )
