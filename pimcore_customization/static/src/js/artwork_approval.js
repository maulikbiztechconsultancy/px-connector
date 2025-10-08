/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";
$(document).ready(function () {
    $('select[name="approval_status"]').change(function () {
    let anySelected = false;
    $('select[name="approval_status"]').each(function () {
        const selectedValue = $(this).val();
        if (selectedValue) {
            anySelected = true;
            return false; // exit loop early, since we found one
        }
    });
    if (anySelected) {
        document.querySelector('input[name="All Product Approved"]').disabled = true;
    } else {
        document.querySelector('input[name="All Product Approved"]').disabled = false;
    }
});
});
publicWidget.registry.ArtworkApproval = publicWidget.Widget.extend({
    selector: ".submit-artwork",
    events: {
        "click": "_onSubmitArtwork",
    },

    _onSubmitArtwork: function (ev) {
        var isValid = true;
        var lineId;
        var allLineID = [];
        let html = $('#service_lines_wrapper').html();
        let $parsedHTML = $($.parseHTML(html));

        const isChecked = document.querySelector('input[name="All Product Approved"]').checked;
        if (isChecked){
            $parsedHTML.find('[data-line-id]').each(function () {
                let lineId = $(this).data('line-id');
                if (!allLineID.includes(lineId)) {
                    allLineID.push(lineId);
                }
            });
        }
        $('select[name="approval_status"]').each(function () {
            var input_value = $(this).val();
            var validationMessage = $(this).closest('td').find('.validation-message');
            var commentBox = $(this).closest('td').find('textarea[name="decline_message"]');
            var comment = (typeof commentBox !== 'undefined' && commentBox.val()) ? commentBox.val().trim() : '';


            if (!input_value && !isChecked) {
                validationMessage.text("Approval status is required").css("color", "red");
                isValid = false;
            }

            if (input_value === "reject" || input_value === "accept_with_change" && !isChecked) {
                if (!comment) {
                    commentBox.css("border", "1px solid red");
                    validationMessage.text("Comments are required for this selection").css("color", "red");
                    isValid = false;
                }
            }

        });

        $('select[name="approval_status"]').change(function () {
            var validationMessage = $(this).closest('td').find('.validation-message');
            if ($(this).val()) {
                validationMessage.text("");
            }
        });

        $('textarea[name="decline_message"]').on('input', function () {
            $(this).css("border", "");
            $(this).closest('td').find('.validation-message').text("");
        });

        if (!isValid && !isChecked) {
            return false;
        }

        var allRequests = {};  // Store requests grouped by line_id
        var order_id = this.el.attributes["data-order-id"].nodeValue
        var submit_type = this.el.dataset.submitType

        $('select[name="approval_status"]').each(function () {
            var line_id = $(this).closest('td').data('line-id');
            var selectedValue = $(this).val();
            var commentBox = $(this).closest('td').find('textarea[name="decline_message"]');
            var comment = (typeof commentBox !== 'undefined' && commentBox.val()) ? commentBox.val().trim() : '';
            if (selectedValue || comment) {
                if (!allRequests[line_id]) {
                    allRequests[line_id] = [];  
                }
                allRequests[line_id].push({
                    line_id : line_id || "",
                    approval_status: selectedValue || "",
                    comment: comment || ""
                });
            }
        });
        rpc('/my/artwork/approval', {
            data: allRequests,
            order_id: order_id,
            submit_type: submit_type,
            isChecked:isChecked,
            allLineID: allLineID ? allLineID : '',
        }).then(function (response) {
            var url = new URL(window.location.href);            
            if (url.searchParams.get('required_approval')) {
                url.searchParams.set('required_approval', false);
                url.searchParams.append('send_approval_mail', true);
                url.searchParams.append('submit_type', submit_type);
            } else {
                url.searchParams.append('send_approval_mail', true);
                url.searchParams.append('submit_type', submit_type);
            }
            window.location.href = url
        }).catch(function (error) {
            console.error("Error submitting data:", error);
        });
    },
});


