from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DisassemblyWizard(models.TransientModel):
    _name = 'disassembly.wizard'
    _description = 'Partial Disassembly Wizard'

    product_id = fields.Many2one(
        'product.product',
        string='Finished Product',
        required=True,
        help='The finished good to partially disassemble',
    )
    bom_id = fields.Many2one(
        'mrp.bom',
        string='Bill of Materials',
        required=True,
        domain="[('product_tmpl_id', '=', product_tmpl_id)]",
    )
    product_tmpl_id = fields.Many2one(
        related='product_id.product_tmpl_id',
    )
    product_qty = fields.Float(
        string='Quantity',
        default=1.0,
        required=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        required=True,
        domain="[('usage', '=', 'internal')]",
        help='Location where the finished product is stored',
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        required=True,
        domain="[('usage', '=', 'internal')]",
        help='Location where removed parts will be placed',
    )
    line_ids = fields.One2many(
        'disassembly.wizard.line',
        'wizard_id',
        string='Components',
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            bom = self.env['mrp.bom']._bom_find(
                self.product_id,
                company_id=self.env.company.id,
            ).get(self.product_id)
            self.bom_id = bom
            if bom:
                self._load_bom_lines()
        else:
            self.bom_id = False
            self.line_ids = [(5, 0, 0)]

    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        if self.bom_id:
            self._load_bom_lines()
        else:
            self.line_ids = [(5, 0, 0)]

    def _load_bom_lines(self):
        """Load top-level BOM components as selectable lines."""
        lines = []
        if not self.bom_id:
            return
        for bom_line in self.bom_id.bom_line_ids:
            lines.append((0, 0, {
                'selected': False,
                'product_id': bom_line.product_id.id,
                'product_qty': bom_line.product_qty,
                'product_uom_id': bom_line.product_uom_id.id,
                'bom_line_id': bom_line.id,
            }))
        self.line_ids = [(5, 0, 0)] + lines

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        if warehouse:
            res['location_id'] = warehouse.lot_stock_id.id
            res['location_dest_id'] = warehouse.lot_stock_id.id
        return res

    def action_create_disassembly(self):
        """Create stock moves to extract selected components.

        The finished product (cockpit) stays in stock — only the
        selected sub-assemblies are moved into stock from a virtual
        production location, representing parts removed from the
        finished good.
        """
        self.ensure_one()

        selected_lines = self.line_ids.filtered('selected')
        if not selected_lines:
            raise UserError(_('Please select at least one component to remove.'))

        production_location = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not production_location:
            raise UserError(_('No virtual production location found for this company.'))

        # Create stock moves directly (no picking needed)
        moves = self.env['stock.move']
        for line in selected_lines:
            qty = line.product_qty * self.product_qty
            moves |= self.env['stock.move'].create({
                'product_id': line.product_id.id,
                'product_uom_qty': qty,
                'product_uom': line.product_uom_id.id,
                'location_id': production_location.id,
                'location_dest_id': self.location_dest_id.id,
            })

        moves._action_confirm()
        moves._action_assign()
        moves.move_line_ids.write({'quantity': moves.move_line_ids.mapped('quantity') or 0})
        for move in moves:
            for move_line in move.move_line_ids:
                move_line.quantity = move.product_uom_qty
        moves._action_done()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Disassembly Complete'),
                'message': _('%d component(s) moved to %s') % (
                    len(selected_lines),
                    self.location_dest_id.display_name,
                ),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class DisassemblyWizardLine(models.TransientModel):
    _name = 'disassembly.wizard.line'
    _description = 'Partial Disassembly Wizard Line'

    wizard_id = fields.Many2one(
        'disassembly.wizard',
        required=True,
        ondelete='cascade',
    )
    selected = fields.Boolean(
        string='Remove',
        default=False,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Component',
        readonly=True,
    )
    product_qty = fields.Float(
        string='Quantity',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        readonly=True,
    )
    bom_line_id = fields.Many2one(
        'mrp.bom.line',
        string='BOM Line',
    )
