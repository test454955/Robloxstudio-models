import http.server
import socketserver
import webbrowser
import os
import json
from urllib.parse import urlparse, parse_qs
import uuid
import shutil
from datetime import datetime

PORT = 8000
PRODUCTS_FILE = "products.json"
UPLOAD_FOLDER = "uploads"
ADMIN_PASSWORD = "Adminmegood"  # Change this in production
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def _set_headers(self, content_type='text/html'):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_GET(self):
        try:
            url = urlparse(self.path)
            
            if url.path == '/':
                self.serve_file('index.html')
            elif url.path == '/admin':
                self.serve_file('admin_login.html')
            elif url.path == '/admin_panel':
                self.serve_file('admin_panel.html')
            elif url.path == '/get_products':
                self.serve_products()
            elif url.path.startswith('/download/'):
                self.serve_download(url.path[10:])
            elif url.path.startswith('/uploads/'):
                self.serve_uploaded_file(url.path)
            elif url.path == '/get_product_details':
                self.serve_product_details(parse_qs(url.query))
            else:
                super().do_GET()
        except Exception as e:
            self.send_error(500, f"Server Error: {str(e)}")

    def do_POST(self):
        try:
            url = urlparse(self.path)
            
            if url.path == '/create_product':
                self.handle_create_product()
            elif url.path == '/update_product':
                self.handle_update_product()
            elif url.path == '/delete_product':
                self.handle_delete_product()
            elif url.path == '/upload_image':
                self.handle_upload('image')
            elif url.path == '/upload_file':
                self.handle_upload('file')
            elif url.path == '/add_rating':
                self.handle_add_rating()
            elif url.path == '/add_comment':
                self.handle_add_comment()
            elif url.path == '/verify_admin':
                self.handle_verify_admin()
            else:
                self.send_error(404, "Not Found")
        except Exception as e:
            self.send_error(500, f"Server Error: {str(e)}")

    def serve_file(self, filename):
        if os.path.exists(filename):
            self._set_headers()
            with open(filename, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
        else:
            self.send_error(404, "File not found")

    def serve_products(self):
        products = self._load_products()
        query = parse_qs(urlparse(self.path).query)
        
        # Apply filters if provided
        if 'search' in query:
            search_term = query['search'][0].lower()
            products = [p for p in products if search_term in p['name'].lower() or 
                       search_term in p['category'].lower()]
        
        if 'category' in query:
            category = query['category'][0]
            products = [p for p in products if p['category'] == category]
        
        if 'sort' in query:
            sort_type = query['sort'][0]
            if sort_type == 'newest':
                products.sort(key=lambda x: x['created_at'], reverse=True)
            elif sort_type == 'popular':
                products.sort(key=lambda x: x['download_count'], reverse=True)
            elif sort_type == 'rating':
                products.sort(key=lambda x: x.get('average_rating', 0), reverse=True)
            elif sort_type == 'featured':
                products.sort(key=lambda x: x.get('is_featured', False), reverse=True)
        
        self._set_headers('application/json')
        self.wfile.write(json.dumps(products).encode())

    def serve_product_details(self, query_params):
        products = self._load_products()
        product_id = query_params.get('id', [None])[0]
        
        if product_id:
            product = next((p for p in products if p['id'] == product_id), None)
            if product:
                self._set_headers('application/json')
                self.wfile.write(json.dumps(product).encode())
                return
        
        self.send_error(404, "Product not found")

    def serve_download(self, file_id):
        products = self._load_products()
        product = next((p for p in products if p['file_id'] == file_id), None)
        
        if product:
            # Update download count
            product['download_count'] = product.get('download_count', 0) + 1
            self._save_products(products)
            
            if os.path.exists(product['file_path']):
                self.send_response(200)
                self.send_header('Content-type', 'application/octet-stream')
                self.send_header('Content-Disposition', 
                               f'attachment; filename="{product["original_file_name"]}"')
                self.send_header('Content-Length', os.path.getsize(product['file_path']))
                self.end_headers()
                
                with open(product['file_path'], 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
                return
        
        self.send_error(404, "File not found")

    def serve_uploaded_file(self, path):
        filepath = path[1:]  # Remove leading slash
        if os.path.exists(filepath):
            ext = os.path.splitext(filepath)[1].lower()
            content_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.rbxl': 'application/octet-stream'
            }.get(ext, 'application/octet-stream')
            
            self._set_headers(content_type)
            with open(filepath, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
        else:
            self.send_error(404, "File not found")

    def handle_create_product(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        product_data = json.loads(post_data)
        
        products = self._load_products()
        product_id = str(uuid.uuid4())
        
        new_product = {
            "id": product_id,
            "name": product_data['name'],
            "description": product_data.get('description', ''),
            "category": product_data.get('category', 'Other'),
            "image": product_data['image'],
            "file_id": str(uuid.uuid4()),
            "file_path": product_data['file_path'],
            "original_file_name": product_data['original_file_name'],
            "file_type": product_data.get('file_type', 'application/octet-stream'),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "download_count": 0,
            "is_featured": product_data.get('is_featured', False),
            "versions": [{
                "version": "1.0",
                "release_date": datetime.now().isoformat(),
                "changelog": "Initial release",
                "file_path": product_data['file_path'],
                "file_id": str(uuid.uuid4())
            }],
            "ratings": [],
            "comments": []
        }
        
        products.append(new_product)
        self._save_products(products)
        
        self._set_headers('application/json')
        self.wfile.write(json.dumps({
            "status": "success",
            "redirect": "/?created=true"
        }).encode())

    def handle_update_product(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        update_data = json.loads(post_data)
        
        products = self._load_products()
        product = next((p for p in products if p['id'] == update_data['id']), None)
        
        if product:
            # Update basic info
            product['name'] = update_data.get('name', product['name'])
            product['description'] = update_data.get('description', product['description'])
            product['category'] = update_data.get('category', product['category'])
            product['is_featured'] = update_data.get('is_featured', product.get('is_featured', False))
            product['updated_at'] = datetime.now().isoformat()
            
            # Update image if provided
            if 'image' in update_data:
                product['image'] = update_data['image']
            
            # Add new version if file is updated
            if 'file_path' in update_data:
                product['versions'].insert(0, {
                    "version": update_data.get('version', f"{float(product['versions'][0]['version']) + 0.1}"),
                    "release_date": datetime.now().isoformat(),
                    "changelog": update_data.get('changelog', 'No changelog provided'),
                    "file_path": update_data['file_path'],
                    "file_id": str(uuid.uuid4())
                })
                product['file_path'] = update_data['file_path']
                product['original_file_name'] = update_data.get('original_file_name', product['original_file_name'])
            
            self._save_products(products)
            
            self._set_headers('application/json')
            self.wfile.write(json.dumps({"status": "success"}).encode())
        else:
            self.send_error(404, "Product not found")

    def handle_delete_product(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        products = self._load_products()
        products = [p for p in products if p['id'] != data['id']]
        
        self._save_products(products)
        
        self._set_headers('application/json')
        self.wfile.write(json.dumps({"status": "success"}).encode())

    def handle_add_rating(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        rating_data = json.loads(post_data)
        
        products = self._load_products()
        product = next((p for p in products if p['id'] == rating_data['product_id']), None)
        
        if product:
            # Add or update rating
            existing_rating = next((r for r in product['ratings'] if r['user_id'] == rating_data['user_id']), None)
            if existing_rating:
                existing_rating['rating'] = rating_data['rating']
            else:
                product['ratings'].append({
                    "user_id": rating_data['user_id'],
                    "rating": rating_data['rating'],
                    "date": datetime.now().isoformat()
                })
            
            # Calculate average rating
            if product['ratings']:
                product['average_rating'] = sum(r['rating'] for r in product['ratings']) / len(product['ratings'])
            
            self._save_products(products)
            
            self._set_headers('application/json')
            self.wfile.write(json.dumps({"status": "success"}).encode())
        else:
            self.send_error(404, "Product not found")

    def handle_add_comment(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        comment_data = json.loads(post_data)
        
        products = self._load_products()
        product = next((p for p in products if p['id'] == comment_data['product_id']), None)
        
        if product:
            product['comments'].append({
                "user_id": comment_data['user_id'],
                "user_name": comment_data['user_name'],
                "text": comment_data['text'],
                "date": datetime.now().isoformat()
            })
            
            self._save_products(products)
            
            self._set_headers('application/json')
            self.wfile.write(json.dumps({"status": "success"}).encode())
        else:
            self.send_error(404, "Product not found")

    def handle_verify_admin(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        if data.get('password') == ADMIN_PASSWORD:
            self._set_headers('application/json')
            self.wfile.write(json.dumps({
                "status": "success",
                "redirect": "/admin_panel"
            }).encode())
        else:
            self.send_error(401, "Unauthorized")

    def handle_upload(self, file_type):
        content_type = self.headers['Content-Type']
        if not content_type.startswith('multipart/form-data'):
            self.send_error(400, "Bad Request: Invalid content type")
            return
            
        content_length = int(self.headers['Content-Length'])
        boundary = content_type.split("=")[1].encode()
        data = self.rfile.read(content_length)
        
        for part in data.split(boundary):
            if b'filename="' in part:
                header, file_data = part.split(b'\r\n\r\n', 1)
                filename = header.split(b'filename="')[1].split(b'"')[0].decode()
                file_data = file_data.rstrip(b'\r\n--')
                
                # Validate Roblox Place file
                if file_type == 'file' and not filename.lower().endswith('.rbxl'):
                    self.send_error(400, "Bad Request: Only .rbxl files are allowed")
                    return
                
                unique_filename = f"{uuid.uuid4()}_{filename}"
                filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                
                with open(filepath, 'wb') as f:
                    f.write(file_data)
                
                self._set_headers('application/json')
                self.wfile.write(json.dumps({
                    "status": "success",
                    "filename": unique_filename,
                    "filepath": filepath,
                    "original_filename": filename,
                    "file_type": 'application/octet-stream'
                }).encode())
                return
        
        self.send_error(400, "Bad Request: No file uploaded")

    def _load_products(self):
        try:
            if os.path.exists(PRODUCTS_FILE):
                with open(PRODUCTS_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return []

    def _save_products(self, products):
        with open(PRODUCTS_FILE, 'w') as f:
            json.dump(products, f, indent=2)

with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    print(f"Roblox Studio Giveaways running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop the server")
    webbrowser.open_new_tab(f"http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped successfully")