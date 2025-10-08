# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api

class OMASTemplateMapping(models.Model):
	_name = 'omas.template.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Template Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('product.template','Odoo Template', required=True)
	odoo_template_id = fields.Integer('Odoo Template ID',required=True)
	default_code = fields.Char('Default code/SKU')
	barcode = fields.Char('Barcode/EAN/UPC or ISBN')

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_template_id = self.name.id

	# delete omas product mapping if reference omas template mapping is deleted
	def unlink(self):
		instance_ids = self.mapped('instance_id.id')
		template_ids = list(map(int, self.mapped('odoo_template_id')))
		mappings = self.env['omas.product.mapping'].search(
			[
				('instance_id', 'in', instance_ids),
				('odoo_template_id', 'in', template_ids)
			]
		)
		mappings.unlink()
		return super(OMASTemplateMapping, self).unlink()
