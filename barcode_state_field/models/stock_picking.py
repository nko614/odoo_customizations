from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    item_state = fields.Selection([
        ('new', 'New'),
        ('used', 'Used')
    ], string='State', default='new')

class StockMove(models.Model):
    _inherit = 'stock.move'

    item_state = fields.Selection([
        ('new', 'New'),
        ('used', 'Used')
    ], string='State', default='new')

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    item_state = fields.Selection([
        ('new', 'New'),
        ('used', 'Used')
    ], string='State', default='new')