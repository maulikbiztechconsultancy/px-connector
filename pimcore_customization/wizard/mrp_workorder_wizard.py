from odoo import fields, models,_
from odoo.exceptions import  ValidationError

class MrpWorkOrderWizard(models.TransientModel):
    _name = 'mrp.workorder.wizard'
    _description = 'Mrp Workorder Wizard'

    workcenter_id = fields.Many2one('mrp.workcenter',string="Select Workcenter")
    resource_id = fields.Many2one('res.users', string="Select Resource")

    def action_update_workcenter(self):
        workorder_id = self.env.context.get('default_workorder_id')
        if workorder_id and self.workcenter_id:
            workorder_ids = self.env['mrp.workorder'].browse(workorder_id)
            for workorder in workorder_ids:
                if workorder.state in ['progress', 'done']:
                    raise ValidationError(f"You cannot change the workcenter of a workorder {workorder.display_name} that have state {workorder.state}")
                workorder.workcenter_id = self.workcenter_id
        if workorder_id and self.resource_id:
            workorder_ids = self.env['mrp.workorder'].browse(workorder_id)
            for workorder in workorder_ids:
                workorder.resource_id = self.resource_id