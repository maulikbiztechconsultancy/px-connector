# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from datetime import date

class CpqProduct(models.AbstractModel):
    _name = 'report.cpq.product'
    _description = 'Cpq Product Report'

    @api.model
    def get_html(self, data):
        render_values = self._get_report_data(data)
        return self.env['ir.qweb']._render('pimcore_customization.cpq_report',render_values)
    
    def _get_report_data(self, data):
        res_currency = self.env['res.currency']
        currency_id = data.get('currency_id')
        currency = res_currency.browse(currency_id)
        if not currency_id:
            currency = res_currency.search([('id','=',self.env.company.currency_id.id)])
        records = self.env['cpq.product.info'].search([('company_id','=',self.env.company.id)])
        product = []
        for rec in records:
            variant_ids = [val.product_variant for val in rec.product_variant_line if val.product_qty > 0]
            converted_total =  self.env.company.currency_id._convert(rec.grand_total, currency ,self.env.company,date.today())
            product.append({'id':rec.id,
                        'product_template_id':rec.product_template_id,
                        'variant_ids':variant_ids,
                        'printing_product_ids': rec.printing_product_ids,
                        'delivery_product_ids': rec.delivery_product_ids,
                        'total': converted_total
                    })
        return{
            'currency': currency,
            'products':product
        }