from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class CustomProductConfig(models.Model):
    _name = 'custom.product.config'
    _description = 'Custom Product Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Configuration Name',
        required=True,
        help="Name for this custom product configuration"
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade',
        help="The product this configuration applies to"
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        help="Customer this configuration was created for"
    )
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        help="Sales order this configuration was created from"
    )
    
    template_id = fields.Many2one(
        'custom.product.template',
        string='Template',
        help="Template used to create this configuration"
    )
    
    configuration_data = fields.Text(
        string='Configuration Data',
        help="JSON data storing the product configuration"
    )
    
    bom_id = fields.Many2one(
        'mrp.bom',
        string='Bill of Materials',
        help="Bill of Materials for this custom product"
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('produced', 'In Production'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft')
    
    notes = fields.Text(
        string='Notes',
        help="Additional notes for this configuration"
    )
    
    image = fields.Binary(
        string='Image',
        help="Image of the custom product"
    )
    
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_total_cost',
        store=True,
        help="Total cost based on BOM"
    )
    
    estimated_price = fields.Float(
        string='Estimated Price',
        help="Estimated selling price"
    )

    @api.depends('bom_id', 'bom_id.bom_line_ids')
    def _compute_total_cost(self):
        for config in self:
            if config.bom_id:
                total_cost = 0
                for line in config.bom_id.bom_line_ids:
                    total_cost += line.product_id.standard_price * line.product_qty
                config.total_cost = total_cost
            else:
                config.total_cost = config.product_id.standard_price

    def action_create_bom(self):
        """Create a new BOM for this custom product"""
        self.ensure_one()
        return {
            'name': _('Create Bill of Materials'),
            'type': 'ir.actions.act_window',
            'res_model': 'bom.builder.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
                'default_product_id': self.product_id.id,
                'default_custom_config_id': self.id,
            }
        }

    def action_duplicate_config(self):
        """Duplicate this configuration"""
        self.ensure_one()
        copy_vals = {
            'name': f"{self.name} (Copy)",
            'template_id': self.template_id.id,
            'configuration_data': self.configuration_data,
            'notes': self.notes,
            'state': 'draft',
        }
        new_config = self.copy(copy_vals)
        
        return {
            'name': _('Custom Product Configuration'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.product.config',
            'res_id': new_config.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CustomProductTemplate(models.Model):
    _name = 'custom.product.template'
    _description = 'Custom Product Template'
    _order = 'sequence, name'

    name = fields.Char(
        string='Template Name',
        required=True,
        help="Name of the product template"
    )
    
    description = fields.Text(
        string='Description',
        help="Description of what this template is for"
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Sequence for ordering templates"
    )
    
    category_id = fields.Many2one(
        'product.category',
        string='Product Category',
        help="Default category for products created from this template"
    )
    
    default_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        help="Default unit of measure"
    )
    
    template_fields = fields.Text(
        string='Template Fields',
        help="JSON configuration for template fields"
    )
    
    default_bom_components = fields.Text(
        string='Default BOM Components',
        help="JSON list of default BOM components"
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Whether this template is active"
    )
    
    color = fields.Integer(
        string='Color',
        help="Color for the template in kanban view"
    )
    
    icon = fields.Char(
        string='Icon',
        help="Icon class for the template"
    )
    
    base_price = fields.Float(
        string='Base Price',
        help="Base price for products created from this template"
    )
    
    complexity_level = fields.Selection([
        ('simple', 'Simple'),
        ('medium', 'Medium'),
        ('complex', 'Complex'),
    ], string='Complexity Level', default='simple')
    
    lead_time_days = fields.Integer(
        string='Lead Time (Days)',
        default=7,
        help="Expected lead time in days"
    )
    
    component_ids = fields.One2many(
        'custom.product.component',
        'template_id',
        string='Template Components'
    )

    def action_create_product_from_template(self):
        """Create a new custom product using this template"""
        self.ensure_one()
        return {
            'name': _('Create Product from Template'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.product.creator',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
            }
        }


class CustomProductComponent(models.Model):
    _name = 'custom.product.component'
    _description = 'Custom Product Component'
    _order = 'sequence'

    config_id = fields.Many2one(
        'custom.product.config',
        string='Configuration',
        ondelete='cascade'
    )
    
    template_id = fields.Many2one(
        'custom.product.template',
        string='Template',
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    component_type = fields.Selection([
        ('product', 'Product'),
        ('service', 'Service'),
        ('material', 'Material'),
        ('labor', 'Labor'),
        ('other', 'Other'),
    ], string='Type', default='product')
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )
    
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        required=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id'
    )
    
    unit_cost = fields.Float(
        string='Unit Cost',
        related='product_id.standard_price'
    )
    
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_total_cost'
    )
    
    notes = fields.Text(
        string='Notes'
    )
    
    is_required = fields.Boolean(
        string='Required',
        default=True,
        help="Whether this component is required"
    )
    
    description = fields.Text(
        string='Description',
        help="Description of this component"
    )

    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for component in self:
            component.total_cost = component.quantity * component.unit_cost