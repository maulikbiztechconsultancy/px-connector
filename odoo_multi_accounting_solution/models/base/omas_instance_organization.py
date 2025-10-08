# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import api,fields,models
from odoo.exceptions import ValidationError


class OMASInstanceOrganization(models.Model):
    _name        = 'omas.instance.organization'
    _description = 'OMAS Instance Organizations'

    name = fields.Char()
    instance_id = fields.Many2one(
        comodel_name='omas',
        string='Instance')
    instance_name = fields.Selection(string='Instance Name',related='instance_id.instance',store=True)
    remote_id = fields.Char('Remote ID')
    connection_id = fields.Char(string='Connection Id', help="This Field Store The Remote Connection Id Which Will Help While Disconnecting The Individual Connection")
    _sql_constraints = [
        ('value_instance_state_uniq', 'unique (instance_id, remote_id)',
        'This organization already exists !')
    ]
