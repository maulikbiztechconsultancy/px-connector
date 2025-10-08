# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
import logging
_logger = logging.getLogger('__name__')
from odoo import api,fields,models

class OMASExportOperation(models.TransientModel):
	_name = 'omas.export.operation'
	_description = 'Odoo Multi-Accounting Solution Export Operation'

	object = fields.Selection(selection=[
		('accounts', 'Accounts'),
		('customers', 'Customers'),
		('templates', 'Products'),
		('orders', 'Sale Orders'),
  		('purchase_orders', 'Purchase Order'),
		('invoices', 'Invoices'),
  		('credit_notes', 'Credit Notes'),
		('payments', 'Account Payments'),
		
	])
 
	invoice_bill_selection = fields.Selection([
     ('out_invoice', 'Customer Invoices'),
     ('in_invoice', 'Vendor Bills')
     ], default="out_invoice")

	credit_refund_selection = fields.Selection([
		('out_refund','Credit Note'),
		('in_refund','Refund')
	], default="out_refund")

	operation=fields.Selection(
		selection=[
			('export','Export'),
			('update','Update')
		],
		default ='export',
		required=True
	)

	instance_id=fields.Many2one(
		comodel_name='omas',
		string      ='Instance',
		domain      =[('is_connected','=',True)]
	)

	instance = fields.Selection(related='instance_id.instance', string='Instance Type')

	def export_button(self):
		kwargs = {}
		object = self.object
		if object == 'invoices':
			kwargs.update({'move_type':self.invoice_bill_selection})
		elif object == 'credit_notes':
			kwargs.update({'move_type':self.credit_refund_selection})
		return self.instance_id.export_entities(object, **kwargs)
