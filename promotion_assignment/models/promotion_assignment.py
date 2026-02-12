from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PromotionAssignment(models.Model):
    _name = 'promotion.assignment'
    _description = 'Promotion Assignment'
    _order = 'date_start desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Name', compute='_compute_name', store=True,
    )
    customer_id = fields.Many2one(
        'res.partner', string='Customer', required=True, index=True,
    )
    product_id = fields.Many2one(
        'product.product', string='Product', required=True, index=True,
    )
    discount_pct = fields.Float(string='Discount %')
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    month = fields.Char(
        string='Month', compute='_compute_month', store=True,
    )
    promotion_type = fields.Selection([
        ('internal', 'Internal'),
        ('mailing', 'Mailing'),
        ('social_media', 'Social Media'),
        ('event', 'Event'),
        ('other', 'Other'),
    ], string='Promotion Type', default='internal')
    category = fields.Selection([
        ('clearance', 'Clearance'),
        ('seasonal', 'Seasonal'),
        ('new_product', 'New Product'),
        ('volume', 'Volume'),
        ('loyalty', 'Loyalty'),
        ('other', 'Other'),
    ], string='Category')

    sale_line_count = fields.Integer(
        string='Sale Lines', compute='_compute_sale_lines',
    )
    total_revenue = fields.Monetary(
        string='Total Revenue', compute='_compute_sale_lines',
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id',
    )

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    @api.depends('customer_id', 'product_id')
    def _compute_name(self):
        for rec in self:
            customer = rec.customer_id.name or ''
            product = rec.product_id.display_name or ''
            rec.name = f"{customer} - {product}" if customer and product else customer or product or _('New')

    @api.depends('date_start')
    def _compute_month(self):
        for rec in self:
            rec.month = rec.date_start.strftime('%Y-%m') if rec.date_start else False

    def _compute_sale_lines(self):
        SaleLine = self.env['sale.order.line']
        for rec in self:
            if rec.customer_id and rec.product_id and rec.date_start and rec.date_end:
                lines = SaleLine.search([
                    ('order_partner_id', '=', rec.customer_id.id),
                    ('product_id', '=', rec.product_id.id),
                    ('order_id.date_order', '>=', rec.date_start),
                    ('order_id.date_order', '<=', rec.date_end),
                    ('order_id.state', 'in', ('sale', 'done')),
                ])
                rec.sale_line_count = len(lines)
                rec.total_revenue = sum(lines.mapped('price_subtotal'))
            else:
                rec.sale_line_count = 0
                rec.total_revenue = 0.0

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("End date must be on or after start date."))

    @api.constrains('product_id', 'date_start', 'date_end')
    def _check_no_overlap(self):
        for rec in self:
            if not (rec.product_id and rec.date_start and rec.date_end):
                continue
            overlapping = self.search([
                ('id', '!=', rec.id),
                ('product_id', '=', rec.product_id.id),
                ('date_start', '<=', rec.date_end),
                ('date_end', '>=', rec.date_start),
            ], limit=1)
            if overlapping:
                raise ValidationError(_(
                    "Product \"%(product)s\" already has a promotion for "
                    "\"%(customer)s\" from %(start)s to %(end)s. "
                    "Only one customer can promote a product during any given period.",
                    product=rec.product_id.display_name,
                    customer=overlapping.customer_id.name,
                    start=overlapping.date_start,
                    end=overlapping.date_end,
                ))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_view_sale_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order Lines'),
            'res_model': 'sale.order.line',
            'view_mode': 'list,form',
            'domain': [
                ('order_partner_id', '=', self.customer_id.id),
                ('product_id', '=', self.product_id.id),
                ('order_id.date_order', '>=', self.date_start),
                ('order_id.date_order', '<=', self.date_end),
                ('order_id.state', 'in', ('sale', 'done')),
            ],
            'context': {'create': False},
        }
