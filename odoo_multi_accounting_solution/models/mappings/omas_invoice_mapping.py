# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields, api

class OMASInvoiceMapping(models.Model):
	_name = 'omas.invoice.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Invoice Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('account.move','Odoo Invoice', required=True)
	odoo_invoice_id = fields.Integer('Odoo Invoice ID',required=True)
	mapping_move_type = fields.Selection([
		('in_invoice','Vendor Bill'),
		('in_refund', 'Refund'),
		('out_invoice','Customer Invoice'),
		('out_refund', 'Credit Note'),
	], default="out_invoice", string="Type", required=True)

	@api.constrains('name')
	def change_odoo_id(self):
		self.odoo_invoice_id = self.name.id
