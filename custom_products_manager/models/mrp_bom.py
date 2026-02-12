from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    is_custom_bom = fields.Boolean(
        string='Custom BOM',
        default=False,
        help="This is a custom Bill of Materials"
    )
    
    custom_config_id = fields.Many2one(
        'custom.product.config',
        string='Custom Configuration',
        help="Link to custom product configuration"
    )
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        help="Sales order this BOM was created for"
    )
    
    template_bom_id = fields.Many2one(
        'mrp.bom',
        string='Template BOM',
        help="Template BOM this custom BOM is based on"
    )
    
    estimated_cost = fields.Float(
        string='Estimated Cost',
        compute='_compute_estimated_cost',
        store=True,
        help="Total estimated cost of all components"
    )
    
    labor_cost = fields.Float(
        string='Labor Cost',
        default=0.0,
        help="Additional labor cost for this BOM"
    )
    
    overhead_cost = fields.Float(
        string='Overhead Cost',
        default=0.0,
        help="Overhead cost percentage or fixed amount"
    )
    
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_total_cost',
        store=True,
        help="Total cost including materials, labor, and overhead"
    )
    
    margin_percentage = fields.Float(
        string='Target Margin %',
        default=20.0,
        help="Target profit margin percentage"
    )
    
    suggested_price = fields.Float(
        string='Suggested Price',
        compute='_compute_suggested_price',
        help="Suggested selling price based on cost and margin"
    )
    
    complexity_level = fields.Selection([
        ('simple', 'Simple'),
        ('medium', 'Medium'),
        ('complex', 'Complex'),
        ('very_complex', 'Very Complex'),
    ], string='Complexity', default='medium',
       help="Manufacturing complexity level")
    
    lead_time_days = fields.Integer(
        string='Lead Time (Days)',
        default=1,
        help="Estimated manufacturing lead time in days"
    )
    
    notes = fields.Text(
        string='Manufacturing Notes',
        help="Special notes for manufacturing this product"
    )

    @api.depends('bom_line_ids.product_qty', 'bom_line_ids.product_id.standard_price')
    def _compute_estimated_cost(self):
        for bom in self:
            total_cost = 0
            for line in bom.bom_line_ids:
                component_cost = line.product_id.standard_price * line.product_qty
                total_cost += component_cost
            bom.estimated_cost = total_cost

    @api.depends('estimated_cost', 'labor_cost', 'overhead_cost')
    def _compute_total_cost(self):
        for bom in self:
            bom.total_cost = bom.estimated_cost + bom.labor_cost + bom.overhead_cost

    @api.depends('total_cost', 'margin_percentage')
    def _compute_suggested_price(self):
        for bom in self:
            if bom.total_cost and bom.margin_percentage:
                markup = 1 + (bom.margin_percentage / 100)
                bom.suggested_price = bom.total_cost * markup
            else:
                bom.suggested_price = bom.total_cost

    def action_create_manufacturing_order(self):
        """Create a manufacturing order from this BOM"""
        self.ensure_one()
        if not self.product_id:
            raise ValidationError(_("Cannot create manufacturing order without a product."))
        
        return {
            'name': _('Create Manufacturing Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': self.product_id.id,
                'default_bom_id': self.id,
                'default_product_qty': 1,
                'default_product_uom_id': self.product_id.uom_id.id,
            }
        }

    def action_copy_to_template(self):
        """Copy this custom BOM as a template for future use"""
        self.ensure_one()
        
        copy_vals = {
            'code': f"{self.code}-TEMPLATE",
            'is_custom_bom': False,
            'custom_config_id': False,
            'sale_order_id': False,
            'template_bom_id': False,
        }
        
        template_bom = self.copy(copy_vals)
        
        return {
            'name': _('Template BOM Created'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom',
            'res_id': template_bom.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_optimize_costs(self):
        """Open cost optimization wizard"""
        self.ensure_one()
        return {
            'name': _('Optimize BOM Costs'),
            'type': 'ir.actions.act_window',
            'res_model': 'bom.cost.optimizer',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bom_id': self.id,
            }
        }


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    component_type = fields.Selection([
        ('raw_material', 'Raw Material'),
        ('component', 'Component'),
        ('consumable', 'Consumable'),
        ('service', 'Service'),
        ('subcontract', 'Subcontract'),
    ], string='Component Type', default='raw_material',
       help="Type of component in the BOM")
    
    is_optional = fields.Boolean(
        string='Optional Component',
        default=False,
        help="This component is optional and can be excluded"
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Preferred Supplier',
        domain=[('is_company', '=', True), ('supplier_rank', '>', 0)],
        help="Preferred supplier for this component"
    )
    
    lead_time_days = fields.Integer(
        string='Lead Time (Days)',
        default=0,
        help="Lead time for this component in days"
    )
    
    unit_cost = fields.Float(
        string='Unit Cost',
        related='product_id.standard_price',
        help="Cost per unit of this component"
    )
    
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_total_cost',
        help="Total cost for this component line"
    )
    
    alternative_products = fields.Many2many(
        'product.product',
        string='Alternative Products',
        help="Alternative products that can be used instead"
    )
    
    notes = fields.Text(
        string='Component Notes',
        help="Special notes for this component"
    )

    @api.depends('product_qty', 'unit_cost')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = line.product_qty * line.unit_cost

    def action_view_alternatives(self):
        """View alternative products for this component"""
        self.ensure_one()
        return {
            'name': _('Alternative Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.alternative_products.ids)],
            'context': {'create': False}
        }

    def action_find_alternatives(self):
        """Find alternative products based on category and attributes"""
        self.ensure_one()
        
        # Search for products in same category with similar attributes
        domain = [
            ('categ_id', '=', self.product_id.categ_id.id),
            ('id', '!=', self.product_id.id),
            ('sale_ok', '=', True),
        ]
        
        alternatives = self.env['product.product'].search(domain, limit=10)
        self.alternative_products = [(6, 0, alternatives.ids)]
        
        return {
            'name': _('Found Alternatives'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_mode': 'list',
            'domain': [('id', 'in', alternatives.ids)],
            'context': {'create': False}
        }