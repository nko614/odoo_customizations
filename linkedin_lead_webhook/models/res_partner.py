from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    linkedin_url = fields.Char('LinkedIn Profile URL', index=True)
