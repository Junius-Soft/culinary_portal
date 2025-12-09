frappe.ui.form.on('Customer', {
    refresh: function(frm) {
        // Add Customer Enable/Disable button only if custom_role is 'customerpendingapprove'
        if (!frm.is_new() && frm.doc.custom_role === 'customerpendingapprove') {
            frm.add_custom_button(__('Approve Customer'), function() {
                toggle_customer_status(frm);
            });
        }

        // Refresh Agreements butonu ekle
        if (!frm.is_new() && frm.fields_dict.custom_customer_agreements) {
            frm.add_custom_button(__('Refresh Agreements'), function() {
                frm.reload_doc();
            }, __('Actions'));
        }

        // Customer Agreements table'ını stillendir
        if (!frm.is_new() && frm.fields_dict.custom_customer_agreements) {
            style_customer_agreements_grid(frm);
        }
    }
});


function toggle_customer_status(frm) {
    // Önce responsible_kitchen kontrolü
    if (!frm.doc.responsible_kitchen || (typeof frm.doc.responsible_kitchen === 'string' && frm.doc.responsible_kitchen.trim() === '')) {
        frappe.msgprint({
            title: __('Warning'),
            message: __('Responsible Kitchen field cannot be empty. Please fill this field before approving the customer.'),
            indicator: 'orange'
        });
        return;
    }

    // Confirm modal'ı önce göster (save'den önce)
    const customer_name = frm.doc.customer_name || frm.doc.name;
    const action_text = __('Toggle Customer Status for {0}?', [customer_name]);
    
    frappe.confirm(
        action_text,
        function() {
            // "Yes" tıklandığında önce formu kaydet
            frm.save().then(function() {
                // Form kaydedildikten sonra reload et ve backend çağrısını yap
                frm.reload_doc();
                
                // Reload tamamlandıktan sonra backend çağrısı yap
                setTimeout(function() {
                    // Backend'e approve çağrısı yap
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
                                    
                                    // Sayfayı tamamen yenile (güncel verileri görmek için)
                                    setTimeout(function() {
                                        window.location.reload();
                                    }, 1500);
                                    
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
                }, 500);
            }).catch(function(err) {
                // Save hatası durumunda
                frappe.msgprint({
                    title: __('Save Error'),
                    message: __('Could not save the form. Please check for validation errors.'),
                    indicator: 'red'
                });
            });
        }
    );
}

function style_customer_agreements_grid(frm) {
    // Customer Agreements grid'ine stil ve fonksiyon ekle
    if (!frm.fields_dict.custom_customer_agreements) {
        return;
    }

    // Grid'e özel CSS ekle
    setTimeout(function() {
        // Status sütununa renkli badge ekle
        frm.fields_dict.custom_customer_agreements.grid.wrapper.find('.grid-body .rows').on('DOMNodeInserted', function() {
            // Status sütununa renkli badge ekle
            $(this).find('[data-fieldname="status"]').each(function() {
                let status_text = $(this).text().trim();
                let badge_class = 'secondary';
                
                if (status_text === 'Active') badge_class = 'success';
                else if (status_text === 'Expired') badge_class = 'danger';
                else if (status_text === 'Cancelled') badge_class = 'dark';
                else if (status_text === 'Not Started') badge_class = 'warning';
                
                if (status_text && !$(this).find('.badge').length) {
                    $(this).html(`<span class="badge badge-${badge_class}">${status_text}</span>`);
                }
            });

            // name1 (Agreement) sütununa icon ekle
            $(this).find('[data-fieldname="name1"] a').each(function() {
                if (!$(this).find('.fa-file-text').length) {
                    $(this).prepend('<i class="fa fa-file-text" style="margin-right: 5px; color: #2490ef;"></i>');
                    $(this).css('font-weight', '600');
                }
            });
        });
    }, 500);
}

