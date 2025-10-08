/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { onWillStart, Component, onMounted, onWillRender} from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { hexToRGBA } from "@web/core/colors/colors";

export class omasDashboard extends Component {
    static template = 'omas_dashboard_template'
    setup() {
        var _this = this
        this.rpc = rpc;
        this.orm = useService("orm");
        this.action = useService('action');
        $(document).on("click", ".btn_open_view", function(){
            let model_id = $(this).attr("id").split('_')
            let model = model_id[0]
            let id = model_id[1]
            _this.OpenRecordView(id, model);
        });
        onWillStart(async () => {
            let self = this
            await loadBundle('odoo_multi_accounting_solution.assetsLib');

            // return $.when(
            //     loadBundle(this),
            // ).then(function() {
            //     self.fetchDashboardData();
            // })
            
        });
        onMounted(() => {
            this.on_attach_callback();
            });
        onWillRender(() => {
            this.on_attach_callback();
            });
    };

    on_attach_callback() {
        this.fetchDashboardData()
        this.reloadDonutChart()
        this.reloadBarChart()
        this.reloadLineChart()
        this.reloadPieChart()
        this.topRevenueList()
    };
    on_action(e) {
        let instance = e.target.id
        let dataList = instance.split("_")

        return this.action.doAction({
            name: 'Instance',
            type: 'ir.actions.act_window',
            res_model: dataList[0],
            res_id: Number(dataList[1]),
            views: [
                [false, 'form']
            ],
            target: 'current'
        })
    };
    openImportWizard() {
        return this.action.doAction('odoo_multi_accounting_solution.omas_import_operation_action')
    };
    openExportWizard() {
        return this.action.doAction('odoo_multi_accounting_solution.omas_export_operation_action')
    };
    openInstances() {
        return this.action.doAction('odoo_multi_accounting_solution.omas_action')
    };
    OpenRecordView(id, model) {
        return this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            res_id: parseInt(id),
            views: [[false, 'form']],
        })
    };
    topRevenueList() {
        let is_mapped = $('#revenue_data_change').is(':checked')
        let selected_option = 'all'
        if (is_mapped){
            selected_option = 'all mapped'
        }
        let selected_obj = $('#revenue_obj_change option:selected').val()
        let interval = $('#revenue_date_change option:selected')
        let top_revenue_detail = $('#top_revenue_detail')
        return this.rpc('/omas/fetch_top_revenue', {
            selected_option: selected_option,
            selected_obj: selected_obj,
            interval: interval.val(),
            table_size: 5
        }).then(function(data) {
            if (selected_obj == 'product') { // Product Table
                $('#top_revenue_text').text('Best Selling Products')
                top_revenue_detail.text(`Best in ${selected_option} Selling Product from ${interval.text()} based on Sales Count`)
                $('#productTable tbody').empty();
                $('#productTable tbody').html('<tr></tr>')
                $('#productTable').removeClass('d-none')
                $('#orderTable').addClass('d-none')
                if (data.length){
                    for (let i = 0; i < data.length; i++) {
                        if (i < data.length) {
                            let p_id = 'product.product_'+data[i]['id']
                            let p_name = `<td style="color:#1d6bda;"><button id=${p_id} class='btn btn-link btn_open_view' style="color:#1d6bda;">${data[i]['name']}</button></td>`
                            $('#productTable tbody tr:last').after(`<tr>${p_name}<td>${data[i]['count']}</td><td>$${data[i]['revenue']}</td><td>${data[i]['date']}</td></tr>`)
                        }
                    }
                }
            }
            else { // Order Table
                $('#top_revenue_text').text('Top Sales Orders')
                top_revenue_detail.text(`Top Orders in ${selected_option} Sales From ${interval.text()} based on Revenue`)
                $('#orderTable tbody').empty();
                $('#orderTable tbody').html('<tr></tr>')
                $('#productTable').addClass('d-none')
                $('#orderTable').removeClass('d-none')
                if (data.length){
                    for (let i = 0; i < data.length; i++) {
                        if (i < data.length) {
                            let s_id = "sale.order_"+data[i]['id']
                            let s_name = `<td><button id='${s_id}' class='btn btn-link btn_open_view' style="color:#1d6bda;">${data[i]['name']}</button></td>`
                            $('#orderTable tbody tr:last').after(`<tr>${s_name}<td>${data[i]['customer']}</td><td>${data[i]['total']}</td><td>${data[i]['date']}</td><td class='text-capitalize'>${data[i]['state']}</td></tr>`)
                            }
                        }
                    }   
                }
        })
    };
    replaceDonutPie(e) {
        var target = $(e.currentTarget)
        if (target.data('mode') == 'donut') {
            $('.pie_button').removeClass('active')
            $('.donut_button').addClass('active')
            $('#pie_chart_view').addClass('d-none')
            $('#donut_chart_view').removeClass('d-none')
            this.reloadDonutChart()
        }
        else{
            $('.donut_button').removeClass('active')
            $('.pie_button').addClass('active')
            $('#pie_chart_view').removeClass('d-none')
            $('#donut_chart_view').addClass('d-none')
            this.reloadPieChart()
        }
    };
    fetchDashboardData() {
        return this.rpc('/omas/fetch_dashboard_data').then(function(result) {
            let self = this
            $('#navPanelPaid').text(result.paid)
            $('#navPanelUnpaid').text(result.not_paid)
            $('#navPanelPending').text(result.draft)
            $('#navPanelCompleted').text(result.sale)
            $('#connectedInstances').text(result.instance_id.length)
        })
    };
    fetchOrderData(chart = 'donut', interval = 7) {
        return this.rpc(
            '/omas/fetch_order_data',
            { chart: chart, interval: interval }
        )
    };
    fetchPurchaseData(chart = 'donut', interval = 7) {
        return this.rpc(
            '/omas/fetch_purchase_data',
            { chart:chart, interval:interval }
        )
    };
    fetchProductData(chart = 'donut', interval = 7) {
        return this.rpc(
            '/omas/fetch_product_data',
            {chart: chart, interval: interval }
        )
    };
    fetchCustomerData(chart = 'donut', interval = 7) {
        return this.rpc(
            '/omas/fetch_customer_data',
            {chart: chart, interval: interval }
        )
    };
    fetchInvoiceData(chart = 'donut', interval = 7) {
        return this.rpc(
            '/omas/fetch_invoice_data',
            {chart: chart, interval: interval }
        )
    };
    renderDonutChart(data, labels, colors) {
        let self = this
        $('#donut_chart').replaceWith($('<canvas/>', { id: 'donut_chart' }))
        self.chart = new Chart('donut_chart', {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    showInLegend: true,
                    hoverOffset: 2,
                    hoverBorderWidth: 2,
                }],
            },
            options: {
                rotation: 180,
                cutout: "65%",
                responsive: true,
                animation: {
                    animateRotate: true,
                    animateScale: true,
                },
                maintainAspectRatio: false,
                layout: {
                    padding: 40,
                },
                plugins: {
                    legend: {
                        position: 'left',
                        display: true,
                        labels: {
                            usePointStyle: true,
                            font: {
                                size: 14,
                            },
                        },
                    }
                }
            },
            centerText: {
                display: true,
                text: "Orders"
            }
        });

    };
    renderBarChart(data, labels, colors, chart_label) {
        let self = this;
        $('#bar_chart').replaceWith($('<canvas/>', { id: 'bar_chart' }))
        self.chart = new Chart('bar_chart', {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: chart_label.text(),
                    data: data,
                    backgroundColor: colors,
                    borderColor: colors,
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            pointStyle: 'line',
                            usePointStyle: true,
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false,
                        },
                    },
                    y: {
                        beginAtZero: true
                    }
                },
            },
        });
    };
    renderLineChart(data, labels, chart_label) {
        let self = this;
        $('#line_chart').replaceWith($('<canvas/>', { id: 'line_chart' }))
        self.chart = new Chart('line_chart', {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: chart_label.text(),
                    data: data,
                    fill: 'start',
                    borderColor: '#2796dd',
                    tension: 0.4,
                    borderWidth: 3,
                    pointRadius: 3,
                    pointHoverRadius: 10,
                    backgroundColor: hexToRGBA('#2796dd', 0.3),
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            pointStyle: 'line',
                            usePointStyle: true,
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            padding: 5,
                        },
                        grid: {
                            display: false,
                        },
                    },
                    y: {
                        ticks: {
                            padding: 5,
                        },
                        beginAtZero: true,
                    }
                },
            },
        });

    };
    renderPieChart(data, labels, colors) {
        let self = this;
        $('#pie_chart').replaceWith($('<canvas/>', { id: 'pie_chart' }))
        self.chart = new Chart('pie_chart', {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    // label: 'Counts/Amount',
                    data: data,
                    backgroundColor: colors,
                    hoverOffset: 2,
                    hoverBorderWidth: 2,
                }],
            },
            options: {
                rotation: 180,
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: 40,
                },
                animation: {
                    animateRotate: true,
                    animateScale: true,
                },
                plugins: {
                    legend: {
                        position: 'left',
                        display: true,
                        labels: {
                            usePointStyle: true,
                            font: {
                                size: 14,
                            },
                        },
                    }
                }
            },
        });

    };
    reloadDonutChart() {
        let self = this
        let selected_option = $('#donut-obj-change option:selected').val()
        let donut_chart_label = $('#donut-chart-label')
        let donut_top_text = $('#donut-top-text')
        switch (selected_option) {
            case 'order':
                donut_chart_label.text('Sale Orders')
                return self.fetchOrderData('donut', parseInt($('#donut-date-change option:selected').val())).then(function(result) {
                    donut_top_text.text('Top 5 Sale Orders with Most Revenue in Odoo')
                    self.renderDonutChart(result.data, result.labels, result.colors)
                })
            case 'product':
                donut_chart_label.text('Products')
                return self.fetchProductData('donut', parseInt($('#donut-date-change option:selected').val())).then(function(result) {
                    donut_top_text.text('Top 5 Products with Most Sales Count in Odoo')
                    self.renderDonutChart(result.data, result.labels, result.colors)
                })
            case 'invoice':
                donut_chart_label.text('Invoices')
                return self.fetchInvoiceData('donut', parseInt($('#donut-date-change option:selected').val())).then(function(result) {
                    donut_top_text.text('Top 5 Invoices with Most Revenue in Odoo')
                    self.renderDonutChart(result.data, result.labels, result.colors)
                })
            case 'customer':
                donut_chart_label.text('Customers')
                return self.fetchCustomerData('donut', parseInt($('#donut-date-change option:selected').val())).then(function(result) {
                    donut_top_text.text('Top 5 Customers with Most Sales Count in Odoo')
                    self.renderDonutChart(result.data, result.labels, result.colors)
                })
            case 'purchase':
                donut_chart_label.text('Purchase')
                return self.fetchPurchaseData('donut', parseInt($('#donut-date-change option:selected').val())).then(function(result) {
                    donut_top_text.text('Top 5 Purchase Orders with Most Purchase Amount in Odoo')
                    self.renderDonutChart(result.data, result.labels, result.colors)
                })
            default:
                donut_chart_label.text('')
        }
    };
    reloadBarChart() {
        let self = this
        let selected_option = $('#bar-obj-change option:selected').val()
        let bar_chart_label = $('#bar-chart-label')
        let bar_top_text = $('#bar-top-text')
        switch (selected_option) {
            case 'order':
                bar_chart_label.text('Sales Orders')
                bar_top_text.text('Sales Orders With Mapping Created in Odoo')
                return self.fetchOrderData('bar', parseInt($('#bar-date-change option:selected').val())).then(function(result) {
                    self.renderBarChart(result.data, result.labels, result.colors, bar_chart_label)
                })
            case 'product':
                bar_chart_label.text('Products')
                bar_top_text.text('Products With Mapping Created in Odoo')
                return self.fetchProductData('bar', parseInt($('#bar-date-change option:selected').val())).then(function(result) {
                    self.renderBarChart(result.data, result.labels, result.colors, bar_chart_label)
                })
            case 'invoice':
                bar_chart_label.text('Invoices')
                bar_top_text.text('Invoices With Mapping Created in Odoo')
                return self.fetchInvoiceData('bar', parseInt($('#bar-date-change option:selected').val())).then(function(result) {
                    self.renderBarChart(result.data, result.labels, result.colors, bar_chart_label)
                })
            case 'customer':
                bar_chart_label.text('Customers')
                bar_top_text.text('Customers With Mapping Created in Odoo')
                return self.fetchCustomerData('bar', parseInt($('#bar-date-change option:selected').val())).then(function(result) {
                    self.renderBarChart(result.data, result.labels, result.colors, bar_chart_label)
                })
            case 'purchase':
                bar_chart_label.text('Purchase Order')
                bar_top_text.text('Purchase Orders With Mapping Created in Odoo')
                return self.fetchPurchaseData('bar', parseInt($('#bar-date-change option:selected').val())).then(function(result) {
                    self.renderBarChart(result.data, result.labels, result.colors, bar_chart_label)
                })
            default:
                bar_chart_label.text('')
        }

    };
    reloadLineChart() {
        let self = this
        let selected_option = $('#line-obj-change option:selected').val()
        let line_chart_label = $('#line-chart-label')
        let line_top_text = $('#line-top-text')
        switch (selected_option) {
            case 'order':
                line_chart_label.text('Sales Orders')
                line_top_text.text('Sale Orders With Mapping Created in Odoo')
                return self.fetchOrderData('line',
                    parseInt($('#line-date-change option:selected').val())
                ).then(function(result) {
                    self.renderLineChart(result.data, result.labels, line_chart_label)
                })
            case 'product':
                line_chart_label.text('Products')
                line_top_text.text('Products With Mapping Created in Odoo')
                return self.fetchProductData('line',
                    parseInt($('#line-date-change option:selected').val())
                ).then(function(result) {
                    self.renderLineChart(result.data, result.labels, line_chart_label)
                })
            case 'invoice':
                line_chart_label.text('Invoices')
                line_top_text.text('Invoices With Mapping Created in Odoo')
                return self.fetchInvoiceData('line',
                    parseInt($('#line-date-change option:selected').val())
                ).then(function(result) {
                    self.renderLineChart(result.data, result.labels, line_chart_label)
                })
            case 'customer':
                line_chart_label.text('Customers')
                line_top_text.text('Customers With Mapping Created in Odoo')
                return self.fetchCustomerData('line',
                    parseInt($('#line-date-change option:selected').val())
                ).then(function(result) {
                    return self.renderLineChart(result.data, result.labels, line_chart_label)
                })
            case 'purchase':
                line_chart_label.text('Purchase Order')
                line_top_text.text('Purchase Orders With Mapping Created in Odoo')
                return self.fetchPurchaseData('line',
                    parseInt($('#line-date-change option:selected').val())
                ).then(function(result) {
                    return self.renderLineChart(result.data, result.labels, line_chart_label)
                })
            default:
                line_chart_label.text('')
        }
    };
    reloadPieChart() {
        let self = this
        let selected_option = $('#pie-obj-change option:selected').val()
        let pie_chart_label = $('#pie-chart-label')
        let pie_top_text = $('#pie-top-text')
        switch (selected_option) {
            case 'order':
                pie_chart_label.text('Sales Orders')
                return self.fetchOrderData('pie',
                parseInt($('#pie-date-change option:selected').val()),
                ).then(function(result) {
                    pie_top_text.text('Top '+ result.data.length + ' Mapped Sale Order With Most Revenue Created in Odoo')
                    self.renderPieChart(result.data, result.labels, result.colors)
                })
            case 'product':
                pie_chart_label.text('Products')
                return self.fetchProductData('pie',
                parseInt($('#pie-date-change option:selected').val()),
                ).then(function(result) {
                    pie_top_text.text('Top '+ result.data.length + ' Mapped Products with Most Sales Count in Odoo')
                    self.renderPieChart(result.data, result.labels, result.colors)
                })
            case 'invoice':
                pie_chart_label.text('Invoices')
                return self.fetchInvoiceData('pie',
                parseInt($('#pie-date-change option:selected').val()),
                ).then(function(result) {
                    pie_top_text.text('Top '+ result.data.length + ' Mapped Invoice With Most Revenue Created in Odoo')
                    self.renderPieChart(result.data, result.labels, result.colors)
                })
            case 'customer':
                pie_chart_label.text('Customers')
                return self.fetchCustomerData('pie',
                parseInt($('#pie-date-change option:selected').val()),
                ).then(function(result) {
                    pie_top_text.text('Top '+ result.data.length + ' Mapped Customers with Most Sales Count in Odoo')
                    self.renderPieChart(result.data, result.labels, result.colors)
                })
            case 'purchase':
                pie_chart_label.text('Purchase Order')
                return self.fetchPurchaseData('pie',
                parseInt($('#pie-date-change option:selected').val()),
                ).then(function(result) {
                    pie_top_text.text('Top '+ result.data.length + ' Mapped Purchase Order With Most Purchase Amount Created in Odoo')
                    self.renderPieChart(result.data, result.labels, result.colors)
                })
            default:
                pie_chart_label.text('')
        }
    };
}

omasDashboard.template = "odoo_multi_accounting_solution.omas_dashboard_template";
registry.category("actions").add("omas_dashboard_action", omasDashboard);
