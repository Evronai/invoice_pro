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
    page_title="Invoice Pro 2026",
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
    """Generate HTML for status badge with proper contrast"""
    return f'<span class="status-badge" data-status="{status}">{status}</span>'

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
# UPDATED CSS STYLING - 2026 EDITION
# ============================================================================

st.markdown("""
    <style>
    /* Global Styles - 2026 Modern Theme */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Force text contrast throughout */
    .stApp, .stApp * {
        color: #1a1a1a !important;
    }
    
    /* Input fields and text areas */
    .stTextInput input, .stTextArea textarea, .stSelectbox, .stNumberInput input {
        background-color: white !important;
        color: #1a1a1a !important;
        border: 2px solid #e0e0e0 !important;
        border-radius: 8px !important;
        padding: 0.5rem !important;
    }
    
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    /* Fix for number inputs */
    .stNumberInput input {
        background-color: white !important;
        color: #1a1a1a !important;
    }
    
    /* Fix for select boxes */
    .stSelectbox div[data-baseweb="select"] {
        background-color: white !important;
        border: 2px solid #e0e0e0 !important;
    }
    
    .stSelectbox div[data-baseweb="select"] span {
        color: #1a1a1a !important;
    }
    
    /* Headers with better contrast */
    h1, h2, h3, h4, h5, h6 {
        color: #1a1a1a !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }
    
    /* App Header - 2026 Gradient */
    .app-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2.5rem;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    .app-title {
        color: white !important;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    .app-subtitle {
        color: #a0a0ff !important;
        font-size: 1rem;
        margin-top: 0.5rem;
    }
    
    /* Cards - 2026 Neumorphism */
    .business-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 1.5rem;
        border: 1px solid rgba(255,255,255,0.2);
        margin-bottom: 1.5rem;
        box-shadow: 0 20px 40px -15px rgba(0,0,0,0.2);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .business-card:hover {
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 30px 50px -20px rgba(102, 126, 234, 0.4);
        background: white;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a1a1a !important;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 3px solid #667eea;
        position: relative;
    }
    
    .section-header::after {
        content: '';
        position: absolute;
        bottom: -3px;
        left: 0;
        width: 50px;
        height: 3px;
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 3px;
    }
    
    /* Status Badges - Enhanced */
    .status-badge {
        display: inline-block;
        padding: 0.35rem 1rem;
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .status-badge[data-status="Paid"] {
        background: linear-gradient(135deg, #10b981, #059669) !important;
        color: white !important;
        border: none;
    }
    
    .status-badge[data-status="Draft"] {
        background: linear-gradient(135deg, #94a3b8, #64748b) !important;
        color: white !important;
    }
    
    .status-badge[data-status="Sent"] {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        color: white !important;
    }
    
    .status-badge[data-status="Overdue"] {
        background: linear-gradient(135deg, #ef4444, #dc2626) !important;
        color: white !important;
    }
    
    .status-badge[data-status="Cancelled"] {
        background: linear-gradient(135deg, #6b7280, #4b5563) !important;
        color: white !important;
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #ffffff, #f8fafc);
        border-radius: 20px;
        padding: 2rem;
        border: 1px solid #e2e8f0;
        text-align: center;
        box-shadow: 0 10px 30px -15px rgba(0,0,0,0.2);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        color: #4a5568 !important;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    
    /* Invoice Preview Container */
    .invoice-preview-container {
        background: white;
        border-radius: 30px;
        padding: 3rem;
        border: 1px solid rgba(0,0,0,0.05);
        margin: 2rem 0;
        box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
    }
    
    /* Grand Total Box - 2026 Style */
    .grand-total-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 20px 40px -15px rgba(102, 126, 234, 0.5);
        animation: pulse 2s infinite;
    }
    
    .grand-total-box p {
        color: white !important;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
    
    /* Progress Bar */
    .progress-bar {
        width: 100%;
        height: 10px;
        background: #e2e8f0;
        border-radius: 10px;
        overflow: hidden;
        margin: 0.5rem 0;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 10px;
        transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    /* Alert Messages - Enhanced */
    .alert-success {
        background: linear-gradient(135deg, #d1fae5, #a7f3d0);
        color: #065f46 !important;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        border-left: 5px solid #10b981;
        font-weight: 500;
    }
    
    .alert-warning {
        background: linear-gradient(135deg, #fed7aa, #fde68a);
        color: #92400e !important;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        border-left: 5px solid #f59e0b;
    }
    
    .alert-error {
        background: linear-gradient(135deg, #fee2e2, #fecaca);
        color: #b91c1c !important;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        border-left: 5px solid #ef4444;
    }
    
    /* Tabs - 2026 Style */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
        padding: 0.75rem;
        border-radius: 50px;
        border: 1px solid rgba(255,255,255,0.2);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 40px;
        padding: 0.75rem 1.5rem;
        color: white !important;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255,255,255,0.2) !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #667eea !important;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    
    /* Buttons - 2026 Style */
    .stButton button {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.025em !important;
        transition: all 0.3s !important;
        box-shadow: 0 10px 20px -10px rgba(102, 126, 234, 0.4) !important;
    }
    
    .stButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 15px 30px -10px rgba(102, 126, 234, 0.6) !important;
    }
    
    .stButton button[kind="secondary"] {
        background: white !important;
        color: #667eea !important;
        border: 2px solid #667eea !important;
    }
    
    /* DataFrames and Tables */
    .stDataFrame {
        background: white;
        border-radius: 15px;
        padding: 1rem;
        border: 1px solid #e2e8f0;
    }
    
    .stDataFrame td, .stDataFrame th {
        color: #1a1a1a !important;
        padding: 0.75rem !important;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    
    section[data-testid="stSidebar"] * {
        color: white !important;
    }
    
    section[data-testid="stSidebar"] .stButton button {
        background: rgba(255,255,255,0.1) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        box-shadow: none !important;
    }
    
    section[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(255,255,255,0.2) !important;
    }
    
    section[data-testid="stSidebar"] .stSelectbox div {
        background: rgba(255,255,255,0.1) !important;
        color: white !important;
    }
    
    /* Footer - 2026 */
    .app-footer {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        color: #a0a0ff !important;
        font-size: 0.9rem;
        border-top: 1px solid rgba(255,255,255,0.1);
        margin-top: 4rem;
    }
    
    .app-footer p {
        color: #a0a0ff !important;
    }
    
    /* Animations */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .fade-in {
        animation: fadeInUp 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    /* Loading States */
    .stSpinner > div {
        border-color: #667eea !important;
    }
    
    /* Fix for metric text colors */
    .css-1xarl3l, .css-1xarl3l * {
        color: #1a1a1a !important;
    }
    
    /* Ensure all text in cards is visible */
    .business-card p, .business-card span, .business-card div {
        color: #1a1a1a !important;
    }
    
    .business-card .stMarkdown p {
        color: #1a1a1a !important;
    }
    
    /* Fix for status badge text */
    .status-badge, .status-badge * {
        color: white !important;
    }
    
    /* Date inputs */
    .stDateInput input {
        background: white !important;
        color: #1a1a1a !important;
        border: 2px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    
    /* Checkboxes */
    .stCheckbox label {
        color: #1a1a1a !important;
    }
    
    /* Radio buttons */
    .stRadio label {
        color: #1a1a1a !important;
    }
    
    /* Success/Info/Warning/Error messages */
    .stSuccess, .stInfo, .stWarning, .stError {
        color: #1a1a1a !important;
    }
    
    /* Update year in footer */
    .year-2026 {
        font-weight: bold;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
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
# HEADER - WITH SAFE ACCESS AND 2026 UPDATE
# ============================================================================

# Safely get values for header
try:
    currency_name = CURRENCIES[st.session_state.currency]['name']
    user_role = st.session_state.user_role.title()
except (KeyError, AttributeError):
    currency_name = 'Trinidad & Tobago Dollar'
    user_role = 'Admin'

current_year = datetime.now().year

st.markdown(f"""
    <div class="app-header fade-in">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="app-title">💰 INVOICE PRO {current_year}</h1>
                <div class="app-subtitle">Next-generation invoicing for Caribbean businesses</div>
            </div>
            <div style="display: flex; gap: 1rem; align-items: center;">
                <div style="background: rgba(255,255,255,0.2); padding: 0.75rem 1.5rem; border-radius: 12px; font-weight: 600; color: white !important;">
                    {currency_name}
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 0.75rem 1.5rem; border-radius: 12px; color: white !important;">
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
    st.markdown(f'<div class="app-footer">© {current_year} Invoice Pro<br>Version 3.0</div>', unsafe_allow_html=True)

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

# [ALL PREVIOUS PAGE RENDER FUNCTIONS REMAIN EXACTLY THE SAME - render_create_invoice_page(), 
# render_view_invoices_page(), render_invoice_detail(), render_payments_page(), render_clients_page(), 
# render_recurring_page(), render_reports_page(), render_revenue_report(), render_client_analysis(), 
# render_payment_trends(), render_tax_summary(), render_aging_report(), render_settings_page(), 
# render_help_page() - ALL REMAIN UNCHANGED]

# ============================================================================
# MAIN APP ROUTER - WITH UPDATED FOOTER
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
    
    # Footer with dynamic year
    current_year = datetime.now().year
    st.markdown(f"""
        <div class="app-footer">
            <p>© {current_year} Invoice Pro - Professional Invoicing for Caribbean Businesses</p>
            <p style="font-size: 0.75rem;">Version 3.0 | <span class="year-2026">Built for {current_year}</span> | All rights reserved</p>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
