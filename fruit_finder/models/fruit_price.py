from odoo import models, fields


class FruitPrice(models.Model):
    _name = "fruit.price"
    _description = "Fruit Price"
    _order = "name, form"

    name = fields.Char(string="Fruit", required=True)
    form = fields.Selection(
        [
            ("fresh", "Fresh"),
            ("frozen", "Frozen"),
            ("canned", "Canned"),
            ("dried", "Dried"),
            ("juice", "Juice"),
        ],
        string="Form",
        required=True,
    )
    price_per_lb = fields.Float(string="Price per Pound ($)")
    price_per_cup = fields.Float(string="Price per Cup ($)")
    unit = fields.Char(string="Unit")
    note = fields.Char(string="Note")
