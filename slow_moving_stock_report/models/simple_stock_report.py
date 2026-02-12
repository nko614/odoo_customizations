# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class SimpleStockReport(models.Model):
    _name = 'simple.stock.report'
    _description = 'Simple Stock Report'
    _rec_name = 'product_id'
    
    product_id = fields.Many2one('product.product', string='Product', required=True)
    default_code = fields.Char(string='Internal Reference', related='product_id.default_code')
    categ_id = fields.Many2one('product.category', string='Product Category', related='product_id.categ_id')
    location_id = fields.Many2one('stock.location', string='Location')
    qty_on_hand = fields.Float(string='Quantity On Hand')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id')
    value_on_hand = fields.Float(string='Value On Hand')
    
    # Movement quantities - stored fields
    qty_30_days = fields.Float(string='Qty Moved (30 days)')
    qty_60_days = fields.Float(string='Qty Moved (60 days)')
    qty_90_days = fields.Float(string='Qty Moved (90 days)')
    
    # Turnover rates - stored fields
    turnover_30_days = fields.Float(string='Turnover Rate (30 days)', help="Percentage of stock moved in 30 days", store=True)
    turnover_60_days = fields.Float(string='Turnover Rate (60 days)', help="Percentage of stock moved in 60 days", store=True)
    turnover_90_days = fields.Float(string='Turnover Rate (90 days)', help="Percentage of stock moved in 90 days", store=True)
    
    # Auto-compute trigger
    auto_compute = fields.Boolean(string='Auto Compute', compute='_compute_movements', store=False)
    
    @api.depends('product_id', 'qty_on_hand')
    def _compute_movements(self):
        """Auto-compute movements when record is displayed"""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("=== _compute_movements called ===")
        
        for record in self:
            _logger.info(f"Processing record for product: {record.product_id.name if record.product_id else 'None'}")
            # Always calculate to debug
            if record.product_id:
                record.calculate_movements()
            record.auto_compute = True
    
    def get_historical_inventory(self, product_id, date):
        """Get inventory quantity at a specific date"""
        # Get all stock moves that were completed up to that date
        moves = self.env['stock.move'].search([
            ('product_id', '=', product_id),
            ('state', '=', 'done'),
            ('date', '<=', date)
        ])
        
        # Calculate net effect of all moves up to that date
        net_qty = 0
        for move in moves:
            if move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
                # Moving out of internal locations (sales, etc.)
                net_qty -= move.product_uom_qty
            elif move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal':
                # Moving into internal locations (purchases, etc.)
                net_qty += move.product_uom_qty
            elif move.location_id.usage == 'inventory' and move.location_dest_id.usage == 'internal':
                # Inventory adjustments (positive)
                net_qty += move.product_uom_qty
            elif move.location_id.usage == 'internal' and move.location_dest_id.usage == 'inventory':
                # Inventory adjustments (negative)
                net_qty -= move.product_uom_qty
        
        return max(0, net_qty)  # Don't return negative inventory

    def calculate_movements(self):
        """Calculate cumulative movement data with correct turnover formula"""
        from datetime import datetime, timedelta
        import logging
        _logger = logging.getLogger(__name__)
        
        # Use Odoo's timezone-aware dates
        today = fields.Datetime.now()
        date_30 = today - timedelta(days=30)
        date_60 = today - timedelta(days=60)
        date_90 = today - timedelta(days=90)
        
        _logger.info(f"=== CALCULATING TURNOVER FOR: {self.product_id.name} ===")
        
        # Update current quantity from real-time inventory
        current_qty = self.product_id.qty_available
        self.qty_on_hand = current_qty
        self.value_on_hand = current_qty * self.product_id.list_price
        
        _logger.info(f"Real-time quantity on hand: {current_qty}")
        
        # Get CUMULATIVE outgoing moves (customer shipments only) for each period
        # 30 days: all moves in last 30 days
        outgoing_moves_30 = self.env['stock.move'].search([
            ('product_id', '=', self.product_id.id),
            ('state', '=', 'done'),
            ('date', '>=', date_30),
            ('picking_id.picking_type_id.code', '=', 'outgoing'),
            ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', '=', 'customer')
        ])
        
        # 60 days: all moves in last 60 days
        outgoing_moves_60 = self.env['stock.move'].search([
            ('product_id', '=', self.product_id.id),
            ('state', '=', 'done'),
            ('date', '>=', date_60),
            ('picking_id.picking_type_id.code', '=', 'outgoing'),
            ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', '=', 'customer')
        ])
        
        # 90 days: all moves in last 90 days
        outgoing_moves_90 = self.env['stock.move'].search([
            ('product_id', '=', self.product_id.id),
            ('state', '=', 'done'),
            ('date', '>=', date_90),
            ('picking_id.picking_type_id.code', '=', 'outgoing'),
            ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', '=', 'customer')
        ])
        
        # Get all outgoing moves in the last 90 days to calculate cumulative quantities
        all_outgoing_moves = self.env['stock.move'].search([
            ('product_id', '=', self.product_id.id),
            ('state', '=', 'done'),
            ('date', '>=', date_90),
            ('picking_id.picking_type_id.code', '=', 'outgoing'),
            ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', '=', 'customer')
        ])
        
        # Calculate CUMULATIVE quantities moved out for each period
        qty_30 = qty_60 = qty_90 = 0.0
        for move in all_outgoing_moves:
            move_date = move.date
            qty = move.product_uom_qty
            
            if move_date >= date_30:  # Last 30 days
                qty_30 += qty
            if move_date >= date_60:  # Last 60 days
                qty_60 += qty
            qty_90 += qty  # All moves in last 90 days
        
        _logger.info(f"CUMULATIVE Qty moved out - 30d: {qty_30}, 60d: {qty_60}, 90d: {qty_90}")
        
        # Validate cumulative logic: 90d >= 60d >= 30d
        if not (qty_90 >= qty_60 >= qty_30):
            _logger.warning(f"Cumulative validation failed: 90d({qty_90}) >= 60d({qty_60}) >= 30d({qty_30})")
        
        # Store cumulative movement quantities in fields
        self.qty_30_days = qty_30
        self.qty_60_days = qty_60
        self.qty_90_days = qty_90
        
        # Estimate beginning inventory for each period using simplified approach:
        # beginning_inventory ≈ current_qty + qty_sold (assume no purchases for simplicity)
        begin_30 = current_qty + qty_30
        begin_60 = current_qty + qty_60  
        begin_90 = current_qty + qty_90
        
        _logger.info(f"Estimated beginning inventory - 30d ago: {begin_30}, 60d ago: {begin_60}, 90d ago: {begin_90}")
        
        # Calculate Average Inventory = (beginning + ending) / 2
        avg_inventory_30 = (current_qty + begin_30) / 2 if begin_30 > 0 else current_qty
        avg_inventory_60 = (current_qty + begin_60) / 2 if begin_60 > 0 else current_qty
        avg_inventory_90 = (current_qty + begin_90) / 2 if begin_90 > 0 else current_qty
        
        # Prevent division by zero
        avg_inventory_30 = max(avg_inventory_30, 0.01)
        avg_inventory_60 = max(avg_inventory_60, 0.01)
        avg_inventory_90 = max(avg_inventory_90, 0.01)
        
        # Calculate proper Turnover % = (Qty Moved / Average Inventory) 
        # Store as decimal for percentage widget (0.0-1.0 range)
        turnover_30_pct = qty_30 / avg_inventory_30 if avg_inventory_30 > 0 else 0
        turnover_60_pct = qty_60 / avg_inventory_60 if avg_inventory_60 > 0 else 0
        turnover_90_pct = qty_90 / avg_inventory_90 if avg_inventory_90 > 0 else 0
        
        # Cap at reasonable levels (300% = 3.0 for percentage widget)
        self.turnover_30_days = min(turnover_30_pct, 3.0)
        self.turnover_60_days = min(turnover_60_pct, 3.0)
        self.turnover_90_days = min(turnover_90_pct, 3.0)
        
        _logger.info(f"Average inventory - 30d: {avg_inventory_30:.2f}, 60d: {avg_inventory_60:.2f}, 90d: {avg_inventory_90:.2f}")
        _logger.info(f"Turnover rates - 30d: {turnover_30_pct:.4f} ({turnover_30_pct*100:.1f}%), 60d: {turnover_60_pct:.4f} ({turnover_60_pct*100:.1f}%), 90d: {turnover_90_pct:.4f} ({turnover_90_pct*100:.1f}%)")
        _logger.info(f"PROPER Formula: Qty Sold / Average Inventory (not qty_sold/qty_remaining)")
    
    @api.model
    def debug_stock_moves(self):
        """Debug method to check stock moves"""
        from datetime import datetime, timedelta
        
        # Get a sample product
        product = self.env['product.product'].search([('type', '=', 'product')], limit=1)
        if not product:
            return "No products found"
        
        # Check all moves for this product
        all_moves = self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('state', '=', 'done')
        ], order='date desc', limit=20)
        
        result = f"\nDebugging stock moves for: {product.name}\n"
        result += f"Total done moves found: {len(all_moves)}\n\n"
        
        for move in all_moves:
            result += f"Date: {move.date}\n"
            result += f"Reference: {move.reference or move.picking_id.name or 'N/A'}\n"
            result += f"From: {move.location_id.complete_name} (usage: {move.location_id.usage})\n"
            result += f"To: {move.location_dest_id.complete_name} (usage: {move.location_dest_id.usage})\n"
            result += f"Quantity: {move.product_uom_qty}\n"
            result += f"State: {move.state}\n"
            result += "-" * 50 + "\n"
        
        return result
    
    @api.model
    def action_recalculate_all_movements(self):
        """Recalculate movements for all records"""
        records = self.search([])
        
        # Test with first product to see what's happening
        if records:
            test_product = records[0].product_id
            
            # Check what moves exist
            all_moves = self.env['stock.move'].search([
                ('product_id', '=', test_product.id),
                ('state', '=', 'done')
            ], limit=5)
            
            print(f"\n=== Testing Product: {test_product.name} ===")
            print(f"Found {len(all_moves)} done moves")
            
            for move in all_moves:
                print(f"Date: {move.date}, From: {move.location_id.name} ({move.location_id.usage}) → To: {move.location_dest_id.name} ({move.location_dest_id.usage}), Qty: {move.product_uom_qty}")
            
            # Check move lines too
            move_lines = self.env['stock.move.line'].search([
                ('product_id', '=', test_product.id),
                ('state', '=', 'done')
            ], limit=5)
            
            print(f"\nFound {len(move_lines)} done move lines")
            for line in move_lines:
                print(f"Date: {line.date}, From: {line.location_usage} → To: {line.location_dest_usage}, Qty Done: {line.qty_done}")
            
            # Specifically look for customer shipments
            customer_moves = self.env['stock.move.line'].search([
                ('product_id', '=', test_product.id),
                ('state', '=', 'done'),
                ('location_usage', '=', 'internal'),
                ('location_dest_usage', '=', 'customer')
            ], limit=5)
            
            print(f"\nFound {len(customer_moves)} customer shipment move lines")
            for line in customer_moves:
                print(f"CUSTOMER SHIPMENT - Date: {line.date}, Qty: {line.qty_done}")
        
        # Now recalculate all
        for record in records:
            record.calculate_movements()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Recalculated movements for {len(records)} products',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def refresh_data(self):
        """Generate complete report data with movement & turnover calculations"""
        from datetime import timedelta
        import logging
        _logger = logging.getLogger(__name__)
        
        # Clear existing records for fresh calculation
        self.search([]).unlink()
        
        # Date ranges for movement calculations
        now = fields.Datetime.now()
        date_30 = now - timedelta(days=30)
        date_60 = now - timedelta(days=60)
        date_90 = now - timedelta(days=90)
        
        # Get all active products with broader type filter
        products = self.env['product.product'].search([
            ('active', '=', True),
            ('type', 'in', ['product', 'consu'])  # Include both storable and consumable products
        ])
        
        _logger.info(f"Found {len(products)} total products")
        
        # If no products found, try without type filter for debugging
        if not products:
            all_products = self.env['product.product'].search([('active', '=', True)])
            _logger.info(f"DEBUG: Found {len(all_products)} products of any type")
            if all_products:
                # Show first few product types for debugging
                for i, p in enumerate(all_products[:5]):
                    _logger.info(f"DEBUG: Product {p.name} has type: {p.type}")
            
            # Use all products for now to get some data
            products = all_products
        
        records_to_create = []
        products_with_stock = 0
        
        for product in products:
            # Get current stock quantity using product field
            total_on_hand = product.qty_available
            
            _logger.info(f"Product {product.name}: qty_available = {total_on_hand}")
            
            # Skip products with no stock
            if total_on_hand <= 0:
                continue
                
            products_with_stock += 1
            
            # Get a default location
            try:
                location_id = self.env.ref('stock.stock_location_stock').id
            except:
                location_id = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1).id
            
            # Fetch outgoing stock moves (customer deliveries) in last 90 days
            outgoing_moves = self.env['stock.move'].search([
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('location_id.usage', '=', 'internal'),
                ('location_dest_id.usage', '=', 'customer'),
                ('date', '>=', date_90)
            ])
            
            # Calculate CUMULATIVE quantities moved out for each period
            qty_30 = qty_60 = qty_90 = 0.0
            for move in outgoing_moves:
                move_date = move.date
                qty = move.product_uom_qty
                
                if move_date >= date_30:  # Last 30 days
                    qty_30 += qty
                if move_date >= date_60:  # Last 60 days
                    qty_60 += qty
                qty_90 += qty  # All moves in last 90 days
            
            # Estimate beginning inventory for each period
            # Simplified: beginning ≈ current + sold (assumes no major purchases)
            begin_30 = total_on_hand + qty_30
            begin_60 = total_on_hand + qty_60
            begin_90 = total_on_hand + qty_90
            
            # Calculate Average Inventory = (beginning + ending) / 2
            avg_30 = (total_on_hand + begin_30) / 2 if begin_30 > 0 else total_on_hand
            avg_60 = (total_on_hand + begin_60) / 2 if begin_60 > 0 else total_on_hand
            avg_90 = (total_on_hand + begin_90) / 2 if begin_90 > 0 else total_on_hand
            
            # Prevent division by zero
            avg_30 = max(avg_30, 0.01)
            avg_60 = max(avg_60, 0.01)
            avg_90 = max(avg_90, 0.01)
            
            # Calculate Turnover % = (Qty Moved / Average Inventory)
            # Store as decimal for percentage widget (0.0-3.0 range, cap at 300%)
            turnover_30 = min((qty_30 / avg_30), 3.0) if avg_30 > 0 else 0.0
            turnover_60 = min((qty_60 / avg_60), 3.0) if avg_60 > 0 else 0.0
            turnover_90 = min((qty_90 / avg_90), 3.0) if avg_90 > 0 else 0.0
            
            # Create record with all calculated values
            records_to_create.append({
                'product_id': product.id,
                'location_id': location_id,
                'qty_on_hand': total_on_hand,
                'qty_30_days': qty_30,
                'qty_60_days': qty_60,
                'qty_90_days': qty_90,
                'turnover_30_days': turnover_30,
                'turnover_60_days': turnover_60,
                'turnover_90_days': turnover_90,
                'value_on_hand': total_on_hand * product.list_price,
            })

        # Create all records at once for better performance
        created_count = 0
        _logger.info(f"Found {products_with_stock} products with stock out of {len(products)} total products")
        _logger.info(f"Ready to create {len(records_to_create)} records")
        
        if records_to_create:
            created_records = self.create(records_to_create)
            created_count = len(created_records)
            _logger.info(f"Successfully created {created_count} complete records with movement calculations")
        else:
            _logger.info("No products with stock found to create records")
            
        # Return summary
        return {
            'new_records_created': created_count,
            'existing_records_updated': 0,
            'total_records': created_count
        }
    
    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to automatically add new products with stock when viewing the list"""
        # Check for and add new products before searching (only on first page)
        if not offset:  # Only on first page load, not pagination
            self.refresh_data()
        
        # Return the normal search results
        return super().search_read(domain, fields, offset, limit, order)