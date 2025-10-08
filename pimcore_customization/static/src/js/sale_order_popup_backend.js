
/** @odoo-module **/

import { SaleOrderLineProductField } from '@sale/js/sale_product_field';
import { serializeDateTime } from "@web/core/l10n/dates";
import { x2ManyCommands } from "@web/core/orm_service";
import { _t } from "@web/core/l10n/translation";
import { useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import {ProductConfiguratorDialog} from '@sale/js/product_configurator_dialog/product_configurator_dialog';
import { createSaleOrder } from "./sale_order_utils.js";
import {GlobalData} from './product_configurator_dialog';

async function applyProduct(record, product) {
    // handle custom values & no variants
    const customAttributesCommands = [
        x2ManyCommands.set([]),  // Command.clear isn't supported in static_list/_applyCommands
    ];
    for (const ptal of product.attribute_lines) {
        const selectedCustomPTAV = ptal.attribute_values.find(
            ptav => ptav.is_custom && ptal.selected_attribute_value_ids.includes(ptav.id)
        );
        if (selectedCustomPTAV) {
            customAttributesCommands.push(
                x2ManyCommands.create(undefined, {
                    custom_product_template_attribute_value_id: [selectedCustomPTAV.id, "we don't care"],
                    custom_value: ptal.customValue,
                })
            );
        };
    }

    const noVariantPTAVIds = product.attribute_lines.filter(
        ptal => ptal.create_variant === "no_variant"
    ).flatMap(ptal => ptal.selected_attribute_value_ids);

    await record.update({
        product_id: [product.id, product.display_name],
        product_uom_qty: product.quantity,
        product_no_variant_attribute_value_ids: [x2ManyCommands.set(noVariantPTAVIds)],
        product_custom_attribute_value_ids: customAttributesCommands,
    });
};

patch(SaleOrderLineProductField.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.actionService = useService("action");
        let isMounted = false;
        let isInternalUpdate = false;
        const originalUpdateRecord = this.updateRecord;
        this.updateRecord = (value) => {
            isInternalUpdate = true;
            return originalUpdateRecord.call(this, value);
        };
        const seenNames = new Set();
        let hasDuplicates = false;
        let updatedBreadcrumbs = this.env.config.breadcrumbs.filter((item) => {
            if (seenNames.has(item.name)) {
                hasDuplicates = true;
                return false;
            }
            seenNames.add(item.name);
            return true;
        });

        if (this.props.record.data.show_cpq && this.props.record.model.config.resId) {
            const filteredBreadcrumbs = this.env.config.breadcrumbs.filter(item => item.name !== 'New');
            this.env.config.breadcrumbs.length = 0;
            this.env.config.breadcrumbs.push(...filteredBreadcrumbs);
        }

        if (hasDuplicates) {
            this.env.config.breadcrumbs.length = 0;  // Clear existing breadcrumbs
            this.env.config.breadcrumbs.push(...updatedBreadcrumbs); // Add new ones
            this.render(true);
        }

       useEffect(() => {
        if (!isMounted) {
            isMounted = true;
            return;
        }

        if (isInternalUpdate && this.value) {
            const productTemplateId = this.props.record.data.product_template_id?.[0];
            let saleOrderId = this.props.record.model.config.resId; // Just check the plain sale_order_id here
            const showCpq = this.props.record.data.show_cpq; // Get the `show_cpq` value
            if (!showCpq) {
                    isInternalUpdate = false; // Reset internal update flag
                    return; // Don't open the wizard
            }
            if(this.props.record.data.product_add_mode == "configurator")
            {
                if(!saleOrderId)
                {
                    if(this.props.record.data.show_cpq){

                        let missingFields = [];
                        if (!this.props.record._parentRecord.data.partner_id) {
                            missingFields.push("Customer");
                        }
                        if (!this.props.record._parentRecord.data.partner_invoice_id) {
                            missingFields.push("Invoice Address");
                        }
                        if (!this.props.record._parentRecord.data.partner_shipping_id) {
                            missingFields.push("Delivery Address");
                        }

                        if (missingFields.length > 0) {
                            missingFields.forEach(field => {
                                this.notification.add(`• ${field}`, {
                                    title: "Invalid Fields:",
                                    type: "danger",
                                });
                            });
                            const saleOrderRecord = this.props.record.model.root;
                            saleOrderRecord.data.order_line.delete(this.props.record);
                        }
                        else{
                            createSaleOrder(this.orm, this.props).then((newSaleOrderId) => {
                                    this.props.record.model.config.resId = newSaleOrderId;
                                    this.orm
                                    .call("product.template", "get_attribute_line_data", [productTemplateId])
                                    .then((result) => {
                                        if (this.relation === "product.template" && !result.has_configurable_attributes) {
                                                this.actionService.doAction({
                                                    name: _t("Open Wizard"),
                                                    type: "ir.actions.act_window",
                                                    res_model: "sale.line.properties.wiz",
                                                    views: [[false, "form"]],
                                                    context:{
                                                        default_product_tmpl_id: productTemplateId,
                                                        related_printing_product_ids: result.related_printing_product_ids,
                                                        related_delivery_product_ids:result.related_delivery_product_ids,
                                                        active_id: newSaleOrderId,
                                                        showCpq:showCpq,
                                                    },
                                                    target: "new",
                                                });
                                        }
                                    })
                                    .catch((error) => {
                                        console.error(_t("Error fetching attribute line data:"), error);
                                    });
                            });
                        }
                    }
                }
                else if (productTemplateId && saleOrderId) {
                    this.orm.call("product.template", "get_attribute_line_data", [productTemplateId])
                        .then((data) => {
                                if (data){
                                    this.orm
                                    .call("product.template", "get_attribute_line_data", [productTemplateId])
                                    .then((result) => {
                                        if (this.relation === "product.template" && !result.has_configurable_attributes) {
                                            this.actionService.doAction({
                                                name: _t("Open Wizard"),
                                                type: "ir.actions.act_window",
                                                res_model: "sale.line.properties.wiz",
                                                views: [[false, "form"]],
                                                context:{
                                                    default_product_tmpl_id: productTemplateId,
                                                    related_printing_product_ids: result.related_printing_product_ids,
                                                    related_delivery_product_ids:result.related_delivery_product_ids,
                                                    active_id: saleOrderId,
                                                    showCpq:showCpq
                                                },
                                                target: "new",
                                            });
                                        }
                                    })
                                .catch((error) => {
                                    console.error(_t("Error fetching attribute line data:"), error);
                                });
                            }
                        }).catch((error) => {
                                console.error(_t("Error fetching attribute line data:"), error);
                            });
                }
            }
        }
        isInternalUpdate = false;
        }, () => [Array.isArray(this.value) && this.value[0]]);
    },

    async _openGridConfigurator(edit=false) {
        const saleOrderRecord = this.props.record.model.root;

        // fetch matrix information from server;
        await saleOrderRecord.update({
            grid_product_tmpl_id: this.props.record.data.product_template_id,
        });

        let updatedLineAttributes = [];
        if (edit) {
            // provide attributes of edited line to automatically focus on matching cell in the matrix
            for (let ptnvav of this.props.record.data.product_no_variant_attribute_value_ids.records) {
                updatedLineAttributes.push(ptnvav.resId);
            }
            for (let ptav of this.props.record.data.product_template_attribute_value_ids.records) {
                updatedLineAttributes.push(ptav.resId);
            }
            updatedLineAttributes.sort((a, b) => { return a - b; });
        }

        if(this.props.record.data.show_cpq){
            let missingFields = [];
            if (!this.props.record._parentRecord.data.partner_id) {
                missingFields.push("Customer");
            }
            if (!this.props.record._parentRecord.data.partner_invoice_id) {
                missingFields.push("Invoice Address");
            }
            if (!this.props.record._parentRecord.data.partner_shipping_id) {
                missingFields.push("Delivery Address");
            }

            if (missingFields.length > 0) {
                missingFields.forEach(field => {
                    this.notification.add(`• ${field}`, {
                        title: "Invalid Fields:",
                        type: "danger",
                    });
                });

            }
            else{
                this._openMatrixConfigurator(
                    saleOrderRecord.data.grid,
                    this.props.record.data.product_template_id[0],
                    updatedLineAttributes,
                );
            }
        }
        else{
            this._openMatrixConfigurator(
                saleOrderRecord.data.grid,
                this.props.record.data.product_template_id[0],
                updatedLineAttributes,
            );
        }

        if (!edit) {
            // remove new line used to open the matrix
            saleOrderRecord.data.order_line.delete(this.props.record);
        }
    },


    onEditConfiguration() {
        super.onEditConfiguration(...arguments);
        if (this.props.record.data.product_add_mode == 'matrix') {
            this._openGridConfigurator(true);
        }
        else{
            this._openProductConfigurator(true);
        }
    },

    get isConfigurableTemplate() {
        return super.isConfigurableTemplate || this.props.record.data.is_configurable_product;
    },

    async _openProductConfigurator(edit=false) {
        if (this.props.record.data.product_add_mode == 'matrix') return;
        const saleOrderRecord = this.props.record.model.root;
        const saleOrderLine = this.props.record.data;
        let ptavIds = this._getVariantPtavIds(saleOrderLine);
        let customPtavs = [];

        if (edit) {
            /**
             * no_variant and custom attribute don't need to be given to the configurator for new
             * products.
             */
            ptavIds.push(...this._getNoVariantPtavIds(saleOrderLine));
            customPtavs = await this._getCustomPtavs(saleOrderLine);
        }
        if(this.props.record._parentRecord.data.partner_id &&
            this.props.record._parentRecord.data.partner_invoice_id &&
            this.props.record._parentRecord.data.partner_shipping_id)
        {

            if (GlobalData.dialogIsOpen) return;
                GlobalData.dialogIsOpen = true;

            this.dialog.add(ProductConfiguratorDialog, {
                productTemplateId: saleOrderLine.product_template_id[0],
                ptavIds: ptavIds,
                customPtavs: customPtavs,
                quantity: saleOrderLine.product_uom_qty,
                productUOMId: saleOrderLine.product_uom[0],
                companyId: saleOrderRecord.data.company_id[0],
                pricelistId: saleOrderRecord.data.pricelist_id[0],
                currencyId: saleOrderLine.currency_id[0],
                record: this.props.record.model.root,
                soDate: serializeDateTime(saleOrderRecord.data.date_order),
                edit: edit,
                save: async (mainProduct, optionalProducts) => {
                    GlobalData.dialogIsOpen = false;
                    await Promise.all([
                        applyProduct(this.props.record, mainProduct),
                        ...optionalProducts.map(async product => {
                            const line = await saleOrderRecord.data.order_line.addNewRecord({
                                position: 'bottom', mode: 'readonly'
                            });
                            await applyProduct(line, product);
                        }),
                    ]);
                    this._onProductUpdate();
                    saleOrderRecord.data.order_line.leaveEditMode();
                },
                close: ()=>{
                    GlobalData.dialogIsOpen = false;
                },
                discard: () => {
                    GlobalData.dialogIsOpen = false;
                    saleOrderRecord.data.order_line.delete(this.props.record);
                },
                ...this._getAdditionalDialogProps(),
            });
        }
    },
});