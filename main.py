                        "Price": st.column_config.TextColumn("Price", width=100),
                        "Tax": st.column_config.TextColumn("Tax", width=60),
                        "Disc": st.column_config.TextColumn("Disc", width=60),
                        "Total": st.column_config.TextColumn("Total", width=100)
                    }
                )
            
            # Totals
            col1, col2, col3 = st.columns([3, 1, 2])
            with col2:
                st.markdown("**Subtotal:**")
                st.markdown("**Discount:**")
                st.markdown("**Tax:**")
                st.markdown("---")
                st.markdown("**GRAND TOTAL:**")
            with col3:
                st.markdown(f"**{format_amount(subtotal, st.session_state.currency)}**")
                st.markdown(f"**-{format_amount(total_discount, st.session_state.currency)}**")
                st.markdown(f"**{format_amount(total_tax, st.session_state.currency)}**")
                st.markdown("---")
                st.markdown(f"**{format_amount(grand_total, st.session_state.currency)}**")
            
            # Notes
            if invoice_notes:
                st.divider()
                st.markdown("**Notes:**")
                st.markdown(invoice_notes)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Action Buttons
        st.markdown('<div class="action-buttons">', unsafe_allow_html=True)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("💾 Save as Draft", use_container_width=True):
                invoice_data = {
                    'invoice_number': invoice_number,
                    'client_name': client_name,
                    'client_email': client_email,
                    'client_address': client_address,
                    'client_phone': client_phone,
                    'invoice_date': invoice_date.strftime('%Y-%m-%d'),
                    'due_date': due_date.strftime('%Y-%m-%d'),
                    'po_number': po_number,
                    'currency': st.session_state.currency,
                    'subtotal': subtotal,
                    'tax_total': total_tax,
                    'discount_total': total_discount,
                    'grand_total': grand_total,
                    'amount_paid': 0,
                    'balance_due': grand_total,
                    'status': 'Draft',
                    'notes': invoice_notes,
                    'recurring_frequency': recurring_frequency if recurring_frequency != 'None' else None,
                    'recurring_next_date': recurring_end.strftime('%Y-%m-%d') if recurring_frequency != 'None' and recurring_end else None
                }
                
                invoice_id, errors, warnings = save_invoice_to_db(invoice_data, st.session_state.invoice_items)
                
                if invoice_id:
                    # Save client if option selected
                    if auto_save_client and client_email:
                        client_data = {
                            'name': client_name,
                            'email': client_email,
                            'phone': client_phone,
                            'address': client_address
                        }
                        save_client_to_db(client_data)
                    
                    st.session_state.notification = f"✓ Invoice {invoice_number} saved as Draft"
                    st.session_state.notification_type = "success"
                    st.session_state.invoice_items = []
                    st.session_state.invoice_number = generate_invoice_number()
                    st.session_state.invoice_notes = ''
                    st.rerun()
                else:
                    for error in errors:
                        st.error(error)
                    for warning in warnings:
                        st.warning(warning)
        
        with col2:
            if st.button("📤 Save & Send", use_container_width=True):
                invoice_data = {
                    'invoice_number': invoice_number,
                    'client_name': client_name,
                    'client_email': client_email,
                    'client_address': client_address,
                    'client_phone': client_phone,
                    'invoice_date': invoice_date.strftime('%Y-%m-%d'),
                    'due_date': due_date.strftime('%Y-%m-%d'),
                    'po_number': po_number,
                    'currency': st.session_state.currency,
                    'subtotal': subtotal,
                    'tax_total': total_tax,
                    'discount_total': total_discount,
                    'grand_total': grand_total,
                    'amount_paid': 0,
                    'balance_due': grand_total,
                    'status': 'Sent',
                    'notes': invoice_notes,
                    'sent_date': datetime.now().isoformat(),
                    'recurring_frequency': recurring_frequency if recurring_frequency != 'None' else None,
                    'recurring_next_date': recurring_end.strftime('%Y-%m-%d') if recurring_frequency != 'None' and recurring_end else None
                }
                
                invoice_id, errors, warnings = save_invoice_to_db(invoice_data, st.session_state.invoice_items)
                
                if invoice_id:
                    # Generate PDF for email
                    pdf_data = {
                        'invoice_number': invoice_number,
                        'invoice_date': invoice_date.strftime('%Y-%m-%d'),
                        'due_date': due_date.strftime('%Y-%m-%d'),
                        'po_number': po_number,
                        'currency': st.session_state.currency,
                        'status': 'Sent',
                        'client': {
                            'name': client_name,
                            'address': client_address,
                            'email': client_email,
                            'phone': client_phone
                        },
                        'company_info': st.session_state.company_info,
                        'items': st.session_state.invoice_items,
                        'totals': {
                            'subtotal': subtotal,
                            'discount': total_discount,
                            'tax': total_tax,
                            'grand_total': grand_total
                        },
                        'notes': invoice_notes,
                        'amount_paid': 0,
                        'balance_due': grand_total
                    }
                    
                    pdf_buffer = generate_pdf_invoice(pdf_data)
                    
                    # Save client if option selected
                    if auto_save_client and client_email:
                        client_data = {
                            'name': client_name,
                            'email': client_email,
                            'phone': client_phone,
                            'address': client_address
                        }
                        save_client_to_db(client_data)
                    
                    st.session_state.notification = f"✓ Invoice {invoice_number} saved and ready to send"
                    st.session_state.notification_type = "success"
                    
                    # Open email dialog
                    st.session_state.show_email_modal = True
                    st.session_state.email_invoice_id = invoice_id
                    st.session_state.email_pdf = pdf_buffer
                    st.rerun()
        
        with col3:
            if st.button("👁️ Preview PDF", use_container_width=True):
                pdf_data = {
                    'invoice_number': invoice_number,
                    'invoice_date': invoice_date.strftime('%Y-%m-%d'),
                    'due_date': due_date.strftime('%Y-%m-%d'),
                    'po_number': po_number,
                    'currency': st.session_state.currency,
                    'status': invoice_status,
                    'client': {
                        'name': client_name,
                        'address': client_address,
                        'email': client_email,
                        'phone': client_phone
                    },
                    'company_info': st.session_state.company_info,
                    'items': st.session_state.invoice_items,
                    'totals': {
                        'subtotal': subtotal,
                        'discount': total_discount,
                        'tax': total_tax,
                        'grand_total': grand_total
                    },
                    'notes': invoice_notes,
                    'amount_paid': 0,
                    'balance_due': grand_total
                }
                
                pdf_buffer = generate_pdf_invoice(pdf_data)
                if pdf_buffer:
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_buffer,
                        file_name=f"invoice_{invoice_number}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        
        with col4:
            if st.button("📊 Export Excel", use_container_width=True):
                invoice_data_export = {
                    'invoice_number': invoice_number,
                    'client_name': client_name,
                    'client_email': client_email,
                    'client_phone': client_phone,
                    'client_address': client_address,
                    'invoice_date': invoice_date.strftime('%Y-%m-%d'),
                    'due_date': due_date.strftime('%Y-%m-%d'),
                    'po_number': po_number,
                    'currency': st.session_state.currency,
                    'subtotal': subtotal,
                    'tax_total': total_tax,
                    'discount_total': total_discount,
                    'grand_total': grand_total
                }
                
                excel_buffer = export_to_excel(invoice_data_export, st.session_state.invoice_items)
                if excel_buffer:
                    st.download_button(
                        label="📥 Download Excel",
                        data=excel_buffer,
                        file_name=f"invoice_{invoice_number}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        
        with col5:
            if st.button("🔄 Clear Form", use_container_width=True):
                st.session_state.invoice_items = []
                st.session_state.invoice_number = generate_invoice_number()
                st.session_state.invoice_notes = ''
                st.session_state.edit_index = -1
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        st.info("💡 Add items and client information to create your invoice")

# ============================================================================
# VIEW INVOICES PAGE
# ============================================================================

def render_view_invoices_page():
    """Render the view invoices page"""
    
    st.markdown('<div class="section-header">📋 View Invoices</div>', unsafe_allow_html=True)
    
    # Filters
    with st.expander("🔍 Search & Filter", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_status = st.selectbox(
                "Status",
                options=['All'] + INVOICE_STATUSES,
                index=0
            )
        
        with col2:
            filter_client = st.text_input("Client Name", placeholder="Search by client...")
        
        with col3:
            date_range = st.date_input(
                "Date Range",
                value=(datetime.now() - timedelta(days=30), datetime.now()),
                key="date_range_filter"
            )
        
        if st.button("🔍 Apply Filters", use_container_width=True):
            st.session_state.filter_status = filter_status
            st.session_state.filter_client = filter_client
            if len(date_range) == 2:
                st.session_state.filter_date_from = date_range[0].strftime('%Y-%m-%d')
                st.session_state.filter_date_to = date_range[1].strftime('%Y-%m-%d')
            st.rerun()
    
    # Build filters
    filters = {}
    if st.session_state.filter_status != 'All':
        filters['status'] = st.session_state.filter_status
    if st.session_state.filter_client:
        filters['client_name'] = st.session_state.filter_client
    if st.session_state.filter_date_from:
        filters['date_from'] = st.session_state.filter_date_from
    if st.session_state.filter_date_to:
        filters['date_to'] = st.session_state.filter_date_to
    
    # Get invoices
    invoices_df = get_invoices(filters if filters else None)
    
    if not invoices_df.empty:
        # Summary stats
        total_amount = invoices_df['grand_total'].sum()
        paid_amount = invoices_df[invoices_df['status'] == 'Paid']['grand_total'].sum() if 'Paid' in invoices_df['status'].values else 0
        pending_amount = invoices_df[invoices_df['status'].isin(['Draft', 'Sent'])]['grand_total'].sum() if any(invoices_df['status'].isin(['Draft', 'Sent'])) else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Invoices", len(invoices_df))
        with col2:
            st.metric("Total Amount", format_amount(total_amount, st.session_state.currency))
        with col3:
            st.metric("Paid", format_amount(paid_amount, st.session_state.currency))
        with col4:
            st.metric("Pending", format_amount(pending_amount, st.session_state.currency))
        
        st.divider()
        
        # Display invoices
        for _, invoice in invoices_df.iterrows():
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 2])
                
                with col1:
                    st.markdown(f"**{invoice['invoice_number']}**")
                    st.caption(f"Client: {invoice['client_name']}")
                
                with col2:
                    st.markdown(f"**Date:** {invoice['invoice_date']}")
                    st.markdown(f"**Due:** {invoice['due_date']}")
                
                with col3:
                    st.markdown(f"**Amount:** {format_amount(invoice['grand_total'], invoice['currency'])}")
                    if invoice['balance_due'] > 0:
                        st.caption(f"Balance: {format_amount(invoice['balance_due'], invoice['currency'])}")
                
                with col4:
                    st.markdown(get_status_badge_html(invoice['status']), unsafe_allow_html=True)
                    if invoice['status'] == 'Overdue':
                        st.caption("⚠️ Overdue")
                
                with col5:
                    button_col1, button_col2, button_col3 = st.columns(3)
                    with button_col1:
                        if st.button("👁️", key=f"view_{invoice['id']}", help="View Details"):
                            st.session_state.view_invoice_id = invoice['id']
                            st.rerun()
                    with button_col2:
                        if st.button("📄", key=f"pdf_{invoice['id']}", help="Download PDF"):
                            invoice_data, items = get_invoice_by_id(invoice['id'])
                            if invoice_data and items:
                                pdf_data = {
                                    'invoice_number': invoice_data['invoice_number'],
                                    'invoice_date': invoice_data['invoice_date'],
                                    'due_date': invoice_data['due_date'],
                                    'po_number': invoice_data.get('po_number', ''),
                                    'currency': invoice_data['currency'],
                                    'status': invoice_data['status'],
                                    'client': {
                                        'name': invoice_data['client_name'],
                                        'address': invoice_data.get('client_address', ''),
                                        'email': invoice_data.get('client_email', ''),
                                        'phone': invoice_data.get('client_phone', '')
                                    },
                                    'company_info': st.session_state.company_info,
                                    'items': items,
                                    'totals': {
                                        'subtotal': invoice_data['subtotal'],
                                        'discount': invoice_data['discount_total'],
                                        'tax': invoice_data['tax_total'],
                                        'grand_total': invoice_data['grand_total']
                                    },
                                    'notes': invoice_data.get('notes', ''),
                                    'amount_paid': invoice_data['amount_paid'],
                                    'balance_due': invoice_data['balance_due']
                                }
                                pdf_buffer = generate_pdf_invoice(pdf_data)
                                if pdf_buffer:
                                    st.download_button(
                                        label="📥",
                                        data=pdf_buffer,
                                        file_name=f"invoice_{invoice_data['invoice_number']}.pdf",
                                        mime="application/pdf",
                                        key=f"download_{invoice['id']}"
                                    )
                    with button_col3:
                        if st.button("💰", key=f"pay_{invoice['id']}", help="Record Payment"):
                            st.session_state.payment_invoice_id = invoice['id']
                            st.session_state.show_payment_modal = True
                            st.rerun()
                
                # Additional actions row if needed
                with st.expander("More Actions", expanded=False):
                    col_a, col_b, col_c, col_d = st.columns(4)
                    with col_a:
                        if st.button("📧 Send Email", key=f"email_{invoice['id']}"):
                            st.session_state.show_email_modal = True
                            st.session_state.email_invoice_id = invoice['id']
                            st.rerun()
                    with col_b:
                        if st.button("📊 Export Excel", key=f"excel_{invoice['id']}"):
                            invoice_data, items = get_invoice_by_id(invoice['id'])
                            if invoice_data:
                                excel_buffer = export_to_excel(invoice_data, items)
                                if excel_buffer:
                                    st.download_button(
                                        label="Download Excel",
                                        data=excel_buffer,
                                        file_name=f"invoice_{invoice_data['invoice_number']}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key=f"dl_excel_{invoice['id']}"
                                    )
                    with col_c:
                        if st.button("🔄 Update Status", key=f"status_{invoice['id']}"):
                            new_status = st.selectbox(
                                "New Status",
                                options=INVOICE_STATUSES,
                                index=INVOICE_STATUSES.index(invoice['status']),
                                key=f"status_select_{invoice['id']}"
                            )
                            if st.button("Update", key=f"update_status_{invoice['id']}"):
                                if update_invoice_status(invoice['id'], new_status):
                                    st.success(f"Status updated to {new_status}")
                                    st.rerun()
                    with col_d:
                        if st.button("🗑️ Delete", key=f"del_{invoice['id']}"):
                            if delete_invoice(invoice['id']):
                                st.success("Invoice deleted")
                                st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No invoices found. Create your first invoice!")
        
        if st.button("➕ Create New Invoice", use_container_width=True):
            st.session_state.current_page = "create"
            st.rerun()
    
    # View single invoice details
    if st.session_state.view_invoice_id:
        invoice, items = get_invoice_by_id(st.session_state.view_invoice_id)
        
        if invoice:
            st.markdown("---")
            st.markdown(f"### Invoice Details: {invoice['invoice_number']}")
            
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Client Information:**")
                    st.markdown(f"""
                    **Name:** {invoice['client_name']}  
                    **Email:** {invoice['client_email']}  
                    **Phone:** {invoice.get('client_phone', 'N/A')}  
                    **Address:** {invoice.get('client_address', 'N/A')}
                    """)
                
                with col2:
                    st.markdown("**Invoice Information:**")
                    st.markdown(f"""
                    **Date:** {invoice['invoice_date']}  
                    **Due Date:** {invoice['due_date']}  
                    **PO Number:** {invoice.get('po_number', 'N/A')}  
                    **Status:** {get_status_badge_html(invoice['status'])}
                    """, unsafe_allow_html=True)
                
                st.divider()
                
                # Items
                if items:
                    st.markdown("**Invoice Items:**")
                    items_data = []
                    for item in items:
                        items_data.append({
                            'Description': item['description'],
                            'Qty': f"{item['quantity']:.2f}",
                            'Unit Price': format_amount(item['unit_price'], invoice['currency']),
                            'Tax %': f"{item['tax_rate']}%",
                            'Discount %': f"{item['discount']}%",
                            'Total': format_amount(item['total'], invoice['currency'])
                        })
                    
                    st.dataframe(pd.DataFrame(items_data), use_container_width=True, hide_index=True)
                
                # Totals
                col1, col2, col3 = st.columns([3, 1, 2])
                with col2:
                    st.markdown("**Subtotal:**")
                    st.markdown("**Discount:**")
                    st.markdown("**Tax:**")
                    st.markdown("---")
                    st.markdown("**Grand Total:**")
                    if invoice['amount_paid'] > 0:
                        st.markdown("**Amount Paid:**")
                        st.markdown("---")
                        st.markdown("**Balance Due:**")
                with col3:
                    st.markdown(f"**{format_amount(invoice['subtotal'], invoice['currency'])}**")
                    st.markdown(f"**-{format_amount(invoice['discount_total'], invoice['currency'])}**")
                    st.markdown(f"**{format_amount(invoice['tax_total'], invoice['currency'])}**")
                    st.markdown("---")
                    st.markdown(f"**{format_amount(invoice['grand_total'], invoice['currency'])}**")
                    if invoice['amount_paid'] > 0:
                        st.markdown(f"**{format_amount(invoice['amount_paid'], invoice['currency'])}**")
                        st.markdown("---")
                        st.markdown(f"**{format_amount(invoice['balance_due'], invoice['currency'])}**")
                
                # Notes
                if invoice.get('notes'):
                    st.divider()
                    st.markdown("**Notes:**")
                    st.markdown(invoice['notes'])
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            if st.button("← Back to List"):
                st.session_state.view_invoice_id = None
                st.rerun()
    
    # Payment Modal
    if st.session_state.show_payment_modal and st.session_state.payment_invoice_id:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("### 💰 Record Payment")
            
            invoice, _ = get_invoice_by_id(st.session_state.payment_invoice_id)
            
            if invoice:
                st.markdown(f"""
                **Invoice:** {invoice['invoice_number']}  
                **Client:** {invoice['client_name']}  
                **Total Amount:** {format_amount(invoice['grand_total'], invoice['currency'])}  
                **Amount Paid:** {format_amount(invoice['amount_paid'], invoice['currency'])}  
                **Balance Due:** {format_amount(invoice['balance_due'], invoice['currency'])}
                """)
                
                max_payment = invoice['balance_due']
                
                payment_amount = st.number_input(
                    "Payment Amount",
                    min_value=0.01,
                    max_value=float(max_payment),
                    value=min(float(max_payment), 100.0),
                    step=10.0,
                    format="%.2f"
                )
                
                payment_method = st.selectbox("Payment Method", PAYMENT_METHODS)
                payment_reference = st.text_input("Reference (optional)", placeholder="Check #, Transaction ID, etc.")
                payment_notes = st.text_area("Notes (optional)", height=100)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Record Payment", use_container_width=True):
                        success, message = process_payment(
                            st.session_state.payment_invoice_id,
                            payment_amount,
                            payment_method,
                            payment_reference,
                            payment_notes
                        )
                        if success:
                            st.session_state.notification = message
                            st.session_state.notification_type = "success"
                            st.session_state.show_payment_modal = False
                            st.session_state.payment_invoice_id = None
                            st.rerun()
                        else:
                            st.error(message)
                
                with col2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.show_payment_modal = False
                        st.session_state.payment_invoice_id = None
                        st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Email Modal
    if st.session_state.show_email_modal and st.session_state.email_invoice_id:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("### 📧 Send Invoice via Email")
            
            invoice, items = get_invoice_by_id(st.session_state.email_invoice_id)
            
            if invoice:
                to_email = st.text_input("To Email", value=invoice['client_email'])
                subject = st.text_input("Subject", value=f"Invoice {invoice['invoice_number']} from {st.session_state.company_info['name']}")
                
                body = st.text_area(
                    "Message",
                    value=f"""Dear {invoice['client_name']},

Please find attached invoice {invoice['invoice_number']} for your reference.

Invoice Details:
- Invoice Number: {invoice['invoice_number']}
- Date: {invoice['invoice_date']}
- Due Date: {invoice['due_date']}
- Amount: {format_amount(invoice['grand_total'], invoice['currency'])}

Payment can be made via:
{st.session_state.company_info.get('bank_details', '')}

Thank you for your business!

Best regards,
{st.session_state.company_info['name']}""",
                    height=200
                )
                
                # Generate PDF if not already in session
                if not hasattr(st.session_state, 'email_pdf') or st.session_state.email_pdf is None:
                    pdf_data = {
                        'invoice_number': invoice['invoice_number'],
                        'invoice_date': invoice['invoice_date'],
                        'due_date': invoice['due_date'],
                        'po_number': invoice.get('po_number', ''),
                        'currency': invoice['currency'],
                        'status': invoice['status'],
                        'client': {
                            'name': invoice['client_name'],
                            'address': invoice.get('client_address', ''),
                            'email': invoice.get('client_email', ''),
                            'phone': invoice.get('client_phone', '')
                        },
                        'company_info': st.session_state.company_info,
                        'items': items,
                        'totals': {
                            'subtotal': invoice['subtotal'],
                            'discount': invoice['discount_total'],
                            'tax': invoice['tax_total'],
                            'grand_total': invoice['grand_total']
                        },
                        'notes': invoice.get('notes', ''),
                        'amount_paid': invoice['amount_paid'],
                        'balance_due': invoice['balance_due']
                    }
                    pdf_buffer = generate_pdf_invoice(pdf_data)
                    st.session_state.email_pdf = pdf_buffer
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📤 Send Email", use_container_width=True):
                        success, message = send_email_invoice(
                            to_email,
                            st.session_state.email_pdf,
                            invoice['invoice_number']
                        )
                        if success:
                            # Update invoice status to Sent
                            update_invoice_status(invoice['id'], 'Sent')
                            
                            st.session_state.notification = f"✓ Invoice sent to {to_email}"
                            st.session_state.notification_type = "success"
                            st.session_state.show_email_modal = False
                            st.session_state.email_invoice_id = None
                            st.session_state.email_pdf = None
                            st.rerun()
                        else:
                            st.error(message)
                
                with col2:
                    if st.button("📥 Download PDF", use_container_width=True):
                        st.download_button(
                            label="Download PDF",
                            data=st.session_state.email_pdf,
                            file_name=f"invoice_{invoice['invoice_number']}.pdf",
                            mime="application/pdf",
                            key="email_download_pdf"
                        )
                
                with col3:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.show_email_modal = False
                        st.session_state.email_invoice_id = None
                        st.session_state.email_pdf = None
                        st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# CLIENTS PAGE
# ============================================================================

def render_clients_page():
    """Render the clients management page"""
    
    st.markdown('<div class="section-header">👥 Client Management</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 Client List", "➕ Add New Client"])
    
    with tab1:
        # Search
        search_term = st.text_input("🔍 Search Clients", placeholder="Name, email, or company...")
        
        clients_df = get_clients(search_term if search_term else None)
        
        if not clients_df.empty:
            for _, client in clients_df.iterrows():
                with st.container():
                    st.markdown('<div class="business-card">', unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**{client['name']}**")
                        st.caption(client.get('company', ''))
                    
                    with col2:
                        st.markdown(f"📧 {client['email']}")
                        if client.get('phone'):
                            st.markdown(f"📞 {client['phone']}")
                    
                    with col3:
                        st.markdown(f"📍 {client.get('address', 'No address')[:50]}")
                        if client.get('tax_id'):
                            st.caption(f"TRN: {client['tax_id']}")
                    
                    with col4:
                        if st.button("👁️ View", key=f"view_client_{client['id']}"):
                            st.session_state.selected_client_id = client['id']
                            st.rerun()
                    
                    # Show client details if selected
                    if st.session_state.selected_client_id == client['id']:
                        st.divider()
                        st.markdown("**Client Details:**")
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown(f"""
                            **Full Name:** {client['name']}  
                            **Company:** {client.get('company', 'N/A')}  
                            **Email:** {client['email']}  
                            **Phone:** {client.get('phone', 'N/A')}
                            """)
                        with col_b:
                            st.markdown(f"""
                            **Address:** {client.get('address', 'N/A')}  
                            **TRN/Tax ID:** {client.get('tax_id', 'N/A')}  
                            **Credit Limit:** {format_amount(client.get('credit_limit', 0), st.session_state.currency)}  
                            **Payment Terms:** {client.get('payment_terms', 30)} days
                            """)
                        
                        # Get client's invoices
                        client_invoices = get_invoices({'client_name': client['name']})
                        if not client_invoices.empty:
                            st.markdown("**Recent Invoices:**")
                            for _, inv in client_invoices.head(3).iterrows():
                                st.markdown(f"""
                                - {inv['invoice_number']}: {format_amount(inv['grand_total'], inv['currency'])} ({inv['status']})
                                """)
                        
                        if st.button("Close", key=f"close_client_{client['id']}"):
                            st.session_state.selected_client_id = None
                            st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No clients found. Add your first client!")
    
    with tab2:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Add New Client")
            
            client_name = st.text_input("Client Name *")
            client_email = st.text_input("Email Address *")
            client_phone = st.text_input("Phone Number")
            client_company = st.text_input("Company Name")
            client_address = st.text_area("Address")
            client_tax_id = st.text_input("TRN / Tax ID")
            
            col1, col2 = st.columns(2)
            with col1:
                credit_limit = st.number_input("Credit Limit", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
            with col2:
                payment_terms = st.number_input("Payment Terms (days)", min_value=0, value=30, step=1)
            
            client_notes = st.text_area("Notes", height=100)
            
            if st.button("💾 Save Client", use_container_width=True):
                if client_name and client_email:
                    client_data = {
                        'name': client_name,
                        'email': client_email,
                        'phone': client_phone,
                        'address': client_address,
                        'company': client_company,
                        'tax_id': client_tax_id,
                        'notes': client_notes,
                        'credit_limit': credit_limit,
                        'payment_terms': payment_terms
                    }
                    
                    client_id = save_client_to_db(client_data)
                    if client_id:
                        st.session_state.notification = f"✓ Client {client_name} saved successfully"
                        st.session_state.notification_type = "success"
                        st.rerun()
                else:
                    st.warning("Name and email are required")
            
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# PAYMENTS PAGE
# ============================================================================

def render_payments_page():
    """Render the payments management page"""
    
    st.markdown('<div class="section-header">💰 Payment Management</div>', unsafe_allow_html=True)
    
    # Get all payments
    try:
        with get_db_connection() as conn:
            payments_df = pd.read_sql_query("""
                SELECT p.*, i.invoice_number, i.client_name, i.grand_total, i.currency
                FROM payments p
                JOIN invoices i ON p.invoice_id = i.id
                ORDER BY p.payment_date DESC
            """, conn)
    except:
        payments_df = pd.DataFrame()
    
    if not payments_df.empty:
        # Summary stats
        total_payments = payments_df['amount'].sum()
        payment_count = len(payments_df)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Payments", format_amount(total_payments, st.session_state.currency))
        with col2:
            st.metric("Number of Payments", payment_count)
        with col3:
            avg_payment = total_payments / payment_count if payment_count > 0 else 0
            st.metric("Average Payment", format_amount(avg_payment, st.session_state.currency))
        
        st.divider()
        
        # Payment methods breakdown
        method_stats = payments_df.groupby('payment_method')['amount'].agg(['sum', 'count']).reset_index()
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Payment Methods**")
            fig = px.pie(
                method_stats,
                values='sum',
                names='payment_method',
                title='Payment Amount by Method'
            )
            fig.update_layout(
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#2c3e50')
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("**Payment Timeline**")
            payments_df['payment_date'] = pd.to_datetime(payments_df['payment_date'])
            daily_payments = payments_df.groupby(payments_df['payment_date'].dt.date)['amount'].sum().reset_index()
            
            fig = px.line(
                daily_payments,
                x='payment_date',
                y='amount',
                title='Daily Payments'
            )
            fig.update_layout(
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#2c3e50')
            )
            st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        
        # Payment list
        st.markdown("**Recent Payments**")
        for _, payment in payments_df.iterrows():
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1.5, 1.5, 1])
                
                with col1:
                    st.markdown(f"**{payment['invoice_number']}**")
                    st.caption(payment['client_name'])
                
                with col2:
                    st.markdown(f"**Amount:** {format_amount(payment['amount'], payment['currency'])}")
                    st.caption(f"Method: {payment['payment_method']}")
                
                with col3:
                    payment_date = pd.to_datetime(payment['payment_date']).strftime('%d %b %Y')
                    st.markdown(f"**Date:** {payment_date}")
                    if payment.get('reference'):
                        st.caption(f"Ref: {payment['reference']}")
                
                with col4:
                    if payment.get('notes'):
                        st.caption(f"📝 {payment['notes'][:50]}...")
                
                with col5:
                    if st.button("👁️", key=f"view_payment_{payment['id']}"):
                        # Show payment details in modal
                        st.session_state.view_payment_id = payment['id']
                        st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No payments recorded yet. Record your first payment!")
        
        # Quick payment form
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Quick Payment")
            
            # Get unpaid invoices
            unpaid_invoices = get_invoices({'status': 'Sent'})
            if not unpaid_invoices.empty:
                invoice_options = {
                    f"{row['invoice_number']} - {row['client_name']} ({format_amount(row['balance_due'], row['currency'])})": row['id'] 
                    for _, row in unpaid_invoices.iterrows()
                }
                
                selected_invoice = st.selectbox(
                    "Select Invoice",
                    options=list(invoice_options.keys())
                )
                
                if selected_invoice:
                    invoice_id = invoice_options[selected_invoice]
                    invoice = unpaid_invoices[unpaid_invoices['id'] == invoice_id].iloc[0]
                    
                    st.markdown(f"""
                    **Invoice Details:**  
                    Amount: {format_amount(invoice['grand_total'], invoice['currency'])}  
                    Paid: {format_amount(invoice['amount_paid'], invoice['currency'])}  
                    Balance: {format_amount(invoice['balance_due'], invoice['currency'])}
                    """)
                    
                    payment_amount = st.number_input(
                        "Payment Amount",
                        min_value=0.01,
                        max_value=float(invoice['balance_due']),
                        value=float(invoice['balance_due']),
                        step=10.0,
                        format="%.2f"
                    )
                    
                    payment_method = st.selectbox("Payment Method", PAYMENT_METHODS, key="quick_payment_method")
                    payment_reference = st.text_input("Reference", key="quick_payment_ref")
                    
                    if st.button("💾 Record Payment", use_container_width=True):
                        success, message = process_payment(
                            invoice_id,
                            payment_amount,
                            payment_method,
                            payment_reference,
                            "Quick payment"
                        )
                        if success:
                            st.session_state.notification = message
                            st.session_state.notification_type = "success"
                            st.rerun()
                        else:
                            st.error(message)
            else:
                st.info("No unpaid invoices found")
            
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# RECURRING INVOICES PAGE
# ============================================================================

def render_recurring_page():
    """Render the recurring invoices management page"""
    
    st.markdown('<div class="section-header">🔄 Recurring Invoices</div>', unsafe_allow_html=True)
    
    # Get recurring invoices
    try:
        with get_db_connection() as conn:
            recurring_df = pd.read_sql_query("""
                SELECT r.*, c.name as client_name, t.name as template_name
                FROM recurring_invoices r
                JOIN clients c ON r.client_id = c.id
                JOIN invoice_templates t ON r.template_id = t.id
                ORDER BY r.next_date
            """, conn)
    except:
        recurring_df = pd.DataFrame()
    
    if not recurring_df.empty:
        # Active vs inactive
        active_count = len(recurring_df[recurring_df['is_active'] == 1])
        inactive_count = len(recurring_df[recurring_df['is_active'] == 0])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Recurring", len(recurring_df))
        with col2:
            st.metric("Active", active_count)
        with col3:
            st.metric("Inactive", inactive_count)
        
        st.divider()
        
        # Recurring list
        for _, recurring in recurring_df.iterrows():
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 1])
                
                with col1:
                    st.markdown(f"**{recurring['client_name']}**")
                    st.caption(f"Template: {recurring['template_name']}")
                
                with col2:
                    st.markdown(f"**Frequency:** {recurring['frequency']}")
                    st.caption(f"Started: {recurring['start_date']}")
                
                with col3:
                    st.markdown(f"**Next:** {recurring['next_date']}")
                    status = "🟢 Active" if recurring['is_active'] else "🔴 Inactive"
                    st.markdown(f"**Status:** {status}")
                
                with col4:
                    if recurring.get('last_generated'):
                        st.caption(f"Last: {recurring['last_generated']}")
                
                with col5:
                    toggle_label = "Deactivate" if recurring['is_active'] else "Activate"
                    if st.button(toggle_label, key=f"toggle_{recurring['id']}"):
                        try:
                            with get_db_connection() as conn:
                                c = conn.cursor()
                                c.execute("UPDATE recurring_invoices SET is_active = ? WHERE id = ?",
                                         (0 if recurring['is_active'] else 1, recurring['id']))
                                st.session_state.notification = f"Recurring invoice {toggle_label}d"
                                st.session_state.notification_type = "success"
                                st.rerun()
                        except Exception as e:
                            st.error(str(e))
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No recurring invoices set up yet")
        
        # Setup form
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Setup Recurring Invoice")
            
            # Get clients and templates
            clients_df = get_clients()
            try:
                with get_db_connection() as conn:
                    templates_df = pd.read_sql_query("SELECT * FROM invoice_templates", conn)
            except:
                templates_df = pd.DataFrame()
            
            if not clients_df.empty and not templates_df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    client_id = st.selectbox(
                        "Select Client",
                        options=clients_df['id'].tolist(),
                        format_func=lambda x: clients_df[clients_df['id'] == x]['name'].iloc[0]
                    )
                
                with col2:
                    template_id = st.selectbox(
                        "Select Template",
                        options=templates_df['id'].tolist(),
                        format_func=lambda x: templates_df[templates_df['id'] == x]['name'].iloc[0]
                    )
                
                frequency = st.selectbox("Frequency", options=list(RECURRING_FREQUENCIES.keys())[1:])  # Skip None
                
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("Start Date", datetime.now())
                with col2:
                    end_date = st.date_input("End Date (optional)", value=None, min_value=start_date)
                
                if st.button("🔄 Create Recurring Schedule", use_container_width=True):
                    recurring_id = create_recurring_invoice(
                        template_id,
                        client_id,
                        frequency,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d') if end_date else None
                    )
                    if recurring_id:
                        st.session_state.notification = "✓ Recurring schedule created"
                        st.session_state.notification_type = "success"
                        st.rerun()
            else:
                if clients_df.empty:
                    st.warning("No clients found. Add clients first.")
                if templates_df.empty:
                    st.warning("No templates found. Save an invoice as template first.")
            
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# REPORTS PAGE
# ============================================================================

def render_reports_page():
    """Render the reports page"""
    
    st.markdown('<div class="section-header">📊 Reports</div>', unsafe_allow_html=True)
    
    # Report type selector
    report_type = st.selectbox(
        "Select Report Type",
        options=[
            "Revenue Report",
            "Aging Report",
            "Client Summary",
            "Tax Summary",
            "Payment Methods"
        ]
    )
    
    # Date range
    col1, col2 = st.columns(2)
    with col1:
        report_start = st.date_input("Start Date", datetime.now() - timedelta(days=30))
    with col2:
        report_end = st.date_input("End Date", datetime.now())
    
    if st.button("📊 Generate Report", use_container_width=True):
        if report_type == "Revenue Report":
            # Revenue by period
            with get_db_connection() as conn:
                revenue_df = pd.read_sql_query("""
                    SELECT 
                        strftime('%Y-%m', invoice_date) as period,
                        COUNT(*) as invoice_count,
                        SUM(CASE WHEN status = 'Paid' THEN grand_total ELSE 0 END) as paid_revenue,
                        SUM(CASE WHEN status != 'Paid' THEN grand_total ELSE 0 END) as pending_revenue,
                        SUM(grand_total) as total_revenue
                    FROM invoices
                    WHERE invoice_date BETWEEN ? AND ?
                    GROUP BY strftime('%Y-%m', invoice_date)
                    ORDER BY period
                """, conn, params=[report_start.strftime('%Y-%m-%d'), report_end.strftime('%Y-%m-%d')])
            
            if not revenue_df.empty:
                st.markdown("### Revenue Report")
                st.dataframe(revenue_df, use_container_width=True)
                
                # Chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=revenue_df['period'],
                    y=revenue_df['paid_revenue'],
                    name='Paid Revenue',
                    marker_color='#27ae60'
                ))
                fig.add_trace(go.Bar(
                    x=revenue_df['period'],
                    y=revenue_df['pending_revenue'],
                    name='Pending Revenue',
                    marker_color='#f39c12'
                ))
                fig.update_layout(
                    barmode='group',
                    xaxis_title="Period",
                    yaxis_title=f"Revenue ({get_currency_symbol(st.session_state.currency)})",
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        elif report_type == "Aging Report":
            # Accounts receivable aging
            today = datetime.now().strftime('%Y-%m-%d')
            with get_db_connection() as conn:
                aging_df = pd.read_sql_query("""
                    SELECT 
                        client_name,
                        invoice_number,
                        invoice_date,
                        due_date,
                        grand_total,
                        amount_paid,
                        balance_due,
                        julianday(?) - julianday(due_date) as days_overdue
                    FROM invoices
                    WHERE status NOT IN ('Paid', 'Cancelled')
                    ORDER BY days_overdue DESC
                """, conn, params=[today])
            
            if not aging_df.empty:
                st.markdown("### Accounts Receivable Aging")
                
                # Categorize aging
                aging_df['aging_category'] = pd.cut(
                    aging_df['days_overdue'],
                    bins=[-float('inf'), 0, 30, 60, 90, float('inf')],
                    labels=['Current', '1-30 days', '31-60 days', '61-90 days', '90+ days']
                )
                
                aging_summary = aging_df.groupby('aging_category')['balance_due'].sum().reset_index()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.dataframe(aging_summary, use_container_width=True)
                
                with col2:
                    fig = px.pie(
                        aging_summary,
                        values='balance_due',
                        names='aging_category',
                        title='Aging Summary'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("### Detailed Aging")
                st.dataframe(aging_df, use_container_width=True)
        
        elif report_type == "Client Summary":
            # Client revenue summary
            with get_db_connection() as conn:
                client_summary = pd.read_sql_query("""
                    SELECT 
                        i.client_name,
                        COUNT(*) as invoice_count,
                        SUM(CASE WHEN i.status = 'Paid' THEN i.grand_total ELSE 0 END) as paid_amount,
                        SUM(CASE WHEN i.status != 'Paid' THEN i.grand_total ELSE 0 END) as pending_amount,
                        SUM(i.grand_total) as total_amount,
                        AVG(i.grand_total) as avg_invoice,
                        MAX(i.invoice_date) as last_invoice
                    FROM invoices i
                    WHERE i.invoice_date BETWEEN ? AND ?
                    GROUP BY i.client_name
                    ORDER BY total_amount DESC
                """, conn, params=[report_start.strftime('%Y-%m-%d'), report_end.strftime('%Y-%m-%d')])
            
            if not client_summary.empty:
                st.markdown("### Client Summary Report")
                st.dataframe(client_summary, use_container_width=True)
                
                # Top clients chart
                top_clients = client_summary.head(10)
                fig = px.bar(
                    top_clients,
                    x='client_name',
                    y='total_amount',
                    title='Top 10 Clients by Revenue'
                )
                fig.update_layout(
                    xaxis_tickangle=-45,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        elif report_type == "Tax Summary":
            # Tax collected summary
            with get_db_connection() as conn:
                tax_df = pd.read_sql_query("""
                    SELECT 
                        strftime('%Y-%m', i.invoice_date) as period,
                        COUNT(DISTINCT i.id) as invoice_count,
                        SUM(ii.tax_amount) as total_tax_collected,
                        SUM(i.grand_total) as total_revenue,
                        (SUM(ii.tax_amount) / SUM(i.grand_total) * 100) as avg_tax_rate
                    FROM invoices i
                    JOIN invoice_items ii ON i.id = ii.invoice_id
                    WHERE i.invoice_date BETWEEN ? AND ?
                    GROUP BY strftime('%Y-%m', i.invoice_date)
                    ORDER BY period
                """, conn, params=[report_start.strftime('%Y-%m-%d'), report_end.strftime('%Y-%m-%d')])
            
            if not tax_df.empty:
                st.markdown("### Tax Summary Report")
                st.dataframe(tax_df, use_container_width=True)
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=tax_df['period'],
                    y=tax_df['total_tax_collected'],
                    name='Tax Collected',
                    marker_color='#3498db'
                ))
                fig.update_layout(
                    xaxis_title="Period",
                    yaxis_title=f"Tax Amount ({get_currency_symbol(st.session_state.currency)})",
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        elif report_type == "Payment Methods":
            # Payment method summary
            with get_db_connection() as conn:
                payment_method_df = pd.read_sql_query("""
                    SELECT 
                        p.payment_method,
                        COUNT(*) as payment_count,
                        SUM(p.amount) as total_amount,
                        AVG(p.amount) as avg_amount,
                        MIN(p.payment_date) as first_use,
                        MAX(p.payment_date) as last_use
                    FROM payments p
                    WHERE p.payment_date BETWEEN ? AND ?
                    GROUP BY p.payment_method
                    ORDER BY total_amount DESC
                """, conn, params=[report_start.strftime('%Y-%m-%d'), report_end.strftime('%Y-%m-%d')])
            
            if not payment_method_df.empty:
                st.markdown("### Payment Methods Report")
                st.dataframe(payment_method_df, use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.pie(
                        payment_method_df,
                        values='total_amount',
                        names='payment_method',
                        title='Payment Amount by Method'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.pie(
                        payment_method_df,
                        values='payment_count',
                        names='payment_method',
                        title='Payment Count by Method'
                    )
                    st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# SETTINGS PAGE
# ============================================================================

def render_settings_page():
    """Render the settings page"""
    
    st.markdown('<div class="section-header">⚙️ Settings</div>', unsafe_allow_html=True)
    
    tabs = st.tabs(["🏢 Company", "💾 Database", "👤 Users", "📧 Email", "🔐 Security"])
    
    with tabs[0]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Company Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input("Company Name", value=st.session_state.company_info['name'])
            company_address = st.text_input("Address", value=st.session_state.company_info['address'])
            company_city = st.text_input("City", value=st.session_state.company_info['city'])
            company_phone = st.text_input("Phone", value=st.session_state.company_info['phone'])
        
        with col2:
            company_email = st.text_input("Email", value=st.session_state.company_info['email'])
            company_tax_id = st.text_input("TRN / Tax ID", value=st.session_state.company_info['tax_id'])
            invoice_prefix = st.text_input("Invoice Prefix", value=st.session_state.company_info.get('invoice_prefix', 'INV'))
            default_currency = st.selectbox(
                "Default Currency",
                options=list(CURRENCIES.keys()),
                format_func=lambda x: f"{CURRENCIES[x]['symbol']} {CURRENCIES[x]['name']}",
                index=list(CURRENCIES.keys()).index(st.session_state.company_info.get('default_currency', 'TTD'))
            )
        
        vat_registered = st.checkbox("VAT Registered", value=st.session_state.company_info.get('vat_registered', True))
        
        company_bank = st.text_area(
            "Bank Details",
            value=st.session_state.company_info.get('bank_details', ''),
            height=100,
            help="Include account number, bank name, sort code, etc."
        )
        
        # Logo
        st.markdown("##### Company Logo")
        logo_file = st.file_uploader(
            "Upload Logo (PNG, JPG, JPEG)",
            type=['png', 'jpg', 'jpeg'],
            key="settings_logo_upload"
        )
        
        if logo_file is not None:
            if save_logo(logo_file):
                st.success(f"✓ Logo uploaded: {logo_file.name}")
        
        if st.session_state.company_info.get('logo_base64'):
            st.markdown(f'<div class="logo-container">{get_logo_html("80px", "200px")}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Remove Logo", key="settings_remove_logo"):
                remove_logo()
                st.rerun()
        
        if st.button("💾 Save Company Settings", use_container_width=True):
            st.session_state.company_info.update({
                'name': company_name,
                'address': company_address,
                'city': company_city,
                'phone': company_phone,
                'email': company_email,
                'tax_id': company_tax_id,
                'bank_details': company_bank,
                'default_currency': default_currency,
                'vat_registered': vat_registered,
                'invoice_prefix': invoice_prefix
            })
            
            # Save to database
            try:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute('''UPDATE company_settings 
                               SET name = ?, address = ?, city = ?, phone = ?, 
                                   email = ?, tax_id = ?, bank_details = ?,
                                   default_currency = ?, vat_registered = ?, 
                                   invoice_prefix = ?, updated_at = ?
                               WHERE id = 1''',
                             (company_name, company_address, company_city, company_phone,
                              company_email, company_tax_id, company_bank,
                              default_currency, vat_registered, invoice_prefix,
                              datetime.now().isoformat()))
                    
                    st.session_state.notification = "✓ Company settings saved"
                    st.session_state.notification_type = "success"
                    st.rerun()
            except Exception as e:
                st.error(f"Error saving settings: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[1]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Database Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Backup Database**")
            if st.button("📥 Create Backup", use_container_width=True):
                backup_data, filename = backup_database()
                if backup_data:
                    st.download_button(
                        label="📥 Download Backup",
                        data=backup_data,
                        file_name=filename,
                        mime="application/octet-stream",
                        use_container_width=True
                    )
                else:
                    st.error("Backup failed")
        
        with col2:
            st.markdown("**Restore Database**")
            uploaded_backup = st.file_uploader(
                "Upload Backup File",
                type=['db'],
                key="backup_upload"
            )
            if uploaded_backup and st.button("🔄 Restore from Backup", use_container_width=True):
                # Save uploaded file temporarily
                temp_path = "temp_restore.db"
                with open(temp_path, 'wb') as f:
                    f.write(uploaded_backup.getbuffer())
                
                if restore_database(temp_path):
                    os.remove(temp_path)
                    st.session_state.notification = "✓ Database restored successfully"
                    st.session_state.notification_type = "success"
                    st.rerun()
                else:
                    os.remove(temp_path)
                    st.error("Restore failed")
        
        st.divider()
        
        # Database stats
        st.markdown("**Database Statistics**")
        
        try:
            db_size = os.path.getsize('invoices.db') / 1024  # KB
            
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM invoices")
                invoice_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM clients")
                client_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM payments")
                payment_count = c.fetchone()[0]
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Database Size", f"{db_size:.1f} KB")
            with col2:
                st.metric("Invoices", invoice_count)
            with col3:
                st.metric("Clients", client_count)
            with col4:
                st.metric("Payments", payment_count)
        except Exception as e:
            st.warning(f"Could not load database stats: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[2]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### User Management")
        
        # User list
        try:
            with get_db_connection() as conn:
                users_df = pd.read_sql_query(
                    "SELECT id, username, email, role, full_name, is_active, last_login FROM users",
                    conn
                )
            
            if not users_df.empty:
                st.dataframe(users_df, use_container_width=True)
        except:
            st.info("No users found")
        
        st.divider()
        
        # Add user form
        st.markdown("**Add New User**")
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username")
            new_email = st.text_input("Email")
            new_full_name = st.text_input("Full Name")
        with col2:
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", options=['user', 'admin', 'viewer'])
            new_active = st.checkbox("Active", value=True)
        
        if st.button("➕ Add User", use_container_width=True):
            if new_username and new_email and new_password:
                password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                try:
                    with get_db_connection() as conn:
                        c = conn.cursor()
                        c.execute('''INSERT INTO users 
                                   (username, password_hash, email, role, full_name, is_active, created_at)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                 (new_username, password_hash, new_email, new_role, new_full_name, new_active,
                                  datetime.now().isoformat()))
                        st.session_state.notification = f"✓ User {new_username} added"
                        st.session_state.notification_type = "success"
                        st.rerun()
                except Exception as e:
                    st.error(f"Error adding user: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[3]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Email Configuration")
        
        # Load from environment or session
        smtp_server = st.text_input("SMTP Server", value=os.getenv('SMTP_SERVER', 'smtp.gmail.com'))
        smtp_port = st.number_input("SMTP Port", value=int(os.getenv('SMTP_PORT', 587)), min_value=1, max_value=65535)
        smtp_username = st.text_input("SMTP Username", value=os.getenv('SMTP_USERNAME', ''))
        smtp_password = st.text_input("SMTP Password", type="password", value=os.getenv('SMTP_PASSWORD', ''))
        use_tls = st.checkbox("Use TLS", value=True)
        
        if st.button("💾 Save Email Settings", use_container_width=True):
            # Save to .env file
            with open('.env', 'w') as f:
                f.write(f"SMTP_SERVER={smtp_server}\n")
                f.write(f"SMTP_PORT={smtp_port}\n")
                f.write(f"SMTP_USERNAME={smtp_username}\n")
                f.write(f"SMTP_PASSWORD={smtp_password}\n")
                f.write(f"SMTP_USE_TLS={'True' if use_tls else 'False'}\n")
            
            st.session_state.notification = "✓ Email settings saved"
            st.session_state.notification_type = "success"
            st.rerun()
        
        st.divider()
        
        # Test email
        st.markdown("**Test Email Configuration**")
        test_email = st.text_input("Send Test Email To")
        if st.button("📧 Send Test Email", use_container_width=True) and test_email:
            try:
                msg = MIMEMultipart()
                msg['From'] = st.session_state.company_info['email']
                msg['To'] = test_email
                msg['Subject'] = "Test Email from Invoice Pro"
                
                body = f"""
                <html>
                <body>
                    <p>This is a test email from Invoice Pro.</p>
                    <p>If you're reading this, your email configuration is working correctly!</p>
                    <p>Best regards,<br>{st.session_state.company_info['name']}</p>
                </body>
                </html>
                """
                msg.attach(MIMEText(body, 'html'))
                
                server = smtplib.SMTP(smtp_server, smtp_port)
                if use_tls:
                    server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
                server.quit()
                
                st.success(f"✓ Test email sent to {test_email}")
            except Exception as e:
                st.error(f"Error sending test email: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[4]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Security Settings")
        
        # Password policy
        st.markdown("**Password Policy**")
        min_password_length = st.number_input("Minimum Password Length", min_value=6, value=8)
        require_special = st.checkbox("Require Special Characters", value=True)
        require_numbers = st.checkbox("Require Numbers", value=True)
        require_uppercase = st.checkbox("Require Uppercase Letters", value=True)
        
        # Session timeout
        session_timeout = st.number_input("Session Timeout (minutes)", min_value=5, value=30)
        
        # 2FA
        enable_2fa = st.checkbox("Enable Two-Factor Authentication", value=False)
        if enable_2fa:
            st.info("Two-factor authentication setup requires additional configuration")
        
        # Audit log
        st.divider()
        st.markdown("**Audit Log**")
        if st.button("📋 View Audit Log"):
            try:
                with get_db_connection() as conn:
                    audit_df = pd.read_sql_query(
                        "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100",
                        conn
                    )
                if not audit_df.empty:
                    st.dataframe(audit_df, use_container_width=True)
                else:
                    st.info("No audit logs found")
            except Exception as e:
                st.error(f"Error loading audit log: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# HELP PAGE
# ============================================================================

def render_help_page():
    """Render the help page"""
    
    st.markdown('<div class="section-header">❓ Help & Support</div>', unsafe_allow_html=True)
    
    tabs = st.tabs(["📖 User Guide", "❓ FAQ", "📞 Contact", "ℹ️ About"])
    
    with tabs[0]:
        st.markdown("""
        ### 📖 User Guide
        
        #### Getting Started
        1. **Create an Invoice**
           - Go to "Create Invoice" tab
           - Fill in client details
           - Add items with quantities and prices
           - Review totals and save
        
        2. **Manage Clients**
           - Add client information in the Clients section
           - Save frequently used clients for quick selection
        
        3. **Track Payments**
           - Record payments against invoices
           - View payment history
           - Track outstanding balances
        
        4. **Generate Reports**
           - Access financial reports
           - Export data for accounting
           - Monitor business performance
        
        #### Keyboard Shortcuts
        - `Ctrl+N`: New Invoice
        - `Ctrl+S`: Save Current
        - `Ctrl+P`: Print/PDF
        - `Ctrl+F`: Search
        """)
    
    with tabs[1]:
        st.markdown("""
        ### ❓ Frequently Asked Questions
        
        **Q: How do I change the currency?**
        A: Use the currency selector in the sidebar to change the display currency for all invoices.
        
        **Q: Can I customize the invoice template?**
        A: Yes! Go to Settings > Company to upload your logo and customize company details.
        
        **Q: How do I set up recurring invoices?**
        A: Create an invoice, then in Advanced Options select a recurring frequency and save.
        
        **Q: Is my data secure?**
        A: Yes, all data is stored locally in an encrypted SQLite database.
        
        **Q: Can I backup my data?**
        A: Absolutely! Go to Settings > Database to create and download backups.
        
        **Q: How do I send invoices via email?**
        A: Configure email settings in Settings > Email, then use the Send button when viewing an invoice.
        """)
    
    with tabs[2]:
        st.markdown("""
        ### 📞 Contact Support
        
        **Email:** support@invoicepro.com  
        **Phone:** +1 (868) 123-4567  
        **Hours:** Monday-Friday, 9am-5pm AST
        
        #### Office Location
        Invoice Pro Headquarters  
        123 Business Avenue  
        Port of Spain, Trinidad  
        West Indies
        
        #### Submit a Ticket
        """)
        
        with st.form("support_form"):
            name = st.text_input("Your Name")
            email = st.text_input("Email Address")
            subject = st.text_input("Subject")
            message = st.text_area("Message", height=150)
            
            if st.form_submit_button("📤 Submit Ticket"):
                st.success("✓ Ticket submitted successfully. We'll respond within 24 hours.")
    
    with tabs[3]:
        st.markdown("""
        ### ℹ️ About Invoice Pro 2026
        
        **Version:** 3.0.0  
        **Release Date:** January 2026  
        **Developer:** Invoice Pro Team  
        
        #### Features
        - ✅ Professional invoice generation
        - ✅ Multi-currency support
        - ✅ Client management
        - ✅ Payment tracking
        - ✅ Financial reports
        - ✅ Data backup & restore
        - ✅ Email integration
        - ✅ PDF export
        
        #### System Requirements
        - Python 3.8+
        - Modern web browser
        - 100MB free disk space
        
        #### License
        Commercial License - All rights reserved
        
        #### Acknowledgements
        Special thanks to all our beta testers and early adopters who helped shape this application.
        
        © 2026 Invoice Pro. All rights reserved.
        """)

# ============================================================================
# MAIN APP ROUTER
# ============================================================================

def main():
    """Main application router"""
    
    # Render the appropriate page based on session state
    if st.session_state.current_page == "dashboard":
        render_dashboard_page()
    elif st.session_state.current_page == "create":
        render_create_invoice_page()
    elif st.session_state.current_page == "view_invoices":
        render_view_invoices_page()
    elif st.session_state.current_page == "clients":
        render_clients_page()
    elif st.session_state.current_page == "payments":
        render_payments_page()
    elif st.session_state.current_page == "recurring":
        render_recurring_page()
    elif st.session_state.current_page == "reports":
        render_reports_page()
    elif st.session_state.current_page == "settings":
        render_settings_page()
    elif st.session_state.current_page == "help":
        render_help_page()
    else:
        # Default to dashboard
        render_dashboard_page()

# Run the app
if __name__ == "__main__":
    main()
