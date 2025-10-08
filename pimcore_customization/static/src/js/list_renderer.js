/* @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {

    async onDeleteRecord(record) {
        this.keepColumnWidths = true;
        if (this.editedRecord && this.editedRecord !== record) {
            const left = await this.props.list.leaveEditMode();
            if (!left) {
                return;
            }
        }
        if (this.activeActions.onDelete) {
            const display_type = record.data.display_type;

            if (display_type === "line_section") {
                const allLines = this.props.list.records;
                const index = allLines.findIndex(line => line === record);

                const linesToDelete = [];
                for (let i = index + 1; i < allLines.length; i++) {
                    const nextLine = allLines[i];
                    if (nextLine.data.display_type === "line_section") {
                        break;
                    }
                    linesToDelete.push(nextLine);
                }

                // Delete all lines under the section
                for (const line of linesToDelete) {
                    await this.activeActions.onDelete(line);
                }

                return this.activeActions.onDelete(record);
            }

            this.activeActions.onDelete(record);
        }
    }

});
