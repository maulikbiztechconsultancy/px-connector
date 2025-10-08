# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, tools

class ProductTemplate(models.Model):
    _inherit = "product.template"

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'uom_id_co2' in fields_list and not res.get('uom_id_co2'):
            res['uom_id_co2'] = self._get_default_uom_id().id
        return res

    @tools.ormcache()
    def _get_default_uom_id_co2_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref('uom.product_uom_gram')

    product_service_type = fields.Selection([
            ('finished', 'Finished'),
            ('printing', 'Printing Service'),
            ('delivery', 'Delivery'),
            ('raw_product', 'Raw Product'),
            ('extra_charges','Extra Charges')],
        string="Service Type",
        help="Type of service",
        default='finished',
        required=True
        )

    is_printing_method = fields.Boolean('Is Printing Method?')
    price = fields.Boolean('Printing Price')
    extra_price = fields.Boolean("Extra Price")
    priority = fields.Selection([
            ('0', 'Normal'),
            ('1', 'Favorite')],
        default='0', string="priority")
    is_artwork_product = fields.Boolean('Is Artwork Product')
    carbon_co2 =  fields.Float(string="CO2")

    purchase_validation = fields.Boolean(string="Purchase Validation", default=False)
    is_artwork_proofing = fields.Boolean(string="Is Artwork Approval")
    artwork_approval = fields.Integer(string="Artwork Approval Cycle")
    approval_amount = fields.Float(string="Artwork Approval Amount")
    carbon_co2 =  fields.Float(string="CO2")
    uom_id_co2 = fields.Many2one(
        'uom.uom', 'Unit of Measure',
        default=_get_default_uom_id_co2_id, required=True, readonly=True, store=True,
        help="Default unit of measure used for all stock operations.")

    def get_related_printing_product_ids(self,variant):
        varinat_ids = []
        delivery_ids  = []
        for data in variant:
            varinat_ids.append(variant.printing_variant_ids.ids)
            delivery_ids.append(variant.shipping_variant_ids.ids)
            related_delivery_product_ids = [item for sublist in delivery_ids for item in sublist]
            related_product_ids = [item for sublist in varinat_ids for item in sublist]
        return {'related_printing_product_ids': related_product_ids or [],'related_delivery_product_ids':related_delivery_product_ids or []}

    def get_data_val(self,combination_ids):
        combination = self.env['product.template.attribute.value'].browse(combination_ids)
        variant = self._get_variant_for_combination(combination)
        related_product_ids = self.get_related_printing_product_ids(variant).get('related_printing_product_ids')
        related_delivery_product_ids = self.get_related_printing_product_ids(variant).get('related_delivery_product_ids')
        return {'variant_id': variant.id if variant else None,
                'related_printing_product_ids':
                 related_product_ids if related_product_ids else [],
                'related_delivery_product_ids': related_delivery_product_ids if related_delivery_product_ids else []
                }
    def get_data_val_config(self):
        related_product_ids = self.get_related_printing_product_ids(self.product_variant_ids).get('related_printing_product_ids')
        related_delivery_product_ids = self.get_related_printing_product_ids(self.product_variant_ids).get('related_delivery_product_ids')
        return {'related_printing_product_ids':related_product_ids if related_product_ids else [],'related_delivery_product_ids': related_delivery_product_ids if related_delivery_product_ids else []}

    def get_attribute_line_data(self):
        if self:
            related_product_ids = self.get_related_printing_product_ids(self.product_variant_ids).get('related_printing_product_ids')
            related_delivery_product_ids = self.get_related_printing_product_ids(self.product_variant_ids).get('related_delivery_product_ids')
            return {'related_printing_product_ids':related_product_ids if related_product_ids else [],
                    'has_configurable_attributes':self.has_configurable_attributes,
                    'related_delivery_product_ids': related_delivery_product_ids if related_delivery_product_ids else [],
                     }

    def product_service_type_data(self):
        if self:
            if self.product_service_type in ['finished','raw_product']:
                return True

class ProductProduct(models.Model):
    _inherit = 'product.product'

    related_printing_service_products = fields.Many2many(
        'product.template',
        'product_product_printing_service_rel', 
        'product_id', 
        'related_product_id',
        string='Related Printing Service Products',
        domain=[('product_service_type', '=', 'printing')], 
        help="Only products with 'Printing Service' as service type are considered"
    )
    releted_supplier_products = fields.Many2many(
        'product.template',
        'product_product_supplier_rel',  # Custom relation table
        'product_id', 
        'related_product_id',
        string='Related Printing Supplier Products',
        domain=[('product_service_type', '=', 'finished')], 
        help="Only products with 'Printing Service' as service type are considered"
    )
    printing_thumbnail = fields.Binary('Printing Image', store=True)
    printing_thumbnail_upload = fields.Binary('Printing Image Upload', store=True)
    printing_thumbnail_name = fields.Char(string="Printing File name")
    display_name_with_variant = fields.Char(
        string="Descriptions",
        compute="_compute_display_name_with_variant",
    )

    @api.depends('product_template_variant_value_ids.name')
    def _compute_display_name_with_variant(self):
        for product in self:
            variant_names = product.product_template_variant_value_ids.mapped('name')
            product.display_name_with_variant = f"{product.name} ({', '.join(variant_names)})" if variant_names else product.name

    @api.onchange('printing_thumbnail')
    def _onchange_printing_thumbnail_upload(self):
        for data in self:
            if data.printing_thumbnail:
                data.printing_thumbnail_upload = data.printing_thumbnail
            else:
                data.printing_thumbnail_upload = False