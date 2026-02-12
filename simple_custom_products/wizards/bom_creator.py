from odoo import models, fields, api, _


class SimpleBomCreator(models.TransientModel):
    _name = 'simple.bom.creator'
    _description = 'Simple BOM Creator'

    # Product info (readonly)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    
    # BOM lines
    component_lines = fields.One2many('simple.bom.line', 'wizard_id', string='Components')
    
    # Context fields
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Line')
    order_id = fields.Many2one('sale.order', string='Sale Order')
    quantity = fields.Float(string='Quantity for Sale Order', default=1.0)
    list_price = fields.Float(string='Sales Price')

    def action_create_bom_and_add_to_order(self):
        """Create BOM and add product to sale order line"""
        self.ensure_one()
        
        import logging
        _logger = logging.getLogger(__name__)
        
        # Create BOM with proper settings for manufacturing
        bom_vals = {
            'product_tmpl_id': self.product_tmpl_id.id,
            'product_id': self.product_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'ready_to_produce': 'all_available',  # Manufacturing trigger
        }
        
        bom = self.env['mrp.bom'].create(bom_vals)
        _logger.info(f"Created BOM {bom.id} for product {self.product_id.name}")
        
        # Create BOM lines
        component_count = 0
        for line in self.component_lines:
            if line.product_id and line.product_qty > 0:
                self.env['mrp.bom.line'].create({
                    'bom_id': bom.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_qty,
                    'product_uom_id': line.product_uom_id.id,
                })
                component_count += 1
        
        _logger.info(f"Added {component_count} components to BOM {bom.id}")
        
        # Verify product still has proper manufacturing routes
        template = self.product_tmpl_id
        product = self.product_id
        
        # Check routes on template and variant
        _logger.info(f"BOM Creator - Template {template.name} routes: {template.route_ids.mapped('name')}")
        if product and hasattr(product, 'route_ids'):
            _logger.info(f"BOM Creator - Variant {product.name} routes: {product.route_ids.mapped('name') if product.route_ids else 'Inherits from template'}")
        
        # If no routes, try to restore them
        if not template.route_ids:
            _logger.warning(f"Product {template.name} has no routes! Attempting to restore MTO and manufacturing routes.")
            
            # Find MTO and Manufacturing routes
            routes_to_add = []
            mto_route = self.env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
            if mto_route:
                routes_to_add.append(mto_route.id)
                
            manufacture_routes = self.env['stock.route'].search([
                ('rule_ids.action', '=', 'manufacture'),
                ('active', '=', True)
            ], limit=1)
            if manufacture_routes:
                routes_to_add.append(manufacture_routes[0].id)
                
            if routes_to_add:
                template.write({'route_ids': [(6, 0, routes_to_add)]})
                self.env.cr.commit()
                _logger.info(f"Restored routes {routes_to_add} to {template.name}")
            else:
                _logger.error(f"Could not find any routes to restore for {template.name}")
        
        # Update sale order line
        if self.sale_line_id:
            self.sale_line_id.write({
                'product_id': self.product_id.id,
                'name': self.product_id.display_name,  # Update description with product name
                'product_uom_qty': self.quantity,
                'price_unit': self.list_price,
                'is_custom_product': True,  # Mark as custom product
            })
            _logger.info(f"Updated sale order line {self.sale_line_id.id} with product {self.product_id.name}")
        
        # Close wizard and return to sale order
        return {'type': 'ir.actions.act_window_close'}


class SimpleBomLine(models.TransientModel):
    _name = 'simple.bom.line'
    _description = 'Simple BOM Line'

    wizard_id = fields.Many2one('simple.bom.creator', string='Wizard')
    product_id = fields.Many2one('product.product', string='Component', required=True)
    product_qty = fields.Float(string='Quantity', default=1.0, required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit', required=True)
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id