/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("actions").add("copy_shopify_url", (env, action) => {
    const url = action.params.url;

    navigator.clipboard.writeText(url).then(() => {
        env.services.notification.add("Copy App URL to clipboard!", {
            type: "success",
        });
    }).catch(() => {
        env.services.notification.add("Failed to copy URL.", {
            type: "danger",
        });
    });
});
