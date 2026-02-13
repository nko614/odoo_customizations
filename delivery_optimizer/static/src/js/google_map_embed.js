/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Widget to embed Google Maps iframe in a form view
 * Fills parent container height automatically
 */
class GoogleMapEmbed extends Component {
    static template = xml`
        <div class="o_google_map_embed h-100 w-100" t-if="props.record.data[props.name]">
            <iframe
                t-att-src="props.record.data[props.name]"
                width="100%"
                height="100%"
                style="border:0; display:block; min-height: 450px;"
                allowfullscreen=""
                loading="lazy"
                referrerpolicy="no-referrer-when-downgrade">
            </iframe>
        </div>
        <div t-else="" class="text-muted text-center p-5 bg-light rounded h-100 d-flex flex-column align-items-center justify-content-center">
            <i class="fa fa-map-marker fa-4x mb-3 text-secondary"/>
            <p class="mb-0">No route available</p>
        </div>
    `;
    static props = { ...standardFieldProps };
}

registry.category("fields").add("google_map_embed", {
    component: GoogleMapEmbed,
});
