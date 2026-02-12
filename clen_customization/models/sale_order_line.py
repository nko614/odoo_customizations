from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_customer_specific_vendor(self):
        """Get the vendor specific to this customer for this product"""
        self.ensure_one()
        _logger.info("Getting customer-specific vendor for product %s and customer %s", 
                    self.product_id.name, self.order_id.partner_id.name)

        if not self.product_id or not self.order_id.partner_id:
            return False

        # Search for a vendor specific to this customer
        supplier_info = self.env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id),
            ('x_customer_id', '=', self.order_id.partner_id.id),
        ], limit=1, order='sequence')

        if supplier_info:
            _logger.info("Found customer-specific vendor: %s", supplier_info.partner_id.name)
            return supplier_info.partner_id
        
        # Fallback to default vendor if no customer-specific vendor is found
        default_supplier = self.env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id),
            ('x_customer_id', '=', False),
        ], limit=1, order='sequence')

        if default_supplier:
            _logger.info("Using default vendor: %s", default_supplier.partner_id.name)
            return default_supplier.partner_id

        _logger.info("No vendor found for product")
        return False

    def _prepare_procurement_values(self, group_id=False):
        """Override to set the customer-specific vendor"""
        values = super()._prepare_procurement_values(group_id=group_id)
        
        # Get the customer-specific vendor
        vendor = self._get_customer_specific_vendor()
        if vendor:
            _logger.info("Setting vendor %s for procurement", vendor.name)
            values['supplier_id'] = vendor
            values['partner_id'] = vendor.id
        
        # Add the customer information
        values['customer_id'] = self.order_id.partner_id.id
        
        _logger.info("Prepared procurement values: %s", values)
        return values 