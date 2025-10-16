frappe.listview_settings['Supplier'] = {
    onload: function(listview) {
        // Bulk Dokan Vendor Sync button
        listview.page.add_inner_button(__('Bulk Sync Dokan Vendors'), function() {
            let selected_suppliers = listview.get_checked_items();
            
            if (selected_suppliers.length === 0) {
                frappe.msgprint(__('Please select at least one Supplier'));
                return;
            }
            
            bulk_sync_dokan_vendors(selected_suppliers);
        });
    }
};


function bulk_sync_dokan_vendors(selected_suppliers) {
    const supplier_names = selected_suppliers.map(item => item.name);
    
    frappe.confirm(
        __('Sync Dokan Vendors for {0} Suppliers?', [supplier_names.length]) + '<br><br>' +
        `<small>${__('Selected Suppliers')}: ${supplier_names.slice(0, 5).join(', ')}${supplier_names.length > 5 ? '...' : ''}</small>`,
        function() {
            frappe.call({
                method: 'culinary_portal.custom_hooks.sync_supplier.bulk_sync_dokan_vendors',
                args: {
                    supplier_names: supplier_names
                },
                freeze: true,
                freeze_message: __('Syncing Dokan Stores...'),
                callback: function(r) {
                    if (r.message) {
                        const response = r.message;
                        
                        if (response.status === 'success' || response.status === 'partial') {
                            frappe.show_alert({
                                message: `
                                    <strong>${__('Bulk Sync Completed')}</strong><br>
                                    ${response.message}
                                `,
                                indicator: response.status === 'success' ? 'green' : 'orange'
                            }, 15);
                            
                            // Refresh list view
                            cur_list.refresh();
                            
                            // Show detailed results (optional)
                            if (response.not_found_count > 0 || response.error_count > 0) {
                                frappe.msgprint({
                                    title: __('Sync Results'),
                                    message: response.message,
                                    indicator: response.status === 'success' ? 'green' : 'orange',
                                    primary_action: {
                                        label: __('OK'),
                                        action: function() {
                                            // Close dialog
                                        }
                                    }
                                });
                            }
                            
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

