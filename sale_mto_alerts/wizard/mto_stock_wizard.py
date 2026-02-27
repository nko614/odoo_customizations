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
        """Swap the product on the SO line with the alternative."""
        self.ensure_one()
        order = self.sale_order_id
        so_line = order.order_line.filtered(
            lambda l: l.product_id == self.sale_line_product_id
        )
        if so_line:
            so_line[0].product_id = alt_product
        return {'type': 'ir.actions.act_window_close'}

    def action_continue(self):
        """Continue without swapping - just close the wizard."""
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
