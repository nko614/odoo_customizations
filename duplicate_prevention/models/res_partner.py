from odoo import models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("email")
    def _check_duplicate_customer(self):
        prevent = self.env["ir.config_parameter"].sudo().get_param(
            "duplicate_prevention.prevent_duplicate_customer"
        )
        if not prevent or prevent == "False":
            return
        for partner in self:
            if not partner.email:
                continue
            domain = [
                ("email", "=ilike", partner.email),
                ("id", "!=", partner.id),
            ]
            duplicate = self.search(domain, limit=1)
            if duplicate:
                raise ValidationError(
                    _('A contact with email "%s" already exists: "%s". Duplicate contacts are not allowed.')
                    % (partner.email, duplicate.display_name)
                )
