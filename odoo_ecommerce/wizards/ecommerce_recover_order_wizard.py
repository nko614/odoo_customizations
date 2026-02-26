# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AmazonRecoverOrderWizard(models.TransientModel):
    _name = 'ecommerce.recover.order.wizard'
    _description = "ECommerce Recover Order Wizard"

    ecommerce_order_ref = fields.Char(
        string="Ecommerce Order Reference",
        help="The reference to the Ecommerce order to recover.",
        required=True,
    )

    def action_ecommerce_recover_order(self):
        """Recover an order using a reference value.

        To support additional reference keys:
        - Inherit this wizard view and add new fields.
        - Inherit this method and pass the new fields to
        `_sync_order_by_reference()` as required.
        """
        self.ensure_one()
        account = self.env['ecommerce.account'].browse(self.env.context['active_id'])
        return account._sync_order_by_reference(self.ecommerce_order_ref)
