/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";

class SalesDashboard extends Component {
    static template = "sales_dashboard.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            date: this._todayStr(),
            total_orders: 0,
            total_revenue: 0,
            currency: "",
            salesperson_data: [],
            loading: true,
        });

        onWillStart(() => this.loadData());
    }

    _todayStr() {
        const now = new Date();
        const y = now.getFullYear();
        const m = String(now.getMonth() + 1).padStart(2, "0");
        const d = String(now.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
    }

    async loadData() {
        this.state.loading = true;
        const data = await this.orm.call(
            "sales.dashboard",
            "get_dashboard_data",
            [],
            { date: this.state.date }
        );
        Object.assign(this.state, data, { loading: false });
    }

    async onDateChange(ev) {
        this.state.date = ev.target.value;
        await this.loadData();
    }

    formatCurrency(value) {
        return `${this.state.currency} ${formatFloat(value, { digits: [0, 2] })}`;
    }

    viewOrders(userId) {
        const domain = [
            ["state", "=", "sale"],
            ["date_order", ">=", `${this.state.date} 00:00:00`],
            ["date_order", "<=", `${this.state.date} 23:59:59`],
        ];
        if (userId) {
            domain.push(["user_id", "=", userId]);
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Confirmed Sale Orders",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
        });
    }
}

registry.category("actions").add("sales_dashboard", SalesDashboard);
