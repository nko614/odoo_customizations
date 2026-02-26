# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Mapping of Magento order states to Common structure states
ORDER_STATE_MAPPING = {
    "new": "confirmed",
    "holded": "confirmed",
    "processing": "confirmed",
    "pending_payment": "confirmed",
    "payment_review": "confirmed",
    "complete": "confirmed",
    "closed": "confirmed",
    "canceled": "canceled",
}
# Mapping of Magento delivery carriers to Odoo delivery carriers
DELIVERY_CARRIER_MAPPING = {
    "flatrate_flatrate": "Flat Rate",
    "freeshipping_freeshipping": "Free Shipping",
    "fedex": "Fedex International",
    "dhl": "DHL",
    "ups": "UPS US",
    "usps": "USPS International",
}
