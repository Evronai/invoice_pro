# app_improved.py - Enhanced Invoice Pro Application
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

# Exchange rates (mock rates - in production, use live API)
FIXED_RATES = {
    'TTD': 6.78,  # TTD to USD
    'USD': 1.0,
    'EUR': 0.92,
    'GBP': 0.79,
    'CAD': 1.35,
    'JPY': 149.50,
    'AUD': 1.52,
    'CHF': 0.88,
    'CNY': 7.24,
    'INR': 83.12,
    'BBD': 2.00,
    'JMD': 155.50,
    'GYD': 209.00,
    'BZD': 2.00,
    'XCD': 2.70
}

# Invoice statuses
INVOICE_STATUSES = ['Draft', 'Sent', 'Paid', 'Overdue', 'Cancelled']
STATUS_COLORS = {
    'Draft': '#94a3b8',
    'Sent': '#3b82f6',
    'Paid': '#10b981',
    'Overdue': '#ef4444',
    'Cancelled': '#64748b'
}

# ============================================================================
# ENHANCED CSS STYLING
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
    
    /* App Header */
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
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    /* Button Styles */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
        border: none;
        cursor: pointer;
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #3b82f6);
        color: white !important;
    }
    
    .stButton > button:not([kind="primary"]) {
        background: white;
        color: #2563eb !important;
        border: 2px solid #2563eb;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Success Buttons */
    .stButton > button:has(span:contains("Save")),
    .stButton > button:has(span:contains("Add")),
    .stButton > button:has(span:contains("Update")) {
        background: white;
        color: #059669 !important;
        border: 2px solid #059669;
    }
    
    /* Danger Buttons */
    .stButton > button:has(span:contains("Delete")),
    .stButton > button:has(span:contains("Remove")),
    .stButton > button[key*="del"],
    .stButton > button[key*="remove"] {
        background: white;
        color: #dc2626 !important;
        border: 2px solid #dc2626;
    }
    
    /* Edit Buttons */
    .stButton > button[key*="edit"] {
        background: white;
        color: #ea580c !important;
        border: 2px solid #ea580c;
        padding: 0.25rem 0.5rem;
        font-size: 0.9rem;
    }
    
    /* PDF Button */
    .stButton > button:has(span:contains("PDF")) {
        background: white;
        color: #7c3aed !important;
        border: 2px solid #7c3aed;
    }
    
    /* Email Button */
    .stButton > button:has(span:contains("Email")) {
        background: white;
        color: #ea580c !important;
        border: 2px solid #ea580c;
    }
    
    /* New/Reset Buttons */
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
    
    /* Currency Selector - No black background */
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
    
    /* Invoice Preview */
    .invoice-preview-container {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        border: 1px solid #e2e8f0;
        margin: 1rem 0 2rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Text wrapping */
    .preview-description, .preview-table td:first-child {
        white-space: normal !important;
        word-wrap: break-word !important;
        max-width: 300px;
    }
    
    /* Preview table */
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
        background: linear-gradient(135deg, #1e40af, #3b82f6);
        padding: 1.5rem;
        border-radius: 8px;
        color: white;
        box-shadow: 0 4px 6px rgba(30, 64, 175, 0.3);
    }
    
    .grand-total-box p {
        color: white !important;
        margin: 0;
    }
    
    /* DataFrames */
    .dataframe {
        font-size: 0.9rem;
    }
    
    .dataframe th {
        background-color: #f8fafc !important;
        color: #0f172a !important;
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
    
    /* Hide code blocks */
    pre, code {
        display: none !important;
    }
    
    /* Text visibility */
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
    
    /* Success/Warning/Error messages */
    .stAlert {
        border-radius: 8px;
    }
    
    /* Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 600;
    }
    
    /* Search box */
    .search-box {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# DATABASE FUNCTIONS - ENHANCED
# ============================================================================

def init_database():
    """Initialize SQLite database with enhanced schema"""
    try:
        conn = sqlite3.connect('invoices.db')
        c = conn.cursor()
        
        # Invoices table
        c.execute('''CREATE TABLE IF NOT EXISTS invoices
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      invoice_number TEXT UNIQUE,
                      client_id INTEGER,
                      client_name TEXT,
                      client_email TEXT,
                      client_address TEXT,
                      client_phone TEXT,
                      invoice_date TEXT,
                      due_date TEXT,
                      po_number TEXT,
                      currency TEXT,
                      subtotal REAL,
                      tax_total REAL,
                      discount_total REAL,
                      grand_total REAL,
                      amount_paid REAL DEFAULT 0,
                      balance_due REAL,
                      status TEXT,
                      notes TEXT,
                      created_at TEXT,
                      updated_at TEXT,
                      sent_date TEXT,
                      paid_date TEXT)''')
        
        # Invoice items table
        c.execute('''CREATE TABLE IF NOT EXISTS invoice_items
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      invoice_id INTEGER,
                      description TEXT,
                      quantity REAL,
                      unit_price REAL,
                      tax_rate REAL,
                      discount REAL,
                      subtotal REAL,
                      discount_amount REAL,
                      tax_amount REAL,
                      total REAL,
                      FOREIGN KEY (invoice_id) REFERENCES invoices(id))''')
        
        # Clients table
        c.execute('''CREATE TABLE IF NOT EXISTS clients
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      email TEXT UNIQUE,
                      phone TEXT,
                      address TEXT,
                      company TEXT,
                      tax_id TEXT,
                      notes TEXT,
                      created_at TEXT,
                      updated_at TEXT)''')
        
        # Payments table
        c.execute('''CREATE TABLE IF NOT EXISTS payments
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      invoice_id INTEGER,
                      amount REAL,
                      payment_date TEXT,
                      payment_method TEXT,
                      reference TEXT,
                      notes TEXT,
                      created_at TEXT,
                      FOREIGN KEY (invoice_id) REFERENCES invoices(id))''')
        
        # Company settings table
        c.execute('''CREATE TABLE IF NOT EXISTS company_settings
                     (id INTEGER PRIMARY KEY,
                      name TEXT,
                      address TEXT,
                      city TEXT,
                      phone TEXT,
                      email TEXT,
                      tax_id TEXT,
                      bank_details TEXT,
                      logo_data BLOB,
                      logo_mime TEXT,
                      default_currency TEXT,
                      updated_at TEXT)''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False

def save_invoice_to_db(invoice_data, items):
    """Save invoice and items to database"""
    try:
        conn = sqlite3.connect('invoices.db')
        c = conn.cursor()
        
        # Calculate balance due
        balance_due = invoice_data['grand_total'] - invoice_data.get('amount_paid', 0)
        
        # Insert invoice
        c.execute('''INSERT INTO invoices 
                   (invoice_number, client_name, client_email, client_address, client_phone,
                    invoice_date, due_date, po_number, currency, subtotal, tax_total, 
                    discount_total, grand_total, amount_paid, balance_due, status, notes, 
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (invoice_data['invoice_number'], invoice_data['client_name'], 
                  invoice_data['client_email'], invoice_data.get('client_address', ''),
                  invoice_data.get('client_phone', ''), invoice_data['invoice_date'],
                  invoice_data['due_date'], invoice_data.get('po_number', ''),
                  invoice_data['currency'], invoice_data['subtotal'], 
                  invoice_data['tax_total'], invoice_data['discount_total'],
                  invoice_data['grand_total'], invoice_data.get('amount_paid', 0),
                  balance_due, invoice_data.get('status', 'Draft'),
                  invoice_data.get('notes', ''), datetime.now().isoformat(),
                  datetime.now().isoformat()))
        
        invoice_id = c.lastrowid
        
        # Insert invoice items
        for item in items:
            c.execute('''INSERT INTO invoice_items 
                       (invoice_id, description, quantity, unit_price, tax_rate, discount,
                        subtotal, discount_amount, tax_amount, total)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (invoice_id, item['description'], item['quantity'], item['unit_price'],
                      item['tax_rate'], item['discount'], item['subtotal'],
                      item['discount_amount'], item['tax_amount'], item['total']))
        
        conn.commit()
        conn.close()
        return invoice_id
    except Exception as e:
        logger.error(f"Save invoice error: {e}")
        return None

def update_invoice_status(invoice_id, new_status):
    """Update invoice status"""
    try:
        conn = sqlite3.connect('invoices.db')
        c = conn.cursor()
        
        update_fields = {'status': new_status, 'updated_at': datetime.now().isoformat()}
        
        if new_status == 'Sent':
            update_fields['sent_date'] = datetime.now().isoformat()
        elif new_status == 'Paid':
            update_fields['paid_date'] = datetime.now().isoformat()
        
        set_clause = ', '.join([f"{k} = ?" for k in update_fields.keys()])
        values = list(update_fields.values()) + [invoice_id]
        
        c.execute(f"UPDATE invoices SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Update status error: {e}")
        return False

def get_invoices(filters=None):
    """Get invoices with optional filters"""
    try:
        conn = sqlite3.connect('invoices.db')
        
        query = "SELECT * FROM invoices"
        params = []
        
        if filters:
            conditions = []
            if 'status' in filters and filters['status']:
                conditions.append("status = ?")
                params.append(filters['status'])
            if 'client_name' in filters and filters['client_name']:
                conditions.append("client_name LIKE ?")
                params.append(f"%{filters['client_name']}%")
            if 'date_from' in filters and filters['date_from']:
                conditions.append("invoice_date >= ?")
                params.append(filters['date_from'])
            if 'date_to' in filters and filters['date_to']:
                conditions.append("invoice_date <= ?")
                params.append(filters['date_to'])
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Get invoices error: {e}")
        return pd.DataFrame()

def get_invoice_by_id(invoice_id):
    """Get invoice details by ID"""
    try:
        conn = sqlite3.connect('invoices.db')
        
        # Get invoice
        invoice_df = pd.read_sql_query(
            "SELECT * FROM invoices WHERE id = ?", conn, params=[invoice_id]
        )
        
        if invoice_df.empty:
            conn.close()
            return None, None
        
        invoice = invoice_df.iloc[0].to_dict()
        
        # Get invoice items
        items_df = pd.read_sql_query(
            "SELECT * FROM invoice_items WHERE invoice_id = ?", conn, params=[invoice_id]
        )
        
        conn.close()
        
        items = items_df.to_dict('records') if not items_df.empty else []
        
        return invoice, items
    except Exception as e:
        logger.error(f"Get invoice by ID error: {e}")
        return None, None

def delete_invoice(invoice_id):
    """Delete invoice and its items"""
    try:
        conn = sqlite3.connect('invoices.db')
        c = conn.cursor()
        
        # Delete items first (foreign key constraint)
        c.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        
        # Delete payments
        c.execute("DELETE FROM payments WHERE invoice_id = ?", (invoice_id,))
        
        # Delete invoice
        c.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Delete invoice error: {e}")
        return False

def save_client_to_db(client_data):
    """Save or update client"""
    try:
        conn = sqlite3.connect('invoices.db')
        c = conn.cursor()
        
        # Check if client exists
        c.execute("SELECT id FROM clients WHERE email = ?", (client_data['email'],))
        existing = c.fetchone()
        
        if existing:
            # Update existing client
            c.execute('''UPDATE clients SET name = ?, phone = ?, address = ?, 
                        company = ?, tax_id = ?, notes = ?, updated_at = ?
                        WHERE email = ?''',
                     (client_data['name'], client_data.get('phone', ''),
                      client_data.get('address', ''), client_data.get('company', ''),
                      client_data.get('tax_id', ''), client_data.get('notes', ''),
                      datetime.now().isoformat(), client_data['email']))
            client_id = existing[0]
        else:
            # Insert new client
            c.execute('''INSERT INTO clients 
                       (name, email, phone, address, company, tax_id, notes, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (client_data['name'], client_data['email'], 
                      client_data.get('phone', ''), client_data.get('address', ''),
                      client_data.get('company', ''), client_data.get('tax_id', ''),
                      client_data.get('notes', ''), datetime.now().isoformat(),
                      datetime.now().isoformat()))
            client_id = c.lastrowid
        
        conn.commit()
        conn.close()
        return client_id
    except Exception as e:
        logger.error(f"Save client error: {e}")
        return None

def get_clients(search=None):
    """Get clients with optional search"""
    try:
        conn = sqlite3.connect('invoices.db')
        
        if search:
            query = "SELECT * FROM clients WHERE name LIKE ? OR email LIKE ? OR company LIKE ? ORDER BY name"
            params = [f"%{search}%", f"%{search}%", f"%{search}%"]
            df = pd.read_sql_query(query, conn, params=params)
        else:
            df = pd.read_sql_query("SELECT * FROM clients ORDER BY name", conn)
        
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Get clients error: {e}")
        return pd.DataFrame()

# ============================================================================
# PDF GENERATION - ENHANCED
# ============================================================================

def generate_pdf_invoice(invoice_data):
    """Generate PDF invoice with enhanced formatting"""
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
        
        description_style = ParagraphStyle(
            'Description',
            parent=normal_style,
            wordWrap='CJK',
            alignment=TA_LEFT
        )
        
        right_style = ParagraphStyle(
            'RightAlign',
            parent=normal_style,
            alignment=TA_RIGHT
        )
        
        # Get company info
        company = invoice_data.get('company_info', {})
        
        # Create header
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
        
        if invoice_data.get('status'):
            header_data.append([Paragraph("", normal_style),
                               Paragraph(f"<b>Status: {invoice_data['status']}</b>", right_style)])
        
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
        
        # Items table
        if 'items' in invoice_data and invoice_data['items']:
            table_data = [
                ['Description', 'Qty', 'Unit Price', 'Tax %', 'Disc %', 'Total']
            ]
            
            currency = invoice_data.get('currency', 'TTD')
            symbol = get_currency_symbol(currency)
            
            for item in invoice_data['items']:
                desc_para = Paragraph(item.get('description', ''), description_style)
                
                table_data.append([
                    desc_para,
                    str(item.get('quantity', '1')),
                    f"{symbol}{item.get('unit_price', 0):,.2f}",
                    f"{item.get('tax_rate', 0)}%",
                    f"{item.get('discount', 0)}%",
                    f"{symbol}{item.get('total', 0):,.2f}"
                ])
            
            col_widths = [2.8*inch, 0.4*inch, 0.8*inch, 0.5*inch, 0.5*inch, 1*inch]
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1e293b')),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ('ALIGN', (2, 1), (5, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 20))
            
            # Totals section
            totals = invoice_data.get('totals', {})
            subtotal = totals.get('subtotal', 0)
            discount = totals.get('discount', 0)
            tax = totals.get('tax', 0)
            grand_total = totals.get('grand_total', 0)
            
            totals_data = [
                ['Subtotal:', f"{symbol}{subtotal:,.2f}"],
                ['Discount:', f"-{symbol}{discount:,.2f}"],
                ['Tax:', f"{symbol}{tax:,.2f}"],
                ['Grand Total:', f"{symbol}{grand_total:,.2f}"]
            ]
            
            # Add payment info if available
            if invoice_data.get('amount_paid', 0) > 0:
                totals_data.append(['Amount Paid:', f"{symbol}{invoice_data['amount_paid']:,.2f}"])
                totals_data.append(['Balance Due:', f"{symbol}{invoice_data.get('balance_due', 0):,.2f}"])
            
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
            
            story.append(Table([[totals_table]], colWidths=[7*inch]))
            story.append(Spacer(1, 20))
        
        # Payment details
        if company.get('bank_details'):
            story.append(Paragraph("<b>Payment Details:</b>", normal_style))
            story.append(Paragraph(company['bank_details'], normal_style))
            story.append(Spacer(1, 20))
        
        # Notes
        if invoice_data.get('notes'):
            story.append(Paragraph("<b>Notes:</b>", normal_style))
            story.append(Paragraph(invoice_data['notes'], normal_style))
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
        
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return None

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

def calculate_item_totals(quantity, unit_price, tax_rate=0, discount=0):
    """Calculate item totals"""
    subtotal = quantity * unit_price
    discount_amount = subtotal * (discount / 100)
    taxable_amount = subtotal - discount_amount
    tax_amount = taxable_amount * (tax_rate / 100)
    total = taxable_amount + tax_amount
    
    return {
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'tax_amount': tax_amount,
        'total': total
    }

def generate_invoice_number():
    """Generate unique invoice number"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"INV-{timestamp}"

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

def get_status_badge_html(status):
    """Generate HTML for status badge"""
    color = STATUS_COLORS.get(status, '#64748b')
    return f'<span class="status-badge" style="background-color: {color}; color: white;">{status}</span>'

# ============================================================================
# SESSION STATE INITIALIZATION
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
        'invoice_number': generate_invoice_number(),
        'company_info': company_info,
        'currency': 'TTD',
        'database_initialized': False,
        'current_page': 'create',
        'clients': [],
        'edit_index': -1,
        'selected_client_id': None,
        'invoice_notes': '',
        'invoice_status': 'Draft',
        'view_invoice_id': None,
        'filter_status': '',
        'filter_client': '',
        'filter_date_from': None,
        'filter_date_to': None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# Initialize database
if not st.session_state.database_initialized:
    if init_database():
        st.session_state.database_initialized = True

# ============================================================================
# HEADER
# ============================================================================

st.markdown("""
    <div class="app-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="app-title">💰 INVOICE PRO</h1>
                <div class="app-subtitle">Professional invoicing for Caribbean businesses</div>
            </div>
            <div style="background: linear-gradient(135deg, #f1f5f9, #e2e8f0); padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; color: #0f172a;">
                {current_currency}
            </div>
        </div>
    </div>
""".format(current_currency=CURRENCIES[st.session_state.currency]['name']), unsafe_allow_html=True)

# ============================================================================
# SIDEBAR NAVIGATION
# ============================================================================

with st.sidebar:
    st.markdown("### 📍 Navigation")
    st.markdown("---")
    
    pages = {
        "📄 Create Invoice": "create",
        "📋 View Invoices": "view_invoices",
        "👥 Clients": "clients",
        "📊 Reports": "reports",
        "⚙️ Settings": "settings"
    }
    
    for page_name, page_id in pages.items():
        if st.button(page_name, use_container_width=True, 
                    type="primary" if st.session_state.current_page == page_id else "secondary",
                    key=f"nav_{page_id}"):
            st.session_state.current_page = page_id
            st.rerun()
    
    st.markdown("---")
    
    # Currency selector
    st.markdown("### 💱 Currency")
    currency_options = list(CURRENCIES.keys())
    
    try:
        current_idx = currency_options.index(st.session_state.currency)
    except ValueError:
        current_idx = 0
        st.session_state.currency = 'TTD'
    
    selected_currency = st.selectbox(
        "Select Currency",
        options=currency_options,
        format_func=lambda x: f"{CURRENCIES[x]['symbol']} {CURRENCIES[x]['name']}",
        index=current_idx,
        key="sidebar_currency",
        label_visibility="collapsed"
    )
    
    if selected_currency != st.session_state.currency:
        st.session_state.currency = selected_currency
        st.rerun()
    
    st.markdown("---")
    
    # Quick stats
    st.markdown("### 📊 Quick Stats")
    try:
        conn = sqlite3.connect('invoices.db')
        total_invoices = pd.read_sql_query("SELECT COUNT(*) as count FROM invoices", conn).iloc[0]['count']
        total_revenue = pd.read_sql_query("SELECT SUM(grand_total) as total FROM invoices WHERE status = 'Paid'", conn).iloc[0]['total'] or 0
        total_clients = pd.read_sql_query("SELECT COUNT(*) as count FROM clients", conn).iloc[0]['count']
        pending_amount = pd.read_sql_query("SELECT SUM(balance_due) as total FROM invoices WHERE status NOT IN ('Paid', 'Cancelled')", conn).iloc[0]['total'] or 0
        conn.close()
        
        st.metric("Invoices", f"{total_invoices}")
        st.metric("Total Revenue", format_amount(total_revenue, st.session_state.currency))
        st.metric("Clients", f"{total_clients}")
        st.metric("Pending", format_amount(pending_amount, st.session_state.currency))
    except:
        st.metric("Items", str(len(st.session_state.invoice_items)))
        # app_improved_pages.py - Page implementations for Invoice Pro
# This file contains all the page logic to be integrated with app_improved.py

# ============================================================================
# CREATE INVOICE PAGE
# ============================================================================

def render_create_invoice_page():
    """Render the create invoice page"""
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Invoice Details Card
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">📋 Invoice Details</div>', unsafe_allow_html=True)
            
            col_num, col_status = st.columns([2, 1])
            with col_num:
                invoice_number = st.text_input("Invoice Number *", value=st.session_state.invoice_number)
            with col_status:
                invoice_status = st.selectbox("Status", INVOICE_STATUSES, index=INVOICE_STATUSES.index(st.session_state.invoice_status))
            
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                invoice_date = st.date_input("Invoice Date", datetime.now())
            with date_col2:
                due_date = st.date_input("Due Date", datetime.now() + timedelta(days=30))
            
            po_number = st.text_input("PO Number (optional)")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Client Information Card with Quick Select
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">👤 Client Information</div>', unsafe_allow_html=True)
            
            # Quick select existing client
            clients_df = get_clients()
            if not clients_df.empty:
                st.markdown("##### Quick Select Client")
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
                else:
                    default_name = ''
                    default_email = ''
                    default_phone = ''
                    default_address = ''
            else:
                default_name = ''
                default_email = ''
                default_phone = ''
                default_address = ''
            
            st.markdown("##### Client Details")
            client_name = st.text_input("Client Name *", value=default_name)
            client_email = st.text_input("Email Address *", value=default_email)
            client_phone = st.text_input("Phone Number", value=default_phone)
            client_address = st.text_area("Address", value=default_address, height=80)
            
            # Auto-save client option
            auto_save_client = st.checkbox("Save client to database", value=True)
            
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
                    'bank_details': company_bank
                })
                st.success("✓ Company information updated")
        
        # Additional Notes
        with st.expander("📝 Additional Notes"):
            invoice_notes = st.text_area(
                "Notes (will appear on invoice)",
                value=st.session_state.invoice_notes,
                height=100,
                placeholder="Payment terms, special instructions, etc."
            )
            st.session_state.invoice_notes = invoice_notes
    
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
                                st.success("✓ Item updated")
                                st.rerun()
                            else:
                                st.warning("Description and price are required")
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
                                st.success("✓ Item added")
                                st.rerun()
                            else:
                                st.warning("Description and price are required")
                
                with col2:
                    if editing:
                        if st.form_submit_button("❌ Cancel Edit", use_container_width=True):
                            st.session_state.edit_index = -1
                            st.rerun()
            
            st.markdown("---")
            
            # Display Items
            if st.session_state.invoice_items:
                st.markdown("##### Current Items")
                
                # Create a more compact table display
                for idx, item in enumerate(st.session_state.invoice_items):
                    with st.container():
                        col_desc, col_actions = st.columns([4, 1])
                        
                        with col_desc:
                            st.markdown(f"**{idx + 1}. {item['description']}**")
                            st.caption(f"Qty: {item['quantity']} × {format_amount(item['unit_price'], st.session_state.currency)} | Tax: {item['tax_rate']}% | Disc: {item['discount']}%")
                            st.markdown(f"**Total: {format_amount(item['total'], st.session_state.currency)}**")
                        
                        with col_actions:
                            col_edit, col_del = st.columns(2)
                            with col_edit:
                                if st.button("✏️", key=f"edit_{idx}", help="Edit item"):
                                    st.session_state.edit_index = idx
                                    st.rerun()
                            with col_del:
                                if st.button("🗑️", key=f"del_{idx}", help="Delete item"):
                                    st.session_state.invoice_items.pop(idx)
                                    if st.session_state.edit_index == idx:
                                        st.session_state.edit_index = -1
                                    st.rerun()
                    
                    if idx < len(st.session_state.invoice_items) - 1:
                        st.divider()
                
                st.divider()
                
                # Calculate totals
                subtotal = sum(item['subtotal'] for item in st.session_state.invoice_items)
                total_discount = sum(item['discount_amount'] for item in st.session_state.invoice_items)
                total_tax = sum(item['tax_amount'] for item in st.session_state.invoice_items)
                grand_total = sum(item['total'] for item in st.session_state.invoice_items)
                
                # Summary
                st.markdown("### 📊 Invoice Summary")
                
                summary_data = {
                    "Item": ["Subtotal", "Discount", "Tax", "**GRAND TOTAL**"],
                    "Amount": [
                        format_amount(subtotal, st.session_state.currency),
                        f"-{format_amount(total_discount, st.session_state.currency)}",
                        format_amount(total_tax, st.session_state.currency),
                        f"**{format_amount(grand_total, st.session_state.currency)}**"
                    ]
                }
                
                st.table(pd.DataFrame(summary_data))
                
                # Actions
                col_reset, col_recalc = st.columns(2)
                with col_reset:
                    if st.button("🔄 Reset All Items", use_container_width=True):
                        st.session_state.invoice_items = []
                        st.session_state.edit_index = -1
                        st.rerun()
                with col_recalc:
                    if st.button("📊 Recalculate", use_container_width=True):
                        st.rerun()
            else:
                st.info("💡 No items added yet. Use the form above to add invoice items.")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Preview and Actions Section
    if st.session_state.invoice_items and client_name:
        st.markdown("---")
        st.markdown('<div class="section-header">👁️ Invoice Preview & Actions</div>', unsafe_allow_html=True)
        
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
                    hide_index=True
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
                        'notes': invoice_notes
                    }
                    
                    invoice_id = save_invoice_to_db(invoice_data, st.session_state.invoice_items)
                    
                    if invoice_id:
                        st.success(f"✓ Invoice saved successfully! (ID: {invoice_id})")
                        st.balloons()
                    else:
                        st.error("Failed to save invoice")
                except Exception as e:
                    st.error(f"Error saving invoice: {e}")
        
        with col2:
            if PDF_AVAILABLE:
                if st.button("📄 Download PDF", use_container_width=True):
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
            email_to = st.text_input("", value=client_email if client_email else "", key="email_input", placeholder="Email address")
        
        with col4:
            if st.button("📧 Send Email", use_container_width=True, disabled=not email_to):
                if email_to:
                    st.info("📧 Email functionality - configure SMTP settings in production")
                    # In production, integrate with email service
                else:
                    st.warning("⚠️ Enter an email address")
        
        with col5:
            if st.button("🔄 New Invoice", use_container_width=True):
                st.session_state.invoice_items = []
                st.session_state.edit_index = -1
                st.session_state.invoice_number = generate_invoice_number()
                st.session_state.invoice_notes = ''
                st.session_state.invoice_status = 'Draft'
                st.success("✓ Ready for new invoice")
                st.rerun()

# ============================================================================
# VIEW INVOICES PAGE
# ============================================================================

def render_view_invoices_page():
    """Render the view invoices page"""
    
    st.markdown('<div class="section-header">📋 Invoice Management</div>', unsafe_allow_html=True)
    
    # Filters
    with st.container():
        st.markdown('<div class="search-box">', unsafe_allow_html=True)
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
        
        st.markdown('</div>', unsafe_allow_html=True)
    
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
        st.markdown(f"### 📊 {len(invoices_df)} Invoice(s) Found")
        
        # Display invoices in cards
        for idx, invoice in invoices_df.iterrows():
            with st.container():
                st.markdown('<div class="business-card">', unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                
                with col1:
                    st.markdown(f"### {invoice['invoice_number']}")
                    st.markdown(f"**{invoice['client_name']}**")
                    st.caption(invoice['client_email'])
                
                with col2:
                    st.markdown(f"**Date:** {invoice['invoice_date']}")
                    st.markdown(f"**Due:** {invoice['due_date']}")
                    currency_symbol = get_currency_symbol(invoice['currency'])
                    st.markdown(f"**Amount:** {currency_symbol}{invoice['grand_total']:,.2f}")
                
                with col3:
                    st.markdown(get_status_badge_html(invoice['status']), unsafe_allow_html=True)
                    
                    # Balance due if not paid
                    if invoice['status'] not in ['Paid', 'Cancelled']:
                        balance = invoice.get('balance_due', invoice['grand_total'])
                        if balance > 0:
                            st.caption(f"Balance: {currency_symbol}{balance:,.2f}")
                
                with col4:
                    # Actions
                    if st.button("👁️ View", key=f"view_{invoice['id']}", use_container_width=True):
                        st.session_state.view_invoice_id = invoice['id']
                        st.rerun()
                    
                    if st.button("📄 PDF", key=f"pdf_{invoice['id']}", use_container_width=True):
                        # Generate PDF for this invoice
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
                                        label="📥 Download",
                                        data=pdf_buffer,
                                        file_name=f"invoice_{invoice_data['invoice_number']}.pdf",
                                        mime="application/pdf",
                                        key=f"download_pdf_{invoice['id']}"
                                    )
                    
                    # Status update
                    new_status = st.selectbox(
                        "Update Status",
                        options=INVOICE_STATUSES,
                        index=INVOICE_STATUSES.index(invoice['status']),
                        key=f"status_{invoice['id']}",
                        label_visibility="collapsed"
                    )
                    
                    if new_status != invoice['status']:
                        if update_invoice_status(invoice['id'], new_status):
                            st.success(f"✓ Status updated to {new_status}")
                            st.rerun()
                    
                    if st.button("🗑️ Delete", key=f"delete_{invoice['id']}", use_container_width=True):
                        if delete_invoice(invoice['id']):
                            st.success("✓ Invoice deleted")
                            st.rerun()
                        else:
                            st.error("Failed to delete invoice")
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Summary statistics
        st.markdown("---")
        st.markdown("### 📈 Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_amount = invoices_df['grand_total'].sum()
        paid_amount = invoices_df[invoices_df['status'] == 'Paid']['grand_total'].sum()
        pending_amount = invoices_df[invoices_df['status'].isin(['Draft', 'Sent'])]['grand_total'].sum()
        overdue_amount = invoices_df[invoices_df['status'] == 'Overdue']['grand_total'].sum()
        
        with col1:
            st.metric("Total Amount", format_amount(total_amount, st.session_state.currency))
        with col2:
            st.metric("Paid", format_amount(paid_amount, st.session_state.currency))
        with col3:
            st.metric("Pending", format_amount(pending_amount, st.session_state.currency))
        with col4:
            st.metric("Overdue", format_amount(overdue_amount, st.session_state.currency))
    
    else:
        st.info("📭 No invoices found. Create your first invoice!")

