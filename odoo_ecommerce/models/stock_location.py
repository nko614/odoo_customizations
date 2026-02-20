# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    ecommerce_location_ids = fields.One2many(
        comodel_name="ecommerce.location",
        inverse_name="matched_location_id",
        string="E-commerce Locations",
        help="List of ecommerce warehouses/locations/sources that is associated with this stock location.",
    )
    ecommerce_channel_id = fields.Many2one(
        comodel_name="ecommerce.channel",
        string="E-commerce Channel",
    )

    location_count = fields.Integer(compute='_compute_location_count')

    def _compute_location_count(self):
        locations_data = self.env['ecommerce.location']._read_group(
            [('matched_location_id', 'in', self.ids)], ['matched_location_id'], ['__count']
        )
        locations_data = {location.id: count for location, count in locations_data}
        for location in self:
            location.location_count = locations_data.get(location.id, 0)

    def action_view_ecommerce_location(self):
        self.ensure_one()
        return {
            'name': "Locations",
            'type': 'ir.actions.act_window',
            'res_model': 'ecommerce.location',
            'view_mode': 'list',
            'domain': [('matched_location_id', '=', self.id)],
            'context': {'group_by': 'ecommerce_account_id', 'create': False}
        }
