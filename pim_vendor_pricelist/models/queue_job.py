# -*- coding: utf-8 -*
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
from odoo import _, api, exceptions, fields, models, _
from odoo.osv import expression
from odoo.tools import config, html_escape
from odoo import Command

from odoo.addons.base_sparse_field.models.fields import Serialized

_logger = logging.getLogger(__name__)



class QueueJob(models.Model):
    _inherit = 'queue.job'

    def set_pricelist(self):
        """
           Set pricelist least sync.
        """
        model = self.env['ir.model'].search([('model', '=', 'product.pricelist')], limit=1).id
        job_queues = self.env['queue.job'].search([('model_id', '=', model), ('state', '=', 'process')], limit=250)
        cr = self.env.cr
        sub_references = job_queues.mapped('sub_reference')
        varianr_dict = {}
        if sub_references:
            cr.execute(
                """
                SELECT default_code,id
                FROM product_product
                WHERE default_code in %s
                """,
                (tuple(sub_references),)
            )
            varianr_dict = dict(cr.fetchall())

        for queue in job_queues:
            method_name = "set_pricelist_%s" % queue.pim_config_id.vendor_short_code.lower()
            method = getattr(queue, method_name, None)
            varianr_id = varianr_dict.get(queue.sub_reference) or False
            method(varianr_id)

    def set_pricelist_pf(self, varianr_id):
        try:
            if varianr_id:
                update_variant = self.env['product.product'].sudo().browse(varianr_id)
                currency = self.pim_config_id.currency_id
                to_currency = self.pim_config_id.converted_currency_id
                self.env.cr.execute("""
                    DELETE FROM product_pricelist_item
                    WHERE product_id = %s
                """, [varianr_id])
                self.env.cr.commit()

                self.env.cr.execute("""
                    DELETE FROM product_supplierinfo
                    WHERE partner_id = %s AND product_id = %s
                """, (self.pim_config_id.partner_id.id, update_variant.id))
                self.env.cr.commit()
                pim_config_id = self.pim_config_id
                pricelist = 1
                seen_keys_sales = set()
                seen_keys_vendor = set()
                pricelist_items_to_create = []
                pricelist_items_to_update = []
                supplierinfo_to_create = []
                supplierinfo_to_update = []
                for pricing_data in self.result.get('pricing'):
                    min_qty = float(pricing_data.get('priceBar') or 1.0)
                    prices = pricing_data.get('nettPrice', '0')
                    base_price = self._sanitize_price_string(prices)
                    price_raw = base_price
                    if currency != to_currency:
                        price_raw = self._get_currency_convert_amount(currency,float(base_price),to_currency)
                    try:
                        base_price = float(price_raw or 0.0)
                    except ValueError:
                        base_price = 0.0
                    # Sales mode
                    if pim_config_id.create_pricelist in ('sales', 'both'):
                        margin_percent = pim_config_id.sale_margin or 0.0
                        price = base_price + (base_price * margin_percent / 100.0)
                        key_sales = (update_variant.id, min_qty)
                        if key_sales not in seen_keys_sales:
                            seen_keys_sales.add(key_sales)
                            pricelist_items_to_create.append((0, 0, {
                                'product_id': update_variant.id,
                                'fixed_price': price,
                                'pim_config_id': pim_config_id.id,
                                'price': price,
                                'min_quantity': min_qty,
                                'currency_id': pim_config_id.converted_currency_id.id,
                            }))

                    # Vendor mode
                    if pim_config_id.create_pricelist in ('vendor', 'both'):
                        if min_qty not in seen_keys_vendor:
                            seen_keys_vendor.add(min_qty)
                            supplierinfo_to_create.append((0, 0, {
                                'partner_id': pim_config_id.partner_id.id,
                                'product_id': update_variant.id,
                                'pim_config_id': pim_config_id.id,
                                'min_qty': min_qty,
                                'price': base_price,
                                'currency_id': pim_config_id.converted_currency_id.id,
                            }))
                # Write updates
                if pricelist_items_to_update or pricelist_items_to_create:
                    self.env['product.pricelist'].sudo().browse(pricelist).write({'item_ids': pricelist_items_to_update + pricelist_items_to_create})
                if supplierinfo_to_update or supplierinfo_to_create:
                    update_variant.write({'seller_ids': supplierinfo_to_update + supplierinfo_to_create})
                self.unlink()

            else:
                self.state = 'fail'
                self.error_reason_text = 'Product not found.'
        except Exception as e:
            self.error_reason_text = str(e)
            self.state = 'fail'
