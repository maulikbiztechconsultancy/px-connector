from odoo import models, fields, api

class OMASBaseMapping(models.Model):
    _name = 'omas.base.mapping'
    _description = 'Base Mapping Model for Odoo Multi Accounting Solution'

    instance_id = fields.Many2one(comodel_name = 'omas', string='Instance ID')
    remote_id = fields.Char('Remote ID')
    need_sync = fields.Boolean(default=False, string='Update Required')
    operation = fields.Selection([
        ('import', 'Import'),
        ('export', 'export')
        ],default = 'import')

    @api.model
    def _get_instances(self):
        return self.env['omas'].get_instances()

    def toggle_active_mappings(self):
        for record in self:
            record.active = not record.active

    instance = fields.Selection(related = 'instance_id.instance')

    _sql_constraints = [
		(
			'instance_remote_id_uniq',
			'unique(instance_id,remote_id)',
			'Remote ID must be unique for Instance mapping!'
		)
	]
