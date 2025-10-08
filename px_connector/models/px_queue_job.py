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
import time


_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    _name = "queue.job"
    _description = "Queue Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'reference'

    @api.depends('date_started', 'date_done')
    def _compute_duration_seconds(self):
        for job in self:
            exec_time = 0.0
            if job.date_done and job.date_started:
                delta = job.date_done - job.date_done
                exec_time = delta.total_seconds()
            job.exec_time = exec_time

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
    result_text = fields.Text("Result Text", readonly=True)
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
    exec_time = fields.Float('Time(s)', readonly=True, compute="_compute_duration_seconds", store=True)


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

    def start_process_now(self, job_count=None):
        # Updating record based on data
        if not job_count:
            job_count = 1
        finding_job = self.search([('state', '=', 'draft')], limit=job_count)
        for queue in finding_job:
            queue.start_process()

    def start_process(self):
        # Updating record based on data
        start_time = datetime.now()
        self.date_created = start_time
        self.date_started = start_time
        # try:
        if self.supplier_id:
            if self.supplier_id:
                self.env[self.model_id.model].json_process(self, self.supplier_id)
        # except Exception as e:
        #     self.write({
        #         'error_reason': e,
        #         'state': 'fail'
        #         })
        end_time = datetime.now()
        exec_time = (end_time - start_time).total_seconds()
        self.date_done = end_time
        self.exec_time = exec_time


    def action_product_update(self):
        for queue in self:
            # Build method name dynamically
            method_name = "set_product_details_%s" % queue.supplier_id.vendor_short_code.lower()

            # Call method on product_template instead of supplier_id
            product_template = queue.supplier_id.printing_product_id.product_tmpl_id

            method = getattr(product_template, method_name, None)
            if method:
                return method()
            else:
                raise UserError(_(f"Please contact administration: Purchase Vendor {queue.supplier_id.name}"))

    def set_pricelist(self):
        for queue in self:
            method_name = "set_pricelist_%s" % queue.supplier_id.vendor_short_code.lower()
            product_template = queue.supplier_id.printing_product_id

            method = getattr(product_template, method_name, None)
            if method:
                return method()
            else:
                raise UserError(_(f"Please contact administration: Purchase Vendor {queue.supplier_id.name}"))

