# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models
from odoo.exceptions import ValidationError


class OMASInstanceOrderStates(models.Model):
	_name        = 'omas.instance.order.state'
	_description = 'OMAS Instance Order State'
	rec_name     = 'odoo_order_state'

	instance_state = fields.Char('Instance Order State')
	odoo_order_state = fields.Selection([
		('draft', 'Quotation'),
		('sale', 'Sales Order'),
		('shipped', 'Shipped'),
		('cancelled', 'Cancelled')
	],'Odoo Order State')
	instance_id = fields.Many2one(
		comodel_name='omas',
		string='Instance')
	instance_name = fields.Selection(string='Instance Name',related='instance_id.instance',store=True)
	default_order_state = fields.Boolean(
		string='Default State',
		help="Default state if store state does not match the odoo state.")
	odoo_create_invoice = fields.Boolean(
		'Create Invoice', help="Create invoice in odoo.")
	odoo_set_invoice_state = fields.Selection([
		('open', 'Open'), ('paid', 'Paid')],
		string='Set Invoice State',
		help="The field is used to retrieve orders that are in a specific state.")
	odoo_ship_order = fields.Boolean(string="Create Shipment")
	_sql_constraints = [
		('value_instance_state_uniq', 'unique (instance_state, instance_id)', 'The instance order state already exists !')
	]

	@api.constrains('odoo_order_state', 'odoo_create_invoice', 'odoo_set_invoice_state')
	def _check_order_state(self):
		for rec in self:
			if rec.odoo_order_state not in ['sale', 'done'] and rec.odoo_create_invoice:
				raise ValidationError("Invoice can not be created for a %s sale order." % (rec.odoo_order_state))
			if (not rec.odoo_create_invoice) and rec.odoo_set_invoice_state:
				raise ValidationError("Create Invoice should be checked first.")

	@api.constrains('instance_id', 'default_order_state')
	def _check_default_order_state(self):
		for rec in self:
			if len(self.search([
				('default_order_state', '=', True),
				('instance_id', '=', rec.instance_id.id)
			])) > 1:
				raise ValidationError(
					"Only one state can be default at once !")
