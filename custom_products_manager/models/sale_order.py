from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    has_custom_products = fields.Boolean(
        string='Has Custom Products',
        compute='_compute_has_custom_products',
        store=True,
        help="Indicates if this order contains custom products"
    )
    
    custom_products_count = fields.Integer(
        string='Custom Products Count',
        compute='_compute_custom_products_count',
        help="Number of custom products in this order"
    )

    @api.depends('order_line.is_custom_product')
    def _compute_has_custom_products(self):
        for order in self:
            order.has_custom_products = any(line.is_custom_product for line in order.order_line)

    def _compute_custom_products_count(self):
        for order in self:
            order.custom_products_count = len(order.order_line.filtered('is_custom_product'))

    def action_create_custom_product(self):
        """Open wizard to create a custom product and add to order"""
        self.ensure_one()
        return {
            'name': _('Create Custom Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.product.creator',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_partner_id': self.partner_id.id,
            }
        }

    def action_view_custom_products(self):
        """View all custom products in this order"""
        custom_lines = self.order_line.filtered('is_custom_product')
        product_ids = custom_lines.mapped('product_id.id')
        
        return {
            'name': _('Custom Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'domain': [('id', 'in', product_ids)],
            'context': {'create': False}
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_custom_product = fields.Boolean(
        string='Custom Product',
        default=False,
        help="Indicates if this line contains a custom product"
    )
    
    custom_product_id = fields.Many2one(
        'custom.product.config',
        string='Custom Product Config',
        help="Link to custom product configuration"
    )
    
    bom_id = fields.Many2one(
        'mrp.bom',
        string='Bill of Materials',
        help="Bill of Materials for this custom product"
    )
    
    estimated_cost = fields.Float(
        string='Estimated Cost',
        compute='_compute_estimated_cost',
        store=True,
        help="Estimated cost based on BOM components"
    )
    
    margin_percentage = fields.Float(
        string='Margin %',
        compute='_compute_margin_percentage',
        help="Profit margin percentage"
    )

    @api.depends('bom_id', 'bom_id.bom_line_ids')
    def _compute_estimated_cost(self):
        for line in self:
            if line.bom_id:
                total_cost = 0
                for bom_line in line.bom_id.bom_line_ids:
                    component_cost = bom_line.product_id.standard_price * bom_line.product_qty
                    total_cost += component_cost
                line.estimated_cost = total_cost * line.product_uom_qty
            else:
                line.estimated_cost = line.product_id.standard_price * line.product_uom_qty

    @api.depends('price_unit', 'estimated_cost')
    def _compute_margin_percentage(self):
        for line in self:
            if line.estimated_cost and line.price_unit:
                line.margin_percentage = ((line.price_unit - line.estimated_cost) / line.price_unit) * 100
            else:
                line.margin_percentage = 0

    def action_create_custom_product(self):
        """Create a custom product for this line"""
        self.ensure_one()
        return {
            'name': _('Create Custom Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.product.creator',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.order_id.id,
                'default_sale_line_id': self.id,
                'default_partner_id': self.order_id.partner_id.id,
                'default_quantity': self.product_uom_qty,
            }
        }

    def action_edit_bom(self):
        """Edit or create BOM for this custom product"""
        self.ensure_one()
        if not self.bom_id:
            # Create a new BOM
            bom_vals = {
                'product_tmpl_id': self.product_id.product_tmpl_id.id,
                'product_id': self.product_id.id,
                'product_qty': 1,
                'type': 'normal',
                'code': f"BOM-{self.product_id.default_code or self.product_id.name}",
            }
            self.bom_id = self.env['mrp.bom'].create(bom_vals)
        
        return {
            'name': _('Edit Bill of Materials'),
            'type': 'ir.actions.act_window',
            'res_model': 'bom.builder.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bom_id': self.bom_id.id,
                'default_sale_line_id': self.id,
            }
        }

    def action_view_bom(self):
        """View the BOM for this product"""
        self.ensure_one()
        if not self.bom_id:
            raise ValidationError(_("No Bill of Materials found for this product."))
        
        return {
            'name': _('Bill of Materials'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom',
            'res_id': self.bom_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.onchange('product_id')
    def _onchange_product_id_custom(self):
        """Check if the selected product is a custom product"""
        if self.product_id:
            custom_config = self.env['custom.product.config'].search([
                ('product_id', '=', self.product_id.id)
            ], limit=1)
            if custom_config:
                self.is_custom_product = True
                self.custom_product_id = custom_config.id
                # Find existing BOM
                bom = self.env['mrp.bom'].search([
                    ('product_id', '=', self.product_id.id)
                ], limit=1)
                if bom:
                    self.bom_id = bom.id