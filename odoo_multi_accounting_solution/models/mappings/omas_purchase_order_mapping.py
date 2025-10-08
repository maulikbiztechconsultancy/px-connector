# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api

class OMASPurchaseOrderMapping(models.Model):
	_name = 'omas.purchase.order.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Order Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('purchase.order','Odoo Purchase Order', required=True)
	odoo_purchase_order_id = fields.Integer('Odoo Purchase Order ID',required=True)

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_purchase_order_id = self.name.id
