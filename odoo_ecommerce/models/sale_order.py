# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ecommerce_order_identifier = fields.Char(
        string="E-commerce Order ID",
        readonly=True, copy=False)
    ec_order_ref = fields.Char(
        string="E-commerce Order Reference",
        readonly=True, copy=False)

    ecommerce_account_id = fields.Many2one(
        comodel_name="ecommerce.account",
        string="E-commerce Account", readonly=True, copy=False, ondelete="restrict")

    _unique_ecommerce_account_ecommerce_order_identifier = models.Constraint(
        "UNIQUE(ecommerce_account_id, ecommerce_order_identifier)",
        "E-commerce order identifier should be unique per ecommerce account."
    )

    def _create_activity_resolve_fulfillment_conflict(self, user_id):
        """Create an activity on the E-commerce sale order for the salesperson to resolve
        the conflict of fulfillments received from E-commerce when order is fulfilled by Odoo.

        :param int user_id: The salesperson of the related E-commerce account.
        :return: None.
        """
        activity_message = self.env._(
            "This %s sale order is handled on Odoo, but pickings are also"
            " being created in %s. Please resolve this conflict.",
            self.ecommerce_account_id.ecommerce_channel_id.name, self.ecommerce_account_id.ecommerce_channel_id.name
        )
        self.activity_schedule(
            act_type_xmlid="mail.mail_activity_data_todo",
            user_id=user_id,
            note=activity_message,
        )

    def _action_cancel(self):
        out_of_sync_orders = self.env[self._name]
        if self.env.context.get('canceled_by_ecommerce'):
            for order in self:
                picking = self.env['stock.picking'].search(
                    [('sale_id', '=', order.id), ('state', '=', 'done')]
                )
                if picking and order.ecommerce_account_id.fulfilled_by == 'odoo':
                    # The picking was processed on Odoo while Ecommerce canceled it.
                    order.message_post(
                        body=self.env._(
                            "The order has been cancelled by the %s merchant/customer while some "
                            "products have already been delivered. Please create a return for this "
                            "order to adjust the stock.",
                            order.ecommerce_account_id.ecommerce_channel_id.name
                        )
                    )
                    out_of_sync_orders |= order
        return super(SaleOrder, self - out_of_sync_orders)._action_cancel()
