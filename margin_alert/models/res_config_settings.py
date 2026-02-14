from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    margin_alert_threshold = fields.Float(
        string="Minimum Margin (%)",
        config_parameter="margin_alert.threshold",
        default=15.0,
        help="Sales orders with an overall margin below this percentage will trigger a warning or be blocked.",
    )
    margin_alert_mode = fields.Selection(
        [
            ("warn", "Warn (allow confirmation)"),
            ("block", "Block (prevent confirmation)"),
        ],
        string="Alert Mode",
        config_parameter="margin_alert.mode",
        default="warn",
        help="Warn shows a confirmation dialog. Block prevents the order from being confirmed.",
    )
