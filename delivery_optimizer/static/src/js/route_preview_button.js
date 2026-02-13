/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Route Preview Button Widget
 * Shows a map icon button that displays a popover with Google Maps directions on hover/click
 */
class RoutePreviewButton extends Component {
    static template = xml`
        <div class="o_route_preview_button position-relative d-inline-block">
            <button
                class="btn btn-sm"
                t-att-class="state.loading ? 'btn-secondary' : 'btn-outline-primary'"
                t-on-mouseenter="onMouseEnter"
                t-on-mouseleave="onMouseLeave"
                t-on-click="onClick"
                t-att-disabled="state.loading"
                title="Preview Route">
                <i t-att-class="state.loading ? 'fa fa-spinner fa-spin' : 'fa fa-map-marker'"/>
            </button>

            <!-- Popover Card -->
            <div t-if="state.showPopover and state.routeInfo"
                 class="o_route_popover position-absolute bg-white shadow-lg rounded-3 p-0"
                 style="z-index: 1050; width: 400px; right: 0; top: 100%; margin-top: 8px;"
                 t-on-mouseenter="keepPopoverOpen"
                 t-on-mouseleave="onMouseLeave">

                <!-- Header -->
                <div class="bg-primary text-white p-3 rounded-top">
                    <h6 class="mb-0">
                        <i class="fa fa-truck me-2"/>
                        Route to <t t-esc="state.routeInfo.partner_name"/>
                    </h6>
                </div>

                <!-- Metrics -->
                <div class="d-flex border-bottom">
                    <div class="flex-fill text-center p-3 border-end">
                        <div class="h4 mb-0 text-primary">
                            <t t-esc="state.routeInfo.distance_text"/>
                        </div>
                        <small class="text-muted">Distance</small>
                    </div>
                    <div class="flex-fill text-center p-3">
                        <div class="h4 mb-0 text-success">
                            <t t-esc="state.routeInfo.duration_text"/>
                        </div>
                        <small class="text-muted">Drive Time</small>
                    </div>
                </div>

                <!-- Embedded Map -->
                <div class="p-2">
                    <iframe
                        t-att-src="state.routeInfo.embed_url"
                        width="100%"
                        height="250"
                        style="border:0; border-radius: 8px;"
                        allowfullscreen=""
                        loading="lazy"
                        referrerpolicy="no-referrer-when-downgrade">
                    </iframe>
                </div>

                <!-- Addresses -->
                <div class="p-3 bg-light small">
                    <div class="mb-2">
                        <strong><i class="fa fa-warehouse me-1 text-secondary"/> From:</strong>
                        <span class="text-muted ms-1" t-esc="state.routeInfo.warehouse_address"/>
                    </div>
                    <div>
                        <strong><i class="fa fa-map-pin me-1 text-danger"/> To:</strong>
                        <span class="text-muted ms-1" t-esc="state.routeInfo.delivery_address"/>
                    </div>
                </div>

                <!-- Actions -->
                <div class="p-3 border-top d-flex gap-2">
                    <a t-att-href="state.routeInfo.maps_url"
                       target="_blank"
                       class="btn btn-primary btn-sm flex-fill">
                        <i class="fa fa-external-link me-1"/>
                        Open in Google Maps
                    </a>
                    <button class="btn btn-outline-secondary btn-sm" t-on-click="closePopover">
                        Close
                    </button>
                </div>
            </div>

            <!-- Error State -->
            <div t-if="state.showPopover and state.error"
                 class="o_route_popover position-absolute bg-white shadow-lg rounded p-3"
                 style="z-index: 1050; width: 300px; right: 0; top: 100%; margin-top: 8px;">
                <div class="text-danger">
                    <i class="fa fa-exclamation-circle me-1"/>
                    <t t-esc="state.error"/>
                </div>
            </div>
        </div>
    `;

    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            showPopover: false,
            loading: false,
            routeInfo: null,
            error: null,
            keepOpen: false,
        });
        this.hideTimeout = null;
    }

    get pickingId() {
        return this.props.record.resId;
    }

    async fetchRouteInfo() {
        if (this.state.routeInfo) {
            return; // Already fetched
        }

        this.state.loading = true;
        this.state.error = null;

        try {
            const result = await this.orm.call(
                "stock.picking",
                "get_single_delivery_route_info",
                [[this.pickingId]]
            );

            if (result.success) {
                this.state.routeInfo = result;
            } else {
                this.state.error = result.error || "Failed to load route";
            }
        } catch (e) {
            this.state.error = e.message || "Failed to load route information";
        } finally {
            this.state.loading = false;
        }
    }

    onMouseEnter() {
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }
        this.state.showPopover = true;
        this.fetchRouteInfo();
    }

    keepPopoverOpen() {
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }
        this.state.keepOpen = true;
    }

    onMouseLeave() {
        this.state.keepOpen = false;
        this.hideTimeout = setTimeout(() => {
            if (!this.state.keepOpen) {
                this.state.showPopover = false;
            }
        }, 300);
    }

    onClick(ev) {
        ev.stopPropagation();
        this.state.showPopover = !this.state.showPopover;
        if (this.state.showPopover) {
            this.fetchRouteInfo();
        }
    }

    closePopover() {
        this.state.showPopover = false;
    }
}

registry.category("fields").add("route_preview_button", {
    component: RoutePreviewButton,
});
