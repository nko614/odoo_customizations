from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'
    
    start_weight = fields.Float(
        string='Starting Paint Weight',
        digits='Product Unit of Measure',
        help='Total weight of paint at work order start'
    )
    
    end_weight = fields.Float(
        string='Ending Paint Weight',
        digits='Product Unit of Measure',
        help='Total weight of remaining paint at work order end'
    )
    
    delta_weight = fields.Float(
        string='Paint Used (Delta)',
        digits='Product Unit of Measure',
        compute='_compute_delta_weight',
        store=True,
        help='Amount of paint used (Start Weight - End Weight)'
    )
    
    weight_uom_id = fields.Many2one(
        'uom.uom',
        string='Weight Unit',
        default=lambda self: self.env.ref('uom.product_uom_lb', raise_if_not_found=False),
        help='Unit of measure for weight tracking'
    )
    
    paint_product_id = fields.Many2one(
        'product.product',
        string='Paint Product',
        compute='_compute_paint_product',
        store=True,
        help='The paint/material product being consumed (auto-detected from BOM)'
    )
    
    has_weight_tracking = fields.Boolean(
        string='Enable Weight Tracking',
        help='Enable paint weight tracking for this work order'
    )
    
    weight_captured_at_start = fields.Boolean(
        string='Start Weight Captured',
        default=False
    )
    
    weight_captured_at_end = fields.Boolean(
        string='End Weight Captured', 
        default=False
    )
    
    @api.depends('start_weight', 'end_weight')
    def _compute_delta_weight(self):
        for workorder in self:
            workorder.delta_weight = workorder.start_weight - workorder.end_weight
    
    @api.depends('production_id.move_raw_ids', 'has_weight_tracking')
    def _compute_paint_product(self):
        """Auto-detect paint product from BOM raw materials"""
        for workorder in self:
            if not workorder.has_weight_tracking or not workorder.production_id:
                workorder.paint_product_id = False
                continue
                
            # Look for paint products in BOM raw materials
            raw_moves = workorder.production_id.move_raw_ids
            paint_product = False
            
            # Strategy 1: Look for products with 'paint' in the name
            for move in raw_moves:
                if 'paint' in move.product_id.name.lower():
                    paint_product = move.product_id
                    break
            
            # Strategy 2: Look for products measured by weight (same category as weight_uom_id)
            if not paint_product and workorder.weight_uom_id:
                for move in raw_moves:
                    if move.product_uom.category_id == workorder.weight_uom_id.category_id:
                        paint_product = move.product_id
                        break
            
            # Strategy 3: Use the first consumable product
            if not paint_product:
                for move in raw_moves:
                    if move.product_id.type == 'consu':  # Consumable products
                        paint_product = move.product_id
                        break
            
            # Strategy 4: Fallback to first raw material
            if not paint_product and raw_moves:
                paint_product = raw_moves[0].product_id
                
            workorder.paint_product_id = paint_product
    
    def button_start(self, **kwargs):
        """Override to prompt for starting weight if weight tracking is enabled"""
        if self.has_weight_tracking and not self.weight_captured_at_start:
            return self.action_capture_start_weight()
        
        return super().button_start(**kwargs)
    
    def action_capture_start_weight(self):
        """Open form to capture starting weight"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enter Starting Paint Weight'),
            'res_model': 'mrp.workorder',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mrp_weight_tracking_clean.view_workorder_start_weight_form').id,
            'target': 'new',
        }
    
    def action_capture_end_weight(self):
        """Open form to capture ending weight"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enter Remaining Paint Weight'),
            'res_model': 'mrp.workorder',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mrp_weight_tracking_clean.view_workorder_end_weight_form').id,
            'target': 'new',
        }
    
    def confirm_start_weight(self):
        """Confirm the starting weight and close popup"""
        self.ensure_one()
        if self.start_weight <= 0:
            raise UserError(_('Starting weight must be greater than 0.'))
        self.weight_captured_at_start = True
        return {'type': 'ir.actions.act_window_close'}
    
    def confirm_end_weight(self):
        """Confirm the ending weight and close popup"""
        self.ensure_one()
        if self.end_weight < 0:
            raise UserError(_('Ending weight cannot be negative.'))
        if self.end_weight >= self.start_weight:
            raise UserError(_('Ending weight should be less than starting weight (%.2f %s).') % (self.start_weight, self.weight_uom_id.name or 'units'))
        self.weight_captured_at_end = True
        return {'type': 'ir.actions.act_window_close'}
    
    def button_finish(self):
        """Override to capture end weight before finishing"""
        if self.has_weight_tracking and not self.weight_captured_at_end:
            return self.action_capture_end_weight()
        
        # Create stock move for weight delta
        self._create_weight_delta_stock_move()
        
        return super().button_finish()
    
    def _create_weight_delta_stock_move(self):
        """Create stock move for the paint consumption (weight delta)"""
        self.ensure_one()
        
        if not self.has_weight_tracking or self.delta_weight <= 0:
            return False
        
        # Use the auto-detected paint product from BOM
        product = self.paint_product_id
        if not product:
            raise UserError(_('No paint product found in the bill of materials. Please add a paint product to the BOM or enable weight tracking to auto-detect it.'))
        
        # Determine locations for consumption
        production = self.production_id
        source_location = production.location_src_id  # Where paint is stored (inventory)
        dest_location = self.env.ref('stock.stock_location_production', raise_if_not_found=False) or production.location_dest_id  # Production consumption location
        
        # Convert weight to product UOM if needed
        quantity = self.delta_weight
        product_uom = product.uom_id
        if product_uom.category_id == self.weight_uom_id.category_id:
            quantity = self.weight_uom_id._compute_quantity(self.delta_weight, product_uom)
        
        # Directly update stock quantity
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', source_location.id)
        ], limit=1)
        
        if quant:
            # Reduce existing stock
            new_quantity = quant.quantity - quantity
            quant.write({'quantity': new_quantity})
        else:
            # Create new quant with negative quantity (consumed more than available)
            self.env['stock.quant'].create({
                'product_id': product.id,
                'location_id': source_location.id,
                'quantity': -quantity,
            })
        
        return True
    
    def toggle_weight_tracking(self):
        """Toggle weight tracking for this work order"""
        self.ensure_one()
        
        if self.state in ('done', 'cancel'):
            raise UserError(_('Cannot modify weight tracking on completed or cancelled work orders.'))
        
        # Toggle the weight tracking
        self.has_weight_tracking = not self.has_weight_tracking
        
        # Reset weight values if disabling
        if not self.has_weight_tracking:
            self.write({
                'start_weight': 0,
                'end_weight': 0,
                'weight_captured_at_start': False,
                'weight_captured_at_end': False,
                'paint_product_id': False,
            })
        
        # Show notification
        if self.has_weight_tracking:
            message = _('Weight tracking enabled for work order %s') % self.name
        else:
            message = _('Weight tracking disabled for work order %s') % self.name
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Weight Tracking'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }