# Custom Products Manager

A comprehensive Odoo module for managing custom products, configurations, and bills of materials directly from sales orders.

## Features

### 🎯 **Easy Custom Product Creation**
- Create custom products directly from sales orders
- Template-based product creation for consistency
- Automatic product code generation
- Configurable product fields and specifications

### 🔧 **Interactive BOM Builder**
- Drag-and-drop component management
- Search and add components with real-time cost calculation
- Popular components suggestions based on similar products
- Component alternatives and supplier tracking
- Template import functionality

### 📊 **Advanced Cost Management**
- Real-time cost calculation with materials, labor, and overhead
- Suggested pricing based on target margins
- Component cost tracking and optimization
- Manufacturing complexity assessment

### 🎨 **User-Friendly Interface**
- Intuitive wizards for product creation
- Interactive dashboard with key metrics
- Enhanced sales order integration
- Mobile-responsive design

## Installation

1. Copy the module to your Odoo addons directory:
   ```bash
   cp -r custom_products_manager /path/to/odoo/addons/
   ```

2. Update your addons list and install the module:
   - Go to Apps > Update Apps List
   - Search for "Custom Products Manager"
   - Click Install

## Quick Start

### 1. Set Up Templates (Optional)
- Go to Custom Products > Configuration > Product Templates
- Create reusable templates with common configurations

### 2. Create Custom Products
**From Sales Orders:**
- Open any sales order
- Click "Create Custom Product" button
- Fill in product details and specifications
- The product will be automatically added to the order

**From the Module:**
- Go to Custom Products > Quick Actions > Create Custom Product
- Use the wizard to define your custom product

### 3. Build Bills of Materials
- Custom products can automatically create BOMs
- Use the interactive BOM Builder for detailed component management
- Import from templates or build from scratch

## Module Structure

```
custom_products_manager/
├── __manifest__.py              # Module manifest
├── models/                      # Core business logic
│   ├── custom_product.py        # Custom product configurations
│   ├── product_template.py      # Product extensions
│   ├── sale_order.py           # Sales order integration
│   └── mrp_bom.py              # BOM extensions
├── wizards/                     # Interactive wizards
│   ├── custom_product_creator.py
│   ├── bom_builder.py
│   └── bom_template_selector.py
├── views/                       # User interface definitions
│   ├── sale_order_views.xml
│   ├── product_views.xml
│   ├── wizard_views.xml
│   ├── mrp_views.xml
│   └── menu_views.xml
├── static/src/                  # Frontend assets
│   ├── js/                     # JavaScript widgets
│   └── xml/                    # QWeb templates
├── security/                    # Access rights
├── data/                       # Default data
└── README.md                   # This file
```

## Key Models

### `custom.product.config`
Stores custom product configurations, specifications, and pricing.

### `custom.product.template`
Reusable templates for creating similar custom products.

### `bom.builder.wizard`
Interactive wizard for building and managing bills of materials.

### `custom.product.creator`
Wizard for streamlined custom product creation from sales orders.

## Workflow

1. **Template Creation** (Optional): Set up reusable product templates
2. **Product Creation**: Create custom products from sales orders or directly
3. **BOM Building**: Define manufacturing requirements and costs
4. **Cost Analysis**: Review pricing and margins
5. **Manufacturing**: Create manufacturing orders from custom BOMs

## Integration

The module seamlessly integrates with:
- **Sales**: Enhanced sales orders with custom product creation
- **Manufacturing**: Custom BOMs with cost tracking and complexity management
- **Inventory**: Product variants and configurations
- **Purchase**: Supplier tracking for components

## Configuration

### Security Groups
- **Sales Team**: Can create and manage custom product configurations
- **Sales Manager**: Full access to all custom product features
- **Manufacturing User**: Can create and manage custom BOMs

### Settings
Access module settings through the dashboard or individual model configurations.

## Support

For custom products business needs, this module provides:
- ✅ Easy product creation on-the-fly
- ✅ Professional BOM management
- ✅ Cost tracking and pricing optimization
- ✅ Template-based efficiency
- ✅ Seamless Odoo integration

## Version
- **Odoo Version**: 17.0
- **Module Version**: 1.0.0
- **Category**: Sales/Manufacturing

---

*Built for businesses selling custom products who need easy-to-use tools for managing unique configurations and manufacturing requirements.*