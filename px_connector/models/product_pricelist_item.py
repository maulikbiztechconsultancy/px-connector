from odoo import api, exceptions, fields, models, _
import logging
import random
import json
import requests
import base64
import html
import ast
from datetime import datetime, timedelta
from itertools import product
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import config, html_escape
from odoo import Command

from odoo.addons.base_sparse_field.models.fields import Serialized
_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    _name = "queue.job"
    _description = "Queue Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'reference'

    # Based configration of Job Queue
    name = fields.Char(string="Description", required=True)
    state = fields.Selection(
        [('draft', 'Draft'),
         ('process', 'Process'),
         ('done', 'Done'),
         ('cancelled', 'Cancelled'),
         ('fail', 'Fail'),
         ], string='State', default='draft')
    user_id = fields.Many2one(comodel_name="res.users", string="User ID")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", index=True)
    priority = fields.Integer("Priority")
    result = fields.Json("Result")
    result_text = fields.Text("Result Text")
    error_reason = fields.Text("Error Reason")

    # Mapping Record
    model_id = fields.Many2one('ir.model', string="Model", readonly=True)
    mapping_record = fields.Integer("Mapped Record", readonly=True)
    reference = fields.Char('Reference', readonly=True)
    sub_reference = fields.Char('Sub Reference', readonly=True)
    supplier_id = fields.Many2one('supplier.configuration', string="Supplier", readonly=True)

    # Time Configration
    date_created = fields.Datetime(string="Created Date", readonly=True)
    date_started = fields.Datetime(string="Start Date", readonly=True)
    date_enqueued = fields.Datetime(string="Enqueue Time", readonly=True)
    date_done = fields.Datetime(readonly=True)
    exec_time = fields.Float('Time(s)', readonly=True)


    def action_draft(self):
        # Set Draft state.
        for queue in self:
            queue.state = 'draft'

    def action_cancel(self):
        # Set Draft state.
        for queue in self:
            queue.state = 'cancelled'

    def set_display_name(self):
        # Set Display Name
        for queue in self:
            if queue.reference:
                queue.display_name = ' [ ' + queue.reference + ' ]' + queue.name
            else:
                queue.display_name = queue.name

    @api.model_create_multi
    def create(self, vals_list):
        # Override Create method
        queue = super(QueueJob, self).create(vals_list)
        # Set display_name based on ref
        queue.set_display_name()
        return queue

    @api.depends('result')
    def _compute_display_data(self):
        # Visible to result data
        for queue in self:
            try:
                if queue.result:
                    queue.result_text = json.dumps(
                        queue.result.with_context(bin_size=False).to_dict(),
                        indent=4,
                    )
                else:
                    queue.result_text = {}
            except json.decoder.JSONDecodeError:
                queue.result_text = '{}'

    def set_result_data(self):
        # Set result data formate
        self.result = self.result_text

    def start_process(self):
        pass