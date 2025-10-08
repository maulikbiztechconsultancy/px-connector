# -*- coding: utf-8 -*
from odoo import models, fields, api, Command
import xmlrpc.client
from datetime import datetime
from odoo.http import request
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PimoreVendorConfig(models.Model):
    _inherit = 'pimore.vender.config'

    # def action_fetch_pimcore_product_data(self):
    #     """
    #        This method use for the add price lisr for PF Concept
    #     """
    #     for pf_pim in self:
    #         if pf_pim.update_product:
    #             print("----------")
    #         else:
    #             print("++++++++++++++++++++++++++++++++++++++++++++++++++")
    #             super(PimoreVendorConfig, self).action_fetch_pimcore_product_data()