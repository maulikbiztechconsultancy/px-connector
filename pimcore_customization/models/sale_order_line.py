# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import secrets
import base64
from collections import defaultdict
from itertools import groupby
import imghdr
from odoo.exceptions import  ValidationError, UserError
from odoo.http import request

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    pricelist_id = fields.Many2one(comodel_name='product.pricelist',string="Pricelist")
    parent_line_id = fields.Float("Parent")
    printing_thumbnail = fields.Binary('Printing Image', store=True)
    printing_thumbnail_name = fields.Char(string="Printing File name")
    raw_printing_thumbnail = fields.Binary('Raw Printing Image', store=True)
    # raw_printing_thumbnail_name = fields.Char(string="Raw Printing File name")
    product_service_type = fields.Selection(related="product_id.product_service_type")
    show_cpq = fields.Boolean()
    product_approval_status = fields.Selection([
        ('accept', 'Accept'),
        ('accept_with_change', 'Accept with Changes'),
        ('reject', 'Resend with Comment')], string="Approval Status", copy=False)
    artwork_comment = fields.Text('Artwork Comment', copy=False)
    cost_price = fields.Float("Cost Price")
    cost_order_name = fields.Char("Cost Description")
    order_amount_total = fields.Monetary(
        string='Order Total',
        store=True,
        currency_field='currency_id'
    )
    cpq_bunch = fields.Char(compute="_compute_cpq_bunch", store=True)
    image_128 = fields.Image(string="Image")
    carbon_co2 =  fields.Float(string="CO2")
    carbon_product_uom = fields.Many2one(
        comodel_name='uom.uom',
        string="Carbon Unit of Measure",
        compute='_compute_product_uom_co2',
        store=True, readonly=True, precompute=True, ondelete='restrict',
        domain="[('category_id', '=', product_uom_category_id)]")
    co2_price = fields.Float(
        string="Co2 Unit Price",
        digits='Product Price',
        store=True, readonly=False, precompute=True)
    offer_1 = fields.Float("Offer 1")
    offer_price_1 = fields.Float("Offer 1 Price")
    offer_1_margin_price = fields.Float("Margin Price 1" )
    offer_1_margin_percentage= fields.Float("Offer 1 Margin (%)")
    offer_2 = fields.Float("Offer 2")
    offer_price_2 = fields.Float("Offer 2 Price")
    offer_2_margin_price = fields.Float("Margin Price 2")
    offer_2_margin_percentage= fields.Float("Offer 2 Margin (%)")
    skip_offer_onchange = fields.Boolean('Skip Offer Onchange', default=False)

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty_set_offer(self):
        """When product qty changes, reset offers and recompute based on pricelist."""
        for data in self:
            if (
                data.product_id
                and data.product_id.product_service_type in ['raw_product', 'finished']
                and data.product_id.pricelist_item_count
            ):
                data.offer_1 = 0.0
                data.offer_price_1 = 0.0
                data.offer_1_margin_price = 0.0
                data.offer_1_margin_percentage = 0.0
                data.offer_2 = 0.0
                data.offer_price_2 = 0.0
                data.offer_2_margin_price = 0.0
                data.offer_2_margin_percentage = 0.0
                pricelist_items = self.env['product.pricelist.item'].search([
                    ('product_id', '=', data.product_id.id),
                    ('min_quantity', '>', float(data.product_uom_qty))
                ], limit=2, order='min_quantity asc')
                for idx, pricelist in enumerate(pricelist_items):
                    if idx == 0:
                        data.offer_1 = pricelist.min_quantity
                        data.offer_price_1 = pricelist.fixed_price
                        data._compute_offer_margin(1)
                    else:
                        data.offer_2 = pricelist.min_quantity
                        data.offer_price_2 = pricelist.fixed_price
                        data._compute_offer_margin(2)

    def _compute_offer_margin(self, offer_no):
        """Helper to compute margin price & percentage for given offer (1 or 2)."""
        for data in self:
            if offer_no == 1:
                qty, price = data.offer_1, data.offer_price_1
            else:
                qty, price = data.offer_2, data.offer_price_2
            if qty and price and data.price_unit:
                offer_amount = qty * price
                actual_amount = qty * data.price_unit
                margin_price = (actual_amount - offer_amount) / qty
                margin_percentage = (margin_price * 100) / data.price_unit
            else:
                margin_price = 0.0
                margin_percentage = 0.0
            if offer_no == 1:
                data.offer_1_margin_price = margin_price
                data.offer_1_margin_percentage = margin_percentage
            else:
                data.offer_2_margin_price = margin_price
                data.offer_2_margin_percentage = margin_percentage

    @api.onchange('offer_1', 'offer_price_1', 'offer_2', 'offer_price_2', 'offer_1_margin_percentage', 'offer_2_margin_percentage')
    def onchange_offer_price(self):

        def compute_offer_margin_data(qty, offer_price, price_unit):
            offer_amount = (qty * offer_price) if qty and offer_price else 0.0
            actual_amount = (qty * price_unit) if qty else 0.0
            margin_price = ((actual_amount - offer_amount) / qty) if qty else 0.0
            margin_percentage = ((margin_price * 100) / price_unit) if price_unit else 0.0
            return margin_price, margin_percentage
        for rec in self:
            changed_offer_1 = rec._origin.offer_1 != rec.offer_1 or rec._origin.offer_price_1 != rec.offer_price_1
            changed_offer_2 = rec._origin.offer_2 != rec.offer_2 or rec._origin.offer_price_2 != rec.offer_price_2
            changed_offer_1_margin_percentage = rec._origin.offer_1_margin_percentage != rec.offer_1_margin_percentage
            changed_offer_2_margin_percentage = rec._origin.offer_2_margin_percentage != rec.offer_2_margin_percentage

            if rec.skip_offer_onchange:
                rec.skip_offer_onchange = False
                return

            if changed_offer_1:
                rec.offer_1_margin_price, rec.offer_1_margin_percentage = compute_offer_margin_data(
                    rec.offer_1, rec.offer_price_1, rec.price_unit
                )
            elif changed_offer_1_margin_percentage and rec._origin.offer_1_margin_percentage:
                rec.skip_offer_onchange = True
                new_price =((rec.offer_1_margin_percentage * rec.offer_price_1) / rec._origin.offer_1_margin_percentage)
                rec.offer_price_1 = new_price


            if changed_offer_2:
                rec.offer_2_margin_price, rec.offer_2_margin_percentage = compute_offer_margin_data(
                    rec.offer_2, rec.offer_price_2, rec.price_unit
                )
            elif changed_offer_2_margin_percentage and rec._origin.offer_2_margin_percentage:
                rec.offer_price_2 =((rec.offer_2_margin_percentage * rec.offer_price_2) / rec._origin.offer_2_margin_percentage)

    @api.onchange('product_uom_qty','carbon_co2')
    def _onchange_product_uom_qty(self):
        for line in self:
            if line.product_uom_qty and line.carbon_co2:
                line.co2_price = ((line.carbon_co2 * line.company_id.carbon_co2* line.product_uom_qty)/1000)

    @api.depends('product_id')
    def _compute_product_uom_co2(self):
        for line in self:
            if not line.carbon_product_uom or (line.product_id.uom_id_co2.id != line.carbon_product_uom.id) and line.carbon_co2:
                line.carbon_product_uom = line.product_id.uom_id_co2
                line.carbon_co2 = line.product_id.carbon_co2
                line.co2_price = ((line.carbon_co2 * line.product_uom_qty * line.company_id.carbon_co2 )/1000)

    @api.onchange('product_id')
    def onchange_product_image(self):
        for product in self:
            product.image_128 = product.product_id.image_128

    def _purchase_service_generation(self):
        """
        Create one Purchase Order per Sale Order and Vendor.
        Reuses existing draft PO for the same vendor and Sale Order.
        """
        line_groups = defaultdict(list)

        for line in self:
            if line.display_type or line.purchase_line_ids:
                continue
            if not (line.product_id.service_to_purchase or line.product_id.type in ['product', 'consu']):
                continue

            supplierinfo = line._purchase_service_match_supplier()
            if not supplierinfo:
                continue

            vendor = supplierinfo.partner_id
            key = (line.order_id.id, vendor.id)
            line_groups[key].append((line, supplierinfo))

        for (so_id, vendor_id), grouped_lines in line_groups.items():
            first_line = grouped_lines[0][0]
            company = first_line._purchase_service_get_company()

            # Get or create PO via match_or_create method (ensures PO reuse)
            po = first_line._match_or_create_purchase_order(grouped_lines[0][1])

            # Add lines to PO
            for line, supplierinfo in grouped_lines:
                line = line.with_company(company)
                po_line_vals = line._purchase_service_prepare_line_values(po)
                self.env['purchase.order.line'].create(po_line_vals)

    @api.depends('parent_line_id', 'product_id')
    def _compute_cpq_bunch(self):
        for rec in self:
            if rec.parent_line_id:
                if rec.parent_line_id == 1:
                    section_line = self.search([
                    ('parent_line_id', '=', rec.parent_line_id),
                    ('order_id', '=', rec.order_id.id)
                    ])
                    set_label = True
                    for line in section_line:
                        if set_label:
                            rec.cpq_bunch = f"{line.name} - {line.parent_line_id}"
                            set_label = False

                else:
                    section_line = self.search([
                        ('parent_line_id', '=', rec.parent_line_id),
                        ('display_type', '=', 'line_section'),
                        ('order_id', '=', rec.order_id.id)
                    ])
                    for line in section_line:
                        rec.cpq_bunch = f"{line.name} - {line.parent_line_id}"


    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
            res = super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)
            for sale in res:
                order = sale.get('order_id')
                line_domain = [('cpq_bunch', '=', sale.get('cpq_bunch')), ('display_type', '=','line_section')]
                simple_product = [('cpq_bunch', 'in', [1,False]), ('display_type', '!=','line_section')]

                if len(domain) >= 5:
                    line_domain.append(('order_id', '=', domain[4][2]))
                    simple_product.append(('order_id', '=', domain[4][2]))
                sale_line = self.search(line_domain)
                simple_product_line = self.search(simple_product)

                if 'cpq_bunch' in sale:
                    sale['cost_price'] = False
                    sale['order_amount_total'] = False
                    sale['price_subtotal'] = False
                    sale['margin'] = False

                if sale.get('cpq_bunch') in [1, 1.0, False]:
                    set_label = True
                    for vals in simple_product_line:
                        vals.cost_order_name =  vals.product_id.name
                        sale['cost_order_name'] =  vals.product_id.name
                        sale['cost_price'] = False
                        sale['price_subtotal'] = False
                        sale['margin'] = False
                        if set_label:
                            sale.update({'cpq_bunch': vals.product_id.name})
                            set_label = False

                if 'order_id' in groupby and order:
                    order_record = self.env['sale.order'].browse(order[0])
                    sale['order_amount_total'] = order_record.amount_total
                    sale['cost_price'] = False
                    sale['price_subtotal'] = False
                    sale['margin'] = False
            return res

    @api.onchange('printing_thumbnail','raw_printing_thumbnail')
    def _check_image_format(self):
            allowed_types = ['jpeg', 'png', 'jpg', 'svg']

            for record in self:
                for field_name in ['printing_thumbnail', 'raw_printing_thumbnail']:
                    field_value = getattr(record, field_name)

                    if field_value:
                        try:
                            image_data = base64.b64decode(field_value)
                            img_type = imghdr.what(None, image_data)

                            if not img_type:
                                file_content = image_data[:100].decode(errors="ignore").strip().lower()
                                if "svg" in file_content:
                                    img_type = "svg"

                            if img_type not in allowed_types:
                                raise ValidationError(f"The file uploaded in '{field_name}' is not a valid image. Only JPG, PNG, or SVG are allowed!")

                        except Exception:
                            raise ValidationError(f"The file uploaded in '{field_name}' is not a valid image. Only JPG, PNG, or SVG are allowed!")

    # @api.depends('product_id', 'product_uom', 'product_uom_qty')
    # def _compute_pricelist_item_id(self):
    #         """
    #             This Method first get the all price lists data.
    #             Then filters the price rule that has the lowest price and then applied it to sale order line.
    #             Also it set the related pricelist on the saleorder line.
    #         """
    #         for line in self:
    #             if not line.product_id or line.display_type or not line.order_id.pricelist_id:
    #                 line.pricelist_item_id = False
    #             else:
    #                 data_list = []
    #                 cust_price_lists = self.env['product.pricelist'].search([])
    #                 for pl in cust_price_lists:
    #                     pricelist_item = pl._get_product_rule(line.product_id, quantity=line.product_uom_qty or 1.0,
    #                                                         uom=line.product_uom, date=line.order_id.date_order)
    #                     data_list.append(pricelist_item)
    #                 if all(not x for x in data_list):
    #                     line.pricelist_item_id = not all(not x for x in data_list)
    #                 else:
    #                     filtered_data_list = [item for item in data_list if item is not False]
    #                     cust_product_price_list_items = self.env['product.pricelist.item'].browse(filtered_data_list)
    #                     min_price = min(cust_product_price_list_items.mapped('fixed_price'))
    #                     cust_product_price_list_item_with_min_price = cust_product_price_list_items.filtered(lambda x: x.fixed_price == min_price)[0]
    #                     line.pricelist_item_id = cust_product_price_list_item_with_min_price.id
    #                     line.pricelist_id = cust_product_price_list_item_with_min_price.pricelist_id.id

    @api.model
    def create(self, vals):
        # for vals in vals_list:
        if 'product_service_type' not in vals and vals.get('display_type') != 'line_section' and vals.get('product_id') and not self.env.context.get('cpq'):
            product = self.env['product.product'].browse(vals['product_id'])
            vals['product_service_type'] = product.product_tmpl_id.product_service_type

        order_line = super(SaleOrderLine, self).create(vals)

        # for order_line in order_lines:
        order = order_line.order_id

        if vals.get('display_type') == 'line_section':
            if not order.count_line_incremented:
                order.write({'count_line': order.count_line + 1, 'count_line_incremented': True})
            order.write({'count_line_incremented': False})
        order_line.parent_line_id = order.count_line

        if vals.get('show_cpq') and vals.get('product_service_type') in ['finished', 'raw_product'] and not order_line.is_product_added_from_json:
            order_count = self.sudo().search([
                ('order_id', '=', order_line.order_id.id),
                ('parent_line_id', '=', order.count_line),
                ('display_type', '=', 'line_section')
            ], order='id desc', limit=1)

            order_line.sequence = order_count.sequence + 1 if order_count else 11
            order_line.parent_line_id = order_line.parent_line_id if order_count else 11
            order.count_line = 11 if not order_count else order.count_line
        order_line.image_128 = order_line.product_id.image_128

        if not vals.get('show_cpq'):
            order_line.parent_line_id = 1
            order_line.sequence = 1

        # ---- Calculate Total Quantity for Service Product Line ---- #
        for order in order_line.mapped('order_id'):
                self._update_service_line_qty(order)
        if 'product_uom_qty' in vals and vals.get('product_uom_qty', 0) > 0 and vals.get('product_service_type') in ['raw_product','finished']:
            order_line._onchange_product_uom_qty_set_offer()

        return order_line

    def write(self, vals):
        """Override write method to recalculate service product qty when product quantity is manually updated, preventing recursion."""
        if self.env.context.get('avoid_recursion'):
            return super(SaleOrderLine, self).write(vals)

        res = super(SaleOrderLine, self).write(vals)
        if 'product_uom_qty' in vals:
            for line in self.filtered(lambda x: not x.is_product_added_from_json):
                order = line.order_id
                self.with_context(avoid_recursion=True)._update_service_line_qty(order)

        return res

    @api.model
    def _update_service_line_qty(self, order):
        """Recalculates total quantity for service product lines when any related product quantity changes."""
        section_lines = order.order_line.filtered(lambda l: l.display_type == 'line_section')

        for section in section_lines:
            section_id = section.parent_line_id

            related_lines = order.order_line.filtered(
                lambda l: l.parent_line_id == section_id and l.display_type != 'line_section' and l.product_service_type not in ['printing', 'delivery','extra_charges']
            )
            total_quantity = sum(related_lines.mapped('product_uom_qty'))

            service_lines = order.order_line.filtered(
                lambda l: l.parent_line_id == section_id and l.product_service_type == 'printing'
            )

            for service_line in service_lines:
                if service_line.product_uom_qty != total_quantity:
                    service_line.sudo().write({'product_uom_qty': total_quantity})

    def action_open_wizard(self):
        """
            Helper to Open wizard of Product.
            ----------------------------------
            @param:   self:object pointer
            @return:  Action
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("pimcore_customization.sale_line_info_view_on_wiz_form")
        action['res_id'] = self.id
        return action

    @api.model
    def get_attachments_so(self, res_id):
            """
            Fetch attachment details for a given res_id.

            :param res_id: The resource ID (sale.order.line ID) for which attachments are fetched.
            :return: List of attachments with ID, name, and Base64 data.
            """
            try:
                # Search for image attachments linked to the given res_id

                attachments = self.env['ir.attachment'].search([
                    ('res_id', '=', res_id),
                    ('res_model','=','sale.order.line'),
                    ('res_field','=','printing_thumbnail')
                ])

                # Return a list of dictionaries with attachment details
                result = [
                    {
                        'id': attachment.id,
                        'name': attachment.name or f"attachment_{attachment.id}.png",
                        'datas': attachment.datas , # Base64 encoded data
                        'mimetype':attachment.mimetype
                    }
                    for attachment in attachments
                ]

                return result
            except Exception as e:
                raise e

class SaleOrder(models.Model):
    _inherit = "sale.order"

    count_line =  fields.Float(default=10.00)
    count_line_incremented = fields.Boolean(default=False)

    state = fields.Selection(
        selection_add=[
            ("approved", "Approved"),
            ("sale",)
        ],
        tracking=3
    )
    artwork_page_url = fields.Char('Artwork Page URL', copy=False)
    is_artwork_proofing_setting = fields.Boolean(
        related="company_id.is_artwork_proofing", 
        store=True
    )
    is_artwork_proofing_amount_setting = fields.Float(
        related="company_id.approval_amount",
        store=True
    )
    artwork_approval = fields.Integer(related="company_id.artwork_approval",store=True)
    count_for_approved_cycle_complete =  fields.Integer(copy=False)
    price_co2_total = fields.Monetary(
        string="Total co2",
        compute='_compute_co2_amount',
        store=True, precompute=True)
    delivered_to = fields.Selection([('by_supplier','By Supplier'),('by_premier','By Premier')],string="End Delivered",copy="False")

    @api.depends('order_line.product_uom_qty', 'currency_id', 'company_id')
    def _compute_co2_amount(self):
        for order in self:
            price_co2 = 0
            for line in order.order_line:
                price_co2 +=line.co2_price
            order.price_co2_total = price_co2

    def _get_purchase_orders(self):
        for order_line in self.order_line:
            found = False

            for mrp in order_line.order_id.mrp_production_ids:
                if mrp.product_id == order_line.product_id:
                    order_line.cost_order_name = mrp.name + ' - ' + mrp.product_id.display_name
                    total_cost = 0.0
                    for bom in mrp.bom_id.bom_line_ids:
                        total_cost += bom.product_id.standard_price * bom.product_qty * -1
                    order_line.cost_price = total_cost
                    found = True

            if not found and order_line.purchase_line_ids:
                purchase_line = order_line.purchase_line_ids[0]
                order_line.cost_order_name = purchase_line.order_id.name + ' - ' + purchase_line.display_name
                order_line.cost_price = purchase_line.price_subtotal * -1
                found = True

            elif not found:
                for move in self.procurement_group_id.stock_move_ids:
                    for purchase_line in move.created_purchase_line_ids:
                        if purchase_line.product_id == order_line.product_id:
                            order_line.cost_order_name = purchase_line.order_id.name + ' - ' + purchase_line.display_name
                            order_line.cost_price = purchase_line.price_subtotal * -1
                            found = True

            if not found:
                order_line.cost_order_name = order_line.product_id.display_name
                order_line.cost_price = order_line.product_id.standard_price * order_line.product_uom_qty * -1

        return super()._get_purchase_orders()

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)

        for order in self:
            # Fetch all 'line_section' type lines in order sequence
            section_lines = order.order_line.filtered(lambda line: line.display_type == 'line_section').sorted('sequence')

            if section_lines:
                first_section = section_lines[0]  # Identify the first section
                first_section_lines = []

                # Get all lines under the first section
                found_first_section = False
                for line in order.order_line.sorted('sequence'):
                    if line == first_section:
                        found_first_section = True
                        continue  # Skip the first section header itself

                    if found_first_section:
                        if line.display_type == 'line_section':
                            break  # Stop when the second section starts
                        first_section_lines.append(line)

                # Check if all lines in the first section are saved in DB
                if first_section_lines and all(line.id for line in first_section_lines):
                    if order.count_line == 10:  # Set to 11 only if it's not already
                        order.sudo().write({'count_line': 11})

        return res

    def copy(self, default=None):
        default = dict(default or {})
        new_order = super(SaleOrder, self).copy(default=default)
        # Ensure order_line is not empty
        if new_order.order_line:
            for index, line in enumerate(new_order.order_line.sorted('id'), start=1):
                line.sequence = index
        return new_order

    def get_grouped_lines(sale_order):
        grouped_lines = defaultdict(list)
        for line in sale_order.order_line:
            if line.display_type != 'line_section' and line.product_id.product_service_type != 'delivery':
                grouped_lines[line.product_id.product_service_type].append(line)
        return grouped_lines

    def add_section_and_product(self, product_line_vals, max_sequence):
        """ Add a section and product lines to the sale order. """
        new_lines = []

        product_template_id = self.env['product.template'].browse(product_line_vals.get('product_template_id'))

        section_line = {
            'display_type': 'line_section',
            'order_id': self.id,
            'name': product_template_id.name if product_template_id else "Section",
            'sequence': max_sequence if max_sequence !=1 else 2,
            'product_id': False,  # No product for section
            'product_uom_qty': 0,
            'price_unit': 0,
            'product_uom': False,
            'show_cpq':True,
        }
        new_lines.append((0, 0, section_line))
        max_sequence += 1 if max_sequence !=1 else 2

        product_line_vals['sequence'] = max_sequence

        return new_lines, max_sequence

    def generate_artwork_page_url(self):
        token = secrets.token_urlsafe()
        query_string = str({
            'order_id': self.id,
            'required_approval': True,
            'token': token
        })
        encodedBytes = base64.b64encode(query_string.encode("utf-8"))
        encoded_query_string = str(encodedBytes, "utf-8")
        self.artwork_page_url = '/shop/order_artwork/?value=' + encoded_query_string

    def action_send_proofing(self):
        if self.state == 'sale':
            raise ValidationError(_('Your order has been confirmed. Please refresh the page to see the latest updates.'))

        if not self.is_artwork_proofing_setting:
            return
        company = self.env.company
        if company.artwork_approval >= 0 and company.approval_amount >= 0:
            if self.amount_total == 0 or self.amount_total >= company.approval_amount:
                template_id = self.env.ref('pimcore_customization.email_template_confirmation_artwork_files').id
                self.generate_artwork_page_url()
                ctx = {
                    'default_model': 'sale.order',
                    'default_res_ids': self.ids,
                    'default_use_template': bool(template_id),
                    'default_template_id': template_id,
                    'default_composition_mode': 'comment',
                    'custom_layout': 'mail.mail_notification_light',
                    'send_proofing':True,
                    'update_from_magento' : True
                }
                return {
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'mail.compose.message',
                    'target': 'new',
                    'context': ctx,
                }

    @api.model          
    def data_simplify_mail_template(self):
        new_lst = []
        for data in self.order_line:
            new_lst.append({
                'parent_line_id': data.parent_line_id,
                'line_id': data.id,
                'product_service_type': data.product_service_type,
                'product_approval_status': data.product_approval_status
            })
        data_sorted = sorted(new_lst, key=lambda x: x['parent_line_id'])
        grouped_data = groupby(data_sorted, key=lambda x: x['parent_line_id'])
        processed_data = []
        for parent_line_id, group in grouped_data:
            group_list = list(group)
            processed_data.append({
                'parent_line_id': parent_line_id,
                'order_id': self.id,
                'lines': group_list
            })
        return processed_data

    def send_for_approval(self):
        processed_data = []
        for order in self:
            order_lines = order.order_line.sorted('sequence')  # make sure they are in order
            idx = 0
            while idx < len(order_lines):
                line = order_lines[idx]
                if line.display_type == 'line_section':
                    section_lines = []
                    idx += 1
                    while idx < len(order_lines) and order_lines[idx].display_type != 'line_section':
                        section_lines.append(order_lines[idx])
                        idx += 1
                    main_lines = [l for l in section_lines if l.product_service_type in ['finished','raw_product']]
                    printing_lines = [l for l in section_lines if l.product_service_type == 'printing' and (l.product_approval_status == 'reject' or not l.product_approval_status)]
                    main = main_lines[0] if main_lines else False
                    for p in printing_lines:
                        processed_data.append({
                            'order_id': order.id,
                            'main_line_id': main.id if main else False,
                            'main_product': main.product_id.name if main else '',
                            'line_id': p.id,
                            'printing_product': p.product_id.display_name,
                            'approval_status': p.product_approval_status
                        })
                else:
                    idx += 1

        return processed_data

    def _confirmation_error_message(self):
        self.ensure_one()
        if self.state not in {'draft', 'sent','approved'}:
            return _("Some orders are not in a state requiring confirmation.")

        return False

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()

        for sale in self:
            dropship_type = self.env['stock.picking.type'].search([('code', '=', 'dropship')], limit=1)
            new_lines = []
            purchase_orders = sale._get_purchase_orders()
            simple_pos = purchase_orders.filtered(lambda po: self._is_simple_po(po))
            simple_printing_pos = purchase_orders.filtered(lambda po: self._is_simple_printing_po(po)).sorted('id')
            printing_pos = purchase_orders.filtered(lambda po: self._is_printing_po(po)).sorted('id')

            if sale.delivered_to == 'by_premier':
                StockPicking = self.env['stock.picking']
                StockMove = self.env['stock.move']
                picking_type = self.env.ref('stock.picking_type_out')  
                picking = StockPicking.create({
                    'partner_id':self.env.company.partner_id.id if sale.delivered_to == 'by_premier' else False,
                    'picking_type_id': picking_type.id,
                    'location_id': picking_type.default_location_src_id.id,
                    'location_dest_id': sale.partner_shipping_id.property_stock_customer.id,
                    'origin': sale.name,
                    'sale_id': sale.id,
                }) 
                order_lines = sale.order_line.filtered(lambda l: l.display_type != 'line_section' and l.product_service_type =='finished')
                for line in order_lines:
                    StockMove.create({
                        'name': line.name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'picking_id': picking.id,
                        'location_id': picking.location_id.id,
                        'location_dest_id': picking.location_dest_id.id,
                        'sale_line_id': line.id,
                    })

            if simple_pos:
                target_dest_address_id = False  # Set a default to avoid UnboundLocalError
                if simple_printing_pos:
                    target_dest_address_id = simple_printing_pos[0].partner_id.id
                elif printing_pos:
                    target_dest_address_id = printing_pos[0].partner_id.id

                if target_dest_address_id:
                    for po in simple_pos:
                        po.write({'dest_address_id': target_dest_address_id})

            for idx, po in enumerate(simple_printing_pos):
                if idx < len(simple_printing_pos) - 1:
                    next_po = simple_printing_pos[idx + 1]
                    po.write({'dest_address_id': next_po.partner_id.id})


                else:
                    # Last one — fallback to printing or SO address
                    fallback_id = (
                        printing_pos[0].partner_id.id if printing_pos else
                        sale.partner_id.id
                    )
                    po.write({'dest_address_id': sale.company_id.partner_id.id if sale.delivered_to == 'by_premier' else fallback_id,'picking_type_id':dropship_type })
            for idx, po in enumerate(printing_pos):
                if idx < len(printing_pos) - 1:
                    next_po = printing_pos[idx + 1]
                    po.write({'dest_address_id': next_po.partner_id.id,'picking_type_id':dropship_type})

                else:
                    po.write({'dest_address_id': sale.company_id.partner_id.id if sale.delivered_to == 'by_premier' else sale.partner_id.id,'picking_type_id':dropship_type })
        template = request.env.ref(
            'pimcore_customization.email_template_sale_order_confirm')
        if template:
            template.sudo().send_mail(sale.id, force_send=True)
            body_html = template._render_field('body_html', [sale.id])[sale.id]
            sale.message_post(body=body_html,subject=template.subject,message_type='comment',subtype_xmlid='mail.mt_note',)
        return res

    def _is_simple_po(self, po):
        product_types = po.order_line.filtered(
            lambda line: line.product_id.product_service_type != 'delivery'
        ).mapped('product_id.product_service_type')
        return all(pt in ['finished', 'raw_product'] for pt in product_types)

    def _is_simple_printing_po(self, po):
        product_types = po.order_line.filtered(
            lambda line: line.product_id.product_service_type != 'delivery'
        ).mapped('product_id.product_service_type')
        has_supplier = any(pt == 'finished' for pt in product_types)
        has_service = any(pt == 'printing' for pt in product_types)
        return len(product_types) >= 2 and has_supplier and has_service

    def _is_printing_po(self, po):
        product_types = po.order_line.mapped('product_id.product_service_type')
        return all(pt == 'printing' for pt in product_types)

    def get_report_quotation_data(self):
        processed_data = []
        for order in self:
            order_lines = order.order_line.sorted('sequence')  # make sure they are in order
            idx = 0
            while idx < len(order_lines):
                line = order_lines[idx]
                if line.display_type == 'line_section':
                    section_lines = []
                    idx += 1
                    while idx < len(order_lines) and order_lines[idx].display_type != 'line_section':
                        section_lines.append(order_lines[idx])
                        idx += 1
                    main_lines = [l for l in section_lines if l.product_service_type in ['finished','raw_product']]
                    delivery_lines = [l for l in section_lines if l.product_service_type in ['delivery']]
                    for i, main in enumerate(main_lines):
                        delivery = delivery_lines[i] if i < len(delivery_lines) else None

                        offer_amount_1 = (main.offer_1 * main.offer_price_1) if main.offer_1 and main.offer_price_1 else 'Nil'
                        offer_amount_2 = (main.offer_2 * main.offer_price_2) if main.offer_2 and main.offer_price_2 else 'Nil'

                        delivery_charge = delivery.price_unit if delivery and delivery.price_unit else 0.0
                        total_print_amount = sum(l.price_unit for l in section_lines if l.product_service_type == 'printing' and l.parent_line_id == main.parent_line_id)
                        printing_product_names_str = ", ".join(l.product_id.display_name for l in section_lines if l.product_service_type == 'printing' and l.parent_line_id == main.parent_line_id)
                        total_delivery_amount = sum(l.price_unit for l in section_lines if l.product_service_type == 'delivery' and l.parent_line_id == main.parent_line_id)
                        total_extra_amount = sum(l.price_unit for l in section_lines if l.product_service_type == 'extra_charges' and l.parent_line_id == main.parent_line_id)
                        print_qty = next((l.product_uom_qty for l in section_lines if l.product_service_type == 'printing' and l.parent_line_id == main.parent_line_id),0)
                        price_unit = main.price_unit + total_print_amount
                        if print_qty:
                            price_unit += (total_extra_amount / print_qty) + (total_delivery_amount / print_qty)
                        processed_data.append({
                            'main_line_id': main.id,
                            'product_name': main.product_id.display_name,
                            'product_image': main.product_id.image_1920,
                            'product_description': main.product_id.description,
                            'lead_time': main.product_id.sale_delay,
                            'product_code': main.product_id.default_code,
                            'product_uom_qty': main.product_uom_qty,
                            'delivery_charge': delivery_charge,
                            'price_unit': price_unit,
                            'price_subtotal': (round(price_unit, 2) * main.product_uom_qty),
                            'offer_1': main.offer_1 or 0.0,
                            'offer_price_1': main.offer_price_1 or 0.0,
                            'offer_amount_1': offer_amount_1,
                            'actual_amount_offer_1': main.offer_1_margin_price,
                            'offer_2': main.offer_2 or 0.0,
                            'offer_price_2': main.offer_price_2 or 0.0,
                            'offer_amount_2': offer_amount_2,
                            'actual_amount_offer_2': main.offer_2_margin_price,
                            'carbon_co2': main.carbon_co2 or 0.0,
                            'carbon_total': (main.carbon_co2 * main.product_uom_qty) if main.carbon_co2 else 0.0,
                            'offset_total': main.co2_price or 0.0,
                            'setup_charge':main.product_id.setup_charge or 0.0,
                            'printing_product_names':printing_product_names_str,
                        })
                else:
                    idx += 1
        return processed_data

class MailMesage(models.TransientModel):
    _inherit = "mail.compose.message"

    def action_send_mail(self):
        res = super(MailMesage,self).action_send_mail()
        active_id = self.env.context.get("active_id")
        model = self.env.context.get("default_model")
        if active_id and model == "sale.order" and self.env.context.get("send_proofing"):
            order_id = self.env['sale.order'].search([('id','=',active_id)])
            order_id.count_for_approved_cycle_complete += 1
            if order_id.count_for_approved_cycle_complete == order_id.company_id.artwork_approval  or all(line.product_approval_status in ['accept','accept_with_change']  for line in order_id.order_line.filtered(lambda x: x.product_service_type == 'printing')):
                order_id.state = 'approved'
                if order_id.state == 'approved':
                    template_approved = request.env.ref('pimcore_customization.email_template_sale_order_approved')
                    template_approved.sudo().send_mail(order_id.id, True)
        return res

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _make_po_get_domain(self, company, values, partner):
        """
        Override to force new PO creation always.
        Returning an empty domain ensures no existing PO is reused.
        Only applies to sale order triggered POs (optional check below).
        """
        origin = values.get('origin', '')
        if origin.startswith('SO'):  # Optional: only apply to Sale Orders
            return [('id', '=', 0)]  # Always returns no existing PO
        return super()._make_po_get_domain(company, values, partner)