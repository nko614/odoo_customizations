from odoo import models, api, fields, _
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    def action_open_reward_wizard(self):
        """Called when reward button is clicked"""
        # First call the original method
        result = super(SaleOrder, self).action_open_reward_wizard()
        # Schedule a deferred adjustment
        self.env.cr.execute("SELECT nextval('ir_cron_trigger_seq')")
        self.env.cr.commit()
        # Return result
        return result
        
    def write(self, vals):
        """Override to intercept the order write"""
        result = super(SaleOrder, self).write(vals)
        
        # Check if the write involves order lines
        if 'order_line' in vals:
            # Get any reward lines with negative price (eWallet)
            reward_lines = self.order_line.filtered(lambda l: l.is_reward_line and l.price_unit < 0)
            if reward_lines:
                self._check_and_limit_reward_lines(reward_lines)
                
        return result
        
    def _check_and_limit_reward_lines(self, reward_lines):
        """Limit reward lines to allowed products total"""
        self.ensure_one()
        
        # Find programs with restrictions
        restricted_programs = self.env['loyalty.program'].search([
            ('restrict_products', '=', True)
        ])
        
        if not restricted_programs:
            return
            
        # For each reward line
        for reward_line in reward_lines:
            # Try to find which program this reward belongs to
            reward_product = reward_line.product_id
            
            # Check each program to see if this reward line might be from it
            for program in restricted_programs:
                if not program.allowed_product_ids:
                    continue
                    
                # Calculate total for allowed products
                allowed_total = 0
                for line in self.order_line:
                    if (line.product_id in program.allowed_product_ids and 
                        not line.is_reward_line):
                        allowed_total += line.price_subtotal
                
                # Check if the reward amount exceeds the allowed products total
                current_discount = abs(reward_line.price_unit)
                if current_discount > allowed_total:
                    # Update directly with a simpler approach
                    if allowed_total > 0:
                        reward_line.price_unit = -allowed_total
                        
                        # Post a message
                        self.message_post(
                            body=_("Loyalty discount limited to $%.2f as only certain products can be paid with loyalty points.") % allowed_total
                        )
                    else:
                        # If no allowed products, remove the reward line entirely
                        reward_line.unlink()
                        self.message_post(
                            body=_("Loyalty discount removed as there are no products eligible for loyalty points.")
                        )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    @api.model_create_multi
    def create(self, vals_list):
        """Catch reward lines at creation"""
        lines = super(SaleOrderLine, self).create(vals_list)
        
        # Check if any new lines are reward lines
        reward_lines = lines.filtered(lambda l: l.is_reward_line and l.price_unit < 0)
        if reward_lines:
            orders = reward_lines.mapped('order_id')
            for order in orders:
                order._check_and_limit_reward_lines(reward_lines.filtered(lambda l: l.order_id == order))
                
        return lines