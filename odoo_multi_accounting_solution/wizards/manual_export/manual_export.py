# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models
import logging
_logger = logging.getLogger(__name__)


class ManualExportWizard(models.TransientModel):
    _name = "omas.manual.export"
    _description = 'Manual Export'
    _inherit = 'omas.export.operation'

    def manual_export_entity(self, instance_id, object, record):
        status = False
        exported, remote_id, message = instance_id.with_context(object=object).export_entity(record)
        if exported and remote_id:
            status = True
        return status, message

    def manual_export_button(self):
        message = ""
        error_message = ""
        instance_id = self.instance_id
        active_ids = self._context.get('active_ids')
        model = self._context.get('active_model')
        object = self.get_model_object_mapping(model)
        mapped_entities = self.env[instance_id.get_mapping_model(object)].search(
            [('instance_id','=', instance_id.id),('name', 'in', active_ids)]).mapped('name')
        if model == "res.partner":
            odoo_entities = self.env[model].search(
                [('id', 'in', active_ids)])
        else:
            odoo_entities = self.env[model].search([('id', 'in', active_ids)])
        to_export = odoo_entities - mapped_entities
        message_object = instance_id.get_message_object(object)
        if mapped_entities:
            message += f'<p class="text-info">{len(mapped_entities.ids)} Records are already mapped {mapped_entities.ids}'
        if to_export:
            success_ids, error_ids = [], []
            for record in to_export:
                success_ids, error_ids, message_object, error_message = self.manual_export_operation(
                    record, object, success_ids, error_ids, error_message)
            if success_ids:
                message += f'<p class="text-success"> {len(success_ids)} {message_object} Success ids {success_ids}</p>'
            if error_ids:
                message += f'<p class="text-danger">{len(error_ids)} {message_object} Error ids: {error_ids}</p>'
        else:
            message += f'<p class="text-warning"> No Records to Export in {message_object}.'
        if error_message:
            message += "Errors: <br/>"+error_message
        return self.instance_id.display_message(message)

    def manual_export_operation(self, record, object, success_ids, error_ids, error_message=''):
        instance_id = self.instance_id
        message_object = instance_id.get_message_object(object)
        if record._name == "account.move":
            if record.move_type in ['out_refund', 'in_refund']:
                object = 'credit_notes'
            else:
                object = 'invoices'
            message_object = instance_id.get_message_object(record.move_type)
        return_data = self.manual_export_entity(
            instance_id, object, record)
        success_ids.append(
            record.id) if return_data[0] else error_ids.append(record.id)
        if return_data[1]:
            error_message += '<br/>'+return_data[1]
        return success_ids, error_ids, message_object, error_message

    def get_model_object_mapping(self, entity_model):
        model_object_mapping = {
            'product.template': 'templates',
            'account.account': 'accounts',
            'res.partner': 'customers',
            'sale.order': 'orders',
            'account.payment': 'payments',
            'account.move': 'invoices',
            'purchase.order':'purchase_orders'
        }
        return model_object_mapping[entity_model]
