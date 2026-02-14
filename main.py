# enhanced_invoice_app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import base64
import json
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import plotly.graph_objects as go
import plotly.express as px
from forex_python.converter import CurrencyRates
import stripe
from PIL import Image
import io
import hashlib
import re

# Set page configuration
st.set_page_config(
    page_title="Advanced Invoice Generator",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize all session state variables
def init_session_state():
    defaults = {
        'invoice_items': [],
        'invoice_number': f"INV-{datetime.now().strftime('%Y%m%d')}-001",
        'templates': {},
        'current_template': 'default',
        'company_info': {
            'name': 'Your Company Name',
            'address': '123 Business St.',
            'city': 'City, State 12345',
            'phone': '(555) 123-4567',
            'email': 'contact@company.com',
            'tax_id': 'TAX123456',
            'logo': None,
            'bank_details': 'Bank: Example Bank\nAccount: 123456789\nRouting: 987654321'
        },
        'currency': 'USD',
        'exchange_rates': {},
        'payment_links': [],
        'email_settings': {},
        'stripe_settings': {},
        'database_initialized': False,
        'user_id': 'default_user'
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .invoice-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
    }
    .total-section {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.5rem;
        border-radius: 10px;
        font-size: 1.2rem;
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 5px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        border: none;
        transition: all 0.3s;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .template-card {
        border: 2px solid #e0e0e0;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s;
    }
    .template-card:hover {
        border-color: #667eea;
        transform: scale(1.05);
    }
    .template-card.selected {
        border-color: #667eea;
        background-color: #f0f4ff;
    }
    </style>
""", unsafe_allow_html=True)

# Database setup and functions
def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect('invoices.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS invoices
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  invoice_number TEXT UNIQUE,
                  user_id TEXT,
                  invoice_data TEXT,
                  created_at TIMESTAMP,
                  status TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS clients
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  email TEXT,
                  address TEXT,
                  phone TEXT,
                  user_id TEXT,
                  UNIQUE(email, user_id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS templates
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  template_data TEXT,
                  user_id TEXT,
                  is_default BOOLEAN)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS payment_links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  invoice_number TEXT,
                  payment_url TEXT,
                  amount REAL,
                  currency TEXT,
                  status TEXT,
                  created_at TIMESTAMP)''')
    
    conn.commit()
    conn.close()
    st.session_state.database_initialized = True

# Currency conversion functions
def get_exchange_rates(base_currency='USD'):
    """Fetch current exchange rates"""
    try:
        c = CurrencyRates()
        currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR']
        rates = {}
        for currency in currencies:
            try:
                rates[currency] = c.get_rate(base_currency, currency)
            except:
                rates[currency] = 1.0
        return rates
    except Exception as e:
        st.warning(f"Could not fetch live rates: {e}")
        # Return default rates
        return {
            'USD': 1.0, 'EUR': 0.85, 'GBP': 0.73, 'JPY': 110.0,
            'CAD': 1.25, 'AUD': 1.35, 'CHF': 0.92, 'CNY': 6.45, 'INR': 74.0
        }

def convert_currency(amount, from_currency, to_currency):
    """Convert amount between currencies"""
    if from_currency == to_currency:
        return amount
    
    if not st.session_state.exchange_rates:
        st.session_state.exchange_rates = get_exchange_rates(from_currency)
    
    # Convert to USD first if needed
    if from_currency != 'USD':
        usd_amount = amount / st.session_state.exchange_rates.get(from_currency, 1)
    else:
        usd_amount = amount
    
    # Convert from USD to target currency
    converted = usd_amount * st.session_state.exchange_rates.get(to_currency, 1)
    return converted

# Email sending function
def send_invoice_email(recipient_email, subject, body, pdf_buffer=None):
    """Send invoice via email"""
    try:
        smtp_server = st.session_state.email_settings.get('smtp_server', 'smtp.gmail.com')
        smtp_port = st.session_state.email_settings.get('smtp_port', 587)
        sender_email = st.session_state.email_settings.get('sender_email')
        sender_password = st.session_state.email_settings.get('sender_password')
        
        if not all([sender_email, sender_password]):
            st.error("Email settings not configured")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        if pdf_buffer:
            part = MIMEApplication(pdf_buffer.getvalue(), Name='invoice.pdf')
            part['Content-Disposition'] = 'attachment; filename="invoice.pdf"'
            msg.attach(part)
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# Stripe payment integration
def create_stripe_payment_link(amount, currency='usd', description='Invoice Payment'):
    """Create a Stripe payment link"""
    try:
        stripe.api_key = st.session_state.stripe_settings.get('api_key')
        
        # Create a product
        product = stripe.Product.create(
            name=description,
            type='service'
        )
        
        # Create a price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(amount * 100),  # Stripe uses cents
            currency=currency.lower()
        )
        
        # Create payment link
        payment_link = stripe.PaymentLink.create(
            line_items=[{
                'price': price.id,
                'quantity': 1,
            }]
        )
        
        return payment_link.url
    except Exception as e:
        st.error(f"Failed to create payment link: {e}")
        return None

# Template management
def save_template(name, template_data):
    """Save invoice template"""
    conn = sqlite3.connect('invoices.db')
    c = conn.cursor()
    
    c.execute('''INSERT OR REPLACE INTO templates 
                 (name, template_data, user_id, is_default)
                 VALUES (?, ?, ?, ?)''',
              (name, json.dumps(template_data), st.session_state.user_id, False))
    
    conn.commit()
    conn.close()
    
    # Update session state
    st.session_state.templates[name] = template_data

def load_templates():
    """Load user templates"""
    conn = sqlite3.connect('invoices.db')
    c = conn.cursor()
    
    c.execute('SELECT name, template_data FROM templates WHERE user_id = ?',
              (st.session_state.user_id,))
    
    templates = {}
    for row in c.fetchall():
        templates[row[0]] = json.loads(row[1])
    
    conn.close()
    return templates

# Save invoice to database
def save_invoice_to_db(invoice_data, status='draft'):
    """Save invoice to database"""
    conn = sqlite3.connect('invoices.db')
    c = conn.cursor()
    
    try:
        c.execute('''INSERT INTO invoices 
                     (invoice_number, user_id, invoice_data, created_at, status)
                     VALUES (?, ?, ?, ?, ?)''',
                  (invoice_data['invoice_number'], 
                   st.session_state.user_id,
                   json.dumps(invoice_data),
                   datetime.now().isoformat(),
                   status))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Update existing invoice
        c.execute('''UPDATE invoices 
                     SET invoice_data = ?, status = ?
                     WHERE invoice_number = ? AND user_id = ?''',
                  (json.dumps(invoice_data), status,
                   invoice_data['invoice_number'], st.session_state.user_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Database error: {e}")
        return False
    finally:
        conn.close()

# Main app layout
st.markdown("""
    <div class="main-header">
        <h1>💼 Advanced Invoice Generator Pro</h1>
        <p>Professional invoicing with multi-currency, templates, payment integration, and more</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar navigation
with st.sidebar:
    st.image("https://via.placeholder.com/300x100/667eea/ffffff?text=Invoice+Pro", use_container_width=True)
    
    menu_options = [
        "📝 Create Invoice",
        "📋 Templates",
        "👥 Clients",
        "💰 Multi-Currency",
        "💳 Payment Integration",
        "📧 Email Settings",
        "📊 Analytics",
        "🗄️ Database"
    ]
    
    choice = st.radio("Navigation", menu_options)
    
    st.markdown("---")
    st.markdown(f"**Current User:** {st.session_state.user_id}")
    st.markdown(f"**Default Currency:** {st.session_state.currency}")
    
    if st.button("🔄 Initialize Database"):
        init_database()
        st.success("Database initialized!")

# Main content area based on navigation choice
if choice == "📝 Create Invoice":
    # Create invoice tabs
    tab1, tab2, tab3 = st.tabs(["Basic Info", "Items", "Preview & Send"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📋 Invoice Details")
            
            # Invoice basic information
            inv_col1, inv_col2 = st.columns(2)
            with inv_col1:
                invoice_number = st.text_input("Invoice Number", st.session_state.invoice_number)
            with inv_col2:
                template_choice = st.selectbox("Select Template", 
                                               list(st.session_state.templates.keys()) if st.session_state.templates else ["Default"])
            
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                invoice_date = st.date_input("Invoice Date", datetime.now())
            with date_col2:
                due_date = st.date_input("Due Date", datetime.now() + timedelta(days=30))
            
            # Additional fields
            with st.expander("Additional Information", expanded=True):
                po_number = st.text_input("PO Number")
                shipping_address = st.text_area("Shipping Address")
                terms_conditions = st.text_area("Terms & Conditions", 
                                               "Payment due within 30 days. Thank you for your business!")
                notes = st.text_area("Additional Notes")
        
        with col2:
            st.markdown("### 🏢 Company & Client")
            
            # Client information with database lookup
            st.markdown("#### Client Information")
            
            # Client search/select
            conn = sqlite3.connect('invoices.db')
            clients_df = pd.read_sql_query(
                "SELECT name, email, address, phone FROM clients WHERE user_id = ?",
                conn, params=(st.session_state.user_id,)
            )
            conn.close()
            
            if not clients_df.empty:
                client_choice = st.selectbox("Select Existing Client", 
                                           ["New Client"] + clients_df['name'].tolist())
                
                if client_choice != "New Client":
                    client_data = clients_df[clients_df['name'] == client_choice].iloc[0]
                    client_name = client_data['name']
                    client_email = client_data['email']
                    client_address = client_data['address']
                    client_phone = client_data['phone']
                else:
                    client_name = st.text_input("Client Name")
                    client_email = st.text_input("Client Email")
                    client_address = st.text_area("Client Address")
                    client_phone = st.text_input("Client Phone")
            else:
                client_name = st.text_input("Client Name")
                client_email = st.text_input("Client Email")
                client_address = st.text_area("Client Address")
                client_phone = st.text_input("Client Phone")
    
    with tab2:
        st.markdown("### 📦 Invoice Items")
        
        # Item input form
        with st.form("add_item_form", clear_on_submit=True):
            cols = st.columns([3, 1, 1, 1, 1, 1])
            
            with cols[0]:
                description = st.text_input("Description")
            with cols[1]:
                quantity = st.number_input("Qty", min_value=1, value=1)
            with cols[2]:
                unit_price = st.number_input("Unit Price", min_value=0.0, value=0.0, step=10.0)
            with cols[3]:
                tax_rate = st.number_input("Tax %", min_value=0.0, max_value=100.0, value=0.0, step=5.0)
            with cols[4]:
                discount = st.number_input("Discount %", min_value=0.0, max_value=100.0, value=0.0, step=5.0)
            with cols[5]:
                submitted = st.form_submit_button("➕ Add")
            
            if submitted and description:
                subtotal = quantity * unit_price
                discount_amount = subtotal * (discount / 100)
                taxable_amount = subtotal - discount_amount
                tax_amount = taxable_amount * (tax_rate / 100)
                total = taxable_amount + tax_amount
                
                st.session_state.invoice_items.append({
                    'description': description,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'tax_rate': tax_rate,
                    'discount': discount,
                    'subtotal': subtotal,
                    'discount_amount': discount_amount,
                    'taxable_amount': taxable_amount,
                    'tax_amount': tax_amount,
                    'total': total
                })
                st.success(f"Added: {description}")
        
        # Display current items
        if st.session_state.invoice_items:
            df_items = pd.DataFrame(st.session_state.invoice_items)
            
            # Edit items
            edited_df = st.data_editor(
                df_items,
                column_config={
                    "description": "Description",
                    "quantity": st.column_config.NumberColumn("Qty", min_value=1),
                    "unit_price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
                    "tax_rate": st.column_config.NumberColumn("Tax %", format="%.1f%%"),
                    "discount": st.column_config.NumberColumn("Discount %", format="%.1f%%"),
                    "subtotal": st.column_config.NumberColumn("Subtotal", format="$%.2f", disabled=True),
                    "discount_amount": st.column_config.NumberColumn("Discount", format="$%.2f", disabled=True),
                    "tax_amount": st.column_config.NumberColumn("Tax", format="$%.2f", disabled=True),
                    "total": st.column_config.NumberColumn("Total", format="$%.2f", disabled=True)
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Calculate totals
            subtotal = df_items['subtotal'].sum()
            total_discount = df_items['discount_amount'].sum()
            total_tax = df_items['tax_amount'].sum()
            grand_total = df_items['total'].sum()
            
            # Display summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Subtotal", f"${subtotal:,.2f}")
            with col2:
                st.metric("Total Discount", f"${total_discount:,.2f}")
            with col3:
                st.metric("Total Tax", f"${total_tax:,.2f}")
            with col4:
                st.metric("Grand Total", f"${grand_total:,.2f}")
    
    with tab3:
        st.markdown("### 👁️ Preview & Send")
        
        if st.session_state.invoice_items:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Invoice preview based on selected template
                template_name = template_choice
                
                if template_name == "Default" or template_name not in st.session_state.templates:
                    # Default template
                    st.markdown(f"""
                    <div style='background-color: white; padding: 2rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                        <div style='display: flex; justify-content: space-between;'>
                            <div>
                                <h1 style='color: #667eea;'>INVOICE</h1>
                                <p><strong>Invoice #:</strong> {invoice_number}</p>
                                <p><strong>PO #:</strong> {po_number if po_number else 'N/A'}</p>
                                <p><strong>Date:</strong> {invoice_date.strftime('%Y-%m-%d')}</p>
                                <p><strong>Due Date:</strong> {due_date.strftime('%Y-%m-%d')}</p>
                            </div>
                            <div style='text-align: right;'>
                                <h3>{st.session_state.company_info['name']}</h3>
                                <p>{st.session_state.company_info['address']}<br>
                                {st.session_state.company_info['city']}</p>
                            </div>
                        </div>
                        
                        <hr>
                        
                        <h3>Bill To:</h3>
                        <p>{client_name}<br>
                        {client_address if client_address else 'No address provided'}<br>
                        Email: {client_email}</p>
                        
                        {f"<p><strong>Shipping Address:</strong><br>{shipping_address}</p>" if shipping_address else ""}
                        
                        <h3>Items:</h3>
                        {df_items.to_html(index=False)}
                        
                        <hr>
                        
                        <div style='text-align: right;'>
                            <p><strong>Subtotal:</strong> ${subtotal:,.2f}</p>
                            <p><strong>Discount:</strong> ${total_discount:,.2f}</p>
                            <p><strong>Tax:</strong> ${total_tax:,.2f}</p>
                            <h2>Total Due: ${grand_total:,.2f}</h2>
                        </div>
                        
                        {f"<hr><p><strong>Terms:</strong> {terms_conditions}</p>" if terms_conditions else ""}
                        {f"<p><strong>Notes:</strong> {notes}</p>" if notes else ""}
                        
                        <hr>
                        
                        <div style='text-align: center; color: #666;'>
                            <p>{st.session_state.company_info.get('bank_details', '')}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Custom template
                    st.info(f"Using template: {template_name}")
                    # Apply custom template logic here
            
            with col2:
                st.markdown("### 📤 Send Invoice")
                
                # Save to database
                if st.button("💾 Save to Database", use_container_width=True):
                    invoice_data = {
                        'invoice_number': invoice_number,
                        'invoice_date': str(invoice_date),
                        'due_date': str(due_date),
                        'po_number': po_number,
                        'shipping_address': shipping_address,
                        'terms_conditions': terms_conditions,
                        'notes': notes,
                        'client': {
                            'name': client_name,
                            'email': client_email,
                            'address': client_address,
                            'phone': client_phone
                        },
                        'items': st.session_state.invoice_items,
                        'company_info': st.session_state.company_info,
                        'totals': {
                            'subtotal': float(subtotal),
                            'discount': float(total_discount),
                            'tax': float(total_tax),
                            'grand_total': float(grand_total)
                        }
                    }
                    
                    if save_invoice_to_db(invoice_data, 'draft'):
                        st.success("Invoice saved to database!")
                
                # Email sending
                st.markdown("#### Send via Email")
                recipient_email = st.text_input("Recipient Email", value=client_email if client_email else "")
                email_subject = st.text_input("Email Subject", f"Invoice {invoice_number}")
                email_body = st.text_area("Email Body", 
                    f"Dear {client_name},\n\nPlease find attached invoice {invoice_number} for ${grand_total:,.2f}.\n\nThank you for your business!")
                
                if st.button("📧 Send Email", use_container_width=True):
                    if recipient_email:
                        # Here you would generate PDF and send
                        st.info("Email functionality ready - PDF generation would happen here")
                        st.success(f"Email would be sent to {recipient_email}")
                    else:
                        st.warning("Please enter recipient email")
                
                # Payment link
                st.markdown("#### Payment Links")
                payment_amount = st.number_input("Payment Amount", value=float(grand_total))
                payment_currency = st.selectbox("Payment Currency", ['USD', 'EUR', 'GBP', 'JPY'], index=0)
                
                if st.button("💳 Generate Payment Link", use_container_width=True):
                    if st.session_state.stripe_settings.get('api_key'):
                        payment_url = create_stripe_payment_link(payment_amount, payment_currency)
                        if payment_url:
                            st.success("Payment link created!")
                            st.markdown(f"[Click to Pay]({payment_url})")
                    else:
                        st.warning("Please configure Stripe settings first")
                
                # Download options
                st.markdown("#### Download")
                if st.button("📥 Download JSON", use_container_width=True):
                    invoice_data = {
                        'invoice_number': invoice_number,
                        'items': st.session_state.invoice_items,
                        'client': client_name,
                        'total': grand_total
                    }
                    json_str = json.dumps(invoice_data, indent=2)
                    b64 = base64.b64encode(json_str.encode()).decode()
                    href = f'<a href="data:application/json;base64,{b64}" download="invoice_{invoice_number}.json">Download JSON</a>'
                    st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("Add items to preview invoice")

elif choice == "📋 Templates":
    st.markdown("### 🎨 Invoice Templates")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Create New Template")
        template_name = st.text_input("Template Name")
        
        st.markdown("##### Template Settings")
        primary_color = st.color_picker("Primary Color", "#667eea")
        secondary_color = st.color_picker("Secondary Color", "#764ba2")
        font_family = st.selectbox("Font Family", ["Arial", "Helvetica", "Times New Roman", "Courier"])
        show_logo = st.checkbox("Show Logo", True)
        show_bank_details = st.checkbox("Show Bank Details", True)
        
        if st.button("💾 Save Template", use_container_width=True):
            template_data = {
                'primary_color': primary_color,
                'secondary_color': secondary_color,
                'font_family': font_family,
                'show_logo': show_logo,
                'show_bank_details': show_bank_details,
                'created_at': datetime.now().isoformat()
            }
            save_template(template_name, template_data)
            st.success(f"Template '{template_name}' saved!")
    
    with col2:
        st.markdown("#### Available Templates")
        
        # Load templates from database
        st.session_state.templates = load_templates()
        
        if st.session_state.templates:
            # Display templates in a grid
            template_cols = st.columns(3)
            for idx, (name, data) in enumerate(st.session_state.templates.items()):
                with template_cols[idx % 3]:
                    st.markdown(f"""
                    <div class='template-card'>
                        <h4>{name}</h4>
                        <p>Primary: {data.get('primary_color', '#667eea')}</p>
                        <p>Font: {data.get('font_family', 'Arial')}</p>
                        <p>Created: {data.get('created_at', 'Unknown')[:10]}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"Use Template", key=f"use_{name}"):
                        st.session_state.current_template = name
                        st.success(f"Template '{name}' selected!")
        else:
            st.info("No templates saved yet")

elif choice == "👥 Clients":
    st.markdown("### 👥 Client Management")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Add New Client")
        with st.form("add_client_form"):
            new_name = st.text_input("Client Name")
            new_email = st.text_input("Email")
            new_phone = st.text_input("Phone")
            new_address = st.text_area("Address")
            
            if st.form_submit_button("➕ Add Client"):
                conn = sqlite3.connect('invoices.db')
                c = conn.cursor()
                
                try:
                    c.execute('''INSERT INTO clients (name, email, address, phone, user_id)
                               VALUES (?, ?, ?, ?, ?)''',
                            (new_name, new_email, new_address, new_phone, st.session_state.user_id))
                    conn.commit()
                    st.success(f"Client {new_name} added!")
                except sqlite3.IntegrityError:
                    st.warning("Client with this email already exists")
                finally:
                    conn.close()
    
    with col2:
        st.markdown("#### Client List")
        
        conn = sqlite3.connect('invoices.db')
        clients_df = pd.read_sql_query(
            "SELECT name, email, phone, address FROM clients WHERE user_id = ?",
            conn, params=(st.session_state.user_id,)
        )
        conn.close()
        
        if not clients_df.empty:
            st.dataframe(clients_df, use_container_width=True)
            
            # Export clients
            csv = clients_df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="clients.csv">Download Clients CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No clients added yet")

elif choice == "💰 Multi-Currency":
    st.markdown("### 💰 Multi-Currency Support")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Currency Settings")
        
        base_currency = st.selectbox("Base Currency", 
                                    ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR'],
                                    index=0)
        
        if st.button("🔄 Fetch Latest Rates"):
            with st.spinner("Fetching exchange rates..."):
                st.session_state.exchange_rates = get_exchange_rates(base_currency)
                st.success("Rates updated!")
        
        st.markdown("#### Set Default Currency")
        default_currency = st.selectbox("Default Invoice Currency",
                                       ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR'],
                                       index=0)
        
        if st.button("Save Default Currency"):
            st.session_state.currency = default_currency
            st.success(f"Default currency set to {default_currency}")
    
    with col2:
        st.markdown("#### Current Exchange Rates")
        
        if st.session_state.exchange_rates:
            rates_data = []
            for currency, rate in st.session_state.exchange_rates.items():
                rates_data.append({'Currency': currency, 'Rate': f"{rate:.4f}"})
            
            rates_df = pd.DataFrame(rates_data)
            st.dataframe(rates_df, use_container_width=True)
        else:
            st.info("Click 'Fetch Latest Rates' to get exchange rates")
        
        st.markdown("#### Currency Converter")
        amount = st.number_input("Amount", value=100.0)
        from_curr = st.selectbox("From", ['USD', 'EUR', 'GBP', 'JPY'], key='from_curr')
        to_curr = st.selectbox("To", ['USD', 'EUR', 'GBP', 'JPY'], key='to_curr')
        
        if st.button("Convert"):
            converted = convert_currency(amount, from_curr, to_curr)
            st.success(f"{amount} {from_curr} = {converted:.2f} {to_curr}")

elif choice == "💳 Payment Integration":
    st.markdown("### 💳 Payment Integration")
    
    tab1, tab2 = st.tabs(["Stripe Settings", "Payment Links"])
    
    with tab1:
        st.markdown("#### Stripe Configuration")
        
        api_key = st.text_input("Stripe API Key", 
                               value=st.session_state.stripe_settings.get('api_key', ''),
                               type="password")
        webhook_secret = st.text_input("Webhook Secret", 
                                     value=st.session_state.stripe_settings.get('webhook_secret', ''),
                                     type="password")
        
        if st.button("Save Stripe Settings"):
            st.session_state.stripe_settings = {
                'api_key': api_key,
                'webhook_secret': webhook_secret
            }
            st.success("Stripe settings saved!")
        
        st.markdown("---")
        st.markdown("#### How to get Stripe API keys:")
        st.markdown("""
        1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
        2. Navigate to Developers → API keys
        3. Copy your Secret key
        4. For webhooks, go to Developers → Webhooks
        """)
    
    with tab2:
        st.markdown("#### Created Payment Links")
        
        conn = sqlite3.connect('invoices.db')
        payments_df = pd.read_sql_query(
            "SELECT invoice_number, payment_url, amount, currency, status, created_at FROM payment_links",
            conn
        )
        conn.close()
        
        if not payments_df.empty:
            st.dataframe(payments_df, use_container_width=True)
        else:
            st.info("No payment links created yet")

elif choice == "📧 Email Settings":
    st.markdown("### 📧 Email Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### SMTP Settings")
        
        smtp_server = st.text_input("SMTP Server", value=st.session_state.email_settings.get('smtp_server', 'smtp.gmail.com'))
        smtp_port = st.number_input("SMTP Port", value=st.session_state.email_settings.get('smtp_port', 587))
        sender_email = st.text_input("Sender Email", value=st.session_state.email_settings.get('sender_email', ''))
        sender_password = st.text_input("Sender Password", type="password", 
                                      value=st.session_state.email_settings.get('sender_password', ''))
        
        if st.button("Save Email Settings"):
            st.session_state.email_settings = {
                'smtp_server': smtp_server,
                'smtp_port': smtp_port,
                'sender_email': sender_email,
                'sender_password': sender_password
            }
            st.success("Email settings saved!")
    
    with col2:
        st.markdown("#### Email Templates")
        
        email_template = st.text_area("Default Email Template",
            "Dear {client_name},\n\nPlease find attached invoice {invoice_number} for the amount of {amount}.\n\nThank you for your business!")
        
        if st.button("Save Template"):
            st.session_state.email_template = email_template
            st.success("Email template saved!")
        
        st.markdown("#### Test Connection")
        test_email = st.text_input("Test Email Address")
        
        if st.button("Send Test Email"):
            if test_email and st.session_state.email_settings.get('sender_email'):
                test_body = "This is a test email from your Invoice Generator system."
                if send_invoice_email(test_email, "Test Email", test_body):
                    st.success("Test email sent!")
                else:
                    st.error("Failed to send test email")
            else:
                st.warning("Please configure email settings first")

elif choice == "📊 Analytics":
    st.markdown("### 📊 Analytics Dashboard")
    
    conn = sqlite3.connect('invoices.db')
    
    # Get invoice statistics
    invoices_df = pd.read_sql_query(
        "SELECT * FROM invoices WHERE user_id = ?",
        conn, params=(st.session_state.user_id,)
    )
    
    conn.close()
    
    if not invoices_df.empty:
        # Parse invoice data
        totals = []
        dates = []
        
        for _, row in invoices_df.iterrows():
            data = json.loads(row['invoice_data'])
            if 'totals' in data:
                totals.append(data['totals']['grand_total'])
                dates.append(row['created_at'][:10])
        
        # Create visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            # Revenue over time
            if dates and totals:
                fig = px.line(x=dates, y=totals, title="Revenue Over Time")
                fig.update_layout(xaxis_title="Date", yaxis_title="Amount ($)")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Invoice status distribution
            status_counts = invoices_df['status'].value_counts()
            fig = px.pie(values=status_counts.values, names=status_counts.index, 
                        title="Invoice Status Distribution")
            st.plotly_chart(fig, use_container_width=True)
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Invoices", len(invoices_df))
        with col2:
            st.metric("Total Revenue", f"${sum(totals):,.2f}" if totals else "$0")
        with col3:
            st.metric("Average Invoice", f"${sum(totals)/len(totals):,.2f}" if totals else "$0")
        with col4:
            paid_count = len(invoices_df[invoices_df['status'] == 'paid'])
            st.metric("Paid Invoices", paid_count)
    else:
        st.info("No invoice data available for analytics")

elif choice == "🗄️ Database":
    st.markdown("### 🗄️ Database Management")
    
    conn = sqlite3.connect('invoices.db')
    
    tab1, tab2, tab3 = st.tabs(["Invoices", "Clients", "Backup"])
    
    with tab1:
        st.markdown("#### Stored Invoices")
        
        invoices_df = pd.read_sql_query(
            "SELECT invoice_number, created_at, status FROM invoices WHERE user_id = ?",
            conn, params=(st.session_state.user_id,)
        )
        
        if not invoices_df.empty:
            st.dataframe(invoices_df, use_container_width=True)
            
            # Export option
            csv = invoices_df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="invoices_export.csv">Download Invoices CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No invoices in database")
    
    with tab2:
        st.markdown("#### Stored Clients")
        
        clients_df = pd.read_sql_query(
            "SELECT name, email, phone, address FROM clients WHERE user_id = ?",
            conn, params=(st.session_state.user_id,)
        )
        
        if not clients_df.empty:
            st.dataframe(clients_df, use_container_width=True)
        else:
            st.info("No clients in database")
    
    with tab3:
        st.markdown("#### Database Backup")
        
        if st.button("📥 Download Database Backup"):
            with open('invoices.db', 'rb') as f:
                db_bytes = f.read()
            
            b64 = base64.b64encode(db_bytes).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="invoices_backup.db">Download Database</a>'
            st.markdown(href, unsafe_allow_html=True)
        
        st.markdown("#### Clear Database")
        st.warning("⚠️ This action cannot be undone!")
        
        confirm = st.checkbox("I understand this will delete all data")
        if confirm and st.button("🗑️ Clear All Data"):
            # Clear all tables
            c = conn.cursor()
            c.execute("DELETE FROM invoices WHERE user_id = ?", (st.session_state.user_id,))
            c.execute("DELETE FROM clients WHERE user_id = ?", (st.session_state.user_id,))
            c.execute("DELETE FROM templates WHERE user_id = ?", (st.session_state.user_id,))
            c.execute("DELETE FROM payment_links")
            conn.commit()
            st.success("All data cleared!")
    
    conn.close()

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>Made with ❤️ using Streamlit | Advanced Invoice Generator Pro v2.0</p>
        <p>💼 Multi-Currency | 📧 Email Integration | 💳 Payment Links | 🗄️ Database Storage</p>
    </div>
""", unsafe_allow_html=True)
