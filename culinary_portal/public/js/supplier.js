frappe.ui.form.on('Supplier', {
    refresh: function(frm) {
        // Add Dokan Vendor ID Sync button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Sync Dokan Vendor'), function() {
                sync_dokan_vendor(frm);
            }, __('WooCommerce'));
        }
    }
});


function sync_dokan_vendor(frm) {
    frappe.confirm(
        __('Sync Dokan Store for {0}?', [frm.doc.supplier_name || frm.doc.name]),
        function() {
            frappe.call({
                method: 'culinary_portal.custom_hooks.sync_supplier.sync_dokan_vendor_id',
                args: {
                    supplier_name: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Checking Dokan Stores...'),
                callback: function(r) {
                    if (r.message) {
                        const response = r.message;
                        
                        if (response.status === 'success') {
                            frappe.show_alert({
                                message: `✅ ${response.message}<br>Vendor ID: ${response.vendor_id}<br>Store: ${response.store_name}`,
                                indicator: 'green'
                            }, 10);
                            
                            // Reload form
                            frm.reload_doc();
                            
                        } else if (response.status === 'not_found') {
                            frappe.msgprint({
                                title: __('Store Not Found'),
                                message: `
                                    <p><strong>${response.message}</strong></p>
                                    <p>${__('Searched name')}: <code>${response.searched_name}</code></p>
                                    <p>${__('Total stores')}: ${response.total_stores}</p>
                                    <hr>
                                    <p><em>${__('Note: Store name must match exactly with Supplier Name.')}</em></p>
                                `,
                                indicator: 'orange'
                            });
                            
                        } else {
                            frappe.msgprint({
                                title: __('Error'),
                                message: response.message,
                                indicator: 'red'
                            });
                        }
                    }
                },
                error: function(r) {
                    frappe.msgprint({
                        title: __('API Error'),
                        message: __('Could not connect to Dokan API.'),
                        indicator: 'red'
                    });
                }
            });
        }
    );
}

