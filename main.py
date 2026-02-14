# app.py (Fixed version - ALL issues resolved)
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
# PROFESSIONAL CSS - FIXED TEXT COLORS
# ============================================================================

st.markdown("""
    <style>
    /* Import professional fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global styles */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #f8fafc;
    }
    
    /* Force all text to be dark by default */
    .stApp, .stApp * {
        color: #1e293b !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #0f172a !important;
        font-weight: 600;
    }
    
    /* Header styling */
    .app-header {
        background: white;
        padding: 1.5rem 2rem;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 2rem;
    }
    
    .app-title {
        color: #0f172a !important;
        font-size: 1.8rem;
        font-weight: 600;
        margin: 0;
    }
    
    .app-subtitle {
        color: #475569 !important;
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }
    
    /* Card styling */
    .business-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
    }
    
    .business-card * {
        color: #1e293b !important;
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
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background-color: #ffffff;
        padding: 0.5rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-weight: 500;
        font-size: 1rem;
        background-color: #f1f5f9;
        border-radius: 8px;
        padding: 0.5rem 1.2rem;
        transition: all 0.2s ease;
        border: 1px solid transparent;
    }
    
    .stTabs [data-baseweb="tab"]:not([aria-selected="true"]) {
        color: #1e293b !important;
        background-color: #f1f5f9 !important;
    }
    
    .stTabs [aria-selected="true"] {
        color: #ffffff !important;
        background-color: #2563eb !important;
        font-weight: 600;
        border: 1px solid #1d4ed8;
    }
    
    .stTabs [aria-selected="true"] * {
        color: #ffffff !important;
    }
    
    /* BUTTON STYLING */
    .stButton > button {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
        border: none;
    }
    
    /* Secondary buttons */
    .stButton > button:not([kind="primary"]) {
        background: white;
        color: #2563eb !important;
        border: 2px solid #2563eb;
    }
    
    /* Primary buttons */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
        color: white !important;
        border: none;
        box-shadow: 0 2px 4px rgba(37,99,235,0.2);
    }
    
    .stButton > button[kind="primary"] * {
        color: white !important;
    }
    
    /* Danger/Remove buttons */
    .stButton > button[key*="remove"],
    .stButton > button[key*="del"] {
        background: white;
        color: #dc2626 !important;
        border: 2px solid #dc2626;
        padding: 0.25rem 0.5rem;
        font-size: 0.9rem;
    }
    
    /* Edit buttons */
    .stButton > button[key*="edit"] {
        background: white;
        color: #ea580c !important;
        border: 2px solid #ea580c;
        padding: 0.25rem 0.5rem;
        font-size: 0.9rem;
    }
    
    /* Success buttons */
    .stButton > button:has(span:contains("Save")),
    .stButton > button:has(span:contains("Add")),
    .stButton > button:has(span:contains("Update")),
    .stButton > button:has(span:contains("Recalculate")) {
        background: white;
        color: #059669 !important;
        border: 2px solid #059669;
    }
    
    /* PDF button */
    .stButton > button:has(span:contains("PDF")) {
        background: white;
        color: #7c3aed !important;
        border: 2px solid #7c3aed;
    }
    
    /* Email button */
    .stButton > button:has(span:contains("Email")) {
        background: white;
        color: #ea580c !important;
        border: 2px solid #ea580c;
    }
    
    /* New Invoice button */
    .stButton > button:has(span:contains("New")) {
        background: white;
        color: #6b7280 !important;
        border: 2px solid #6b7280;
    }
    
    /* Sidebar buttons */
    section[data-testid="stSidebar"] .stButton > button {
        background: white;
        color: #2563eb !important;
        border: 2px solid #2563eb;
        text-align: left;
        justify-content: flex-start;
        margin-bottom: 0.25rem;
    }
    
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
        color: white !important;
        border: none;
    }
    
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] * {
        color: white !important;
    }
    
    /* Logo styling */
    .logo-container {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 1rem;
        padding: 1rem;
        background: #f8fafc;
        border-radius: 8px;
        border: 1px dashed #cbd5e1;
    }
    
    .logo-preview {
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 1rem 0;
    }
    
    .invoice-logo {
        max-height: 60px;
        max-width: 150px;
        object-fit: contain;
    }
    
    /* Form labels */
    .stTextInput label,
    .stNumberInput label,
    .stDateInput label,
    .stSelectbox label,
    .stTextArea label,
    .stCheckbox label,
    .stRadio label,
    .stFileUploader label {
        color: #1e293b !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        margin-bottom: 0.25rem !important;
    }
    
    /* Input fields */
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stSelectbox select,
    .stTextArea textarea {
        color: #1e293b !important;
        background-color: white !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px;
        padding: 0.5rem !important;
    }
    
    /* Metric containers */
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
    
    /* DataFrame/Table styling */
    .stDataFrame {
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
        font-weight: 500;
        padding: 0.5rem 1rem;
        border: 1px solid #e2e8f0;
    }
    
    .streamlit-expanderContent {
        color: #1e293b !important;
        background-color: white;
        border: 1px solid #e2e8f0;
        border-top: none;
        border-radius: 0 0 6px 6px;
        padding: 1rem;
    }
    
    .streamlit-expanderContent * {
        color: #1e293b !important;
    }
    
    /* Alert messages */
    .stSuccess {
        background-color: #d1fae5;
        color: #065f46 !important;
        border: 1px solid #a7f3d0;
        border-radius: 6px;
    }
    
    .stSuccess * {
        color: #065f46 !important;
    }
    
    .stWarning {
        background-color: #fed7aa;
        color: #92400e !important;
        border: 1px solid #fdba74;
        border-radius: 6px;
    }
    
    .stWarning * {
        color: #92400e !important;
    }
    
    .stError {
        background-color: #fee2e2;
        color: #991b1b !important;
        border: 1px solid #fecaca;
        border-radius: 6px;
    }
    
    .stError * {
        color: #991b1b !important;
    }
    
    .stInfo {
        background-color: #dbeafe;
        color: #1e40af !important;
        border: 1px solid #bfdbfe;
        border-radius: 6px;
    }
    
    .stInfo * {
        color: #1e40af !important;
    }
    
    /* Invoice preview - FIXED BLACK BACKGROUND ISSUE */
    .invoice-preview {
        background: white !important;
        border-radius: 12px;
        padding: 2rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        margin-top: 1rem;
        margin-bottom: 2rem;
    }
    
    .invoice-preview * {
        color: #1e293b !important;
    }
    
    .invoice-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .invoice-header-left {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .invoice-title {
        font-size: 2rem;
        font-weight: 600;
        color: #0f172a !important;
        letter-spacing: -0.02em;
    }
    
    .company-details {
        text-align: right;
        color: #475569 !important;
        line-height: 1.5;
    }
    
    .company-details * {
        color: #475569 !important;
    }
    
    /* Preview table - FIXED TEXT COLOR */
    .preview-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
        background: white;
    }
    
    .preview-table th {
        background: #f8fafc;
        padding: 0.75rem;
        text-align: left;
        border-bottom: 2px solid #e2e8f0;
        font-weight: 600;
        color: #0f172a !important;
    }
    
    .preview-table td {
        padding: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
        color: #1e293b !important;
    }
    
    .preview-table .amount {
        text-align: right;
    }
    
    /* Totals table */
    .totals-table {
        width: 300px;
        margin-left: auto;
        background: white;
    }
    
    .totals-table td {
        padding: 0.25rem 0.5rem;
        color: #1e293b !important;
    }
    
    .totals-table .total-row {
        border-top: 2px solid #e2e8f0;
        font-weight: 600;
        font-size: 1.1rem;
    }
    
    /* Grand total highlight */
    .grand-total {
        background: #1e40af !important;
        padding: 1rem;
        border-radius: 8px;
        margin-top: 1rem;
    }
    
    .grand-total p {
        color: white !important;
    }
    
    .grand-total p:first-child {
        color: #e2e8f0 !important;
    }
    
    .grand-total p:last-child {
        color: white !important;
    }
    
    /* Items list - FIXED INVISIBLE TEXT */
    div[data-testid="column"] {
        color: #1e293b !important;
    }
    
    div[data-testid="column"] * {
        color: #1e293b !important;
    }
    
    /* Ensure all text in columns is visible */
    .stMarkdown, .stMarkdown * {
        color: #1e293b !important;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid #e2e8f0;
    }
    
    section[data-testid="stSidebar"] * {
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
    
    /* File uploader */
    .stFileUploader > div {
        border: 1px dashed #cbd5e1;
        border-radius: 6px;
        padding: 1rem;
        background: #f8fafc;
    }
    
    .stFileUploader > div * {
        color: #1e293b !important;
    }
    
    /* Download links */
    a {
        color: #2563eb !important;
        text-decoration: none;
        font-weight: 500;
    }
    
    a:hover {
        text-decoration: underline;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# FIXED PDF GENERATION FUNCTIONS - WITH LOGO AND PROPER ALIGNMENT
# ============================================================================

def generate_pdf_invoice(invoice_data):
    """Generate PDF invoice - FIXED ALIGNMENT AND LOGO"""
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
        
        right_style = ParagraphStyle(
            'RightAlign',
            parent=normal_style,
            alignment=TA_RIGHT
        )
        
        # Get company info
        company = invoice_data.get('company_info', {})
        
        # Create header with logo if available
        header_data = []
        
        # Check if logo bytes are available
        logo_bytes = company.get('logo_bytes')
        if logo_bytes:
            try:
                # Create temporary file for logo
                logo_buffer = io.BytesIO(logo_bytes)
                img = RLImage(logo_buffer, width=1.5*inch, height=0.75*inch)
                header_data.append([img, Paragraph("<b>INVOICE</b>", title_style)])
            except Exception as e:
                logger.error(f"Logo processing error: {e}")
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
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e293b')),
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
        
        # Items table - FIXED ALIGNMENT
        if 'items' in invoice_data and invoice_data['items']:
            # Prepare table data with proper headers
            table_data = [
                ['Description', 'Qty', 'Unit Price', 'Tax %', 'Disc %', 'Total']
            ]
            
            currency = invoice_data.get('currency', 'TTD')
            symbol = get_currency_symbol(currency)
            
            # Add items
            for item in invoice_data['items']:
                # Wrap description if too long
                desc = item.get('description', '')
                if len(desc) > 30:
                    desc = desc[:27] + '...'
                
                table_data.append([
                    desc,
                    str(item.get('quantity', '')),
                    f"{symbol}{item.get('unit_price', 0):,.2f}",
                    f"{item.get('tax_rate', 0)}%",
                    f"{item.get('discount', 0)}%",
                    f"{symbol}{item.get('total', 0):,.2f}"
                ])
            
            # Create table with proper column widths
            col_widths = [2.5*inch, 0.4*inch, 0.8*inch, 0.5*inch, 0.5*inch, 1*inch]
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            # Table styling
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
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#2563eb')),
                
                # First column (description) left-aligned
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
                ('TEXTCOLOR', (0, 0), (1, -2), colors.HexColor('#1e293b')),
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
        # Read the file
        bytes_data = uploaded_file.getvalue()
        
        # Convert to base64 for display
        encoded = base64.b64encode(bytes_data).decode()
        
        # Store in session state
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
        return f'<img src="data:{mime};base64,{st.session_state.company_info["logo_base64"]}" style="max-height: {max_height}; max-width: {max_width}; object-fit: contain;" class="invoice-logo">'
    return ""

def remove_logo():
    """Remove logo from session state"""
    if 'logo_bytes' in st.session_state.company_info:
        del st.session_state.company_info['logo_bytes']
    if 'logo_base64' in st.session_state.company_info:
        del st.session_state.company_info['logo_base64']
    if 'logo_filename' in st.session_state.company_info:
        del st.session_state.company_info['logo_filename']
    if 'logo_mime' in st.session_state.company_info:
        del st.session_state.company_info['logo_mime']

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
        'clients': [],
        'edit_index': -1  # For item editing
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
        st.metric("Invoices", str(len(st.session_state.invoice_items)), "0")
    with col2:
        st.metric("Items", str(len(st.session_state.invoice_items)), "0")

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
            
            # Logo upload
            st.markdown("##### Company Logo")
            logo_file = st.file_uploader(
                "Upload Logo (PNG, JPG, JPEG)",
                type=['png', 'jpg', 'jpeg'],
                help="Recommended size: 200x100 pixels",
                key="create_logo_upload"
            )
            
            if logo_file is not None:
                if save_logo(logo_file):
                    st.success(f"Logo uploaded: {logo_file.name}")
            
            # Show current logo if exists
            if st.session_state.company_info.get('logo_base64'):
                st.markdown('<div class="logo-preview">', unsafe_allow_html=True)
                st.markdown(f'<div class="logo-container">{get_logo_html("80px", "200px")}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
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
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">📦 Invoice Items</div>', unsafe_allow_html=True)
            
            # Item entry/Edit form
            with st.form("item_form", clear_on_submit=True):
                # Check if we're editing an existing item
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
                
                description = st.text_input("Description *", placeholder="Item or service description", value=default_desc)
                
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
                
                # Calculate live preview of item total
                if description and unit_price > 0:
                    subtotal = quantity * unit_price
                    discount_amount = subtotal * (discount / 100)
                    taxable_amount = subtotal - discount_amount
                    tax_amount = taxable_amount * (tax_rate / 100)
                    item_total = taxable_amount + tax_amount
                    st.info(f"📊 Item Total: {format_amount(item_total, st.session_state.currency)}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if editing:
                        if st.form_submit_button("✅ Update Item", use_container_width=True):
                            if description and unit_price > 0:
                                # Calculate amounts
                                subtotal = quantity * unit_price
                                discount_amount = subtotal * (discount / 100)
                                taxable_amount = subtotal - discount_amount
                                tax_amount = taxable_amount * (tax_rate / 100)
                                total = taxable_amount + tax_amount
                                
                                # Update the item
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
                                # Reset edit mode
                                st.session_state.edit_index = -1
                                st.rerun()
                    else:
                        if st.form_submit_button("➕ Add Item", use_container_width=True):
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
                
                with col2:
                    if editing:
                        if st.form_submit_button("❌ Cancel Edit", use_container_width=True):
                            st.session_state.edit_index = -1
                            st.rerun()
            
            # Display items with edit/delete options - FIXED VISIBILITY
            if st.session_state.invoice_items:
                st.markdown("##### Current Items")
                
                # Create headers
                col_desc, col_qty, col_price, col_tax, col_disc, col_total, col_actions = st.columns([3, 1, 1, 1, 1, 1, 1])
                with col_desc:
                    st.markdown("**Description**")
                with col_qty:
                    st.markdown("**Qty**")
                with col_price:
                    st.markdown("**Price**")
                with col_tax:
                    st.markdown("**Tax**")
                with col_disc:
                    st.markdown("**Disc**")
                with col_total:
                    st.markdown("**Total**")
                with col_actions:
                    st.markdown("**Actions**")
                
                # Display each item
                for idx, item in enumerate(st.session_state.invoice_items):
                    col_desc, col_qty, col_price, col_tax, col_disc, col_total, col_actions = st.columns([3, 1, 1, 1, 1, 1, 1])
                    
                    with col_desc:
                        st.write(item['description'])
                    with col_qty:
                        st.write(str(item['quantity']))
                    with col_price:
                        st.write(format_amount(item['unit_price'], st.session_state.currency))
                    with col_tax:
                        st.write(f"{item['tax_rate']}%")
                    with col_disc:
                        st.write(f"{item['discount']}%")
                    with col_total:
                        st.write(f"**{format_amount(item['total'], st.session_state.currency)}**")
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
                
                st.divider()
                
                # Calculate and display GRAND TOTAL
                subtotal = sum(item['subtotal'] for item in st.session_state.invoice_items)
                total_discount = sum(item['discount_amount'] for item in st.session_state.invoice_items)
                total_tax = sum(item['tax_amount'] for item in st.session_state.invoice_items)
                grand_total = sum(item['total'] for item in st.session_state.invoice_items)
                
                # Display totals
                st.markdown("### 📊 Invoice Summary")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"""
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0;">
                        <p style="margin: 0; color: #475569;">Subtotal:</p>
                        <p style="font-size: 1.2rem; font-weight: 600; margin: 0; color: #0f172a;">{format_amount(subtotal, st.session_state.currency)}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; margin-top: 0.5rem;">
                        <p style="margin: 0; color: #475569;">Discount:</p>
                        <p style="font-size: 1.2rem; font-weight: 600; margin: 0; color: #dc2626;">-{format_amount(total_discount, st.session_state.currency)}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0;">
                        <p style="margin: 0; color: #475569;">Tax:</p>
                        <p style="font-size: 1.2rem; font-weight: 600; margin: 0; color: #0f172a;">{format_amount(total_tax, st.session_state.currency)}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                    <div class="grand-total">
                        <p style="margin: 0; color: #e2e8f0; font-weight: 500;">GRAND TOTAL:</p>
                        <p style="font-size: 1.8rem; font-weight: 700; margin: 0; color: white;">{format_amount(grand_total, st.session_state.currency)}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Quick actions
                col_reset, col_update = st.columns(2)
                with col_reset:
                    if st.button("🔄 Reset All Items", use_container_width=True):
                        st.session_state.invoice_items = []
                        st.session_state.edit_index = -1
                        st.rerun()
                with col_update:
                    if st.button("📊 Recalculate All", use_container_width=True):
                        # Recalculate all items
                        updated_items = []
                        for item in st.session_state.invoice_items:
                            subtotal = item['quantity'] * item['unit_price']
                            discount_amount = subtotal * (item['discount'] / 100)
                            taxable_amount = subtotal - discount_amount
                            tax_amount = taxable_amount * (item['tax_rate'] / 100)
                            total = taxable_amount + tax_amount
                            
                            item['subtotal'] = subtotal
                            item['discount_amount'] = discount_amount
                            item['tax_amount'] = tax_amount
                            item['total'] = total
                            updated_items.append(item)
                        
                        st.session_state.invoice_items = updated_items
                        st.success("✅ All items recalculated!")
                        st.rerun()
            else:
                st.info("No items added yet. Use the form above to add items.")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Preview section - FIXED VISIBILITY
    if st.session_state.invoice_items and client_name:
        st.markdown('<div class="section-header">👁️ Invoice Preview</div>', unsafe_allow_html=True)
        
        preview_col1, preview_col2 = st.columns([2, 1])
        
        with preview_col1:
            # Get logo HTML
            logo_html = get_logo_html("60px", "150px")
            
            # Calculate totals for preview
            subtotal = sum(item['subtotal'] for item in st.session_state.invoice_items)
            total_discount = sum(item['discount_amount'] for item in st.session_state.invoice_items)
            total_tax = sum(item['tax_amount'] for item in st.session_state.invoice_items)
            grand_total = sum(item['total'] for item in st.session_state.invoice_items)
            
            # Build preview HTML
            preview_html = f'''
            <div class="invoice-preview">
                <div class="invoice-header">
                    <div class="invoice-header-left">
                        {logo_html if logo_html else ''}
                        <div>
                            <div class="invoice-title">INVOICE</div>
                            <div style="color: #475569; margin-top: 0.5rem;">{invoice_number}</div>
                        </div>
                    </div>
                    <div class="company-details">
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
                
                <table class="preview-table">
                    <thead>
                        <tr>
                            <th>Description</th>
                            <th class="amount">Qty</th>
                            <th class="amount">Price</th>
                            <th class="amount">Tax</th>
                            <th class="amount">Disc</th>
                            <th class="amount">Total</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            
            # Add items
            for item in st.session_state.invoice_items:
                preview_html += f'''
                        <tr>
                            <td>{item['description']}</td>
                            <td class="amount">{item['quantity']}</td>
                            <td class="amount">{format_amount(item['unit_price'], st.session_state.currency)}</td>
                            <td class="amount">{item['tax_rate']}%</td>
                            <td class="amount">{item['discount']}%</td>
                            <td class="amount">{format_amount(item['total'], st.session_state.currency)}</td>
                        </tr>
                '''
            
            # Add totals
            preview_html += f'''
                    </tbody>
                </table>
                
                <div style="margin-top: 2rem; display: flex; justify-content: flex-end;">
                    <table class="totals-table">
                        <tr>
                            <td>Subtotal:</td>
                            <td class="amount">{format_amount(subtotal, st.session_state.currency)}</td>
                        </tr>
                        <tr>
                            <td>Discount:</td>
                            <td class="amount">-{format_amount(total_discount, st.session_state.currency)}</td>
                        </tr>
                        <tr>
                            <td>Tax:</td>
                            <td class="amount">{format_amount(total_tax, st.session_state.currency)}</td>
                        </tr>
                        <tr class="total-row">
                            <td>Grand Total:</td>
                            <td class="amount">{format_amount(grand_total, st.session_state.currency)}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; color: #475569;">
                    <strong>Payment Details:</strong><br>
                    {st.session_state.company_info.get('bank_details', 'Bank details not provided')}
                </div>
            </div>
            '''
            
            # Display preview
            st.markdown(preview_html, unsafe_allow_html=True)
        
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
                
                # PDF Generation
                if PDF_AVAILABLE:
                    if st.button("📄 Download PDF", use_container_width=True):
                        with st.spinner("Generating PDF..."):
                            # Prepare invoice data for PDF
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
                                'company_info': st.session_state.company_info,  # This now includes logo_bytes
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
                                href = f'<a href="data:application/pdf;base64,{b64}" download="invoice_{invoice_number}.pdf" style="display: inline-block; padding: 0.5rem 1rem; background: #2563eb; color: white; text-decoration: none; border-radius: 6px; margin-top: 0.5rem; text-align: center;">📥 Download PDF</a>'
                                st.markdown(href, unsafe_allow_html=True)
                                st.success("PDF generated successfully!")
                            else:
                                st.error("Failed to generate PDF")
                else:
                    st.info("PDF generation requires: pip install reportlab")
                
                st.markdown("##### Email Invoice")
                email_to = st.text_input("Send to", value=client_email if client_email else "")
                if st.button("📧 Send Email", use_container_width=True):
                    if email_to:
                        st.info("Email functionality - configure SMTP settings")
                    else:
                        st.warning("Enter an email address")
                
                if st.button("🔄 New Invoice", use_container_width=True):
                    st.session_state.invoice_items = []
                    st.session_state.edit_index = -1
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
    
    tabs = st.tabs(["🏢 Company", "💰 Currency", "💾 Backup"])
    
    with tabs[0]:
        with st.container():
            st.markdown('<div class="business-card">', unsafe_allow_html=True)
            
            # LOGO SECTION
            st.markdown("##### Company Logo")
            st.markdown("Upload your company logo for invoices")
            
            logo_file = st.file_uploader(
                "Choose logo image (PNG, JPG, JPEG)",
                type=['png', 'jpg', 'jpeg'],
                key="settings_logo_upload"
            )
            
            if logo_file is not None:
                if save_logo(logo_file):
                    st.success(f"Logo uploaded: {logo_file.name}")
            
            # Show current logo
            if st.session_state.company_info.get('logo_base64'):
                st.markdown('<div class="logo-preview">', unsafe_allow_html=True)
                st.markdown(f'<div class="logo-container">{get_logo_html("80px", "200px")}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
                if st.button("🗑️ Remove Logo", use_container_width=True, key="remove_logo_settings"):
                    remove_logo()
                    st.rerun()
            
            st.markdown("---")
            
            # COMPANY INFORMATION FORM
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
                
                submitted = st.form_submit_button("💾 Save Company Settings", use_container_width=True)
                
                if submitted:
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
                        href = f'<a href="data:application/octet-stream;base64,{b64}" download="invoice_backup_{timestamp}.db">Click to Download</a>'
                        st.markdown(href, unsafe_allow_html=True)
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
        <p>© 2026 TT Invoice Pro - Professional Invoicing for Trinidad & Tobago</p>
        <p style="font-size: 0.75rem; margin-top: 0.5rem;">Version 2.0 | All amounts in TTD unless specified</p>
    </div>
""", unsafe_allow_html=True)
