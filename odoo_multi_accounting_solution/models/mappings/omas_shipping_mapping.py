# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api

class OMASShippingMapping(models.Model):
	_name = 'omas.shipping.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Shipping Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('delivery.carrier','Odoo Carrier', required=True)
	odoo_shipping_id = fields.Integer('Odoo Shipping ID',required=True)

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_shipping_id = self.name.id
