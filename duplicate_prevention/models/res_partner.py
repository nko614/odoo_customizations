from odoo import models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("name", "email")
    def _check_duplicate_customer(self):
        prevent = self.env["ir.config_parameter"].sudo().get_param(
            "duplicate_prevention.prevent_duplicate_customer"
        )
        if not prevent or prevent == "False":
            return
        for partner in self:
            # Check duplicate email
            if partner.email:
                dup_email = self.search([
                    ("email", "=ilike", partner.email),
                    ("id", "!=", partner.id),
                ], limit=1)
                if dup_email:
                    raise ValidationError(
                        _('A contact with email "%s" already exists: "%s". Duplicate contacts are not allowed.')
                        % (partner.email, dup_email.display_name)
                    )
            # Check duplicate name
            if partner.name:
                dup_name = self.search([
                    ("name", "=ilike", partner.name),
                    ("id", "!=", partner.id),
                ], limit=1)
                if dup_name:
                    raise ValidationError(
                        _('A contact named "%s" already exists. Duplicate contacts are not allowed.')
                        % partner.name
                    )
