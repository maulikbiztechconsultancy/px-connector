# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def send_for_approval(self):
        result = super().send_for_approval()
        # Add description for config-based (PIM) products
        for data in result:
            line = self.env['sale.order.line'].browse(data.get('line_id'))
            if line.printing_line_id:
                desc_parts = []
                # Location
                if line.printing_line_id.location_id:
                    desc_parts.append(f"Location: {line.printing_line_id.location_id.name}")

                # Method(s)
                if line.printing_line_id.color_method_id:
                    desc_parts.append(f"Method: {line.printing_line_id.color_method_id.name}")
                if line.printing_line_id.size_method_id:
                    desc_parts.append(f"Method: {line.printing_line_id.size_method_id.name}")

                # Color / Size
                if line.printing_line_id.color_name:
                    desc_parts.append(f"Color: {line.printing_line_id.color_name}")
                if line.printing_line_id.size_name:
                    desc_parts.append(f"Size: {line.printing_line_id.size_name}")

                if desc_parts:
                    data['printing_product'] = f"{line.product_id.display_name} ({', '.join(desc_parts)})"

        return result
