from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BomTemplateSelector(models.TransientModel):
    _name = 'bom.template.selector'
    _description = 'BOM Template Selector'

    wizard_id = fields.Many2one(
        'bom.builder.wizard',
        string='BOM Builder Wizard',
        required=True
    )
    
    product_category_id = fields.Many2one(
        'product.category',
        string='Product Category'
    )
    
    template_bom_id = fields.Many2one(
        'mrp.bom',
        string='Template BOM',
        required=True,
        domain=[('template_bom_id', '=', False), ('is_custom_bom', '=', False)]
    )
    
    include_optional_components = fields.Boolean(
        string='Include Optional Components',
        default=True,
        help="Include optional components from the template"
    )
    
    template_components = fields.One2many(
        'mrp.bom.line',
        related='template_bom_id.bom_line_ids',
        readonly=True
    )

    def action_import_template(self):
        """Import components from selected template"""
        self.ensure_one()
        
        if not self.template_bom_id:
            raise ValidationError(_("Please select a template BOM."))
        
        wizard = self.wizard_id
        
        # Clear existing components if user confirms
        # (You might want to add a confirmation dialog here)
        
        # Import components from template
        component_lines = []
        for template_line in self.template_bom_id.bom_line_ids:
            # Skip optional components if not requested
            if hasattr(template_line, 'is_optional') and template_line.is_optional and not self.include_optional_components:
                continue
                
            component_vals = {
                'product_id': template_line.product_id.id,
                'product_qty': template_line.product_qty,
                'product_uom_id': template_line.product_uom_id.id,
                'component_type': getattr(template_line, 'component_type', 'raw_material'),
                'is_optional': getattr(template_line, 'is_optional', False),
                'supplier_id': getattr(template_line, 'supplier_id', False) and template_line.supplier_id.id,
                'sequence': template_line.sequence,
            }
            component_lines.append((0, 0, component_vals))
        
        # Update wizard with imported components
        wizard.component_lines = [(5, 0, 0)] + component_lines  # Clear existing and add new
        
        # Mark template as source
        wizard.bom_id.template_bom_id = self.template_bom_id.id
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Template Imported'),
                'message': _('Successfully imported %d components from template.') % len(component_lines),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.onchange('product_category_id')
    def _onchange_product_category_id(self):
        """Filter templates by category"""
        if self.product_category_id:
            return {
                'domain': {
                    'template_bom_id': [
                        ('template_bom_id', '=', False),
                        ('is_custom_bom', '=', False),
                        ('product_tmpl_id.categ_id', 'child_of', self.product_category_id.id)
                    ]
                }
            }
        else:
            return {
                'domain': {
                    'template_bom_id': [
                        ('template_bom_id', '=', False),
                        ('is_custom_bom', '=', False)
                    ]
                }
            }