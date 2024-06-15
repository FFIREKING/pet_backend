from flask import Flask, request, jsonify
import os
import uuid
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from flask_cors import CORS
from werkzeug.utils import secure_filename
from urllib.parse import urlparse, unquote
from octoai.clients.asset_orch import AssetOrchestrator, FileData
from uvicorn.middleware.asgi2 import ASGI2Middleware
import dotenv

# OCTOAI_TOKEN = os.environ.get("OCTOAI_TOKEN")
# PRINTIFY_API_KEY = os.environ.get("PRINTIFY_TOKEN")

OCTOAI_TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjNkMjMzOTQ5In0.eyJzdWIiOiJlZTZhNWJlMC1mZWE3LTRkMWUtYmFiYS04OWMxMGZiNzllNjIiLCJ0eXBlIjoidXNlckFjY2Vzc1Rva2VuIiwidGVuYW50SWQiOiI2OThmYTQ5Yy03ZGQ1LTRiMDgtOGNkOS0xZDNmMTg4OThkN2YiLCJ1c2VySWQiOiJhNWJmMDAzNS04M2JlLTRmNmQtYTliOC02MTk2OGU0ODQ4MmIiLCJyb2xlcyI6WyJGRVRDSC1ST0xFUy1CWS1BUEkiXSwicGVybWlzc2lvbnMiOlsiRkVUQ0gtUEVSTUlTU0lPTlMtQlktQVBJIl0sImF1ZCI6IjNkMjMzOTQ5LWEyZmItNGFiMC1iN2VjLTQ2ZjYyNTVjNTEwZSIsImlzcyI6Imh0dHBzOi8vaWRlbnRpdHkub2N0b21sLmFpIiwiaWF0IjoxNzEzOTY2NDg5fQ.d9juet-PZTNJzHE_G2gDYiKWAncRbh3OwyWHvqqpZrB68lfblri-1Ha9dACQ6VrShkuplqHVDuNMa7rWXiqU-_3X0hlUPTO2ef3-7h1PqFa8BV6SvF9X35_uUgmBLBJJgoKguLp2wlPjhEIqCxkFia6Stc4uTbxA0boUJCb_S-achCjTTvs65116_IBTDK6lplp0wYNFk62Ganex5XgkUU0P0gg28XAWAfjaNDvCs_-n8lFb-K6Tty-qiVLtmAquDYGJNTOGcfJquMrdWem03bYlYXwVxuTlt7_HvgPCkyVAtlQaEi6hxu4RKGOLvWqe86-w22PJbOrmNDbWoFlb_Q"
PRINTIFY_API_KEY="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzN2Q0YmQzMDM1ZmUxMWU5YTgwM2FiN2VlYjNjY2M5NyIsImp0aSI6ImMxZmY5NWFmMGYxNjM3ZjZmOWY1OTJkYzBiZWE1NzNlOGI4NWQ4ZTcxYzYzYWE0YTMxZjZkOTdkZGVmYzI2OTQ1MzIyYzVhMDMzMDBlODZiIiwiaWF0IjoxNzE2MDk3NDM4Ljg4MDQ1OCwibmJmIjoxNzE2MDk3NDM4Ljg4MDQ2LCJleHAiOjE3NDc2MzM0MzguODcyNTU3LCJzdWIiOiIxNDgxODIyMiIsInNjb3BlcyI6WyJzaG9wcy5tYW5hZ2UiLCJzaG9wcy5yZWFkIiwiY2F0YWxvZy5yZWFkIiwib3JkZXJzLnJlYWQiLCJvcmRlcnMud3JpdGUiLCJwcm9kdWN0cy5yZWFkIiwicHJvZHVjdHMud3JpdGUiLCJ3ZWJob29rcy5yZWFkIiwid2ViaG9va3Mud3JpdGUiLCJ1cGxvYWRzLnJlYWQiLCJ1cGxvYWRzLndyaXRlIiwicHJpbnRfcHJvdmlkZXJzLnJlYWQiXX0.Ab6sC44z29HhhULmkhbHxQNVaSvYjLbi0f6CeLjxJLZiUSBXwv-5YmqlOFQGT8l4GHbFLzdnhPQVouh31Eg"
app = Flask(__name__)
CORS(app, origins="*")

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", 'uploads')  # Folder where files will be saved
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}  # Allowed file extensions

PRINTIFY_BASE_URL = 'https://api.printify.com/v1'
printify_headers = {
    'Authorization': f'Bearer {PRINTIFY_API_KEY}',
    'Content-Type': 'application/json'
}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
    
    blueprint_id = data.get("blueprint_id")
    order_payload = {
        "external_id": data.get("externalId"),
        "label": "00012",
        "line_items": [
            {
                "blueprint_id": blueprint_id,
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
                            "scale": 0.5 if blueprint_id == 478 else 1,
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


@app.route('/add_name', methods=['POST'])
def add_name():
    data = request.json
    image_base64 = data.get('image')
    name = data.get('name').upper() 
    
    # Decode the base64 image
    image_data = base64.b64decode(image_base64)
    image = Image.open(io.BytesIO(image_data))

    # Crop the original image to 1024x904
    cropped_image = image.crop((0, 0, 1024, 824))

    # Create a new image for the name tag
    tag_height = 200
    tag_image = Image.new('RGB', (1024, tag_height), color='white')

    # Draw the name on the tag image
    font_size = 80
    draw = ImageDraw.Draw(tag_image)
    font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font", "WorkSans-SemiBold.ttf")
    font = ImageFont.truetype(font_path, font_size)
    text_width = draw.textlength(name, font=font)
    text_height = font_size
    text_x = (1024 - text_width) // 2
    text_y = (tag_height - text_height) // 2 - 50
    draw.text((text_x, text_y), name, fill="black", font=font)

    # Combine the cropped image and the tag image
    combined_image = Image.new('RGB', (1024, 1024))
    combined_image.paste(cropped_image, (0, 0))
    combined_image.paste(tag_image, (0, 824))

    # Save the combined image to a BytesIO object
    img_byte_arr = io.BytesIO()
    combined_image.save(img_byte_arr, format='JPEG', quality=80)
    img_byte_arr = img_byte_arr.getvalue()

    # Encode the image back to base64
    combined_image_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

    return {'image': combined_image_base64}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)