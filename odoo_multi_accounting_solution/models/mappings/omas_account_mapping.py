# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api

class OMASAccountMapping(models.Model):
	_name = 'omas.account.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Account Mapping Model for Odoo Multi Accounting Solution'
	rec_name = 'id'

	name = fields.Many2one('account.account','Odoo Account')
	# odoo_account_id = fields.Integer('Odoo Account ID',required=True)
	odoo_account_id = fields.Integer('Odoo Account ID')
	active = fields.Boolean('Active')
	mapping_display_name = fields.Char("Name")
	remote_account_code = fields.Char('Remote Account Code')

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_account_id = self.name.id
