/** @odoo-module **/

export async function createSaleOrder(orm, props) {
    const parentData = props.record.evalContext?.parent || props.record.evalContext || {};
    const saleOrderData = {
                    locked: parentData.locked || false,
                    partner_id: parentData.partner_id || false,
                    grid: parentData.grid || false,
                    grid_product_tmpl_id: parentData.grid_product_tmpl_id || false,
                    grid_update: parentData.grid_update || false,
                    recompute_delivery_price: parentData.recompute_delivery_price || false,
                    partner_invoice_id: parentData.partner_invoice_id|| false,
                    partner_shipping_id: parentData.partner_shipping_id|| false,
                    sale_order_template_id: parentData.sale_order_template_id || false,
                    count_line: parentData.count_line || 0,
                    count_for_approved_cycle_complete: parentData.count_for_approved_cycle_complete || 0,
                    validity_date: parentData.validity_date || new Date().toISOString().slice(0, 10),
                    date_order: parentData.date_order || new Date().toISOString().slice(0, 19).replace("T", " "),
                    show_update_pricelist: parentData.show_update_pricelist || false,
                    pricelist_id: parentData.pricelist_id || false,
                    company_id: parentData.company_id || false,
                    payment_term_id: parentData.payment_term_id || false,
                    order_line: parentData.order_line || [], // Ensure order lines are included
                    note: parentData.note || "",
                    sale_order_option_ids: parentData.sale_order_option_ids || [],
                    user_id: parentData.user_id || false,
                    team_id: parentData.team_id || false,
                    cart_recovery_email_sent: parentData.cart_recovery_email_sent || false,
                    require_signature: parentData.require_signature || false,
                    require_payment: parentData.require_payment || false,
                    prepayment_percent: parentData.prepayment_percent || 1,
                    client_order_ref: parentData.client_order_ref || false,
                    tag_ids: parentData.tag_ids || [],
                    report_grids: parentData.report_grids || false,
                    show_update_fpos: parentData.show_update_fpos || false,
                    fiscal_position_id: parentData.fiscal_position_id || false,
                    journal_id: parentData.journal_id || false,
                    warehouse_id: parentData.warehouse_id || false,
                    incoterm: parentData.incoterm || false,
                    incoterm_location: parentData.incoterm_location || false,
                    picking_policy: parentData.picking_policy || "direct",
                    commitment_date: parentData.commitment_date || false,
                    origin: parentData.origin || false,
                    opportunity_id: parentData.opportunity_id || false,
                    campaign_id: parentData.campaign_id || false,
                    medium_id: parentData.medium_id || false,
                    source_id: parentData.source_id || false,
                    signed_by: parentData.signed_by || false,
                    signed_on: parentData.signed_on || false,
                    signature: parentData.signature || false,
                };
    try {        
        const newSaleOrderId = await orm.call("sale.order", "create", [[saleOrderData]]);
        setTimeout(() => {
            props.record.model.config.resId = newSaleOrderId[0];
        }, 3000);  // 60000ms = 1 minute

        // Return created order ID immediately (before timeout delay)
        return newSaleOrderId[0];
    } catch (error) {
        console.error("Error creating Sale Order:", error);
        return null;
    }
}