# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    pim_config_id = fields.Many2one("pimore.vender.config", string='PIM ID')


class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    pim_config_id = fields.Many2one("pimore.vender.config", string='PIM ID')
