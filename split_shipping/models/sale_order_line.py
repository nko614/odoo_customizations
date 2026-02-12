from odoo import models, fields, api
from datetime import date


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    shipment_date = fields.Date(
        string='Shipment Date',
        help='Scheduled date for shipping this line. '
             'Lines with the same date will be grouped into one delivery order.'
    )

    # Related field to control visibility in views
    split_shipping = fields.Boolean(
        related='order_id.split_shipping',
        string='Split Shipping Enabled',
        readonly=True
    )

    def _prepare_procurement_values(self):
        """Add shipment date to procurement values for grouping deliveries"""
        values = super()._prepare_procurement_values()

        if self.order_id.split_shipping:
            # Use the line's shipment date, or default to today
            shipment_date = self.shipment_date or fields.Date.today()
            values['split_shipment_date'] = shipment_date
            # Also set date_planned to influence scheduled_date on picking
            values['date_planned'] = fields.Datetime.to_datetime(shipment_date)

        return values
