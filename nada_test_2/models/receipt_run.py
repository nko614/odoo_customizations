import logging
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NadaReceiptRun(models.Model):
    _name = 'nada.receipt.run'
    _inherit = ['mail.thread']
    _description = 'Receipt Automation Run'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default='New',
    )
    date = fields.Date(
        string='Date', default=fields.Date.context_today, required=True,
    )
    user_id = fields.Many2one(
        'res.users', string='Responsible',
        default=lambda self: self.env.user,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processed', 'Processed'),
        ('pos_created', 'POs Created'),
        ('sent', 'Sent'),
        ('done', 'Done'),
    ], string='Status', default='draft', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True,
    )

    line_ids = fields.One2many('nada.receipt.line', 'run_id', string='Lines')
    po_ids = fields.Many2many('purchase.order', string='Purchase Orders')

    po_count = fields.Integer(string='PO Count', compute='_compute_counts')
    exception_count = fields.Integer(string='Exceptions', compute='_compute_counts')
    matched_count = fields.Integer(string='Matched', compute='_compute_counts')

    @api.depends('po_ids', 'line_ids.status')
    def _compute_counts(self):
        for run in self:
            run.po_count = len(run.po_ids)
            run.exception_count = len(run.line_ids.filtered(
                lambda l: l.status in ('no_blanket', 'partial')
            ))
            run.matched_count = len(run.line_ids.filtered(
                lambda l: l.status in ('matched', 'partial')
            ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'nada.receipt.run'
                ) or 'RUN/%s' % fields.Date.context_today(self).strftime('%Y%m%d')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Step 1: Match blanket orders for all lines
    # ------------------------------------------------------------------
    def action_process(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.needed_qty > 0)
        if not lines:
            raise UserError(
                "No lines need ordering. Add products where "
                "Forecasted Sales exceeds On Hand quantity."
            )

        # Delete any split lines from a previous processing run
        split_lines = self.line_ids.filtered(lambda l: l.note and l.note.startswith('Split:'))
        if split_lines:
            split_lines.unlink()

        # Reset matching fields on original lines
        lines.write({
            'allocated_qty': 0,
            'blanket_order_id': False,
            'blanket_line_id': False,
            'vendor_id': False,
            'price_unit': 0,
            'status': 'pending',
            'note': False,
        })

        # Match each line across multiple blanket orders
        for line in lines:
            self._match_blanket_orders(line)

        self.state = 'processed'

    def _match_blanket_orders(self, line):
        """Match a line across multiple blanket orders, splitting if needed."""
        today = fields.Date.context_today(self)

        # Search for valid blanket order lines with this product
        domain = [
            ('product_id', '=', line.product_id.id),
            ('requisition_id.requisition_type', '=', 'blanket_order'),
            ('requisition_id.state', 'in', ('confirmed', 'done')),
            '|',
            ('requisition_id.date_end', '>=', today),
            ('requisition_id.date_end', '=', False),
        ]
        bo_lines = self.env['purchase.requisition.line'].search(
            domain, order='requisition_id asc'
        )

        # Sort by earliest validity start date
        bo_lines = bo_lines.sorted(
            key=lambda l: l.requisition_id.date_start or fields.Date.to_date('1900-01-01')
        )

        remaining = line.needed_qty
        first_line = True
        _logger.info(
            "NADA MATCH: product=%s, needed_qty=%s, found %d blanket order lines",
            line.product_id.display_name, remaining, len(bo_lines),
        )

        for bo_line in bo_lines:
            if remaining <= 0:
                break

            available = bo_line.product_qty - bo_line.qty_ordered
            if available <= 0:
                continue

            allocate = min(remaining, available)
            _logger.info(
                "NADA MATCH: blanket=%s, available=%s, allocating=%s, remaining_after=%s",
                bo_line.requisition_id.name, available, allocate, remaining - allocate,
            )

            if first_line:
                # Use the original line for the first allocation
                line.write({
                    'allocated_qty': allocate,
                    'blanket_order_id': bo_line.requisition_id.id,
                    'blanket_line_id': bo_line.id,
                    'vendor_id': bo_line.requisition_id.vendor_id.id,
                    'price_unit': bo_line.price_unit,
                    'status': 'matched',
                })
                first_line = False
            else:
                # Create a new split line for additional allocations
                self.env['nada.receipt.line'].create({
                    'run_id': self.id,
                    'product_id': line.product_id.id,
                    'forecasted_qty': 0,
                    'allocated_qty': allocate,
                    'blanket_order_id': bo_line.requisition_id.id,
                    'blanket_line_id': bo_line.id,
                    'vendor_id': bo_line.requisition_id.vendor_id.id,
                    'price_unit': bo_line.price_unit,
                    'status': 'matched',
                    'note': 'Split: overflow from %s' % bo_line.requisition_id.name,
                })

            remaining -= allocate

        if remaining > 0 and not first_line:
            # Partially fulfilled across blanket orders
            line.note = "%.2f of %.2f unfilled (no more blanket orders)" % (
                remaining, line.needed_qty
            )
        elif first_line:
            # No blanket orders found at all
            line.write({
                'status': 'no_blanket',
                'note': 'No available blanket order for this product',
            })

    # ------------------------------------------------------------------
    # Step 2: Generate Purchase Orders
    # ------------------------------------------------------------------
    def action_generate_pos(self):
        self.ensure_one()
        if self.state != 'processed':
            raise UserError("Process the lines first.")

        lines = self.line_ids.filtered(lambda l: l.status in ('matched', 'partial'))
        if not lines:
            raise UserError("No matched lines to generate POs from.")

        # Group by blanket order (each PO links to one blanket order)
        bo_lines = defaultdict(lambda: self.env['nada.receipt.line'])
        for line in lines:
            bo_lines[line.blanket_order_id] |= line

        created_pos = self.env['purchase.order']
        for blanket_order, bo_group in bo_lines.items():
            vendor = blanket_order.vendor_id
            _logger.info(
                "NADA PO: creating PO for vendor=%s, blanket_order=%s (id=%s), "
                "lines=%d, total_qty=%s",
                vendor.name, blanket_order.name, blanket_order.id,
                len(bo_group), sum(bo_group.mapped('allocated_qty')),
            )
            po = self._create_purchase_order(vendor, bo_group, blanket_order)
            _logger.info(
                "NADA PO: created PO %s (id=%s), requisition_id=%s",
                po.name, po.id, po.requisition_id.name,
            )
            created_pos |= po

        self.po_ids = [(6, 0, created_pos.ids)]
        self.state = 'pos_created'

    def _create_purchase_order(self, vendor, lines, blanket_order):
        """Create a single PO for a vendor linked to a blanket order."""
        company = self.company_id
        currency = (
            vendor.with_company(company).property_purchase_currency_id
            or company.currency_id
        )
        fpos = self.env['account.fiscal.position'].with_company(
            company
        )._get_fiscal_position(vendor)

        po_vals = {
            'partner_id': vendor.id,
            'requisition_id': blanket_order.id,
            'company_id': company.id,
            'currency_id': currency.id,
            'date_order': fields.Datetime.now(),
            'origin': '%s, %s' % (self.name, blanket_order.name),
            'fiscal_position_id': fpos.id,
            'payment_term_id': vendor.with_company(
                company
            ).property_supplier_payment_term_id.id or False,
        }
        po = self.env['purchase.order'].create(po_vals)

        po_line_vals = []
        for line in lines:
            product = line.product_id
            seller = product.seller_ids.filtered(
                lambda s: s.partner_id == vendor
            )[:1]
            delay = seller.delay if seller else 0
            date_planned = fields.Datetime.now() + timedelta(days=delay)

            taxes = product.supplier_taxes_id.filtered(
                lambda t: t.company_id == company
            )
            if fpos:
                taxes = fpos.map_tax(taxes)

            po_line_vals.append({
                'order_id': po.id,
                'product_id': product.id,
                'product_qty': line.allocated_qty,
                'product_uom_id': product.uom_id.id,
                'price_unit': line.price_unit,
                'date_planned': date_planned,
                'tax_ids': [(6, 0, taxes.ids)],
            })

        self.env['purchase.order.line'].create(po_line_vals)
        return po

    # ------------------------------------------------------------------
    # Step 3: Send POs to vendors
    # ------------------------------------------------------------------
    def action_send_pos(self):
        self.ensure_one()
        if self.state != 'pos_created':
            raise UserError("Generate POs first.")

        template = self.env.ref('purchase.email_template_edi_purchase')
        for po in self.po_ids:
            po.button_confirm()
            template.send_mail(po.id, force_send=True)

        self.state = 'sent'

    # ------------------------------------------------------------------
    # Step 4: Mark done
    # ------------------------------------------------------------------
    def action_done(self):
        self.ensure_one()
        self.state = 'done'

    # ------------------------------------------------------------------
    # Smart button actions
    # ------------------------------------------------------------------
    def action_view_pos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.po_ids.ids)],
        }

    def action_view_exceptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Exceptions',
            'res_model': 'nada.receipt.line',
            'view_mode': 'list',
            'domain': [
                ('run_id', '=', self.id),
                ('status', 'in', ('no_blanket', 'partial')),
            ],
        }
