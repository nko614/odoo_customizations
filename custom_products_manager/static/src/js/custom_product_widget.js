/** @odoo-module **/

import { Component, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class CustomProductWidget extends Component {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.searchInputRef = useRef("searchInput");
        
        onMounted(() => {
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }
        });
    }

    async onSearchInput(ev) {
        const searchTerm = ev.target.value;
        if (searchTerm.length >= 3) {
            try {
                const products = await this.orm.searchRead(
                    "product.product",
                    [
                        "|", "|",
                        ["name", "ilike", searchTerm],
                        ["default_code", "ilike", searchTerm],
                        ["barcode", "ilike", searchTerm],
                        ["purchase_ok", "=", true],
                        ["detailed_type", "in", ["product", "consu"]]
                    ],
                    ["id", "name", "default_code", "standard_price"],
                    { limit: 20 }
                );
                
                this.displaySearchResults(products);
            } catch (error) {
                this.notification.add("Error searching products", { type: "danger" });
            }
        }
    }

    displaySearchResults(products) {
        const resultsContainer = document.getElementById('search_results');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = '';
        
        if (products.length === 0) {
            resultsContainer.innerHTML = '<div class="text-muted">No products found</div>';
            return;
        }

        products.forEach(product => {
            const productElement = document.createElement('div');
            productElement.className = 'list-group-item list-group-item-action';
            productElement.style.cursor = 'pointer';
            productElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${product.name}</strong>
                        ${product.default_code ? `<br><small class="text-muted">${product.default_code}</small>` : ''}
                    </div>
                    <span class="badge badge-primary">${product.standard_price.toFixed(2)}</span>
                </div>
            `;
            
            productElement.addEventListener('click', () => {
                this.addProductToComponents(product);
            });
            
            resultsContainer.appendChild(productElement);
        });
    }

    async addProductToComponents(product) {
        try {
            // Add product to BOM components
            await this.orm.call(
                "bom.builder.wizard",
                "action_add_component",
                [this.props.record.resId],
                { context: { product_id: product.id } }
            );
            
            this.notification.add(`Added ${product.name} to components`, { type: "success" });
            
            // Refresh the component lines
            await this.props.record.load();
            
        } catch (error) {
            this.notification.add("Error adding component", { type: "danger" });
        }
    }

    async onQuickAdd(ev) {
        const productId = parseInt(ev.target.dataset.productId);
        if (productId) {
            try {
                const product = await this.orm.searchRead(
                    "product.product",
                    [["id", "=", productId]],
                    ["name"],
                    { limit: 1 }
                );
                
                if (product.length > 0) {
                    await this.addProductToComponents(product[0]);
                }
            } catch (error) {
                this.notification.add("Error adding component", { type: "danger" });
            }
        }
    }
}

CustomProductWidget.template = "custom_products_manager.CustomProductWidget";

registry.category("fields").add("custom_product_search", CustomProductWidget);