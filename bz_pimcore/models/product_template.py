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
			SELECT reference_id, id FROM product_public_category WHERE pim_config_id = %s
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


	def get_queue_product(self):
		_logger.info("-\n\n------START------%s", datetime.now())
		pim_config_id = self.env['pimore.vender.config'].browse(1)
		attribute_values, categories = self.get_product_data(pim_config_id)
		odoo_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
		db = self.env.cr.dbname
		username = "admin"
		password = "admin"
		# password = 'g~=	^KSn"{eyX?~%3'
		common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
		uid = common.authenticate(db, username, password, {})
		models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")
		model = self.env['ir.model'].search([('model', '=', 'product.template')], limit=1).id
		cr = self.env.cr
		cr.execute(
			"""
			SELECT sub_reference, reference, result
			FROM queue_job
			WHERE state = 'process' AND reference = %s
			LIMIT 100
			""",
			(model,)
		)
		rows = cr.fetchall()
		# Unzip into two separate lists
		sub_references, references, results = zip(*rows) if rows else ([], [], [])
		# Convert to lists
		sub_references = list(sub_references)
		references = list(references)
		results = list(results)
		tempaltes = {}
		if references:
			cr.execute(
				"""
				SELECT model_code,id
				FROM product_template
				WHERE model_code in %s
				""",
				(tuple(references),)
			)
			tempaltes = dict(cr.fetchall())
		product_attribute_dict = {}
		for result in results:
			try:
				attribute_size_data, attribute_color_data = False, False
				attribute_color = result.get('color')
				attribute_size = result.get('size')
				current_attribute = False
				if attribute_color:
					if len(attribute_color) == 1:
						attribute_color_value = attribute_color[0]
					else:
						attribute_color_value = '_'.join(attribute_color)
					if attribute_color_value in attribute_values:
						attribute_color_data = attribute_values.get(attribute_color_value)
					else:
						if len(attribute_color) == 1:
							pass
						else:
							cr.execute(
								"SELECT name FROM product_attribute_value WHERE code_refrence IN %s",
								(tuple(attribute_color),)
							)
							color_multivalue = [row[0].get('en_US') for row in cr.fetchall()]
							value_name = '/'.join(color_multivalue)
							value_id = models.execute_kw(
								db, uid, password,
								'product.attribute.value', 'create',
								[{
									'attribute_id': 1,
									'name': value_name,
									'code_refrence': attribute_color_value
								}]
							)
							attribute_values.update({attribute_color_value: {'code_refrence': attribute_color_value, 'name': value_name, 'id': value_id, 'attribute_id': 7}})
							attribute_color_data = attribute_values.get(attribute_color_value)
				if attribute_size and attribute_size in attribute_values:
					attribute_size_data = attribute_values.get(attribute_size)
				template_data = self.get_product_template_data(result, pim_config_id)

				if result.get('modelCode') in tempaltes:
					main_product_tempalte = tempaltes.get(result.get('modelCode'))
					if attribute_color_data:
						current_attribute = attribute_color_data.get('id')
						existing_line = False
						if main_product_tempalte not in product_attribute_dict and attribute_color_data:
							attribute_lines = models.execute_kw(
								db, uid, password,
								'product.template', 'read',
								[main_product_tempalte],
								{'fields': ['attribute_line_ids']}
							)
							# Get line IDs
							line_ids = attribute_lines[0]['attribute_line_ids']

							# Get attribute_id from each attribute line
							attribute_line_data = models.execute_kw(
								db, uid, password,
								'product.template.attribute.line', 'read',
								[line_ids],
								{'fields': ['attribute_id']}
							)
							for attribute_data in attribute_line_data:
								if main_product_tempalte in product_attribute_dict:
									if attribute_data.get('attribute_id')[0] not in product_attribute_dict.get(main_product_tempalte):
										product_attribute_dict.get(main_product_tempalte).update({attribute_data.get('attribute_id')[0]: attribute_data.get('id')})
								else:
									product_attribute_dict.update({main_product_tempalte: {attribute_data.get('attribute_id')[0]: attribute_data.get('id')}})
								if attribute_color_data.get('attribute_id') == attribute_data.get('attribute_id')[0]:
									existing_line = attribute_data.get('id')
						else:
							if product_attribute_dict.get(main_product_tempalte):
								existing_line = product_attribute_dict.get(main_product_tempalte).get(attribute_color_data.get('attribute_id'))

						if existing_line:
							success = models.execute_kw(
							    db, uid, password,
							    'product.template.attribute.line', 'write',
							    [[existing_line], {
							        'value_ids': [(4, attribute_color_data.get('id'))]
							    }]
							)
						else:
							updating_data = {'attribute_line_ids' : [(0, 0, {
									'attribute_id': attribute_color_data.get('attribute_id'),  # Color
									'value_ids': [(6, 0, [attribute_color_data.get('id')])]  # Red, Blue
								})]}
							success = models.execute_kw(
								db, uid, password,
								'product.template', 'write',
								[[main_product_tempalte], updating_data]
							)
					if attribute_size_data:
						existing_size_line = False
						current_attribute = attribute_size_data.get('id')
						if main_product_tempalte in product_attribute_dict:
							if attribute_size_data.get('attribute_id') in product_attribute_dict.get(main_product_tempalte):
								existing_size_line = product_attribute_dict.get(main_product_tempalte).get(attribute_size_data.get('attribute_id'))
							else:
								attribute_lines = models.execute_kw(
									db, uid, password,
									'product.template', 'read',
									[main_product_tempalte],
									{'fields': ['attribute_line_ids']}
								)
								# Get line IDs
								# Get attribute_id from each attribute line
								line_ids = attribute_lines[0]['attribute_line_ids']
								attribute_line_datas = models.execute_kw(
								    db, uid, password,
								    'product.template.attribute.line', 'search_read',
								    [[
								        ('id', 'in', line_ids),
								        ('attribute_id', '=', attribute_size_data.get('attribute_id'))  # Replace with actual ID
								    ]],
								    {'fields': ['attribute_id']}
								)
								for attribute_line_data in attribute_line_datas:
									if attribute_line_data and attribute_size_data.get('attribute_id') == attribute_line_data.get('attribute_id')[0]:
										product_attribute_dict.get(main_product_tempalte).update({attribute_size_data.get('attribute_id'): attribute_line_data.get('id')})
										existing_size_line = product_attribute_dict.get(main_product_tempalte).get(attribute_size_data.get('attribute_id'))
						else:
							attribute_lines = models.execute_kw(
								db, uid, password,
								'product.template', 'read',
								[main_product_tempalte],
								{'fields': ['attribute_line_ids']}
							)
							# Get line IDs
							line_ids = attribute_lines[0]['attribute_line_ids']
							# Get attribute_id from each attribute line
							attribute_line_checks = models.execute_kw(
								db, uid, password,
								'product.template.attribute.line', 'read',
								[line_ids],
								{'fields': ['attribute_id']}
							)
							for attribute_line_check in attribute_line_checks:
								if attribute_line_check and attribute_size_data.get('attribute_id') == attribute_line_check.get('attribute_id')[0]:
									product_attribute_dict.get(main_product_tempalte).update({attribute_size_data.get('attribute_id'): attribute_line_check.get('id')})
									existing_size_line = product_attribute_dict.get(main_product_tempalte).get(attribute_size_data.get('attribute_id'))
						if existing_size_line:
							success = models.execute_kw(
							    db, uid, password,
							    'product.template.attribute.line', 'write',
							    [[existing_size_line], {
							        'value_ids': [(4, attribute_size_data.get('id'))]
							    }]
							)
						else:
							updating_data = {'attribute_line_ids' : [(0, 0, {
									'attribute_id': attribute_size_data.get('attribute_id'),  # Color
									'value_ids': [(6, 0, [attribute_size_data.get('id')])]  # Red, Blue
								})]}
							success = models.execute_kw(
								db, uid, password,
								'product.template', 'write',
								[[main_product_tempalte], updating_data]
							)
				else:
					attribute_line = []
					if attribute_color_data:
						attribute_line.append(
							(0, 0, {
								'attribute_id': attribute_color_data.get('attribute_id'),  # Color
								'value_ids': [(4, attribute_color_data.get('id'))]  # Red, Blue
							}),
						)
					if attribute_size_data:
						attribute_line.append(
							(0, 0, {
								'attribute_id': attribute_size_data.get('attribute_id'),  # Color
								'value_ids': [(4, attribute_size_data.get('id'))]  # Red, Blue
							}),
						)
					cat_code = result.get('categoryData')[0].get('catCode')  # 'sc86'
					cat_id = categories.get(cat_code, {}).get('id')
					template_data.update({'attribute_line_ids': attribute_line, 'public_categ_ids': [(4,(cat_id))] })
					main_product_tempalte = models.execute_kw(
							db, uid, password,
							'product.template', 'create',
							[template_data]
						)
					tempaltes.update({result.get('modelCode'): main_product_tempalte})



				variant_products = models.execute_kw(
					db, uid, password,
					'product.product', 'search_read',
					[[['product_tmpl_id', '=', main_product_tempalte]]],
					{
						'fields': ['id', 'name', 'default_code', 'product_template_attribute_value_ids'],
						'order': 'id desc',
					}
				)
				update_variant = variant_products[0].get('id')
				for variant_product in variant_products:
					cr.execute("""
					    SELECT product_attribute_value_id
					    FROM product_template_attribute_value
					    WHERE id IN %s
					""", [tuple(variant_product.get('product_template_attribute_value_ids'))])  # Make sure it's a tuple in a list
					# Fetch all rows
					rows = cr.fetchall()
					# Extract just the IDs into a flat list
					value_ids = [row[0] for row in rows]
					if attribute_color_data and attribute_size_data:
						if attribute_color_data.get('id') in value_ids and attribute_size_data.get('id') in value_ids:
							update_variant = variant_product.get('id')
					elif attribute_color_data and not attribute_size_data:
						if attribute_color_data.get('id') in value_ids:
							update_variant = variant_product.get('id')
					elif not attribute_color_data and attribute_size_data:
						if attribute_size_data.get('id') in value_ids:
							update_variant = variant_product.get('id')
					else:
						update_variant = variant_product.get('id')

				variant_date_update = self.get_product_template_data(result, pim_config_id)
				main_image = result.get("imageMain")
				variant_date_update.update({'default_code':result.get('itemCode'),'json_data_varaint':str(result), 'image_1920': base64.b64encode(requests.get(main_image).content).decode('utf-8') if main_image else '',})
				success = models.execute_kw(
					db, uid, password,
					'product.product', 'write',
					[[update_variant], variant_date_update]
				)
				for pricing_data in result.get('pricing', []):
					price = float(pricing_data.get('industryCol') or 0.0)
					min_qty = float(pricing_data.get('priceBar') or 1.0)

					models.execute_kw(db, uid, password, 'product.pricelist', 'write', [[1], {
						'item_ids': [(0, 0, {
							'product_id': update_variant,
							'fixed_price': price,
							'min_quantity': min_qty,
						})]
					}])
				cr.execute("""
					UPDATE queue_job
					SET state = %s, records = %s
					WHERE reference = %s
				""", ('done', update_variant, result.get('itemCode')))
				self.env.cr.commit()
			except Exception as e:
				cr.execute("""
					UPDATE queue_job
					SET state = %s, error_reason_text = %s
					WHERE reference = %s
				""", ('fail', str(e), result.get('itemCode')))
				self.env.cr.commit()
		_logger.info("------END-------%s", datetime.now())

	def get_laltax_data(self):
		_logger.info("-\n\n------START-1212121--get_laltax_data---%s", datetime.now())
		pim_config_id = self.env['pimore.vender.config'].browse(4)
		attribute_values, categories = self.get_product_data(pim_config_id)
		model = self.env['ir.model'].search([('model', '=', 'product.template')], limit=1).id
		odoo_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
		db = self.env.cr.dbname
		username = "admin"
		password = 'admin'
		common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
		uid = common.authenticate(db, username, password, {})
		models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")
		cr = self.env.cr
		cr.execute(
		    """
		    SELECT sub_reference, reference, result
		    FROM queue_job
		    WHERE state = 'process' AND model_id = %s AND pim_config_id = %s
		    LIMIT 20
		    """,
		    (model, pim_config_id.id)
		)
		rows = cr.fetchall()
		# Unzip into two separate lists
		sub_references, references, results = zip(*rows) if rows else ([], [], [])
		# Convert to lists
		sub_references = list(sub_references)
		references = list(references)
		results = list(results)
		tempaltes = {}
		if references:
			cr.execute(
				"""
				SELECT model_code,id
				FROM product_template
				WHERE model_code in %s
				""",
				(tuple(references),)
			)
			tempaltes = dict(cr.fetchall())
		product_attribute_dict = {}
		for result in results:
			if result:
				update_variant, attribute_color_data = False, False
				it_itemColour = result.get('lt_ItemColour')
				current_attribute = False
				template_data = self.get_product_template_data(result, pim_config_id)
				if it_itemColour in attribute_values:
					attribute_color_data = attribute_values.get(it_itemColour)
				if result.get('lt_ProductCode') in tempaltes:
					main_product_tempalte = tempaltes.get(result.get('lt_ProductCode'))
					if attribute_color_data:
						current_attribute = attribute_color_data.get('id')
						existing_line = False
						if main_product_tempalte not in product_attribute_dict and attribute_color_data:
							attribute_lines = models.execute_kw(
								db, uid, password,
								'product.template', 'read',
								[main_product_tempalte],
								{'fields': ['attribute_line_ids']}
							)
							# Get line IDs
							line_ids = attribute_lines[0]['attribute_line_ids']
							attribute_line_data = models.execute_kw(
								db, uid, password,
								'product.template.attribute.line', 'read',
								[line_ids],
								{'fields': ['attribute_id']}
							)
							for attribute_data in attribute_line_data:
								if main_product_tempalte in product_attribute_dict:
									if attribute_data.get('attribute_id')[0] not in product_attribute_dict.get(main_product_tempalte):
										product_attribute_dict.get(main_product_tempalte).update({attribute_data.get('attribute_id')[0]: attribute_data.get('id')})
								else:
									product_attribute_dict.update({main_product_tempalte: {attribute_data.get('attribute_id')[0]: attribute_data.get('id')}})
								if attribute_color_data.get('attribute_id') == attribute_data.get('attribute_id')[0]:
									existing_line = attribute_data.get('id')
						else:
							if product_attribute_dict.get(main_product_tempalte):
								existing_line = product_attribute_dict.get(main_product_tempalte).get(attribute_color_data.get('attribute_id'))
						if existing_line:
							success = models.execute_kw(
							    db, uid, password,
							    'product.template.attribute.line', 'write',
							    [[existing_line], {
							        'value_ids': [(4, attribute_color_data.get('id'))]
							    }]
							)
						else:
							updating_data = {'attribute_line_ids' : [(0, 0, {
									'attribute_id': attribute_color_data.get('attribute_id'),  # Color
									'value_ids': [(6, 0, [attribute_color_data.get('id')])]  # Red, Blue
								})]}
							success = models.execute_kw(
								db, uid, password,
								'product.template', 'write',
								[[main_product_tempalte], updating_data]
							)
				else:
					attribute_line = []
					if attribute_color_data:
						attribute_line.append(
							(0, 0, {
								'attribute_id': attribute_color_data.get('attribute_id'),  # Color
								'value_ids': [(4, attribute_color_data.get('id'))]  # Red, Blue
							}),
						)
					cat_code = result.get('lt_Category')[0].get('code')
					cat_id = categories.get(cat_code, {}).get('id')
					template_data.update({'attribute_line_ids': attribute_line, 'public_categ_ids': [(4,(cat_id))] })
					main_product_tempalte = models.execute_kw(
							db, uid, password,
							'product.template', 'create',
							[template_data]
						)
					tempaltes.update({result.get('lt_ProductCode'): main_product_tempalte})
				variant_products = models.execute_kw(
					db, uid, password,
					'product.product', 'search_read',
					[[['product_tmpl_id', '=', main_product_tempalte]]],
					{
						'fields': ['id', 'name', 'default_code', 'product_template_attribute_value_ids'],
						'order': 'id desc',
					}
				)
				update_variant = variant_products[0].get('id')
				for variant_product in variant_products:
					cr.execute("""
					    SELECT product_attribute_value_id
					    FROM product_template_attribute_value
					    WHERE id IN %s
					""", [tuple(variant_product.get('product_template_attribute_value_ids'))])  # Make sure it's a tuple in a list
					# Fetch all rows
					rows = cr.fetchall()
					# Extract just the IDs into a flat list
					value_ids = [row[0] for row in rows]
					if attribute_color_data:
						if attribute_color_data.get('id') in value_ids:
							update_variant = variant_product.get('id')
					else:
						update_variant = variant_product.get('id')

				variant_date_update = self.get_product_template_data(result, pim_config_id)
				main_image = result.get("lt_ItemImagesPreview")
				variant_date_update.update({'default_code':result.get('lt_ItemCode'),'json_data_varaint':str(result), 'image_1920': base64.b64encode(requests.get(main_image).content).decode('utf-8') if main_image else '',})
				success = models.execute_kw(
					db, uid, password,
					'product.product', 'write',
					[[update_variant], variant_date_update]
				)
				for pricing_data in result.get('lt_ProductPrice', []):
					price = float(pricing_data.get('Price').replace('£', '') or 0.0)
					min_qty = float(pricing_data.get('MinQuantity') or 1.0)

					models.execute_kw(db, uid, password, 'product.pricelist', 'write', [[1], {
						'item_ids': [(0, 0, {
							'product_id': update_variant,
							'fixed_price': price,
							'min_quantity': min_qty,
						})]
					}])
				cr.execute("""
						UPDATE queue_job
						SET state = %s, records = %s
						WHERE reference = %s
					""", ('done', update_variant, result.get('lt_ItemCode')))
				self.env.cr.commit()
			# except Exception as e:
			# 	cr.execute("""
			# 		UPDATE queue_job
			# 		SET state = %s, error_reason_text = %s
			# 		WHERE reference = %s
			# 	""", ('fail', str(e), result.get('lt_ItemCode')))
			# 	self.env.cr.commit()
		_logger.info("------END-------%s", datetime.now())