# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ECommerceChannel(models.Model):
    _name = "ecommerce.channel"
    _description = "E-commerce Channel"
    _order = "sequence, id"

    name = fields.Char(
        string="E-commerce Channel Name",
        required=True,
    )
    code = fields.Char(
        string="E-commerce Channel Code",
        help="Unique code for the ecommerce channel",
        required=True,
    )
    image_128 = fields.Image(
        string="Logo",
    )

    active = fields.Boolean(default=True)
    sequence = fields.Integer()

    support_location = fields.Boolean(
        string="Support Location",
        store=True,
        help="Indicates whether this ecommerce integration supports multiple stock locations.",
        compute='_compute_feature_support_fields'
    )
    support_shipping = fields.Boolean(
        string="Support Shipping",
        store=True,
        help="Indicates whether this ecommerce integration supports shipping operations.",
        compute='_compute_feature_support_fields'
    )

    _uniq_name = models.Constraint(
        "UNIQUE(name)",
        "The name of the ecommerce channel must be unique."
    )
    _uniq_code = models.Constraint(
        "UNIQUE(code)",
        "The code of the ecommerce channel must be unique."
    )

    @api.depends('code')
    def _compute_feature_support_fields(self):
        """ Compute the feature support fields based on the E-commerce platform.

        Feature support fields are used to specify which features are supported by a
        given E-commerce platform. These fields are as follows:

        - `support_location`: Whether the "location support" feature is supported.
        - `support_shipping`: Whether the "shipping support" feature is supported.

        For a E-commerce platform to specify that it supports additional features, it must override this method
        and set the related feature support fields to the desired value on the appropriate
        `ecommerce.channel` records.

        :return: None
        """
        self.update({
            'support_location': True,
            'support_shipping': True,
        })
