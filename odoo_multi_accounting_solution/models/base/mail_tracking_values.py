# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from odoo import models, api

class InhetitMailMessage(models.Model):
    _inherit = "mail.tracking.value"

    # Changed the tracking message for the confidential fields in omas
    @api.model
    def _create_tracking_values(self, initial_value, new_value, col_name, col_info, record):
        if record._name == 'omas':
            if col_name == 'client_id' or col_name == 'client_secret':
                initial_value = 'Client ID' if col_name == 'client_id' else 'Client Secret'
                new_value = "Client ID  has been changed"
                if col_name == 'client_secret':
                    new_value = 'Client Secret has been changed'
        vals = super()._create_tracking_values(initial_value, new_value, col_name, col_info, record)
        return vals