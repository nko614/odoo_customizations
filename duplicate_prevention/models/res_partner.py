from odoo import models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("email")
    def _check_duplicate_customer(self):
        prevent = self.env["ir.config_parameter"].sudo().get_param(
            "duplicate_prevention.prevent_duplicate_customer", "False"
        )
        if prevent != "True":
            return
        for partner in self:
            if not partner.email or not partner.is_company:
                continue
            duplicate = self.search([
                ("email", "=ilike", partner.email),
                ("is_company", "=", True),
                ("id", "!=", partner.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _('A customer with email "%s" already exists: "%s". Duplicate customers are not allowed.')
                    % (partner.email, duplicate.display_name)
                )
