from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_custom_product = fields.Boolean(
        string='Custom Product',
        default=False,
        help="Mark this product as customizable"
    )
    
    custom_product_type = fields.Selection([
        ('configurable', 'Configurable Product'),
        ('made_to_order', 'Made to Order'),
        ('template_based', 'Template Based'),
        ('fully_custom', 'Fully Custom'),
    ], string='Custom Product Type', 
       help="Type of custom product configuration")
    
    allow_custom_bom = fields.Boolean(
        string='Allow Custom BOM',
        default=False,
        help="Allow creating custom BOMs for this product"
    )
    
    custom_config_count = fields.Integer(
        string='Configurations Count',
        compute='_compute_custom_config_count',
        help="Number of custom configurations for this product"
    )
    
    base_cost_multiplier = fields.Float(
        string='Base Cost Multiplier',
        default=1.0,
        help="Multiplier for base cost calculations"
    )
    
    custom_fields_config = fields.Text(
        string='Custom Fields Configuration',
        help="JSON configuration for custom fields"
    )

    @api.model
    def _ensure_custom_product_routes(self):
        """Ensure all custom products have MTO and Manufacture routes"""
        # Get MTO and Manufacture routes by searching for them
        mto_route = self.env['stock.route'].search([
            ('name', 'ilike', 'Replenish on Order'),
            '|', ('name', 'ilike', 'MTO'), ('name', 'ilike', 'Make To Order')
        ], limit=1)
        
        manufacture_route = self.env['stock.route'].search([
            ('name', 'ilike', 'Manufacture'),
            ('name', 'ilike', 'Manufacturing')
        ], limit=1)
        
        # Fallback to XML IDs if search doesn't work
        if not mto_route:
            mto_route = self.env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
        if not manufacture_route:
            manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
        
        route_ids = []
        if mto_route:
            route_ids.append(mto_route.id)
        if manufacture_route:
            route_ids.append(manufacture_route.id)
        
        if route_ids:
            # Find all custom products without the correct routes
            custom_products = self.search([('is_custom_product', '=', True)])
            for product in custom_products:
                current_routes = set(product.route_ids.ids)
                required_routes = set(route_ids)
                if not required_routes.issubset(current_routes):
                    # Add missing routes
                    all_routes = current_routes | required_routes
                    product.route_ids = [(6, 0, list(all_routes))]

    def action_debug_routes(self):
        """Debug method to show which routes are available and assigned"""
        self.ensure_one()
        
        # Get available routes
        all_routes = self.env['stock.route'].search([])
        mto_routes = all_routes.filtered(lambda r: 'mto' in r.name.lower() or 'make to order' in r.name.lower() or 'replenish on order' in r.name.lower())
        manufacture_routes = all_routes.filtered(lambda r: 'manufacture' in r.name.lower() or 'manufacturing' in r.name.lower())
        
        message = f"Product: {self.name}\n\n"
        message += f"Current Routes: {', '.join(self.route_ids.mapped('name'))}\n\n"
        message += f"Available MTO Routes: {', '.join(mto_routes.mapped('name'))}\n"
        message += f"Available Manufacture Routes: {', '.join(manufacture_routes.mapped('name'))}\n\n"
        message += f"Is Custom Product: {self.is_custom_product}"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Route Debug Info',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to automatically set routes for custom products"""
        templates = super().create(vals_list)
        
        # Set routes for custom products
        custom_templates = templates.filtered('is_custom_product')
        if custom_templates:
            custom_templates._set_custom_product_routes()
        
        return templates

    def write(self, vals):
        """Override write to set routes when is_custom_product is set to True"""
        result = super().write(vals)
        
        if vals.get('is_custom_product'):
            self._set_custom_product_routes()
        
        return result

    def _set_custom_product_routes(self):
        """Set MTO and Manufacture routes for custom products"""
        # Get MTO and Manufacture routes by searching for them
        mto_route = self.env['stock.route'].search([
            ('name', 'ilike', 'Replenish on Order'),
            '|', ('name', 'ilike', 'MTO'), ('name', 'ilike', 'Make To Order')
        ], limit=1)
        
        manufacture_route = self.env['stock.route'].search([
            ('name', 'ilike', 'Manufacture'),
            ('name', 'ilike', 'Manufacturing')
        ], limit=1)
        
        # Fallback to XML IDs if search doesn't work
        if not mto_route:
            mto_route = self.env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
        if not manufacture_route:
            manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
        
        route_ids = []
        if mto_route:
            route_ids.append(mto_route.id)
        if manufacture_route:
            route_ids.append(manufacture_route.id)
        
        if route_ids:
            for template in self:
                current_routes = set(template.route_ids.ids)
                required_routes = set(route_ids)
                if not required_routes.issubset(current_routes):
                    # Add missing routes
                    all_routes = current_routes | required_routes
                    template.route_ids = [(6, 0, list(all_routes))]

    def _compute_custom_config_count(self):
        for template in self:
            template.custom_config_count = self.env['custom.product.config'].search_count([
                ('product_id.product_tmpl_id', '=', template.id)
            ])

    def action_view_custom_configurations(self):
        """View all custom configurations for this product template"""
        self.ensure_one()
        return {
            'name': _('Custom Configurations'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.product.config',
            'view_mode': 'list,form',
            'domain': [('product_id.product_tmpl_id', '=', self.id)],
            'context': {'create': False}
        }

    def action_create_custom_variant(self):
        """Create a new custom variant for this template"""
        self.ensure_one()
        return {
            'name': _('Create Custom Variant'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.product.creator',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.id,
                'default_is_variant_creation': True,
            }
        }


class ProductProduct(models.Model):
    _inherit = 'product.product'

    custom_config_id = fields.Many2one(
        'custom.product.config',
        string='Custom Configuration',
        help="Link to custom product configuration"
    )
    
    is_custom_variant = fields.Boolean(
        string='Custom Variant',
        default=False,
        help="This is a custom product variant"
    )
    
    parent_product_id = fields.Many2one(
        'product.product',
        string='Parent Product',
        help="Parent product for custom variants"
    )
    
    custom_variant_count = fields.Integer(
        string='Custom Variants Count',
        compute='_compute_custom_variant_count',
        help="Number of custom variants created from this product"
    )

    def _compute_custom_variant_count(self):
        for product in self:
            product.custom_variant_count = self.env['product.product'].search_count([
                ('parent_product_id', '=', product.id)
            ])

    def action_view_custom_variants(self):
        """View custom variants of this product"""
        self.ensure_one()
        return {
            'name': _('Custom Variants'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'domain': [('parent_product_id', '=', self.id)],
            'context': {'create': False}
        }

    def action_create_bom_from_product(self):
        """Create a BOM for this product"""
        self.ensure_one()
        return {
            'name': _('Create Bill of Materials'),
            'type': 'ir.actions.act_window',
            'res_model': 'bom.builder.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.product_tmpl_id.id,
                'default_product_id': self.id,
            }
        }

    def action_duplicate_as_custom(self):
        """Duplicate this product as a custom product"""
        self.ensure_one()
        
        # Get MTO and Manufacture routes by searching for them
        mto_route = self.env['stock.route'].search([
            ('name', 'ilike', 'Replenish on Order'),
            '|', ('name', 'ilike', 'MTO'), ('name', 'ilike', 'Make To Order')
        ], limit=1)
        
        manufacture_route = self.env['stock.route'].search([
            ('name', 'ilike', 'Manufacture'),
            ('name', 'ilike', 'Manufacturing')
        ], limit=1)
        
        # Fallback to XML IDs if search doesn't work
        if not mto_route:
            mto_route = self.env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
        if not manufacture_route:
            manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
        
        route_ids = []
        if mto_route:
            route_ids.append(mto_route.id)
        if manufacture_route:
            route_ids.append(manufacture_route.id)
        
        # Create a copy with custom product settings
        copy_vals = {
            'name': f"{self.name} (Custom)",
            'default_code': f"{self.default_code or 'PROD'}-CUSTOM",
            'is_custom_variant': True,
            'parent_product_id': self.id,
            'route_ids': [(6, 0, route_ids)] if route_ids else False,
        }
        
        custom_product = self.copy(copy_vals)
        
        # Create custom configuration
        config_vals = {
            'name': f"Config for {custom_product.name}",
            'product_id': custom_product.id,
        }
        config = self.env['custom.product.config'].create(config_vals)
        custom_product.custom_config_id = config.id
        
        return {
            'name': _('Custom Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': custom_product.id,
            'view_mode': 'form',
            'target': 'current',
        }