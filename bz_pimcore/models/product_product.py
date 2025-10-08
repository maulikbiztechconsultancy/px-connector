from odoo import models, fields, api


class ProductProduct(models.Model):
	_inherit = "product.product"

	json_data_varaint = fields.Text()
	pim_config_id = fields.Many2one("pimore.vender.config", string="PIM ID")
	stock_location_ids = fields.One2many("product.location.stock", 'product_id', string="Stock Locations")