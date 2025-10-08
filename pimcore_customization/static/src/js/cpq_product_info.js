/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";
import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { Layout } from "@web/search/layout";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class DynamicReportSalesEstimation extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");

        const pastState = this.props.state || {};

        this.activeIds = this.props.action.context.active_ids;
        this.state = useState({
            html: "",
            currenlists: [],
            selectedCurrelist: {},
        });
        onWillStart(async () => {
            await loadJS("/web/static/lib/jquery/jquery.js");
            var self = this
            this.renderHtml();
            this.state.currenlists = await this.getCurrenlists()
            this.state.selectedCurrelist = pastState.selectedCurrelist || this.currenlists[this.state.currenlists.length - 1];
            setTimeout(function () {

                $('.view-record').click(function(){
                    self.ClickProductTemplate()
                });
                $('.edit-record').click(function(){
                    self.ClickEditsRecord()
                });
                $('.estimation-checkbox').click(function(){
                    self.onChangeCheckbox()
                });
                $('.estimation-pricelist-header').click(function(ev){
                    self.onClickLink(ev)
                });
                    var $active_breadcrumb = $('div.o_control_panel').find('div.o_last_breadcrumb_item.active');
                    $active_breadcrumb.find('span').html('<span class="min-w-0 text-truncate">CPQ Product List</span>');
            },1000)
        });
    }

    get html() {
        return this.state.html;
    }

    get currenlists() {
        return this.state.currenlists;
    }

    get reportParams() {
        return {
            wizard_active_ids: this.props.action.context.active_ids ||'cpq.product.info',
            active_model: this.props.action.context.active_model,
            currency_id: this.selectedCurrelist.id || '',
        };
    }

    get selectedCurrelist() {
        return this.state.selectedCurrelist;
    }

    getCurrenlists() {
        return this.orm.searchRead("res.currency", [], ["id", "name"]);
    }

    async deleteRecords(ids, model) {
        return await this.orm.call(
            model, "unlink", [ids]
        );
    }

    async renderHtml() {
        let html = await this.orm.call(
            "report.cpq.product", "get_html", [], {data: this.reportParams}
        );
        this.state.html = markup(html);
    }

    onClickLink(ev) {
        ev.preventDefault();
        let classes = ev.target.getAttribute("class", "");
        let resModel = ev.target.getAttribute("data-model", "");
        let resId = ev.target.getAttribute("data-res-id", "");

        if (classes && classes.includes("o_action") && resModel && resId) {
            this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: resModel,
                res_id: parseInt(resId),
                views: [[false, 'form']],
                target: 'self',
            });
        }
    }

    ClickSelectProducts () {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'CPQ Product Information',
            res_model: 'cpq.product.info',
            views: [[false, 'form']],
            view_type: 'form',
            target: 'new',
        });
    }

    ClickCreateQuotation () {
        var self = this
        this.renderHtml();
        var estimation_id = [];
        $.each($("input[name='estimation_id']:checked"), function() {
            estimation_id.push(parseInt($(this).val()));
        });
        var currency_id = $("a.estimation-pricelist-header").data('res-id');
        this.props.action.context.currency_id = currency_id;
        this.props.action.context.estimation_id = estimation_id;
        this.props.action.context.custome_quotation = 'custom_quotation'
        if (estimation_id[0]) {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "cpq.create.quotation",
                name: "CPQ Create Quotation",
                views: [
                    [false, 'form'],
                    [false, 'list'],
                ],
                context: this.props.action.context,
                target: 'new',
            });
        }
        else{
            this.actionService.doAction({
                type: "ir.actions.act_window",
                name: "Create Quotation",
                res_model: "sale.order",
                views: [
                    [false, 'form'],
                    [false, 'list'],
                ],
                context: this.props.action.context,
                target: 'current',
            });
        }
        setTimeout(function () {
            $('.edit-record').click(function(){
                self.ClickEditsRecord()
            });
            $('.view-record').click(function(){
                self.ClickProductTemplate()
            });
            $('.estimation-checkbox').click(function(){
                self.onChangeCheckbox()
            });
            $('.estimation-pricelist-header').click(function(ev){
                self.onClickLink(ev)
            })
            var $active_breadcrumb = $('div.o_action_manager').find('li.breadcrumb-item');
            $active_breadcrumb.find('a').html('<a class="fw-bold text-truncate">CPQ Product List</a>');
            $('ol.breadcrumb').append("<li class='breadcrumb-item d-inline-flex min-w-0' data-hotkey='b'><span class='min-w-0 text-truncate'> Quotations </span> </li>");
        },2000)
    }

    ClickClearProducts () {
        var self = this;
        this.renderHtml();
        var estimation_id = [];
        $.each($("input[name='estimation_id']:checked"), function() {
            estimation_id.push(parseInt($(this).val()));
        });
        if (estimation_id != false){
            this.env.services.dialog.add(ConfirmationDialog, {
                body: _t("Are you sure you want to delete this record ?"),
                confirm: () => {
                    this.deleteRecords(estimation_id,'cpq.product.info').then(function () {
                        self.actionService.doAction({'type': 'ir.actions.client',
                                'name' : 'CPQ Poduct List',
                                'tag': 'dynamic_estimation_calculator_view','target': 'main'})
                    });
                }
            });
        }
        else{
            this.notification.add('Select a product from the list', {
                title: "Invalid Fields:",
                type: "danger",
            });
        }
    }

    onChangeCheckbox () {
        var rowCount = $('input[type="checkbox"]:checked').length;
        if(rowCount == 0){
            $('.clear-estimation-products').css('display', 'none');
        }
        else{
            $('.clear-estimation-products').css('display', 'inline');
        }
    }

    ClickEditsRecord () {
        var estimation_id = $(event.currentTarget).closest('tr').data('row-id');
        if (estimation_id) {
            this.orm.call("cpq.product.info", "write", [[estimation_id], { status: "configure" }])
                .then(() => {
                    this.actionService.doAction({
                        type: "ir.actions.act_window",
                        name: "CPQ Product Info Wizard",
                        res_model: "cpq.product.info",
                        res_id: estimation_id,
                        views: [[false, 'form']],
                        target: "new",
                    });
                });
        }
    }

    onSelectCurrenlist(ev) {
        var self = this
        this.state.selectedCurrelist = this.currenlists.filter(currency =>
            currency.id === parseInt(ev.target.value)
        )[0];
        this.renderHtml();
        setTimeout(function () {
            $('.edit-record').click(function(){
                self.ClickEditsRecord()
            });
            $('.view-record').click(function(){
                self.ClickProductTemplate()
            });
            $('.estimation-checkbox').click(function(){
                self.onChangeCheckbox()
            });
            $('.estimation-pricelist-header').click(function(ev){
                self.onClickLink(ev)
            })
        },1000)
    }

    ClickProductTemplate () {
        const selectedwizardId = $(event.currentTarget).data('product-template-id');
        this.orm.call("cpq.product.section.line", "action_open_selected_product",  [selectedwizardId],{})
        .then((data) => {
           this.actionService.doAction({
               type: "ir.actions.act_window",
               name: "CPQ Product Info Wizard",
               res_model: "cpq.product.info",
               views: [[data.view_id[0], 'form']],
               target: 'new',
               context:{
                   wizard_id:selectedwizardId,
                   currency_id: this.state.selectedCurrelist?.id
               }
           });
        });
    }

}

DynamicReportSalesEstimation.props = {
    action: { type: Object },
    "*": true,
}
DynamicReportSalesEstimation.components = { Layout };
DynamicReportSalesEstimation.template = "pimcore_customization.DynamicReportSalesEstimation";
registry.category("actions").add("dynamic_estimation_calculator_view", DynamicReportSalesEstimation);