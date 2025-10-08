/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { onWillStart, useState, useSubEnv } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import {ProductConfiguratorDialog} from '@sale/js/product_configurator_dialog/product_configurator_dialog';
import { createSaleOrder } from "./sale_order_utils.js";

export const GlobalData = {
    dialogIsOpen: false,
};

patch(ProductConfiguratorDialog, {
    props: {
        ...ProductConfiguratorDialog.props,
        record: Object,
    },
});

patch (ProductConfiguratorDialog.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.title = _t("Configure your product");
        this.actionService = useService("action");
        this.state = useState({
            products: [],
            optionalProducts: [],
        });
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

        useSubEnv({
            mainProductTmplId: this.props.productTemplateId,
            currencyId: this.props.currencyId,
            addProduct: this._addProduct.bind(this),
            removeProduct: this._removeProduct.bind(this),
            setQuantity: this._setQuantity.bind(this),
            updateProductTemplateSelectedPTAV: this._updateProductTemplateSelectedPTAV.bind(this),
            updatePTAVCustomValue: this._updatePTAVCustomValue.bind(this),
            isPossibleCombination: this._isPossibleCombination,
        });

        onWillStart(async () => {
            GlobalData.dialogIsOpen = false;
            const { products, optional_products } = await this._loadData(this.props.edit);
            this.state.products = products;
            this.state.optionalProducts = optional_products;
            for (const customValue of this.props.customPtavs) {
                this._updatePTAVCustomValue(
                    this.env.mainProductTmplId,
                    customValue.ptavId,
                    customValue.value
                );
            }
            this._checkExclusions(this.state.products[0]);
        });
    },


    onDiscard() {
        GlobalData.dialogIsOpen = false;

        // Call props like original
        if (!this.props.edit) {
            this.props.discard?.(); // optional chaining avoids crash
        }
        this.props.close?.();
    },

    async _onNextConfigureProduct() {
        if (!this.isPossibleConfiguration() || this.props.edit) return;

        let saleOrderId = this.props.record.model.config.resId; // Just check the plain sale_order_id here
        if(!saleOrderId)
        {
            createSaleOrder(this.orm, this.props).then((newSaleOrderId) => {
                    this.props.record.model.config.resId = newSaleOrderId;
            });
        }

        let variantIds = [];
        let variantQuantities = {};
        const defaultProductTmplId = this.props.productTemplateId;

        for (const product of this.state.products) {
            variantQuantities[product.id] = product.quantity;

            if (
                !product.id &&
                product.attribute_lines.some(ptal => ptal.create_variant === "dynamic")
            ) {
                const productId = await this._createProduct(product);
                product.id = parseInt(productId);
            }

            if (product.product_tmpl_id !== defaultProductTmplId) {
                variantIds.push(product.id);
            }
        }

        await this.props.save(
            this.state.products.find(
                p => p.product_tmpl_id === this.env.mainProductTmplId
            ),
            this.state.products.filter(
                p => p.product_tmpl_id !== this.env.mainProductTmplId
            ),
        );
        this.props.close();
        this.actionService.doAction({
        type: 'ir.actions.act_window',
        name: 'Printing Products',
        res_model: 'sale.line.properties.wiz',
        views: [[false, 'form']],
        view_type: 'form',
        target: 'new',
        context: {
            active_id: this.props.record.evalContext.id,
            product_id_from_js: variantIds,
            product_quantities: variantQuantities,
            default_product_tmpl_id: defaultProductTmplId,
            showCpq: this.show_cpq,
        },
    });
    }
    },
)