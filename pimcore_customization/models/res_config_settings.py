# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_artwork_proofing = fields.Boolean(related="company_id.is_artwork_proofing", string="Is Artwork Approval",readonly=False)
    artwork_approval = fields.Integer(related="company_id.artwork_approval", string="Artwork Approval Cycle",readonly=False)
    approval_amount = fields.Float(related="company_id.approval_amount", string="Artwork Approval Amount",readonly=False)

    @api.model
    def default_get(self, fields_list):
        defaults = super(ResConfigSettings, self).default_get(fields_list)
        company = self.env.company
        if 'is_artwork_proofing' in fields_list:
            defaults['is_artwork_proofing'] = company.is_artwork_proofing 
        if 'artwork_approval' in fields_list:
            defaults['artwork_approval'] = company.artwork_approval
        if 'approval_amount' in fields_list:
            defaults['approval_amount'] = company.approval_amount
        return defaults

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        company_ids = self.env['res.company'].search([])
        for company in company_ids:
            company.write({
                'is_artwork_proofing': self.is_artwork_proofing,
                'artwork_approval': self.artwork_approval,
                'approval_amount': self.approval_amount,
           })