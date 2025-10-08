from odoo import models,fields

class WorkOrder(models.Model):
    _inherit = 'mrp.workorder'

    resource_id = fields.Many2one('res.users', string="resource")

    def action_open_workcenter(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Set Workcenter',
            'res_model': 'mrp.workorder.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': 
            {
                'default_workorder_id': self.ids,
            },
        }