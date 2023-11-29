from flask import Flask, request, render_template, redirect, url_for, session
import cv2
from pyzbar import pyzbar
import os
import pandas as pd
from io import StringIO
import re
from device_templates import DEVICE_TEMPLATES
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'Rz!BXb3KP7UZmyQeBxq9pWYmv#!H^fhHb3b'

# Ensure the uploads directory exists
uploads_dir = 'uploads'
os.makedirs(uploads_dir, exist_ok=True)

@app.route('/', methods=['GET'])
def index():
    device = session.get('recognized_device', None)
    barcode_data = session.get('barcode_data', None)
    specs_uploaded = 'specs_uploaded' in session
    # Pass the device name and barcode data to the template directly
    return render_template('index.html', device=device, specs=specs_uploaded, barcode=barcode_data)

def recognize_device(target_path):
    # Initialize SIFT detector
    sift = cv2.SIFT_create()
    flann = cv2.FlannBasedMatcher({'algorithm': 1, 'trees': 5}, {'checks': 50})
    
    # Load the target image
    target = cv2.imread(target_path, 0)
    keypoints_target, descriptors_target = sift.detectAndCompute(target, None)

    if descriptors_target is None:
        return "No descriptors found in the target image"

    device_scores = {device_name: 0 for device_name in set(DEVICE_TEMPLATES.values())}

    # Go through each template and try to find matches
    for template_path, model_name in DEVICE_TEMPLATES.items():
        template = cv2.imread(template_path, 0)
        keypoints_template, descriptors_template = sift.detectAndCompute(template, None)
        
        if descriptors_template is None:
            continue

        matches = flann.knnMatch(descriptors_template, descriptors_target, k=2)
        good_matches = [m for m, n in matches if m.distance < 0.7 * n.distance]
        device_scores[model_name] += len(good_matches)

    recognized_device = max(device_scores, key=device_scores.get)
    max_score = device_scores[recognized_device]
    MIN_MATCH_COUNT = 10
    if max_score >= MIN_MATCH_COUNT:
        session['recognized_device'] = recognized_device  # Set the session here
        print("Recognized Device:", recognized_device)  # Debug print
        return recognized_device
    else:
        return "Unknown Device"

def scan_barcode(filepath):
    image = cv2.imread(filepath)
    barcodes = pyzbar.decode(image)
    
    for barcode in barcodes:
        barcode_data = barcode.data.decode('utf-8')
        return barcode_data.upper()  # Convert barcode data to uppercase
    
    return "No barcode found"

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part"

    file = request.files['file']
    if file.filename == '':
        return "No selected file"

    if file:
        filepath = os.path.join(uploads_dir, file.filename)
        file.save(filepath)
        
        # Recognize the device
        device_name = recognize_device(filepath)
        if device_name != "Unknown Device":
            session['recognized_device'] = device_name
            #   session['specs_uploaded'] = False  # Ensure specs_uploaded is set to False

        # Scan the barcode
        barcode_data = scan_barcode(filepath)
        session['barcode_data'] = barcode_data  # Store barcode data in session
        print("Barcode Data:", barcode_data)  # Debug print

        return redirect(url_for('index'))

    return "File processed successfully"

@app.route('/upload-specs', methods=['POST'])
def upload_specs():
    if 'specs_csv' not in request.files:
        return "No CSV file part"

    specs_file = request.files['specs_csv']
    if specs_file.filename == '':
        return "No selected CSV file"

    if specs_file:
        csv_filepath = os.path.join(uploads_dir, specs_file.filename)
        specs_file.save(csv_filepath)
        print("CSV file saved to:", csv_filepath)  # Debug print: check if the file path is correct
        session['specs_uploaded'] = True  # Set to True only after specs are processed
        # Parse the CSV file to extract specs
        specs = parse_csv(csv_filepath)
        print("Parsed specs:", specs)  # Debug print: check the parsed output immediately after parsing
        model_name = session.get('recognized_device', 'Unknown Model')
        full_description = format_specs(specs, model_name)

        # Call the search_ebay function to perform eBay search and render the results
        return search_ebay(full_description)

    return "CSV file processed successfully"

def parse_csv(csv_filepath):
    # Read the CSV into a DataFrame
    data = pd.read_csv(csv_filepath, encoding='utf-8')
    print(data)  # This will print the entire DataFrame to the console
        
    # Define the patterns to search for each component
    patterns = {
        'CPU': r'I7-\d+',
        'RAM': r'DIMM\d+',
        'SSD': r'SSDR\d+',
    }
    
    # Initialize dictionary to hold the specs
    specs = {key: 'Unknown' for key in patterns}
    
    # Function to search for patterns
    def search_specs(data, pattern):
      for component in data['Description']:
        print(f"Trying to match: {component}")  # This will print each component it's trying to match
        # Ensure that the component is a string before searching
        if isinstance(component, str):
            match = re.search(pattern, component)
            if match:
                return match.group()
      return 'Unknown'  # Return 'Unknown' if no match is found or if component is not a string

    
    # Search and store the specs
    for key, pattern in patterns.items():
        specs[key] = search_specs(data, pattern)
    
    print(f"Specs after parsing: {specs}")  # This will print the specs after parsing
    return specs

def format_specs(specs, model_name):
    # Format the specs into a human-readable string
    cpu = specs.get('CPU', 'i7').replace('Processor', '').strip()
    ram = specs.get('RAM', '16GB').replace('Memory', '').strip()
    ssd = specs.get('SSD', '512GB').replace('Solid State Drive', '').strip()
    gpu = specs.get('GPU', 'GTX 1050').replace('Graphics', '').replace('NVIDIA(R)', '').replace('GeForce(R)', '').strip()

    # Combine the model and specs into one string
    full_description = f"{model_name} {cpu} {ram} RAM {ssd} SSD {gpu}"
    return full_description

def search_ebay(dynamic_content):
    # Replace spaces with plus signs for the URL
    query = dynamic_content.replace(' ', '+')
    url = f"https://www.ebay.co.uk/sch/i.html?_from=R40&_nkw={query}&_sacat=0&LH_PrefLoc=1&LH_Sold=1&LH_Complete=1&_dmd=2&rt=nc&LH_BIN=1"
    
    # Headers to mimic a browser visit
    headers = {'User-Agent': 'Mozilla/5.0'}

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find prices on the page
    prices = soup.find_all('span', {'class': 's-item__price'})
    # Extract the numeric values and convert to float
    prices = []
    for price in soup.find_all('span', {'class': 's-item__price'}):
        text = price.get_text() if price and hasattr(price, 'get_text') else ''
    if text.startswith('£'):
        try:
            # Attempt to convert the first part of the price range to float
            prices.append(float(text.split(' to ')[0].replace('£', '').replace(',', '').strip()))
        except ValueError:
            # If there's an error during conversion, we can print it or pass for now
            print(f"Could not convert {text} to float.")


    # Check if we have any prices to process
    if prices:
        min_price = min(prices)
        max_price = max(prices)
    else:
        min_price = max_price = None

    # Convert prices back to strings for display
    min_price = f"£{min_price:.2f}" if min_price is not None else 'Not available'
    max_price = f"£{max_price:.2f}" if max_price is not None else 'Not available'

    print("Prices returned after eBay search:", min_price, max_price)  # Debug print

    # Render the template with price data
    return render_template('index.html', min_price=min_price, max_price=max_price, search_string=dynamic_content)

if __name__ == '__main__':
    app.run(debug=True)
