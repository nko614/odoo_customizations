from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class CustomProductCreator(models.TransientModel):
    _name = 'custom.product.creator'
    _description = 'Custom Product Creator Wizard'

    # Basic Information
    product_name = fields.Char(
        string='Product Name',
        required=True,
        help="Name for the new custom product"
    )
    
    product_code = fields.Char(
        string='Internal Reference',
        help="Internal reference/SKU for the product"
    )
    
    description = fields.Text(
        string='Description',
        help="Product description"
    )
    
    # Template and Category
    template_id = fields.Many2one(
        'custom.product.template',
        string='Product Template',
        help="Base template for this custom product"
    )
    
    category_id = fields.Many2one(
        'product.category',
        string='Product Category',
        required=True,
        help="Product category"
    )
    
    # Pricing
    list_price = fields.Float(
        string='Sales Price',
        default=0.0,
        required=True,
        help="Selling price for this product"
    )
    
    cost_price = fields.Float(
        string='Cost Price',
        default=0.0,
        help="Cost price for this product"
    )
    
    # Units
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True,
        default=lambda self: self.env.ref('uom.product_uom_unit', raise_if_not_found=False),
        help="Unit of measure for this product"
    )
    
    uom_po_id = fields.Many2one(
        'uom.uom',
        string='Purchase Unit of Measure',
        help="Unit of measure for purchases"
    )
    
    # Product Type
    detailed_type = fields.Selection([
        ('consu', 'Goods'),
        ('service', 'Service'),
        ('combo', 'Combo'),
    ], string='Product Type', default='consu', required=True)
    
    # Inventory
    tracking = fields.Selection([
        ('none', 'No Tracking'),
        ('lot', 'By Lots'),
        ('serial', 'By Unique Serial Number'),
    ], string='Tracking', default='none')
    
    # Manufacturing
    create_bom = fields.Boolean(
        string='Create Bill of Materials',
        default=True,
        help="Create a BOM for this custom product"
    )
    
    bom_type = fields.Selection([
        ('normal', 'Manufacture this product'),
        ('phantom', 'Kit'),
        ('subcontract', 'Subcontracting'),
    ], string='BOM Type', default='normal')
    
    # Context fields
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        help="Sales order to add this product to"
    )
    
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Sales Order Line',
        help="Sales order line to update"
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        help="Customer for this custom product"
    )
    
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        help="Quantity to add to sales order"
    )
    
    # Custom fields for configuration
    custom_fields = fields.Text(
        string='Custom Configuration',
        help="JSON data for custom fields"
    )
    
    # Image
    image_1920 = fields.Binary(
        string='Image',
        help="Product image"
    )
    
    # Advanced options
    can_be_sold = fields.Boolean(
        string='Can be Sold',
        default=True
    )
    
    can_be_purchased = fields.Boolean(
        string='Can be Purchased',
        default=True
    )
    
    is_storable = fields.Boolean(
        string='Is Storable',
        compute='_compute_is_storable'
    )

    @api.depends('detailed_type')
    def _compute_is_storable(self):
        for wizard in self:
            wizard.is_storable = wizard.detailed_type == 'consu'

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load template defaults"""
        if self.template_id:
            if self.template_id.category_id:
                self.category_id = self.template_id.category_id.id
            if self.template_id.default_uom_id:
                self.uom_id = self.template_id.default_uom_id.id
            if self.template_id.template_fields:
                self.custom_fields = self.template_id.template_fields

    @api.onchange('product_name')
    def _onchange_product_name(self):
        """Auto-generate product code"""
        if self.product_name and not self.product_code:
            # Generate code from name
            code = self.product_name.upper().replace(' ', '-')[:10]
            # Add timestamp suffix for uniqueness
            import time
            suffix = str(int(time.time()))[-4:]
            self.product_code = f"{code}-{suffix}"

    @api.onchange('detailed_type')
    def _onchange_detailed_type(self):
        """Update tracking based on product type"""
        if self.detailed_type != 'consu':
            self.tracking = 'none'
            self.create_bom = False

    def action_create_product(self):
        """Create the custom product and add to sales order"""
        self.ensure_one()
        
        # Validate required fields
        if not self.product_name:
            raise ValidationError(_("Product name is required."))
        
        # Check for duplicate product codes
        if self.product_code:
            existing = self.env['product.product'].search([
                ('default_code', '=', self.product_code)
            ], limit=1)
            if existing:
                raise ValidationError(_("Product with code '%s' already exists.") % self.product_code)
        
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
        
        # Create product template first
        template_vals = {
            'name': self.product_name,
            'categ_id': self.category_id.id,
            'list_price': self.list_price,
            'standard_price': self.cost_price,
            'uom_id': self.uom_id.id,
            'uom_po_id': self.uom_po_id.id or self.uom_id.id,
            'type': self.detailed_type,
            'tracking': self.tracking,
            'sale_ok': self.can_be_sold,
            'purchase_ok': self.can_be_purchased,
            'is_custom_product': True,
            'image_1920': self.image_1920,
            'route_ids': [(6, 0, route_ids)] if route_ids else False,
        }
        
        template = self.env['product.template'].create(template_vals)
        
        # Get the product variant
        product = template.product_variant_ids[0]
        if self.product_code:
            product.default_code = self.product_code
        
        # Create custom configuration
        config_vals = {
            'name': f"Config for {self.product_name}",
            'product_id': product.id,
            'partner_id': self.partner_id.id,
            'sale_order_id': self.sale_order_id.id,
            'template_id': self.template_id.id,
            'configuration_data': self.custom_fields,
            'estimated_price': self.list_price,
            'state': 'confirmed',
        }
        
        config = self.env['custom.product.config'].create(config_vals)
        product.custom_config_id = config.id
        
        # Create BOM if requested
        bom = None
        if self.create_bom and self.detailed_type == 'consu':
            bom_vals = {
                'product_tmpl_id': product.product_tmpl_id.id,
                'product_id': product.id,
                'product_qty': 1,
                'type': self.bom_type,
                'code': f"BOM-{product.default_code or product.name}",
                'is_custom_bom': True,
                'custom_config_id': config.id,
                'sale_order_id': self.sale_order_id.id,
            }
            bom = self.env['mrp.bom'].create(bom_vals)
            config.bom_id = bom.id
        
        # Add to sales order if specified
        if self.sale_order_id:
            if self.sale_line_id:
                # Update existing line
                self.sale_line_id.write({
                    'product_id': product.id,
                    'product_uom_qty': self.quantity,
                    'is_custom_product': True,
                    'custom_product_id': config.id,
                    'bom_id': bom.id if bom else False,
                })
            else:
                # Create new line
                line_vals = {
                    'order_id': self.sale_order_id.id,
                    'product_id': product.id,
                    'product_uom_qty': self.quantity,
                    'price_unit': self.list_price,
                    'is_custom_product': True,
                    'custom_product_id': config.id,
                    'bom_id': bom.id if bom else False,
                }
                self.env['sale.order.line'].create(line_vals)
        
        # Return action based on what was created
        if self.create_bom and bom:
            # Open BOM builder if BOM was created
            return {
                'name': _('Build Bill of Materials'),
                'type': 'ir.actions.act_window',
                'res_model': 'bom.builder.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_bom_id': bom.id,
                    'default_custom_config_id': config.id,
                    'just_created': True,
                }
            }
        else:
            # Show success message and close
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _('Custom product "%s" created successfully.') % self.product_name,
                    'type': 'success',
                    'sticky': False,
                }
            }

    def action_create_and_continue(self):
        """Create product and open form for editing"""
        result = self.action_create_product()
        
        # If a notification was returned, we need to find the created product
        if result.get('tag') == 'display_notification':
            # Find the product we just created
            product = self.env['product.product'].search([
                ('name', '=', self.product_name)
            ], limit=1, order='id desc')
            
            if product:
                return {
                    'name': _('Custom Product'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'product.product',
                    'res_id': product.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        
        return result

    def action_preview_product(self):
        """Preview the product configuration"""
        self.ensure_one()
        
        preview_data = {
            'name': self.product_name,
            'code': self.product_code,
            'category': self.category_id.name,
            'price': self.list_price,
            'cost': self.cost_price,
            'type': dict(self._fields['detailed_type'].selection)[self.detailed_type],
            'template': self.template_id.name if self.template_id else 'None',
        }
        
        message = _("Product Preview:\n\n")
        for key, value in preview_data.items():
            message += f"{key.title()}: {value}\n"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Product Preview'),
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }