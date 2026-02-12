/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { BarcodePickingModel } from "@stock_barcode/models/barcode_picking_model";
import { MainComponent } from "@stock_barcode/components/main";

// Extend the BarcodePickingModel to handle state field
patch(BarcodePickingModel.prototype, {
    setup() {
        super.setup(...arguments);
        this.itemState = 'new';
    },

    setItemState(state) {
        this.itemState = state;
        // Apply to current line if exists
        if (this.selectedLine) {
            this.selectedLine.item_state = state;
        }
    }
});

// Extend the MainComponent to add state selector
patch(MainComponent.prototype, {
    setup() {
        super.setup(...arguments);
        this.itemState = 'new';
    },

    onMounted() {
        super.onMounted(...arguments);
        // Add event listener for state selector after component mounts
        const selector = document.getElementById('item_state_selector');
        if (selector) {
            selector.addEventListener('change', (ev) => {
                this.itemState = ev.target.value;
                if (this.env.model.setItemState) {
                    this.env.model.setItemState(this.itemState);
                }
                // Store in session
                sessionStorage.setItem('barcode_item_state', this.itemState);
            });

            // Restore saved state
            const savedState = sessionStorage.getItem('barcode_item_state');
            if (savedState) {
                selector.value = savedState;
                this.itemState = savedState;
            }
        }
    }
});