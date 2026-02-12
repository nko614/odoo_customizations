from odoo import models
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_procurement_values(self):
        values = super()._prepare_procurement_values()
        _logger.info("Stock move group_id: %s", self.group_id)
        _logger.info("Stock move sale_id: %s", self.group_id.sale_id if self.group_id else None)
        
        if self.group_id and self.group_id.sale_id and self.group_id.sale_id.partner_id:
            values['customer_id'] = self.group_id.sale_id.partner_id.id
            _logger.info("Added customer_id to procurement values: %s", values['customer_id'])
        
        _logger.info("Final procurement values: %s", values)
        return values 