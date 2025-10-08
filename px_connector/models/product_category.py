from odoo import api, exceptions, fields, models, _


class ProductCatgoryu(models.Model):
    _inherit = "product.category"

    supplier_id = fields.Many2one('supplier.configuration', string="Supplier", readonly=True)

    def json_process(self, job, supplier_id):
        """
            Process import category based on queue.
        """
        method_name = "set_category_%s" % supplier_id.vendor_short_code.lower()
        method = getattr(self, method_name, None)
        if method:
            return method(job, supplier_id)

    def set_category_pf_concept(self, job, supplier_id, record=False):
        """
            Creating product Category Based on set values.
        """
        if not record:
            category = self.sudo().create({
                'name': job.result.get('name'),
                'supplier_id': supplier_id.id
                })
            web_category = self.env['product.public.category'].sudo().create({
                'name': job.result.get('name'),
                'website_description': job.result.get('description'),
                'supplier_id': supplier_id.id
                })
            job.write({
                'mapping_record': category.id,
                'state': 'done'
                })

class ProductPublicCatgoryu(models.Model):
    _inherit = "product.public.category"

    supplier_id = fields.Many2one('supplier.configuration', string="Supplier", readonly=True)