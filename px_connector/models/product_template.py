from odoo import api, exceptions, fields, models, _
import logging
import json
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Based configration of Job Queue
    supplier_id = fields.Many2one('supplier.configuration', string="Supplier", readonly=True)
    template_code = fields.Char('Template Code', readonly=True)
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
    can_change_service_type = fields.Boolean(string="Can Change Service Type", copy=False)

    @api.onchange('product_service_type')
    def _onchange_product_service_type(self):
        """
        Prevents changing the product_service_type if can_change_service_type is True.
        Shows a warning and resets the value in the UI.
        """
        if self and self.can_change_service_type:
            # Reset to previous value if not allowed
            if self._origin and self._origin.product_service_type:
                self.product_service_type = self._origin.product_service_type
            return {
                'warning': {
                    'title': 'Not Allowed',
                    'message': 'You are not allowed to change the Service Type for this product.'
                }
            }

    def write(self, vals):
        """
        Prevents changing product_service_type on update if can_change_service_type is True.
        Raises UserError if not allowed.
        """
        if 'product_service_type' in vals:
            for rec in self:
                if rec.can_change_service_type:
                    raise exceptions.UserError('You are not allowed to change the Service Type for this product.')
        return super().write(vals)