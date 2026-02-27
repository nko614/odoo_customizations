# Shopify Theme Setup — UTM Capture Snippet

This snippet must be installed on your Shopify storefront theme to capture
UTM parameters (source, medium, campaign) from landing page URLs and attach
them to orders as note attributes.

## How it works

1. When a visitor lands on your store via a URL with `utm_source`, `utm_medium`,
   or `utm_campaign` query parameters (e.g. from an Odoo link tracker redirect),
   the script reads them and stores them in a browser cookie (30-day expiry).
2. On every page load, if the cookie exists, the script writes the UTM values
   to the Shopify cart as cart attributes via `/cart/update.js`.
3. When the customer completes checkout, Shopify saves the cart attributes as
   order note attributes (visible under "Additional details" on the order).
4. The `shopify_marketing` Odoo module reads these note attributes via the
   GraphQL API and populates Source, Medium, and Campaign on the sale order.

## Installation

### Step 1: Create the snippet

1. In Shopify Admin, go to **Online Store > Themes**
2. Click **"..." > Edit code** on your active theme
3. In the **Snippets** folder, click **Add a new snippet**
4. Name it `utm-capture`
5. Paste the contents of `utm-capture.liquid` from this folder
6. Save

### Step 2: Include the snippet in your theme layout

1. In the same code editor, open **Layout > theme.liquid**
2. Scroll to the bottom of the file
3. Add the following line immediately before `</body>`:

       {% render 'utm-capture' %}

4. Save

## Verification

1. Open an incognito browser window
2. Navigate to a product page with UTM params, e.g.:
   `https://your-store.myshopify.com/products/example?utm_source=test&utm_medium=email&utm_campaign=demo`
3. Open Developer Tools (Cmd+Shift+J / F12)
4. Check **Application > Cookies** — you should see an `odoo_utm` cookie
5. Check **Network** tab, filter for `cart/update` — you should see a POST request
6. Add the product to cart and complete checkout
7. In Shopify Admin, open the order — under **Additional details** you should
   see `utm_source`, `utm_medium`, `utm_campaign`

## Notes

- The cookie persists for 30 days. If a visitor clicks a tracked link today
  and returns to buy tomorrow, the UTM data is still captured.
- If a visitor arrives via a new tracked link, the cookie is overwritten with
  the new UTM values (last-touch attribution).
- The snippet has no dependencies and works with any Shopify theme.

## Odoo Requirements

- The `shopify_marketing` Odoo module must be installed alongside `ecommerce_shopify`
- Odoo's system parameter `link_tracker.no_external_tracking` must be OFF (default)
  for UTM params to be appended to external redirect URLs
