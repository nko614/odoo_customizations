from odoo import models, api, fields, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    duplicate_warning = fields.Text(
        compute="_compute_duplicate_warning",
        store=False,
    )

    @api.depends("name", "email")
    def _compute_duplicate_warning(self):
        prevent = self.env["ir.config_parameter"].sudo().get_param(
            "duplicate_prevention.prevent_duplicate_customer"
        )
        for partner in self:
            if not prevent or prevent == "False":
                partner.duplicate_warning = False
                continue

            warnings = []

            if partner.name and partner._origin.id:
                dup_names = self.search([
                    ("name", "=ilike", partner.name),
                    ("id", "!=", partner._origin.id),
                ])
                if dup_names:
                    names = ", ".join(
                        "%s (ID: %s)" % (d.name, d.id) for d in dup_names[:5]
                    )
                    warnings.append(
                        _("Contacts with the same name: %s") % names
                    )

            if partner.email and partner._origin.id:
                dup_emails = self.search([
                    ("email", "=ilike", partner.email),
                    ("id", "!=", partner._origin.id),
                ])
                if dup_emails:
                    emails = ", ".join(
                        "%s (%s, ID: %s)" % (d.name, d.email, d.id) for d in dup_emails[:5]
                    )
                    warnings.append(
                        _("Contacts with the same email: %s") % emails
                    )

            partner.duplicate_warning = "\n".join(warnings) if warnings else False
