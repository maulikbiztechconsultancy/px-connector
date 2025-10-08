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

	def get_product_data_preseli(self, pim_config_id):
		cr = self.env.cr
		cr.execute("""
			SELECT reference, id FROM product_category WHERE pim_config_id = %s
		""", (pim_config_id.id,))
		categories = {
			row[0]: {
				'id': row[1],
			}for row in cr.fetchall()
		}
		return categories


