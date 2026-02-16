# ============================================================================
# CREATE INVOICE PAGE
# ============================================================================

def render_create_invoice_page():
    """Render the create invoice page"""
    
    st.markdown('<div class="section-header">📄 Create New Invoice</div>', unsafe_allow_html=True)
    
    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(["📋 Invoice Details", "🏢 Company Info", "⚙️ Advanced"])
    
    with tab1:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Invoice Details Card
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                
                col_num, col_status = st.columns([2, 1])
                with col_num:
                    invoice_number = st.text_input("Invoice Number *", value=st.session_state.invoice_number)
                with col_status:
                    invoice_status = st.selectbox("Status", INVOICE_STATUSES, 
                                                 index=INVOICE_STATUSES.index(st.session_state.invoice_status))
                
                date_col1, date_col2 = st.columns(2)
                with date_col1:
                    invoice_date = st.date_input("Invoice Date", datetime.now())
                with date_col2:
                    due_date = st.date_input("Due Date", datetime.now() + timedelta(days=30))
                
                po_number = st.text_input("PO Number (optional)")
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Client Information Card
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                st.markdown("##### 👤 Client Information")
                
                # Quick select existing client
                clients_df = get_clients()
                if not clients_df.empty:
                    client_options = ['-- New Client --'] + clients_df['name'].tolist()
                    selected_client = st.selectbox(
                        "Select existing client",
                        options=client_options,
                        key="quick_select_client"
                    )
                    
                    if selected_client != '-- New Client --':
                        client_data = clients_df[clients_df['name'] == selected_client].iloc[0]
                        default_name = client_data['name']
                        default_email = client_data['email']
                        default_phone = client_data.get('phone', '')
                        default_address = client_data.get('address', '')
                        st.session_state.selected_client_id = client_data['id']
                    else:
                        default_name = ''
                        default_email = ''
                        default_phone = ''
                        default_address = ''
                        st.session_state.selected_client_id = None
                else:
                    default_name = ''
                    default_email = ''
                    default_phone = ''
                    default_address = ''
                
                client_name = st.text_input("Client Name *", value=default_name)
                client_email = st.text_input("Email Address *", value=default_email)
                client_phone = st.text_input("Phone Number", value=default_phone)
                client_address = st.text_area("Address", value=default_address, height=80)
                
                # Auto-save client option
                auto_save_client = st.checkbox("Save client to database", value=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            # Invoice Items Card
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                st.markdown("##### 📦 Invoice Items")
                
                # Item Entry Form
                with st.form("item_form", clear_on_submit=True):
                    editing = st.session_state.edit_index >= 0 and st.session_state.edit_index < len(st.session_state.invoice_items)
                    
                    if editing:
                        st.markdown(f"##### ✏️ Editing Item #{st.session_state.edit_index + 1}")
                        item = st.session_state.invoice_items[st.session_state.edit_index]
                        default_desc = item['description']
                        default_qty = item['quantity']
                        default_price = item['unit_price']
                        default_tax = item['tax_rate']
                        default_discount = item['discount']
                    else:
                        st.markdown("##### ➕ Add New Item")
                        default_desc = ""
                        default_qty = 1
                        default_price = 0.0
                        default_tax = 0.0
                        default_discount = 0.0
                    
                    description = st.text_area(
                        "Description *", 
                        value=default_desc,
                        height=60,
                        placeholder="Item or service description"
                    )
                    
                    col_qty, col_price = st.columns(2)
                    with col_qty:
                        quantity = st.number_input("Quantity", min_value=0.01, value=float(default_qty), step=0.01, format="%.2f")
                    with col_price:
                        unit_price = st.number_input(
                            f"Unit Price ({get_currency_symbol(st.session_state.currency)})", 
                            min_value=0.0, value=default_price, step=10.0, format="%.2f"
                        )
                    
                    col_tax, col_discount = st.columns(2)
                    with col_tax:
                        tax_rate = st.number_input("Tax %", min_value=0.0, max_value=100.0, value=default_tax, step=0.5, format="%.1f")
                    with col_discount:
                        discount = st.number_input("Discount %", min_value=0.0, max_value=100.0, value=default_discount, step=0.5, format="%.1f")
                    
                    # Preview calculation
                    if quantity > 0 and unit_price > 0:
                        preview_totals = calculate_item_totals(quantity, unit_price, tax_rate, discount)
                        st.info(f"**Item Total: {format_amount(preview_totals['total'], st.session_state.currency)}**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if editing:
                            if st.form_submit_button("✅ Update Item", use_container_width=True):
                                if description and unit_price > 0:
                                    totals = calculate_item_totals(quantity, unit_price, tax_rate, discount)
                                    
                                    st.session_state.invoice_items[st.session_state.edit_index] = {
                                        'description': description,
                                        'quantity': quantity,
                                        'unit_price': unit_price,
                                        'tax_rate': tax_rate,
                                        'discount': discount,
                                        **totals
                                    }
                                    st.session_state.edit_index = -1
                                    st.session_state.notification = "✓ Item updated successfully"
                                    st.session_state.notification_type = "success"
                                    st.rerun()
                        else:
                            if st.form_submit_button("➕ Add Item", use_container_width=True):
                                if description and unit_price > 0:
                                    totals = calculate_item_totals(quantity, unit_price, tax_rate, discount)
                                    
                                    st.session_state.invoice_items.append({
                                        'description': description,
                                        'quantity': quantity,
                                        'unit_price': unit_price,
                                        'tax_rate': tax_rate,
                                        'discount': discount,
                                        **totals
                                    })
                                    st.session_state.notification = "✓ Item added successfully"
                                    st.session_state.notification_type = "success"
                                    st.rerun()
                                else:
                                    st.warning("Description and price are required")
                    
                    with col2:
                        if editing:
                            if st.form_submit_button("❌ Cancel Edit", use_container_width=True):
                                st.session_state.edit_index = -1
                                st.rerun()
                
                # Display Items
                if st.session_state.invoice_items:
                    st.markdown("##### Current Items")
                    
                    for idx, item in enumerate(st.session_state.invoice_items):
                        with st.container():
                            cols = st.columns([3, 1, 1])
                            with cols[0]:
                                st.markdown(f"**{idx + 1}. {item['description']}**")
                                st.caption(f"Qty: {item['quantity']} × {format_amount(item['unit_price'], st.session_state.currency)}")
                            with cols[1]:
                                st.markdown(f"**{format_amount(item['total'], st.session_state.currency)}**")
                            with cols[2]:
                                col_edit, col_del = st.columns(2)
                                with col_edit:
                                    if st.button("✏️", key=f"edit_{idx}"):
                                        st.session_state.edit_index = idx
                                        st.rerun()
                                with col_del:
                                    if st.button("🗑️", key=f"del_{idx}"):
                                        st.session_state.invoice_items.pop(idx)
                                        if st.session_state.edit_index == idx:
                                            st.session_state.edit_index = -1
                                        st.rerun()
                        
                        if idx < len(st.session_state.invoice_items) - 1:
                            st.divider()
                    
                    # Calculate totals
                    subtotal = sum(item['subtotal'] for item in st.session_state.invoice_items)
                    total_discount = sum(item['discount_amount'] for item in st.session_state.invoice_items)
                    total_tax = sum(item['tax_amount'] for item in st.session_state.invoice_items)
                    grand_total = sum(item['total'] for item in st.session_state.invoice_items)
                    
                    st.divider()
                    
                    # Summary
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Subtotal", format_amount(subtotal, st.session_state.currency))
                    with col2:
                        st.metric("Discount", f"-{format_amount(total_discount, st.session_state.currency)}")
                    with col3:
                        st.metric("Tax", format_amount(total_tax, st.session_state.currency))
                    
                    st.markdown(f"""
                        <div style="background: #2563eb20; padding: 1rem; border-radius: 8px; margin-top: 1rem;">
                            <h3 style="margin:0; color: #2563eb;">GRAND TOTAL: {format_amount(grand_total, st.session_state.currency)}</h3>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Action buttons
                    col_reset, _ = st.columns([1, 3])
                    with col_reset:
                        if st.button("🔄 Clear All", use_container_width=True):
                            st.session_state.invoice_items = []
                            st.session_state.edit_index = -1
                            st.rerun()
                else:
                    st.info("💡 No items added yet. Use the form above to add items.")
                
                st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### 🏢 Company Information")
        
        company_name = st.text_input("Company Name", value=st.session_state.company_info['name'])
        company_address = st.text_input("Address", value=st.session_state.company_info['address'])
        company_city = st.text_input("City", value=st.session_state.company_info['city'])
        company_phone = st.text_input("Phone", value=st.session_state.company_info['phone'])
        company_email = st.text_input("Email", value=st.session_state.company_info['email'])
        company_tax_id = st.text_input("TRN / Tax ID", value=st.session_state.company_info['tax_id'])
        company_bank = st.text_area("Bank Details", value=st.session_state.company_info.get('bank_details', ''), height=100)
        
        # VAT Registration
        vat_registered = st.checkbox("VAT Registered", value=st.session_state.company_info.get('vat_registered', True))
        
        # Invoice prefix
        invoice_prefix = st.text_input("Invoice Prefix", value=st.session_state.company_info.get('invoice_prefix', 'INV'))
        
        # Logo upload
        st.markdown("##### Company Logo")
        logo_file = st.file_uploader(
            "Upload Logo (PNG, JPG, JPEG)",
            type=['png', 'jpg', 'jpeg'],
            key="create_logo_upload"
        )
        
        if logo_file is not None:
            if save_logo(logo_file):
                st.success(f"✓ Logo uploaded: {logo_file.name}")
        
        # Show current logo
        if st.session_state.company_info.get('logo_base64'):
            st.markdown(f'<div class="logo-container">{get_logo_html("80px", "200px")}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Remove Logo", key="remove_logo_create"):
                remove_logo()
                st.rerun()
        
        if st.button("💾 Update Company Info", use_container_width=True):
            st.session_state.company_info.update({
                'name': company_name,
                'address': company_address,
                'city': company_city,
                'phone': company_phone,
                'email': company_email,
                'tax_id': company_tax_id,
                'bank_details': company_bank,
                'vat_registered': vat_registered,
                'invoice_prefix': invoice_prefix
            })
            st.session_state.notification = "✓ Company information updated"
            st.session_state.notification_type = "success"
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab3:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### ⚙️ Advanced Options")
        
        # Notes
        invoice_notes = st.text_area(
            "Invoice Notes",
            value=st.session_state.invoice_notes,
            height=100,
            placeholder="Payment terms, special instructions, thank you message, etc."
        )
        st.session_state.invoice_notes = invoice_notes
        
        # Recurring invoice
        st.markdown("##### 🔄 Recurring Invoice")
        recurring_frequency = st.selectbox(
            "Repeat every",
            options=list(RECURRING_FREQUENCIES.keys()),
            index=0
        )
        
        if recurring_frequency != 'None':
            recurring_end = st.date_input(
                "End date (optional)",
                value=None,
                min_value=datetime.now()
            )
        
        # Save as template
        st.markdown("##### 📋 Save as Template")
        template_name = st.text_input("Template Name", placeholder="e.g., Monthly Retainer")
        if st.button("💾 Save as Template", use_container_width=True) and template_name:
            template_data = {
                'items': st.session_state.invoice_items,
                'notes': invoice_notes
            }
            template_id = save_invoice_template(template_name, template_data)
            if template_id:
                st.session_state.notification = f"✓ Template '{template_name}' saved"
                st.session_state.notification_type = "success"
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Preview and Actions Section
    if st.session_state.invoice_items and client_name:
        st.markdown("---")
        st.markdown("### 👁️ Invoice Preview")
        
        # Calculate totals
        subtotal = sum(item['subtotal'] for item in st.session_state.invoice_items)
        total_discount = sum(item['discount_amount'] for item in st.session_state.invoice_items)
        total_tax = sum(item['tax_amount'] for item in st.session_state.invoice_items)
        grand_total = sum(item['total'] for item in st.session_state.invoice_items)
        
        # Preview Container
        with st.container():
            st.markdown('<div class="invoice-preview-container">', unsafe_allow_html=True)
            
            # Header with logo
            col_left, col_right = st.columns(2)
            with col_left:
                if st.session_state.company_info.get('logo_base64'):
                    st.image(io.BytesIO(st.session_state.company_info['logo_bytes']), width=150)
                st.markdown(f"### INVOICE")
                st.markdown(f"**{invoice_number}**")
                st.markdown(get_status_badge_html(invoice_status), unsafe_allow_html=True)
            with col_right:
                st.markdown(f"""
                **{st.session_state.company_info['name']}**  
                {st.session_state.company_info['address']}  
                {st.session_state.company_info['city']}  
                📞 {st.session_state.company_info['phone']}  
                ✉️ {st.session_state.company_info['email']}  
                {'VAT Registered' if st.session_state.company_info.get('vat_registered') else ''}
                """)
            
            st.divider()
            
            # Client and Invoice Details
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Bill To:**")
                st.markdown(f"""
                **{client_name}**  
                {client_address if client_address else ''}  
                ✉️ {client_email}  
                {f'📞 {client_phone}' if client_phone else ''}
                """)
            with col2:
                st.markdown("**Invoice Details:**")
                st.markdown(f"""
                **Date:** {invoice_date.strftime('%d %b %Y')}  
                **Due:** {due_date.strftime('%d %b %Y')}  
                {f'**PO:** {po_number}' if po_number else ''}  
                **Currency:** {CURRENCIES[st.session_state.currency]['name']}
                """)
            
            st.divider()
            
            # Items Table
            if st.session_state.invoice_items:
                items_data = []
                for item in st.session_state.invoice_items:
                    items_data.append({
                        "Description": item['description'],
                        "Qty": f"{item['quantity']:.2f}",
                        "Price": format_amount(item['unit_price'], st.session_state.currency),
                        "Tax": f"{item['tax_rate']}%",
                        "Disc": f"{item['discount']}%",
                        "Total": format_amount(item['total'], st.session_state.currency)
                    })
                
                st.dataframe(
                    pd.DataFrame(items_data),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Description": st.column_config.TextColumn("Description", width="large"),
                        "Total": st.column_config.TextColumn("Total", width="medium"),
                    }
                )
            
            st.divider()
            
            # Totals
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                st.markdown(f"""
                **Subtotal:** {format_amount(subtotal, st.session_state.currency)}  
                **Discount:** -{format_amount(total_discount, st.session_state.currency)}  
                **Tax:** {format_amount(total_tax, st.session_state.currency)}  
                """)
            with col3:
                st.markdown(f'<div class="grand-total-box"><p style="font-size: 0.9rem; margin-bottom: 0.25rem;">GRAND TOTAL</p><p style="font-size: 2rem; font-weight: 700; margin: 0;">{format_amount(grand_total, st.session_state.currency)}</p></div>', unsafe_allow_html=True)
            
            # Payment Details
            if st.session_state.company_info.get('bank_details'):
                st.divider()
                st.markdown("**Payment Details:**")
                st.text(st.session_state.company_info['bank_details'])
            
            # Notes
            if invoice_notes:
                st.divider()
                st.markdown("**Notes:**")
                st.text(invoice_notes)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Action Buttons
        st.markdown("---")
        st.markdown("### 🎯 Actions")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("💾 Save Invoice", use_container_width=True):
                try:
                    # Save client if auto-save is enabled
                    if auto_save_client and client_name and client_email:
                        client_id = save_client_to_db({
                            'name': client_name,
                            'email': client_email,
                            'phone': client_phone,
                            'address': client_address
                        })
                    
                    # Prepare invoice data
                    invoice_data = {
                        'invoice_number': invoice_number,
                        'client_name': client_name,
                        'client_email': client_email,
                        'client_address': client_address,
                        'client_phone': client_phone,
                        'invoice_date': str(invoice_date),
                        'due_date': str(due_date),
                        'po_number': po_number,
                        'currency': st.session_state.currency,
                        'subtotal': subtotal,
                        'tax_total': total_tax,
                        'discount_total': total_discount,
                        'grand_total': grand_total,
                        'status': invoice_status,
                        'notes': invoice_notes,
                        'recurring_frequency': recurring_frequency if recurring_frequency != 'None' else None,
                        'recurring_next_date': str(invoice_date + RECURRING_FREQUENCIES[recurring_frequency]) if recurring_frequency != 'None' and RECURRING_FREQUENCIES[recurring_frequency] else None
                    }
                    
                    invoice_id, errors, warnings = save_invoice_to_db(invoice_data, st.session_state.invoice_items)
                    
                    if invoice_id:
                        for warning in warnings:
                            st.warning(warning)
                        st.session_state.notification = f"✓ Invoice saved successfully! (ID: {invoice_id})"
                        st.session_state.notification_type = "success"
                        st.balloons()
                        
                        # Clear form for next invoice
                        st.session_state.invoice_items = []
                        st.session_state.invoice_number = generate_invoice_number()
                        st.session_state.invoice_notes = ''
                        st.rerun()
                    else:
                        for error in errors:
                            st.error(error)
                except Exception as e:
                    st.error(f"Error saving invoice: {e}")
        
        with col2:
            if PDF_AVAILABLE:
                if st.button("📄 Generate PDF", use_container_width=True):
                    with st.spinner("Generating PDF..."):
                        invoice_data = {
                            'invoice_number': invoice_number,
                            'invoice_date': invoice_date.strftime('%d %b %Y'),
                            'due_date': due_date.strftime('%d %b %Y'),
                            'po_number': po_number,
                            'status': invoice_status,
                            'client': {
                                'name': client_name,
                                'email': client_email,
                                'address': client_address
                            },
                            'company_info': st.session_state.company_info,
                            'items': st.session_state.invoice_items,
                            'currency': st.session_state.currency,
                            'notes': invoice_notes,
                            'totals': {
                                'subtotal': subtotal,
                                'discount': total_discount,
                                'tax': total_tax,
                                'grand_total': grand_total
                            }
                        }
                        
                        pdf_buffer = generate_pdf_invoice(invoice_data)
                        if pdf_buffer:
                            st.download_button(
                                label="📥 Download PDF",
                                data=pdf_buffer,
                                file_name=f"invoice_{invoice_number}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                        else:
                            st.error("Failed to generate PDF")
            else:
                st.button("📄 PDF (Install ReportLab)", disabled=True, use_container_width=True)
        
        with col3:
            if EXCEL_AVAILABLE:
                if st.button("📊 Export Excel", use_container_width=True):
                    invoice_data = {
                        'invoice_number': invoice_number,
                        'client_name': client_name,
                        'client_email': client_email,
                        'invoice_date': str(invoice_date),
                        'due_date': str(due_date),
                        'subtotal': subtotal,
                        'tax_total': total_tax,
                        'discount_total': total_discount,
                        'grand_total': grand_total
                    }
                    
                    excel_buffer = export_to_excel(invoice_data, st.session_state.invoice_items)
                    if excel_buffer:
                        st.download_button(
                            label="📥 Download Excel",
                            data=excel_buffer,
                            file_name=f"invoice_{invoice_number}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
        
        with col4:
            email_to = st.text_input("", value=client_email if client_email else "", 
                                    key="email_input", placeholder="Email address")
        
        with col5:
            if st.button("📧 Send Email", use_container_width=True, disabled=not email_to):
                if email_to:
                    with st.spinner("Sending email..."):
                        # Generate PDF for email
                        invoice_data = {
                            'invoice_number': invoice_number,
                            'invoice_date': invoice_date.strftime('%d %b %Y'),
                            'due_date': due_date.strftime('%d %b %Y'),
                            'po_number': po_number,
                            'status': invoice_status,
                            'client': {
                                'name': client_name,
                                'email': client_email,
                                'address': client_address
                            },
                            'company_info': st.session_state.company_info,
                            'items': st.session_state.invoice_items,
                            'currency': st.session_state.currency,
                            'notes': invoice_notes,
                            'totals': {
                                'subtotal': subtotal,
                                'discount': total_discount,
                                'tax': total_tax,
                                'grand_total': grand_total
                            }
                        }
                        
                        pdf_buffer = generate_pdf_invoice(invoice_data)
                        if pdf_buffer:
                            success, message = send_email_invoice(email_to, pdf_buffer, invoice_number)
                            if success:
                                st.session_state.notification = message
                                st.session_state.notification_type = "success"
                            else:
                                st.session_state.notification = message
                                st.session_state.notification_type = "warning"
                            st.rerun()
                else:
                    st.warning("⚠️ Enter an email address")

# ============================================================================
# VIEW INVOICES PAGE
# ============================================================================

def render_view_invoices_page():
    """Render the view invoices page"""
    
    st.markdown('<div class="section-header">📋 Invoice Management</div>', unsafe_allow_html=True)
    
    # Check if viewing a specific invoice
    if st.session_state.view_invoice_id:
        render_invoice_detail(st.session_state.view_invoice_id)
        if st.button("← Back to List", use_container_width=False):
            st.session_state.view_invoice_id = None
            st.rerun()
        return
    
    # Filters
    with st.container():
        st.markdown("### 🔍 Search & Filter")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            filter_status = st.selectbox(
                "Status",
                options=['All'] + INVOICE_STATUSES,
                key="filter_status_select"
            )
        
        with col2:
            filter_client = st.text_input("Client Name", key="filter_client_input", placeholder="Search by client")
        
        with col3:
            filter_date_from = st.date_input("From Date", value=None, key="filter_date_from")
        
        with col4:
            filter_date_to = st.date_input("To Date", value=None, key="filter_date_to")
    
    # Build filters
    filters = {}
    if filter_status != 'All':
        filters['status'] = filter_status
    if filter_client:
        filters['client_name'] = filter_client
    if filter_date_from:
        filters['date_from'] = str(filter_date_from)
    if filter_date_to:
        filters['date_to'] = str(filter_date_to)
    
    # Get invoices
    invoices_df = get_invoices(filters)
    
    if not invoices_df.empty:
        st.markdown(f"### 📊 Found {len(invoices_df)} Invoice(s)")
        
        # Summary stats for filtered results
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Amount", format_amount(invoices_df['grand_total'].sum(), st.session_state.currency))
        with col2:
            paid_amount = invoices_df[invoices_df['status'] == 'Paid']['grand_total'].sum()
            st.metric("Paid", format_amount(paid_amount, st.session_state.currency))
        with col3:
            pending = invoices_df[invoices_df['status'].isin(['Draft', 'Sent'])]['grand_total'].sum()
            st.metric("Pending", format_amount(pending, st.session_state.currency))
        with col4:
            overdue = invoices_df[invoices_df['status'] == 'Overdue']['grand_total'].sum()
            st.metric("Overdue", format_amount(overdue, st.session_state.currency))
        
        st.markdown("---")
        
        # Display invoices in cards
        for idx, invoice in invoices_df.iterrows():
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1.5])
                
                with col1:
                    st.markdown(f"### {invoice['invoice_number']}")
                    st.markdown(f"**{invoice['client_name']}**")
                    st.caption(invoice['client_email'])
                
                with col2:
                    st.markdown(f"**Date:** {invoice['invoice_date']}")
                    st.markdown(f"**Due:** {invoice['due_date']}")
                    currency_symbol = get_currency_symbol(invoice['currency'])
                    st.markdown(f"**Amount:** {currency_symbol}{invoice['grand_total']:,.2f}")
                    
                    # Progress bar for paid amount
                    if invoice['status'] != 'Paid' and invoice['grand_total'] > 0:
                        paid_pct = (invoice.get('amount_paid', 0) / invoice['grand_total']) * 100
                        st.markdown(f"""
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {paid_pct}%;"></div>
                            </div>
                            <small>Paid: {paid_pct:.1f}%</small>
                        """, unsafe_allow_html=True)
                
                with col3:
                    st.markdown(get_status_badge_html(invoice['status']), unsafe_allow_html=True)
                
                with col4:
                    if invoice['status'] not in ['Paid', 'Cancelled']:
                        balance = invoice.get('balance_due', invoice['grand_total'])
                        if balance > 0:
                            st.markdown(f"**Balance:** {currency_symbol}{balance:,.2f}")
                
                with col5:
                    # Actions
                    col_view, col_pdf, col_pay, col_del = st.columns(4)
                    with col_view:
                        if st.button("👁️", key=f"view_{invoice['id']}", help="View Details"):
                            st.session_state.view_invoice_id = invoice['id']
                            st.rerun()
                    
                    with col_pdf:
                        if st.button("📄", key=f"pdf_{invoice['id']}", help="Download PDF"):
                            invoice_data, items = get_invoice_by_id(invoice['id'])
                            if invoice_data and items:
                                pdf_data = {
                                    'invoice_number': invoice_data['invoice_number'],
                                    'invoice_date': invoice_data['invoice_date'],
                                    'due_date': invoice_data['due_date'],
                                    'po_number': invoice_data.get('po_number', ''),
                                    'status': invoice_data['status'],
                                    'client': {
                                        'name': invoice_data['client_name'],
                                        'email': invoice_data['client_email'],
                                        'address': invoice_data.get('client_address', '')
                                    },
                                    'company_info': st.session_state.company_info,
                                    'items': items,
                                    'currency': invoice_data['currency'],
                                    'notes': invoice_data.get('notes', ''),
                                    'totals': {
                                        'subtotal': invoice_data['subtotal'],
                                        'discount': invoice_data['discount_total'],
                                        'tax': invoice_data['tax_total'],
                                        'grand_total': invoice_data['grand_total']
                                    }
                                }
                                
                                if PDF_AVAILABLE:
                                    pdf_buffer = generate_pdf_invoice(pdf_data)
                                    if pdf_buffer:
                                        st.download_button(
                                            label="📥",
                                            data=pdf_buffer,
                                            file_name=f"invoice_{invoice_data['invoice_number']}.pdf",
                                            mime="application/pdf",
                                            key=f"download_pdf_{invoice['id']}"
                                        )
                    
                    with col_pay:
                        if invoice['status'] not in ['Paid', 'Cancelled']:
                            if st.button("💰", key=f"pay_{invoice['id']}", help="Record Payment"):
                                st.session_state.payment_invoice_id = invoice['id']
                                st.session_state.show_payment_modal = True
                                st.rerun()
                    
                    with col_del:
                        if st.button("🗑️", key=f"delete_{invoice['id']}", help="Delete"):
                            if delete_invoice(invoice['id']):
                                st.session_state.notification = "✓ Invoice deleted"
                                st.session_state.notification_type = "success"
                                st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        st.info("📭 No invoices found. Create your first invoice!")
        if st.button("➕ Create Invoice", use_container_width=True):
            st.session_state.current_page = "create"
            st.rerun()

def render_invoice_detail(invoice_id):
    """Render detailed view of a single invoice"""
    invoice, items = get_invoice_by_id(invoice_id)
    
    if not invoice:
        st.error("Invoice not found")
        return
    
    st.markdown(f"### Invoice {invoice['invoice_number']}")
    
    # Header with actions
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.view_invoice_id = None
            st.rerun()
    
    with col2:
        new_status = st.selectbox(
            "Status",
            options=INVOICE_STATUSES,
            index=INVOICE_STATUSES.index(invoice['status']),
            key="detail_status"
        )
        if new_status != invoice['status']:
            if update_invoice_status(invoice_id, new_status):
                st.success(f"Status updated to {new_status}")
                st.rerun()
    
    with col3:
        if st.button("📄 PDF", use_container_width=True):
            invoice_data, items = get_invoice_by_id(invoice_id)
            if invoice_data and items:
                pdf_data = {
                    'invoice_number': invoice_data['invoice_number'],
                    'invoice_date': invoice_data['invoice_date'],
                    'due_date': invoice_data['due_date'],
                    'po_number': invoice_data.get('po_number', ''),
                    'status': invoice_data['status'],
                    'client': {
                        'name': invoice_data['client_name'],
                        'email': invoice_data['client_email'],
                        'address': invoice_data.get('client_address', '')
                    },
                    'company_info': st.session_state.company_info,
                    'items': items,
                    'currency': invoice_data['currency'],
                    'notes': invoice_data.get('notes', ''),
                    'totals': {
                        'subtotal': invoice_data['subtotal'],
                        'discount': invoice_data['discount_total'],
                        'tax': invoice_data['tax_total'],
                        'grand_total': invoice_data['grand_total']
                    }
                }
                
                if PDF_AVAILABLE:
                    pdf_buffer = generate_pdf_invoice(pdf_data)
                    if pdf_buffer:
                        st.download_button(
                            label="Download PDF",
                            data=pdf_buffer,
                            file_name=f"invoice_{invoice_data['invoice_number']}.pdf",
                            mime="application/pdf"
                        )
    
    with col4:
        if invoice['status'] not in ['Paid', 'Cancelled']:
            if st.button("💰 Record Payment", use_container_width=True):
                st.session_state.payment_invoice_id = invoice_id
                st.session_state.show_payment_modal = True
                st.rerun()
    
    with col5:
        if st.button("✉️ Email", use_container_width=True):
            st.session_state.show_email_modal = True
    
    st.markdown("---")
    
    # Invoice details in tabs
    tab1, tab2, tab3 = st.tabs(["📋 Details", "💰 Payments", "📊 History"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Client Information")
            st.markdown(f"""
            **Name:** {invoice['client_name']}  
            **Email:** {invoice['client_email']}  
            **Phone:** {invoice.get('client_phone', 'N/A')}  
            **Address:** {invoice.get('client_address', 'N/A')}
            """)
        
        with col2:
            st.markdown("#### Invoice Information")
            st.markdown(f"""
            **Invoice Number:** {invoice['invoice_number']}  
            **Date:** {invoice['invoice_date']}  
            **Due Date:** {invoice['due_date']}  
            **PO Number:** {invoice.get('po_number', 'N/A')}  
            **Currency:** {invoice['currency']}
            """)
        
        st.markdown("#### Invoice Items")
        if items:
            items_df = pd.DataFrame(items)
            items_df['amount'] = items_df.apply(
                lambda x: format_amount(x['total'], invoice['currency']), axis=1
            )
            st.dataframe(
                items_df[['description', 'quantity', 'unit_price', 'tax_rate', 'discount', 'amount']],
                column_config={
                    "description": "Description",
                    "quantity": "Qty",
                    "unit_price": st.column_config.NumberColumn("Unit Price", format=f"{get_currency_symbol(invoice['currency'])}%.2f"),
                    "tax_rate": "Tax %",
                    "discount": "Disc %",
                    "amount": "Amount"
                },
                use_container_width=True,
                hide_index=True
            )
        
        st.markdown("#### Totals")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Subtotal", format_amount(invoice['subtotal'], invoice['currency']))
        with col2:
            st.metric("Discount", format_amount(invoice['discount_total'], invoice['currency']))
        with col3:
            st.metric("Tax", format_amount(invoice['tax_total'], invoice['currency']))
        with col4:
            st.metric("Grand Total", format_amount(invoice['grand_total'], invoice['currency']))
        
        if invoice['notes']:
            st.markdown("#### Notes")
            st.info(invoice['notes'])
    
    with tab2:
        # Payment history
        try:
            with get_db_connection() as conn:
                payments_df = pd.read_sql_query(
                    "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date DESC",
                    conn, params=[invoice_id]
                )
            
            if not payments_df.empty:
                st.dataframe(
                    payments_df[['payment_date', 'amount', 'payment_method', 'reference', 'notes']],
                    column_config={
                        "payment_date": "Date",
                        "amount": st.column_config.NumberColumn("Amount", format=f"{get_currency_symbol(invoice['currency'])}%.2f"),
                        "payment_method": "Method",
                        "reference": "Reference",
                        "notes": "Notes"
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                total_paid = payments_df['amount'].sum()
                st.metric("Total Paid", format_amount(total_paid, invoice['currency']))
                st.metric("Balance Due", format_amount(invoice['grand_total'] - total_paid, invoice['currency']))
            else:
                st.info("No payments recorded yet")
        except Exception as e:
            st.error(f"Error loading payments: {e}")
    
    with tab3:
        # Audit history
        try:
            with get_db_connection() as conn:
                audit_df = pd.read_sql_query(
                    """SELECT * FROM audit_log 
                       WHERE details LIKE ? 
                       ORDER BY timestamp DESC LIMIT 10""",
                    conn, params=[f'%{invoice["invoice_number"]}%']
                )
            
            if not audit_df.empty:
                st.dataframe(
                    audit_df[['timestamp', 'action', 'details']],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No history available")
        except Exception as e:
            st.error(f"Error loading history: {e}")

# ============================================================================
# PAYMENTS PAGE
# ============================================================================

def render_payments_page():
    """Render the payments page"""
    
    st.markdown('<div class="section-header">💰 Payment Management</div>', unsafe_allow_html=True)
    
    # Payment modal
    if st.session_state.get('show_payment_modal'):
        with st.form("payment_form"):
            st.markdown("### Record Payment")
            
            invoice_id = st.session_state.payment_invoice_id
            invoice, items = get_invoice_by_id(invoice_id)
            
            if invoice:
                st.markdown(f"**Invoice:** {invoice['invoice_number']}")
                st.markdown(f"**Client:** {invoice['client_name']}")
                st.markdown(f"**Total:** {format_amount(invoice['grand_total'], invoice['currency'])}")
                st.markdown(f"**Amount Paid:** {format_amount(invoice.get('amount_paid', 0), invoice['currency'])}")
                st.markdown(f"**Balance Due:** {format_amount(invoice['balance_due'], invoice['currency'])}")
                
                amount = st.number_input(
                    "Payment Amount",
                    min_value=0.01,
                    max_value=float(invoice['balance_due']),
                    value=float(invoice['balance_due']),
                    step=10.0
                )
                
                payment_method = st.selectbox("Payment Method", PAYMENT_METHODS)
                payment_date = st.date_input("Payment Date", datetime.now())
                reference = st.text_input("Reference Number (optional)")
                notes = st.text_area("Notes (optional)")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("✅ Record Payment", use_container_width=True):
                        success, message = process_payment(
                            invoice_id, amount, payment_method, reference, notes
                        )
                        if success:
                            st.session_state.notification = message
                            st.session_state.notification_type = "success"
                            st.session_state.show_payment_modal = False
                            st.rerun()
                        else:
                            st.error(message)
                
                with col2:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state.show_payment_modal = False
                        st.rerun()
    
    # Payment history
    st.markdown("### Payment History")
    
    try:
        with get_db_connection() as conn:
            payments_df = pd.read_sql_query("""
                SELECT p.*, i.invoice_number, i.client_name, i.currency
                FROM payments p
                JOIN invoices i ON p.invoice_id = i.id
                ORDER BY p.payment_date DESC
                LIMIT 100
            """, conn)
        
        if not payments_df.empty:
            # Format amounts
            payments_df['formatted_amount'] = payments_df.apply(
                lambda x: format_amount(x['amount'], x['currency']), axis=1
            )
            
            st.dataframe(
                payments_df[['payment_date', 'invoice_number', 'client_name', 'formatted_amount', 
                           'payment_method', 'reference', 'notes']],
                column_config={
                    "payment_date": "Date",
                    "invoice_number": "Invoice",
                    "client_name": "Client",
                    "formatted_amount": "Amount",
                    "payment_method": "Method",
                    "reference": "Reference",
                    "notes": "Notes"
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Payments", len(payments_df))
            with col2:
                total_amount = payments_df['amount'].sum()
                st.metric("Total Amount", format_amount(total_amount, st.session_state.currency))
            with col3:
                avg_payment = payments_df['amount'].mean()
                st.metric("Average Payment", format_amount(avg_payment, st.session_state.currency))
        else:
            st.info("No payments recorded yet")
    except Exception as e:
        st.error(f"Error loading payments: {e}")

# ============================================================================
# CLIENTS PAGE
# ============================================================================

def render_clients_page():
    """Render the clients management page"""
    
    st.markdown('<div class="section-header">👥 Client Management</div>', unsafe_allow_html=True)
    
    # Add/Edit Client Form
    with st.expander("➕ Add New Client", expanded=False):
        with st.form("client_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Client Name *")
                email = st.text_input("Email *")
                phone = st.text_input("Phone")
            
            with col2:
                company = st.text_input("Company")
                tax_id = st.text_input("TRN / Tax ID")
                credit_limit = st.number_input("Credit Limit", min_value=0.0, value=0.0)
                payment_terms = st.number_input("Payment Terms (days)", min_value=0, value=30)
            
            address = st.text_area("Address", height=80)
            notes = st.text_area("Notes", height=80)
            
            if st.form_submit_button("💾 Save Client", use_container_width=True):
                if name and email:
                    client_data = {
                        'name': name,
                        'email': email,
                        'phone': phone,
                        'address': address,
                        'company': company,
                        'tax_id': tax_id,
                        'notes': notes,
                        'credit_limit': credit_limit,
                        'payment_terms': payment_terms
                    }
                    client_id = save_client_to_db(client_data)
                    if client_id:
                        st.session_state.notification = f"✓ Client saved successfully"
                        st.session_state.notification_type = "success"
                        st.rerun()
                    else:
                        st.error("Error saving client")
                else:
                    st.warning("Name and email are required")
    
    # Search clients
    st.markdown("### Search Clients")
    search_term = st.text_input("Search by name, email, or company", placeholder="Type to search...")
    
    # Get clients
    clients_df = get_clients(search_term if search_term else None)
    
    if not clients_df.empty:
        st.markdown(f"### {len(clients_df)} Client(s) Found")
        
        for _, client in clients_df.iterrows():
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"### {client['name']}")
                    st.markdown(f"**Email:** {client['email']}")
                    if client.get('phone'):
                        st.markdown(f"**Phone:** {client['phone']}")
                
                with col2:
                    if client.get('company'):
                        st.markdown(f"**Company:** {client['company']}")
                    if client.get('tax_id'):
                        st.markdown(f"**TRN:** {client['tax_id']}")
                    if client.get('credit_limit', 0) > 0:
                        st.markdown(f"**Credit Limit:** {format_amount(client['credit_limit'], st.session_state.currency)}")
                
                with col3:
                    # Get client invoice summary
                    try:
                        with get_db_connection() as conn:
                            summary = pd.read_sql_query("""
                                SELECT COUNT(*) as invoice_count,
                                       SUM(CASE WHEN status = 'Paid' THEN grand_total ELSE 0 END) as paid,
                                       SUM(CASE WHEN status NOT IN ('Paid', 'Cancelled') THEN balance_due ELSE 0 END) as outstanding
                                FROM invoices
                                WHERE client_id = ?
                            """, conn, params=[client['id']]).iloc[0]
                        
                        st.metric("Invoices", summary['invoice_count'])
                        if summary['outstanding'] > 0:
                            st.warning(f"Outstanding: {format_amount(summary['outstanding'], st.session_state.currency)}")
                    except:
                        pass
                
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No clients found. Add your first client!")

# ============================================================================
# RECURRING INVOICES PAGE
# ============================================================================

def render_recurring_page():
    """Render the recurring invoices page"""
    
    st.markdown('<div class="section-header">🔄 Recurring Invoices</div>', unsafe_allow_html=True)
    
    try:
        with get_db_connection() as conn:
            recurring_df = pd.read_sql_query("""
                SELECT r.*, c.name as client_name, t.name as template_name
                FROM recurring_invoices r
                LEFT JOIN clients c ON r.client_id = c.id
                LEFT JOIN invoice_templates t ON r.template_id = t.id
                WHERE r.is_active = 1
                ORDER BY r.next_date
            """, conn)
        
        if not recurring_df.empty:
            for _, recurring in recurring_df.iterrows():
                with st.container():
                    st.markdown('<div class="business-card">', unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{recurring['client_name']}**")
                        st.markdown(f"Template: {recurring['template_name']}")
                    
                    with col2:
                        st.markdown(f"Frequency: {recurring['frequency']}")
                        st.markdown(f"Next: {recurring['next_date']}")
                    
                    with col3:
                        if recurring['end_date']:
                            st.markdown(f"Until: {recurring['end_date']}")
                    
                    with col4:
                        if st.button("⏸️ Pause", key=f"pause_{recurring['id']}"):
                            # Update recurring status
                            st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No recurring invoices configured")
            
            # Form to create recurring
            with st.form("recurring_form"):
                st.markdown("### Create Recurring Invoice")
                
                # Get templates
                with get_db_connection() as conn:
                    templates_df = pd.read_sql_query("SELECT * FROM invoice_templates", conn)
                
                if not templates_df.empty:
                    template = st.selectbox(
                        "Select Template",
                        options=templates_df['name'].tolist()
                    )
                    
                    # Get clients
                    with get_db_connection() as conn:
                        clients_df = pd.read_sql_query("SELECT * FROM clients", conn)
                    
                    if not clients_df.empty:
                        client = st.selectbox(
                            "Select Client",
                            options=clients_df['name'].tolist()
                        )
                        
                        frequency = st.selectbox(
                            "Frequency",
                            options=[k for k in RECURRING_FREQUENCIES.keys() if k != 'None']
                        )
                        
                        start_date = st.date_input("Start Date", datetime.now())
                        end_date = st.date_input("End Date (optional)", value=None)
                        
                        if st.form_submit_button("Create Recurring Invoice"):
                            # Get IDs
                            template_id = templates_df[templates_df['name'] == template].iloc[0]['id']
                            client_id = clients_df[clients_df['name'] == client].iloc[0]['id']
                            
                            recurring_id = create_recurring_invoice(
                                template_id, client_id, frequency,
                                start_date.strftime('%Y-%m-%d'),
                                end_date.strftime('%Y-%m-%d') if end_date else None
                            )
                            
                            if recurring_id:
                                st.success("Recurring invoice created!")
                                st.rerun()
    except Exception as e:
        st.error(f"Error loading recurring invoices: {e}")

# ============================================================================
# REPORTS PAGE
# ============================================================================

def render_reports_page():
    """Render the reports page"""
    
    st.markdown('<div class="section-header">📊 Reports & Analytics</div>', unsafe_allow_html=True)
    
    # Report type selector
    report_type = st.selectbox(
        "Select Report Type",
        ["Revenue Overview", "Client Analysis", "Payment Trends", "Tax Summary", "Aging Report"]
    )
    
    # Date range
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    if report_type == "Revenue Overview":
        render_revenue_report(start_date, end_date)
    elif report_type == "Client Analysis":
        render_client_analysis(start_date, end_date)
    elif report_type == "Payment Trends":
        render_payment_trends(start_date, end_date)
    elif report_type == "Tax Summary":
        render_tax_summary(start_date, end_date)
    elif report_type == "Aging Report":
        render_aging_report()

def render_revenue_report(start_date, end_date):
    """Render revenue report"""
    try:
        with get_db_connection() as conn:
            query = """
            SELECT 
                date(invoice_date) as date,
                SUM(CASE WHEN status = 'Paid' THEN grand_total ELSE 0 END) as paid,
                SUM(CASE WHEN status = 'Overdue' THEN grand_total ELSE 0 END) as overdue,
                SUM(CASE WHEN status = 'Sent' THEN grand_total ELSE 0 END) as pending,
                COUNT(*) as invoice_count
            FROM invoices
            WHERE date(invoice_date) BETWEEN ? AND ?
            GROUP BY date(invoice_date)
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=[str(start_date), str(end_date)])
            
            if not df.empty:
                # Revenue chart
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df['date'], y=df['paid'], name='Paid', marker_color='#10b981'))
                fig.add_trace(go.Bar(x=df['date'], y=df['overdue'], name='Overdue', marker_color='#ef4444'))
                fig.add_trace(go.Bar(x=df['date'], y=df['pending'], name='Pending', marker_color='#3b82f6'))
                
                fig.update_layout(
                    barmode='group',
                    title='Daily Revenue Breakdown',
                    xaxis_title="Date",
                    yaxis_title=f"Amount ({get_currency_symbol(st.session_state.currency)})",
                    hovermode='x unified',
                    plot_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Invoices", df['invoice_count'].sum())
                with col2:
                    st.metric("Total Revenue", format_amount(df['paid'].sum(), st.session_state.currency))
                with col3:
                    st.metric("Average per Invoice", 
                             format_amount(df['paid'].sum() / df['invoice_count'].sum() if df['invoice_count'].sum() > 0 else 0, 
                                         st.session_state.currency))
                with col4:
                    collection_rate = (df['paid'].sum() / (df['paid'].sum() + df['overdue'].sum() + df['pending'].sum()) * 100)
                    st.metric("Collection Rate", f"{collection_rate:.1f}%")
            else:
                st.info("No data available for selected period")
    except Exception as e:
        st.error(f"Error generating report: {e}")

def render_client_analysis(start_date, end_date):
    """Render client analysis report"""
    try:
        with get_db_connection() as conn:
            query = """
            SELECT 
                client_name,
                COUNT(*) as invoice_count,
                SUM(grand_total) as total_billed,
                SUM(CASE WHEN status = 'Paid' THEN grand_total ELSE 0 END) as total_paid,
                SUM(CASE WHEN status NOT IN ('Paid', 'Cancelled') THEN balance_due ELSE 0 END) as outstanding
            FROM invoices
            WHERE date(invoice_date) BETWEEN ? AND ?
            GROUP BY client_name
            ORDER BY total_billed DESC
            LIMIT 10
            """
            df = pd.read_sql_query(query, conn, params=[str(start_date), str(end_date)])
            
            if not df.empty:
                # Top clients chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df['client_name'],
                    y=df['total_billed'],
                    name='Total Billed',
                    marker_color='#3b82f6'
                ))
                fig.add_trace(go.Bar(
                    x=df['client_name'],
                    y=df['total_paid'],
                    name='Paid',
                    marker_color='#10b981'
                ))
                
                fig.update_layout(
                    title='Top Clients by Revenue',
                    xaxis_title="Client",
                    yaxis_title=f"Amount ({get_currency_symbol(st.session_state.currency)})",
                    barmode='group',
                    plot_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Client table
                df['collection_rate'] = (df['total_paid'] / df['total_billed'] * 100).round(1)
                st.dataframe(
                    df,
                    column_config={
                        "client_name": "Client",
                        "invoice_count": "Invoices",
                        "total_billed": st.column_config.NumberColumn("Total Billed", format=f"{get_currency_symbol(st.session_state.currency)}%.2f"),
                        "total_paid": st.column_config.NumberColumn("Paid", format=f"{get_currency_symbol(st.session_state.currency)}%.2f"),
                        "outstanding": st.column_config.NumberColumn("Outstanding", format=f"{get_currency_symbol(st.session_state.currency)}%.2f"),
                        "collection_rate": "Collection Rate %"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No client data available for selected period")
    except Exception as e:
        st.error(f"Error generating report: {e}")

def render_payment_trends(start_date, end_date):
    """Render payment trends report"""
    try:
        with get_db_connection() as conn:
            query = """
            SELECT 
                date(payment_date) as date,
                payment_method,
                SUM(amount) as total
            FROM payments
            WHERE date(payment_date) BETWEEN ? AND ?
            GROUP BY date(payment_date), payment_method
            ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=[str(start_date), str(end_date)])
            
            if not df.empty:
                # Payment trend line chart
                fig = px.line(
                    df, 
                    x='date', 
                    y='total', 
                    color='payment_method',
                    title='Payment Trends by Method'
                )
                fig.update_layout(plot_bgcolor='white')
                st.plotly_chart(fig, use_container_width=True)
                
                # Payment method distribution
                method_totals = df.groupby('payment_method')['total'].sum().reset_index()
                fig2 = px.pie(
                    method_totals, 
                    values='total', 
                    names='payment_method',
                    title='Payment Method Distribution'
                )
                st.plotly_chart(fig2, use_container_width=True)
                
                # Summary stats
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Payments", len(df))
                with col2:
                    st.metric("Total Amount", format_amount(df['total'].sum(), st.session_state.currency))
            else:
                st.info("No payment data available for selected period")
    except Exception as e:
        st.error(f"Error generating report: {e}")

def render_tax_summary(start_date, end_date):
    """Render tax summary report"""
    try:
        with get_db_connection() as conn:
            query = """
            SELECT 
                strftime('%Y-%m', invoice_date) as month,
                SUM(tax_total) as tax_collected,
                COUNT(*) as invoice_count
            FROM invoices
            WHERE date(invoice_date) BETWEEN ? AND ?
            AND status = 'Paid'
            GROUP BY strftime('%Y-%m', invoice_date)
            ORDER BY month
            """
            df = pd.read_sql_query(query, conn, params=[str(start_date), str(end_date)])
            
            if not df.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df['month'],
                    y=df['tax_collected'],
                    name='Tax Collected',
                    marker_color='#8b5cf6'
                ))
                fig.update_layout(
                    title='Tax Collection by Month',
                    xaxis_title="Month",
                    yaxis_title=f"Tax Amount ({get_currency_symbol(st.session_state.currency)})",
                    plot_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                total_tax = df['tax_collected'].sum()
                st.metric("Total Tax Collected", format_amount(total_tax, st.session_state.currency))
                st.metric("Average Monthly Tax", format_amount(total_tax / len(df), st.session_state.currency))
            else:
                st.info("No tax data available for selected period")
    except Exception as e:
        st.error(f"Error generating report: {e}")

def render_aging_report():
    """Render aging report"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        with get_db_connection() as conn:
            query = f"""
            SELECT 
                client_name,
                invoice_number,
                invoice_date,
                due_date,
                grand_total,
                amount_paid,
                balance_due,
                julianday('{today}') - julianday(due_date) as days_overdue
            FROM invoices
            WHERE status NOT IN ('Paid', 'Cancelled')
            AND balance_due > 0
            ORDER BY days_overdue DESC
            """
            df = pd.read_sql_query(query, conn)
            
            if not df.empty:
                # Aging buckets
                buckets = {
                    'Current': 0,
                    '1-30 days': 0,
                    '31-60 days': 0,
                    '61-90 days': 0,
                    '90+ days': 0
                }
                
                for _, row in df.iterrows():
                    days = row['days_overdue'] if pd.notna(row['days_overdue']) else 0
                    if days <= 0:
                        buckets['Current'] += row['balance_due']
                    elif days <= 30:
                        buckets['1-30 days'] += row['balance_due']
                    elif days <= 60:
                        buckets['31-60 days'] += row['balance_due']
                    elif days <= 90:
                        buckets['61-90 days'] += row['balance_due']
                    else:
                        buckets['90+ days'] += row['balance_due']
                
                # Aging chart
                fig = go.Figure(data=[
                    go.Bar(
                        x=list(buckets.keys()),
                        y=list(buckets.values()),
                        marker_color=['#10b981', '#fbbf24', '#f59e0b', '#f97316', '#ef4444']
                    )
                ])
                fig.update_layout(
                    title='Aging Summary',
                    xaxis_title="Age",
                    yaxis_title=f"Amount ({get_currency_symbol(st.session_state.currency)})",
                    plot_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Detail table
                df['age'] = df['days_overdue'].apply(
                    lambda x: 'Current' if x <= 0 else
                             '1-30 days' if x <= 30 else
                             '31-60 days' if x <= 60 else
                             '61-90 days' if x <= 90 else
                             '90+ days'
                )
                
                st.dataframe(
                    df[['client_name', 'invoice_number', 'invoice_date', 'due_date', 'balance_due', 'age']],
                    column_config={
                        "client_name": "Client",
                        "invoice_number": "Invoice",
                        "invoice_date": "Date",
                        "due_date": "Due Date",
                        "balance_due": st.column_config.NumberColumn("Amount Due", format=f"{get_currency_symbol(st.session_state.currency)}%.2f"),
                        "age": "Age"
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                total_overdue = df[df['days_overdue'] > 0]['balance_due'].sum()
                st.warning(f"Total Overdue: {format_amount(total_overdue, st.session_state.currency)}")
            else:
                st.info("No outstanding invoices")
    except Exception as e:
        st.error(f"Error generating aging report: {e}")

# ============================================================================
# SETTINGS PAGE
# ============================================================================

def render_settings_page():
    """Render the settings page"""
    
    st.markdown('<div class="section-header">⚙️ Settings</div>', unsafe_allow_html=True)
    
    tabs = st.tabs(["Company", "Invoice", "Email", "Backup", "Users"])
    
    with tabs[0]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("### Company Information")
        
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM company_settings WHERE id = 1")
            company = c.fetchone()
            
            if company:
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("Company Name", value=company['name'])
                    new_address = st.text_input("Address", value=company['address'])
                    new_city = st.text_input("City", value=company['city'])
                    new_phone = st.text_input("Phone", value=company['phone'])
                
                with col2:
                    new_email = st.text_input("Email", value=company['email'])
                    new_tax_id = st.text_input("Tax ID", value=company['tax_id'])
                    new_bank = st.text_area("Bank Details", value=company['bank_details'], height=100)
                    new_vat = st.checkbox("VAT Registered", value=bool(company['vat_registered']))
                
                if st.button("💾 Update Company Settings", use_container_width=True):
                    with get_db_connection() as conn:
                        c = conn.cursor()
                        c.execute('''UPDATE company_settings 
                                   SET name=?, address=?, city=?, phone=?, email=?, 
                                       tax_id=?, bank_details=?, vat_registered=?, updated_at=?
                                   WHERE id=1''',
                                 (new_name, new_address, new_city, new_phone, new_email,
                                  new_tax_id, new_bank, new_vat, datetime.now().isoformat()))
                    st.success("Settings updated!")
                    
                    # Update session state
                    st.session_state.company_info.update({
                        'name': new_name,
                        'address': new_address,
                        'city': new_city,
                        'phone': new_phone,
                        'email': new_email,
                        'tax_id': new_tax_id,
                        'bank_details': new_bank,
                        'vat_registered': new_vat
                    })
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[1]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("### Invoice Defaults")
        
        col1, col2 = st.columns(2)
        with col1:
            default_currency = st.selectbox(
                "Default Currency",
                options=list(CURRENCIES.keys()),
                format_func=lambda x: CURRENCIES[x]['name'],
                index=list(CURRENCIES.keys()).index(st.session_state.company_info.get('default_currency', 'TTD'))
            )
            default_payment_terms = st.number_input("Default Payment Terms (days)", min_value=0, value=30)
        
        with col2:
            invoice_prefix = st.text_input("Invoice Number Prefix", value=st.session_state.company_info.get('invoice_prefix', 'INV'))
            default_tax_rate = st.number_input("Default Tax Rate %", min_value=0.0, max_value=100.0, value=0.0)
        
        if st.button("💾 Update Invoice Settings", use_container_width=True):
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute('''UPDATE company_settings 
                           SET default_currency=?, invoice_prefix=?, updated_at=?
                           WHERE id=1''',
                         (default_currency, invoice_prefix, datetime.now().isoformat()))
            
            st.session_state.company_info['default_currency'] = default_currency
            st.session_state.company_info['invoice_prefix'] = invoice_prefix
            st.success("Settings updated!")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[2]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("### Email Configuration")
        
        smtp_server = st.text_input("SMTP Server", value=os.getenv('SMTP_SERVER', 'smtp.gmail.com'))
        smtp_port = st.number_input("SMTP Port", value=int(os.getenv('SMTP_PORT', 587)))
        smtp_username = st.text_input("SMTP Username", value=os.getenv('SMTP_USERNAME', ''))
        smtp_password = st.text_input("SMTP Password", type="password", value=os.getenv('SMTP_PASSWORD', ''))
        
        if st.button("💾 Save Email Settings", use_container_width=True):
            # In production, save to .env file or database
            st.success("Email settings saved (mock)")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[3]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("### Database Backup")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Create Backup", use_container_width=True):
                backup_data, filename = backup_database()
                if backup_data:
                    st.download_button(
                        label="Download Backup",
                        data=backup_data,
                        file_name=filename,
                        mime="application/octet-stream"
                    )
                    st.success("Backup created!")
        
        with col2:
            uploaded_backup = st.file_uploader("Restore from Backup", type=['db'])
            if uploaded_backup and st.button("🔄 Restore Database", use_container_width=True):
                with open('temp_restore.db', 'wb') as f:
                    f.write(uploaded_backup.getvalue())
                if restore_database('temp_restore.db'):
                    st.success("Database restored successfully!")
                    os.remove('temp_restore.db')
                    st.rerun()
                else:
                    st.error("Failed to restore database")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[4]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("### User Management")
        
        # List users
        with get_db_connection() as conn:
            users_df = pd.read_sql_query("SELECT id, username, email, role, full_name, is_active FROM users", conn)
            
            if not users_df.empty:
                st.dataframe(users_df, use_container_width=True, hide_index=True)
            
            # Add user form
            with st.expander("Add New User"):
                with st.form("new_user"):
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    email = st.text_input("Email")
                    full_name = st.text_input("Full Name")
                    role = st.selectbox("Role", ['user', 'admin', 'viewer'])
                    
                    if st.form_submit_button("Create User"):
                        password_hash = hashlib.sha256(password.encode()).hexdigest()
                        c = conn.cursor()
                        c.execute('''INSERT INTO users 
                                   (username, password_hash, email, full_name, role, created_at)
                                   VALUES (?, ?, ?, ?, ?, ?)''',
                                 (username, password_hash, email, full_name, role, datetime.now().isoformat()))
                        st.success("User created!")
                        st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# HELP PAGE
# ============================================================================

def render_help_page():
    """Render the help page"""
    
    st.markdown('<div class="section-header">❓ Help & Support</div>', unsafe_allow_html=True)
    
    with st.expander("📖 Getting Started", expanded=True):
        st.markdown("""
        ### Welcome to Invoice Pro!
        
        **Quick Start Guide:**
        1. **Set up your company** - Go to Settings and enter your company details
        2. **Add your first client** - Use the Clients page to add client information
        3. **Create an invoice** - Navigate to Create Invoice and fill in the details
        4. **Add items** - Enter the products/services with quantities and prices
        5. **Save and send** - Save the invoice, download PDF, or email to client
        
        **Tips:**
        - Use the currency selector in the sidebar for multi-currency invoicing
        - Save frequent items as templates for faster invoicing
        - Track payments and view aging reports in the Reports section
        """)
    
    with st.expander("💡 Features Guide"):
        st.markdown("""
        ### Key Features
        
        **📄 Invoice Creation**
        - Create professional invoices with your logo
        - Add multiple items with tax and discount
        - Preview before saving
        
        **👥 Client Management**
        - Store client information
        - Quick client selection
        - Track client payment history
        
        **💰 Payment Tracking**
        - Record partial or full payments
        - Multiple payment methods
        - Automatic balance calculation
        
        **📊 Reports**
        - Revenue overview
        - Client analysis
        - Payment trends
        - Aging reports
        
        **🔄 Recurring Invoices**
        - Set up automatic recurring invoices
        - Daily, weekly, monthly options
        - Never miss a billing cycle
        
        **📧 Email Integration**
        - Send invoices directly to clients
        - PDF attachments automatically
        - Professional email templates
        """)
    
    with st.expander("❓ Frequently Asked Questions"):
        st.markdown("""
        **Q: How do I change the currency for an invoice?**
        A: Use the currency selector in the sidebar before creating the invoice.
        
        **Q: Can I edit an invoice after saving?**
        A: Yes, you can update the status and record payments, but for major changes, create a new invoice.
        
        **Q: How do I add my company logo?**
        A: Go to Settings > Company Information and upload your logo.
        
        **Q: Is my data secure?**
        A: All data is stored locally in an encrypted SQLite database. Regular backups are recommended.
        
        **Q: Can I export my invoices to Excel?**
        A: Yes, use the Export to Excel button on the View Invoices page.
        
        **Q: How do I set up recurring invoices?**
        A: When creating an invoice, go to the Advanced tab and select a recurring frequency.
        """)
    
    with st.expander("📞 Contact Support"):
        st.markdown("""
        ### Need Help?
        
        **Email:** support@invoicepro.com  
        **Phone:** +1 (868) 123-4567  
        **Hours:** Monday-Friday, 9am-5pm AST
        
        **Office Address:**  
        Invoice Pro Software  
        123 Business Street  
        Port of Spain, Trinidad
        """)
