# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api

class OMASCustomerMapping(models.Model):
	_name = 'omas.customer.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Customer Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('res.partner','Odoo Customer')
	odoo_customer_id = fields.Integer('Odoo Customer ID', required = True)
	type = fields.Selection([
		('contact','Contact'),
		('invoice', 'Invoice'),
		('delivery', 'Delivery')
	], string = 'Type', default='contact')
	customer_type = fields.Selection([
		('customer','Customer'),
		('vendor', 'Vendor')
  	], string="Customer Type", default='customer')

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_customer_id = self.name.id
