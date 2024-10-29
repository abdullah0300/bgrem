from flask import Flask, request, redirect, session, jsonify
from flask_oauthlib.client import OAuth
from faunadb import FaunaClient
import requests
import io
from PIL import Image
from rembg import remove  # for background removal

app = Flask(__name__)
app.secret_key = 'your-secret-key'
oauth = OAuth(app)
client = FaunaClient(secret='fnAFu6PCZvAAQgZq7YTLySZ7-ZJ5gJB7t7jXqNEa')

# Shopify OAuth setup
shopify = oauth.remote_app(
    'shopify',
    consumer_key='aeb49989ce766e5bba9e1e2cb855c44a',
    consumer_secret='81061afae17afd93f3f0fe39ff3d3b17',
    request_token_params={
        'scope': 'read_products,write_products,read_collections',
    },
    base_url='https://{shop}.myshopify.com/admin/api/2021-07',
    request_token_url=None,
    access_token_url='/oauth/access_token',
    authorize_url='https://{shop}.myshopify.com/admin/oauth/authorize'
)

@app.route('/install')
def install():
    shop = request.args.get('shop')
    return shopify.authorize(callback=f'https://your-app-url/render.com/auth/callback')

@app.route('/auth/callback')
def auth_callback():
    response = shopify.authorized_response()
    if response is None or response.get('access_token') is None:
        return 'Access Denied'
    session['shopify_token'] = (response['access_token'], '')
    return redirect('/dashboard')

# Fetch collections for selection in dashboard
@app.route('/collections')
def collections():
    shop = session['shop']
    headers = {"X-Shopify-Access-Token": session['shopify_token'][0]}
    response = requests.get(f'https://{shop}/admin/api/2021-07/custom_collections.json', headers=headers)
    return jsonify(response.json())

# Remove background process endpoint
@app.route('/remove_background', methods=['POST'])
def remove_background():
    data = request.json
    collection_id = data.get("collection_id")
    # Fetch product images based on collection
    # Loop through each image, remove background, update the image on Shopify
    for product in products:
        image_url = product['image']['src']
        response = requests.get(image_url)
        image_data = io.BytesIO(response.content)
        image = Image.open(image_data)
        image = remove(image)  # Background removal with `rembg`
        
        # Save and upload the new image
        new_image_io = io.BytesIO()
        image.save(new_image_io, format="PNG")
        new_image_io.seek(0)

        # Upload to Shopify
        response = requests.put(
            f'https://{shop}/admin/api/2021-07/products/{product["id"]}.json',
            headers=headers,
            json={"product": {"id": product["id"], "images": [{"attachment": new_image_io.getvalue().decode("utf-8")}]}}
        )

    return jsonify({'status': 'Background removal complete.'})
