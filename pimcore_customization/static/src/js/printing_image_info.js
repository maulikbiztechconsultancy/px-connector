/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { Component, onWillRender } from "@odoo/owl";

class CustomPopup extends Component {
     setup() {
        this.actionService = useService("action");
    }
}
CustomPopup.template = "pritxpand_community.CustomPopup"; // Define this template in XML

class CustomPrintingImageWidget extends Component {
    setup() {
        this.popover = usePopover(this.constructor.components.Popover, { position: "top" });
        this.orm = useService("orm");
        onWillRender(() => {
            this.initCalcData();
        })
    }
    async initCalcData() {
        try {
            const { data } = this.props.record;
            this.thumbnailName = this.props.record.data.printing_thumbnail_name;
            const resId = this.props.record._config.resId;

            if (!resId || typeof resId !== "number") {
                console.error("Invalid res_id:", resId);
                return;
            }

                // Search for attachments with the given res_id
            const attachments = await this.orm.call(
                "sale.order.line",    // The model name
                "get_attachments_so",    // The method name
                [resId]               // Arguments to pass (res_id)
            );

            this.attachmentImages = attachments.map(attachment => ({
                id: attachment.id,
                name: attachment.name,
                url: `data:${attachment.mimetype};base64,${attachment.datas}`
            }));

        } catch (error) {
            console.error("Error during initCalcData:", error);
        }
    }

    showPopup(ev) {
        this.popover.open(ev.currentTarget, {
            record: this.props.record,
            thumbnailName: this.thumbnailName, // Pass imageUrl to the popover
            attachmentImages : this.attachmentImages
        });
    }
}

CustomPrintingImageWidget.components = { Popover: CustomPopup };
CustomPrintingImageWidget.template = "pritxpand_community.PrintingImageWidget";

export const customPrintingImageWidget = {
    component: CustomPrintingImageWidget,
};
registry.category("view_widgets").add("custom_printing_image_widget", customPrintingImageWidget);

// export { CustomPrintingImageWidget };