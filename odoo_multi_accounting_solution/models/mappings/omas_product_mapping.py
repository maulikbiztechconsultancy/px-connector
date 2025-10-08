# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api

class OMASProductMapping(models.Model):
	_name = 'omas.product.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Product Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('product.product','Odoo Product')
	odoo_product_id = fields.Integer('Odoo Product ID',required=True)
	odoo_template_id = fields.Many2one(string='Odoo Template',related='name.product_tmpl_id')
	default_code = fields.Char("Default code/SKU")
	barcode = fields.Char("Barcode/EAN/UPC or ISBN")
	remote_template_id = fields.Char('Remote Template ID')

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_product_id = self.name.id
