# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import models, fields,tools

class ResCompany(models.Model):
    _inherit = 'res.company'

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'uom_id' in fields_list and not res.get('uom_id'):
            res['uom_id'] = self._get_default_uom_id().id
        return res


    @tools.ormcache()
    def _get_default_uom_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref('uom.product_uom_kgm')

    purchase_validation = fields.Boolean(string="Purchase Validation", default=False)
    is_artwork_proofing = fields.Boolean(string="Is Artwork Approval")
    artwork_approval = fields.Integer(string="Artwork Approval Cycle")
    approval_amount = fields.Float(string="Artwork Approval Amount")
    carbon_co2 =  fields.Float(string="CO2")
    uom_id = fields.Many2one(
        'uom.uom', 'Unit of Measure',
        default=_get_default_uom_id, required=True, readonly=True, store=True,
        help="Default unit of measure used for all stock operations.")
    quote_first_image = fields.Binary()
    logo_white = fields.Binary()
    logo_black = fields.Binary()
    turtile_header = fields.Binary()