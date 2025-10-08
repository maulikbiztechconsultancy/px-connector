# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from datetime import date, datetime, timedelta
import logging
_logger = logging.getLogger(__name__)
from odoo.http import request
from odoo import http

class OMASControllers(http.Controller):

    @http.route('/omas',type='http',auth='public', website=True)
    def create_connection(self,*args,**kwargs):
        instance_id = request.session.get('instance_id')
        record = request.env['omas'].browse(instance_id)
        if record:
            record.authorization_token = kwargs.get('code')
            record.with_context(authorization=True).create_online_connection()
        action_id = request.env.ref('odoo_multi_accounting_solution.omas_action').id
        url = f"/web#id={record.id}&action={action_id}&model=omas&view_type=form"
        return request.redirect(url)
    
    @http.route('/omas/fetch_dashboard_data', type='json', auth='user')
    def fetch_dashboard_data(self, *args, **kwargs):
        entities = ['order', 'invoice', 'product','partner']
        data = self._get_panel_data()
        for entity in entities:
            data[entity] = getattr(self, f'_get_{entity}_dashboard_data')()
        data.update(instance_id = self._get_instance_id())
        return data


    @http.route('/omas/fetch_top_revenue', type='json', auth='user')
    def fetch_top_revenue(self, *args, **kwargs):
        size = int(kwargs.get('table_size'))
        interval = kwargs.get('interval')
        where_clause = 'WHERE'
        if not interval == 'all':
            where_clause = f"WHERE o.create_date >= NOW() - interval '{interval} month' AND"
        data, query = [], False
        if kwargs.get('selected_option') == 'all mapped':
            if kwargs.get('selected_obj') == 'order':
                query = f"""SELECT o.id, o.name as name, r.name as customer, to_char(o.create_date, 'DD-MM-YYYY') as date, 
                    o.amount_total as total, o.state FROM omas_order_mapping m 
                    LEFT JOIN sale_order o ON m.odoo_order_id = o.id 
                    LEFT JOIN res_partner r ON o.partner_id = r.id
                    {where_clause} o.state NOT IN ('cancel') ORDER BY o.amount_total DESC LIMIT {size}
                """
            elif kwargs.get('selected_obj') == 'product':
                product_ids = request.env['omas.product.mapping'].search([]).mapped('name')
                return self.get_best_selling_product(product_ids, interval, size)
        else:
            if kwargs.get('selected_obj') == 'order':
                query = f"""SELECT o.id, o.name as name, r.name as customer, to_char(o.create_date, 'DD-MM-YYYY') as date, 
                        o.amount_total as total, o.state FROM sale_order o
                        LEFT JOIN res_partner r ON o.partner_id = r.id
                        {where_clause} state NOT IN ('cancel') ORDER BY amount_total DESC LIMIT {size}
                        """
            elif kwargs.get('selected_obj') == 'product':
                product_ids = request.env['product.product'].search([])
                return self.get_best_selling_product(product_ids, interval, size)
        if query:
            data = self._get_query_result(query)
        return data
        
    def get_best_selling_product(self, product_ids, interval, size):
        data = []
        if product_ids:
            domain = [
                ('state', 'in', ['sale']),
                ('product_id', 'in', product_ids.ids),
            ]
            if not interval == 'all':
                deltatime =  timedelta(days=30) if interval == '1' else  timedelta(days=365)
                create_date = datetime.now() - deltatime
                domain += [('date', '>=', create_date)]
            data = request.env['sale.report'].sudo()._read_group(
                domain,
                groupby=['product_id'],
                aggregates=['product_uom_qty:sum', 'price_subtotal:sum'],
                order="product_uom_qty:max DESC",
                limit=size,
                )
            if data:
                data = list({'id':x.id,'name': x.name, 'count': y, 'revenue': round(z,2), 'date': x.create_date.date()} 
                            for x, y, z in data[:size])
        return data

    def _get_instance_id(self):
        return request.env['omas'].search([
            ('is_connected', '=', 'True'),
            ('active','=', 'True')
        ]).mapped('id')
    
    @http.route('/omas/fetch_order_data', type='json', auth='user')
    def fetch_order_data(self, *args, **kwargs):
        interval = kwargs.get('interval')
        chart = kwargs.get('chart')
        if chart in ['donut']:
            query = f"""SELECT o.amount_total as total, o.name FROM sale_order o
                WHERE o.create_date >= NOW() - interval '{interval} day' ORDER BY o.amount_total DESC LIMIT 5"""
            query_data = self._get_query_result(query)
            data = self._get_donut_pie_chart_data('order', query_data)
        elif chart == 'pie':
            query = f"""SELECT o.amount_total as total, o.name FROM omas_order_mapping m LEFT JOIN sale_order o ON m.odoo_order_id = o.id 
                WHERE o.create_date >= NOW() - interval '{interval}' day ORDER BY o.amount_total DESC LIMIT 5"""       
            query_data = self._get_query_result(query)
            data = self._get_donut_pie_chart_data('order', query_data)
        elif chart == 'bar':
            if interval == 7: # Days
                query = f"""SELECT to_char(o.create_date, 'Dy') as month, count(o.state) FROM omas_order_mapping m LEFT JOIN sale_order o ON m.odoo_order_id = o.id
                    WHERE o.create_date >= NOW() - interval '{interval} Day' GROUP BY 1 ORDER BY 1"""
            else: # Months
                query = f"""SELECT to_char(o.create_date, 'Mon') as month, count(o.state) FROM omas_order_mapping m LEFT JOIN sale_order o ON m.odoo_order_id = o.id
                    WHERE o.create_date >= NOW() - interval '{interval} month' GROUP BY 1 ORDER BY 1"""
            query_data = self._get_query_result(query)
            data = self._get_bar_chart_data(interval, query_data)
        elif chart in ['line', 'line2']:
            if interval == 7:
                query = f"""
                    SELECT to_char(o.create_date, 'Dy') as day, count(o.state) as total FROM omas_order_mapping m LEFT JOIN sale_order o ON m.odoo_order_id = o.id 
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            elif interval == 30:
                query = f"""
                    SELECT cast(ROUND(EXTRACT('Day' FROM o.create_date)) as int) as day, count(o.state) as total FROM omas_order_mapping m LEFT JOIN sale_order o ON m.odoo_order_id = o.id 
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            else:
                query = f"""
                    SELECT to_char(o.create_date, 'Mon') as day, count(o.state) as total FROM omas_order_mapping m LEFT JOIN sale_order o ON m.odoo_order_id = o.id 
                    WHERE o.create_date >= now() - interval '{interval} month' GROUP BY 1 ORDER BY 1 
                """
            query_data = self._get_query_result(query)
            data = self._get_line_chart_data(interval, query_data)
        return data

    @http.route('/omas/fetch_purchase_data', type='json', auth='user')
    def fetch_purchase_data(self, *args, **kwargs):
        interval = kwargs.get('interval')
        chart = kwargs.get('chart')
        if chart in ['donut']:
            query = f"""SELECT o.amount_total as total, o.name FROM purchase_order o
                WHERE o.create_date >= NOW() - interval '{interval} day' ORDER BY o.amount_total DESC LIMIT 5"""
            query_data = self._get_query_result(query)
            data = self._get_donut_pie_chart_data('purchase', query_data)
        elif chart == 'pie':
            query = f"""SELECT o.amount_total as total, o.name FROM omas_purchase_order_mapping m LEFT JOIN purchase_order o ON m.odoo_purchase_order_id = o.id 
                WHERE o.create_date >= NOW() - interval '{interval} day' ORDER BY o.amount_total DESC LIMIT 5"""
            query_data = self._get_query_result(query)
            data = self._get_donut_pie_chart_data('purchase', query_data)
        elif chart == 'bar':
            if interval == 7:
                query = f"""SELECT to_char(o.create_date, 'Dy') as month, count(o.state) FROM omas_purchase_order_mapping m LEFT JOIN purchase_order o ON m.odoo_purchase_order_id = o.id
                    WHERE o.create_date >= NOW() - interval '{interval} day' GROUP BY 1 ORDER BY 1"""
            else:
                query = f"""SELECT to_char(o.create_date, 'Mon') as month, count(o.state) FROM omas_purchase_order_mapping m LEFT JOIN purchase_order o ON m.odoo_purchase_order_id = o.id
                    WHERE o.create_date >= NOW() - interval '{interval} month' GROUP BY 1 ORDER BY 1"""
            query_data = self._get_query_result(query)
            data = self._get_bar_chart_data(interval, query_data)
        elif chart == 'line':
            if interval == 7:
                query = f"""
                    SELECT to_char(o.create_date, 'Dy') as day, count(o.state) as total FROM omas_purchase_order_mapping m LEFT JOIN purchase_order o ON m.odoo_purchase_order_id = o.id 
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            elif interval == 30:
                query = f"""
                    SELECT cast(ROUND(EXTRACT('Day' FROM o.create_date)) as int) as day, count(o.state) as total FROM omas_purchase_order_mapping m LEFT JOIN purchase_order o ON m.odoo_purchase_order_id = o.id 
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            else:
                query = f"""
                    SELECT to_char(o.create_date, 'Mon') as day, count(o.state) as total FROM omas_purchase_order_mapping m LEFT JOIN purchase_order o ON m.odoo_purchase_order_id = o.id 
                    WHERE o.create_date >= now() - interval '{interval} month' GROUP BY 1 ORDER BY 1 
                """
            query_data = self._get_query_result(query)
            data = self._get_line_chart_data(interval, query_data)
        return data
    
    @http.route('/omas/fetch_product_data', type='json', auth='user')
    def fetch_product_data(self, *args, **kwargs):
        interval = kwargs.get('interval')
        chart = kwargs.get('chart')
        if chart in ['donut', 'pie']:
            data = self._get_product_donut_pie_chart_data(chart)
        elif chart == 'bar':
            if interval == 7:
                query = f"""SELECT to_char(o.create_date, 'Dy') as month, count(o.name) FROM omas_template_mapping m LEFT JOIN product_template o ON m.odoo_template_id = o.id
                    WHERE o.create_date >= NOW() - interval '{interval} day' GROUP BY 1 ORDER BY 1"""
            else:
                query = f"""SELECT to_char(o.create_date, 'Mon') as month, count(o.name) FROM omas_template_mapping m LEFT JOIN product_template o ON m.odoo_template_id = o.id
                    WHERE o.create_date >= NOW() - interval '{interval} month' GROUP BY 1 ORDER BY 1"""
            query_data = self._get_query_result(query)
            data = self._get_bar_chart_data(interval, query_data)
        elif chart in ['line', 'line2']:
            if interval == 7:
                query = f"""
                    SELECT to_char(o.create_date, 'Dy') as day, count(o.name) as total FROM omas_template_mapping m LEFT JOIN product_template o ON m.odoo_template_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            elif interval == 30:
                query = f"""
                    SELECT cast(ROUND(EXTRACT('Day' FROM o.create_date)) as int) as day, count(o.name) as total FROM omas_template_mapping m LEFT JOIN product_template o ON m.odoo_template_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            else:
                query = f"""
                    SELECT to_char(o.create_date, 'Mon') as day, count(o.name) as total FROM omas_template_mapping m LEFT JOIN product_template o ON m.odoo_template_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} month' GROUP BY 1 ORDER BY 1 
                """
            query_data = self._get_query_result(query)
            data = self._get_line_chart_data(interval, query_data)
        return data

    @http.route('/omas/fetch_invoice_data', type='json', auth='user')
    def fetch_invoice_data(self, *args, **kwargs):
        interval = kwargs.get('interval')
        chart = kwargs.get('chart')
        if chart in ['donut']:
            query = f"""SELECT o.amount_total as total, o.name FROM account_move o  
                WHERE o.create_date >= NOW() - interval '{interval} day' AND o.state IN ('posted') ORDER BY o.amount_total DESC LIMIT 5"""
            query_data = self._get_query_result(query)
            data = self._get_donut_pie_chart_data('invoice', query_data)
            
        elif chart == 'pie':
            query = f"""SELECT o.amount_total as total, o.name FROM omas_invoice_mapping m LEFT JOIN account_move o ON m.odoo_invoice_id = o.id 
                WHERE o.create_date >= NOW() - interval '{interval} day' AND o.state IN ('posted') ORDER BY o.amount_total DESC LIMIT 5"""
            query_data = self._get_query_result(query)
            data = self._get_donut_pie_chart_data('invoice', query_data)
        elif chart == 'bar':
            if interval == 7:
                query = f"""SELECT to_char(o.create_date, 'Dy') as month, count(o.state) FROM omas_invoice_mapping m LEFT JOIN account_move o ON m.odoo_invoice_id = o.id 
                    WHERE o.create_date >= NOW() - interval '{interval} day' GROUP BY 1 ORDER BY 1"""
            else:
                query = f"""SELECT to_char(o.create_date, 'Mon') as month, count(o.state) FROM omas_invoice_mapping m LEFT JOIN account_move o ON m.odoo_invoice_id = o.id 
                    WHERE o.create_date >= NOW() - interval '{interval} month' GROUP BY 1 ORDER BY 1"""
            query_data = self._get_query_result(query)
            data = self._get_bar_chart_data(interval, query_data)
        elif chart in ['line', 'line2']:
            if interval == 7:
                query = f"""
                    SELECT to_char(o.create_date, 'Dy') as day, count(o.state) as total FROM omas_invoice_mapping m LEFT JOIN account_move o ON m.odoo_invoice_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            elif interval == 30:
                query = f"""
                    SELECT cast(ROUND(EXTRACT('Day' FROM o.create_date)) as int) as day, count(o.state) as total FROM omas_invoice_mapping m LEFT JOIN account_move o ON m.odoo_invoice_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            else:
                query = f"""
                    SELECT to_char(o.create_date, 'Mon') as day, count(o.state) as total FROM omas_invoice_mapping m LEFT JOIN account_move o ON m.odoo_invoice_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} month' GROUP BY 1 ORDER BY 1 
                """
            query_data = self._get_query_result(query)
            data = self._get_line_chart_data(interval, query_data)
        return data
    
    @http.route('/omas/fetch_customer_data', type='json', auth='user')
    def fetch_customer_data(self, *args, **kwargs):
        interval = kwargs.get('interval')
        chart = kwargs.get('chart')
        if chart in ['donut', 'pie']:
            data = self._get_customer_donut_pie_chart_data(chart)
        elif chart == 'bar':
            if interval == 7:
                query = f"""SELECT to_char(o.create_date, 'Dy') as month, count(o.name) FROM omas_customer_mapping m LEFT JOIN res_partner o ON m.odoo_customer_id = o.id
                    WHERE o.create_date >= NOW() - interval '{interval} day' GROUP BY 1 ORDER BY 1"""
            else:
                query = f"""SELECT to_char(o.create_date, 'Mon') as month, count(o.name) FROM omas_customer_mapping m LEFT JOIN res_partner o ON m.odoo_customer_id = o.id
                    WHERE o.create_date >= NOW() - interval '{interval} month' GROUP BY 1 ORDER BY 1"""
            query_data = self._get_query_result(query)
            data = self._get_bar_chart_data(interval, query_data)
        elif chart in ['line', 'line2']:
            if interval == 7:
                query = f"""
                    SELECT to_char(o.create_date, 'Dy') as day, count(o.name) as total FROM omas_customer_mapping m LEFT JOIN res_partner o on m.odoo_customer_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            elif interval == 30:
                query = f"""
                    SELECT cast(ROUND(EXTRACT('Day' FROM o.create_date)) as int) as day, count(o.name) as total FROM omas_customer_mapping m LEFT JOIN res_partner o on m.odoo_customer_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} day' GROUP BY 1 ORDER BY 1 
                """
            else:
                query = f"""
                    SELECT to_char(o.create_date, 'Mon') as day, count(o.name) as total FROM omas_customer_mapping m LEFT JOIN res_partner o on m.odoo_customer_id = o.id
                    WHERE o.create_date >= now() - interval '{interval} month' GROUP BY 1 ORDER BY 1 
                """
            query_data = self._get_query_result(query)
            data = self._get_line_chart_data(interval, query_data)
        return data

    def _get_donut_pie_chart_data(self, obj, query_data):
        if obj in ["order", "purchase", 'invoice']:
            color = ['#2796dd','#FF8231','#ee82ee','#624fb0','#33FF7D']
            color = dict(zip([i.get('name') for i in query_data[:5]], color))
        data = {'data':[],'labels':[],'colors':[]}
        sale_data = {result['name'].strip():result['total'] for result in query_data}
        for check in color:
            data['data'].append(sale_data.get(check,0))
            data['colors'].append(color[check])
            data['labels'].append(check)
        return data
    
    def _get_product_donut_pie_chart_data(self, chart):
        data = {
                'data':[],
                'labels':[],
                'colors' : ['#2796dd','#FF8231','#ee82ee','#624fb0','#33FF7D']
            }
        if chart == 'donut':
            product_env = request.env['product.template'].search([])
        else:
            product_env = request.env['omas.template.mapping'].search([]).mapped('name')
        product_env = product_env.filtered(lambda x: x.sales_count)
        sales_count = product_env.mapped('sales_count')
        names = product_env.mapped('name')
        sales_count_tuple = list(zip(sales_count, names))
        sales_count_tuple.sort(reverse=True, key=lambda x: x[0])
        top5 =sales_count_tuple[:5]
        for element in top5:
            data['data'].append(element[0])
            data['labels'].append(element[1])
        return data

    def _get_customer_donut_pie_chart_data(self, chart):
        data = {
                'data':[],
                'labels':[],
                'colors' : ['#2796dd','#FF8231','#ee82ee','#624fb0','#33FF7D']
            }
        if chart == 'donut':
            partner_env = request.env['res.partner'].search([])
        else:
            partner_env = request.env['omas.customer.mapping'].search([]).mapped('name')
        partner_env = partner_env.filtered(lambda x: x.sale_order_count)
        order_count = partner_env.mapped('sale_order_count')
        names = partner_env.mapped('name')
        order_count_tuple = list(zip(order_count, names))
        order_count_tuple.sort(reverse = True, key=lambda x: x[0])
        top5=order_count_tuple[:5]
        for element in top5:
            data['data'].append(element[0])
            data['labels'].append(element[1])
        return data
    
    def _get_bar_chart_data(self, interval, query_data):
        labels, colors = [],[]
        if interval == 7:
            labels = []
            terms = {
                '0': 'Mon',
                '1': 'Tue',
                '2': 'Wed',
                '3': 'Thu',
                '4': 'Fri',
                '5': 'Sat',
                '6': 'Sun'
            }
            term = date.today().weekday()
        else:
            terms = {
                '12':'Dec',
                '11':'Nov',
                '10':'Oct',
                '9':'Sep',
                '8':'Aug',
                '7':'Jul',
                '6':'Jun',
                '5':'May',
                '4':'Apr',
                '3':'Mar',
                '2':'Feb',
                '1':'Jan',
            }
            term = date.today().month
        
        for i in range(interval):
            try:
                colors.append('#2796dd')
                labels.insert(0, terms[str(term)])
            except KeyError:
                term = 6 if interval == 7 else 12               
                labels.insert(0,terms[str(term)])
            term -= 1
        data_dict=dict.fromkeys(labels, 0)
        data_dict.update({ record['month']:record['count'] for record in query_data})
        return {
            'labels':labels,
            'colors':colors,
            'data': [data_dict[label] for label in labels]
        }
    
    def _get_line_chart_data(self, interval, query_data):
        labels = []
        if interval == 7:
            days = {
                '0': 'Mon',
                '1': 'Tue',
                '2': 'Wed',
                '3': 'Thu',
                '4': 'Fri',
                '5': 'Sat',
                '6': 'Sun'
            }
            day = date.today().weekday()
            for i in range(interval):
                try:
                    labels.insert(0, days[str(day)])
                except KeyError:
                    day = 6
                    labels.insert(0,days[str(day)])
                day -= 1
        elif interval == 30:
            months = list(range(1, 32))
            today = date.today().day
            for i in range(interval):
                try:
                    labels.insert(0, months[today])
                except KeyError:
                    today = 30
                    labels.insert(0, months[today])
                today -= 1
        else:
            months = {
                '1':'Jan',
                '2':'Feb',
                '3':'Mar',
                '4':'Apr',
                '5':'May',
                '6':'Jun',
                '7':'Jul',
                '8':'Aug',
                '9':'Sep',
                '10':'Oct',
                '11':'Nov',
                '12':'Dec',
            }
            month = date.today().month
            month = 1 if month == 12 else month +1
            for i in range(interval):
                try:
                    labels.insert(0, months[str(month)])
                except KeyError:
                    month = 12
                    labels.insert(0, months[str(month)])
                month -= 1
        data_dict = dict.fromkeys(labels, 0)
        data_dict.update({record['day'] : record['total'] for record in query_data})
        return {
            'labels':labels,
            'data': [data_dict[label] for label in labels]
        }
    
    def _get_order_dashboard_data(self):
        return self._get_query_result(f"""
                SELECT o.id, o.name, to_char(o.create_date, 'DD-MM-YYYY') as date,o.amount_total, o.state from omas_order_mapping m LEFT JOIN sale_order o ON m.odoo_order_id=o.id 
            """)
    
    def _get_invoice_dashboard_data(self):
        return self._get_query_result(f"""
                SELECT o.id, o.name,to_char(o.invoice_date, 'DD-MM-YYYY') as date,o.amount_total_signed,o. amount_residual_signed, o.state from omas_invoice_mapping m LEFT JOIN account_move o ON m.odoo_invoice_id=o.id 
            """)

    def _get_product_dashboard_data(self):
        return self._get_query_result(f"""
                SELECT o.id, o.default_code,o.name, o.list_price from omas_template_mapping m LEFT JOIN product_template o ON m.odoo_template_id=o.id 
            """)

    def _get_partner_dashboard_data(self):
        return self._get_query_result(f"""
                SELECT o.id, o.name,o.phone, o.email from omas_customer_mapping m LEFT JOIN res_partner o ON m.odoo_customer_id=o.id 
            """)
    
    def _get_panel_data(self):
        data={
            'draft':0,
            'sale':0,
            'paid':0,
            'not_paid':0
        }
        query = f"""SELECT count(o.state) as total, o.state FROM omas_order_mapping om LEFT JOIN sale_order o 
            ON om.odoo_order_id=o.id WHERE state IN ('draft','sale') GROUP BY state UNION SELECT count(a.payment_state) 
            as total, a.payment_state FROM omas_invoice_mapping im LEFT JOIN account_move a ON im.odoo_invoice_id=a.id 
            WHERE payment_state IN ('paid','not_paid') GROUP BY payment_state"""
        query_data = self._get_query_result(query)
        for record in query_data:
            data[record['state']] = record['total']
        return data
    
    def _get_query_result(self, query):
        request._cr.execute(query)
        return request._cr.dictfetchall()
