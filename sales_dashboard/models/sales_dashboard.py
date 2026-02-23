from odoo import api, fields, models
from odoo.tools import SQL


class SalesDashboard(models.AbstractModel):
    _name = "sales.dashboard"
    _description = "Sales Dashboard"

    @api.model
    def get_dashboard_data(self, date=None):
        """Return today's confirmed sale order stats grouped by salesperson."""
        if not date:
            date = fields.Date.context_today(self)

        query = SQL(
            """
            SELECT
                rp.name AS salesperson,
                ru.id AS user_id,
                COUNT(so.id) AS order_count,
                COALESCE(SUM(so.amount_total), 0) AS total_amount,
                rc.name AS currency
            FROM sale_order so
            JOIN res_users ru ON ru.id = so.user_id
            JOIN res_partner rp ON rp.id = ru.partner_id
            LEFT JOIN res_currency rc ON rc.id = so.currency_id
            WHERE so.state = 'sale'
              AND so.date_order::date = %s
            GROUP BY rp.name, ru.id, rc.name
            ORDER BY total_amount DESC
            """,
            date,
        )
        self.env.cr.execute(query)
        rows = self.env.cr.dictfetchall()

        total_orders = sum(r["order_count"] for r in rows)
        total_revenue = sum(r["total_amount"] for r in rows)

        # Get currency symbol from first row or company default
        currency = ""
        if rows:
            # currency name is stored as jsonb in Odoo 19, extract display value
            raw = rows[0].get("currency")
            if isinstance(raw, dict):
                currency = raw.get("en_US", "") or next(iter(raw.values()), "")
            elif isinstance(raw, str):
                currency = raw
        if not currency:
            currency = self.env.company.currency_id.name or ""

        return {
            "date": str(date),
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "currency": currency,
            "salesperson_data": [
                {
                    "salesperson": r["salesperson"] if isinstance(r["salesperson"], str)
                    else (r["salesperson"].get("en_US", "") or next(iter(r["salesperson"].values()), ""))
                    if isinstance(r["salesperson"], dict) else str(r["salesperson"]),
                    "user_id": r["user_id"],
                    "order_count": r["order_count"],
                    "total_amount": r["total_amount"],
                }
                for r in rows
            ],
        }
