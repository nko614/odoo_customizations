from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    split_shipment_date = fields.Date(
        string='Split Shipment Date',
        help='Date used for grouping moves into separate deliveries'
    )

    def _key_assign_picking(self):
        """
        Add split_shipment_date to the key used for grouping moves into pickings.
        Moves with different dates will get different pickings.
        """
        keys = super()._key_assign_picking()
        # Add split_shipment_date to the grouping key
        # This ensures moves with different dates won't be grouped together
        return keys + (self.split_shipment_date,)

    def _get_new_picking_values(self):
        """Set scheduled_date on new picking based on split shipment date"""
        vals = super()._get_new_picking_values()
        # Get first move's split_shipment_date (all moves in this group should have the same date)
        split_date = self.filtered('split_shipment_date').mapped('split_shipment_date')
        if split_date:
            vals['scheduled_date'] = fields.Datetime.to_datetime(split_date[0])
        return vals

    def _search_picking_for_assignation(self):
        """
        Override to ensure moves with different split_shipment_dates
        are assigned to different pickings.
        """
        self.ensure_one()

        # If no split shipment date, use standard behavior
        if not self.split_shipment_date:
            return super()._search_picking_for_assignation()

        # Get the domain for searching compatible pickings
        domain = self._search_picking_for_assignation_domain()

        # Add filter for matching scheduled_date
        # Convert date to datetime for comparison with scheduled_date
        target_datetime = fields.Datetime.to_datetime(self.split_shipment_date)
        # Match pickings scheduled for the same date (comparing date part only)
        domain += [
            ('scheduled_date', '>=', fields.Datetime.to_string(target_datetime.replace(hour=0, minute=0, second=0))),
            ('scheduled_date', '<', fields.Datetime.to_string(target_datetime.replace(hour=23, minute=59, second=59))),
        ]

        picking = self.env['stock.picking'].search(domain, limit=1)
        return picking

    def _search_picking_for_assignation_domain(self):
        """Get base domain for picking assignation search"""
        self.ensure_one()

        # Call super if it exists, otherwise build base domain
        if hasattr(super(), '_search_picking_for_assignation_domain'):
            return super()._search_picking_for_assignation_domain()

        # Build base domain matching Odoo's standard logic
        domain = [
            ('group_id', '=', self.group_id.id),
            ('location_id', '=', self.location_id.id),
            ('location_dest_id', '=', self.location_dest_id.id),
            ('picking_type_id', '=', self.picking_type_id.id),
            ('printed', '=', False),
            ('immediate_transfer', '=', False),
            ('state', 'in', ['draft', 'confirmed', 'waiting', 'partially_available', 'assigned']),
        ]

        if self.partner_id:
            domain += [('partner_id', '=', self.partner_id.id)]

        return domain
