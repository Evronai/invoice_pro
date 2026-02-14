# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import base64
import json
import sqlite3
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

try:
    import stripe
    STRIPE_AVAILABLE = False
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

CURRENCIES = {
    'TTD': {'symbol': 'TT$', 'name': 'Trinidad & Tobago Dollar'},
    'USD': {'symbol': 'US$', 'name': 'US Dollar'},
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

# Exchange rates
FIXED_RATES = {
    'TTD': 6.78,  # TTD to USD
    'USD': 1.0,
    'EUR': 0.92,
    'GBP': 0.79,
    'CAD': 1.35
}

# ============================================================================
# PROFESSIONAL CSS - FIXED FOR READABILITY
# ============================================================================

st.markdown("""
    <style>
    /* Import professional fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global styles - FIXED: proper contrast */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #f5f7fa;
        color: #1e293b;
    }
    
    /* Override Streamlit defaults for better contrast */
    .stMarkdown, .stText, p, li, .st-cb, .st-at {
        color: #1e293b !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #0f172a !important;
        font-weight: 600;
    }
    
    /* Header styling - FIXED: dark text on light background */
    .app-header {
        background: white;
        padding: 1.5rem 2rem;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 2rem;
        color: #0f172a;
    }
    
    .app-title {
        color: #0f172a !important;
        font-size: 1.8rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: -0.02em;
    }
    
    .app-subtitle {
        color: #475569 !important;
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }
    
    /* Card styling - FIXED: dark text */
    .business-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
        color: #1e293b;
    }
    
    .business-card * {
        color: #1e293b;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #0f172a !important;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
    }
    
    /* Metric container */
    .metric-container {
        background: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #e2e8f0;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 600;
        color: #0f172a !important;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #475569 !important;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }
    
    /* Form labels - FIXED: visible */
    .stTextInput label, .stNumberInput label, .stDateInput label, .stSelectbox label, .stTextArea label {
        color: #1e293b !important;
        font-weight: 500;
        font-size: 0.9rem;
    }
    
    /* Input fields */
    .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox select, .stTextArea textarea {
        color: #1e293b !important;
        background-color: white !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px;
    }
    
    /* Button styling - FIXED: visible text */
    .stButton > button {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        background: white;
        color: #1e293b !important;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        border-color: #94a3b8;
        background: #f8fafc;
        color: #0f172a !important;
    }
    
    .stButton > button[kind="primary"] {
        background: #0f172a;
        color: white !important;
        border: none;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: #1e293b;
        color: white !important;
    }
    
    /* DataFrames - FIXED: visible text */
    .stDataFrame {
        color: #1e293b !important;
    }
    
    .dataframe {
        color: #1e293b !important;
    }
    
    .dataframe th {
        background-color: #f1f5f9;
        color: #0f172a !important;
        font-weight: 600;
        padding: 0.75rem;
    }
    
    .dataframe td {
        color: #1e293b !important;
        padding: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        color: #1e293b !important;
        background-color: #f8fafc;
        border-radius: 6px;
    }
    
    /* Success/Warning/Error messages - FIXED: readable */
    .stAlert {
        color: #1e293b !important;
    }
    
    .stSuccess {
        background-color: #dcfce7;
        color: #166534 !important;
    }
    
    .stWarning {
        background-color: #fef9c3;
        color: #854d0e !important;
    }
    
    .stError {
        background-color: #fee2e2;
        color: #991b1b !important;
    }
    
    .stInfo {
        background-color: #dbeafe;
        color: #1e40af !important;
    }
    
    /* Invoice preview - FIXED: dark text */
    .invoice-preview {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        border: 1px solid #e2e8f0;
        color: #1e293b;
    }
    
    .invoice-preview * {
        color: #1e293b;
    }
    
    .invoice-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .invoice-title {
        font-size: 2rem;
        font-weight: 600;
        color: #0f172a !important;
    }
    
    /* Table in preview */
    .invoice-preview table {
        color: #1e293b !important;
    }
    
    .invoice-preview th {
        color: #0f172a !important;
        font-weight: 600;
    }
    
    .invoice-preview td {
        color: #1e293b !important;
    }
    
    /* Sidebar - FIXED: readable */
    .css-1d391kg, .css-1wrcr25 {
        background-color: white;
    }
    
    .sidebar .sidebar-content {
        background-color: white;
        color: #1e293b;
    }
    
    /* Radio buttons and checkboxes */
    .stRadio label, .stCheckbox label {
        color: #1e293b !important;
    }
    
    /* Footer */
    .app-footer {
        text-align: center;
        padding: 2rem;
        color: #64748b !important;
        font-size: 0.85rem;
        border-top: 1px solid #e2e8f0;
        margin-top: 3rem;
        background: white;
    }
    
    .app-footer p {
        color: #64748b !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #64748b !important;
    }
    
    .stTabs [aria-selected="true"] {
        color: #0f172a !important;
        font-weight: 600;
    }
    
    /* Metric cards */
    div[data-testid="metric-container"] {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
    }
    
    div[data-testid="metric-container"] label {
        color: #475569 !important;
    }
    
    div[data-testid="metric-container"] div {
        color: #0f172a !important;
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
        
        # Create tables
        c.execute('''CREATE TABLE IF NOT EXISTS invoices
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      invoice_number TEXT UNIQUE,
                      client_name TEXT,
                      client_email TEXT,
                      invoice_date TEXT,
                      due_date TEXT,
                      currency TEXT,
                      subtotal REAL,
                      tax_total REAL,
                      grand_total REAL,
                      status TEXT,
                      created_at TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS clients
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      email TEXT UNIQUE,
                      phone TEXT,
                      address TEXT,
                      company TEXT,
                      created_at TEXT)''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_currency_symbol(currency_code):
    """Get currency symbol"""
    return CURRENCIES.get(currency_code, {'symbol': '$'})['symbol']

def format_amount(amount, currency='TTD'):
    """Format amount with currency symbol"""
    symbol = get_currency_symbol(currency)
    return f"{symbol}{amount:,.2f}"

# ============================================================================
# INITIALIZE SESSION STATE
# ============================================================================

def init_session_state():
    """Initialize all session state variables with safe defaults"""
    
    # Company info with all required fields
    company_info = {
        'name': 'Your Business Name',
        'address': '123 Business Street',
        'city': 'Port of Spain, Trinidad',
        'phone': '(868) 123-4567',
        'email': 'accounts@yourbusiness.com',
        'tax_id': '123456789',
        'bank_details': 'First Citizens Bank\nAccount: 123456789\nSort Code: 123-456'
    }
    
    defaults = {
        'invoice_items': [],
        'invoice_number': f"INV-{datetime.now().strftime('%Y%m')}-{datetime.now().strftime('%d')}",
        'company_info': company_info,
        'currency': 'TTD',
        'database_initialized': False,
        'current_page': 'create',
        'clients': []
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
                <div class="app-subtitle">Professional invoicing for Caribbean businesses</div>
            </div>
            <div style="background: #f1f5f9; padding: 0.5rem 1rem; border-radius: 6px; color: #0f172a; font-weight: 500;">
                <span style="color: #0f172a;">TT$</span> <span style="color: #0f172a;">Trinidad & Tobago Dollar</span>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR NAVIGATION
# ============================================================================

with st.sidebar:
    st.markdown("### Navigation")
    st.markdown("---")
    
    pages = {
        "📄 Create Invoice": "create",
        "👥 Clients": "clients",
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
    st.markdown("### Currency Settings")
    currency_options = list(CURRENCIES.keys())
    
    # Find index safely
    try:
        current_idx = currency_options.index(st.session_state.currency)
    except ValueError:
        current_idx = 0
        st.session_state.currency = 'TTD'
    
    selected_currency = st.selectbox(
        "Default Currency",
        options=currency_options,
        format_func=lambda x: f"{CURRENCIES[x]['name']} ({CURRENCIES[x]['symbol']})",
        index=current_idx
    )
    
    if selected_currency != st.session_state.currency:
        st.session_state.currency = selected_currency
        st.rerun()
    
    st.markdown("---")
    
    # Quick stats
    st.markdown("### Quick Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Invoices", "0", "0")
    with col2:
        st.metric("Clients", "0", "0")

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
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">📋 Invoice Details</div>', unsafe_allow_html=True)
            
            invoice_number = st.text_input("Invoice Number *", value=st.session_state.invoice_number)
            
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                invoice_date = st.date_input("Invoice Date", datetime.now())
            with date_col2:
                due_date = st.date_input("Due Date", datetime.now() + timedelta(days=30))
            
            po_number = st.text_input("PO Number (optional)", placeholder="e.g., PO-2024-001")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with st.container():
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
            company_tax_id = st.text_input("TRN / Tax ID", value=st.session_state.company_info['tax_id'])
            company_bank = st.text_area("Bank Details", value=st.session_state.company_info.get('bank_details', ''), height=80)
            
            if st.button("Update Company Info", use_container_width=True):
                st.session_state.company_info.update({
                    'name': company_name,
                    'address': company_address,
                    'city': company_city,
                    'phone': company_phone,
                    'email': company_email,
                    'tax_id': company_tax_id,
                    'bank_details': company_bank
                })
                st.success("Company information updated")
    
    with col2:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">📦 Invoice Items</div>', unsafe_allow_html=True)
            
            # Item entry form
            with st.form("item_form", clear_on_submit=True):
                description = st.text_input("Description *", placeholder="Item or service description")
                
                col_qty, col_price = st.columns(2)
                with col_qty:
                    quantity = st.number_input("Quantity", min_value=1, value=1)
                with col_price:
                    unit_price = st.number_input(f"Unit Price ({get_currency_symbol(st.session_state.currency)})", 
                                                min_value=0.0, value=0.0, step=10.0)
                
                col_tax, col_discount = st.columns(2)
                with col_tax:
                    tax_rate = st.number_input("Tax %", min_value=0.0, max_value=100.0, value=0.0, step=2.5)
                with col_discount:
                    discount = st.number_input("Discount %", min_value=0.0, max_value=100.0, value=0.0, step=5.0)
                
                if st.form_submit_button("Add Item", use_container_width=True):
                    if description and unit_price > 0:
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
                st.markdown("##### Current Items")
                
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
                
                # Calculate totals
                subtotal = sum(item['subtotal'] for item in st.session_state.invoice_items)
                total_discount = sum(item['discount_amount'] for item in st.session_state.invoice_items)
                total_tax = sum(item['tax_amount'] for item in st.session_state.invoice_items)
                grand_total = sum(item['total'] for item in st.session_state.invoice_items)
                
                # Summary
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                with col_s1:
                    st.metric("Subtotal", format_amount(subtotal, st.session_state.currency))
                with col_s2:
                    st.metric("Discount", format_amount(total_discount, st.session_state.currency))
                with col_s3:
                    st.metric("Tax", format_amount(total_tax, st.session_state.currency))
                with col_s4:
                    st.metric("Total", format_amount(grand_total, st.session_state.currency))
                
                if st.button("Clear All Items", use_container_width=True):
                    st.session_state.invoice_items = []
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Preview section
    if st.session_state.invoice_items and client_name:
        st.markdown('<div class="section-header">👁️ Invoice Preview</div>', unsafe_allow_html=True)
        
        preview_col1, preview_col2 = st.columns([2, 1])
        
        with preview_col1:
            st.markdown(f"""
            <div class="invoice-preview">
                <div class="invoice-header">
                    <div>
                        <div class="invoice-title">INVOICE</div>
                        <div style="color: #475569; margin-top: 0.5rem;">{invoice_number}</div>
                    </div>
                    <div style="text-align: right;">
                        <strong>{st.session_state.company_info['name']}</strong><br>
                        {st.session_state.company_info['address']}<br>
                        {st.session_state.company_info['city']}<br>
                        {st.session_state.company_info['phone']}
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 2rem;">
                    <div>
                        <strong>Bill To:</strong><br>
                        {client_name}<br>
                        {client_address if client_address else ''}<br>
                        {client_email}
                    </div>
                    <div>
                        <strong>Invoice Details:</strong><br>
                        Date: {invoice_date.strftime('%d %b %Y')}<br>
                        Due: {due_date.strftime('%d %b %Y')}<br>
                        {f'PO: {po_number}' if po_number else ''}
                    </div>
                </div>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
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
                        <tr style="border-bottom: 1px solid #e2e8f0;">
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
                
                <div style="margin-top: 2rem; display: flex; justify-content: flex-end;">
                    <table style="width: 300px;">
                        <tr>
                            <td style="padding: 0.25rem;">Subtotal:</td>
                            <td style="padding: 0.25rem; text-align: right;">{format_amount(subtotal, st.session_state.currency)}</td>
                        </tr>
                        <tr>
                            <td style="padding: 0.25rem;">Discount:</td>
                            <td style="padding: 0.25rem; text-align: right;">-{format_amount(total_discount, st.session_state.currency)}</td>
                        </tr>
                        <tr>
                            <td style="padding: 0.25rem;">Tax:</td>
                            <td style="padding: 0.25rem; text-align: right;">{format_amount(total_tax, st.session_state.currency)}</td>
                        </tr>
                        <tr style="border-top: 2px solid #e2e8f0;">
                            <td style="padding: 0.5rem 0.25rem; font-weight: 600;">Total:</td>
                            <td style="padding: 0.5rem 0.25rem; text-align: right; font-weight: 600;">{format_amount(grand_total, st.session_state.currency)}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; color: #475569;">
                    <strong>Payment Details:</strong><br>
                    {st.session_state.company_info.get('bank_details', 'Bank details not provided')}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with preview_col2:
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                st.markdown("##### Actions")
                
                if st.button("💾 Save Invoice", use_container_width=True):
                    try:
                        conn = sqlite3.connect('invoices.db')
                        c = conn.cursor()
                        c.execute('''INSERT INTO invoices 
                                   (invoice_number, client_name, client_email, invoice_date, 
                                    due_date, currency, subtotal, tax_total, grand_total, status, created_at)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                 (invoice_number, client_name, client_email, str(invoice_date),
                                  str(due_date), st.session_state.currency, subtotal, 
                                  total_tax, grand_total, 'draft', datetime.now().isoformat()))
                        conn.commit()
                        conn.close()
                        st.success("Invoice saved successfully!")
                    except Exception as e:
                        st.error(f"Error saving: {e}")
                
                if PDF_AVAILABLE:
                    st.button("📄 Download PDF", use_container_width=True)
                else:
                    st.info("PDF generation: pip install reportlab")
                
                st.markdown("##### Email Invoice")
                email_to = st.text_input("Send to", value=client_email if client_email else "")
                if st.button("📧 Send", use_container_width=True):
                    if email_to:
                        st.info("Email functionality - configure SMTP settings")
                    else:
                        st.warning("Enter an email address")
                
                if st.button("🔄 New Invoice", use_container_width=True):
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
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Add New Client")
            
            with st.form("client_form"):
                name = st.text_input("Client Name *")
                email = st.text_input("Email *")
                phone = st.text_input("Phone")
                address = st.text_area("Address")
                company = st.text_input("Company")
                
                if st.form_submit_button("Add Client", use_container_width=True):
                    if name and email:
                        try:
                            conn = sqlite3.connect('invoices.db')
                            c = conn.cursor()
                            c.execute('''INSERT INTO clients 
                                       (name, email, phone, address, company, created_at)
                                       VALUES (?, ?, ?, ?, ?, ?)''',
                                     (name, email, phone, address, company, datetime.now().isoformat()))
                            conn.commit()
                            conn.close()
                            st.success(f"Client {name} added!")
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("Name and email are required")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Client List")
            
            try:
                conn = sqlite3.connect('invoices.db')
                clients_df = pd.read_sql_query(
                    "SELECT name, email, phone, company FROM clients ORDER BY created_at DESC LIMIT 10",
                    conn
                )
                conn.close()
                
                if not clients_df.empty:
                    st.dataframe(clients_df, use_container_width=True, hide_index=True)
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
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Invoices", "0", "0")
    
    with col2:
        st.metric("Total Revenue", format_amount(0, st.session_state.currency), "0")
    
    with col3:
        st.metric("Active Clients", "0", "0")
    
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
    
    tabs = st.tabs(["Company", "Currency", "Backup"])
    
    with tabs[0]:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Company Information")
            
            with st.form("company_settings"):
                col1, col2 = st.columns(2)
                with col1:
                    comp_name = st.text_input("Company Name", value=st.session_state.company_info['name'])
                    comp_address = st.text_input("Address", value=st.session_state.company_info['address'])
                    comp_city = st.text_input("City", value=st.session_state.company_info['city'])
                with col2:
                    comp_phone = st.text_input("Phone", value=st.session_state.company_info['phone'])
                    comp_email = st.text_input("Email", value=st.session_state.company_info['email'])
                    comp_tax = st.text_input("TRN/Tax ID", value=st.session_state.company_info['tax_id'])
                
                comp_bank = st.text_area("Bank Details", value=st.session_state.company_info.get('bank_details', ''), height=100)
                
                if st.form_submit_button("Save Settings", use_container_width=True):
                    st.session_state.company_info.update({
                        'name': comp_name,
                        'address': comp_address,
                        'city': comp_city,
                        'phone': comp_phone,
                        'email': comp_email,
                        'tax_id': comp_tax,
                        'bank_details': comp_bank
                    })
                    st.success("Settings saved!")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[1]:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Currency Settings")
            
            new_currency = st.selectbox(
                "Default Currency",
                options=list(CURRENCIES.keys()),
                format_func=lambda x: f"{CURRENCIES[x]['name']} ({CURRENCIES[x]['symbol']})",
                index=list(CURRENCIES.keys()).index(st.session_state.currency)
            )
            
            if st.button("Set as Default", use_container_width=True):
                st.session_state.currency = new_currency
                st.success(f"Default currency set to {CURRENCIES[new_currency]['name']}")
            
            st.markdown("##### Exchange Rates (vs USD)")
            rates_data = []
            for currency in ['TTD', 'EUR', 'GBP', 'CAD']:
                if currency != 'USD':
                    rates_data.append({
                        'Currency': f"{CURRENCIES[currency]['name']} ({currency})",
                        'Rate': f"{FIXED_RATES.get(currency, 1.0):.4f}"
                    })
            
            if rates_data:
                st.table(pd.DataFrame(rates_data))
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[2]:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown("##### Database Backup")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 Download Backup", use_container_width=True):
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
                    if st.button("Restore Database", use_container_width=True):
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
