# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    offer_count = fields.Integer(compute='_compute_offer_count')

    def _compute_offer_count(self):
        offers_data = self.env['ecommerce.offer']._read_group(
            [('matched_product_id', 'in', self.ids)], ['matched_product_id'], ['__count']
        )
        products_data = {product.id: count for product, count in offers_data}
        for product in self:
            product.offer_count = products_data.get(product.id, 0)

    def action_view_ecommerce_offer(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("E-commerce Offer"),
            'res_model': 'ecommerce.offer',
            'view_mode': 'list',
            'context': {'group_by': 'ecommerce_account_id'},
            'domain': [('matched_product_id', '=', self.id)],
        }

    @api.model
    def _restore_data_product(self, default_name, default_type, xmlid):
        """ Create a product and assign it the provided and previously valid xmlid. """
        product = self.env['product.product'].with_context(mail_create_nosubscribe=True).create({
            'name': default_name,
            'type': default_type,
            'list_price': 0.,
            'sale_ok': False,
            'purchase_ok': False,
        })
        product._configure_for_ecommerce()
        self.env['ir.model.data'].sudo().search(
            [('module', '=', 'ecommerce'), ('name', '=', xmlid)]
        ).write({'res_id': product.id})
        return product

    def _configure_for_ecommerce(self):
        """ Archive products and their templates and define their invoice policy. """
        # Archiving is achieved by the mean of write instead of action_archive to allow this method
        # to be called from data without restoring the products when they were already archived.
        self.write({'active': False})
        for product_template in self.product_tmpl_id:
            product_template.write({
                'active': False,
                'invoice_policy': 'order' if product_template.type == 'service' else 'delivery',
            })
