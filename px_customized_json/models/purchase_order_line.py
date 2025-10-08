# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.model
    def _prepare_purchase_order_line_from_procurement(self, product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values, po):
        # Added by Radhika: Set purchase order line price_unit from sales order's calculated purchase_price
        # and convert to vendor currency
        res = super()._prepare_purchase_order_line_from_procurement(
            product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values, po
        )
        sale_line_id = values.get('sale_line_id')
        if sale_line_id and po:
            sol = self.env['sale.order.line'].browse(sale_line_id)
            purchase_price = sol.purchase_price
            if sol.product_id.product_service_type in ['printing', 'delivery', 'extra_charges']:
                # Convert from sale order currency to vendor/PO currency
                sale_currency = sol.order_id.currency_id
                po_currency = po.currency_id

                if sale_currency and po_currency and sale_currency != po_currency:
                    try:
                        purchase_price = sale_currency._convert(
                            purchase_price,
                            po_currency,
                            po.company_id,
                            po.date_order or self.env.context.get('default_date_order') or fields.Date.context_today(self)
                        )
                    except Exception:
                        pass

                res['price_unit'] = purchase_price
        return res
