from odoo import api, fields, models


class MtoStockWizard(models.TransientModel):
    _name = 'sale.mto.stock.wizard'
    _description = 'MTO Component Stock Alert'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    sale_line_product_id = fields.Many2one('product.product', string='Original Product', required=True)
    sale_line_qty = fields.Float(string='Order Quantity', required=True)
    line_ids = fields.One2many(
        'sale.mto.stock.wizard.line', 'wizard_id',
        string='Short Components',
    )
    alternative_ids = fields.One2many(
        'sale.mto.stock.wizard.alternative', 'wizard_id',
        string='Available Alternatives',
    )
    has_alternatives = fields.Boolean(compute='_compute_has_alternatives')

    @api.depends('alternative_ids')
    def _compute_has_alternatives(self):
        for wiz in self:
            wiz.has_alternatives = bool(wiz.alternative_ids)

    def action_swap_product(self, alt_product):
        """Swap the product on the SO line with the alternative, then re-check."""
        self.ensure_one()
        order = self.sale_order_id
        so_line = order.order_line.filtered(
            lambda l: l.product_id == self.sale_line_product_id
        )
        if so_line:
            so_line[0].product_id = alt_product
        # Re-open the confirm flow so they can confirm or see updated status
        return order.action_confirm()

    def action_confirm_anyway(self):
        """Confirm the order despite MTO stock shortages."""
        self.ensure_one()
        return self.sale_order_id.with_context(skip_mto_stock_check=True).action_confirm()

    def action_cancel(self):
        """Go back to the quotation without confirming."""
        return {'type': 'ir.actions.act_window_close'}


class MtoStockWizardLine(models.TransientModel):
    _name = 'sale.mto.stock.wizard.line'
    _description = 'MTO Stock Wizard - Short Component'

    wizard_id = fields.Many2one('sale.mto.stock.wizard', required=True, ondelete='cascade')
    component_id = fields.Many2one('product.product', string='Component', readonly=True)
    required_qty = fields.Float(string='Required Qty', readonly=True)
    available_qty = fields.Float(string='Available Qty', readonly=True)
    shortage_qty = fields.Float(string='Shortage', compute='_compute_shortage_qty')

    @api.depends('required_qty', 'available_qty')
    def _compute_shortage_qty(self):
        for line in self:
            line.shortage_qty = line.required_qty - line.available_qty


class MtoStockWizardAlternative(models.TransientModel):
    _name = 'sale.mto.stock.wizard.alternative'
    _description = 'MTO Stock Wizard - Alternative Variant'

    wizard_id = fields.Many2one('sale.mto.stock.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Alternative Variant', readonly=True)
    default_code = fields.Char(related='product_id.default_code', string='Internal Ref')
    variant_values = fields.Char(
        string='Variant',
        compute='_compute_variant_values',
    )

    @api.depends('product_id')
    def _compute_variant_values(self):
        for line in self:
            if line.product_id:
                line.variant_values = ', '.join(
                    line.product_id.product_template_variant_value_ids.mapped('name')
                )
            else:
                line.variant_values = ''

    def action_swap(self):
        """Swap the sale order line product with this alternative variant."""
        self.ensure_one()
        return self.wizard_id.action_swap_product(self.product_id)
