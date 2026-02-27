from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    customer_alert = fields.Html(
        string="Customer Alert",
        compute='_compute_customer_alert',
    )
    has_mto_stock_issues = fields.Boolean(
        compute='_compute_has_mto_stock_issues',
    )

    @api.depends('partner_id')
    def _compute_customer_alert(self):
        for order in self:
            if order.partner_id and order.partner_id.comment:
                order.customer_alert = order.partner_id.comment
            else:
                order.customer_alert = False

    @api.depends('order_line.product_id', 'order_line.product_uom_qty')
    def _compute_has_mto_stock_issues(self):
        for order in self:
            has_issues = False
            for line in order.order_line:
                if not line.product_id or line.display_type:
                    continue
                if line._is_mto_product(line.product_id):
                    bom = self.env['mrp.bom']._bom_find(line.product_id)[line.product_id]
                    if bom and line._get_short_components(bom, line.product_id, line.product_uom_qty or 1.0):
                        has_issues = True
                        break
            order.has_mto_stock_issues = has_issues

    def action_check_mto_stock(self):
        """Open MTO stock wizard for all MTO lines with component shortages."""
        self.ensure_one()
        wizard_lines = []
        wizard_alternatives = []

        for line in self.order_line:
            if not line.product_id or line.display_type:
                continue
            product = line.product_id
            qty = line.product_uom_qty or 1.0

            if not line._is_mto_product(product):
                continue

            bom = self.env['mrp.bom']._bom_find(product)[product]
            if not bom:
                continue

            short_components = line._get_short_components(bom, product, qty)
            if not short_components:
                continue

            for comp in short_components:
                wizard_lines.append((0, 0, {
                    'component_id': comp['component'].id,
                    'required_qty': comp['required'],
                    'available_qty': comp['available'],
                }))

            alternatives = line._find_alternative_variants(product, bom, qty)
            for alt in alternatives:
                wizard_alternatives.append((0, 0, {
                    'product_id': alt.id,
                }))

        if not wizard_lines:
            return {'type': 'ir.actions.act_window_close'}

        # Use the first MTO product with issues as the primary one
        first_mto_product = False
        first_qty = 1.0
        for line in self.order_line:
            if not line.product_id or line.display_type:
                continue
            if line._is_mto_product(line.product_id):
                bom = self.env['mrp.bom']._bom_find(line.product_id)[line.product_id]
                if bom and line._get_short_components(bom, line.product_id, line.product_uom_qty or 1.0):
                    first_mto_product = line.product_id
                    first_qty = line.product_uom_qty or 1.0
                    break

        wizard = self.env['sale.mto.stock.wizard'].create({
            'sale_order_id': self.id,
            'sale_line_product_id': first_mto_product.id,
            'sale_line_qty': first_qty,
            'line_ids': wizard_lines,
            'alternative_ids': wizard_alternatives,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'MTO Component Stock Alert',
            'res_model': 'sale.mto.stock.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_id', 'product_uom_qty')
    def _onchange_product_mto_stock_check(self):
        """Check MTO component stock when product or qty changes."""
        if not self.product_id:
            return

        product = self.product_id
        qty = self.product_uom_qty or 1.0

        if not self._is_mto_product(product):
            return

        bom = self.env['mrp.bom']._bom_find(product)[product]
        if not bom:
            return

        short_components = self._get_short_components(bom, product, qty)
        if not short_components:
            return

        alternatives = self._find_alternative_variants(product, bom, qty)
        msg = self._build_stock_warning_message(product, short_components, alternatives)

        return {
            'warning': {
                'title': 'MTO Component Stock Alert',
                'message': msg,
            }
        }

    def _is_mto_product(self, product):
        """Check if a product uses the MTO route."""
        company = self.order_id.company_id or self.env.company
        warehouses = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id),
        ], limit=1)
        if not warehouses:
            return False
        mto_route = warehouses.mto_pull_id.route_id
        if not mto_route:
            return False
        product_routes = product.route_ids | product.categ_id.total_route_ids
        return mto_route in product_routes

    def _get_short_components(self, bom, product, qty):
        """Return list of components with insufficient free_qty."""
        short = []
        ratio = qty / (bom.product_qty or 1.0)
        for line in bom.bom_line_ids:
            if line.bom_product_template_attribute_value_ids:
                ptav_ids = line.bom_product_template_attribute_value_ids
                variant_ptavs = product.product_template_attribute_value_ids
                if not (ptav_ids & variant_ptavs):
                    continue
            required = line.product_qty * ratio
            available = line.product_id.free_qty
            if available < required:
                short.append({
                    'component': line.product_id,
                    'required': required,
                    'available': max(available, 0.0),
                })
        return short

    def _find_alternative_variants(self, product, bom, qty):
        """Find sibling variants of the same template with all components in stock."""
        template = product.product_tmpl_id
        sibling_variants = template.product_variant_ids.filtered(
            lambda v: v.id != product.id and v.active
        )
        alternatives = self.env['product.product']
        ratio = qty / (bom.product_qty or 1.0)

        for variant in sibling_variants:
            variant_bom = self.env['mrp.bom']._bom_find(variant)[variant]
            if not variant_bom:
                continue
            all_in_stock = True
            for line in variant_bom.bom_line_ids:
                if line.bom_product_template_attribute_value_ids:
                    ptav_ids = line.bom_product_template_attribute_value_ids
                    variant_ptavs = variant.product_template_attribute_value_ids
                    if not (ptav_ids & variant_ptavs):
                        continue
                required = line.product_qty * ratio
                if line.product_id.free_qty < required:
                    all_in_stock = False
                    break
            if all_in_stock:
                alternatives |= variant

        return alternatives

    def _build_stock_warning_message(self, product, short_components, alternatives):
        """Build a readable warning message for the MTO stock alert."""
        lines = []
        lines.append("The following raw material components do not have enough stock:\n")
        for comp in short_components:
            lines.append(
                "  - %s: Need %.2f, Available %.2f (Short %.2f)" % (
                    comp['component'].display_name,
                    comp['required'],
                    comp['available'],
                    comp['required'] - comp['available'],
                )
            )
        if alternatives:
            lines.append(
                "\nRecommended alternative variants with all components in stock:"
            )
            for alt in alternatives:
                variant_vals = ', '.join(
                    alt.product_template_variant_value_ids.mapped('name')
                )
                ref = (" [%s]" % alt.default_code) if alt.default_code else ""
                lines.append("  - %s%s (%s)" % (alt.display_name, ref, variant_vals))
            lines.append(
                "\nSave the order and click 'Check MTO Stock' to swap to an alternative."
            )
        else:
            lines.append(
                "\nNo alternative variants with sufficient component stock were found."
            )
        return '\n'.join(lines)
