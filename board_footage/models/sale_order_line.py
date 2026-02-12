from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_feet = fields.Float(
        string='Feet', 
        help="Linear feet of lumber"
    )
    x_board_feet = fields.Float(
        string='Board Feet', 
        help="Board feet calculation: (length × width × thickness) / 12"
    )
    hide_from_pdf = fields.Boolean(
        string='Hide from PDF',
        help="Check this box to hide this line from the PDF report while keeping it in the subtotal",
        default=False
    )

    @api.onchange('product_id')
    def _onchange_product_id_board_footage(self):
        """Calculate initial values when product changes"""
        _logger.info("=== PRODUCT CHANGED ===")
        if self.product_id:
            # Get product dimensions
            length = self.product_id.x_studio_length or self.product_id.x_length or 0.0
            width = self.product_id.x_width or 0.0
            thickness = self.product_id.x_thickness or 0.0
            
            _logger.info(f"Product: {self.product_id.name}")
            _logger.info(f"x_studio_length: {getattr(self.product_id, 'x_studio_length', 'NOT FOUND')}")
            _logger.info(f"x_length: {getattr(self.product_id, 'x_length', 'NOT FOUND')}")
            _logger.info(f"x_width: {getattr(self.product_id, 'x_width', 'NOT FOUND')}")
            _logger.info(f"x_thickness: {getattr(self.product_id, 'x_thickness', 'NOT FOUND')}")
            _logger.info(f"Final Length: {length}")
            _logger.info(f"Final Width: {width}")
            _logger.info(f"Final Thickness: {thickness}")
            
            # Set default quantity to 1 if not set
            if not self.product_uom_qty:
                self.product_uom_qty = 1.0
            
            # Calculate based on quantity (convert inches to feet)
            self.x_feet = (self.product_uom_qty * length) / 12
            if width > 0 and thickness > 0:
                self.x_board_feet = self.product_uom_qty * (length * width * thickness) / 12
            else:
                self.x_board_feet = 0.0
                
            _logger.info(f"Calculated Feet: {self.x_feet}")
            _logger.info(f"Calculated Board Feet: {self.x_board_feet}")
        else:
            self.x_feet = 0.0
            self.x_board_feet = 0.0

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty_board_footage(self):
        """Recalculate feet and board feet when quantity changes"""
        _logger.info("=== QUANTITY CHANGED ===")
        if self.product_id and self.product_uom_qty:
            # Get product dimensions
            length = self.product_id.x_studio_length or self.product_id.x_length or 0.0
            width = self.product_id.x_width or 0.0
            thickness = self.product_id.x_thickness or 0.0
            
            _logger.info(f"Product: {self.product_id.name}")
            _logger.info(f"New Quantity: {self.product_uom_qty}")
            _logger.info(f"Length: {length}, Width: {width}, Thickness: {thickness}")
            
            # Calculate feet and board feet from quantity (convert inches to feet)
            self.x_feet = (self.product_uom_qty * length) / 12
            if width > 0 and thickness > 0:
                self.x_board_feet = self.product_uom_qty * (length * width * thickness) / 12
            else:
                self.x_board_feet = 0.0
                
            _logger.info(f"Calculated Feet: {self.x_feet}")
            _logger.info(f"Calculated Board Feet: {self.x_board_feet}")

    @api.onchange('x_feet')
    def _onchange_x_feet_board_footage(self):
        """Recalculate quantity and board feet when feet changes"""
        _logger.info("=== FEET CHANGED ===")
        if self.product_id and self.x_feet:
            # Get product dimensions
            length = self.product_id.x_studio_length or self.product_id.x_length or 0.0
            width = self.product_id.x_width or 0.0
            thickness = self.product_id.x_thickness or 0.0
            
            _logger.info(f"New Feet: {self.x_feet}")
            _logger.info(f"Length: {length}, Width: {width}, Thickness: {thickness}")
            
            # Calculate quantity from feet (convert feet to inches)
            if length > 0:
                self.product_uom_qty = (self.x_feet * 12) / length
                # Calculate board feet from new quantity
                if width > 0 and thickness > 0:
                    self.x_board_feet = self.product_uom_qty * (length * width * thickness) / 12
                else:
                    self.x_board_feet = 0.0
            else:
                self.product_uom_qty = 0.0
                self.x_board_feet = 0.0
                
            _logger.info(f"Calculated Quantity: {self.product_uom_qty}")
            _logger.info(f"Calculated Board Feet: {self.x_board_feet}")

    @api.onchange('x_board_feet')
    def _onchange_x_board_feet_board_footage(self):
        """Recalculate quantity and feet when board feet changes"""
        _logger.info("=== BOARD FEET CHANGED ===")
        if self.product_id and self.x_board_feet:
            # Get product dimensions
            length = self.product_id.x_studio_length or self.product_id.x_length or 0.0
            width = self.product_id.x_width or 0.0
            thickness = self.product_id.x_thickness or 0.0
            
            _logger.info(f"New Board Feet: {self.x_board_feet}")
            _logger.info(f"Length: {length}, Width: {width}, Thickness: {thickness}")
            
            # Calculate quantity from board feet
            if width > 0 and thickness > 0 and length > 0:
                board_feet_per_unit = (length * width * thickness) / 12
                if board_feet_per_unit > 0:
                    self.product_uom_qty = self.x_board_feet / board_feet_per_unit
                    # Calculate feet from new quantity (convert inches to feet)
                    self.x_feet = (self.product_uom_qty * length) / 12
                else:
                    self.product_uom_qty = 0.0
                    self.x_feet = 0.0
            else:
                self.product_uom_qty = 0.0
                self.x_feet = 0.0
                
            _logger.info(f"Calculated Quantity: {self.product_uom_qty}")
            _logger.info(f"Calculated Feet: {self.x_feet}")

    @api.constrains('x_feet', 'x_board_feet', 'product_uom_qty')
    def _check_positive_values(self):
        """Ensure all values are positive"""
        for line in self:
            if line.x_feet < 0:
                raise ValidationError("Feet value cannot be negative")
            if line.x_board_feet < 0:
                raise ValidationError("Board feet value cannot be negative")
            if line.product_uom_qty < 0:
                raise ValidationError("Quantity cannot be negative")