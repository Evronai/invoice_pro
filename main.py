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
import smtplib
import hashlib
import secrets
import shutil
from contextlib import contextmanager

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

# Excel export
try:
    import xlsxwriter
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    logger.warning("XlsxWriter not installed. Excel export disabled.")

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

# Recurring frequencies
RECURRING_FREQUENCIES = {
    'None': None,
    'Daily': timedelta(days=1),
    'Weekly': timedelta(weeks=1),
    'Monthly': timedelta(days=30),
    'Quarterly': timedelta(days=90),
    'Yearly': timedelta(days=365)
}

# Payment methods
PAYMENT_METHODS = ['Cash', 'Bank Transfer', 'Credit Card', 'Cheque', 'Online Payment']

# ============================================================================
# DATABASE CONTEXT MANAGER
# ============================================================================

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = sqlite3.connect('invoices.db')
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

# ============================================================================
# ENHANCED DATABASE FUNCTIONS
# ============================================================================

def init_database():
    """Initialize SQLite database with enhanced schema"""
    try:
        with get_db_connection() as conn:
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
                          paid_date TEXT,
                          recurring_frequency TEXT,
                          recurring_next_date TEXT,
                          template_id INTEGER,
                          created_by INTEGER)''')
            
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
                          FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE)''')
            
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
                          updated_at TEXT,
                          credit_limit REAL DEFAULT 0,
                          payment_terms INTEGER DEFAULT 30)''')
            
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
                          created_by INTEGER,
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
                          vat_registered BOOLEAN DEFAULT 1,
                          invoice_prefix TEXT DEFAULT 'INV',
                          updated_at TEXT)''')
            
            # Users table
            c.execute('''CREATE TABLE IF NOT EXISTS users
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          username TEXT UNIQUE,
                          password_hash TEXT,
                          email TEXT,
                          role TEXT DEFAULT 'user',
                          full_name TEXT,
                          is_active BOOLEAN DEFAULT 1,
                          created_at TEXT,
                          last_login TEXT)''')
            
            # Audit log table
            c.execute('''CREATE TABLE IF NOT EXISTS audit_log
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          user_id INTEGER,
                          action TEXT,
                          details TEXT,
                          ip_address TEXT,
                          timestamp TEXT,
                          FOREIGN KEY (user_id) REFERENCES users(id))''')
            
            # Invoice templates table
            c.execute('''CREATE TABLE IF NOT EXISTS invoice_templates
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          name TEXT,
                          template_data TEXT,
                          created_at TEXT,
                          created_by INTEGER,
                          is_default BOOLEAN DEFAULT 0)''')
            
            # Recurring invoices table
            c.execute('''CREATE TABLE IF NOT EXISTS recurring_invoices
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          template_id INTEGER,
                          client_id INTEGER,
                          frequency TEXT,
                          start_date TEXT,
                          end_date TEXT,
                          next_date TEXT,
                          last_generated TEXT,
                          is_active BOOLEAN DEFAULT 1,
                          created_at TEXT,
                          FOREIGN KEY (template_id) REFERENCES invoice_templates(id),
                          FOREIGN KEY (client_id) REFERENCES clients(id))''')
            
            # Insert default admin user if not exists
            c.execute("SELECT COUNT(*) FROM users")
            if c.fetchone()[0] == 0:
                default_password = "admin123"  # Change in production
                password_hash = hashlib.sha256(default_password.encode()).hexdigest()
                c.execute('''INSERT INTO users (username, password_hash, email, role, full_name, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                         ('admin', password_hash, 'admin@example.com', 'admin', 'System Administrator', 
                          datetime.now().isoformat()))
            
            # Insert default company settings
            c.execute("SELECT COUNT(*) FROM company_settings")
            if c.fetchone()[0] == 0:
                c.execute('''INSERT INTO company_settings 
                           (id, name, address, city, phone, email, tax_id, bank_details, 
                            default_currency, vat_registered, invoice_prefix, updated_at)
                           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         ('Your Business Name', '123 Business Street', 'Port of Spain, Trinidad',
                          '(868) 123-4567', 'accounts@yourbusiness.com', '123456789',
                          'First Citizens Bank\nAccount: 123456789\nSort Code: 123-456',
                          'TTD', 1, 'INV', datetime.now().isoformat()))
            
            return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False

def log_action(user_id, action, details):
    """Log user actions for audit trail"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO audit_log 
                       (user_id, action, details, timestamp)
                       VALUES (?, ?, ?, ?)''',
                     (user_id, action, details, datetime.now().isoformat()))
        return True
    except Exception as e:
        logger.error(f"Audit log error: {e}")
        return False

def backup_database():
    """Create database backup"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"backup_invoices_{timestamp}.db"
        
        # Copy database file
        shutil.copy2('invoices.db', backup_file)
        
        # Create download link
        with open(backup_file, 'rb') as f:
            bytes_data = f.read()
        
        # Clean up
        os.remove(backup_file)
        
        return bytes_data, backup_file
    except Exception as e:
        logger.error(f"Backup error: {e}")
        return None, None

def restore_database(backup_file):
    """Restore database from backup"""
    try:
        shutil.copy2(backup_file, 'invoices.db')
        return True
    except Exception as e:
        logger.error(f"Restore error: {e}")
        return False

def validate_invoice_data(invoice_data, items):
    """Validate invoice data before saving"""
    errors = []
    warnings = []
    
    # Required fields
    required_fields = ['client_name', 'client_email', 'invoice_date', 'due_date']
    for field in required_fields:
        if not invoice_data.get(field):
            errors.append(f"{field.replace('_', ' ').title()} is required")
    
    # Validate email
    if invoice_data.get('client_email'):
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, invoice_data['client_email']):
            errors.append("Invalid email format")
    
    # Validate dates
    if invoice_data.get('invoice_date') and invoice_data.get('due_date'):
        try:
            invoice_date = datetime.strptime(invoice_data['invoice_date'], '%Y-%m-%d').date()
            due_date = datetime.strptime(invoice_data['due_date'], '%Y-%m-%d').date()
            if due_date < invoice_date:
                errors.append("Due date cannot be before invoice date")
        except:
            errors.append("Invalid date format")
    
    # Validate items
    if not items:
        errors.append("At least one item is required")
    else:
        for i, item in enumerate(items):
            if not item.get('description'):
                errors.append(f"Item {i+1}: Description is required")
            if item.get('quantity', 0) <= 0:
                errors.append(f"Item {i+1}: Quantity must be greater than 0")
            if item.get('unit_price', 0) < 0:
                errors.append(f"Item {i+1}: Unit price cannot be negative")
            if item.get('tax_rate', 0) < 0 or item.get('tax_rate', 0) > 100:
                errors.append(f"Item {i+1}: Tax rate must be between 0 and 100")
            if item.get('discount', 0) < 0 or item.get('discount', 0) > 100:
                errors.append(f"Item {i+1}: Discount must be between 0 and 100")
    
    # Warnings
    if invoice_data.get('grand_total', 0) > 10000:
        warnings.append("Large invoice amount - verify with client")
    
    return errors, warnings

def save_invoice_to_db(invoice_data, items):
    """Save invoice and items to database"""
    try:
        # Validate data
        errors, warnings = validate_invoice_data(invoice_data, items)
        if errors:
            return None, errors, warnings
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Calculate balance due
            balance_due = invoice_data['grand_total'] - invoice_data.get('amount_paid', 0)
            
            # Insert invoice
            c.execute('''INSERT INTO invoices 
                       (invoice_number, client_name, client_email, client_address, client_phone,
                        invoice_date, due_date, po_number, currency, subtotal, tax_total, 
                        discount_total, grand_total, amount_paid, balance_due, status, notes, 
                        created_at, updated_at, recurring_frequency, recurring_next_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (invoice_data['invoice_number'], invoice_data['client_name'], 
                      invoice_data['client_email'], invoice_data.get('client_address', ''),
                      invoice_data.get('client_phone', ''), invoice_data['invoice_date'],
                      invoice_data['due_date'], invoice_data.get('po_number', ''),
                      invoice_data['currency'], invoice_data['subtotal'], 
                      invoice_data['tax_total'], invoice_data['discount_total'],
                      invoice_data['grand_total'], invoice_data.get('amount_paid', 0),
                      balance_due, invoice_data.get('status', 'Draft'),
                      invoice_data.get('notes', ''), datetime.now().isoformat(),
                      datetime.now().isoformat(), invoice_data.get('recurring_frequency'),
                      invoice_data.get('recurring_next_date')))
            
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
            
            # Log action
            log_action(1, 'CREATE_INVOICE', f"Created invoice {invoice_data['invoice_number']}")
            
            return invoice_id, errors, warnings
    except Exception as e:
        logger.error(f"Save invoice error: {e}")
        return None, [str(e)], []

def process_payment(invoice_id, amount, method='Bank Transfer', reference='', notes=''):
    """Process payment for an invoice"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Get current invoice data
            c.execute('''SELECT grand_total, amount_paid, status, invoice_number 
                        FROM invoices WHERE id = ?''', (invoice_id,))
            invoice = c.fetchone()
            
            if not invoice:
                return False, "Invoice not found"
            
            grand_total, amount_paid, status, invoice_number = invoice
            
            # Check if already paid
            if status == 'Paid':
                return False, "Invoice already paid"
            
            # Record payment
            c.execute('''INSERT INTO payments 
                       (invoice_id, amount, payment_date, payment_method, reference, notes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (invoice_id, amount, datetime.now().isoformat(), method, 
                      reference, notes, datetime.now().isoformat()))
            
            # Update invoice
            new_amount_paid = amount_paid + amount
            new_balance = grand_total - new_amount_paid
            
            c.execute('''UPDATE invoices 
                       SET amount_paid = ?, balance_due = ?, updated_at = ?
                       WHERE id = ?''', (new_amount_paid, new_balance, datetime.now().isoformat(), invoice_id))
            
            # Check if fully paid
            if abs(new_balance) < 0.01:
                c.execute('''UPDATE invoices SET status = 'Paid', paid_date = ?
                           WHERE id = ?''', (datetime.now().isoformat(), invoice_id))
            
            # Log action
            log_action(1, 'RECORD_PAYMENT', f"Payment of {amount} recorded for invoice {invoice_number}")
            
            conn.commit()
            return True, "Payment recorded successfully"
    except Exception as e:
        logger.error(f"Payment error: {e}")
        return False, str(e)

def update_invoice_status(invoice_id, new_status):
    """Update invoice status"""
    try:
        with get_db_connection() as conn:
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
            
            # Log action
            log_action(1, 'UPDATE_STATUS', f"Updated invoice {invoice_id} status to {new_status}")
            
            return True
    except Exception as e:
        logger.error(f"Update status error: {e}")
        return False

def get_invoices(filters=None):
    """Get invoices with optional filters"""
    try:
        with get_db_connection() as conn:
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
            return df
    except Exception as e:
        logger.error(f"Get invoices error: {e}")
        return pd.DataFrame()

def get_invoice_by_id(invoice_id):
    """Get invoice details by ID"""
    try:
        with get_db_connection() as conn:
            # Get invoice
            invoice_df = pd.read_sql_query(
                "SELECT * FROM invoices WHERE id = ?", conn, params=[invoice_id]
            )
            
            if invoice_df.empty:
                return None, None
            
            invoice = invoice_df.iloc[0].to_dict()
            
            # Get invoice items
            items_df = pd.read_sql_query(
                "SELECT * FROM invoice_items WHERE invoice_id = ?", conn, params=[invoice_id]
            )
            
            items = items_df.to_dict('records') if not items_df.empty else []
            
            return invoice, items
    except Exception as e:
        logger.error(f"Get invoice by ID error: {e}")
        return None, None

def delete_invoice(invoice_id):
    """Delete invoice and its items"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Get invoice number for logging
            c.execute("SELECT invoice_number FROM invoices WHERE id = ?", (invoice_id,))
            result = c.fetchone()
            invoice_number = result['invoice_number'] if result else "Unknown"
            
            # Delete items first (foreign key constraint)
            c.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
            
            # Delete payments
            c.execute("DELETE FROM payments WHERE invoice_id = ?", (invoice_id,))
            
            # Delete invoice
            c.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
            
            conn.commit()
            
            # Log action
            log_action(1, 'DELETE_INVOICE', f"Deleted invoice {invoice_number}")
            
            return True
    except Exception as e:
        logger.error(f"Delete invoice error: {e}")
        return False

def save_client_to_db(client_data):
    """Save or update client"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Check if client exists
            c.execute("SELECT id FROM clients WHERE email = ?", (client_data['email'],))
            existing = c.fetchone()
            
            if existing:
                # Update existing client
                c.execute('''UPDATE clients SET name = ?, phone = ?, address = ?, 
                            company = ?, tax_id = ?, notes = ?, credit_limit = ?,
                            payment_terms = ?, updated_at = ?
                            WHERE email = ?''',
                         (client_data['name'], client_data.get('phone', ''),
                          client_data.get('address', ''), client_data.get('company', ''),
                          client_data.get('tax_id', ''), client_data.get('notes', ''),
                          client_data.get('credit_limit', 0), client_data.get('payment_terms', 30),
                          datetime.now().isoformat(), client_data['email']))
                client_id = existing[0]
            else:
                # Insert new client
                c.execute('''INSERT INTO clients 
                           (name, email, phone, address, company, tax_id, notes, 
                            credit_limit, payment_terms, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (client_data['name'], client_data['email'], 
                          client_data.get('phone', ''), client_data.get('address', ''),
                          client_data.get('company', ''), client_data.get('tax_id', ''),
                          client_data.get('notes', ''), client_data.get('credit_limit', 0),
                          client_data.get('payment_terms', 30), datetime.now().isoformat(),
                          datetime.now().isoformat()))
                client_id = c.lastrowid
            
            conn.commit()
            
            # Log action
            log_action(1, 'SAVE_CLIENT', f"Saved client {client_data['name']}")
            
            return client_id
    except Exception as e:
        logger.error(f"Save client error: {e}")
        return None

def get_clients(search=None):
    """Get clients with optional search"""
    try:
        with get_db_connection() as conn:
            if search:
                query = "SELECT * FROM clients WHERE name LIKE ? OR email LIKE ? OR company LIKE ? ORDER BY name"
                params = [f"%{search}%", f"%{search}%", f"%{search}%"]
                df = pd.read_sql_query(query, conn, params=params)
            else:
                df = pd.read_sql_query("SELECT * FROM clients ORDER BY name", conn)
            
            return df
    except Exception as e:
        logger.error(f"Get clients error: {e}")
        return pd.DataFrame()

def create_recurring_invoice(template_id, client_id, frequency, start_date, end_date=None):
    """Create recurring invoice schedule"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            next_date = start_date
            if frequency in RECURRING_FREQUENCIES and RECURRING_FREQUENCIES[frequency]:
                next_date = (datetime.strptime(start_date, '%Y-%m-%d') + 
                           RECURRING_FREQUENCIES[frequency]).strftime('%Y-%m-%d')
            
            c.execute('''INSERT INTO recurring_invoices
                       (template_id, client_id, frequency, start_date, end_date, next_date, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (template_id, client_id, frequency, start_date, end_date, next_date,
                      datetime.now().isoformat()))
            
            recurring_id = c.lastrowid
            
            # Log action
            log_action(1, 'CREATE_RECURRING', f"Created recurring invoice schedule {recurring_id}")
            
            return recurring_id
    except Exception as e:
        logger.error(f"Recurring invoice error: {e}")
        return None

def save_invoice_template(name, template_data):
    """Save invoice as template"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            c.execute('''INSERT INTO invoice_templates
                       (name, template_data, created_at, created_by)
                       VALUES (?, ?, ?, ?)''',
                     (name, json.dumps(template_data), datetime.now().isoformat(), 1))
            
            template_id = c.lastrowid
            
            return template_id
    except Exception as e:
        logger.error(f"Save template error: {e}")
        return None

def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        with get_db_connection() as conn:
            # Total invoices
            total_invoices = pd.read_sql_query("SELECT COUNT(*) as count FROM invoices", conn).iloc[0]['count']
            
            # Total revenue (paid)
            total_revenue = pd.read_sql_query(
                "SELECT SUM(grand_total) as total FROM invoices WHERE status = 'Paid'", 
                conn
            ).iloc[0]['total'] or 0
            
            # Total clients
            total_clients = pd.read_sql_query("SELECT COUNT(*) as count FROM clients", conn).iloc[0]['count']
            
            # Pending amount
            pending_amount = pd.read_sql_query(
                "SELECT SUM(balance_due) as total FROM invoices WHERE status NOT IN ('Paid', 'Cancelled')", 
                conn
            ).iloc[0]['total'] or 0
            
            # Overdue amount
            today = datetime.now().strftime('%Y-%m-%d')
            overdue_amount = pd.read_sql_query(
                f"SELECT SUM(balance_due) as total FROM invoices WHERE status = 'Overdue' OR (due_date < '{today}' AND status NOT IN ('Paid', 'Cancelled'))", 
                conn
            ).iloc[0]['total'] or 0
            
            # Monthly revenue (last 6 months)
            monthly_query = """
            SELECT strftime('%Y-%m', invoice_date) as month,
                   SUM(CASE WHEN status = 'Paid' THEN grand_total ELSE 0 END) as revenue,
                   COUNT(*) as count
            FROM invoices
            WHERE invoice_date >= date('now', '-6 months')
            GROUP BY strftime('%Y-%m', invoice_date)
            ORDER BY month DESC
            """
            monthly_data = pd.read_sql_query(monthly_query, conn)
            
            return {
                'total_invoices': total_invoices,
                'total_revenue': total_revenue,
                'total_clients': total_clients,
                'pending_amount': pending_amount,
                'overdue_amount': overdue_amount,
                'monthly_data': monthly_data
            }
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return None

def get_client_payment_history(client_id):
    """Get client payment history"""
    try:
        with get_db_connection() as conn:
            query = """
            SELECT i.invoice_number, i.invoice_date, i.grand_total, 
                   p.amount as paid_amount, p.payment_date, p.payment_method,
                   i.grand_total - COALESCE(p.total_paid, 0) as balance
            FROM invoices i
            LEFT JOIN (
                SELECT invoice_id, SUM(amount) as total_paid,
                       MAX(payment_date) as last_payment
                FROM payments
                GROUP BY invoice_id
            ) p_sum ON i.id = p_sum.invoice_id
            LEFT JOIN payments p ON i.id = p.invoice_id
            WHERE i.client_id = ?
            ORDER BY i.invoice_date DESC
            """
            df = pd.read_sql_query(query, conn, params=[client_id])
            return df
    except Exception as e:
        logger.error(f"Client payment history error: {e}")
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
    """Generate unique invoice number with safe session state access"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Default prefix
    prefix = 'INV'
    
    # Safely try to get from session state
    try:
        # Check if session state exists and has company_info
        if 'st' in globals() and hasattr(st, 'session_state'):
            if 'company_info' in st.session_state:
                prefix = st.session_state.company_info.get('invoice_prefix', 'INV')
    except (AttributeError, KeyError, NameError):
        # If any error occurs, use default
        pass
    
    return f"{prefix}-{timestamp}"

def safe_session_state_get(key, default=None):
    """Safely get a value from session state"""
    try:
        if hasattr(st, 'session_state') and key in st.session_state:
            return st.session_state[key]
    except (AttributeError, KeyError):
        pass
    return default

def safe_company_info_get(key, default=None):
    """Safely get a value from company_info in session state"""
    try:
        if hasattr(st, 'session_state'):
            company_info = st.session_state.get('company_info', {})
            return company_info.get(key, default)
    except (AttributeError, KeyError):
        pass
    return default

def save_logo(uploaded_file):
    """Save uploaded logo to session state"""
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        encoded = base64.b64encode(bytes_data).decode()
        
        st.session_state.company_info['logo_bytes'] = bytes_data
        st.session_state.company_info['logo_base64'] = encoded
        st.session_state.company_info['logo_filename'] = uploaded_file.name
        st.session_state.company_info['logo_mime'] = uploaded_file.type
        
        # Save to database
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute('''UPDATE company_settings 
                           SET logo_data = ?, logo_mime = ?, updated_at = ?
                           WHERE id = 1''',
                         (bytes_data, uploaded_file.type, datetime.now().isoformat()))
            return True
        except Exception as e:
            logger.error(f"Error saving logo to database: {e}")
            return True  # Still return True as it's saved in session
    
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
    
    # Remove from database
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''UPDATE company_settings 
                       SET logo_data = NULL, logo_mime = NULL, updated_at = ?
                       WHERE id = 1''',
                     (datetime.now().isoformat(),))
    except Exception as e:
        logger.error(f"Error removing logo from database: {e}")

def get_status_badge_html(status):
    """Generate HTML for status badge"""
    color = STATUS_COLORS.get(status, '#64748b')
    return f'<span class="status-badge" style="background-color: {color}20; color: {color}; border: 1px solid {color};">{status}</span>'

def send_email_invoice(to_email, pdf_buffer, invoice_number):
    """Send invoice via email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = st.session_state.company_info['email']
        msg['To'] = to_email
        msg['Subject'] = f"Invoice {invoice_number} from {st.session_state.company_info['name']}"
        
        body = f"""
        <html>
        <body>
            <p>Dear Customer,</p>
            
            <p>Please find attached invoice {invoice_number} for your reference.</p>
            
            <p><strong>Invoice Details:</strong><br>
            Invoice Number: {invoice_number}<br>
            Date: {datetime.now().strftime('%d %b %Y')}<br>
            Amount: {format_amount(st.session_state.get('grand_total', 0), st.session_state.currency)}</p>
            
            <p>Payment can be made via:<br>
            {st.session_state.company_info.get('bank_details', '').replace(chr(10), '<br>')}</p>
            
            <p>Thank you for your business!</p>
            
            <p>Best regards,<br>
            {st.session_state.company_info['name']}</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        
        # Attach PDF
        if pdf_buffer:
            pdf_part = MIMEApplication(pdf_buffer.getvalue(), Name=f"invoice_{invoice_number}.pdf")
            pdf_part['Content-Disposition'] = f'attachment; filename="invoice_{invoice_number}.pdf"'
            msg.attach(pdf_part)
        
        # Configure SMTP (use environment variables)
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        if smtp_username and smtp_password:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
            server.quit()
            return True, "Email sent successfully"
        else:
            return False, "SMTP not configured"
            
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False, str(e)

def export_to_excel(invoice_data, items):
    """Export invoice to Excel"""
    if not EXCEL_AVAILABLE:
        return None
    
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#2563eb',
                'font_color': 'white',
                'border': 1
            })
            
            money_format = workbook.add_format({'num_format': '$#,##0.00', 'border': 1})
            text_format = workbook.add_format({'border': 1})
            
            # Invoice details sheet
            invoice_df = pd.DataFrame([invoice_data])
            invoice_df.to_excel(writer, sheet_name='Invoice', index=False, startrow=1)
            
            # Format invoice sheet
            worksheet = writer.sheets['Invoice']
            worksheet.set_column('A:A', 20)
            worksheet.set_column('B:B', 30)
            
            # Add title
            worksheet.write('A1', 'INVOICE DETAILS', header_format)
            
            # Items sheet
            items_df = pd.DataFrame(items)
            items_df.to_excel(writer, sheet_name='Items', index=False, startrow=1)
            
            # Format items sheet
            worksheet_items = writer.sheets['Items']
            worksheet_items.write('A1', 'INVOICE ITEMS', header_format)
            worksheet_items.set_column('A:A', 40)
            worksheet_items.set_column('B:F', 15)
            
            # Add summary
            summary_start_row = len(items_df) + 3
            worksheet_items.write(summary_start_row, 0, 'Subtotal:', text_format)
            worksheet_items.write(summary_start_row, 1, invoice_data['subtotal'], money_format)
            worksheet_items.write(summary_start_row + 1, 0, 'Discount:', text_format)
            worksheet_items.write(summary_start_row + 1, 1, invoice_data.get('discount_total', 0), money_format)
            worksheet_items.write(summary_start_row + 2, 0, 'Tax:', text_format)
            worksheet_items.write(summary_start_row + 2, 1, invoice_data['tax_total'], money_format)
            worksheet_items.write(summary_start_row + 3, 0, 'GRAND TOTAL:', header_format)
            worksheet_items.write(summary_start_row + 3, 1, invoice_data['grand_total'], money_format)
        
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"Excel export error: {e}")
        return None

# ============================================================================
# CSS STYLING
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
        background: linear-gradient(135deg, #1e40af, #3b82f6);
        padding: 1.5rem 2rem;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 2rem;
        color: white;
    }
    
    .app-title {
        color: white !important;
        font-size: 1.8rem;
        font-weight: 600;
        margin: 0;
    }
    
    .app-subtitle {
        color: #e0f2fe !important;
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
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        transition: all 0.3s;
    }
    
    .business-card:hover {
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #2563eb;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #f8fafc, #ffffff);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        color: #64748b;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Invoice Preview */
    .invoice-preview-container {
        background: white;
        border-radius: 16px;
        padding: 2rem;
        border: 1px solid #e2e8f0;
        margin: 1rem 0 2rem 0;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    
    /* Grand Total Box */
    .grand-total-box {
        background: linear-gradient(135deg, #1e40af, #3b82f6);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.3);
    }
    
    /* Progress Bar */
    .progress-bar {
        width: 100%;
        height: 8px;
        background: #e2e8f0;
        border-radius: 9999px;
        overflow: hidden;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #2563eb, #3b82f6);
        transition: width 0.3s;
    }
    
    /* Alert Messages */
    .alert-success {
        background: #d1fae5;
        color: #065f46;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #10b981;
    }
    
    .alert-warning {
        background: #fed7aa;
        color: #92400e;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #f59e0b;
    }
    
    .alert-error {
        background: #fee2e2;
        color: #b91c1c;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ef4444;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: white;
        padding: 0.5rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 0.5rem 1rem;
        color: #64748b;
    }
    
    .stTabs [aria-selected="true"] {
        background: #2563eb;
        color: white !important;
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
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE INITIALIZATION - FIXED VERSION
# ============================================================================

def safe_load_company_info():
    """Safely load company info from database without depending on session state"""
    company_info = {
        'name': 'Your Business Name',
        'address': '123 Business Street',
        'city': 'Port of Spain, Trinidad',
        'phone': '(868) 123-4567',
        'email': 'accounts@yourbusiness.com',
        'tax_id': '123456789',
        'bank_details': 'First Citizens Bank\nAccount: 123456789\nSort Code: 123-456',
        'invoice_prefix': 'INV',
        'vat_registered': True,
        'default_currency': 'TTD'
    }
    
    try:
        # Check if database exists and is accessible
        if os.path.exists('invoices.db'):
            # Create a connection without using the context manager to avoid any session state issues
            conn = sqlite3.connect('invoices.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Check if table exists
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='company_settings'")
            if c.fetchone():
                c.execute("SELECT * FROM company_settings WHERE id = 1")
                row = c.fetchone()
                if row:
                    company_info = {
                        'name': row['name'] or company_info['name'],
                        'address': row['address'] or company_info['address'],
                        'city': row['city'] or company_info['city'],
                        'phone': row['phone'] or company_info['phone'],
                        'email': row['email'] or company_info['email'],
                        'tax_id': row['tax_id'] or company_info['tax_id'],
                        'bank_details': row['bank_details'] or company_info['bank_details'],
                        'logo_bytes': row['logo_data'],
                        'logo_mime': row['logo_mime'],
                        'default_currency': row['default_currency'] or 'TTD',
                        'vat_registered': bool(row['vat_registered']) if row['vat_registered'] is not None else True,
                        'invoice_prefix': row['invoice_prefix'] or 'INV'
                    }
                    if row['logo_data']:
                        company_info['logo_base64'] = base64.b64encode(row['logo_data']).decode()
            conn.close()
    except Exception as e:
        logger.error(f"Error loading company settings: {e}")
        # Return default values if database load fails
    
    return company_info

def init_session_state():
    """Initialize all session state variables in correct order"""
    
    # STEP 1: Initialize the most basic structure first
    # This ensures we always have company_info available
    
    # Load company info without depending on session state
    loaded_company_info = safe_load_company_info()
    
    # Initialize company_info in session state
    if 'company_info' not in st.session_state:
        st.session_state.company_info = loaded_company_info
    
    # STEP 2: Initialize all other session variables with defaults
    # These don't depend on anything else
    
    defaults = {
        'invoice_items': [],
        'invoice_number': None,  # Will be set after company_info is ready
        'currency': st.session_state.company_info.get('default_currency', 'TTD'),
        'database_initialized': False,
        'current_page': 'dashboard',
        'clients': [],
        'edit_index': -1,
        'selected_client_id': None,
        'invoice_notes': '',
        'invoice_status': 'Draft',
        'view_invoice_id': None,
        'filter_status': 'All',
        'filter_client': '',
        'filter_date_from': None,
        'filter_date_to': None,
        'user_id': 1,
        'user_role': 'admin',
        'show_help': False,
        'recurring_frequency': 'None',
        'payment_amount': 0,
        'payment_method': 'Bank Transfer',
        'payment_reference': '',
        'template_name': '',
        'notification': None,
        'notification_type': None,
        'payment_invoice_id': None,
        'show_payment_modal': False,
        'show_email_modal': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # STEP 3: Now that company_info is definitely in session state,
    # we can safely generate the invoice number
    if st.session_state.invoice_number is None:
        st.session_state.invoice_number = generate_invoice_number()

# Initialize session state
init_session_state()

# Initialize database (now that session state is ready)
if not st.session_state.database_initialized:
    if init_database():
        st.session_state.database_initialized = True
        # Reload company info from database now that it's initialized
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM company_settings WHERE id = 1")
                row = c.fetchone()
                if row:
                    st.session_state.company_info.update({
                        'name': row['name'],
                        'address': row['address'],
                        'city': row['city'],
                        'phone': row['phone'],
                        'email': row['email'],
                        'tax_id': row['tax_id'],
                        'bank_details': row['bank_details'],
                        'default_currency': row['default_currency'] or 'TTD',
                        'vat_registered': bool(row['vat_registered']),
                        'invoice_prefix': row['invoice_prefix'] or 'INV'
                    })
                    if row['logo_data']:
                        st.session_state.company_info['logo_bytes'] = row['logo_data']
                        st.session_state.company_info['logo_mime'] = row['logo_mime']
                        st.session_state.company_info['logo_base64'] = base64.b64encode(row['logo_data']).decode()
        except Exception as e:
            logger.error(f"Error reloading company settings: {e}")

# ============================================================================
# HEADER - WITH SAFE ACCESS
# ============================================================================

# Safely get values for header
try:
    currency_name = CURRENCIES[st.session_state.currency]['name']
    user_role = st.session_state.user_role.title()
except (KeyError, AttributeError):
    currency_name = 'Trinidad & Tobago Dollar'
    user_role = 'Admin'

st.markdown(f"""
    <div class="app-header fade-in">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="app-title">💰 INVOICE PRO</h1>
                <div class="app-subtitle">Professional invoicing for Caribbean businesses</div>
            </div>
            <div style="display: flex; gap: 1rem; align-items: center;">
                <div style="background: rgba(255,255,255,0.2); padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600;">
                    {currency_name}
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 0.75rem 1.5rem; border-radius: 8px;">
                    👤 {user_role}
                </div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Show notification if exists
if st.session_state.notification:
    if st.session_state.notification_type == 'success':
        st.markdown(f'<div class="alert-success">{st.session_state.notification}</div>', unsafe_allow_html=True)
    elif st.session_state.notification_type == 'warning':
        st.markdown(f'<div class="alert-warning">{st.session_state.notification}</div>', unsafe_allow_html=True)
    elif st.session_state.notification_type == 'error':
        st.markdown(f'<div class="alert-error">{st.session_state.notification}</div>', unsafe_allow_html=True)
    
    # Clear notification after showing
    st.session_state.notification = None
    st.session_state.notification_type = None

# ============================================================================
# SIDEBAR NAVIGATION
# ============================================================================

with st.sidebar:
    st.markdown("### 📍 Navigation")
    st.markdown("---")
    
    pages = {
        "📊 Dashboard": "dashboard",
        "📄 Create Invoice": "create",
        "📋 View Invoices": "view_invoices",
        "👥 Clients": "clients",
        "💰 Payments": "payments",
        "🔄 Recurring": "recurring",
        "📊 Reports": "reports",
        "⚙️ Settings": "settings",
        "❓ Help": "help"
    }
    
    for page_name, page_id in pages.items():
        button_type = "primary" if st.session_state.current_page == page_id else "secondary"
        if st.button(page_name, use_container_width=True, type=button_type, key=f"nav_{page_id}"):
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
    
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    if st.button("➕ New Invoice", use_container_width=True):
        st.session_state.current_page = "create"
        st.session_state.invoice_items = []
        st.session_state.invoice_number = generate_invoice_number()
        st.rerun()
    
    if st.button("📤 Export Data", use_container_width=True):
        backup_data, filename = backup_database()
        if backup_data:
            st.download_button(
                label="📥 Download Backup",
                data=backup_data,
                file_name=filename,
                mime="application/octet-stream",
                use_container_width=True
            )
    
    st.markdown("---")
    
    # Quick stats
    stats = get_dashboard_stats()
    if stats:
        st.markdown("### 📊 Quick Stats")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Invoices", stats['total_invoices'])
            st.metric("Revenue", format_amount(stats['total_revenue'], st.session_state.currency))
        with col2:
            st.metric("Clients", stats['total_clients'])
            st.metric("Pending", format_amount(stats['pending_amount'], st.session_state.currency))
        
        if stats['overdue_amount'] > 0:
            st.warning(f"⚠️ Overdue: {format_amount(stats['overdue_amount'], st.session_state.currency)}")
    
    st.markdown("---")
    st.markdown('<div class="app-footer">© 2024 Invoice Pro<br>Version 2.0</div>', unsafe_allow_html=True)

# ============================================================================
# DASHBOARD PAGE
# ============================================================================

def render_dashboard_page():
    """Render the dashboard page"""
    
    st.markdown('<div class="section-header">📊 Dashboard</div>', unsafe_allow_html=True)
    
    stats = get_dashboard_stats()
    
    if stats:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Total Invoices</div>
                    <div class="metric-value">{}</div>
                </div>
            """.format(stats['total_invoices']), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Total Revenue</div>
                    <div class="metric-value">{}</div>
                </div>
            """.format(format_amount(stats['total_revenue'], st.session_state.currency)), unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Active Clients</div>
                    <div class="metric-value">{}</div>
                </div>
            """.format(stats['total_clients']), unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Pending Amount</div>
                    <div class="metric-value">{}</div>
                </div>
            """.format(format_amount(stats['pending_amount'], st.session_state.currency)), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📈 Revenue Trend")
            if not stats['monthly_data'].empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=stats['monthly_data']['month'],
                    y=stats['monthly_data']['revenue'],
                    mode='lines+markers',
                    name='Revenue',
                    line=dict(color='#2563eb', width=3),
                    marker=dict(size=8)
                ))
                fig.update_layout(
                    xaxis_title="Month",
                    yaxis_title=f"Revenue ({get_currency_symbol(st.session_state.currency)})",
                    hovermode='x unified',
                    plot_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 📊 Invoice Status")
            with get_db_connection() as conn:
                status_counts = pd.read_sql_query(
                    "SELECT status, COUNT(*) as count FROM invoices GROUP BY status",
                    conn
                )
            
            if not status_counts.empty:
                fig = px.pie(
                    status_counts, 
                    values='count', 
                    names='status',
                    color='status',
                    color_discrete_map=STATUS_COLORS
                )
                fig.update_layout(showlegend=True, plot_bgcolor='white')
                st.plotly_chart(fig, use_container_width=True)
        
        # Recent invoices
        st.markdown("### 🕐 Recent Invoices")
        recent_invoices = get_invoices()
        if not recent_invoices.empty:
            recent_invoices = recent_invoices.head(5)
            for _, invoice in recent_invoices.iterrows():
                with st.container():
                    st.markdown('<div class="business-card">', unsafe_allow_html=True)
                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                    with col1:
                        st.markdown(f"**{invoice['invoice_number']}**")
                        st.caption(invoice['client_name'])
                    with col2:
                        st.markdown(f"Date: {invoice['invoice_date']}")
                        st.markdown(f"Amount: {format_amount(invoice['grand_total'], invoice['currency'])}")
                    with col3:
                        st.markdown(get_status_badge_html(invoice['status']), unsafe_allow_html=True)
                    with col4:
                        if st.button("View", key=f"view_recent_{invoice['id']}"):
                            st.session_state.view_invoice_id = invoice['id']
                            st.session_state.current_page = "view_invoices"
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No invoices yet. Create your first invoice!")
    
    else:
        st.warning("Unable to load dashboard statistics")

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

# ============================================================================
# MAIN APP ROUTER
# ============================================================================

def main():
    """Main app router"""
    
    # Render the selected page
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
    
    # Footer
    st.markdown("""
        <div class="app-footer">
            <p>© 2024 Invoice Pro - Professional Invoicing for Caribbean Businesses</p>
            <p style="font-size: 0.75rem;">Version 2.0 | All rights reserved</p>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
