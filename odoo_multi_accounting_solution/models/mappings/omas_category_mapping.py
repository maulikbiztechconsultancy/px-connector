# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api

class OMASCategoryMapping(models.Model):
	_name = 'omas.category.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Category Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('product.category','Odoo Category', required=True)
	odoo_category_id = fields.Integer('Odoo Category ID',required=True)

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_category_id = self.name.id
