# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class SlowMovingStockReport(models.Model):
    _name = 'slow.moving.stock.report'
    _description = 'Slow Moving Stock Report'
    _auto = True  # Changed to regular model for debugging
    _rec_name = 'product_id'
    _order = 'qty_90_days desc'
    
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    default_code = fields.Char(string='Internal Reference', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    
    qty_on_hand = fields.Float(string='Quantity On Hand', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)
    
    qty_30_days = fields.Float(string='Qty Moved (30 days)', readonly=True)
    qty_60_days = fields.Float(string='Qty Moved (60 days)', readonly=True)
    qty_90_days = fields.Float(string='Qty Moved (90 days)', readonly=True)
    
    turnover_30_days = fields.Float(string='Turnover Rate (30 days)', readonly=True, help="Number of times stock turned over in 30 days")
    turnover_60_days = fields.Float(string='Turnover Rate (60 days)', readonly=True, help="Number of times stock turned over in 60 days")
    turnover_90_days = fields.Float(string='Turnover Rate (90 days)', readonly=True, help="Number of times stock turned over in 90 days")
    
    value_on_hand = fields.Float(string='Value On Hand', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    def init(self):
        """Drop any existing view before creating table"""
        if hasattr(super(), 'init'):
            super().init()
        try:
            self._cr.execute("DROP VIEW IF EXISTS slow_moving_stock_report CASCADE")
        except:
            pass
    
    @api.model
    def generate_report_data(self):
        """Generate report data programmatically"""
        # Clear existing records
        self.search([]).unlink()
        
        # Get all products with stock
        products = self.env['product.product'].search([
            ('active', '=', True),
            ('type', '=', 'product')
        ])
        
        records_to_create = []
        
        for product in products[:20]:  # Limit to first 20 products for testing
            # Get stock quantities
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0)
            ])
            
            if quants:
                for quant in quants:
                    records_to_create.append({
                        'product_id': product.id,
                        'product_tmpl_id': product.product_tmpl_id.id,
                        'default_code': product.default_code,
                        'categ_id': product.categ_id.id,
                        'location_id': quant.location_id.id,
                        'qty_on_hand': quant.quantity,
                        'uom_id': product.uom_id.id,
                        'qty_30_days': 0.0,  # Will calculate later
                        'qty_60_days': 0.0,
                        'qty_90_days': 0.0,
                        'turnover_30_days': 0.0,
                        'turnover_60_days': 0.0,
                        'turnover_90_days': 0.0,
                        'value_on_hand': quant.quantity * product.list_price,
                        'currency_id': self.env.company.currency_id.id,
                    })
            else:
                # Include products without stock as well
                records_to_create.append({
                    'product_id': product.id,
                    'product_tmpl_id': product.product_tmpl_id.id,
                    'default_code': product.default_code,
                    'categ_id': product.categ_id.id,
                    'location_id': 1,  # Default location
                    'qty_on_hand': 0.0,
                    'uom_id': product.uom_id.id,
                    'qty_30_days': 0.0,
                    'qty_60_days': 0.0,
                    'qty_90_days': 0.0,
                    'turnover_30_days': 0.0,
                    'turnover_60_days': 0.0,
                    'turnover_90_days': 0.0,
                    'value_on_hand': 0.0,
                    'currency_id': self.env.company.currency_id.id,
                })
        
        if records_to_create:
            self.create(records_to_create)
            
        return len(records_to_create)
        
    @api.model
    def get_slow_movers(self, turnover_threshold=0.5):
        """Get products with turnover rate below threshold"""
        return self.search([
            ('turnover_90_days', '<', turnover_threshold),
            ('qty_on_hand', '>', 0)
        ])