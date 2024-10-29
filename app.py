from flask import Flask, request, redirect, session, jsonify, render_template
from authlib.integrations.flask_client import OAuth
from faunadb import query as q
from faunadb.client import FaunaClient
import os
import requests
import io
from PIL import Image
from rembg import remove  # for background removal

app = Flask(__name__)
app.secret_key = '81061afae17afd93f3f0fe39ff3d3b17'

# Set up OAuth for Shopify
oauth = OAuth(app)
shopify = oauth.register(
    'shopify',
    client_id='aeb49989ce766e5bba9e1e2cb855c44a',
    client_secret='81061afae17afd93f3f0fe39ff3d3b17',
    authorize_url='https://{shop}.myshopify.com/admin/oauth/authorize',
    access_token_url='https://{shop}.myshopify.com/admin/oauth/access_token',
    client_kwargs={'scope': 'read_products,write_products,read_collections'},
)

# Initialize FaunaDB client
client = FaunaClient(secret="fnAFu6PCZvAAQgZq7YTLySZ7-ZJ5gJB7t7jXqNEa")

# Helper function to add user
def add_user(store_name, access_token):
    return client.query(
        q.create(
            q.collection("Users"),
            {"data": {"store_name": store_name, "access_token": access_token}}
        )
    )

# Helper function to log background removal operations
def log_background_removal(store_name, product_id, status):
    return client.query(
        q.create(
            q.collection("Logs"),
            {"data": {"store_name": store_name, "product_id": product_id, "status": status}}
        )
    )

# Shopify app install route
@app.route('/install')
def install():
    shop = request.args.get('shop')
    return shopify.authorize_redirect(redirect_uri=url_for('auth_callback', _external=True))

# OAuth callback route
@app.route('/auth/callback')
def auth_callback():
    token = shopify.authorize_access_token()
    shop = request.args.get('shop')
    session['shopify_token'] = token
    add_user(shop, token['access_token'])
    return redirect('/dashboard')

# Dashboard route to select collection
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Fetch collections for dashboard display
@app.route('/collections')
def collections():
    shop = session['shop']
    headers = {"X-Shopify-Access-Token": session['shopify_token']['access_token']}
    response = requests.get(f'https://{shop}/admin/api/2021-07/custom_collections.json', headers=headers)
    return jsonify(response.json())

# Background removal process route
@app.route('/remove_background', methods=['POST'])
def remove_background():
    data = request.json
    collection_id = data.get("collection_id")
    shop = session['shop']
    headers = {"X-Shopify-Access-Token": session['shopify_token']['access_token']}

    # Fetch products in collection
    response = requests.get(f'https://{shop}/admin/api/2021-07/collections/{collection_id}/products.json', headers=headers)
    products = response.json().get('products', [])
    
    for product in products:
        image_url = product['image']['src']
        response = requests.get(image_url)
        image_data = io.BytesIO(response.content)
        image = Image.open(image_data)
        image = remove(image)  # Background removal with `rembg`
        
        # Save and upload new image
        new_image_io = io.BytesIO()
        image.save(new_image_io, format="PNG")
        new_image_io.seek(0)
        
        # Upload to Shopify
        requests.put(
            f'https://{shop}/admin/api/2021-07/products/{product["id"]}.json',
            headers=headers,
            json={"product": {"id": product["id"], "images": [{"attachment": new_image_io.getvalue().decode("utf-8")}]}}
        )
        # Log success or failure
        log_background_removal(shop, product["id"], "completed")

    return jsonify({'status': 'Background removal complete.'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
