# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class OMASPaymentMapping(models.Model):
	_name        = 'omas.payment.mapping'
	_inherit     = 'omas.base.mapping'
	_description = 'Payment Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('account.payment','Odoo payment', required=True)
	odoo_payment_id = fields.Integer('Odoo Payment ID',required=True)

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_payment_id = self.name.id
