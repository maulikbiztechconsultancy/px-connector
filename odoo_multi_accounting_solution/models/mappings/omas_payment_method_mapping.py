# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class OMASPaymentMethodMapping(models.Model):
	_name = 'omas.payment.method.mapping'
	_inherit = 'omas.base.mapping'
	_description = 'Payment Method Mapping Model for Odoo Multi Accounting Solution'

	name = fields.Many2one('account.journal', 'Odoo payment Method')
	odoo_payment_method_id = fields.Integer('Odoo Payment Method ID')
	remote_name = fields.Char('Remote Journal Name')
	mapping_display_name = fields.Char("Name")

	@api.constrains('name')
	def change_odoo_id(self):
		if self.name:
			self.odoo_payment_method_id = self.name.id

	@api.model
	def create_entity(self, instance_id, payment_method):
		odoo_id = False
		import_type = self._context.get('import_type', 'blank')
		name = payment_method.get('name')
		code = payment_method.get('code', False)
		type = payment_method.get('type', 'bank')
		match_mapping = self.env['omas.payment.method.mapping'].search([('instance_id','=',instance_id.id),('remote_id','=', payment_method.get('remote_id'))])
		if match_mapping:
			return match_mapping
		if import_type == 'create':
			if not code:
				if instance_id.journal_sequence_id:
					code = instance_id.journal_sequence_id.next_by_id()
				else:
					raise ValidationError("""Journal Code is Mandatory. Please enable the Set Payment Method Sequence field in Odoo Multi-Accounting Configuration View.\n""")
			odoo_id =  self.env['account.journal'].search([('code', '=', code)], limit=1)
			if not odoo_id:
				odoo_id = self.env['account.journal'].create({
					'name': name,
					'code': code,
					'type': type,
				})
		return self.create({
			'instance_id':instance_id.id,
			'name': odoo_id.id if odoo_id else False,
			'mapping_display_name': name,
			'remote_id': payment_method.get('remote_id'),
		})
