from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BomBuilderWizard(models.TransientModel):
    _name = 'bom.builder.wizard'
    _description = 'Interactive BOM Builder'

    # BOM Information
    bom_id = fields.Many2one(
        'mrp.bom',
        string='Bill of Materials',
        required=True,
        ondelete='cascade'
    )
    
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='bom_id.product_tmpl_id',
        readonly=True
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='bom_id.product_id',
        readonly=True
    )
    
    # Wizard fields
    component_lines = fields.One2many(
        'bom.builder.line',
        'wizard_id',
        string='Components'
    )
    
    # Search and add components
    search_product = fields.Char(
        string='Search Products',
        help="Search for products to add as components"
    )
    
    search_results = fields.Many2many(
        'product.product',
        string='Search Results',
        compute='_compute_search_results',
        help="Products matching the search"
    )
    
    # Quick add popular components
    popular_components = fields.Many2many(
        'product.product',
        'bom_builder_popular_rel',
        string='Popular Components',
        compute='_compute_popular_components'
    )
    
    # BOM totals
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_totals'
    )
    
    total_weight = fields.Float(
        string='Total Weight',
        compute='_compute_totals'
    )
    
    # Context
    custom_config_id = fields.Many2one(
        'custom.product.config',
        string='Custom Configuration'
    )
    
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Sales Order Line'
    )
    
    just_created = fields.Boolean(
        string='Just Created',
        default=False,
        help="BOM was just created and needs components"
    )

    @api.depends('search_product')
    def _compute_search_results(self):
        for wizard in self:
            if wizard.search_product and len(wizard.search_product) >= 3:
                domain = [
                    '|', '|',
                    ('name', 'ilike', wizard.search_product),
                    ('default_code', 'ilike', wizard.search_product),
                    ('barcode', 'ilike', wizard.search_product),
                    ('purchase_ok', '=', True),
                    ('product_tmpl_id.type', 'in', ['consu']),
                ]
                products = self.env['product.product'].search(domain, limit=20)
                wizard.search_results = products
            else:
                wizard.search_results = self.env['product.product']

    def _compute_popular_components(self):
        """Get popular components based on usage in other BOMs"""
        for wizard in self:
            # Find most used products in BOMs of same category
            category_id = wizard.product_id.categ_id.id if wizard.product_id else False
            
            if category_id:
                # Get products from BOMs in same category
                similar_boms = self.env['mrp.bom'].search([
                    ('product_tmpl_id.categ_id', '=', category_id),
                    ('id', '!=', wizard.bom_id.id)
                ])
                
                component_usage = {}
                for bom in similar_boms:
                    for line in bom.bom_line_ids:
                        product_id = line.product_id.id
                        component_usage[product_id] = component_usage.get(product_id, 0) + 1
                
                # Get top 10 most used components
                popular_ids = sorted(component_usage.keys(), 
                                   key=lambda x: component_usage[x], 
                                   reverse=True)[:10]
                
                wizard.popular_components = self.env['product.product'].browse(popular_ids)
            else:
                wizard.popular_components = self.env['product.product']

    @api.depends('component_lines.total_cost')
    def _compute_totals(self):
        for wizard in self:
            wizard.total_cost = sum(line.total_cost for line in wizard.component_lines)
            wizard.total_weight = sum(line.total_weight for line in wizard.component_lines)

    @api.model
    def default_get(self, fields_list):
        """Load existing BOM components"""
        result = super().default_get(fields_list)
        
        bom_id = self.env.context.get('default_bom_id')
        if bom_id:
            bom = self.env['mrp.bom'].browse(bom_id)
            component_lines = []
            
            for line in bom.bom_line_ids:
                component_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_qty': line.product_qty,
                    'product_uom_id': line.product_uom_id.id,
                    'bom_line_id': line.id,
                    'component_type': getattr(line, 'component_type', 'raw_material'),
                    'is_optional': getattr(line, 'is_optional', False),
                }))
            
            result['component_lines'] = component_lines
        
        return result

    def action_add_component(self):
        """Add selected components to the BOM"""
        self.ensure_one()
        
        # This will be called from JavaScript with product_id in context
        product_id = self.env.context.get('product_id')
        if not product_id:
            raise ValidationError(_("No product selected."))
        
        product = self.env['product.product'].browse(product_id)
        
        # Check if component already exists
        existing = self.component_lines.filtered(lambda l: l.product_id.id == product_id)
        if existing:
            # Increase quantity
            existing[0].product_qty += 1
        else:
            # Add new component
            self.component_lines = [(0, 0, {
                'product_id': product_id,
                'product_qty': 1,
                'product_uom_id': product.uom_id.id,
                'component_type': 'raw_material',
            })]
        
        return {'type': 'ir.actions.do_nothing'}

    def action_save_bom(self):
        """Save the BOM with all components"""
        self.ensure_one()
        
        # Clear existing BOM lines
        self.bom_id.bom_line_ids.unlink()
        
        # Create new BOM lines
        for line in self.component_lines:
            if line.product_qty > 0:  # Only create lines with positive quantity
                bom_line_vals = {
                    'bom_id': self.bom_id.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_qty,
                    'product_uom_id': line.product_uom_id.id,
                    'sequence': line.sequence,
                }
                
                # Add custom fields if they exist
                if hasattr(line, 'component_type'):
                    bom_line_vals['component_type'] = line.component_type
                if hasattr(line, 'is_optional'):
                    bom_line_vals['is_optional'] = line.is_optional
                if hasattr(line, 'supplier_id'):
                    bom_line_vals['supplier_id'] = line.supplier_id.id
                
                self.env['mrp.bom.line'].create(bom_line_vals)
        
        # Update custom config if linked
        if self.custom_config_id:
            self.custom_config_id.bom_id = self.bom_id.id
        
        # Update sale order line if linked
        if self.sale_line_id:
            self.sale_line_id.bom_id = self.bom_id.id
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success!'),
                'message': _('Bill of Materials saved with %d components.') % len(self.component_lines),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_save_and_close(self):
        """Save BOM and close wizard"""
        self.action_save_bom()
        return {'type': 'ir.actions.act_window_close'}

    def action_save_and_view_bom(self):
        """Save BOM and open BOM form"""
        self.action_save_bom()
        
        return {
            'name': _('Bill of Materials'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom',
            'res_id': self.bom_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_import_from_template(self):
        """Import components from a template BOM"""
        self.ensure_one()
        
        return {
            'name': _('Import from Template'),
            'type': 'ir.actions.act_window',
            'res_model': 'bom.template.selector',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wizard_id': self.id,
                'default_product_category_id': self.product_id.categ_id.id,
            }
        }


class BomBuilderLine(models.TransientModel):
    _name = 'bom.builder.line'
    _description = 'BOM Builder Component Line'
    _order = 'sequence, product_id'

    wizard_id = fields.Many2one(
        'bom.builder.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain=[('product_tmpl_id.type', 'in', ['consu'])]
    )
    
    product_qty = fields.Float(
        string='Quantity',
        default=1.0,
        required=True
    )
    
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True
    )
    
    component_type = fields.Selection([
        ('raw_material', 'Raw Material'),
        ('component', 'Component'),
        ('consumable', 'Consumable'),
        ('service', 'Service'),
    ], string='Type', default='raw_material')
    
    is_optional = fields.Boolean(
        string='Optional',
        default=False
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        domain=[('supplier_rank', '>', 0)]
    )
    
    # Computed fields
    unit_cost = fields.Float(
        string='Unit Cost',
        related='product_id.standard_price'
    )
    
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_totals'
    )
    
    unit_weight = fields.Float(
        string='Unit Weight',
        related='product_id.weight'
    )
    
    total_weight = fields.Float(
        string='Total Weight',
        compute='_compute_totals'
    )
    
    # Link to existing BOM line if editing
    bom_line_id = fields.Many2one(
        'mrp.bom.line',
        string='BOM Line'
    )

    @api.depends('product_qty', 'unit_cost', 'unit_weight')
    def _compute_totals(self):
        for line in self:
            line.total_cost = line.product_qty * line.unit_cost
            line.total_weight = line.product_qty * line.unit_weight

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update UOM when product changes"""
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id.id
            
            # Set default supplier if available
            if self.product_id.seller_ids:
                self.supplier_id = self.product_id.seller_ids[0].partner_id.id

    def action_remove_component(self):
        """Remove this component from the BOM"""
        self.unlink()
        return {'type': 'ir.actions.do_nothing'}

    def action_duplicate_component(self):
        """Duplicate this component line"""
        self.copy({'sequence': self.sequence + 1})
        return {'type': 'ir.actions.do_nothing'}