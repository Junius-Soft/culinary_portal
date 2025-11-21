frappe.ui.form.on('Customer', {
    refresh: function(frm) {
        // Add Customer Enable/Disable button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Customer Enable/Disable'), function() {
                toggle_customer_status(frm);
            }, __('Portal'));
        }
    }
});


function toggle_customer_status(frm) {
    const customer_name = frm.doc.customer_name || frm.doc.name;
    const action_text = __('Toggle Customer Status for {0}?', [customer_name]);
    
    frappe.confirm(
        action_text,
        function() {
            frappe.call({
                method: 'culinary_portal.custom_hooks.sync_supplier.toggle_customer_status',
                args: {
                    customer_name: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Updating Customer Status...'),
                callback: function(r) {
                    if (r.message) {
                        const response = r.message;
                        
                        if (response.status === 'success') {
                            frappe.show_alert({
                                message: `✅ ${response.message}`,
                                indicator: 'green'
                            }, 5);
                            
                            // Reload form to show updated disabled status
                            frm.reload_doc();
                            
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
                        message: __('Could not update customer status.'),
                        indicator: 'red'
                    });
                }
            });
        }
    );
}

