# Culinary Portal

**Version:** 0.0.1  
**License:** MIT  
**Platform:** ERPNext v15 + Frappe Framework

Culinary Portal is a custom ERPNext application designed to integrate ERPNext with WooCommerce and Dokan marketplace. It provides seamless synchronization of products, categories, suppliers, and vendor data between ERPNext and WooCommerce/Dokan platforms.

---

## 🚀 Features

### 1️⃣ **Item Synchronization**
- ✅ Automatic sync of Items to WooCommerce products
- ✅ Real-time price updates (Standard Selling + Customer-specific prices)
- ✅ B2B King integration for group-based pricing
- ✅ Multi-category support (Item Group + Supplier categories)
- ✅ Image synchronization
- ✅ Stock status management
- ✅ Draft/Publish status based on pricing availability
- ✅ Automatic WooCommerce ID tracking

### 2️⃣ **Supplier Management**
- ✅ Automatic WooCommerce Category creation for Suppliers
- ✅ Dokan Vendor synchronization
- ✅ Single Supplier → Dokan Vendor matching
- ✅ Bulk Supplier → Dokan Vendor sync
- ✅ Category hierarchy support (parent: 303)
- ✅ Image and metadata sync

### 3️⃣ **Item Group Management**
- ✅ Automatic WooCommerce Category creation for Item Groups
- ✅ Category update on Item Group changes
- ✅ Category deletion on Item Group trash
- ✅ WooCommerce Category ID tracking

### 4️⃣ **Item Deletion**
- ✅ Automatic WooCommerce product deletion when Item is deleted from ERPNext
- ✅ Force delete with cleanup
- ✅ Error logging and handling

### 5️⃣ **Multilingual Support**
- ✅ English (default)
- ✅ Turkish (tr) translations
- ✅ Easy to add more languages

---

## 📦 Installation

### Prerequisites
- ERPNext v15.x
- Frappe v15.x
- WooCommerce REST API access
- (Optional) Dokan Pro plugin for vendor management

### Install Steps

1. **Clone the repository:**
```bash
cd ~/frappe-bench/apps
git clone [repository-url] culinary_portal
```

2. **Install the app:**
```bash
cd ~/frappe-bench
bench --site [site-name] install-app culinary_portal
```

3. **Build assets:**
```bash
bench build --app culinary_portal
```

4. **Restart services:**
```bash
bench restart
```

---

## ⚙️ Configuration

### 1. Site Configuration (`site_config.json`)

Add the following to your site's `site_config.json`:

```json
{
  "woocommerce_url": "https://your-wordpress-site.com",
  "consumer_key": "ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "consumer_secret": "cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "base_url": "https://your-erp-site.com"
}
```

**Note:** Get your Consumer Key and Secret from:
- WooCommerce → Settings → Advanced → REST API

### 2. WooCommerce Server DocType

Create a "WooCommerce Server" record:
- **Name:** www.temayolu.com (or your domain)
- **API Consumer Key:** Your WooCommerce REST API Consumer Key
- **API Consumer Secret:** Your WooCommerce REST API Consumer Secret

---

## 🎯 Usage

### Item Synchronization

#### Automatic Sync
Items are automatically synced to WooCommerce when:
- ✅ Item is created or updated
- ✅ Item Price is updated
- ✅ Standard Selling price is defined

#### Manual Sync (Bulk)
Use the Python function:
```python
frappe.call('culinary_portal.custom_hooks.create_item.sync_all_items_to_woocommerce')
```

#### Item Deletion
Items are automatically deleted from WooCommerce when deleted from ERPNext.

---

### Supplier & Dokan Vendor Sync

#### Single Supplier Sync
1. Open a Supplier document
2. Click **WooCommerce → Sync Dokan Vendor**
3. System will match Supplier name with Dokan Store name
4. Vendor ID will be saved to `custom_woocommerce_vendor_id`

#### Bulk Supplier Sync
1. Go to **Supplier List**
2. Select multiple Suppliers (checkbox)
3. Click **Bulk Sync Dokan Vendors**
4. View detailed sync results

**Matching Logic:**
- Exact match: `Supplier Name` == `Dokan Store Name` (case-insensitive)

---

### Item Group Sync

Item Groups are automatically synced as WooCommerce Categories:
- ✅ **on_update:** Creates or updates category
- ✅ **on_trash:** Deletes category from WooCommerce

---

## 🗂️ File Structure

```
culinary_portal/
├── culinary_portal/
│   ├── custom_hooks/
│   │   ├── create_item.py          # Item sync logic
│   │   ├── delete_item.py          # Item deletion handler
│   │   ├── sync_supplier.py        # Supplier & Dokan sync
│   │   └── create_category.py      # Item Group sync
│   ├── public/
│   │   └── js/
│   │       ├── item.js             # Item form customizations
│   │       ├── supplier.js         # Supplier form button
│   │       └── supplier_list.js    # Bulk sync button
│   ├── translations/
│   │   └── tr.csv                  # Turkish translations
│   ├── hooks.py                    # App hooks configuration
│   └── ...
└── README.md
```

---

## 🔧 Custom Fields Required

### Supplier DocType
- `custom_woocommerce_category_id` (Data) - WooCommerce Category ID
- `custom_woocommerce_vendor_id` (Data) - Dokan Vendor ID
- `custom_woocommerce_slug` (Data) - Optional slug
- `custom_email` (Data) - Supplier email
- `custom_phone` (Data) - Supplier phone

### Item DocType
- `custom_woocommerce_id` (Data) - WooCommerce Product ID

### Item Group DocType
- `custom_woocommerce_category_id` (Data) - WooCommerce Category ID

**Note:** These fields are automatically created via fixtures on app installation.

---

## 🔄 Hooks Configuration

### Document Events

```python
doc_events = {
    "Item": {
        "on_update": "culinary_portal.custom_hooks.create_item.handle_item_saved",
        "on_trash": "culinary_portal.custom_hooks.delete_item.handle_item_deleted",
    },
    "Item Price": {
        "on_update": "culinary_portal.custom_hooks.create_item.handle_item_saved",
    },
    "Item Group": {
        "on_update": "culinary_portal.custom_hooks.create_category.handle_item_group_after_insert",
        "after_rename": "culinary_portal.custom_hooks.create_category.handle_item_group_after_insert",
        "on_trash": "culinary_portal.custom_hooks.create_category.handle_item_group_on_trash",
    },
    "Supplier": {
        "on_update": "culinary_portal.custom_hooks.sync_supplier.handle_supplier_sync",
        "after_rename": "culinary_portal.custom_hooks.sync_supplier.handle_supplier_sync",
        "on_trash": "culinary_portal.custom_hooks.sync_supplier.handle_supplier_on_trash",
    }
}
```

### Client Scripts

```python
doctype_js = {
    "Item": "public/js/item.js",
    "Supplier": "public/js/supplier.js"
}

doctype_list_js = {
    "Supplier": "public/js/supplier_list.js"
}
```

---

## 📊 B2B King Integration

### Price List Mapping
The app supports B2B King customer group pricing:

1. **Customer → Price List:** Each customer has a price list with the same name
2. **Standard Selling:** Used as regular price for all groups
3. **Customer-specific prices:** Used as sale price for respective groups
4. **Meta Data:** Automatically generated for each customer group:
   - `b2bking_regular_product_price_group_{group_id}`
   - `b2bking_sale_product_price_group_{group_id}`

---

## 🌐 API Endpoints

### Whitelisted Functions

#### 1. Sync Single Dokan Vendor
```python
frappe.call({
    method: 'culinary_portal.custom_hooks.sync_supplier.sync_dokan_vendor_id',
    args: { supplier_name: 'Supplier Name' }
})
```

#### 2. Bulk Sync Dokan Vendors
```python
frappe.call({
    method: 'culinary_portal.custom_hooks.sync_supplier.bulk_sync_dokan_vendors',
    args: { supplier_names: ['Supplier1', 'Supplier2'] }
})
```

#### 3. Sync All Items
```python
frappe.call({
    method: 'culinary_portal.custom_hooks.create_item.sync_all_items_to_woocommerce'
})
```

#### 4. Collect B2B King Groups
```python
frappe.call({
    method: 'culinary_portal.custom_hooks.create_item.collect_customer_b2bking_groups'
})
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. **401 Unauthorized Error**
- ✅ Check Consumer Key and Secret in site_config.json
- ✅ Ensure WooCommerce REST API is enabled
- ✅ Verify API permissions (Read/Write)

#### 2. **Dokan Vendor Not Found**
- ✅ Check exact name match between Supplier and Store
- ✅ Verify Dokan plugin is active
- ✅ Check Dokan API endpoint: `/wp-json/dokan/v1/stores`

#### 3. **Category Not Created**
- ✅ Check parent category ID (default: 303)
- ✅ Verify WooCommerce API credentials
- ✅ Check error logs in ERPNext

#### 4. **Price Not Syncing**
- ✅ Ensure "Standard Selling" Price List exists
- ✅ Check Item Price records
- ✅ Verify customer-specific price lists

---

## 📝 Development Guidelines

### Code Standards
- ✅ Single Responsibility Principle
- ✅ Meaningful naming (English)
- ✅ Comments in Turkish
- ✅ No nested blocks beyond 2 levels
- ✅ Error logging with frappe.log_error
- ✅ No trial-and-error debugging

### Testing
- ✅ Manual testing before merge
- ✅ Automatic testing where applicable
- ✅ Log and verify all API responses

### Branch Strategy
- ✅ Never develop on main/master
- ✅ Use feature branches
- ✅ Regular pulls from main branch
- ✅ Clear commit messages (English)

---

## 📄 Translation

### Adding New Languages

1. Create translation file:
```bash
apps/culinary_portal/culinary_portal/translations/[lang_code].csv
```

2. Add translations:
```csv
English Text,Translated Text
Sync Dokan Vendor,Dokan Satıcısını Eşleştir
```

3. Build app:
```bash
bench build --app culinary_portal
```

### Supported Languages
- 🇬🇧 English (en) - Default
- 🇹🇷 Turkish (tr)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Contact: culinary@gmail.com

---

## 📜 License

MIT License

---

## 🙏 Credits

Developed for Culinary Portal by the ERPNext development team.

**Built with:**
- [Frappe Framework](https://frappeframework.com/)
- [ERPNext](https://erpnext.com/)
- [WooCommerce REST API](https://woocommerce.github.io/woocommerce-rest-api-docs/)
- [Dokan Multivendor](https://dokan.co/)

---

## 📈 Version History

### v0.0.1 (Initial Release)
- ✅ Item synchronization to WooCommerce
- ✅ Supplier → WooCommerce Category sync
- ✅ Supplier → Dokan Vendor sync (single & bulk)
- ✅ Item Group → WooCommerce Category sync
- ✅ Item deletion sync
- ✅ B2B King pricing integration
- ✅ Multi-category support
- ✅ Turkish translation
- ✅ Custom UI buttons and workflows

---

**Made with ❤️ for the culinary industry**
