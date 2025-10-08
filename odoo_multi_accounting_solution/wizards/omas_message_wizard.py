#
#   Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
##########################################################################

from odoo import fields, models

class OMASMessageWizard(models.TransientModel):
	_name = "omas.message.wizard"
	_description = "Message Wizard For Odoo Multi Accounting Solution"
	
	text = fields.Html(string='Message', readonly=True, translate=True)

	def generate_message(self, message, name='Message/Summary'):
		partial_id = self.create({'text':message}).id
		return {
			'name':name,
			'view_mode': 'form',
			'view_id': False,
			'res_model': 'omas.message.wizard',
			'res_id': partial_id,
			'type': 'ir.actions.act_window',
			'nodestroy': True,
			'target': 'new',
			'domain': '[]',
		}
