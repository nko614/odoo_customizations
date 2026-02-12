from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _make_po_get_domain(self, company_id, values, partner):
        """Override to ensure we use the customer-specific vendor"""
        if values.get('supplier_id'):
            _logger.info("Using supplier from procurement values: %s", values['supplier_id'].name)
            partner = values['supplier_id']
        
        domain = (
            ('partner_id', '=', partner.id),
            ('state', '=', 'draft'),
            ('picking_type_id', '=', self.picking_type_id.id),
            ('company_id', '=', company_id.id),
        )
        _logger.info("PO search domain: %s", domain)
        return domain

    def _prepare_purchase_order(self, company_id, origins, values_list):
        """Override to set the customer on the PO"""
        vals = super()._prepare_purchase_order(company_id, origins, values_list)
        
        if values_list and values_list[0].get('group_id'):
            group = values_list[0]['group_id']
            if group.sale_id:
                vals['x_customer_id'] = group.sale_id.partner_id.id
                _logger.info("Setting customer_id on PO: %s", vals['x_customer_id'])
                
        # Ensure we're using the correct supplier
        if values_list and values_list[0].get('supplier_id'):
            vals['partner_id'] = values_list[0]['supplier_id'].id
            _logger.info("Setting supplier on PO: %s", vals['partner_id'])
                
        return vals

    def _run_buy(self, procurements):
        """Override to ensure supplier is set before running procurement"""
        _logger.info("Starting _run_buy with procurements: %s", procurements)
        for procurement, rule in procurements:
            if procurement.values.get('supplier_id'):
                procurement.values['partner_id'] = procurement.values['supplier_id'].id
                _logger.info("Set partner_id from supplier_id: %s", procurement.values['partner_id'])
        return super()._run_buy(procurements) 