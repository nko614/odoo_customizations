/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SaleOrderLineProductField } from "@sale/js/sale_product_field";
import { useService } from "@web/core/utils/hooks";

patch(SaleOrderLineProductField.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
    },

    _onProductUpdate() {
        super._onProductUpdate();
        this._checkMtoStock();
    },

    async _checkMtoStock() {
        const record = this.props.record;
        const saleOrder = record.model.root;
        const productData = record.data.product_id;
        if (!productData || !productData.id) {
            return;
        }
        const productId = productData.id;
        const qty = record.data.product_uom_qty || 1.0;
        const companyData = saleOrder.data.company_id;
        const companyId = companyData ? companyData.id : false;

        let result;
        try {
            result = await this.orm.call(
                "sale.order.line",
                "check_mto_component_stock",
                [],
                {
                    product_id: productId,
                    qty: qty,
                    company_id: companyId,
                }
            );
        } catch (e) {
            console.error("MTO stock check failed:", e);
            return;
        }

        if (result && result.action) {
            this.actionService.doAction(result.action, {
                onClose: async (closeInfo) => {
                    if (closeInfo && closeInfo.productId) {
                        await record.update({
                            product_id: {
                                id: closeInfo.productId,
                                display_name: closeInfo.productName,
                            },
                        });
                    }
                },
            });
        }
    },
});
