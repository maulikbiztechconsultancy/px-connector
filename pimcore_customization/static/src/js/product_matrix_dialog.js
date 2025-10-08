/** @odoo-module **/

import { Dialog } from '@web/core/dialog/dialog';
import { useService } from "@web/core/utils/hooks";
import { ProductMatrixDialog } from "@product_matrix/js/product_matrix_dialog";
import { patch } from "@web/core/utils/patch";
import { createSaleOrder } from "./sale_order_utils.js";
import { Component, onMounted, markup, useRef } from "@odoo/owl";

patch(ProductMatrixDialog.prototype,  {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.showCustomMatrix = false;  
        this.show_cpq = false;
        if(this.props.record &&  this.props.record.data && this.props.record.data.order_line && this.props.record.data.order_line._cache)
        {
            let cache = this.props.record.data.order_line._cache;
            let cacheKeys = Object.keys(cache);
            if(cacheKeys.length > 0)
            {
                let lastKey = cacheKeys[cacheKeys.length -1];
                let lastRecord = cache[lastKey];

                if(lastRecord && lastRecord.data)
                {
                    let showcpq = lastRecord.data.show_cpq;
                    this.show_cpq = showcpq
                }
            }
        }
        onMounted(() => {
            if(this.props.editedCellAttributes.length) {
                const inputs = document.getElementsByClassName('o_matrix_input');
                const relevantInput = Array.from(inputs).filter((matrixInput) =>
                    matrixInput.attributes.ptav_ids.nodeValue === this.props.editedCellAttributes
                )[0];
                if (relevantInput) {
                    relevantInput.select();
                } else {
                    // Based on the record creation, it may ignore the 'no_variant' attributes
                    // (e.g. from a stock.move), thus finding no match in the matrix.
                    inputs[0].select();
                }
            } else {
                document.getElementsByClassName('o_matrix_input')[0].select();
            }
        });
    },

    _onConfirmCustom() {
        if(this.props.editedCellAttributes !== "") return;

        if(this.show_cpq){
            let combinationIds = [];
            let variantIds = [];
            let variantQuantities = {};
            const inputs = document.getElementsByClassName('o_matrix_input');
            let saleOrderId = this.props.record.model.config.resId;
            if(!saleOrderId)
            {
                createSaleOrder(this.orm, this.props).then((newSaleOrderId) => {
                    this.props.record.model.config.resId = newSaleOrderId;
                    for (let matrixInput of inputs) {
                        if (matrixInput.value > 0) {
                            if (matrixInput.attributes.ptav_ids) {
                                let ptavIds = matrixInput.attributes.ptav_ids.nodeValue;
                                if (ptavIds) {
                                    const ids = ptavIds.split(',').map(id => parseInt(id.trim()));
                                    combinationIds = ids;
                                    this.orm.call("product.template", "get_data_val", [this.props.product_template_id,combinationIds],{})
                                    .then((data) => {
                                        if (data.variant_id) {
                                            variantIds.push(data.variant_id);
                                            variantQuantities[data.variant_id] = parseInt(matrixInput.value);
                                        }
                                        this.props.close();
                                        this.actionService.doAction({
                                            type: 'ir.actions.act_window',
                                            name: 'Printing Products',
                                            res_model: 'sale.line.properties.wiz',
                                            views: [[false, 'form']],
                                            view_type: 'form',
                                            target: 'new',
                                            context: {
                                                active_id: newSaleOrderId,
                                                product_id_from_js: variantIds,
                                                product_quantities: variantQuantities,
                                                default_product_tmpl_id:this.props.product_template_id,
                                                // related_printing_product_ids: data.related_printing_product_ids,
                                                // related_delivery_product_ids:data.related_delivery_product_ids,
                                                showCpq:this.show_cpq
                                            },
                                        });
                                    })
                                    .catch((error) => {
                                        console.error("Error calling ORM method:", error);
                                    });
                                }
                            }
                        }
                    }
                });
            }
            else
            {
                for (let matrixInput of inputs) {
                    if (matrixInput.value > 0) {
                        if (matrixInput.attributes.ptav_ids) {
                            let ptavIds = matrixInput.attributes.ptav_ids.nodeValue;
                            if (ptavIds) {
                                const ids = ptavIds.split(',').map(id => parseInt(id.trim()));
                                combinationIds = ids;
                                this.orm.call("product.template", "get_data_val", [this.props.product_template_id,combinationIds],{})
                                .then((data) => {
                                    if (data.variant_id) {
                                        variantIds.push(data.variant_id);
                                        variantQuantities[data.variant_id] = parseInt(matrixInput.value);
                                    }
                                    this.props.close();
                                    this.actionService.doAction({
                                        type: 'ir.actions.act_window',
                                        name: 'Printing Products',
                                        res_model: 'sale.line.properties.wiz',
                                        views: [[false, 'form']],
                                        view_type: 'form',
                                        target: 'new',
                                        context: {
                                            active_id : this.props.record.model.config.resId,
                                            product_id_from_js: variantIds,
                                            product_quantities: variantQuantities,
                                            default_product_tmpl_id:this.props.product_template_id,
                                            // related_printing_product_ids: data.related_printing_product_ids,
                                            // related_delivery_product_ids:data.related_delivery_product_ids,
                                            showCpq:this.show_cpq
                                        },
                                    });
                                })
                                .catch((error) => {
                                    console.error("Error calling ORM method:", error);
                                });
                            }
                        }
                    }
                }
            }
        }
    },
});

ProductMatrixDialog.template = 'pimcore_customization.productMatrixDialogInherit';
ProductMatrixDialog.props = {
    header: { type: Object },
    rows: { type: Object },
    editedCellAttributes: { type: String },
    product_template_id: { type: Number },
    record: { type: Object },
    close: { type: Function },
};
ProductMatrixDialog.components = { Dialog };