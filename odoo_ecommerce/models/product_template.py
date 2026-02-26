# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    offer_count = fields.Integer(
        compute='_compute_offer_count',
    )

    def _compute_offer_count(self):
        offers_data = self.env['ecommerce.offer']._read_group(
            [('matched_product_template_id', 'in', self.ids)],
            ['matched_product_template_id'],
            ['__count'],
        )
        product_templates_data = {
            product_template.id: count
            for product_template, count in offers_data
        }
        for product_template in self:
            product_template.offer_count = product_templates_data.get(product_template.id, 0)

    def action_view_ecommerce_offer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("E-commerce Offers"),
            'res_model': 'ecommerce.offer',
            'view_mode': 'list',
            'context': {'group_by': 'ecommerce_account_id'},
            'domain': [('matched_product_id.product_tmpl_id', '=', self.id)],
        }
