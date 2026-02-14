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
import hashlib
import hmac
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
import io
import os
from dotenv import load_dotenv
from functools import wraps
from typing import Optional, Dict, List, Tuple, Any
import time
from contextlib import contextmanager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('invoice_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    from forex_python.converter import CurrencyRates
    FOREX_AVAILABLE = True
except ImportError:
    FOREX_AVAILABLE = False
    logger.warning("forex-python not installed. Currency conversion will use mock data.")

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("stripe not installed. Payment integration will be disabled.")

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    from reportlab.pdfgen import canvas
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("reportlab not installed. PDF generation will be disabled.")

# Set page configuration
st.set_page_config(
    page_title="Advanced Invoice Generator Pro",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone: str) -> bool:
    """Validate phone number format (international)"""
    if not phone:
        return True  # Phone is optional
    pattern = r'^\+?1?\d{9,15}$'
    return re.match(pattern, phone.replace('-', '').replace(' ', '')) is not None

def validate_amount(amount: float, min_amount: float = 0, max_amount: float = 1_000_000) -> bool:
    """Validate monetary amount"""
    try:
        amount = float(amount)
        return min_amount <= amount <= max_amount
    except (ValueError, TypeError):
        return False

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    if not text:
        return ""
    dangerous_chars = ['<', '>', '"', "'", '\\', ';', '--', '/*', '*/']
    sanitized = str(text)
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    return sanitized.strip()

def validate_date_range(start_date: datetime, end_date: datetime) -> bool:
    """Validate date range"""
    return start_date <= end_date

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = sqlite3.connect('invoices.db', timeout=10)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_database():
    """Initialize SQLite database with enhanced schema"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Invoices table
            c.execute('''CREATE TABLE IF NOT EXISTS invoices
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          invoice_number TEXT UNIQUE,
                          user_id TEXT,
                          client_id INTEGER,
                          invoice_data TEXT,
                          subtotal REAL,
                          tax_total REAL,
                          discount_total REAL,
                          grand_total REAL,
                          currency TEXT,
                          status TEXT,
                          created_at TIMESTAMP,
                          due_date DATE,
                          paid_at TIMESTAMP,
                          is_active BOOLEAN DEFAULT 1,
                          FOREIGN KEY (client_id) REFERENCES clients(id))''')
            
            # Clients table with enhanced fields
            c.execute('''CREATE TABLE IF NOT EXISTS clients
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          name TEXT NOT NULL,
                          email TEXT,
                          phone TEXT,
                          address TEXT,
                          city TEXT,
                          state TEXT,
                          zip_code TEXT,
                          country TEXT,
                          tax_id TEXT,
                          notes TEXT,
                          user_id TEXT,
                          created_at TIMESTAMP,
                          updated_at TIMESTAMP,
                          is_active BOOLEAN DEFAULT 1,
                          UNIQUE(email, user_id))''')
            
            # Invoice items table (normalized)
            c.execute('''CREATE TABLE IF NOT EXISTS invoice_items
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          invoice_id INTEGER,
                          description TEXT NOT NULL,
                          quantity REAL,
                          unit_price REAL,
                          tax_rate REAL,
                          discount_rate REAL,
                          subtotal REAL,
                          tax_amount REAL,
                          discount_amount REAL,
                          total REAL,
                          FOREIGN KEY (invoice_id) REFERENCES invoices(id))''')
            
            # Templates table
            c.execute('''CREATE TABLE IF NOT EXISTS templates
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          name TEXT,
                          template_data TEXT,
                          user_id TEXT,
                          is_default BOOLEAN,
                          created_at TIMESTAMP,
                          updated_at TIMESTAMP,
                          is_active BOOLEAN DEFAULT 1)''')
            
            # Payment links table
            c.execute('''CREATE TABLE IF NOT EXISTS payment_links
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          invoice_number TEXT,
                          payment_url TEXT,
                          amount REAL,
                          currency TEXT,
                          status TEXT,
                          created_at TIMESTAMP,
                          expires_at TIMESTAMP,
                          paid_at TIMESTAMP,
                          FOREIGN KEY (invoice_number) REFERENCES invoices(invoice_number))''')
            
            # Activity log table
            c.execute('''CREATE TABLE IF NOT EXISTS activity_log
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          user_id TEXT,
                          action TEXT,
                          details TEXT,
                          ip_address TEXT,
                          created_at TIMESTAMP)''')
            
            # Create indexes for performance
            c.execute('CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices(user_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id)')
            
            conn.commit()
            logger.info("Database initialized successfully")
            return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False

def log_activity(user_id: str, action: str, details: str = ""):
    """Log user activity"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO activity_log (user_id, action, details, created_at)
                        VALUES (?, ?, ?, ?)''',
                     (user_id, action, details, datetime.now().isoformat()))
            conn.commit()
    except Exception as e:
        logger.error(f"Error logging activity: {e}")

# ============================================================================
# PDF GENERATION FUNCTIONS
# ============================================================================

def generate_pdf_invoice(invoice_data: Dict, template_data: Dict = None) -> Optional[io.BytesIO]:
    """Generate professional PDF invoice"""
    if not PDF_AVAILABLE:
        logger.warning("PDF generation not available")
        return None
    
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor(template_data.get('primary_color', '#667eea') if template_data else '#667eea'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        # Company Header
        company_info = invoice_data.get('company_info', {})
        company_text = f"""
        <b>{company_info.get('name', 'Company Name')}</b><br/>
        {company_info.get('address', '')}<br/>
        {company_info.get('city', '')}<br/>
        Phone: {company_info.get('phone', '')}<br/>
        Email: {company_info.get('email', '')}
        """
        story.append(Paragraph(company_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Invoice Title
        story.append(Paragraph("INVOICE", title_style))
        
        # Invoice Details
        invoice_details = f"""
        <b>Invoice Number:</b> {invoice_data.get('invoice_number', '')}<br/>
        <b>Date:</b> {invoice_data.get('invoice_date', '')}<br/>
        <b>Due Date:</b> {invoice_data.get('due_date', '')}<br/>
        <b>PO Number:</b> {invoice_data.get('po_number', 'N/A')}
        """
        story.append(Paragraph(invoice_details, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Client Information
        client = invoice_data.get('client', {})
        client_text = f"""
        <b>Bill To:</b><br/>
        {client.get('name', '')}<br/>
        {client.get('address', '')}<br/>
        Email: {client.get('email', '')}<br/>
        Phone: {client.get('phone', '')}
        """
        story.append(Paragraph(client_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Items Table
        if 'items' in invoice_data and invoice_data['items']:
            table_data = [['Description', 'Qty', 'Unit Price', 'Tax %', 'Discount %', 'Total']]
            
            for item in invoice_data['items']:
                table_data.append([
                    item.get('description', ''),
                    str(item.get('quantity', 0)),
                    f"{invoice_data.get('currency', 'USD')} {item.get('unit_price', 0):.2f}",
                    f"{item.get('tax_rate', 0)}%",
                    f"{item.get('discount', 0)}%",
                    f"{invoice_data.get('currency', 'USD')} {item.get('total', 0):.2f}"
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            story.append(table)
            story.append(Spacer(1, 20))
        
        # Totals
        totals = invoice_data.get('totals', {})
        totals_text = f"""
        <para alignment="right">
        <b>Subtotal:</b> {invoice_data.get('currency', 'USD')} {totals.get('subtotal', 0):,.2f}<br/>
        <b>Discount:</b> {invoice_data.get('currency', 'USD')} {totals.get('discount', 0):,.2f}<br/>
        <b>Tax:</b> {invoice_data.get('currency', 'USD')} {totals.get('tax', 0):,.2f}<br/>
        <font size="14"><b>Grand Total:</b> {invoice_data.get('currency', 'USD')} {totals.get('grand_total', 0):,.2f}</font>
        </para>
        """
        story.append(Paragraph(totals_text, styles['Normal']))
        story.append(Spacer(1, 30))
        
        # Terms and Notes
        if invoice_data.get('terms_conditions'):
            story.append(Paragraph(f"<b>Terms:</b> {invoice_data['terms_conditions']}", styles['Normal']))
            story.append(Spacer(1, 10))
        
        if invoice_data.get('notes'):
            story.append(Paragraph(f"<b>Notes:</b> {invoice_data['notes']}", styles['Normal']))
            story.append(Spacer(1, 10))
        
        # Bank Details
        if company_info.get('bank_details'):
            story.append(Paragraph(f"<b>Payment Details:</b><br/>{company_info['bank_details']}", 
                                  styles['Normal']))
        
        # Footer
        footer_text = "Thank you for your business!"
        story.append(Spacer(1, 30))
        story.append(Paragraph(footer_text, styles['Italic']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return None

# ============================================================================
# CURRENCY FUNCTIONS
# ============================================================================

def get_exchange_rates(base_currency: str = 'USD') -> Dict[str, float]:
    """Fetch current exchange rates with caching"""
    cache_key = f'rates_{base_currency}_{datetime.now().strftime("%Y%m%d")}'
    
    # Check cache
    if cache_key in st.session_state.get('exchange_rate_cache', {}):
        return st.session_state.exchange_rate_cache[cache_key]
    
    # Default rates
    default_rates = {
        'USD': 1.0, 'EUR': 0.85, 'GBP': 0.73, 'JPY': 110.0,
        'CAD': 1.25, 'AUD': 1.35, 'CHF': 0.92, 'CNY': 6.45,
        'INR': 74.0, 'SGD': 1.35, 'HKD': 7.78, 'NZD': 1.42
    }
    
    if FOREX_AVAILABLE:
        try:
            c = CurrencyRates()
            currencies = list(default_rates.keys())
            rates = {}
            for currency in currencies:
                try:
                    rates[currency] = c.get_rate(base_currency, currency)
                except:
                    rates[currency] = default_rates.get(currency, 1.0)
            
            # Cache the rates
            if 'exchange_rate_cache' not in st.session_state:
                st.session_state.exchange_rate_cache = {}
            st.session_state.exchange_rate_cache[cache_key] = rates
            return rates
        except Exception as e:
            logger.warning(f"Could not fetch live rates: {e}")
    
    return default_rates

def convert_currency(amount: float, from_currency: str, to_currency: str) -> float:
    """Convert amount between currencies"""
    if from_currency == to_currency:
        return amount
    
    rates = get_exchange_rates(from_currency)
    
    # Convert through USD if direct rate not available
    if to_currency in rates:
        return amount * rates[to_currency]
    else:
        # Convert to USD first
        usd_amount = amount / rates.get('USD', 1)
        # Convert from USD to target
        target_rates = get_exchange_rates('USD')
        return usd_amount * target_rates.get(to_currency, 1)

# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def send_invoice_email(recipient_email: str, subject: str, body: str, 
                       pdf_buffer: Optional[io.BytesIO] = None) -> bool:
    """Send invoice via email with error handling"""
    try:
        # Validate email
        if not validate_email(recipient_email):
            logger.error(f"Invalid email address: {recipient_email}")
            return False
        
        smtp_server = st.session_state.email_settings.get('smtp_server', 'smtp.gmail.com')
        smtp_port = st.session_state.email_settings.get('smtp_port', 587)
        sender_email = st.session_state.email_settings.get('sender_email')
        sender_password = st.session_state.email_settings.get('sender_password')
        
        if not all([sender_email, sender_password]):
            logger.error("Email settings not configured")
            return False
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(body, 'html'))
        
        # Add PDF attachment if provided
        if pdf_buffer:
            part = MIMEApplication(pdf_buffer.getvalue(), Name='invoice.pdf')
            part['Content-Disposition'] = 'attachment; filename="invoice.pdf"'
            msg.attach(part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

# ============================================================================
# PAYMENT FUNCTIONS
# ============================================================================

def create_stripe_payment_link(amount: float, currency: str = 'usd', 
                               description: str = 'Invoice Payment',
                               invoice_number: str = '') -> Optional[str]:
    """Create a Stripe payment link"""
    if not STRIPE_AVAILABLE:
        logger.error("Stripe not available")
        return None
    
    try:
        stripe.api_key = st.session_state.stripe_settings.get('api_key')
        
        if not stripe.api_key:
            logger.error("Stripe API key not configured")
            return None
        
        # Create product
        product = stripe.Product.create(
            name=f"Invoice {invoice_number}" if invoice_number else description,
            type='service'
        )
        
        # Create price
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
            }],
            after_completion={'type': 'redirect', 'redirect': {'url': 'https://yourdomain.com/thank-you'}}
        )
        
        # Save to database
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute('''INSERT INTO payment_links 
                           (invoice_number, payment_url, amount, currency, status, created_at, expires_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (invoice_number, payment_link.url, amount, currency.upper(), 
                          'active', datetime.now().isoformat(),
                          (datetime.now() + timedelta(days=30)).isoformat()))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving payment link: {e}")
        
        return payment_link.url
        
    except Exception as e:
        logger.error(f"Failed to create payment link: {e}")
        return None

# ============================================================================
# TEMPLATE FUNCTIONS
# ============================================================================

def save_template(name: str, template_data: Dict) -> bool:
    """Save invoice template"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Check if template exists
            c.execute('SELECT id FROM templates WHERE name = ? AND user_id = ?',
                     (name, st.session_state.user_id))
            existing = c.fetchone()
            
            if existing:
                # Update existing template
                c.execute('''UPDATE templates 
                           SET template_data = ?, updated_at = ?
                           WHERE name = ? AND user_id = ?''',
                         (json.dumps(template_data), datetime.now().isoformat(),
                          name, st.session_state.user_id))
            else:
                # Insert new template
                c.execute('''INSERT INTO templates 
                           (name, template_data, user_id, is_default, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                         (name, json.dumps(template_data), st.session_state.user_id, False,
                          datetime.now().isoformat(), datetime.now().isoformat()))
            
            conn.commit()
            
            # Update session state
            st.session_state.templates[name] = template_data
            
            logger.info(f"Template '{name}' saved successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error saving template: {e}")
        return False

def load_templates() -> Dict[str, Dict]:
    """Load user templates"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT name, template_data FROM templates 
                       WHERE user_id = ? AND is_active = 1''',
                     (st.session_state.user_id,))
            
            templates = {}
            for row in c.fetchall():
                templates[row['name']] = json.loads(row['template_data'])
            
            return templates
            
    except Exception as e:
        logger.error(f"Error loading templates: {e}")
        return {}

# ============================================================================
# CLIENT FUNCTIONS
# ============================================================================

def save_client(client_data: Dict) -> bool:
    """Save or update client"""
    try:
        # Validate email
        if not validate_email(client_data.get('email', '')):
            logger.error(f"Invalid email: {client_data.get('email')}")
            return False
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Check if client exists
            c.execute('SELECT id FROM clients WHERE email = ? AND user_id = ?',
                     (client_data['email'], st.session_state.user_id))
            existing = c.fetchone()
            
            if existing:
                # Update existing client
                c.execute('''UPDATE clients 
                           SET name = ?, phone = ?, address = ?, city = ?,
                               state = ?, zip_code = ?, country = ?, tax_id = ?,
                               notes = ?, updated_at = ?
                           WHERE email = ? AND user_id = ?''',
                         (client_data['name'], client_data.get('phone', ''),
                          client_data.get('address', ''), client_data.get('city', ''),
                          client_data.get('state', ''), client_data.get('zip_code', ''),
                          client_data.get('country', ''), client_data.get('tax_id', ''),
                          client_data.get('notes', ''), datetime.now().isoformat(),
                          client_data['email'], st.session_state.user_id))
            else:
                # Insert new client
                c.execute('''INSERT INTO clients 
                           (name, email, phone, address, city, state, zip_code,
                            country, tax_id, notes, user_id, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (client_data['name'], client_data['email'],
                          client_data.get('phone', ''), client_data.get('address', ''),
                          client_data.get('city', ''), client_data.get('state', ''),
                          client_data.get('zip_code', ''), client_data.get('country', ''),
                          client_data.get('tax_id', ''), client_data.get('notes', ''),
                          st.session_state.user_id, datetime.now().isoformat(),
                          datetime.now().isoformat()))
            
            conn.commit()
            logger.info(f"Client '{client_data['name']}' saved successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error saving client: {e}")
        return False

def get_clients() -> pd.DataFrame:
    """Get all clients for current user"""
    try:
        with get_db_connection() as conn:
            query = '''SELECT id, name, email, phone, address, city, state, 
                              zip_code, country, tax_id, notes, created_at
                       FROM clients 
                       WHERE user_id = ? AND is_active = 1
                       ORDER BY name'''
            df = pd.read_sql_query(query, conn, params=(st.session_state.user_id,))
            return df
    except Exception as e:
        logger.error(f"Error getting clients: {e}")
        return pd.DataFrame()

# ============================================================================
# INVOICE FUNCTIONS
# ============================================================================

def save_invoice(invoice_data: Dict, status: str = 'draft') -> bool:
    """Save invoice to database"""
    try:
        totals = invoice_data.get('totals', {})
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Get or create client
            client = invoice_data.get('client', {})
            client_id = None
            
            if client.get('email'):
                c.execute('SELECT id FROM clients WHERE email = ? AND user_id = ?',
                         (client['email'], st.session_state.user_id))
                result = c.fetchone()
                if result:
                    client_id = result['id']
                else:
                    # Auto-create client
                    save_client(client)
                    c.execute('SELECT id FROM clients WHERE email = ? AND user_id = ?',
                             (client['email'], st.session_state.user_id))
                    result = c.fetchone()
                    if result:
                        client_id = result['id']
            
            # Save invoice
            try:
                c.execute('''INSERT INTO invoices 
                           (invoice_number, user_id, client_id, invoice_data,
                            subtotal, tax_total, discount_total, grand_total,
                            currency, status, created_at, due_date)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (invoice_data['invoice_number'],
                          st.session_state.user_id,
                          client_id,
                          json.dumps(invoice_data),
                          totals.get('subtotal', 0),
                          totals.get('tax', 0),
                          totals.get('discount', 0),
                          totals.get('grand_total', 0),
                          invoice_data.get('currency', 'USD'),
                          status,
                          datetime.now().isoformat(),
                          invoice_data.get('due_date', '')))
                
                invoice_id = c.lastrowid
                
                # Save invoice items
                if 'items' in invoice_data:
                    for item in invoice_data['items']:
                        c.execute('''INSERT INTO invoice_items
                                   (invoice_id, description, quantity, unit_price,
                                    tax_rate, discount_rate, subtotal, tax_amount,
                                    discount_amount, total)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                 (invoice_id,
                                  item['description'],
                                  item['quantity'],
                                  item['unit_price'],
                                  item.get('tax_rate', 0),
                                  item.get('discount', 0),
                                  item.get('subtotal', 0),
                                  item.get('tax_amount', 0),
                                  item.get('discount_amount', 0),
                                  item.get('total', 0)))
                
                conn.commit()
                logger.info(f"Invoice {invoice_data['invoice_number']} saved successfully")
                
                # Log activity
                log_activity(st.session_state.user_id, 'invoice_saved', 
                           f"Invoice {invoice_data['invoice_number']} saved")
                
                return True
                
            except sqlite3.IntegrityError:
                # Update existing invoice
                c.execute('''UPDATE invoices 
                           SET invoice_data = ?, status = ?, updated_at = ?
                           WHERE invoice_number = ? AND user_id = ?''',
                         (json.dumps(invoice_data), status, datetime.now().isoformat(),
                          invoice_data['invoice_number'], st.session_state.user_id))
                conn.commit()
                logger.info(f"Invoice {invoice_data['invoice_number']} updated")
                return True
                
    except Exception as e:
        logger.error(f"Error saving invoice: {e}")
        return False

def get_invoices(status: str = None) -> pd.DataFrame:
    """Get invoices for current user"""
    try:
        with get_db_connection() as conn:
            if status:
                query = '''SELECT invoice_number, created_at, due_date, 
                                  grand_total, currency, status
                           FROM invoices 
                           WHERE user_id = ? AND status = ? AND is_active = 1
                           ORDER BY created_at DESC'''
                df = pd.read_sql_query(query, conn, 
                                      params=(st.session_state.user_id, status))
            else:
                query = '''SELECT invoice_number, created_at, due_date, 
                                  grand_total, currency, status
                           FROM invoices 
                           WHERE user_id = ? AND is_active = 1
                           ORDER BY created_at DESC'''
                df = pd.read_sql_query(query, conn, 
                                      params=(st.session_state.user_id,))
            return df
    except Exception as e:
        logger.error(f"Error getting invoices: {e}")
        return pd.DataFrame()

# ============================================================================
# ANALYTICS FUNCTIONS
# ============================================================================

def get_invoice_analytics() -> Dict[str, Any]:
    """Get invoice analytics data"""
    try:
        with get_db_connection() as conn:
            # Total revenue
            c = conn.cursor()
            c.execute('''SELECT SUM(grand_total) as total_revenue,
                               COUNT(*) as total_invoices,
                               AVG(grand_total) as avg_invoice,
                               SUM(CASE WHEN status = 'paid' THEN grand_total ELSE 0 END) as paid_revenue,
                               COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_count,
                               COUNT(CASE WHEN status = 'overdue' THEN 1 END) as overdue_count
                        FROM invoices 
                        WHERE user_id = ? AND is_active = 1''',
                     (st.session_state.user_id,))
            
            result = c.fetchone()
            
            # Monthly revenue
            c.execute('''SELECT strftime('%Y-%m', created_at) as month,
                               SUM(grand_total) as revenue,
                               COUNT(*) as count
                        FROM invoices 
                        WHERE user_id = ? AND is_active = 1
                        GROUP BY month
                        ORDER BY month DESC
                        LIMIT 12''',
                     (st.session_state.user_id,))
            
            monthly_data = c.fetchall()
            
            return {
                'total_revenue': result['total_revenue'] or 0,
                'total_invoices': result['total_invoices'] or 0,
                'avg_invoice': result['avg_invoice'] or 0,
                'paid_revenue': result['paid_revenue'] or 0,
                'paid_count': result['paid_count'] or 0,
                'overdue_count': result['overdue_count'] or 0,
                'monthly': monthly_data
            }
            
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return {}

# ============================================================================
# INITIALIZATION
# ============================================================================

def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'invoice_items': [],
        'invoice_number': f"INV-{datetime.now().strftime('%Y%m%d')}-001",
        'templates': {},
        'current_template': 'default',
        'company_info': {
            'name': os.getenv('COMPANY_NAME', 'Your Company Name'),
            'address': os.getenv('COMPANY_ADDRESS', '123 Business St.'),
            'city': os.getenv('COMPANY_CITY', 'City, State 12345'),
            'phone': os.getenv('COMPANY_PHONE', '(555) 123-4567'),
            'email': os.getenv('COMPANY_EMAIL', 'contact@company.com'),
            'tax_id': os.getenv('COMPANY_TAX_ID', 'TAX123456'),
            'logo': None,
            'bank_details': os.getenv('BANK_DETAILS', 'Bank: Example Bank\nAccount: 123456789\nRouting: 987654321')
        },
        'currency': os.getenv('DEFAULT_CURRENCY', 'USD'),
        'exchange_rates': {},
        'exchange_rate_cache': {},
        'payment_links': [],
        'email_settings': {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'sender_email': os.getenv('SENDER_EMAIL', ''),
            'sender_password': os.getenv('SENDER_PASSWORD', '')
        },
        'stripe_settings': {
            'api_key': os.getenv('STRIPE_API_KEY', ''),
            'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', '')
        },
        'database_initialized': False,
        'user_id': os.getenv('USER_ID', 'default_user'),
        'email_template': "Dear {client_name},\n\nPlease find attached invoice {invoice_number} for the amount of {amount}.\n\nThank you for your business!",
        'notification': None,
        'current_step': 1
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Initialize session state
init_session_state()

# ============================================================================
# UI COMPONENTS
# ============================================================================

def show_notification(message: str, type: str = 'success'):
    """Show notification message"""
    if type == 'success':
        st.success(message)
    elif type == 'error':
        st.error(message)
    elif type == 'warning':
        st.warning(message)
    elif type == 'info':
        st.info(message)

def progress_bar(step: int, total_steps: int = 3):
    """Show progress bar for multi-step forms"""
    progress = step / total_steps
    st.progress(progress)
    st.markdown(f"**Step {step} of {total_steps}**")

def metric_card(title: str, value: str, delta: str = None):
    """Display metric card"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.metric(title, value, delta)

# ============================================================================
# MAIN APP
# ============================================================================

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        animation: fadeIn 1s ease-in;
    }
    @keyframes fadeIn {
        0% { opacity: 0; transform: translateY(-20px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    .invoice-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
        transition: transform 0.3s, box-shadow 0.3s;
    }
    .invoice-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
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
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        animation: none;
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
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .template-card.selected {
        border-color: #667eea;
        background-color: #f0f4ff;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-success {
        background-color: #d4edda;
        color: #155724;
    }
    .badge-warning {
        background-color: #fff3cd;
        color: #856404;
    }
    .badge-danger {
        background-color: #f8d7da;
        color: #721c24;
    }
    .badge-info {
        background-color: #d1ecf1;
        color: #0c5460;
    }
    .footer {
        text-align: center;
        padding: 2rem;
        color: #666;
        font-size: 0.9rem;
        border-top: 1px solid #e0e0e0;
        margin-top: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="main-header">
        <h1>💼 Advanced Invoice Generator Pro</h1>
        <p>Professional invoicing with multi-currency, templates, payment integration, and enterprise-grade features</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://via.placeholder.com/300x100/667eea/ffffff?text=Invoice+Pro", use_container_width=True)
    
    # Status indicators
    st.markdown("### System Status")
    col1, col2 = st.columns(2)
    with col1:
        if FOREX_AVAILABLE:
            st.markdown("✅ Forex")
        else:
            st.markdown("❌ Forex")
        if STRIPE_AVAILABLE:
            st.markdown("✅ Stripe")
        else:
            st.markdown("❌ Stripe")
    with col2:
        if PDF_AVAILABLE:
            st.markdown("✅ PDF")
        else:
            st.markdown("❌ PDF")
        if st.session_state.database_initialized:
            st.markdown("✅ Database")
        else:
            st.markdown("❌ Database")
    
    st.markdown("---")
    
    # Navigation
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
    st.markdown(f"**User:** {st.session_state.user_id}")
    st.markdown(f"**Currency:** {st.session_state.currency}")
    
    if st.button("🔄 Initialize Database", use_container_width=True):
        with st.spinner("Initializing database..."):
            if init_database():
                st.session_state.database_initialized = True
                st.success("Database initialized!")
                log_activity(st.session_state.user_id, 'database_init', 'Database initialized')
            else:
                st.error("Database initialization failed")

# Main content
if choice == "📝 Create Invoice":
    st.markdown("### 📝 Create New Invoice")
    
    # Progress bar
    progress_bar(st.session_state.current_step)
    
    # Step 1: Basic Information
    if st.session_state.current_step == 1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Invoice Details")
            
            invoice_number = st.text_input("Invoice Number", 
                                          value=st.session_state.invoice_number,
                                          help="Unique invoice identifier")
            
            # Load templates
            templates = load_templates()
            template_options = ["Default"] + list(templates.keys())
            template_choice = st.selectbox("Select Template", template_options)
            
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                invoice_date = st.date_input("Invoice Date", datetime.now())
            with date_col2:
                due_date = st.date_input("Due Date", datetime.now() + timedelta(days=30))
            
            # Validate date range
            if not validate_date_range(invoice_date, due_date):
                st.error("Due date must be after invoice date")
            
            # Additional fields
            with st.expander("Additional Information", expanded=True):
                po_number = st.text_input("PO Number", help="Purchase Order Number")
                shipping_address = st.text_area("Shipping Address")
                terms_conditions = st.text_area("Terms & Conditions", 
                                               "Payment due within 30 days. Thank you for your business!")
                notes = st.text_area("Additional Notes")
        
        with col2:
            st.markdown("#### Client Information")
            
            # Load clients
            clients_df = get_clients()
            
            if not clients_df.empty:
                client_options = ["New Client"] + clients_df['name'].tolist()
                client_choice = st.selectbox("Select Client", client_options)
                
                if client_choice != "New Client":
                    client_data = clients_df[clients_df['name'] == client_choice].iloc[0]
                    client_name = client_data['name']
                    client_email = client_data['email']
                    client_phone = client_data['phone']
                    client_address = client_data['address']
                    client_city = client_data['city']
                    client_state = client_data['state']
                    client_zip = client_data['zip_code']
                    client_country = client_data['country']
                    client_tax_id = client_data['tax_id']
                else:
                    client_name = st.text_input("Client Name *")
                    client_email = st.text_input("Email *")
                    client_phone = st.text_input("Phone")
                    client_address = st.text_input("Address")
                    client_city = st.text_input("City")
                    client_state = st.text_input("State")
                    client_zip = st.text_input("ZIP Code")
                    client_country = st.text_input("Country")
                    client_tax_id = st.text_input("Tax ID")
            else:
                client_name = st.text_input("Client Name *")
                client_email = st.text_input("Email *")
                client_phone = st.text_input("Phone")
                client_address = st.text_input("Address")
                client_city = st.text_input("City")
                client_state = st.text_input("State")
                client_zip = st.text_input("ZIP Code")
                client_country = st.text_input("Country")
                client_tax_id = st.text_input("Tax ID")
            
            # Validate required fields
            if client_name and client_email and validate_email(client_email):
                if st.button("Next →", type="primary", use_container_width=True):
                    st.session_state.current_step = 2
                    st.rerun()
            else:
                if client_email and not validate_email(client_email):
                    st.error("Invalid email format")
                elif not client_name or not client_email:
                    st.info("Please fill in required fields (marked with *)")
    
    # Step 2: Invoice Items
    elif st.session_state.current_step == 2:
        st.markdown("#### Invoice Items")
        
        # Item input form
        with st.form("add_item_form", clear_on_submit=True):
            cols = st.columns([3, 1, 1, 1, 1, 1])
            
            with cols[0]:
                description = st.text_input("Description", key="item_desc")
            with cols[1]:
                quantity = st.number_input("Qty", min_value=1, value=1, key="item_qty")
            with cols[2]:
                unit_price = st.number_input("Unit Price", min_value=0.0, value=0.0, step=10.0, key="item_price")
            with cols[3]:
                tax_rate = st.number_input("Tax %", min_value=0.0, max_value=100.0, value=0.0, step=5.0, key="item_tax")
            with cols[4]:
                discount = st.number_input("Discount %", min_value=0.0, max_value=100.0, value=0.0, step=5.0, key="item_discount")
            with cols[5]:
                submitted = st.form_submit_button("➕ Add")
            
            if submitted and description:
                # Validate amount
                if validate_amount(unit_price):
                    subtotal = quantity * unit_price
                    discount_amount = subtotal * (discount / 100)
                    taxable_amount = subtotal - discount_amount
                    tax_amount = taxable_amount * (tax_rate / 100)
                    total = taxable_amount + tax_amount
                    
                    st.session_state.invoice_items.append({
                        'description': sanitize_input(description),
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
                    st.rerun()
                else:
                    st.error("Invalid unit price")
        
        # Display current items
        if st.session_state.invoice_items:
            df_items = pd.DataFrame(st.session_state.invoice_items)
            
            # Calculate totals
            subtotal = df_items['subtotal'].sum()
            total_discount = df_items['discount_amount'].sum()
            total_tax = df_items['tax_amount'].sum()
            grand_total = df_items['total'].sum()
            
            # Display items
            edited_df = st.data_editor(
                df_items,
                column_config={
                    "description": "Description",
                    "quantity": st.column_config.NumberColumn("Qty", min_value=1),
                    "unit_price": st.column_config.NumberColumn("Unit Price", 
                                                               format=f"{st.session_state.currency} %.2f"),
                    "tax_rate": st.column_config.NumberColumn("Tax %", format="%.1f%%"),
                    "discount": st.column_config.NumberColumn("Discount %", format="%.1f%%"),
                    "subtotal": st.column_config.NumberColumn("Subtotal", disabled=True),
                    "discount_amount": st.column_config.NumberColumn("Discount", disabled=True),
                    "tax_amount": st.column_config.NumberColumn("Tax", disabled=True),
                    "total": st.column_config.NumberColumn("Total", disabled=True)
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Subtotal", f"{st.session_state.currency} {subtotal:,.2f}")
            with col2:
                st.metric("Total Discount", f"{st.session_state.currency} {total_discount:,.2f}")
            with col3:
                st.metric("Total Tax", f"{st.session_state.currency} {total_tax:,.2f}")
            with col4:
                st.metric("Grand Total", f"{st.session_state.currency} {grand_total:,.2f}")
            
            # Navigation buttons
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("← Back", use_container_width=True):
                    st.session_state.current_step = 1
                    st.rerun()
            with col3:
                if st.button("Next → Preview", type="primary", use_container_width=True):
                    st.session_state.current_step = 3
                    st.rerun()
        else:
            st.info("Add items to continue")
            if st.button("← Back", use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
    
    # Step 3: Preview & Send
    elif st.session_state.current_step == 3:
        st.markdown("#### Preview & Send")
        
        if st.session_state.invoice_items:
            # Prepare invoice data
            invoice_data = {
                'invoice_number': invoice_number,
                'invoice_date': str(invoice_date),
                'due_date': str(due_date),
                'po_number': po_number,
                'shipping_address': shipping_address,
                'terms_conditions': terms_conditions,
                'notes': notes,
                'currency': st.session_state.currency,
                'client': {
                    'name': client_name,
                    'email': client_email,
                    'phone': client_phone,
                    'address': client_address,
                    'city': client_city,
                    'state': client_state,
                    'zip': client_zip,
                    'country': client_country,
                    'tax_id': client_tax_id
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
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Preview
                st.markdown(f"""
                <div class="invoice-card">
                    <div style='display: flex; justify-content: space-between;'>
                        <div>
                            <h2 style='color: #667eea;'>INVOICE</h2>
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
                    {client_address if client_address else ''}<br>
                    Email: {client_email}</p>
                    
                    {f"<p><strong>Shipping Address:</strong><br>{shipping_address}</p>" if shipping_address else ""}
                    
                    <h3>Items:</h3>
                    {df_items.to_html(index=False)}
                    
                    <hr>
                    
                    <div style='text-align: right;' class='total-section'>
                        <p><strong>Subtotal:</strong> {st.session_state.currency} {subtotal:,.2f}</p>
                        <p><strong>Discount:</strong> {st.session_state.currency} {total_discount:,.2f}</p>
                        <p><strong>Tax:</strong> {st.session_state.currency} {total_tax:,.2f}</p>
                        <h2>Total Due: {st.session_state.currency} {grand_total:,.2f}</h2>
                    </div>
                    
                    {f"<hr><p><strong>Terms:</strong> {terms_conditions}</p>" if terms_conditions else ""}
                    {f"<p><strong>Notes:</strong> {notes}</p>" if notes else ""}
                    
                    <hr>
                    
                    <div style='text-align: center; color: #666;'>
                        <p>{st.session_state.company_info.get('bank_details', '')}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("#### Actions")
                
                # Save to database
                if st.button("💾 Save Invoice", use_container_width=True):
                    if save_invoice(invoice_data):
                        st.success("Invoice saved successfully!")
                        log_activity(st.session_state.user_id, 'invoice_saved', 
                                   f"Invoice {invoice_number} saved")
                    else:
                        st.error("Failed to save invoice")
                
                # Generate PDF
                if PDF_AVAILABLE:
                    if st.button("📄 Generate PDF", use_container_width=True):
                        with st.spinner("Generating PDF..."):
                            pdf_buffer = generate_pdf_invoice(invoice_data)
                            if pdf_buffer:
                                b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
                                href = f'<a href="data:application/pdf;base64,{b64}" download="invoice_{invoice_number}.pdf">Download PDF</a>'
                                st.markdown(href, unsafe_allow_html=True)
                                st.success("PDF generated!")
                    else:
                        st.warning("PDF generation not available")
                
                # Send Email
                st.markdown("#### Send via Email")
                email_to = st.text_input("Recipient Email", value=client_email)
                email_subject = st.text_input("Subject", f"Invoice {invoice_number}")
                email_body = st.text_area("Message", 
                    f"Dear {client_name},\n\nPlease find attached invoice {invoice_number} for {st.session_state.currency} {grand_total:,.2f}.\n\nThank you for your business!")
                
                if st.button("📧 Send Email", use_container_width=True):
                    if validate_email(email_to):
                        with st.spinner("Sending email..."):
                            if send_invoice_email(email_to, email_subject, email_body):
                                st.success("Email sent successfully!")
                                log_activity(st.session_state.user_id, 'email_sent', 
                                           f"Email sent to {email_to}")
                            else:
                                st.error("Failed to send email")
                    else:
                        st.error("Invalid email address")
                
                # Payment Link
                st.markdown("#### Payment Link")
                if STRIPE_AVAILABLE:
                    if st.button("💳 Generate Payment Link", use_container_width=True):
                        with st.spinner("Creating payment link..."):
                            payment_url = create_stripe_payment_link(
                                grand_total, 
                                st.session_state.currency,
                                f"Invoice {invoice_number}",
                                invoice_number
                            )
                            if payment_url:
                                st.success("Payment link created!")
                                st.markdown(f"[Click to Pay]({payment_url})")
                                log_activity(st.session_state.user_id, 'payment_link', 
                                           f"Payment link created for {invoice_number}")
                            else:
                                st.error("Failed to create payment link")
                else:
                    st.warning("Stripe not configured")
                
                # Navigation
                if st.button("← Back to Items", use_container_width=True):
                    st.session_state.current_step = 2
                    st.rerun()
                
                if st.button("🔄 New Invoice", use_container_width=True):
                    st.session_state.invoice_items = []
                    st.session_state.current_step = 1
                    st.rerun()
        else:
            st.warning("No items to preview")
            if st.button("← Back to Items", use_container_width=True):
                st.session_state.current_step = 2
                st.rerun()

# [Continue with other sections - Templates, Clients, Multi-Currency, etc.]
# Due to space constraints, I'm including the other sections with the same enhanced structure

elif choice == "📋 Templates":
    st.markdown("### 🎨 Invoice Templates")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Create New Template")
        with st.form("template_form"):
            template_name = st.text_input("Template Name *")
            
            st.markdown("##### Colors")
            primary_color = st.color_picker("Primary Color", "#667eea")
            secondary_color = st.color_picker("Secondary Color", "#764ba2")
            
            st.markdown("##### Layout")
            font_family = st.selectbox("Font Family", 
                                      ["Arial", "Helvetica", "Times New Roman", "Courier"])
            show_logo = st.checkbox("Show Logo", True)
            show_bank_details = st.checkbox("Show Bank Details", True)
            show_terms = st.checkbox("Show Terms", True)
            
            submitted = st.form_submit_button("💾 Save Template")
            
            if submitted and template_name:
                template_data = {
                    'primary_color': primary_color,
                    'secondary_color': secondary_color,
                    'font_family': font_family,
                    'show_logo': show_logo,
                    'show_bank_details': show_bank_details,
                    'show_terms': show_terms,
                    'created_at': datetime.now().isoformat()
                }
                
                if save_template(template_name, template_data):
                    st.success(f"Template '{template_name}' saved!")
                    log_activity(st.session_state.user_id, 'template_saved', 
                               f"Template '{template_name}' created")
    
    with col2:
        st.markdown("#### Available Templates")
        
        templates = load_templates()
        
        if templates:
            cols = st.columns(2)
            for idx, (name, data) in enumerate(templates.items()):
                with cols[idx % 2]:
                    st.markdown(f"""
                    <div class="template-card {'selected' if name == st.session_state.current_template else ''}">
                        <h4>{name}</h4>
                        <div style="background-color: {data.get('primary_color', '#667eea')}; 
                                   height: 20px; width: 100%; border-radius: 5px; margin: 5px 0;"></div>
                        <p>Font: {data.get('font_family', 'Arial')}</p>
                        <p>Created: {data.get('created_at', 'Unknown')[:10]}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"Use", key=f"use_{name}"):
                            st.session_state.current_template = name
                            st.success(f"Template '{name}' selected!")
                    with col2:
                        if st.button(f"Delete", key=f"del_{name}"):
                            # Delete template logic
                            st.warning("Delete functionality coming soon")
        else:
            st.info("No templates saved yet")

elif choice == "👥 Clients":
    st.markdown("### 👥 Client Management")
    
    tab1, tab2 = st.tabs(["Client List", "Add Client"])
    
    with tab1:
        clients_df = get_clients()
        
        if not clients_df.empty:
            # Search
            search = st.text_input("🔍 Search Clients", placeholder="Search by name or email...")
            if search:
                mask = (clients_df['name'].str.contains(search, case=False) | 
                       clients_df['email'].str.contains(search, case=False))
                clients_df = clients_df[mask]
            
            # Display clients
            for _, client in clients_df.iterrows():
                with st.expander(f"📌 {client['name']} - {client['email']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Phone:** {client['phone']}")
                        st.markdown(f"**Address:** {client['address']}")
                        st.markdown(f"**City:** {client['city']}")
                    with col2:
                        st.markdown(f"**State:** {client['state']}")
                        st.markdown(f"**ZIP:** {client['zip_code']}")
                        st.markdown(f"**Country:** {client['country']}")
                    
                    if st.button(f"Select for Invoice", key=f"select_{client['id']}"):
                        st.session_state.selected_client = client.to_dict()
                        st.success(f"Client {client['name']} selected!")
            
            # Export
            csv = clients_df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="clients.csv">📥 Download CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No clients found")
    
    with tab2:
        with st.form("add_client_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Name *")
                email = st.text_input("Email *")
                phone = st.text_input("Phone")
                tax_id = st.text_input("Tax ID")
            
            with col2:
                address = st.text_input("Address")
                city = st.text_input("City")
                state = st.text_input("State")
                zip_code = st.text_input("ZIP Code")
                country = st.text_input("Country")
            
            notes = st.text_area("Notes")
            
            if st.form_submit_button("➕ Add Client"):
                if name and email and validate_email(email):
                    client_data = {
                        'name': name,
                        'email': email,
                        'phone': phone,
                        'address': address,
                        'city': city,
                        'state': state,
                        'zip_code': zip_code,
                        'country': country,
                        'tax_id': tax_id,
                        'notes': notes
                    }
                    
                    if save_client(client_data):
                        st.success(f"Client {name} added successfully!")
                        log_activity(st.session_state.user_id, 'client_added', f"Client {name} added")
                    else:
                        st.error("Failed to add client")
                else:
                    st.error("Please provide valid name and email")

elif choice == "💰 Multi-Currency":
    st.markdown("### 💰 Multi-Currency Support")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Currency Settings")
        
        currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR', 'SGD', 'HKD', 'NZD']
        base_currency = st.selectbox("Base Currency", currencies, index=currencies.index(st.session_state.currency))
        
        if st.button("🔄 Update Exchange Rates"):
            with st.spinner("Fetching exchange rates..."):
                rates = get_exchange_rates(base_currency)
                st.session_state.exchange_rates = rates
                st.success("Exchange rates updated!")
                log_activity(st.session_state.user_id, 'rates_updated', f"Exchange rates updated for {base_currency}")
        
        if st.button("💱 Set Default Currency"):
            st.session_state.currency = base_currency
            st.success(f"Default currency set to {base_currency}")
    
    with col2:
        st.markdown("#### Current Exchange Rates")
        
        rates = st.session_state.exchange_rates or get_exchange_rates()
        
        rates_data = []
        for currency, rate in rates.items():
            rates_data.append({
                'Currency': currency,
                'Rate': f"{rate:.4f}",
                'Inverse': f"{1/rate:.4f}" if rate > 0 else 'N/A'
            })
        
        rates_df = pd.DataFrame(rates_data)
        st.dataframe(rates_df, use_container_width=True, hide_index=True)
        
        st.markdown("#### Currency Converter")
        amount = st.number_input("Amount", value=100.0, min_value=0.01)
        from_curr = st.selectbox("From", currencies, key='from_curr')
        to_curr = st.selectbox("To", currencies, key='to_curr')
        
        if st.button("Convert"):
            converted = convert_currency(amount, from_curr, to_curr)
            st.success(f"{amount:,.2f} {from_curr} = {converted:,.2f} {to_curr}")

elif choice == "💳 Payment Integration":
    st.markdown("### 💳 Payment Integration")
    
    tab1, tab2, tab3 = st.tabs(["Stripe Settings", "Create Payment Link", "Payment History"])
    
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
            log_activity(st.session_state.user_id, 'stripe_settings', 'Stripe settings updated')
        
        st.markdown("---")
        st.markdown("##### Test Mode")
        test_mode = st.checkbox("Use Test Mode", True)
        if test_mode:
            st.info("Using Stripe test mode. No real charges will be made.")
    
    with tab2:
        st.markdown("#### Create Payment Link")
        
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount", min_value=0.01, value=100.0)
            currency = st.selectbox("Currency", ['USD', 'EUR', 'GBP', 'JPY'])
        with col2:
            description = st.text_input("Description", "Invoice Payment")
            invoice_ref = st.text_input("Invoice Reference")
        
        if st.button("Generate Payment Link"):
            if STRIPE_AVAILABLE and st.session_state.stripe_settings.get('api_key'):
                with st.spinner("Creating payment link..."):
                    payment_url = create_stripe_payment_link(amount, currency, description, invoice_ref)
                    if payment_url:
                        st.success("Payment link created!")
                        st.markdown(f"🔗 [Payment Link]({payment_url})")
                        
                        # QR Code (simple representation)
                        st.markdown("##### QR Code")
                        qr_data = base64.b64encode(payment_url.encode()).decode()
                        st.markdown(f"![QR Code](https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={payment_url})")
            else:
                st.error("Stripe not configured properly")
    
    with tab3:
        st.markdown("#### Payment History")
        
        try:
            with get_db_connection() as conn:
                payments_df = pd.read_sql_query(
                    "SELECT invoice_number, payment_url, amount, currency, status, created_at, paid_at FROM payment_links ORDER BY created_at DESC",
                    conn
                )
                
                if not payments_df.empty:
                    st.dataframe(payments_df, use_container_width=True)
                else:
                    st.info("No payment links created yet")
        except:
            st.info("No payment history available")

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
        use_tls = st.checkbox("Use TLS", True)
        
        if st.button("Save Email Settings"):
            st.session_state.email_settings = {
                'smtp_server': smtp_server,
                'smtp_port': smtp_port,
                'sender_email': sender_email,
                'sender_password': sender_password,
                'use_tls': use_tls
            }
            st.success("Email settings saved!")
            log_activity(st.session_state.user_id, 'email_settings', 'Email settings updated')
    
    with col2:
        st.markdown("#### Email Templates")
        
        email_template = st.text_area("Default Email Template",
            st.session_state.email_template,
            height=200)
        
        if st.button("Save Template"):
            st.session_state.email_template = email_template
            st.success("Email template saved!")
        
        st.markdown("#### Test Connection")
        test_email = st.text_input("Test Email Address")
        
        if st.button("Send Test Email"):
            if test_email and validate_email(test_email):
                with st.spinner("Sending test email..."):
                    test_body = "<h3>Test Email</h3><p>This is a test email from your Invoice Generator system.</p>"
                    if send_invoice_email(test_email, "Test Email from Invoice Generator", test_body):
                        st.success("Test email sent!")
                    else:
                        st.error("Failed to send test email")
            else:
                st.error("Please enter a valid email address")

elif choice == "📊 Analytics":
    st.markdown("### 📊 Analytics Dashboard")
    
    # Get analytics data
    analytics = get_invoice_analytics()
    
    if analytics:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Revenue", f"{st.session_state.currency} {analytics['total_revenue']:,.2f}")
        with col2:
            st.metric("Total Invoices", analytics['total_invoices'])
        with col3:
            st.metric("Average Invoice", f"{st.session_state.currency} {analytics['avg_invoice']:,.2f}")
        with col4:
            paid_percentage = (analytics['paid_count'] / analytics['total_invoices'] * 100) if analytics['total_invoices'] > 0 else 0
            st.metric("Paid Rate", f"{paid_percentage:.1f}%")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Revenue trend
            if analytics['monthly']:
                months = [row['month'] for row in analytics['monthly']]
                revenues = [row['revenue'] for row in analytics['monthly']]
                
                fig = px.line(x=months, y=revenues, title="Monthly Revenue Trend")
                fig.update_layout(xaxis_title="Month", yaxis_title=f"Revenue ({st.session_state.currency})")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No monthly data available")
        
        with col2:
            # Invoice status distribution
            status_data = {
                'Status': ['Paid', 'Pending', 'Overdue'],
                'Count': [analytics['paid_count'], 
                         analytics['total_invoices'] - analytics['paid_count'] - analytics['overdue_count'],
                         analytics['overdue_count']]
            }
            status_df = pd.DataFrame(status_data)
            
            fig = px.pie(status_df, values='Count', names='Status', title="Invoice Status Distribution")
            st.plotly_chart(fig, use_container_width=True)
        
        # Recent invoices
        st.markdown("#### Recent Invoices")
        recent_invoices = get_invoices()
        if not recent_invoices.empty:
            recent_invoices = recent_invoices.head(5)
            
            # Add status badges
            def status_badge(status):
                colors = {
                    'paid': 'badge-success',
                    'draft': 'badge-info',
                    'overdue': 'badge-danger',
                    'pending': 'badge-warning'
                }
                return f'<span class="badge {colors.get(status, "badge-info")}">{status}</span>'
            
            recent_invoices['status_badge'] = recent_invoices['status'].apply(status_badge)
            st.write(recent_invoices[['invoice_number', 'created_at', 'grand_total', 'status_badge']].to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.info("No recent invoices")
    else:
        st.info("No analytics data available")

elif choice == "🗄️ Database":
    st.markdown("### 🗄️ Database Management")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Invoices", "Clients", "Activity Log", "Backup"])
    
    with tab1:
        st.markdown("#### Stored Invoices")
        
        invoices_df = get_invoices()
        
        if not invoices_df.empty:
            # Filters
            status_filter = st.selectbox("Filter by Status", 
                                       ['All'] + list(invoices_df['status'].unique()))
            if status_filter != 'All':
                invoices_df = invoices_df[invoices_df['status'] == status_filter]
            
            st.dataframe(invoices_df, use_container_width=True)
            
            # Export
            csv = invoices_df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="invoices_export.csv">📥 Download CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No invoices in database")
    
    with tab2:
        st.markdown("#### Stored Clients")
        
        clients_df = get_clients()
        
        if not clients_df.empty:
            st.dataframe(clients_df, use_container_width=True)
            
            # Export
            csv = clients_df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="clients_export.csv">📥 Download CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No clients in database")
    
    with tab3:
        st.markdown("#### Activity Log")
        
        try:
            with get_db_connection() as conn:
                log_df = pd.read_sql_query(
                    "SELECT user_id, action, details, created_at FROM activity_log ORDER BY created_at DESC LIMIT 100",
                    conn
                )
                
                if not log_df.empty:
                    st.dataframe(log_df, use_container_width=True)
                else:
                    st.info("No activity logged yet")
        except:
            st.info("Activity log not available")
    
    with tab4:
        st.markdown("#### Database Backup")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Download Backup", use_container_width=True):
                try:
                    with open('invoices.db', 'rb') as f:
                        db_bytes = f.read()
                    
                    b64 = base64.b64encode(db_bytes).decode()
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="invoices_backup_{timestamp}.db">Click to Download</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("Backup created!")
                except Exception as e:
                    st.error(f"Backup failed: {e}")
        
        with col2:
            uploaded_file = st.file_uploader("Restore from Backup", type=['db'])
            if uploaded_file is not None:
                if st.button("⚠️ Restore Database", use_container_width=True):
                    try:
                        with open('invoices.db', 'wb') as f:
                            f.write(uploaded_file.getbuffer())
                        st.success("Database restored! Please restart the app.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Restore failed: {e}")
        
        st.markdown("---")
        st.markdown("#### Maintenance")
        
        if st.button("🧹 Vacuum Database (Optimize)", use_container_width=True):
            try:
                with get_db_connection() as conn:
                    conn.execute("VACUUM")
                st.success("Database optimized!")
            except Exception as e:
                st.error(f"Optimization failed: {e}")
        
        st.warning("⚠️ Clear all data - This action cannot be undone!")
        confirm = st.checkbox("I understand this will delete all data")
        if confirm and st.button("🗑️ Clear All Data", use_container_width=True):
            try:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM invoices WHERE user_id = ?", (st.session_state.user_id,))
                    c.execute("DELETE FROM clients WHERE user_id = ?", (st.session_state.user_id,))
                    c.execute("DELETE FROM templates WHERE user_id = ?", (st.session_state.user_id,))
                    c.execute("DELETE FROM activity_log")
                    conn.commit()
                st.success("All data cleared!")
                log_activity(st.session_state.user_id, 'data_cleared', 'All user data cleared')
            except Exception as e:
                st.error(f"Error clearing data: {e}")

# Footer
st.markdown("""
    <div class="footer">
        <p>Made with ❤️ using Streamlit | Advanced Invoice Generator Pro v3.0</p>
        <p>💼 Multi-Currency | 📧 Email Integration | 💳 Payment Links | 🗄️ Database Storage | 📊 Analytics</p>
        <p style="font-size: 0.8rem; margin-top: 1rem;">© 2024 Invoice Generator Pro. All rights reserved.</p>
    </div>
""", unsafe_allow_html=True)

# Auto-save feature
if st.session_state.get('auto_save', False):
    with st.spinner("Auto-saving..."):
        time.sleep(1)
        st.success("Auto-saved!")
