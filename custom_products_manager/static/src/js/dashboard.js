/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class CustomProductsDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = {};
        this.loadDashboardData();
    }

    async loadDashboardData() {
        try {
            // Load dashboard statistics
            const [configCount, templateCount, bomCount, orderCount] = await Promise.all([
                this.orm.searchCount("custom.product.config", []),
                this.orm.searchCount("custom.product.template", []),
                this.orm.searchCount("mrp.bom", [["is_custom_bom", "=", true]]),
                this.orm.searchCount("sale.order", [["order_line.is_custom_product", "=", true]])
            ]);

            this.state = {
                configCount,
                templateCount,
                bomCount,
                orderCount,
                loaded: true
            };
            
            this.render();
        } catch (error) {
            console.error("Error loading dashboard data:", error);
        }
    }

    openConfigurations() {
        this.action.doAction("custom_products_manager.action_custom_product_config");
    }

    openTemplates() {
        this.action.doAction("custom_products_manager.action_custom_product_template");
    }

    openCustomBOMs() {
        this.action.doAction("custom_products_manager.action_custom_boms");
    }

    openCustomOrders() {
        this.action.doAction("custom_products_manager.action_sale_order_custom");
    }

    createCustomProduct() {
        this.action.doAction("custom_products_manager.action_create_custom_product_wizard");
    }

    buildBOM() {
        this.action.doAction("custom_products_manager.action_build_bom_wizard");
    }
}

CustomProductsDashboard.template = "custom_products_manager.Dashboard";

registry.category("actions").add("custom_products_dashboard", CustomProductsDashboard);