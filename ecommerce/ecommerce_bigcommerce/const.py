# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Mapping of BigCommerce Order Status to Odoo Sale Order Status
ORDER_STATUS_MAPPING = {
    "Pending": "confirmed",
    "Awaiting Payment": "confirmed",
    "Awaiting Fulfillment": "confirmed",
    "Awaiting Shipment": "confirmed",
    "Awaiting Pickup": "confirmed",
    "Partially Shipped": "confirmed",
    "Completed": "confirmed",
    "Shipped": "confirmed",
    "Cancelled": "canceled",
    "Declined": "canceled",
    "Refunded": "canceled",
    "Disputed": "canceled",
    "Manual Verification Required": "canceled",
    "Partially Refunded": "canceled",
    "Deleted": "canceled",
}
