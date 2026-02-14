# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import base64
import json
import sqlite3
import smtplib
import logging
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
import io
import os
from dotenv import load_dotenv
from typing import Optional, Dict, List, Tuple, Any
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Optional imports with fallbacks
try:
    from forex_python.converter import CurrencyRates
    FOREX_AVAILABLE = True
except ImportError:
    FOREX_AVAILABLE = False
    logger.warning("forex-python not installed. Using fixed rates.")

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="TT Invoice Pro",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CURRENCY CONFIGURATION
# ============================================================================

# Comprehensive currency list including TTD
CURRENCIES = {
    'TTD': {'symbol': 'TT$', 'name': 'Trinidad & Tobago Dollar'},
    'USD': {'symbol': '$', 'name': 'US Dollar'},
    'EUR': {'symbol': '€', 'name': 'Euro'},
    'GBP': {'symbol': '£', 'name': 'British Pound'},
    'CAD': {'symbol': 'C$', 'name': 'Canadian Dollar'},
    'JPY': {'symbol': '¥', 'name': 'Japanese Yen'},
    'AUD': {'symbol': 'A$', 'name': 'Australian Dollar'},
    'CHF': {'symbol': 'Fr', 'name': 'Swiss Franc'},
    'CNY': {'symbol': '¥', 'name': 'Chinese Yuan'},
    'INR': {'symbol': '₹', 'name': 'Indian Rupee'},
    'BBD': {'symbol': 'Bds$', 'name': 'Barbadian Dollar'},
    'JMD': {'symbol': 'J$', 'name': 'Jamaican Dollar'},
    'GYD': {'symbol': 'G$', 'name': 'Guyanese Dollar'},
    'BZD': {'symbol': 'BZ$', 'name': 'Belize Dollar'},
    'XCD': {'symbol': 'EC$', 'name': 'East Caribbean Dollar'}
}

# Exchange rates (as of February 2025)
FIXED_RATES = {
    'TTD': {'USD': 0.1475, 'EUR': 0.1360, 'GBP': 0.1165, 'CAD': 0.1990, 'TTD': 1.0},
    'USD': {'TTD': 6.78, 'EUR': 0.92, 'GBP': 0.79, 'CAD': 1.35, 'USD': 1.0},
    'EUR': {'TTD': 7.35, 'USD': 1.09, 'GBP': 0.86, 'CAD': 1.46, 'EUR': 1.0},
    'GBP': {'TTD': 8.58, 'USD': 1.27, 'EUR': 1.16, 'CAD': 1.71, 'GBP': 1.0},
    'CAD': {'TTD': 5.02, 'USD': 0.74, 'EUR': 0.68, 'GBP': 0.59, 'CAD': 1.0}
}

# ============================================================================
# PROFESSIONAL CSS
# ============================================================================

st.markdown("""
    <style>
    /* Import professional fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global styles */
    .stApp {
        font-family: 'Inter', sans-serif;
        background-color: #f5f7fa;
    }
    
    /* Header styling */
    .app-header {
        background: white;
        padding: 1.5rem 2rem;
        border-bottom: 1px solid #e9ecef;
        margin-bottom: 2rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    .app-title {
        color: #1a2639;
        font-size: 1.8rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: -0.02em;
    }
    
    .app-subtitle {
        color: #5f6b7a;
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }
    
    /* Card styling */
    .business-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #e9ecef;
        margin-bottom: 1.5rem;
        transition: all 0.2s ease;
    }
    
    .business-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a2639;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #f0f2f5;
        letter-spacing: -0.01em;
    }
    
    .section-header i {
        color: #2d9cdb;
        margin-right: 0.5rem;
    }
    
    /* Metric styling */
    .metric-container {
        background: #f8fafc;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #e9ecef;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a2639;
        line-height: 1.2;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #5f6b7a;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }
    
    /* Table styling */
    .dataframe {
        font-family: 'Inter', sans-serif;
        border-collapse: collapse;
        width: 100%;
        font-size: 0.9rem;
    }
    
    .dataframe th {
        background-color: #f8fafc;
        color: #1a2639;
        font-weight: 600;
        padding: 0.75rem;
        text-align: left;
        border-bottom: 2px solid #e9ecef;
    }
    
    .dataframe td {
        padding: 0.75rem;
        border-bottom: 1px solid #e9ecef;
        color: #2c3e50;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }
    
    .badge-paid {
        background-color: #e1f7e8;
        color: #0b5e42;
    }
    
    .badge-pending {
        background-color: #fff4e5;
        color: #b45b0f;
    }
    
    .badge-draft {
        background-color: #e8ecf1;
        color: #2c3e50;
    }
    
    .badge-overdue {
        background-color: #fee9e7;
        color: #b34033;
    }
    
    /* Button styling */
    .stButton > button {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        font-size: 0.9rem;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease;
        border: 1px solid transparent;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
    }
    
    /* Primary button */
    .stButton > button[data-baseweb="button"] {
        background: #1a2639;
        color: white;
    }
    
    .stButton > button[data-baseweb="button"]:hover {
        background: #2c3e50;
    }
    
    /* Form styling */
    .stTextInput > div > div > input {
        font-family: 'Inter', sans-serif;
        border-radius: 8px;
        border: 1px solid #e9ecef;
        padding: 0.5rem 0.75rem;
        font-size: 0.9rem;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #2d9cdb;
        box-shadow: 0 0 0 3px rgba(45,156,219,0.1);
    }
    
    .stSelectbox > div > div > select {
        font-family: 'Inter', sans-serif;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    
    /* Footer */
    .app-footer {
        text-align: center;
        padding: 2rem;
        color: #8a9aa8;
        font-size: 0.85rem;
        border-top: 1px solid #e9ecef;
        margin-top: 3rem;
        background: white;
    }
    
    /* Divider */
    .custom-divider {
        height: 1px;
        background: linear-gradient(to right, transparent, #e9ecef, transparent);
        margin: 2rem 0;
    }
    
    /* Invoice preview */
    .invoice-preview {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        border: 1px solid #e9ecef;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
    }
    
    .company-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #f0f2f5;
    }
    
    .invoice-title {
        font-size: 2rem;
        font-weight: 700;
        color: #1a2639;
        letter-spacing: -0.02em;
    }
    
    .company-details {
        text-align: right;
        color: #5f6b7a;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    
    .client-details {
        background: #f8fafc;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    
    .totals-table {
        width: 300px;
        margin-left: auto;
        margin-top: 1.5rem;
    }
    
    .totals-table td {
        padding: 0.5rem;
    }
    
    .totals-table tr:last-child td {
        font-weight: 700;
        font-size: 1.1rem;
        border-top: 2px solid #e9ecef;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def init_database():
    """Initialize SQLite database"""
    try:
        conn = sqlite3.connect('invoices.db')
        c = conn.cursor()
        
        # Invoices table
        c.execute('''CREATE TABLE IF NOT EXISTS invoices
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      invoice_number TEXT UNIQUE,
                      user_id TEXT,
                      client_name TEXT,
                      client_email TEXT,
                      client_address TEXT,
                      invoice_date DATE,
                      due_date DATE,
                      currency TEXT,
                      subtotal REAL,
                      tax_total REAL,
                      discount_total REAL,
                      grand_total REAL,
                      status TEXT,
                      created_at TIMESTAMP,
                      pdf_path TEXT)''')
        
        # Invoice items table
        c.execute('''CREATE TABLE IF NOT EXISTS invoice_items
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      invoice_id INTEGER,
                      description TEXT,
                      quantity REAL,
                      unit_price REAL,
                      tax_rate REAL,
                      discount_rate REAL,
                      amount REAL,
                      FOREIGN KEY (invoice_id) REFERENCES invoices(id))''')
        
        # Clients table
        c.execute('''CREATE TABLE IF NOT EXISTS clients
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      email TEXT,
                      phone TEXT,
                      address TEXT,
                      company TEXT,
                      tax_id TEXT,
                      user_id TEXT,
                      created_at TIMESTAMP,
                      UNIQUE(email, user_id))''')
        
        # Templates table
        c.execute('''CREATE TABLE IF NOT EXISTS templates
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      template_data TEXT,
                      user_id TEXT,
                      is_default BOOLEAN)''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False

# ============================================================================
# CURRENCY FUNCTIONS
# ============================================================================

def get_currency_symbol(currency_code):
    """Get currency symbol"""
    return CURRENCIES.get(currency_code, {'symbol': '$'})['symbol']

def format_amount(amount, currency='TTD'):
    """Format amount with currency symbol"""
    symbol = get_currency_symbol(currency)
    return f"{symbol}{amount:,.2f}"

def convert_currency(amount, from_currency, to_currency):
    """Convert between currencies"""
    if from_currency == to_currency:
        return amount
    
    try:
        if FOREX_AVAILABLE:
            c = CurrencyRates()
            rate = c.get_rate(from_currency, to_currency)
            return amount * rate
        else:
            # Use fixed rates
            if from_currency in FIXED_RATES and to_currency in FIXED_RATES[from_currency]:
                rate = FIXED_RATES[from_currency][to_currency]
                return amount * rate
            else:
                return amount
    except:
        return amount

# ============================================================================
# PDF GENERATION
# ============================================================================

def generate_pdf_invoice(invoice_data):
    """Generate PDF invoice"""
    if not PDF_AVAILABLE:
        return None
    
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        
        styles = getSampleStyleSheet()
        story = []
        
        # Company header
        company_info = invoice_data.get('company_info', {})
        company_text = f"""
        <b>{company_info.get('name', '')}</b><br/>
        {company_info.get('address', '')}<br/>
        {company_info.get('city', '')}<br/>
        Tel: {company_info.get('phone', '')}<br/>
        Email: {company_info.get('email', '')}
        """
        story.append(Paragraph(company_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Invoice title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a2639'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        story.append(Paragraph("INVOICE", title_style))
        
        # Invoice details
        details = f"""
        <b>Invoice Number:</b> {invoice_data.get('invoice_number', '')}<br/>
        <b>Date:</b> {invoice_data.get('invoice_date', '')}<br/>
        <b>Due Date:</b> {invoice_data.get('due_date', '')}
        """
        story.append(Paragraph(details, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Client info
        client = invoice_data.get('client', {})
        client_text = f"""
        <b>Bill To:</b><br/>
        {client.get('name', '')}<br/>
        {client.get('address', '')}<br/>
        Email: {client.get('email', '')}
        """
        story.append(Paragraph(client_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Items table
        if 'items' in invoice_data:
            table_data = [['Description', 'Qty', 'Price', 'Tax', 'Total']]
            
            for item in invoice_data['items']:
                table_data.append([
                    item.get('description', ''),
                    str(item.get('quantity', '')),
                    format_amount(item.get('unit_price', 0), invoice_data.get('currency', 'TTD')),
                    f"{item.get('tax_rate', 0)}%",
                    format_amount(item.get('total', 0), invoice_data.get('currency', 'TTD'))
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 20))
        
        # Totals
        totals = invoice_data.get('totals', {})
        totals_text = f"""
        <para alignment="right">
        <b>Subtotal:</b> {format_amount(totals.get('subtotal', 0), invoice_data.get('currency', 'TTD'))}<br/>
        <b>Tax:</b> {format_amount(totals.get('tax', 0), invoice_data.get('currency', 'TTD'))}<br/>
        <b>Discount:</b> {format_amount(totals.get('discount', 0), invoice_data.get('currency', 'TTD'))}<br/>
        <font size="14"><b>Total Due:</b> {format_amount(totals.get('grand_total', 0), invoice_data.get('currency', 'TTD'))}</font>
        </para>
        """
        story.append(Paragraph(totals_text, styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return None

# ============================================================================
# SESSION STATE
# ============================================================================

def init_session_state():
    """Initialize session state"""
    defaults = {
        'invoice_items': [],
        'invoice_number': f"INV-{datetime.now().strftime('%Y%m')}-{datetime.now().strftime('%d')}",
        'company_info': {
            'name': 'Your Business Name',
            'address': '123 Business Street',
            'city': 'Port of Spain, Trinidad',
            'phone': '(868) 123-4567',
            'email': 'accounts@yourbusiness.com',
            'tax_id': '123456789',
            'bank': 'First Citizens Bank\nAccount: 123456789\nSort Code: 123-456'
        },
        'currency': 'TTD',
        'clients': [],
        'templates': {},
        'database_initialized': False,
        'current_page': 'create'
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================================
# HEADER
# ============================================================================

st.markdown("""
    <div class="app-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="app-title">TT INVOICE PRO</h1>
                <div class="app-subtitle">Professional invoicing for Trinidad & Tobago businesses</div>
            </div>
            <div style="display: flex; gap: 1rem;">
                <span style="background: #f0f2f5; padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.9rem;">
                    💰 TTD
                </span>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown("### Navigation")
    
    pages = {
        "📄 Create Invoice": "create",
        "👥 Clients": "clients",
        "📋 Templates": "templates",
        "📊 Reports": "reports",
        "⚙️ Settings": "settings"
    }
    
    for page_name, page_id in pages.items():
        if st.button(page_name, use_container_width=True, 
                    type="primary" if st.session_state.current_page == page_id else "secondary"):
            st.session_state.current_page = page_id
            st.rerun()
    
    st.markdown("---")
    
    # Currency selector
    st.markdown("### Currency")
    selected_currency = st.selectbox(
        "Default currency",
        options=list(CURRENCIES.keys()),
        format_func=lambda x: f"{CURRENCIES[x]['name']} ({CURRENCIES[x]['symbol']})",
        index=list(CURRENCIES.keys()).index(st.session_state.currency)
    )
    
    if selected_currency != st.session_state.currency:
        st.session_state.currency = selected_currency
        st.rerun()
    
    st.markdown("---")
    
    # Quick stats
    st.markdown("### Quick Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
            <div class="metric-container">
                <div class="metric-value">0</div>
                <div class="metric-label">Invoices</div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
            <div class="metric-container">
                <div class="metric-value">0</div>
                <div class="metric-label">Clients</div>
            </div>
        """, unsafe_allow_html=True)

# ============================================================================
# MAIN CONTENT
# ============================================================================

# Initialize database
if not st.session_state.database_initialized:
    if init_database():
        st.session_state.database_initialized = True

# ============================================================================
# CREATE INVOICE PAGE
# ============================================================================

if st.session_state.current_page == "create":
    
    # Two-column layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">📋 Invoice Details</div>', unsafe_allow_html=True)
        
        # Invoice number
        invoice_number = st.text_input("Invoice Number", value=st.session_state.invoice_number)
        
        # Dates
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            invoice_date = st.date_input("Invoice Date", datetime.now())
        with date_col2:
            due_date = st.date_input("Due Date", datetime.now() + timedelta(days=30))
        
        # PO Number (optional)
        po_number = st.text_input("PO Number (optional)", placeholder="e.g., PO-2024-001")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Client section
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">👤 Client Information</div>', unsafe_allow_html=True)
        
        client_name = st.text_input("Client Name *")
        client_email = st.text_input("Email Address *")
        client_phone = st.text_input("Phone Number")
        client_address = st.text_area("Address", height=80)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Company info (collapsible)
        with st.expander("🏢 Company Information"):
            company_name = st.text_input("Company Name", value=st.session_state.company_info['name'])
            company_address = st.text_input("Address", value=st.session_state.company_info['address'])
            company_city = st.text_input("City", value=st.session_state.company_info['city'])
            company_phone = st.text_input("Phone", value=st.session_state.company_info['phone'])
            company_email = st.text_input("Email", value=st.session_state.company_info['email'])
            company_tax_id = st.text_input("Tax ID / TRN", value=st.session_state.company_info['tax_id'])
            company_bank = st.text_area("Bank Details", value=st.session_state.company_info['bank'], height=80)
            
            if st.button("Update Company Info"):
                st.session_state.company_info.update({
                    'name': company_name,
                    'address': company_address,
                    'city': company_city,
                    'phone': company_phone,
                    'email': company_email,
                    'tax_id': company_tax_id,
                    'bank': company_bank
                })
                st.success("Company information updated")
    
    with col2:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">📦 Invoice Items</div>', unsafe_allow_html=True)
        
        # Item entry form
        with st.form("item_form", clear_on_submit=True):
            item_col1, item_col2 = st.columns([3, 1])
            with item_col1:
                description = st.text_input("Description", placeholder="Item or service description")
            with item_col2:
                quantity = st.number_input("Qty", min_value=1, value=1)
            
            price_col1, price_col2, price_col3 = st.columns(3)
            with price_col1:
                unit_price = st.number_input(f"Unit Price ({CURRENCIES[st.session_state.currency]['symbol']})", 
                                            min_value=0.0, value=0.0, step=10.0)
            with price_col2:
                tax_rate = st.number_input("Tax %", min_value=0.0, max_value=100.0, value=0.0, step=2.5)
            with price_col3:
                discount = st.number_input("Discount %", min_value=0.0, max_value=100.0, value=0.0, step=5.0)
            
            if st.form_submit_button("➕ Add Item"):
                if description and unit_price > 0:
                    # Calculate amounts
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
                        'tax_amount': tax_amount,
                        'total': total
                    })
                    st.rerun()
        
        # Display items
        if st.session_state.invoice_items:
            df_items = pd.DataFrame(st.session_state.invoice_items)
            
            # Calculate totals
            subtotal = df_items['subtotal'].sum()
            total_discount = df_items['discount_amount'].sum()
            total_tax = df_items['tax_amount'].sum()
            grand_total = df_items['total'].sum()
            
            # Items table
            st.markdown("##### Current Items")
            
            # Display as a clean table
            for idx, item in enumerate(st.session_state.invoice_items):
                cols = st.columns([4, 1, 1, 1])
                with cols[0]:
                    st.write(f"**{item['description']}**")
                    st.caption(f"Qty: {item['quantity']} × {format_amount(item['unit_price'], st.session_state.currency)}")
                with cols[1]:
                    st.write(f"Tax: {item['tax_rate']}%")
                with cols[2]:
                    st.write(f"Disc: {item['discount']}%")
                with cols[3]:
                    st.write(f"**{format_amount(item['total'], st.session_state.currency)}**")
                    if st.button("✖", key=f"del_{idx}"):
                        st.session_state.invoice_items.pop(idx)
                        st.rerun()
                st.divider()
            
            # Summary
            st.markdown("##### Summary")
            summary_cols = st.columns(4)
            with summary_cols[0]:
                st.metric("Subtotal", format_amount(subtotal, st.session_state.currency))
            with summary_cols[1]:
                st.metric("Discount", format_amount(total_discount, st.session_state.currency))
            with summary_cols[2]:
                st.metric("Tax", format_amount(total_tax, st.session_state.currency))
            with summary_cols[3]:
                st.metric("Total", format_amount(grand_total, st.session_state.currency), delta=None)
            
            if st.button("Clear All Items", type="secondary"):
                st.session_state.invoice_items = []
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Preview section
    if st.session_state.invoice_items:
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-header">👁️ Invoice Preview</div>', unsafe_allow_html=True)
        
        preview_col1, preview_col2 = st.columns([2, 1])
        
        with preview_col1:
            # Professional invoice preview
            st.markdown(f"""
            <div class="invoice-preview">
                <div class="company-header">
                    <div>
                        <div class="invoice-title">INVOICE</div>
                        <div style="color: #5f6b7a; margin-top: 0.5rem;">
                            <span style="background: #f0f2f5; padding: 0.25rem 0.5rem; border-radius: 4px;">{invoice_number}</span>
                        </div>
                    </div>
                    <div class="company-details">
                        <strong>{company_name if 'company_name' in locals() else st.session_state.company_info['name']}</strong><br>
                        {company_address if 'company_address' in locals() else st.session_state.company_info['address']}<br>
                        {company_city if 'company_city' in locals() else st.session_state.company_info['city']}<br>
                        Tel: {company_phone if 'company_phone' in locals() else st.session_state.company_info['phone']}
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 2rem;">
                    <div>
                        <div style="font-weight: 600; color: #1a2639; margin-bottom: 0.5rem;">Bill To:</div>
                        <div style="color: #2c3e50;">
                            {client_name if client_name else 'Client Name'}<br>
                            {client_address if client_address else 'Client Address'}<br>
                            {client_email if client_email else 'client@email.com'}
                        </div>
                    </div>
                    <div>
                        <div style="font-weight: 600; color: #1a2639; margin-bottom: 0.5rem;">Invoice Details:</div>
                        <div style="color: #2c3e50;">
                            Date: {invoice_date.strftime('%d %b %Y')}<br>
                            Due: {due_date.strftime('%d %b %Y')}<br>
                            {f'PO: {po_number}' if po_number else ''}
                        </div>
                    </div>
                </div>
                
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 2rem;">
                    <thead>
                        <tr style="background: #f8fafc; border-bottom: 2px solid #e9ecef;">
                            <th style="padding: 0.75rem; text-align: left;">Description</th>
                            <th style="padding: 0.75rem; text-align: right;">Qty</th>
                            <th style="padding: 0.75rem; text-align: right;">Price</th>
                            <th style="padding: 0.75rem; text-align: right;">Tax</th>
                            <th style="padding: 0.75rem; text-align: right;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
            """, unsafe_allow_html=True)
            
            for item in st.session_state.invoice_items:
                st.markdown(f"""
                        <tr style="border-bottom: 1px solid #e9ecef;">
                            <td style="padding: 0.75rem;">{item['description']}</td>
                            <td style="padding: 0.75rem; text-align: right;">{item['quantity']}</td>
                            <td style="padding: 0.75rem; text-align: right;">{format_amount(item['unit_price'], st.session_state.currency)}</td>
                            <td style="padding: 0.75rem; text-align: right;">{item['tax_rate']}%</td>
                            <td style="padding: 0.75rem; text-align: right;">{format_amount(item['total'], st.session_state.currency)}</td>
                        </tr>
                """, unsafe_allow_html=True)
            
            st.markdown(f"""
                    </tbody>
                </table>
                
                <div style="display: flex; justify-content: flex-end;">
                    <table class="totals-table">
                        <tr>
                            <td>Subtotal:</td>
                            <td style="text-align: right;">{format_amount(subtotal, st.session_state.currency)}</td>
                        </tr>
                        <tr>
                            <td>Discount:</td>
                            <td style="text-align: right;">({format_amount(total_discount, st.session_state.currency)})</td>
                        </tr>
                        <tr>
                            <td>Tax:</td>
                            <td style="text-align: right;">{format_amount(total_tax, st.session_state.currency)}</td>
                        </tr>
                        <tr>
                            <td style="font-weight: 700;">Total Due:</td>
                            <td style="text-align: right; font-weight: 700; font-size: 1.2rem;">{format_amount(grand_total, st.session_state.currency)}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e9ecef; color: #5f6b7a; font-size: 0.85rem;">
                    <strong>Payment Details:</strong><br>
                    {company_bank if 'company_bank' in locals() else st.session_state.company_info.get('bank', 'Bank details not provided')}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with preview_col2:
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Actions")
            
            # Save invoice
            if st.button("💾 Save Invoice", use_container_width=True):
                invoice_data = {
                    'invoice_number': invoice_number,
                    'invoice_date': str(invoice_date),
                    'due_date': str(due_date),
                    'po_number': po_number,
                    'client': {
                        'name': client_name,
                        'email': client_email,
                        'phone': client_phone,
                        'address': client_address
                    },
                    'company_info': st.session_state.company_info,
                    'items': st.session_state.invoice_items,
                    'currency': st.session_state.currency,
                    'totals': {
                        'subtotal': subtotal,
                        'discount': total_discount,
                        'tax': total_tax,
                        'grand_total': grand_total
                    }
                }
                
                try:
                    conn = sqlite3.connect('invoices.db')
                    c = conn.cursor()
                    c.execute('''INSERT INTO invoices 
                               (invoice_number, client_name, client_email, client_address,
                                invoice_date, due_date, currency, subtotal, tax_total,
                                discount_total, grand_total, status, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (invoice_number, client_name, client_email, client_address,
                              str(invoice_date), str(due_date), st.session_state.currency,
                              subtotal, total_tax, total_discount, grand_total,
                              'draft', datetime.now().isoformat()))
                    invoice_id = c.lastrowid
                    
                    # Save items
                    for item in st.session_state.invoice_items:
                        c.execute('''INSERT INTO invoice_items
                                   (invoice_id, description, quantity, unit_price,
                                    tax_rate, discount_rate, amount)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                 (invoice_id, item['description'], item['quantity'],
                                  item['unit_price'], item['tax_rate'], item['discount'],
                                  item['total']))
                    
                    conn.commit()
                    conn.close()
                    st.success("Invoice saved successfully!")
                except Exception as e:
                    st.error(f"Error saving invoice: {e}")
            
            # Generate PDF
            if PDF_AVAILABLE:
                if st.button("📄 Download PDF", use_container_width=True):
                    invoice_data = {
                        'invoice_number': invoice_number,
                        'invoice_date': str(invoice_date),
                        'due_date': str(due_date),
                        'client': {
                            'name': client_name,
                            'email': client_email,
                            'address': client_address
                        },
                        'company_info': st.session_state.company_info,
                        'items': st.session_state.invoice_items,
                        'currency': st.session_state.currency,
                        'totals': {
                            'subtotal': subtotal,
                            'discount': total_discount,
                            'tax': total_tax,
                            'grand_total': grand_total
                        }
                    }
                    
                    pdf_buffer = generate_pdf_invoice(invoice_data)
                    if pdf_buffer:
                        b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="invoice_{invoice_number}.pdf" style="display: none;" id="downloadLink"></a>'
                        st.markdown(href, unsafe_allow_html=True)
                        st.markdown('<script>document.getElementById("downloadLink").click();</script>', unsafe_allow_html=True)
                        st.success("PDF generated successfully!")
                    else:
                        st.error("Could not generate PDF")
            else:
                st.info("PDF generation requires reportlab: pip install reportlab")
            
            # Email option
            st.markdown("##### Email Invoice")
            email_to = st.text_input("Send to", value=client_email if client_email else "")
            if st.button("📧 Send Email", use_container_width=True):
                if email_to:
                    st.info("Email functionality - configure SMTP settings first")
                else:
                    st.warning("Please enter an email address")
            
            # New invoice
            if st.button("➕ New Invoice", use_container_width=True):
                st.session_state.invoice_items = []
                st.session_state.invoice_number = f"INV-{datetime.now().strftime('%Y%m')}-{datetime.now().strftime('%d')}"
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# CLIENTS PAGE
# ============================================================================

elif st.session_state.current_page == "clients":
    st.markdown('<div class="section-header">👥 Client Management</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Add New Client")
        
        with st.form("client_form"):
            name = st.text_input("Client Name *")
            email = st.text_input("Email *")
            phone = st.text_input("Phone")
            address = st.text_area("Address")
            company = st.text_input("Company")
            tax_id = st.text_input("TRN / Tax ID")
            
            if st.form_submit_button("Add Client"):
                if name and email:
                    try:
                        conn = sqlite3.connect('invoices.db')
                        c = conn.cursor()
                        c.execute('''INSERT INTO clients 
                                   (name, email, phone, address, company, tax_id, user_id, created_at)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                 (name, email, phone, address, company, tax_id, 
                                  'default_user', datetime.now().isoformat()))
                        conn.commit()
                        conn.close()
                        st.success(f"Client {name} added successfully!")
                    except Exception as e:
                        st.error(f"Error adding client: {e}")
                else:
                    st.warning("Name and email are required")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Client List")
        
        try:
            conn = sqlite3.connect('invoices.db')
            clients_df = pd.read_sql_query(
                "SELECT name, email, phone, company, created_at FROM clients WHERE user_id = 'default_user' ORDER BY created_at DESC",
                conn
            )
            conn.close()
            
            if not clients_df.empty:
                for _, client in clients_df.iterrows():
                    with st.expander(f"**{client['name']}** - {client['company'] if client['company'] else 'No company'}"):
                        st.write(f"📧 {client['email']}")
                        st.write(f"📞 {client['phone'] if client['phone'] else 'No phone'}")
                        st.write(f"📅 Added: {client['created_at'][:10]}")
            else:
                st.info("No clients yet. Add your first client.")
        except:
            st.info("Client database not ready")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# REPORTS PAGE
# ============================================================================

elif st.session_state.current_page == "reports":
    st.markdown('<div class="section-header">📊 Reports & Analytics</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
            <div class="business-card" style="text-align: center;">
                <div style="font-size: 2rem; color: #1a2639;">0</div>
                <div style="color: #5f6b7a;">Total Invoices</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="business-card" style="text-align: center;">
                <div style="font-size: 2rem; color: #1a2639;">{format_amount(0, st.session_state.currency)}</div>
                <div style="color: #5f6b7a;">Total Revenue</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div class="business-card" style="text-align: center;">
                <div style="font-size: 2rem; color: #1a2639;">0</div>
                <div style="color: #5f6b7a;">Paid</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
            <div class="business-card" style="text-align: center;">
                <div style="font-size: 2rem; color: #1a2639;">0</div>
                <div style="color: #5f6b7a;">Outstanding</div>
            </div>
        """, unsafe_allow_html=True)
    
    # Placeholder chart
    st.markdown('<div class="business-card">', unsafe_allow_html=True)
    st.markdown("##### Monthly Revenue")
    chart_data = pd.DataFrame({
        'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        'Revenue': [0, 0, 0, 0, 0, 0]
    })
    st.bar_chart(chart_data.set_index('Month'))
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# SETTINGS PAGE
# ============================================================================

elif st.session_state.current_page == "settings":
    st.markdown('<div class="section-header">⚙️ Settings</div>', unsafe_allow_html=True)
    
    tabs = st.tabs(["Company", "Currency", "Email", "Backup"])
    
    with tabs[0]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Company Information")
        
        with st.form("company_settings"):
            col1, col2 = st.columns(2)
            with col1:
                company_name = st.text_input("Company Name", value=st.session_state.company_info['name'])
                company_address = st.text_input("Address", value=st.session_state.company_info['address'])
                company_city = st.text_input("City", value=st.session_state.company_info['city'])
            with col2:
                company_phone = st.text_input("Phone", value=st.session_state.company_info['phone'])
                company_email = st.text_input("Email", value=st.session_state.company_info['email'])
                company_tax_id = st.text_input("TRN / Tax ID", value=st.session_state.company_info['tax_id'])
            
            company_bank = st.text_area("Bank Details", value=st.session_state.company_info.get('bank', ''), height=100)
            
            if st.form_submit_button("Save Company Settings"):
                st.session_state.company_info.update({
                    'name': company_name,
                    'address': company_address,
                    'city': company_city,
                    'phone': company_phone,
                    'email': company_email,
                    'tax_id': company_tax_id,
                    'bank': company_bank
                })
                st.success("Company settings saved!")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[1]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Currency Settings")
        
        default_currency = st.selectbox(
            "Default Currency",
            options=list(CURRENCIES.keys()),
            format_func=lambda x: f"{CURRENCIES[x]['name']} ({CURRENCIES[x]['symbol']})",
            index=list(CURRENCIES.keys()).index(st.session_state.currency)
        )
        
        if st.button("Set as Default"):
            st.session_state.currency = default_currency
            st.success(f"Default currency set to {CURRENCIES[default_currency]['name']}")
        
        st.markdown("##### Exchange Rates")
        st.info("Exchange rates are updated daily")
        
        # Show exchange rates
        rates_data = []
        base = st.session_state.currency
        for currency in ['USD', 'EUR', 'GBP', 'CAD']:
            if currency != base:
                rate = convert_currency(1, base, currency)
                rates_data.append({
                    'From': base,
                    'To': currency,
                    'Rate': f"{rate:.4f}"
                })
        
        if rates_data:
            st.table(pd.DataFrame(rates_data))
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[2]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Email Settings")
        
        smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
        smtp_port = st.number_input("SMTP Port", value=587)
        sender_email = st.text_input("Sender Email")
        sender_password = st.text_input("Sender Password", type="password")
        
        if st.button("Test Connection"):
            st.info("Email settings need to be configured")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[3]:
        st.markdown('<div class="business-card">', unsafe_allow_html=True)
        st.markdown("##### Database Backup")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Download Backup"):
                try:
                    with open('invoices.db', 'rb') as f:
                        db_bytes = f.read()
                    b64 = base64.b64encode(db_bytes).decode()
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="invoice_backup_{timestamp}.db">Click to Download</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("Backup created!")
                except:
                    st.warning("No database file found")
        
        with col2:
            uploaded_file = st.file_uploader("Restore from Backup", type=['db'])
            if uploaded_file:
                if st.button("Restore Database"):
                    try:
                        with open('invoices.db', 'wb') as f:
                            f.write(uploaded_file.getbuffer())
                        st.success("Database restored! Please restart the app.")
                    except:
                        st.error("Restore failed")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("""
    <div class="app-footer">
        <p>© 2025 TT Invoice Pro - Professional Invoicing for Trinidad & Tobago</p>
        <p style="font-size: 0.75rem; margin-top: 0.5rem;">Version 2.0 | All amounts in TTD unless specified</p>
    </div>
""", unsafe_allow_html=True)
