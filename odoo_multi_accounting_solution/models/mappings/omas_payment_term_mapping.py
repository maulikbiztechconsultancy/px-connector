# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models

class OMASPaymentMethodMapping(models.Model):
	_name        = 'omas.payment.term.mapping'
	_inherit     = 'omas.base.mapping'
	_description = 'Payment Term Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('account.payment.term','Odoo payment Term', required=True)
	odoo_payment_term_id = fields.Integer('Odoo Payment Term ID',required=True)

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_payment_term_id = self.name.id
