from flask import Flask, request, jsonify
import os
import uuid
import requests
from flask_cors import CORS
from werkzeug.utils import secure_filename
from urllib.parse import urlparse, unquote
from octoai.clients.asset_orch import AssetOrchestrator, FileData
# import dotenv

# dotenv.load_dotenv()
# OCTOAI_TOKEN = os.environ.get("OCTOAI_TOKEN_pro")
OCTOAI_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjNkMjMzOTQ5In0.eyJzdWIiOiJlZTZhNWJlMC1mZWE3LTRkMWUtYmFiYS04OWMxMGZiNzllNjIiLCJ0eXBlIjoidXNlckFjY2Vzc1Rva2VuIiwidGVuYW50SWQiOiI2OThmYTQ5Yy03ZGQ1LTRiMDgtOGNkOS0xZDNmMTg4OThkN2YiLCJ1c2VySWQiOiJhNWJmMDAzNS04M2JlLTRmNmQtYTliOC02MTk2OGU0ODQ4MmIiLCJyb2xlcyI6WyJGRVRDSC1ST0xFUy1CWS1BUEkiXSwicGVybWlzc2lvbnMiOlsiRkVUQ0gtUEVSTUlTU0lPTlMtQlktQVBJIl0sImF1ZCI6IjNkMjMzOTQ5LWEyZmItNGFiMC1iN2VjLTQ2ZjYyNTVjNTEwZSIsImlzcyI6Imh0dHBzOi8vaWRlbnRpdHkub2N0b21sLmFpIiwiaWF0IjoxNzEzOTY2NDg5fQ.d9juet-PZTNJzHE_G2gDYiKWAncRbh3OwyWHvqqpZrB68lfblri-1Ha9dACQ6VrShkuplqHVDuNMa7rWXiqU-_3X0hlUPTO2ef3-7h1PqFa8BV6SvF9X35_uUgmBLBJJgoKguLp2wlPjhEIqCxkFia6Stc4uTbxA0boUJCb_S-achCjTTvs65116_IBTDK6lplp0wYNFk62Ganex5XgkUU0P0gg28XAWAfjaNDvCs_-n8lFb-K6Tty-qiVLtmAquDYGJNTOGcfJquMrdWem03bYlYXwVxuTlt7_HvgPCkyVAtlQaEi6hxu4RKGOLvWqe86-w22PJbOrmNDbWoFlb_Q"
app = Flask(__name__)
CORS(app, origins="*")

UPLOAD_FOLDER = 'uploads'  # Folder where files will be saved
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}  # Allowed file extensions

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
