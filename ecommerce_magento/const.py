# Part of Odoo. See LICENSE file for full copyright and licensing details.

ORDER_STATE_MAPPING = {
    "new": "confirmed",
    "holded": "confirmed",
    "processing": "confirmed",
    "pending_payment": "confirmed",
    "payment_review": "confirmed",
    "complete": "confirmed",
    "canceled": "canceled",
}
DELIVERY_CARRIER_MAPPING = {
    "flatrate_flatrate": "Standard delivery",  # fixed rate
    "fedex": "Fedex International",
    "dhl": "DHL",
    "ups": "UPS US",
    "usps": "USPS International",
}
