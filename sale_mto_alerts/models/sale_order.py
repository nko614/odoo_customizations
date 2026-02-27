import logging

from odoo import api, fields, models
from odoo.tools.mail import html2plaintext

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    customer_alert = fields.Html(
        string="Customer Alert",
        compute='_compute_customer_alert',
    )

    @api.depends('partner_id')
    def _compute_customer_alert(self):
        for order in self:
            if order.partner_id and order.partner_id.comment:
                order.customer_alert = order.partner_id.comment
            else:
                order.customer_alert = False

    @api.onchange('partner_id')
    def _onchange_partner_customer_alert(self):
        if self.partner_id and self.partner_id.comment:
            note_text = html2plaintext(self.partner_id.comment).strip()
            if note_text:
                return {
                    'warning': {
                        'title': 'CUSTOMER ALERT:',
                        'message': note_text,
                    }
                }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model
    def check_mto_component_stock(self, product_id, qty, company_id=False):
        """RPC method called from JS when product is selected on SO line.
        Returns {'action': {...}} if MTO stock issues found, else False.
        """
        product = self.env['product.product'].browse(product_id)
        if not product.exists():
            return False

        company = self.env['res.company'].browse(company_id) if company_id else self.env.company

        # Check if product has MTO route
        if not self._check_is_mto(product, company):
            return False

        # Find BOM
        bom = self.env['mrp.bom']._bom_find(product)[product]
        if not bom:
            return False

        # Check component stock
        short_components = self._get_short_components(bom, product, qty)
        if not short_components:
            return False

        # Find alternatives
        alternatives = self._find_alternative_variants(product, bom, qty)

        # Create wizard
        wizard = self.env['sale.mto.stock.wizard'].create({
            'sale_line_product_id': product.id,
            'sale_line_qty': qty,
            'line_ids': [(0, 0, {
                'component_id': comp['component'].id,
                'required_qty': comp['required'],
                'available_qty': comp['available'],
            }) for comp in short_components],
            'alternative_ids': [(0, 0, {
                'product_id': alt.id,
            }) for alt in alternatives],
        })

        return {
            'action': {
                'type': 'ir.actions.act_window',
                'name': 'MTO Component Stock Alert',
                'res_model': 'sale.mto.stock.wizard',
                'res_id': wizard.id,
                'views': [[False, 'form']],
                'target': 'new',
            }
        }

    @api.model
    def _check_is_mto(self, product, company):
        """Check if a product uses the MTO route."""
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

    def _is_mto_product(self, product):
        """Instance method wrapper for _check_is_mto."""
        company = self.order_id.company_id or self.env.company
        return self._check_is_mto(product, company)

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
