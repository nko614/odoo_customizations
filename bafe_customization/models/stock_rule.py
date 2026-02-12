from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _make_po_get_domain(self, company_id, values, partner):
        """
        Find existing draft PO for the same vendor
        """
        domain = (
            ('partner_id', '=', partner.id),  # Same vendor
            ('state', '=', 'draft'),          # Only draft POs
            ('picking_type_id', '=', self.picking_type_id.id),
            ('company_id', '=', company_id.id),
        )
        _logger.info("PO grouping domain: %s", domain)
        return domain

    def _prepare_purchase_order(self, company_id, origins, values_list):
        vals = super()._prepare_purchase_order(company_id, origins, values_list)
        
        # Set customer from procurement values
        if values_list and values_list[0].get('group_id'):
            group = values_list[0]['group_id']
            if group.sale_id:
                vals['x_customer_id'] = group.sale_id.partner_id.id
                _logger.info("Setting customer_id on new PO: %s", vals['x_customer_id'])
                
        return vals

    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, company_id, values, po):
        """
        Override to ensure we create unique lines for each sale order line
        """
        _logger.info("Preparing PO line with values: %s", values)
        
        vals = super()._prepare_purchase_order_line(
            product_id=product_id,
            product_qty=product_qty,
            product_uom=product_uom,
            company_id=company_id,
            values=values,
            po=po
        )
        
        # Get the customer_id from the sale order
        if values.get('group_id') and values['group_id'].sale_id:
            customer_id = values['group_id'].sale_id.partner_id.id
            customer = self.env['res.partner'].browse(customer_id)
            
            # Update the line values
            vals.update({
                'name': f"{vals.get('name', '')} (Customer: {customer.name})",
                'x_customer_id': customer_id,
                # Add the sale line reference if available
                'sale_line_id': values.get('sale_line_id', False),
            })
            _logger.info("Added customer info to PO line values: %s", vals)
        
        return vals

    def _run_buy(self, procurements):
        _logger.info("Starting _run_buy with procurements: %s", procurements)
        for procurement, rule in procurements:
            if procurement.values.get('group_id') and procurement.values['group_id'].sale_id:
                customer_id = procurement.values['group_id'].sale_id.partner_id.id
                procurement.values['customer_id'] = customer_id
                _logger.info("Added customer_id to procurement values: %s", customer_id)
        return super()._run_buy(procurements) 