# app.py (Final version - Fixed currency dropdown, removed TT from header)
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

# PDF Generation imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("ReportLab not installed. PDF generation disabled.")

# Page configuration
st.set_page_config(
    page_title="Invoice Pro",
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
# CLEAN CSS - FIXED CURRENCY SELECTOR (NO BLACK BACKGROUND)
# ============================================================================

st.markdown("""
    <style>
    /* Global Styles */
    .stApp {
        background-color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #0f172a !important;
    }
    
    /* App Header - REMOVED TT */
    .app-header {
        background: white;
        padding: 1.5rem 2rem;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 2rem;
    }
    
    .app-title {
        color: #0f172a;
        font-size: 1.8rem;
        font-weight: 600;
        margin: 0;
    }
    
    .app-subtitle {
        color: #475569;
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }
    
    /* Cards */
    .business-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
    }
    
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
    }
    
    /* Button Styles */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
        border: none;
        cursor: pointer;
    }
    
    /* Primary Buttons - Blue */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #3b82f6);
        color: white !important;
    }
    
    /* Secondary Buttons - Blue Outline */
    .stButton > button:not([kind="primary"]) {
        background: white;
        color: #2563eb !important;
        border: 2px solid #2563eb;
    }
    
    /* Success Buttons - Green */
    .stButton > button:has(span:contains("Save")),
    .stButton > button:has(span:contains("Add")),
    .stButton > button:has(span:contains("Update")) {
        background: white;
        color: #059669 !important;
        border: 2px solid #059669;
    }
    
    /* Danger Buttons - Red */
    .stButton > button:has(span:contains("Delete")),
    .stButton > button:has(span:contains("Remove")),
    .stButton > button[key*="del"],
    .stButton > button[key*="remove"] {
        background: white;
        color: #dc2626 !important;
        border: 2px solid #dc2626;
    }
    
    /* Edit Buttons - Orange */
    .stButton > button[key*="edit"] {
        background: white;
        color: #ea580c !important;
        border: 2px solid #ea580c;
        padding: 0.25rem 0.5rem;
        font-size: 0.9rem;
    }
    
    /* PDF Button - Purple */
    .stButton > button:has(span:contains("PDF")) {
        background: white;
        color: #7c3aed !important;
        border: 2px solid #7c3aed;
    }
    
    /* Email Button - Orange */
    .stButton > button:has(span:contains("Email")) {
        background: white;
        color: #ea580c !important;
        border: 2px solid #ea580c;
    }
    
    /* New/Reset Buttons - Gray */
    .stButton > button:has(span:contains("New")),
    .stButton > button:has(span:contains("Reset")),
    .stButton > button:has(span:contains("Clear")) {
        background: white;
        color: #4b5563 !important;
        border: 2px solid #4b5563;
    }
    
    /* Sidebar Buttons */
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: left;
        justify-content: flex-start;
        margin-bottom: 0.25rem;
    }
    
    /* FIXED: Currency Selector - COMPLETELY REMOVED BLACK BACKGROUND */
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: white !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
    }
    
    .stSelectbox div[data-baseweb="select"] span {
        color: #1e293b !important;
    }
    
    .stSelectbox div[data-baseweb="select"] svg {
        fill: #1e293b !important;
    }
    
    /* Dropdown menu - NO BLACK BACKGROUND */
    div[data-baseweb="menu"] {
        background-color: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }
    
    div[data-baseweb="menu"] > div {
        background-color: white !important;
    }
    
    div[data-baseweb="menu"] li {
        background-color: white !important;
        color: #1e293b !important;
    }
    
    div[data-baseweb="menu"] li:hover {
        background-color: #f1f5f9 !important;
    }
    
    div[data-baseweb="menu"] li[aria-selected="true"] {
        background-color: #e2e8f0 !important;
        color: #0f172a !important;
        font-weight: 600;
    }
    
    /* Ensure no black backgrounds anywhere in select */
    .stSelectbox [data-baseweb="select"] {
        background-color: white !important;
    }
    
    .stSelectbox [data-baseweb="popover"] {
        background-color: white !important;
    }
    
    /* Form Inputs */
    .stTextInput input, .stNumberInput input, .stDateInput input,
    .stSelectbox select, .stTextArea textarea {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 0.5rem;
        color: #1e293b !important;
        background-color: white !important;
    }
    
    /* Logo Container */
    .logo-container {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 1rem;
        background: #f8fafc;
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Invoice Preview Container */
    .invoice-preview-container {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        border: 1px solid #e2e8f0;
        margin: 1rem 0 2rem 0;
    }
    
    /* Text wrapping in description */
    .preview-description, .preview-table td:first-child {
        white-space: normal !important;
        word-wrap: break-word !important;
        max-width: 300px;
    }
    
    /* Preview table styling */
    .preview-table {
        width: 100%;
        border-collapse: collapse;
    }
    
    .preview-table th {
        background: #f8fafc;
        padding: 0.75rem;
        text-align: left;
        border-bottom: 2px solid #e2e8f0;
        font-weight: 600;
        color: #0f172a;
    }
    
    .preview-table td {
        padding: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
        color: #1e293b;
    }
    
    .preview-table .amount {
        text-align: right;
    }
    
    /* Grand Total Box */
    .grand-total-box {
        background: #1e40af;
        padding: 1rem;
        border-radius: 8px;
        color: white;
    }
    
    .grand-total-box p {
        color: white !important;
        margin: 0;
    }
    
    /* Footer */
    .app-footer {
        text-align: center;
        padding: 2rem;
        color: #64748b;
        font-size: 0.85rem;
        border-top: 1px solid #e2e8f0;
        margin-top: 3rem;
        background: white;
    }
    
    /* Hide any code that might appear */
    pre, code {
        display: none !important;
    }
    
    /* Ensure text is visible */
    p, span, div, label {
        color: #1e293b;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# PDF GENERATION FUNCTIONS - WITH TEXT WRAPPING
# ============================================================================

def generate_pdf_invoice(invoice_data):
    """Generate PDF invoice - WITH TEXT WRAPPING"""
    if not PDF_AVAILABLE:
        return None
    
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               rightMargin=36, leftMargin=36,
                               topMargin=36, bottomMargin=36)
        
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0f172a'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#1e293b')
        )
        
        # Style for wrapped text in description
        description_style = ParagraphStyle(
            'Description',
            parent=normal_style,
            wordWrap='CJK',  # Enables text wrapping
            alignment=TA_LEFT
        )
        
        right_style = ParagraphStyle(
            'RightAlign',
            parent=normal_style,
            alignment=TA_RIGHT
        )
        
        # Get company info
        company = invoice_data.get('company_info', {})
        
        # Create header with logo if available
        header_data = []
        
        # Add logo if available
        logo_bytes = company.get('logo_bytes')
        if logo_bytes:
            try:
                img_buffer = io.BytesIO(logo_bytes)
                img = RLImage(img_buffer, width=1.5*inch, height=0.75*inch)
                header_data.append([img, Paragraph("<b>INVOICE</b>", title_style)])
            except:
                header_data.append([Paragraph(f"<b>{company.get('name', '')}</b>", normal_style), 
                                   Paragraph("<b>INVOICE</b>", title_style)])
        else:
            header_data.append([Paragraph(f"<b>{company.get('name', '')}</b>", normal_style), 
                               Paragraph("<b>INVOICE</b>", title_style)])
        
        # Add company details
        header_data.extend([
            [Paragraph(company.get('address', ''), normal_style),
             Paragraph(f"<b>#{invoice_data.get('invoice_number', '')}</b>", right_style)],
            [Paragraph(company.get('city', ''), normal_style),
             Paragraph(f"Date: {invoice_data.get('invoice_date', '')}", right_style)],
            [Paragraph(f"Phone: {company.get('phone', '')}", normal_style),
             Paragraph(f"Due: {invoice_data.get('due_date', '')}", right_style)],
            [Paragraph(f"Email: {company.get('email', '')}", normal_style),
             Paragraph(f"PO: {invoice_data.get('po_number', 'N/A')}", right_style)]
        ])
        
        header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 20))
        
        # Client info
        client = invoice_data.get('client', {})
        client_text = f"""
        <b>Bill To:</b><br/>
        {client.get('name', '')}<br/>
        {client.get('address', '')}<br/>
        {client.get('email', '')}
        """
        story.append(Paragraph(client_text, normal_style))
        story.append(Spacer(1, 20))
        
        # Items table - WITH TEXT WRAPPING
        if 'items' in invoice_data and invoice_data['items']:
            # Prepare table data with proper headers
            table_data = [
                ['Description', 'Qty', 'Unit Price', 'Tax %', 'Disc %', 'Total']
            ]
            
            currency = invoice_data.get('currency', 'TTD')
            symbol = get_currency_symbol(currency)
            
            for item in invoice_data['items']:
                # Use Paragraph for description to enable text wrapping
                desc_para = Paragraph(item.get('description', ''), description_style)
                
                table_data.append([
                    desc_para,  # This will now wrap text
                    str(item.get('quantity', '1')),
                    f"{symbol}{item.get('unit_price', 0):,.2f}",
                    f"{item.get('tax_rate', 0)}%",
                    f"{item.get('discount', 0)}%",
                    f"{symbol}{item.get('total', 0):,.2f}"
                ])
            
            # Create table with proper column widths - wider description column for wrapping
            col_widths = [2.8*inch, 0.4*inch, 0.8*inch, 0.5*inch, 0.5*inch, 1*inch]
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                
                # Body
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1e293b')),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Qty centered
                ('ALIGN', (2, 1), (5, -1), 'RIGHT'),   # Amounts right-aligned
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),    # Top alignment for wrapped text
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),    # Description left-aligned
            ]))
            
            story.append(table)
            story.append(Spacer(1, 20))
            
            # Totals section
            totals = invoice_data.get('totals', {})
            subtotal = totals.get('subtotal', 0)
            discount = totals.get('discount', 0)
            tax = totals.get('tax', 0)
            grand_total = totals.get('grand_total', 0)
            
            # Create totals table
            totals_data = [
                ['Subtotal:', f"{symbol}{subtotal:,.2f}"],
                ['Discount:', f"-{symbol}{discount:,.2f}"],
                ['Tax:', f"{symbol}{tax:,.2f}"],
                ['Grand Total:', f"{symbol}{grand_total:,.2f}"]
            ]
            
            totals_table = Table(totals_data, colWidths=[1.5*inch, 1.5*inch])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (1, -1), 12),
                ('LINEABOVE', (0, -1), (1, -1), 2, colors.HexColor('#2563eb')),
                ('BACKGROUND', (0, -1), (1, -1), colors.HexColor('#f0f9ff')),
                ('TEXTCOLOR', (0, -1), (1, -1), colors.HexColor('#0f172a')),
            ]))
            
            # Add totals table aligned to right
            story.append(Table([[totals_table]], colWidths=[7*inch]))
            story.append(Spacer(1, 20))
        
        # Payment details
        if company.get('bank_details'):
            story.append(Paragraph("<b>Payment Details:</b>", normal_style))
            story.append(Paragraph(company['bank_details'], normal_style))
            story.append(Spacer(1, 20))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Italic'],
            fontSize=9,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER
        )
        story.append(Paragraph("Thank you for your business!", footer_style))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return None

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def init_database():
    """Initialize SQLite database"""
    try:
        conn = sqlite3.connect('invoices.db')
        c = conn.cursor()
        
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
                      discount_total REAL,
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
# LOGO FUNCTIONS
# ============================================================================

def save_logo(uploaded_file):
    """Save uploaded logo to session state"""
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        encoded = base64.b64encode(bytes_data).decode()
        
        st.session_state.company_info['logo_bytes'] = bytes_data
        st.session_state.company_info['logo_base64'] = encoded
        st.session_state.company_info['logo_filename'] = uploaded_file.name
        st.session_state.company_info['logo_mime'] = uploaded_file.type
        return True
    return False

def get_logo_html(max_height="60px", max_width="150px"):
    """Get HTML for logo display"""
    if st.session_state.company_info.get('logo_base64'):
        mime = st.session_state.company_info.get('logo_mime', 'image/png')
        return f'<img src="data:{mime};base64,{st.session_state.company_info["logo_base64"]}" style="max-height: {max_height}; max-width: {max_width}; object-fit: contain;">'
    return ""

def remove_logo():
    """Remove logo from session state"""
    keys = ['logo_bytes', 'logo_base64', 'logo_filename', 'logo_mime']
    for key in keys:
        if key in st.session_state.company_info:
            del st.session_state.company_info[key]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_currency_symbol(currency_code):
    """Get currency symbol"""
    return CURRENCIES.get(currency_code, {'symbol': '$'})['symbol']

def format_amount(amount, currency='TTD'):
    """Format amount with currency symbol"""
    if amount == 0:
        return f"{get_currency_symbol(currency)}0.00"
    symbol = get_currency_symbol(currency)
    return f"{symbol}{amount:,.2f}"

# ============================================================================
# INITIALIZE SESSION STATE
# ============================================================================

def init_session_state():
    """Initialize all session state variables"""
    
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
        'clients': [],
        'edit_index': -1
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================================
# HEADER - REMOVED TT
# ============================================================================

st.markdown("""
    <div class="app-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="app-title">INVOICE PRO</h1>
                <div class="app-subtitle">Professional invoicing for Caribbean businesses</div>
            </div>
            <div style="background: #f1f5f9; padding: 0.5rem 1rem; border-radius: 6px; font-weight: 500;">
                Trinidad & Tobago Dollar
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
    
    # Currency selector - FIXED VISIBILITY (NO BLACK BACKGROUND)
    st.markdown("### Currency Settings")
    currency_options = list(CURRENCIES.keys())
    
    try:
        current_idx = currency_options.index(st.session_state.currency)
    except ValueError:
        current_idx = 0
        st.session_state.currency = 'TTD'
    
    # The selectbox will now be visible with white background
    selected_currency = st.selectbox(
        "Select Currency",
        options=currency_options,
        format_func=lambda x: f"{CURRENCIES[x]['name']} ({CURRENCIES[x]['symbol']})",
        index=current_idx,
        key="sidebar_currency"
    )
    
    if selected_currency != st.session_state.currency:
        st.session_state.currency = selected_currency
        st.rerun()
    
    st.markdown("---")
    
    # Quick stats
    st.markdown("### Quick Stats")
    st.metric("Items", str(len(st.session_state.invoice_items)))

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
        # Invoice Details Card
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">📋 Invoice Details</div>', unsafe_allow_html=True)
            
            invoice_number = st.text_input("Invoice Number *", value=st.session_state.invoice_number)
            
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
            st.markdown('<div class="section-header">👤 Client Information</div>', unsafe_allow_html=True)
            
            client_name = st.text_input("Client Name *")
            client_email = st.text_input("Email Address *")
            client_phone = st.text_input("Phone Number")
            client_address = st.text_area("Address", height=80)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Company Info Expander
        with st.expander("🏢 Company Information"):
            company_name = st.text_input("Company Name", value=st.session_state.company_info['name'])
            company_address = st.text_input("Address", value=st.session_state.company_info['address'])
            company_city = st.text_input("City", value=st.session_state.company_info['city'])
            company_phone = st.text_input("Phone", value=st.session_state.company_info['phone'])
            company_email = st.text_input("Email", value=st.session_state.company_info['email'])
            company_tax_id = st.text_input("TRN / Tax ID", value=st.session_state.company_info['tax_id'])
            company_bank = st.text_area("Bank Details", value=st.session_state.company_info.get('bank_details', ''), height=80)
            
            # Logo upload
            st.markdown("##### Company Logo")
            logo_file = st.file_uploader(
                "Upload Logo (PNG, JPG, JPEG)",
                type=['png', 'jpg', 'jpeg'],
                key="create_logo_upload"
            )
            
            if logo_file is not None:
                if save_logo(logo_file):
                    st.success(f"Logo uploaded: {logo_file.name}")
            
            # Show current logo
            if st.session_state.company_info.get('logo_base64'):
                st.markdown(f'<div class="logo-container">{get_logo_html("80px", "200px")}</div>', unsafe_allow_html=True)
                if st.button("🗑️ Remove Logo", key="remove_logo_create"):
                    remove_logo()
                    st.rerun()
            
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
        # Invoice Items Card
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">📦 Invoice Items</div>', unsafe_allow_html=True)
            
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
                
                description = st.text_input("Description *", value=default_desc)
                
                col_qty, col_price = st.columns(2)
                with col_qty:
                    quantity = st.number_input("Quantity", min_value=1, value=default_qty, step=1)
                with col_price:
                    unit_price = st.number_input(f"Unit Price ({get_currency_symbol(st.session_state.currency)})", 
                                                min_value=0.0, value=default_price, step=10.0, format="%.2f")
                
                col_tax, col_discount = st.columns(2)
                with col_tax:
                    tax_rate = st.number_input("Tax %", min_value=0.0, max_value=100.0, value=default_tax, step=0.5, format="%.1f")
                with col_discount:
                    discount = st.number_input("Discount %", min_value=0.0, max_value=100.0, value=default_discount, step=0.5, format="%.1f")
                
                col1, col2 = st.columns(2)
                with col1:
                    if editing:
                        if st.form_submit_button("✅ Update Item", use_container_width=True):
                            if description and unit_price > 0:
                                subtotal = quantity * unit_price
                                discount_amount = subtotal * (discount / 100)
                                taxable_amount = subtotal - discount_amount
                                tax_amount = taxable_amount * (tax_rate / 100)
                                total = taxable_amount + tax_amount
                                
                                st.session_state.invoice_items[st.session_state.edit_index] = {
                                    'description': description,
                                    'quantity': quantity,
                                    'unit_price': unit_price,
                                    'tax_rate': tax_rate,
                                    'discount': discount,
                                    'subtotal': subtotal,
                                    'discount_amount': discount_amount,
                                    'tax_amount': tax_amount,
                                    'total': total
                                }
                                st.session_state.edit_index = -1
                                st.rerun()
                    else:
                        if st.form_submit_button("➕ Add Item", use_container_width=True):
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
                
                with col2:
                    if editing:
                        if st.form_submit_button("❌ Cancel Edit", use_container_width=True):
                            st.session_state.edit_index = -1
                            st.rerun()
            
            # Display Items
            if st.session_state.invoice_items:
                st.markdown("##### Current Items")
                
                # Headers
                cols = st.columns([3, 1, 1, 1, 1, 1, 1])
                headers = ["Description", "Qty", "Price", "Tax", "Disc", "Total", "Actions"]
                for col, header in zip(cols, headers):
                    with col:
                        st.markdown(f"**{header}**")
                
                # Items
                for idx, item in enumerate(st.session_state.invoice_items):
                    cols = st.columns([3, 1, 1, 1, 1, 1, 1])
                    
                    with cols[0]:
                        st.write(item['description'])
                    with cols[1]:
                        st.write(str(item['quantity']))
                    with cols[2]:
                        st.write(format_amount(item['unit_price'], st.session_state.currency))
                    with cols[3]:
                        st.write(f"{item['tax_rate']}%")
                    with cols[4]:
                        st.write(f"{item['discount']}%")
                    with cols[5]:
                        st.write(f"**{format_amount(item['total'], st.session_state.currency)}**")
                    with cols[6]:
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
                
                st.divider()
                
                # Calculate totals
                subtotal = sum(item['subtotal'] for item in st.session_state.invoice_items)
                total_discount = sum(item['discount_amount'] for item in st.session_state.invoice_items)
                total_tax = sum(item['tax_amount'] for item in st.session_state.invoice_items)
                grand_total = sum(item['total'] for item in st.session_state.invoice_items)
                
                # Summary
                st.markdown("### 📊 Invoice Summary")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**Subtotal:** {format_amount(subtotal, st.session_state.currency)}")
                    st.info(f"**Discount:** -{format_amount(total_discount, st.session_state.currency)}")
                with col2:
                    st.info(f"**Tax:** {format_amount(total_tax, st.session_state.currency)}")
                    st.markdown(f'<div class="grand-total-box"><p style="font-size: 1.5rem; font-weight: 700;">GRAND TOTAL: {format_amount(grand_total, st.session_state.currency)}</p></div>', unsafe_allow_html=True)
                
                # Actions
                col_reset, col_update = st.columns(2)
                with col_reset:
                    if st.button("🔄 Reset All Items", use_container_width=True):
                        st.session_state.invoice_items = []
                        st.session_state.edit_index = -1
                        st.rerun()
                with col_update:
                    if st.button("📊 Recalculate All", use_container_width=True):
                        st.rerun()
            else:
                st.info("No items added yet. Use the form above to add items.")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Preview Section
    if st.session_state.invoice_items and client_name:
        st.markdown('<div class="section-header">👁️ Invoice Preview</div>', unsafe_allow_html=True)
        
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
                st.markdown(f"### INVOICE\n{invoice_number}")
            with col_right:
                st.markdown(f"""
                **{st.session_state.company_info['name']}**  
                {st.session_state.company_info['address']}  
                {st.session_state.company_info['city']}  
                {st.session_state.company_info['phone']}
                """)
            
            st.divider()
            
            # Client and Invoice Details
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Bill To:**")
                st.markdown(f"{client_name}\n\n{client_address}\n\n{client_email}")
            with col2:
                st.markdown("**Invoice Details:**")
                st.markdown(f"""
                Date: {invoice_date.strftime('%d %b %Y')}  
                Due: {due_date.strftime('%d %b %Y')}  
                {f'PO: {po_number}' if po_number else ''}
                """)
            
            st.divider()
            
            # Items Table - WITH TEXT WRAPPING
            items_data = []
            for item in st.session_state.invoice_items:
                items_data.append({
                    "Description": item['description'],
                    "Qty": item['quantity'],
                    "Price": format_amount(item['unit_price'], st.session_state.currency),
                    "Tax %": f"{item['tax_rate']}%",
                    "Disc %": f"{item['discount']}%",
                    "Total": format_amount(item['total'], st.session_state.currency)
                })
            
            if items_data:
                # Use markdown table for better text wrapping
                table_html = '<table class="preview-table">'
                table_html += '<tr><th>Description</th><th class="amount">Qty</th><th class="amount">Price</th><th class="amount">Tax %</th><th class="amount">Disc %</th><th class="amount">Total</th></tr>'
                
                for item in items_data:
                    table_html += '<tr>'
                    table_html += f'<td style="white-space: normal; word-wrap: break-word; max-width: 300px;">{item["Description"]}</td>'
                    table_html += f'<td class="amount">{item["Qty"]}</td>'
                    table_html += f'<td class="amount">{item["Price"]}</td>'
                    table_html += f'<td class="amount">{item["Tax %"]}</td>'
                    table_html += f'<td class="amount">{item["Disc %"]}</td>'
                    table_html += f'<td class="amount"><strong>{item["Total"]}</strong></td>'
                    table_html += '</tr>'
                
                table_html += '</table>'
                st.markdown(table_html, unsafe_allow_html=True)
            
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
                st.markdown(f"### GRAND TOTAL\n# {format_amount(grand_total, st.session_state.currency)}")
            
            # Payment Details
            if st.session_state.company_info.get('bank_details'):
                st.divider()
                st.markdown(f"**Payment Details:**\n{st.session_state.company_info['bank_details']}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Action Buttons
        st.markdown("---")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("💾 Save Invoice", use_container_width=True):
                try:
                    conn = sqlite3.connect('invoices.db')
                    c = conn.cursor()
                    c.execute('''INSERT INTO invoices 
                               (invoice_number, client_name, client_email, invoice_date, 
                                due_date, currency, subtotal, tax_total, discount_total,
                                grand_total, status, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (invoice_number, client_name, client_email, str(invoice_date),
                              str(due_date), st.session_state.currency, subtotal, 
                              total_tax, total_discount, grand_total, 'draft', datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
                    st.success("Invoice saved successfully!")
                except Exception as e:
                    st.error(f"Error saving: {e}")
        
        with col2:
            if PDF_AVAILABLE:
                if st.button("📄 Download PDF", use_container_width=True):
                    with st.spinner("Generating PDF..."):
                        invoice_data = {
                            'invoice_number': invoice_number,
                            'invoice_date': invoice_date.strftime('%d %b %Y'),
                            'due_date': due_date.strftime('%d %b %Y'),
                            'po_number': po_number,
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
                            st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="invoice_{invoice_number}.pdf" style="display: inline-block; padding: 0.5rem 1rem; background: #2563eb; color: white; text-decoration: none; border-radius: 6px; text-align: center;">📥 Download PDF</a>', unsafe_allow_html=True)
                        else:
                            st.error("Failed to generate PDF")
            else:
                st.button("📄 PDF (ReportLab required)", disabled=True, use_container_width=True)
        
        with col3:
            email_to = st.text_input("Email to:", value=client_email if client_email else "", key="email_input", label_visibility="collapsed", placeholder="Email address")
        
        with col4:
            if st.button("📧 Send Email", use_container_width=True, disabled=not email_to):
                if email_to:
                    st.info("Email functionality - configure SMTP settings in production")
                else:
                    st.warning("Enter an email address")
        
        with col5:
            if st.button("🔄 New Invoice", use_container_width=True):
                st.session_state.invoice_items = []
                st.session_state.edit_index = -1
                st.session_state.invoice_number = f"INV-{datetime.now().strftime('%Y%m')}-{datetime.now().strftime('%d')}"
                st.rerun()

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
                
                if st.form_submit_button("➕ Add Client", use_container_width=True):
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
        st.metric("Total Invoices", "0")
    with col2:
        st.metric("Total Revenue", format_amount(0, st.session_state.currency))
    with col3:
        st.metric("Active Clients", "0")
    
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
    
    tabs = st.tabs(["🏢 Company", "💰 Currency", "💾 Backup"])
    
    with tabs[0]:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            
            st.markdown("##### Company Logo")
            logo_file = st.file_uploader(
                "Choose logo image (PNG, JPG, JPEG)",
                type=['png', 'jpg', 'jpeg'],
                key="settings_logo_upload"
            )
            
            if logo_file is not None:
                if save_logo(logo_file):
                    st.success(f"Logo uploaded: {logo_file.name}")
            
            if st.session_state.company_info.get('logo_base64'):
                st.markdown(f'<div class="logo-container">{get_logo_html("80px", "200px")}</div>', unsafe_allow_html=True)
                if st.button("🗑️ Remove Logo", use_container_width=True, key="remove_logo_settings"):
                    remove_logo()
                    st.rerun()
            
            st.markdown("---")
            
            with st.form("company_settings_form"):
                st.markdown("##### Company Details")
                
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
                
                if st.form_submit_button("💾 Save Company Settings", use_container_width=True):
                    st.session_state.company_info.update({
                        'name': comp_name,
                        'address': comp_address,
                        'city': comp_city,
                        'phone': comp_phone,
                        'email': comp_email,
                        'tax_id': comp_tax,
                        'bank_details': comp_bank
                    })
                    st.success("Company settings saved successfully!")
            
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
                        st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="invoice_backup_{timestamp}.db">Click to Download</a>', unsafe_allow_html=True)
                        st.success("Backup created!")
                    except:
                        st.warning("No database file found")
            
            with col2:
                uploaded_file = st.file_uploader("Restore from Backup", type=['db'], key="db_restore")
                if uploaded_file is not None:
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
        <p>© 2026 Invoice Pro - Professional Invoicing for Caribbean businesses</p>
        <p style="font-size: 0.75rem; margin-top: 0.5rem;">Version 2.0</p>
    </div>
""", unsafe_allow_html=True)
