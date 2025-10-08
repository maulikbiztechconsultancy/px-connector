# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import fields, models, exceptions

import logging
_logger = logging.getLogger(__name__)


class OMASImportOperation(models.TransientModel):
	_name = 'omas.import.operation'
	_description = 'Odoo Multi-Accounting Solution Import Operation'

	object = fields.Selection(selection=[
		('taxes','Taxes'),
		('accounts', 'Accounts'),
		('payment_methods','Payment Methods'),
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

	operation = fields.Selection(
		selection=[
			('import', "Import"),
			('update', 'Update')
		],
		default='import',
		required=True
	)

	instance_id=fields.Many2one(
		comodel_name='omas',
		string ='Instance',
		domain = [('is_connected','=',True)]
	)
	instance = fields.Selection(related='instance_id.instance', string ='Instance Type',)

	import_type = fields.Selection([('blank','Blank Mapping'),
                                     	('create','Create Records')], default="blank")
	
	def import_button(self):
		kwargs = {}
		if hasattr(self, f'{self.instance}_get_filter_type'):
			kwargs.update(getattr(self, f'{self.instance}_get_filter_type')())
		object = self.object
		if object in ["taxes", "accounts", "payment_methods"]:
			kwargs.update({'import_type': self.import_type})
		if object in ['invoices', 'credit_notes']:
			move_type = self.invoice_bill_selection if object == 'invoices' else self.credit_refund_selection
			kwargs.update({'move_type': move_type})  
		return self.instance_id.import_entities(object, **kwargs)
