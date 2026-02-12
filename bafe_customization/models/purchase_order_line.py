from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    x_customer_id = fields.Many2one(
        'res.partner', 
        string='End Customer',
        store=True
    )

    def _prepare_run_values(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        """Override to prevent line merging"""
        _logger.info("Preventing line merge by making values unique")
        # Add a unique identifier to prevent merging
        values = dict(values or {})
        values['unique_key'] = self.env['ir.sequence'].next_by_code('purchase.order.line.unique') or '/'
        return values

    def _merge_in_existing_line(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        """Never merge lines - each sale order line gets its own purchase order line"""
        _logger.info("Preventing line merge for values: %s", values)
        return False

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("Creating purchase order lines with vals: %s", vals_list)
        records = super().create(vals_list)
        records._update_customer_specific_prices()
        return records

    def _update_customer_specific_prices(self):
        for record in self:
            _logger.info("Updating prices for PO line: %s", record)
            _logger.info("Customer ID: %s", record.x_customer_id)
            
            if not record.product_id or not record.partner_id:
                continue
                
            # Get the essential IDs
            product_tmpl_id = record.product_id.product_tmpl_id.id
            vendor_id = record.partner_id.id
            
            _logger.info("Product template ID: %s, Vendor ID: %s", product_tmpl_id, vendor_id)
            
            # Check if customer_id exists and is not False
            if record.x_customer_id:
                customer_id = record.x_customer_id.id
                
                # Query for customer-specific price
                self.env.cr.execute("""
                    SELECT price 
                    FROM product_supplierinfo 
                    WHERE product_tmpl_id = %s 
                    AND partner_id = %s 
                    AND x_customer_id = %s
                    LIMIT 1
                """, [product_tmpl_id, vendor_id, customer_id])
                
                result = self.env.cr.fetchone()
                _logger.info("Customer-specific price query result: %s", result)
                
                if result and result[0]:
                    _logger.info("Setting customer-specific price: %s", result[0])
                    record.write({'price_unit': result[0]})
                    continue
            
            # If we get here, either there's no customer or no customer-specific price
            # Try to find a generic price for this vendor without customer specified
            self.env.cr.execute("""
                SELECT price 
                FROM product_supplierinfo 
                WHERE product_tmpl_id = %s 
                AND partner_id = %s 
                AND (x_customer_id IS NULL OR x_customer_id = 0)
                ORDER BY sequence ASC
                LIMIT 1
            """, [product_tmpl_id, vendor_id])
            
            fallback_result = self.env.cr.fetchone()
            _logger.info("Generic price query result: %s", fallback_result)
            
            if fallback_result and fallback_result[0]:
                _logger.info("Setting generic price: %s", fallback_result[0])
                record.write({'price_unit': fallback_result[0]}) 