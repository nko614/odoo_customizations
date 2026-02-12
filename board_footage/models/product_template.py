from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_length = fields.Float(string='Length (inches)', help='Length in inches')
    x_width = fields.Float(string='Width (inches)', help='Width in inches')
    x_thickness = fields.Float(string='Thickness (inches)', help='Thickness in inches')
    x_studio_length = fields.Float(string='Studio Length (inches)', help='Studio length field for compatibility') 