# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api


class OMASTaxMapping(models.Model):
	_name        = 'omas.tax.mapping'
	_inherit     = 'omas.base.mapping'
	_description = 'Tax Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('account.tax','Odoo Tax')
	odoo_tax_id = fields.Integer('Odoo Tax ID')
	active = fields.Boolean("Active")
	mapping_display_name = fields.Char("Name")
	tax_amount = fields.Char(string="Amount", help="Tax amount in percent (%)")

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_tax_id = self.name.id
