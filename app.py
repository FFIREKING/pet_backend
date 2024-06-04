from flask import Flask, request, jsonify
import os
import uuid
import requests
from flask_cors import CORS
from werkzeug.utils import secure_filename
from urllib.parse import urlparse, unquote
from octoai.clients.asset_orch import AssetOrchestrator, FileData
from uvicorn.middleware.asgi2 import ASGI2Middleware
# import dotenv

# dotenv.load_dotenv()
OCTOAI_TOKEN = os.environ.get("OCTOAI_TOKEN")
PRINTIFY_API_KEY = os.environ.get("PRINTIFY_TOKEN")
app = Flask(__name__)
CORS(app, origins="*")
app = ASGI2Middleware(app)

UPLOAD_FOLDER = 'uploads'  # Folder where files will be saved
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}  # Allowed file extensions


# Printify API configuration
PRINTIFY_BASE_URL = 'https://api.printify.com/v1'
printify_headers = {
    'Authorization': f'Bearer {PRINTIFY_API_KEY}',
    'Content-Type': 'application/json'
}

@app.route('/', methods=['GET'])
def hello_world():
    return "Hello, World!"

@app.route('/upload', methods=['POST'])
def upload_files_from_urls():
    file_urls = request.json.get('file_urls')  # Expects a list of URLs in the JSON payload
    if not file_urls or not isinstance(file_urls, list):
        return jsonify({'error': 'No file URLs provided or incorrect format'}), 400

    results = []  # This will store the result of each file processed
    asset_orch = AssetOrchestrator(token=OCTOAI_TOKEN)
    file_paths = []  # List to store paths of files to delete after uploading
    
    for file_url in file_urls:
        # Attempt to download the file from the URL
        try:
            response = requests.get(file_url)
            response.raise_for_status()  # Raises an HTTPError if the request returned an unsuccessful status code
        except requests.exceptions.RequestException as e:
            results.append({'url': file_url, 'error': 'Failed to download file: ' + str(e)})
            continue  # Skip to the next file

        # Parse the URL to extract the filename and ensure it's safe to use as a filename
        parsed_url = urlparse(file_url)
        filename = os.path.basename(parsed_url.path)
        secure_name = secure_filename(unquote(filename))

        # Extract the file extension and check if it is allowed
        file_extension = os.path.splitext(secure_name)[1].lower().lstrip('.')
        if file_extension not in ALLOWED_EXTENSIONS:
            results.append({'url': file_url, 'error': 'File format not supported'})
            continue

        # Generate a unique filename to prevent overwriting existing files
        unique_name = str(uuid.uuid4())
        unique_filename = unique_name + '.' + file_extension
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file_paths.append(file_path)  # Add path for later deletion

        # Ensure the upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        # Save the downloaded file
        with open(file_path, 'wb') as file:
            file.write(response.content)

        # Create asset
        file_data = FileData(file_format=file_extension)
        asset = asset_orch.create(file=file_path, data=file_data, name=unique_name)
        asset_id = asset.id

        results.append({'url': file_url, 'message': 'File downloaded and saved', 'file_path': file_path, 'asset_id': asset_id})

    # Clean up: Delete all files after they have been processed
    for path in file_paths:
        os.remove(path)

    # Return the results for each file processed
    return jsonify(results), 200


@app.route('/get_store', methods=['GET'])
def get_store():
    response = requests.get(f'{PRINTIFY_BASE_URL}/shops.json', headers=printify_headers)
    if response.status_code != 200:
        return jsonify({'status': 'error', 'error': response.json()}), response.status_code
    return jsonify(response.json()), 200

@app.route('/upload_image', methods=['POST'])
def upload_image():
    data = request.json
    file_contents = data.get('contents')

    if not file_contents:
        return jsonify({'status': 'error', 'error': 'Contents not provided'}), 400

    # Generate a unique filename using uuid
    unique_filename = f"{str(uuid.uuid4())}.png"

    # Upload the base64 image to Printify
    payload = {
        "file_name": unique_filename,
        "contents": file_contents
    }
    response = requests.post(f'{PRINTIFY_BASE_URL}/uploads/images.json', headers=printify_headers, json=payload)

    if response.status_code != 200:
        return jsonify({'status': 'error', 'error': response.json()}), response.status_code

    return jsonify(response.json()), 200

@app.route('/create_order/<shop_id>', methods=['POST'])
def create_order(shop_id):
    data = request.json
    if not shop_id:
        return jsonify({'status': 'error', 'error': 'Shop ID is required'}), 400

    order_payload = {
        "external_id": data.get("externalId"),
        "label": "00012",
        "line_items": [
            {
                "blueprint_id": data.get("blueprint_id"),
                "print_provider_id": data.get("print_provider_id"),
                "variant_id": data.get("variant_id"),
                "print_areas": {
                    "front": [
                        {
                            "src": data.get("url"),
                            "height": 1024,
                            "width": 1024,
                            "x": 0.5,
                            "y": 0.5,
                            "scale": 1,
                            "angle": 0
                        }
                    ]
                },
                "quantity": 1
            }
        ],
        "shipping_method": 1,
        "is_printify_express": False,
        "is_economy_shipping": False,
        "send_shipping_notification": False,
        "address_to": {
            "first_name": data.get("firstName"),
            "last_name": data.get("lastName"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "country": data.get("country"),
            "region": data.get("region"),
            "address1": data.get("address1"),
            "address2": data.get("address2"),
            "city": data.get("city"),
            "zip": data.get("zip")
        }
    }

    response = requests.post(f'{PRINTIFY_BASE_URL}/shops/{shop_id}/orders.json', headers=printify_headers, json=order_payload)
    if response.status_code != 200:
        return jsonify({'status': 'error', 'error': response.json()}), response.status_code

    return jsonify(response.json()), 200

@app.route('/calculate_order/<shop_id>', methods=['POST'])
def calculate_order(shop_id):
    data = request.json
    if not shop_id:
        return jsonify({'status': 'error', 'error': 'Shop ID is required'}), 400

    order_payload = {
        "line_items": [
            {
                "print_provider_id": data.get("print_provider_id"),
                "blueprint_id": data.get("blueprint_id"),
                "variant_id": data.get("variant_id"),
                "quantity": 1
            }
        ],
        "address_to": {
            "first_name": data.get("firstName"),
            "last_name": data.get("lastName"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "country": data.get("country"),
            "region": data.get("region"),
            "address1": data.get("address1"),
            "address2": data.get("address2"),
            "city": data.get("city"),
            "zip": data.get("zip")
        }
    }

    response = requests.post(f'{PRINTIFY_BASE_URL}/shops/{shop_id}/orders/shipping.json', headers=printify_headers, json=order_payload)
    if response.status_code != 200:
        return jsonify({'status': 'error', 'error': response.json()}), response.status_code

    return jsonify(response.json()), 200

@app.route('/cancel_order/<shop_id>/<order_id>', methods=['POST'])
def cancel_order(shop_id, order_id):
    response = requests.post(f'{PRINTIFY_BASE_URL}/shops/{shop_id}/orders/{order_id}/cancel.json', headers=printify_headers)
    if response.status_code != 200:
        return jsonify({'status': 'error', 'error': response.json()}), response.status_code

    return jsonify(response.json()), 200

@app.route('/send_to_production/<shop_id>/<order_id>', methods=['POST'])
def send_to_production(shop_id, order_id):
    response = requests.post(f'{PRINTIFY_BASE_URL}/shops/{shop_id}/orders/{order_id}/send_to_production.json', headers=printify_headers)
    if response.status_code != 200:
        return jsonify({'status': 'error', 'error': response.json()}), response.status_code

    return jsonify(response.json()), 200

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)