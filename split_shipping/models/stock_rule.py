from odoo import models, fields, api


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values):
        """
        Pass split_shipment_date from procurement values to stock move.
        """
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_dest_id,
            name, origin, company_id, values
        )

        # Pass split shipment date to the stock move
        if values.get('split_shipment_date'):
            res['split_shipment_date'] = values['split_shipment_date']
            # Also set the move date to the shipment date
            res['date'] = fields.Datetime.to_datetime(values['split_shipment_date'])

        return res
