from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SimpleProductCreator(models.TransientModel):
    _name = 'simple.product.creator'
    _description = 'Simple Product Creator'

    # Basic product info
    product_name = fields.Char(string='Product Name', required=True)
    product_code = fields.Char(string='Product Code')
    list_price = fields.Float(string='Sales Price', default=100.0)
    cost_price = fields.Float(string='Cost Price', default=50.0)
    
    # Context fields
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Line')
    order_id = fields.Many2one('sale.order', string='Sale Order')
    partner_id = fields.Many2one('res.partner', string='Customer')
    quantity = fields.Float(string='Quantity', default=1.0)

    def action_create_product_and_bom(self):
        """Create product and proceed to BOM creation"""
        self.ensure_one()
        
        import logging
        _logger = logging.getLogger(__name__)
        
        # Find routes using a more direct approach
        route_ids = []
        
        # Method 1: Try common XML IDs first (most reliable)
        try:
            mto_route = self.env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
            if mto_route:
                route_ids.append(mto_route.id)
                _logger.info(f"Found MTO route: {mto_route.name}")
        except:
            pass
            
        try:
            manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
            if manufacture_route:
                route_ids.append(manufacture_route.id)
                _logger.info(f"Found Manufacture route: {manufacture_route.name}")
        except:
            pass
        
        # Method 2: Search by name if XML IDs didn't work
        if not route_ids:
            all_routes = self.env['stock.route'].search([('active', '=', True)])
            for route in all_routes:
                name_lower = route.name.lower()
                if any(pattern in name_lower for pattern in ['mto', 'make to order', 'replenish on order']):
                    route_ids.append(route.id)
                    _logger.info(f"Found MTO-like route: {route.name}")
                if any(pattern in name_lower for pattern in ['manufacture', 'manufacturing']):
                    route_ids.append(route.id) 
                    _logger.info(f"Found Manufacture-like route: {route.name}")
                    
        # Method 3: If still no routes, try to find by rules
        if not route_ids:
            # Look for any route that has manufacturing rules
            manufacture_routes = self.env['stock.route'].search([
                ('rule_ids.action', '=', 'manufacture'),
                ('active', '=', True)
            ])
            if manufacture_routes:
                route_ids.append(manufacture_routes[0].id)
                _logger.info(f"Found route with manufacture rules: {manufacture_routes[0].name}")
                
        # Create product template for manufacturing
        template_vals = {
            'name': self.product_name,
            'type': 'consu',  # Goods - valid in Odoo 18
            'list_price': self.list_price,
            'standard_price': self.cost_price,
            'sale_ok': True,
            'purchase_ok': True,
        }
        
        template = self.env['product.template'].create(template_vals)
        product = template.product_variant_ids[0]
        
        # Apply routes using multiple methods to ensure they stick
        if route_ids:
            # Remove duplicates
            route_ids = list(set(route_ids))
            _logger.info(f"Applying routes {route_ids} to product template {template.name} (ID: {template.id})")
            
            # Method A: Write to template after creation
            template.write({'route_ids': [(6, 0, route_ids)]})
            
            # Method B: Force commit and refresh cache
            self.env.cr.commit()
            template.invalidate_recordset(['route_ids'])
            
            # Method C: Also apply routes to the product variant directly if needed
            if product and hasattr(product, 'route_ids'):
                product.write({'route_ids': [(6, 0, route_ids)]})
                _logger.info(f"Applied routes to product variant {product.name} (ID: {product.id})")
            
            # Method D: Verify and use SQL if template still has no routes
            if not template.route_ids:
                _logger.warning("Routes not applied via ORM, using direct SQL")
                for route_id in route_ids:
                    # Insert for template
                    self.env.cr.execute("""
                        INSERT INTO stock_route_product (route_id, product_id) 
                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """, (route_id, template.id))
                    
                    # Also insert for variant if it exists and is different
                    if product and product.id != template.id:
                        self.env.cr.execute("""
                            INSERT INTO stock_route_product (route_id, product_id) 
                            VALUES (%s, %s) ON CONFLICT DO NOTHING
                        """, (route_id, product.id))
                        
                self.env.cr.commit()
                template.invalidate_recordset(['route_ids'])
                if product:
                    product.invalidate_recordset(['route_ids'])
                    
            # Final verification
            _logger.info(f"Template final routes: {template.route_ids.mapped('name')}")
            if product and hasattr(product, 'route_ids'):
                _logger.info(f"Variant final routes: {product.route_ids.mapped('name') if product.route_ids else 'None - inherits from template'}")
        else:
            _logger.error("No routes found! Product may not work correctly for manufacturing orders.")
        
        # Set product code if provided
        if self.product_code:
            product.default_code = self.product_code
        
        # Open BOM creator wizard
        return {
            'name': _('Create Bill of Materials'),
            'type': 'ir.actions.act_window',
            'res_model': 'simple.bom.creator',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': product.id,
                'default_product_tmpl_id': template.id,
                'default_sale_line_id': self.sale_line_id.id,
                'default_order_id': self.order_id.id,
                'default_quantity': self.quantity,
                'default_list_price': self.list_price,
            }
        }