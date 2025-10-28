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
- ✅ Short description support
- ✅ Stock status management
- ✅ Draft/Publish status based on pricing availability
- ✅ Automatic WooCommerce ID tracking
- ✅ Dokan post_author integration (Vendor assignment)
- ✅ Automatic Vendor ID sync when missing
- ✅ Performance-optimized meta_data updates for price changes

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

### 5️⃣ **Customer & B2B Group Management**
- ✅ Automatic B2B Group creation in WordPress when Customer is saved
- ✅ WordPress User creation webhook integration
- ✅ Automatic Customer creation from WordPress User registration
- ✅ B2B Group assignment to WordPress Users
- ✅ Customer deletion syncs to WordPress (deletes User and B2B Group)
- ✅ Background job processing for delete operations
- ✅ Portal User ID tracking

### 6️⃣ **Multilingual Support**
- ✅ English (en) - default
- ✅ Turkish (tr) - Türkçe
- ✅ German (de) - Deutsch
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

5. **Set language (optional):**
```bash
# For Turkish
bench --site [site-name] set-config lang tr

# For German
bench --site [site-name] set-config lang de

# Build after language change
bench build --app culinary_portal
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
  "wp_user": "your-wordpress-username",
  "wp_app_key": "xxxx xxxx xxxx xxxx xxxx xxxx",
  "base_url": "https://your-erp-site.com"
}
```

**Configuration Details:**
- **woocommerce_url:** Your WordPress/WooCommerce site URL
- **consumer_key:** WooCommerce REST API Consumer Key
- **consumer_secret:** WooCommerce REST API Consumer Secret
- **wp_user:** WordPress username for Dokan API authentication
- **wp_app_key:** WordPress Application Password for Dokan API
- **base_url:** Your ERPNext site URL (for image URLs)

**How to get credentials:**
1. **WooCommerce API Keys:**
   - WooCommerce → Settings → Advanced → REST API → Add Key
   - Permissions: Read/Write

2. **WordPress Application Password:**
   - Users → Profile → Application Passwords
   - Create new application password for Dokan API access

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

**What happens during sync:**
1. Item data is sent to WooCommerce (creates/updates product)
2. Product is assigned to Supplier categories
3. B2B King pricing meta_data is updated
4. **Dokan post_author is set automatically:**
   - Item's first Supplier is identified
   - If Supplier has `custom_woocommerce_vendor_id`, it's used
   - If not, `sync_dokan_vendor_id` is called automatically to fetch and save it
   - Vendor ID is sent to Dokan API as `post_author`
   - Product is now owned by the vendor in Dokan

#### Manual Sync (Bulk)
Use the Python function:
```python
frappe.call('culinary_portal.custom_hooks.create_item.sync_all_items_to_woocommerce')
```

#### Item Deletion
Items are automatically deleted from WooCommerce when deleted from ERPNext.

#### Performance Optimizations
- **Item Price updates:** Only affected B2B group's meta_data is updated (not full product data)
- **Vendor ID caching:** Once fetched, vendor ID is stored in Supplier for reuse

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

### Customer & B2B Group Sync

#### Automatic B2B Group Creation (ERPNext → WordPress)

When a Customer is saved in ERPNext:
1. System checks if `custom_b2b_group_id` exists
2. If not, creates a new B2B King Group in WordPress:
   - **Endpoint:** `POST /wp-json/wp/v2/b2bking_group`
   - **Title:** Customer's `customer_name`
   - **Status:** `publish`
3. Saves B2B Group ID to `custom_b2b_group_id`
4. If `custom_portal_user_id` exists, assigns group to WordPress User:
   - **Endpoint:** `PUT /wp-json/wp/v2/users/{portal_user_id}`
   - **Payload:** `{"meta": {"b2bking_customergroup": ["{group_id}"]}}`

#### WordPress User Registration Webhook (WordPress → ERPNext)

When a user registers in WordPress:
1. **WordPress Webhook Configuration:**
   - **Event:** `customer.created` (WooCommerce webhook)
   - **Endpoint:** `{erp_url}/api/method/culinary_portal.culinary_portal.woocommerce_endpoint.user_created`
   - **Method:** POST

2. **ERPNext Processing:**
   - Receives user data (id, username, email, first_name, last_name)
   - Creates/Updates Customer:
     - `customer_name`: `first_name + " " + last_name` (fallback: username)
     - `woocommerce_identifier`: email
     - `custom_portal_user_id`: WordPress user ID
   - Creates B2B Group in WordPress
   - Assigns B2B Group to WordPress User

3. **Webhook Payload Example:**
```json
{
  "id": 70,
  "username": "johndoe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "customer"
}
```

#### Customer Deletion (ERPNext → WordPress)

When a Customer is deleted in ERPNext:
1. System enqueues background job to avoid blocking
2. **Background Job:**
   - Deletes WordPress User:
     - **Endpoint:** `DELETE /wp-json/wp/v2/users/{portal_user_id}`
     - **Params:** `force=true, reassign=1`
   - Deletes B2B King Group:
     - **Endpoint:** `DELETE /wp-json/wp/v2/b2bking_group/{b2b_group_id}`
     - **Params:** `force=true`
3. Customer is deleted immediately in ERPNext (no 500 error)
4. WordPress cleanup happens in background

#### API Functions

**Create B2B Group manually:**
```python
frappe.call({
    method: 'culinary_portal.custom_hooks.create_b2b_group.create_b2b_group_for_customer',
    args: { customer_name: 'Customer Name' }
})
```

---

## 🗂️ File Structure

```
culinary_portal/
├── culinary_portal/
│   ├── custom_hooks/
│   │   ├── create_item.py          # Item sync logic
│   │   ├── delete_item.py          # Item deletion handler
│   │   ├── sync_supplier.py        # Supplier & Dokan sync
│   │   ├── create_category.py      # Item Group sync
│   │   └── create_b2b_group.py     # Customer & B2B Group sync
│   ├── public/
│   │   └── js/
│   │       ├── item.js             # Item form customizations
│   │       ├── supplier.js         # Supplier form button
│   │       └── supplier_list.js    # Bulk sync button
│   ├── translations/
│   │   ├── tr.csv                  # Turkish translations
│   │   ├── en.csv                  # English translations
│   │   └── de.csv                  # German translations
│   ├── hooks.py                    # App hooks configuration
│   ├── woocommerce_endpoint.py     # Webhook endpoints
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
- `custom_short_description` (Text) - Product short description for WooCommerce

### Item Group DocType
- `custom_woocommerce_category_id` (Data) - WooCommerce Category ID

### Customer DocType
- `woocommerce_identifier` (Data) - Customer email for B2B King group matching
  - Used to fetch customer's B2B King group from WooCommerce
  - Each customer must have a Price List with the same name
- `custom_portal_user_id` (Data/Int) - WordPress User ID
  - Stores the WordPress user ID when customer is created from WordPress
- `custom_b2b_group_id` (Data/Int) - B2B King Group ID
  - Stores the WordPress B2B Group ID for this customer

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
    },
    "Customer": {
        "on_update": "culinary_portal.custom_hooks.create_b2b_group.handle_customer_b2b_group",
        "on_trash": "culinary_portal.custom_hooks.create_b2b_group.handle_customer_on_trash",
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

### Price Update Flow

#### Item Save/Update (Full Sync)
When an Item is saved:
1. All customers with `woocommerce_identifier` are fetched
2. For each customer, their B2B King group is retrieved from WooCommerce
3. Customer-specific price from Price List is used as `sale_price`
4. Standard Selling price is used as `regular_price`
5. Meta data for all groups is compiled and sent to WooCommerce

#### Item Price Update (Optimized Sync)
When an Item Price is updated:
1. **Only the specific Price List** (matching the customer) is processed
2. Only that customer's B2B King group meta_data is updated
3. No full product data is sent - **only meta_data payload**
4. This significantly reduces API calls and processing time

**Example:**
- Item has 50 customers with different prices
- Customer "ABC Company" price is updated in "ABC Company" Price List
- Only ABC Company's B2B group meta_data is updated (not all 50)
- Reduces sync time from ~10s to ~1s per price update

---

## 🌐 API Endpoints

### WooCommerce REST API Endpoints Used
- `GET/POST/PUT /wp-json/wc/v3/products` - Product management
- `GET/POST/PUT/DELETE /wp-json/wc/v3/products/categories` - Category management
- `GET /wp-json/wc/v3/customers` - Customer data for B2B King groups

### Dokan REST API Endpoints Used
- `GET /wp-json/dokan/v1/stores` - Fetch all Dokan vendor stores
- `PUT /wp-json/dokan/v1/products/{id}` - Update product post_author (vendor assignment)

### WordPress REST API Endpoints Used
- `POST /wp-json/wp/v2/b2bking_group` - Create B2B King Group
- `DELETE /wp-json/wp/v2/b2bking_group/{id}` - Delete B2B King Group
- `PUT /wp-json/wp/v2/users/{id}` - Update user (assign B2B Group)
- `DELETE /wp-json/wp/v2/users/{id}` - Delete user

### ERPNext Webhook Endpoints
- `POST /api/method/culinary_portal.culinary_portal.woocommerce_endpoint.user_created` - WordPress user registration webhook

### Whitelisted Functions (ERPNext)

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

#### 5. Create B2B Group for Customer
```python
frappe.call({
    method: 'culinary_portal.custom_hooks.create_b2b_group.create_b2b_group_for_customer',
    args: { customer_name: 'Customer Name' }
})
```

---

## 🔧 Technical Implementation Details

### Dokan Vendor Assignment (post_author)

When a product is created or updated in WooCommerce, the system automatically assigns it to the correct Dokan vendor:

#### Flow:
```
Item Save/Update
    ↓
Send to WooCommerce API (create/update product)
    ↓
Get WooCommerce Product ID
    ↓
Get Item's first Supplier
    ↓
Check if Supplier has custom_woocommerce_vendor_id
    ↓
    ├─ YES → Use existing vendor ID
    ↓
    └─ NO → Call sync_dokan_vendor_id()
              ↓
              Fetch all Dokan Stores via API
              ↓
              Match Supplier name with Store name
              ↓
              Save vendor ID to Supplier
              ↓
              Use vendor ID
    ↓
Send PUT request to Dokan API
Endpoint: /wp-json/dokan/v1/products/{product_id}
Auth: WordPress Application Password
Payload: {"post_author": "{vendor_id}"}
    ↓
Product now owned by Vendor in Dokan
```

#### Key Functions:
1. **`update_dokan_post_author(item_code, wc_product_id)`**
   - Main function that handles vendor assignment
   - Automatically called after WooCommerce product creation/update
   - Skips execution if:
     - Item has no suppliers
     - wp_user or wp_app_key not configured
     - Meta-data-only updates (Item Price changes)

2. **`sync_dokan_vendor_id(supplier_name)`**
   - Fetches all Dokan stores from WordPress
   - Matches Supplier name with Store name (case-insensitive)
   - Saves vendor ID to `custom_woocommerce_vendor_id`
   - Returns status: success/not_found/error

#### Authentication:
- **WooCommerce API:** Uses Consumer Key + Consumer Secret (OAuth1)
- **Dokan API:** Uses WordPress username + Application Password (Basic Auth)

#### Error Handling:
- All errors are logged to ERPNext Error Log
- Console debug messages for troubleshooting
- Non-blocking: If vendor assignment fails, product sync still succeeds

### Product Status Logic

Products are automatically assigned `draft` or `publish` status based on:

#### Draft Status (not visible in store):
- ✅ Item is disabled (`disabled = 1`)
- ✅ Item has no Standard Selling price
- ✅ Standard Selling price is 0

#### Publish Status (visible in store):
- ✅ Item is enabled (`disabled = 0`)
- ✅ Item has valid Standard Selling price (> 0)

**User Notification:**
- When a product has no price, user sees: "Product price not defined. Product will be added as Draft"
- Product will automatically switch to `publish` when price is added

### Category Hierarchy

Products are assigned to multiple categories:

1. **Item Group Category:** Primary category from Item's Item Group
2. **Supplier Category:** Secondary category from Item's Supplier(s)
3. **Parent Category (303):** All categories have parent ID 303 (default)

**Example:**
```json
"categories": [
  {"id": 150},          // Item Group category
  {"id": 200, "parent": 303},  // Supplier category
  {"id": 303}           // Parent category
]
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

#### 5. **Dokan post_author Not Updated**
- ✅ Verify `wp_user` and `wp_app_key` in site_config.json
- ✅ Check if Item has Supplier assigned (supplier_items table)
- ✅ Ensure Supplier has `custom_woocommerce_vendor_id` or can be matched to Dokan Store
- ✅ Check Dokan API endpoint: `/wp-json/dokan/v1/products/{id}`
- ✅ Verify WordPress Application Password is valid
- ✅ Check Error Log for Dokan API errors

#### 6. **Vendor ID Auto-Sync Failed**
- ✅ Check if Supplier name matches Dokan Store name (exact match, case-insensitive)
- ✅ Verify Dokan stores are accessible via API
- ✅ Check network connectivity to WordPress site
- ✅ Review error logs for detailed sync errors

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
- 🇹🇷 Turkish (tr) - Türkçe
- 🇩🇪 German (de) - Deutsch

### Translation Coverage
All user-facing messages are translated:
- ✅ Dokan Vendor sync messages
- ✅ Product sync notifications
- ✅ Error messages
- ✅ Status alerts
- ✅ Bulk operation results

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
- ✅ Multilingual support (English, Turkish, German)
- ✅ Custom UI buttons and workflows
- ✅ Dokan post_author integration (auto vendor assignment)
- ✅ Automatic Vendor ID sync when missing
- ✅ Short description support for products
- ✅ Performance-optimized Item Price updates
- ✅ WordPress Application Password authentication for Dokan API
- ✅ Customer & B2B Group synchronization
- ✅ WordPress User registration webhook integration
- ✅ Automatic Customer creation from WordPress User
- ✅ B2B Group assignment to WordPress Users
- ✅ Customer/User/B2B Group deletion sync
- ✅ Background job processing for delete operations

---

**Made with ❤️ for the culinary industry**
