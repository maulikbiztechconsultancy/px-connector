# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from odoo import fields, api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    xero_doc_number = fields.Char(string='Xero Doc Number')    