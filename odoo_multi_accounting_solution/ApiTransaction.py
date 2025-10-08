# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo.exceptions import UserError
from logging import getLogger
_logger = getLogger(__name__)

class Transaction:
    def __init__(self, instance_id, *args, **kwargs):
        self.instance_id = instance_id
        self.instance = instance_id.instance
        self.env = instance_id.env
        self.organization_id = instance_id.organization_id

    def import_accounting(self, object , **kwargs)->None:
        if not self.organization_id:
            raise UserError(f"Organization is Mandatory. Please Setup the '{self.instance}' Organization in API Credentials")
        try:
            page = 1
            count, feed_count = 0, 0
            message = ''
            import_type = kwargs.get('import_type', '')
            kwargs['per_page'] = self.instance_id.api_limit
            for page in range(1,int(self.instance_id.page_limit)):
                kwargs.update({'page':page})
                if hasattr(self.instance_id, f'import_{self.instance}_{object}'):
                    kwargs, datalist = getattr(self.instance_id, f'import_{self.instance}_{object}')(**kwargs)
                else:
                    raise UserError(f'Getting {object} is not implemented in {self.instance}')
                if isinstance(datalist, list) and datalist:
                    if object in ['payment_methods']: # create without feeds
                        created_map = self.instance_id.with_context(
                            import_type=import_type
                            ).create_entities_without_feed(object, datalist)
                        count += len(created_map)
                    else:
                        feed_model = self.instance_id.get_feed_model(object)
                        feeds, kwargs = self.env[feed_model].with_context({
                            'instance_id' : self.instance_id,
                            'import_type': import_type,
                        }).create_feeds(datalist, kwargs)
                        count += len(feeds)
                        feed_count += kwargs.get('feed_count', 0)
                else:
                    break
                if kwargs.get('stop') or int(kwargs.get('per_page'))>len(datalist):
                    break
            message_object = self.instance_id.get_message_object(object)
            if object in ['invoices', 'credit_notes']:
                message_object = self.instance_id.get_message_object(kwargs.get('move_type'))
            if count or feed_count:
                if count:
                    message = f"<p class='text-success'>{count} {message_object} imported successfully.</p>"
                if feed_count:
                    message += f"<span class='text-danger'>{feed_count} {message_object} feed not evaluated</span>"
            else:
                if page == 1:
                    message = f"<p class='text-warning'>No Record Found...</p>"
                if kwargs.get('message'):
                    message += f"<br/><span class='text-danger'>{kwargs.get('message')}</span>"
        except Exception as e:
            _logger.error('Error: %r',e, exc_info=True)
            raise UserError(e)
        return self.instance_id.display_message(message)
    
    def export_accounting(self, object, **kwargs)->None:
        if not self.organization_id:
            raise UserError(f"Organization is Mandatory. Please Setup the '{self.instance}' Organization in API Credentials")
        try:
            message_object = self.instance_id.get_message_object(object)
            message = f"Error in Exporting {object}."
            entity_model = self.instance_id.get_entity_model(object)
            mapping_model = self.instance_id.get_mapping_model(object)
            mapped_entities = self.env[mapping_model].search([]).mapped('name')
            if object == "customers":
                odoo_entities = self.env[entity_model].search([('parent_id','=',False)])
            elif object in ['invoices', 'credit_notes']: # Credit Notes & Refunds, Invoices & Bills
                odoo_entities = self.env[entity_model].search([('move_type','in',[kwargs.get('move_type')])])
                message_object = self.instance_id.get_message_object(kwargs.get('move_type'))
            else:
                odoo_entities = self.env[entity_model].search([])
            to_export = odoo_entities - mapped_entities
            remote_ids = list(map(self.instance_id.with_context(object = object).export_entity, to_export))
            exported = list(filter(lambda x: x[0], remote_ids))
            return_messages = '<br/>'.join(list(filter(lambda p: p, [n[-1] for n in remote_ids if n])))
            len_exported = len(exported)
            unexported = len(remote_ids) - len_exported
            if exported:
                message = f'<p class="text-success"> {len_exported} {message_object} exported successfully.</p>'
            if unexported:
                message += f'<p class="text-danger"> {unexported} {message_object} cannot be exported.</p>'
            if not to_export:
                message = f'<p class="text-warning"> No Records to Export in {message_object}.'
            if return_messages:
                message += 'Error: <br/>'+ return_messages
        except Exception as e:
            message = f'Error in Exporting {object} : {e}'
            if self.instance_id.debug:
                _logger.info(message, exc_info=True)
        return self.instance_id.display_message(message)
