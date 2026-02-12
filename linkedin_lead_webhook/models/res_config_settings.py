from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    linkedin_webhook_api_key = fields.Char(
        string="LinkedIn Webhook API Key",
        config_parameter='linkedin_lead_webhook.api_key',
        help="API key required in the X-API-Key header for webhook authentication",
    )
