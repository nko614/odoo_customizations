/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SaleOrderLineProductField } from "@sale/js/sale_product_field";
import { useService } from "@web/core/utils/hooks";

patch(SaleOrderLineProductField.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
    },

    async _onProductUpdate() {
        await super._onProductUpdate();
        await this._checkMtoStock();
    },

    async _checkMtoStock() {
        const record = this.props.record;
        const saleOrder = record.model.root;
        const productId = record.data.product_id && record.data.product_id[0];
        if (!productId) {
            return;
        }

        const qty = record.data.product_uom_qty || 1.0;
        const companyId = saleOrder.data.company_id && saleOrder.data.company_id[0];

        const result = await this.orm.call(
            "sale.order.line",
            "check_mto_component_stock",
            [],
            {
                product_id: productId,
                qty: qty,
                company_id: companyId || false,
            }
        );

        if (result && result.action) {
            this.actionService.doAction(result.action, {
                onClose: async (closeInfo) => {
                    if (closeInfo && closeInfo.productId) {
                        // User clicked "Use This Variant" - swap product on the line
                        await record.update({
                            product_id: [closeInfo.productId, closeInfo.productName],
                        });
                    }
                    // Otherwise user clicked "Continue Anyway" or closed - do nothing
                },
            });
        }
    },
});
