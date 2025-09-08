#!/usr/bin/env python3
"""
Enhanced Cracker Shop Billing with GST and Database
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import datetime
import sqlite3
import os

class BillingDatabase:
    def __init__(self):
        self.db_url = os.environ.get('DATABASE_URL')
        self.use_postgres = bool(self.db_url)
        
        print(f"Database URL present: {bool(self.db_url)}")
        if self.db_url:
            print(f"Database URL format: {self.db_url[:20]}...")
        
        self.init_database()
    
    def get_connection(self):
        if self.use_postgres:
            try:
                import psycopg2
                # Handle different URL formats
                db_url = self.db_url
                if db_url and not db_url.startswith('postgresql://'):
                    # If it's just the host, construct proper URL
                    if '=' not in db_url and 'postgresql://' not in db_url:
                        print(f"Invalid DATABASE_URL format: {db_url}")
                        print("Falling back to SQLite...")
                        self.use_postgres = False
                        return sqlite3.connect('billing_records.db')
                
                print("Connecting to PostgreSQL...")
                return psycopg2.connect(db_url)
            except (ImportError, Exception) as e:
                print(f"PostgreSQL connection failed: {e}")
                print("Falling back to SQLite...")
                self.use_postgres = False
                return sqlite3.connect('billing_records.db')
        else:
            print("Using SQLite database...")
            return sqlite3.connect('billing_records.db')
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            # PostgreSQL schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bills (
                    id SERIAL PRIMARY KEY,
                    bill_no VARCHAR(50) UNIQUE,
                    date TIMESTAMP,
                    customer_name VARCHAR(255),
                    customer_phone VARCHAR(20),
                    customer_address TEXT,
                    subtotal DECIMAL(10,2),
                    cgst DECIMAL(10,2),
                    sgst DECIMAL(10,2),
                    total_amount DECIMAL(10,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bill_items (
                    id SERIAL PRIMARY KEY,
                    bill_no VARCHAR(50),
                    product_name VARCHAR(255),
                    quantity INTEGER,
                    unit_price DECIMAL(10,2),
                    total_price DECIMAL(10,2),
                    FOREIGN KEY (bill_no) REFERENCES bills (bill_no)
                )
            ''')
        else:
            # SQLite schema (existing)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_no TEXT UNIQUE,
                    date TEXT,
                    customer_name TEXT,
                    customer_phone TEXT,
                    customer_address TEXT,
                    subtotal REAL,
                    cgst REAL,
                    sgst REAL,
                    total_amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bill_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_no TEXT,
                    product_name TEXT,
                    quantity INTEGER,
                    unit_price REAL,
                    total_price REAL,
                    FOREIGN KEY (bill_no) REFERENCES bills (bill_no)
                )
            ''')
        
        conn.commit()
        conn.close()
    
    def save_bill(self, bill_data, items):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Insert bill
            cursor.execute('''
                INSERT INTO bills (bill_no, date, customer_name, customer_phone, 
                                 customer_address, subtotal, cgst, sgst, total_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bill_data['bill_no'], bill_data['date'], bill_data['customer_name'],
                bill_data['customer_phone'], bill_data['customer_address'],
                bill_data['subtotal'], bill_data['cgst'], bill_data['sgst'],
                bill_data['total_amount']
            ))
            
            # Insert bill items
            for item in items:
                cursor.execute('''
                    INSERT INTO bill_items (bill_no, product_name, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    bill_data['bill_no'], item['product'], item['qty'],
                    item['price'], item['price'] * item['qty']
                ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def get_bills(self, limit=50):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT bill_no, date, customer_name, customer_phone, total_amount
            FROM bills ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        
        bills = cursor.fetchall()
        conn.close()
        return bills

class CrackerBillingHandler(BaseHTTPRequestHandler):
    inventory = {
        "Kuruvi Crackers (2-3/4\")" : {"price": 5, "gst": 18},
        "Electric Sparklers (10cm)": {"price": 25, "gst": 18},
        "Electric Sparklers (15cm)": {"price": 40, "gst": 18},
        "Electric Sparklers (30cm)": {"price": 80, "gst": 18},
        "Color Sparklers": {"price": 60, "gst": 18},
        "Ground Chakkar Small": {"price": 15, "gst": 18},
        "Ground Chakkar Big": {"price": 35, "gst": 18},
        "Flower Pot Small": {"price": 20, "gst": 18},
        "Flower Pot Big": {"price": 45, "gst": 18},
        "Color Flower Pot": {"price": 65, "gst": 18},
        "Fountain Small": {"price": 80, "gst": 18},
        "Fountain Big": {"price": 150, "gst": 18},
        "Baby Rocket": {"price": 8, "gst": 18},
        "Rocket Small": {"price": 15, "gst": 18},
        "Rocket Big": {"price": 25, "gst": 18},
        "Whistling Rocket": {"price": 35, "gst": 18},
        "Lakshmi Bomb": {"price": 5, "gst": 18},
        "Atom Bomb": {"price": 12, "gst": 18},
        "Hydrogen Bomb": {"price": 25, "gst": 18},
        "Garland 100": {"price": 80, "gst": 18},
        "Garland 1000": {"price": 600, "gst": 18},
        "Family Pack": {"price": 500, "gst": 18},
        "Deluxe Gift Box": {"price": 800, "gst": 18},
        "Safety Matches": {"price": 5, "gst": 5}
    }
    
    # Shared cart across all requests
    cart = []
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    db = BillingDatabase()
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_html().encode())
        elif self.path == '/api/inventory':
            self.send_json(self.inventory)
        elif self.path == '/api/cart':
            self.send_json(self.__class__.cart)
        elif self.path == '/api/bills':
            bills = self.db.get_bills()
            self.send_json(bills)
        elif self.path == '/admin/database':
            # Simple database viewer
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            try:
                conn = self.db.get_connection()
                cursor = conn.cursor()
                
                # Get bills count
                cursor.execute('SELECT COUNT(*) FROM bills')
                bill_count = cursor.fetchone()[0]
                
                # Get recent bills
                cursor.execute('SELECT bill_no, date, customer_name, total_amount FROM bills ORDER BY created_at DESC LIMIT 10')
                bills = cursor.fetchall()
                
                html = f'''
                <html><head><title>Database Viewer</title></head>
                <body style="font-family: Arial; padding: 20px;">
                <h2>Rakshana Crackers - Database Status</h2>
                <p><strong>Total Bills:</strong> {bill_count}</p>
                <p><strong>Database Type:</strong> {"PostgreSQL" if self.db.use_postgres else "SQLite"}</p>
                <h3>Recent Bills:</h3>
                <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr><th>Bill No</th><th>Date</th><th>Customer</th><th>Amount</th></tr>
                '''
                
                for bill in bills:
                    html += f'<tr><td>{bill[0]}</td><td>{bill[1]}</td><td>{bill[2]}</td><td>₹{bill[3]}</td></tr>'
                
                html += '</table><br><a href="/">← Back to Billing</a></body></html>'
                self.wfile.write(html.encode())
                conn.close()
                
            except Exception as e:
                error_html = f'<html><body><h2>Database Error</h2><p>{str(e)}</p><a href="/">← Back</a></body></html>'
                self.wfile.write(error_html.encode())
        elif self.path.startswith('/download/'):
            # Download bill file
            filename = self.path.split('/')[-1]
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.end_headers()
                self.wfile.write(content.encode())
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'File not found')
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_json({"error": "No data received"})
                return
                
            post_data = self.rfile.read(content_length)
            if not post_data:
                self.send_json({"error": "Empty request body"})
                return
                
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Raw data: {post_data}")
                self.send_json({"error": "Invalid JSON data"})
                return
        except Exception as e:
            print(f"POST request error: {e}")
            self.send_json({"error": "Request processing failed"})
            return
        
        if self.path == '/api/add-item':
            self.__class__.cart.append(data)
            self.send_json({"success": True})
        elif self.path == '/api/generate-bill':
            bill_text, bill_data = self.generate_bill(data)
            filename = self.save_bill_file(bill_text)
            success = self.db.save_bill(bill_data, self.__class__.cart)
            self.send_json({"bill": bill_text, "filename": filename, "saved": success})
        elif self.path == '/api/clear-cart':
            self.__class__.cart = []
            self.send_json({"success": True})
        elif self.path == '/api/remove-item':
            if 0 <= data['index'] < len(self.__class__.cart):
                self.__class__.cart.pop(data['index'])
            self.send_json({"success": True})
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def calculate_gst(self, amount, gst_rate):
        gst_amount = (amount * gst_rate) / 100
        return round(gst_amount, 2)
    
    def generate_bill(self, customer_data):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bill_no = f"RPP{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        subtotal = 0
        total_cgst = 0
        total_sgst = 0
        
        # Calculate totals
        for item in self.__class__.cart:
            item_total = item["price"] * item["qty"]
            subtotal += item_total
            
            gst_rate = self.inventory[item["product"]]["gst"]
            cgst = self.calculate_gst(item_total, gst_rate / 2)
            sgst = self.calculate_gst(item_total, gst_rate / 2)
            total_cgst += cgst
            total_sgst += sgst
        
        total_amount = subtotal + total_cgst + total_sgst
        
        bill_text = f"""========================================
        RAKSHANA CRACKERS
     CRACKER SHOP BILLING SYSTEM
========================================
Bill No: {bill_no}
Date: {timestamp}
Customer: {customer_data.get('name', 'Walk-in Customer')}
Phone: {customer_data.get('phone', 'N/A')}
Address: {customer_data.get('address', 'N/A')}
GSTIN: 29ABCDE1234F1Z5 (Sample)
----------------------------------------
ITEM                QTY  RATE    AMOUNT
----------------------------------------
"""
        
        for item in self.__class__.cart:
            item_total = item["price"] * item["qty"]
            bill_text += f"{item['product'][:15]:<15} {item['qty']:>3} {item['price']:>5} {item_total:>8.2f}\n"
        
        bill_text += f"""----------------------------------------
Subtotal:                    Rs.{subtotal:>8.2f}
CGST @ 9%:                   Rs.{total_cgst:>8.2f}
SGST @ 9%:                   Rs.{total_sgst:>8.2f}
----------------------------------------
TOTAL AMOUNT:                Rs.{total_amount:>8.2f}
----------------------------------------
Thank you for shopping with us!
Visit: rakshanacrackers.com
========================================"""
        
        bill_data = {
            'bill_no': bill_no,
            'date': timestamp,
            'customer_name': customer_data.get('name', 'Walk-in Customer'),
            'customer_phone': customer_data.get('phone', 'N/A'),
            'customer_address': customer_data.get('address', 'N/A'),
            'subtotal': subtotal,
            'cgst': total_cgst,
            'sgst': total_sgst,
            'total_amount': total_amount
        }
        
        return bill_text, bill_data
    
    def save_bill_file(self, bill):
        import platform
        import pathlib
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"bill_RPP_{timestamp}.txt"
        
        # Save locally (for server)
        with open(filename, 'w') as f:
            f.write(bill)
        
        # Create desktop rakshana folder path
        try:
            system = platform.system()
            if system == "Windows":
                desktop = pathlib.Path.home() / "Desktop" / "rakshana"
            elif system == "Darwin":  # macOS
                desktop = pathlib.Path.home() / "Desktop" / "rakshana"
            else:  # Linux
                desktop = pathlib.Path.home() / "Desktop" / "rakshana"
            
            # Create directory if it doesn't exist
            desktop.mkdir(parents=True, exist_ok=True)
            
            # Save bill to desktop folder
            desktop_file = desktop / filename
            with open(desktop_file, 'w') as f:
                f.write(bill)
            
            print(f"Bill saved to: {desktop_file}")
            
        except Exception as e:
            print(f"Could not save to desktop: {e}")
        
        return filename
    
    def get_html(self):
        return '''<!DOCTYPE html>
<html>
<head>
    <title>Rakshana Crackers - GST Billing System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #ff6b6b, #ffa500);
            min-height: 100vh; padding: 20px;
        }
        .container { 
            max-width: 1400px; margin: 0 auto; background: white; 
            border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .header { 
            background: linear-gradient(45deg, #d32f2f, #ff5722);
            color: white; text-align: center; padding: 20px;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 5px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .main-content { display: flex; gap: 20px; padding: 20px; }
        .left-panel { flex: 2; }
        .right-panel { flex: 1; }
        .section { 
            background: #f8f9fa; margin: 15px 0; padding: 20px; 
            border-radius: 10px; border-left: 4px solid #d32f2f;
        }
        .section h3 { color: #d32f2f; margin-bottom: 15px; }
        select, input, button { 
            padding: 12px; margin: 8px 5px; font-size: 14px; 
            border: 2px solid #ddd; border-radius: 8px; width: calc(100% - 10px);
        }
        button { 
            background: linear-gradient(45deg, #d32f2f, #ff5722);
            color: white; border: none; cursor: pointer; font-weight: bold;
        }
        .cart-item { 
            padding: 12px; border-bottom: 1px solid #eee; 
            display: flex; justify-content: space-between; align-items: center;
        }
        .total { 
            font-weight: bold; font-size: 1.2em; color: #d32f2f; 
            text-align: center; padding: 15px; background: #fff3e0; 
            border-radius: 8px; margin: 10px 0;
        }
        #bill { 
            background: #f9f9f9; padding: 20px; white-space: pre-line; 
            font-family: 'Courier New', monospace; border-radius: 8px;
        }
        .gst-info { 
            background: #e8f5e8; padding: 10px; border-radius: 5px; 
            font-size: 0.9em; margin: 10px 0;
        }
        .bills-history { max-height: 300px; overflow-y: auto; }
        .bill-record { 
            padding: 8px; border-bottom: 1px solid #eee; 
            display: flex; justify-content: space-between;
        }
        .tabs { display: flex; margin-bottom: 20px; }
        .tab { 
            padding: 10px 20px; background: #ddd; cursor: pointer; 
            border-radius: 5px 5px 0 0; margin-right: 5px;
        }
        .tab.active { background: #d32f2f; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>RAKSHANA CRACKERS</h1>
            <p>GST Enabled Fireworks Billing System</p>
        </div>
        
        <div class="tabs">
            <div class="tab active" onclick="showTab('billing')">Billing</div>
            <div class="tab" onclick="showTab('history')">Bill History</div>
        </div>
        
        <div id="billing" class="tab-content active">
            <div class="main-content">
                <div class="left-panel">
                    <div class="section">
                        <h3>Add Product</h3>
                        <select id="product">
                            <option value="">Select Product</option>
                        </select>
                        <input type="number" id="quantity" placeholder="Quantity" min="1" value="1">
                        <button onclick="addToCart()">Add to Cart</button>
                        <div class="gst-info">
                            <strong>GST Information:</strong><br>
                            Most fireworks: 18% GST (9% CGST + 9% SGST)<br>
                            Safety items: 5% GST (2.5% CGST + 2.5% SGST)
                        </div>
                    </div>
                    
                    <div class="section">
                        <h3>Customer Details</h3>
                        <input type="text" id="customerName" placeholder="Customer Name">
                        <input type="text" id="customerPhone" placeholder="Phone Number">
                        <input type="text" id="customerAddress" placeholder="Address">
                    </div>
                </div>
                
                <div class="right-panel">
                    <div class="section">
                        <h3>Shopping Cart (<span id="cartCount">0</span> items)</h3>
                        <div id="cart"></div>
                        <div id="gstSummary"></div>
                        <button onclick="generateBill()">Generate GST Bill</button>
                        <button onclick="clearCart()" style="background: #666;">Clear Cart</button>
                    </div>
                    
                    <div class="section" id="billSection" style="display:none;">
                        <h3>Generated Bill</h3>
                        <div id="bill"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="history" class="tab-content">
            <div class="section">
                <h3>Recent Bills</h3>
                <div id="billsHistory" class="bills-history"></div>
                <button onclick="loadBillHistory()">Refresh</button>
            </div>
        </div>
    </div>

    <script>
        let inventory = {};
        let cart = [];
        
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            
            if (tabName === 'history') {
                loadBillHistory();
            }
        }
        
        async function loadInventory() {
            const response = await fetch('/api/inventory');
            inventory = await response.json();
            const select = document.getElementById('product');
            
            for (const [product, details] of Object.entries(inventory)) {
                const option = document.createElement('option');
                option.value = product;
                option.textContent = `${product} - Rs.${details.price} (GST: ${details.gst}%)`;
                select.appendChild(option);
            }
        }
        
        async function addToCart() {
            const product = document.getElementById('product').value;
            const qty = parseInt(document.getElementById('quantity').value);
            
            if (!product || !qty) {
                alert('Please select product and quantity');
                return;
            }
            
            const item = {
                product: product,
                price: inventory[product].price,
                qty: qty,
                gst: inventory[product].gst
            };
            
            await fetch('/api/add-item', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(item)
            });
            
            loadCart();
            document.getElementById('quantity').value = 1;
        }
        
        async function loadCart() {
            try {
                const response = await fetch('/api/cart');
                cart = await response.json();
                
                // Update cart counter
                document.getElementById('cartCount').textContent = cart.length;
                
                const cartDiv = document.getElementById('cart');
                const gstDiv = document.getElementById('gstSummary');
                
                if (cart.length === 0) {
                    cartDiv.innerHTML = '<p style="color: #666; font-style: italic;">Cart is empty - Add items to get started!</p>';
                    gstDiv.innerHTML = '';
                    // Also clear any bill display
                    document.getElementById('billSection').style.display = 'none';
                    return;
                }
                
                let subtotal = 0;
                let totalCGST = 0;
                let totalSGST = 0;
                let html = '';
                
                cart.forEach((item, index) => {
                const itemTotal = item.price * item.qty;
                subtotal += itemTotal;
                
                const cgst = (itemTotal * item.gst / 2) / 100;
                const sgst = (itemTotal * item.gst / 2) / 100;
                totalCGST += cgst;
                totalSGST += sgst;
                
                html += `<div class="cart-item">
                    <div>
                        <strong>${item.product}</strong><br>
                        <small>Rs.${item.price} x ${item.qty} (GST: ${item.gst}%)</small>
                    </div>
                    <div>
                        <strong>Rs.${itemTotal.toFixed(2)}</strong>
                        <button onclick="removeItem(${index})" style="background: #f44336; padding: 5px 8px; margin-left: 10px; border-radius: 4px; color: white; border: none; cursor: pointer;">Remove</button>
                    </div>
                </div>`;
            });
            
            const grandTotal = subtotal + totalCGST + totalSGST;
            
            gstDiv.innerHTML = `
                <div style="background: #f0f8ff; padding: 10px; border-radius: 5px; font-size: 0.9em;">
                    <div>Subtotal: Rs.${subtotal.toFixed(2)}</div>
                    <div>CGST: Rs.${totalCGST.toFixed(2)}</div>
                    <div>SGST: Rs.${totalSGST.toFixed(2)}</div>
                    <div class="total">Total: Rs.${grandTotal.toFixed(2)}</div>
                </div>
            `;
            
            cartDiv.innerHTML = html;
        }
        
        async function removeItem(index) {
            await fetch('/api/remove-item', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: index})
            });
            loadCart();
        }
        
        async function generateBill() {
            if (cart.length === 0) {
                alert('Cart is empty');
                return;
            }
            
            const customerData = {
                name: document.getElementById('customerName').value,
                phone: document.getElementById('customerPhone').value,
                address: document.getElementById('customerAddress').value
            };
            
            const response = await fetch('/api/generate-bill', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(customerData)
            });
            
            const result = await response.json();
            document.getElementById('bill').textContent = result.bill;
            document.getElementById('billSection').style.display = 'block';
            
            // Add download button
            const downloadBtn = document.createElement('button');
            downloadBtn.textContent = 'Download Bill';
            downloadBtn.style.marginTop = '10px';
            downloadBtn.onclick = () => {
                window.open(`/download/${result.filename}`, '_blank');
            };
            
            const billSection = document.getElementById('billSection');
            const existingBtn = billSection.querySelector('button');
            if (existingBtn) existingBtn.remove();
            billSection.appendChild(downloadBtn);
            
            if (result.saved) {
                alert(`GST Bill generated and saved as ${result.filename}\\nBill saved to desktop/rakshana folder\\nBill record saved to database`);
            } else {
                alert(`Bill generated as ${result.filename}\\nBill saved to desktop/rakshana folder\\nWarning: Could not save to database`);
            }
            
            clearCart();
            document.getElementById('customerName').value = '';
            document.getElementById('customerPhone').value = '';
            document.getElementById('customerAddress').value = '';
        }
        
        async function clearCart() {
            if (cart.length === 0) {
                alert('Cart is already empty!');
                return;
            }
            
            if (confirm('Are you sure you want to clear the cart?')) {
                try {
                    const response = await fetch('/api/clear-cart', {method: 'POST'});
                    const result = await response.json();
                    
                    if (result.success) {
                        // Clear client-side cart
                        cart = [];
                        console.log('Cart cleared on client side:', cart);
                        // Reload cart display
                        await loadCart();
                        console.log('Cart reloaded from server:', cart);
                        // Hide bill section
                        document.getElementById('billSection').style.display = 'none';
                        alert('Cart cleared successfully!');
                    } else {
                        alert('Failed to clear cart. Please try again.');
                    }
                } catch (error) {
                    console.error('Error clearing cart:', error);
                    alert('Error clearing cart. Please refresh the page.');
                }
            }
        }
        
        async function loadBillHistory() {
            const response = await fetch('/api/bills');
            const bills = await response.json();
            
            const historyDiv = document.getElementById('billsHistory');
            if (bills.length === 0) {
                historyDiv.innerHTML = '<p>No bills found</p>';
                return;
            }
            
            let html = '';
            bills.forEach(bill => {
                html += `<div class="bill-record">
                    <div>
                        <strong>${bill[0]}</strong><br>
                        <small>${bill[1]} | ${bill[2]} | ${bill[3]}</small>
                    </div>
                    <div><strong>Rs.${bill[4].toFixed(2)}</strong></div>
                </div>`;
            });
            
            historyDiv.innerHTML = html;
        }
        
        // Initialize
        loadInventory();
        loadCart();
    </script>
</body>
</html>'''

def run_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), CrackerBillingHandler)
    print("*** RAKSHANA CRACKERS GST BILLING SYSTEM ***")
    print("Features: GST Calculation + Database Storage")
    print(f"Server running on port {port}")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    run_server()
