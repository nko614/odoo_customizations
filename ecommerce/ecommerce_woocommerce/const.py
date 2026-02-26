# Part of Odoo. See LICENSE file for full copyright and licensing details.

OAUTHORIZE_END_POINT = '/wc-auth/v1/authorize'
wc_api_endpoint = '/wp-json/wc/v3/'

ORDER_STATUS_MAPPING = {
    'pending': 'confirmed',
    'processing': 'confirmed',
    'on-hold': 'confirmed',
    'completed': 'confirmed',
    'cancelled': 'canceled',
    'refunded': 'canceled',
    'failed': 'canceled',
    'trash': 'canceled',
}
