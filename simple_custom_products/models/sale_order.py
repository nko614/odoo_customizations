from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    def action_add_custom_product_line(self):
        """Add a new line and open wizard to create custom product"""
        self.ensure_one()
        
        # Create a new line
        line_vals = {
            'order_id': self.id,
            'name': 'Custom Product (to be configured)',
            'sequence': len(self.order_line) + 1,
        }
        new_line = self.env['sale.order.line'].create(line_vals)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Custom Product'),
            'res_model': 'simple.product.creator',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_line_id': new_line.id,
                'default_order_id': self.id,
                'default_partner_id': self.partner_id.id,
            }
        }
    


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_custom_product = fields.Boolean(string='Custom Product', default=False)
    
    def action_create_custom_product(self):
        """Open wizard to create custom product for this line"""
        self.ensure_one()
        
        # Ensure line has basic info
        if not self.name or self.name == '/':
            self.name = 'Custom Product (to be configured)'
        
        # If this is a new line without ID, we need to save the order first
        if not self.id:
            # Force save the order to get line IDs
            self.order_id._compute_tax_totals()
            self.order_id.flush_recordset()
            self.env.cr.commit()
        
        # If still no ID after commit, create the line properly
        if not self.id:
            raise ValidationError(_("Unable to create line. Please save the order manually first."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Custom Product'),
            'res_model': 'simple.product.creator',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_line_id': self.id,
                'default_order_id': self.order_id.id,
                'default_partner_id': self.order_id.partner_id.id,
            }
        }