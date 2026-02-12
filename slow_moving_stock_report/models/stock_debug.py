# -*- coding: utf-8 -*-
from odoo import models, fields, api

class StockDebug(models.TransientModel):
    _name = 'stock.debug'
    _description = 'Stock Debug Helper'
    
    name = fields.Char('Name', default='Debug')
    
    @api.model
    def check_stock_data(self):
        """Check what stock data exists"""
        results = {}
        
        # Check products
        products = self.env['product.product'].search([('type', '=', 'product'), ('active', '=', True)])
        results['products_count'] = len(products)
        results['first_5_products'] = [(p.id, p.name) for p in products[:5]]
        
        # Check stock quants
        quants = self.env['stock.quant'].search([('quantity', '>', 0)])
        results['quants_count'] = len(quants)
        results['first_5_quants'] = [(q.product_id.name, q.quantity, q.location_id.name) for q in quants[:5]]
        
        # Check internal locations
        locations = self.env['stock.location'].search([('usage', '=', 'internal')])
        results['locations_count'] = len(locations)
        results['first_5_locations'] = [(l.id, l.name) for l in locations[:5]]
        
        # Check if any quants are in internal locations
        internal_quants = self.env['stock.quant'].search([
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal')
        ])
        results['internal_quants_count'] = len(internal_quants)
        
        return results