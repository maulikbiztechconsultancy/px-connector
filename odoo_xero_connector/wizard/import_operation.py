# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import fields, models, exceptions

import logging
_logger = logging.getLogger(__name__)

class OMASImportOperation(models.TransientModel):
    _inherit = 'omas.import.operation'

    omas_filter_type = fields.Selection(                ######### Selection Field ########
            string='Filter Type',
            selection=[
                ('all','All'),
                ('id','By IDs'),
                ('date_range', 'Date Range')
            ],
            default='all',
            required=True,
        )
        
    omas_min_date = fields.Date('Minimum Date')
    omas_max_date = fields.Date('Maximum Date')
    object_id = fields.Char('Object ID')

    def xero_get_filter_type(self):
        kwargs = {'filter_type': self.omas_filter_type}
        if self.omas_filter_type == 'id':
            kwargs['object_id'] = self.object_id
        if self.omas_filter_type == 'date_range':
            kwargs['min_date'] = self.omas_min_date
            kwargs['max_date'] = self.omas_max_date
        return kwargs