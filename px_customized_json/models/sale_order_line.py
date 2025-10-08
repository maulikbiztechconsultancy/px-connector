# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_product_added_from_json = fields.Boolean(copy=False)
    parent_sale_line_id = fields.Many2one('sale.order.line', copy=False)
    printing_line_id = fields.Many2one('printing.colors.and.sizes', copy=False)
    delivery_line_id = fields.Many2one('shipping.products', copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            payloads = [vals_list]
            return_single = True
        else:
            payloads = list(vals_list)
            return_single = False

        cleaned_payloads = []
        for vals in payloads:
            if not vals.get('name'):
                product_id = vals.get('product_id')
                if product_id:
                    product = self.env['product.product'].browse(product_id)
                    # Only set from product; do not add any placeholder
                    vals['name'] = product.display_name or product.name
                else:
                    # Skip unintended nameless, non-product lines to avoid creating extra blank lines
                    # Keep explicit section lines (they have display_type and a name set upstream)
                    # Any other nameless non-product line is ignored
                    continue
            cleaned_payloads.append(vals)

        if not cleaned_payloads:
            return self.browse()

        records = super().create(cleaned_payloads)
        return records[0] if return_single else records

    def _purchase_service_get_price_unit_and_taxes(self, supplierinfo, purchase_order):
        """Odoo 18 service→purchase: set PO price from SO purchase_price when available."""
        # Added by Radhika: Use custom purchase_price instead of supplier pricing for JSON-added products
        # and convert to vendor currency
        self.ensure_one()
        price_unit, taxes = super()._purchase_service_get_price_unit_and_taxes(supplierinfo, purchase_order)
        if self.purchase_price and purchase_order:
            price_unit = self.purchase_price

            # Convert from sale order currency to vendor/PO currency
            sale_currency = self.order_id.currency_id
            po_currency = purchase_order.currency_id

            if sale_currency and po_currency and sale_currency != po_currency:
                try:
                    price_unit = sale_currency._convert(
                        price_unit,
                        po_currency,
                        purchase_order.company_id,
                        purchase_order.date_order or fields.Date.context_today(self)
                    )
                except Exception:
                    pass
        return price_unit, taxes

    @api.depends('product_id', 'company_id', 'currency_id', 'product_uom')
    def _compute_purchase_price(self):
        # Added by Radhika: Skip default purchase_price computation for custom pricing lines to preserve tier-based costs
        lines_to_super = self.browse()
        for line in self:
            if getattr(line, 'show_cpq', False):
                # For CPQ/JSON products, check if it's a raw product and force to 0
                if (getattr(line, 'is_product_added_from_json', False) and not line.printing_line_id and not line.delivery_line_id and not line.parent_sale_line_id):
                    line.purchase_price = 0.0
                else:
                    line.purchase_price = line.purchase_price or 0.0
            else:
                lines_to_super |= line

        if lines_to_super:
            super(SaleOrderLine, lines_to_super)._compute_purchase_price()

    def write(self, vals):
        # Added by Radhika: Prevent quantity reset issue when writing changes to sales order lines
        if self.env.context.get('avoid_recursion'):
            return super().write(vals)

        res = super().write(vals)

        # Only sync related service line quantities if this is not a direct quantity change
        if 'product_uom_qty' in vals and not self.env.context.get('skip_quantity_sync'):
            for line in self.filtered(lambda x: x.is_product_added_from_json):
                line.with_context(avoid_recursion=True)._update_for_json_service_line_qty(line.order_id)
        return res

    def _update_for_json_service_line_qty(self, order):
        for raw_sale_line in order.order_line.filtered(lambda l: l.is_product_added_from_json and not l.parent_sale_line_id):
            related_service_lines = order.order_line.filtered(
                lambda l: l.parent_sale_line_id == raw_sale_line and l.product_service_type not in ['delivery', 'extra_charges']
            )
            related_service_lines.with_context(avoid_recursion=True).sudo().write({
                'product_uom_qty': raw_sale_line.product_uom_qty
            })

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        # Added by Radhika: Tier-based purchase_price calculation and margin application for unit_price computation
        # Applies to lines with printing_line_id, delivery_line_id, or setup charges; otherwise uses Odoo's base flow
        res = super()._compute_price_unit()
        for line in self:
            # Skip display lines
            if line.display_type:
                continue

            # Skip raw products (those without printing/delivery line IDs or setup charges)
            if not (line.printing_line_id or line.delivery_line_id or (line.product_id.product_service_type == 'extra_charges' and line.parent_sale_line_id)):
                continue

            # Determine which tier pricing to use
            tier_records = None
            pim_config = None
            if line.printing_line_id and line.printing_line_id.qty_price_ids:
                tier_records = line.printing_line_id.qty_price_ids
                pim_config = line.product_template_id.pim_config_id
            elif line.delivery_line_id and line.delivery_line_id.qty_price_ids:
                tier_records = line.delivery_line_id.qty_price_ids
                pim_config = line.product_template_id.pim_config_id
            elif (line.product_id.product_service_type == 'extra_charges' and
                  line.parent_sale_line_id):
                # For setup charges, find the printing line that belongs to the same parent
                printing_line = self.env['sale.order.line'].search([
                    ('parent_sale_line_id', '=', line.parent_sale_line_id.id),
                    ('printing_line_id', '!=', False)
                ], limit=1)

                if printing_line and printing_line.printing_line_id and printing_line.printing_line_id.setup_charge:
                    # Use the printing line's setup_charge as tier record
                    tier_records = [printing_line.printing_line_id]
                    pim_config = line.parent_sale_line_id.product_template_id.pim_config_id

            if not tier_records or not pim_config:
                continue

            # Calculate tier-based purchase price with currency conversion
            calculated_purchase_price = line._get_converted_tier_price(
                tier_records,
                line.product_uom_qty,
                line.order_id,
                pim_config
            )

            if calculated_purchase_price:
                line.purchase_price = calculated_purchase_price
                # Apply margin to calculate selling price
                margin_percent = float(pim_config.sale_margin or 0.0)
                line.price_unit = calculated_purchase_price * (1 + margin_percent / 100.0)
        return res

    @api.model
    def _get_converted_tier_price(self, tiers, qty, order, pim_config):
        # Added by Radhika: Tier quantity-based pricing with currency conversion for purchase_price calculation
        if not tiers:
            return 0.0

        # Handle single tier record - always use it
        if len(tiers) == 1:
            selected = tiers[0]
            # Check if it's a printing line with setup_charge (not a qty_price record)
            if hasattr(selected, 'setup_charge') and selected.setup_charge:
                price = selected.setup_charge or 0.0
            else:
                price = selected.price or 0.0
        else:
            # Multiple tiers - find the appropriate one
            # Find tiers where quantity is <= requested qty (for tier pricing)
            applicable_tiers = tiers.filtered(lambda r: r.quantity <= qty)

            if applicable_tiers:
                # Get the tier with highest quantity from those <= requested qty
                selected = sorted(applicable_tiers, key=lambda r: r.quantity)[-1]
            else:
                # If no tier applies, get the one with lowest quantity
                selected = sorted(tiers, key=lambda r: r.quantity)[0]

            price = selected.price or 0.0
        # Apply currency conversion if needed - ALWAYS convert when currencies differ
        pim_currency = getattr(pim_config, 'currency_id', None)
        order_currency = getattr(order, 'currency_id', None)
        if pim_currency and order_currency and pim_currency != order_currency:
            try:
                price = pim_currency._convert(
                    price,
                    order_currency,
                    order.company_id,
                    order.date_order or fields.Date.context_today(self),
                )
            except Exception:
                # If conversion fails, keep original price
                pass
        return price
