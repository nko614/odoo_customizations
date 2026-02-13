from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    google_maps_api_key = fields.Char(
        string="Google Maps API Key",
        config_parameter="google_maps_api_key",
        help="Enter your Google Maps API key (requires Distance Matrix API enabled)",
    )

    auto_optimize_routes = fields.Boolean(
        string="Auto-optimize Delivery Routes",
        config_parameter="delivery_optimizer.auto_optimize_routes",
        help="Automatically optimize delivery routes at scheduled intervals",
    )

    optimize_route_interval = fields.Selection(
        [
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
        ],
        string="Optimization Interval",
        config_parameter="delivery_optimizer.optimize_route_interval",
        default="daily",
        help="Frequency of automatic route optimization",
    )
