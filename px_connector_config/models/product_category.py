from odoo import fields, models, api, _
import json
from datetime import datetime


class ProductCategoryRelation(models.Model):
    _name = 'product.category.relation'
    _description = 'Product Category Relation'

    config_id = fields.Many2one('pimore.vender.config', string='Vendor Config', ondelete='cascade')
    odoo_caegory_id = fields.Many2one(
        'product.category', string="Current Category",
    )
    pim_category_id = fields.Many2one('queue.job', string="Custom Value", domain="[('model_id', '=', 'product.category'), ('state', '=', 'process'), ('pim_config_id', '=', config_id)]")

class ProductCategory(models.Model):
    _inherit = "product.category"

    reference_id = fields.Char(string='Reference Id',readonly=True)
    reference = fields.Char(string='Reference',readonly=True)
    group_code = fields.Char(string='Group Code', readonly=True)
    group_description = fields.Text(string='Group Description Code', readonly=True)
    pim_config_id = fields.Many2one("pimore.vender.config", string="PIM ID")

    def create_queue_record_create(self,job_queue):
        # queue_categorys = self.env['queue.job'].search([('model_id', '=', 'product.category'), ('state', '=', 'process')], order='priority asc')
        queue_categorys = sorted(job_queue, key=lambda j: j.priority or 0)
        category_parent = False
        CATEGORY = self.search([])
        for queue_category in queue_categorys:
            try:
                CATEGORY = self.get_data_prepartion(CATEGORY, queue_category)
                queue_category.state = 'done'
                if 'parent_category' in queue_category.result:
                    category_parent = True
            except Exception as e:
                queue_category.write({
                    'state': 'fail',
                    'error_reason': str(e)
                    })
                raise Exception(f"An error occurred: {str(e)}")
        if category_parent:
            for queue_category in queue_categorys:
                CATEGORY = self.set_parent_category(CATEGORY, queue_category)

    def get_data_prepartion(self, CATEGORY, queue_category=None):
        pim_config_id = queue_category.pim_config_id
        filed_data = {'pim_config_id': pim_config_id.id}
        result = queue_category.result
        categ = self.env['product.category']
        if queue_category.id not in pim_config_id.category_relation_ids.pim_category_id.ids:
            for fileds in pim_config_id.category_field_lines:
                filed_data.update({
                    fileds.product_category_field_id.name: dict(result).get(fileds.custom_value)
                    })
            if filed_data.get('reference_id'):
                # categ |= self.search([('reference_id', '=', filed_data.get('reference_id'))])
                categ = next((cat for cat in CATEGORY if cat.reference_id == str(filed_data.get('reference_id'))), categ)
                if categ and categ.id:
                    categ.write(filed_data)
                else:
                    if filed_data.get('name'):
                        categ = self.create(filed_data)
                        CATEGORY |= categ
            if categ:
                queue_category.records = categ.id
        return CATEGORY

    def set_parent_category(self, CATEGORY, queue_category=None):
        pim_config_id = queue_category.pim_config_id
        filed_data = {'pim_config_id': pim_config_id.id}
        result = queue_category.result
        categ = self.env['product.category']
        filed_data = {}
        for fileds in pim_config_id.category_field_lines:
            filed_data.update({
                fileds.product_category_field_id.name: fileds.custom_value
                })
        if 'parent_category' in result and result.get('parent_category'):
            parents = result.get('parent_category').split(',')
            reference_id = result.get(filed_data.get('reference_id'))
            if reference_id in parents:
                parents.remove(reference_id)

            # main_category = self.search([('reference_id', '=', reference_id)], limit=1)
            main_category = next((cat for cat in CATEGORY if cat.reference_id == str(reference_id)), categ)
            # for parents_data in self.search([('reference_id', 'in', parents)]):
            for parents_data in next((cat for cat in CATEGORY if cat.reference_id == str(parents)), categ):
                # parent_category = self.search([('reference_id', '=', reference_id),('parent_id', '=', parents_data.id)], limit=1)
                parent_category = next((cat for cat in CATEGORY if cat.reference_id == str(parents) and cat.parent_id.id == parents_data.id), categ)
                if not parent_category:
                    if not main_category.parent_id and not main_category.parent_id.id:
                        main_category.parent_id = parents_data.id
                    else:
                        CATEGORY |= main_category.copy(default={'parent_id': parents_data.id})
        return CATEGORY