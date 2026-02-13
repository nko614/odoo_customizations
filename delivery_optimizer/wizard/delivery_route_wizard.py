from odoo import models, fields, api


class DeliveryRouteWizard(models.TransientModel):
    _name = 'delivery.route.wizard'
    _description = 'Delivery Route Preview'

    picking_id = fields.Many2one('stock.picking', string='Delivery', readonly=True)
    partner_name = fields.Char(string='Customer', readonly=True)
    delivery_address = fields.Char(string='Delivery Address', readonly=True)
    warehouse_address = fields.Char(string='From Warehouse', readonly=True)
    distance_miles = fields.Float(string='Distance (miles)', readonly=True, digits=(16, 1))
    distance_text = fields.Char(string='Distance', readonly=True)
    duration_minutes = fields.Integer(string='Duration (minutes)', readonly=True)
    duration_text = fields.Char(string='Estimated Time', readonly=True)
    embed_url = fields.Char(string='Map URL', readonly=True)
    maps_url = fields.Char(string='Google Maps Link', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Get route info from context
        route_info = self.env.context.get('route_info', {})

        if route_info.get('success'):
            res.update({
                'picking_id': route_info.get('picking_id'),
                'partner_name': route_info.get('partner_name'),
                'delivery_address': route_info.get('delivery_address'),
                'warehouse_address': route_info.get('warehouse_address'),
                'distance_miles': route_info.get('distance_miles'),
                'distance_text': route_info.get('distance_text'),
                'duration_minutes': route_info.get('duration_minutes'),
                'duration_text': route_info.get('duration_text'),
                'embed_url': route_info.get('embed_url'),
                'maps_url': route_info.get('maps_url'),
            })

        return res

    def action_open_in_google_maps(self):
        """Open the route in Google Maps in a new tab"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.maps_url,
            'target': 'new',
        }
