# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import random
from datetime import datetime, timedelta

from odoo import _, api, exceptions, fields, models
from odoo.osv import expression
from odoo.tools import config, html_escape

from odoo.addons.base_sparse_field.models.fields import Serialized


_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    """Model storing the jobs to be executed."""

    _name = "queue.job"
    _description = "Queue Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'reference'

    name = fields.Char(string="Description", readonly=True)
    user_id = fields.Many2one(comodel_name="res.users", string="User ID")
    company_id = fields.Many2one(
        comodel_name="res.company", string="Company", index=True
    )

    model_id = fields.Many2one('ir.model', string="Model", readonly=True)
    dependencies = Serialized(readonly=True)
    
    records = fields.Integer()
    priority = fields.Integer()
    result = fields.Json()
    result_text = fields.Text()
    error_reason = fields.Json()
    error_reason_text = fields.Text()

    reference = fields.Char('Reference', readonly=True)
    sub_reference = fields.Char('Sub Reference', readonly=True)

    date_created = fields.Datetime(string="Created Date", readonly=True)
    date_started = fields.Datetime(string="Start Date", readonly=True)
    date_enqueued = fields.Datetime(string="Enqueue Time", readonly=True)
    date_done = fields.Datetime(readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'),
        ('process', 'Process'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ('fail', 'Fail'),
        ], string='State', default='draft')

    def action_draft(self):
        for queue in self:
            queue.state = 'draft'

    def action_cancel(self):
        for queue in self:
            queue.state = 'cancelled'

    def set_display_name(self):
        for queue in self:
            if queue.reference:
                queue.display_name = queue.name + ' [ ' +queue.reference + ' ]'
            else:
                queue.display_name = queue.name