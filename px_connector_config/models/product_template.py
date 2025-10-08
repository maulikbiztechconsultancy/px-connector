from odoo import models, fields, api
import json
import xmlrpc.client
from datetime import datetime
from odoo.http import request
from odoo.exceptions import UserError
import base64
import logging
import requests
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
	_inherit = "product.template"

	model_code = fields.Char(string="Model Code")
	pim_config_id = fields.Many2one("pimore.vender.config", string="PIM ID")
	json_data_pimcore = fields.Text()

	def get_product_data(self, pim_config_id):
		cr = self.env.cr
		attribute_ids = pim_config_id.attribute_line_fields.attribute_id.ids
		# Use %s with tuple or list
		cr.execute(
			"SELECT code_refrence, name, id, attribute_id FROM product_attribute_value WHERE attribute_id IN %s",
			(tuple(attribute_ids),)
		)
		attribute_values = {
			row[0]: {
				'name': row[1],
				'id': row[2],
				'attribute_id': row[3]
			}
			for row in cr.fetchall()
		}
		cr.execute("""
			SELECT reference, id FROM product_category WHERE pim_config_id = %s
		""", (pim_config_id.id,))
		categories = {
			row[0]: {
				'id': row[1],
			}for row in cr.fetchall()
		}
		return attribute_values, categories

	def get_product_template_data(self, queue_product, pim_config_id):
		field_data = {'pim_config_id': pim_config_id.id}
		for fields in pim_config_id.product_field_lines:
			field_data.update({fields.product_field_id.name: queue_product.get(fields.custom_value)})
		return field_data
