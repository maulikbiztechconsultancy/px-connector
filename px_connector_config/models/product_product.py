from odoo import models, fields, api
import base64
import requests
import logging
import ast
from datetime import datetime
_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
	_inherit = "product.product"

	json_data_varaint = fields.Text()
	pim_config_id = fields.Many2one("pimore.vender.config", string="PIM ID")
	stock_location_ids = fields.One2many("product.location.stock", 'product_id', string="Stock Locations")
	printing_template_ids = fields.Many2many("product.template")
	printing_variant_ids = fields.Many2many('product.product', 'product_printing_variant_rel', 'product_id', 'printing_variant_id', string='Printing Variants')
	shipping_variant_ids = fields.Many2many('product.product','product_shipping_variant_rel', 'product_id', 'shipping_variant_id', string='Shipping Variants')
	repeat_charge = fields.Float(string="Repeat Charge")
	setup_charge = fields.Float(string="Setup Charge")
	image_updated = fields.Boolean()
	image=fields.Char(string="Image")

	def _fetch_image_and_update(self):
		product_ids = self.env['product.product'].search([('type','=','consu'),('pim_config_id','=',1),('image_updated','=',False)],limit=500)
		for rec in product_ids:
			_logger.info("-\n\n------START FETCH IMAGE------%s--%s", datetime.now(),rec)
			try:
				data = ast.literal_eval(rec.json_data_varaint or "{}")
				image_data = rec.pim_config_id.image_data
				if image_data:
					image_url = data.get(image_data)
					if not image_url:
						rec.image_updated = True
						continue
					response = requests.get(image_url)
					response.raise_for_status()
					image_data = base64.b64encode(response.content)
					rec.image_1920 = image_data
				rec.image_updated = True
			except Exception as e:
				_logger.warning("Image fetch failed for product %s: %s", rec.id, e)
				rec.image_updated = True
			_logger.info("-\n\n------END FETCH IMAGE------%s", datetime.now())
