from flask import Flask, request, render_template, session
import cv2
from pyzbar import pyzbar
import os
import numpy as np
import pandas as pd
import re
from device_templates import DEVICE_TEMPLATES

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Ensure the uploads directory exists
uploads_dir = 'uploads'  # Define the uploads directory
os.makedirs(uploads_dir, exist_ok=True)  # Create the directory if it doesn't exist


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

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
        return recognized_device
    else:
        return "Unknown Device"

def scan_barcode(filepath):
    image = cv2.imread(filepath)
    barcodes = pyzbar.decode(image)
    
    for barcode in barcodes:
        barcode_data = barcode.data.decode('utf-8')
        return barcode_data
    
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

        # Now read the saved CSV file
        data = pd.read_csv(filepath)
        def parse_dell_csv(data):
    # Creating a DataFrame from the CSV data
    data = pd.read_csv(StringIO(data), sep='\t')

    # Initialize dictionary to hold the specs
    specs = {
        'CPU': 'Unknown',
        'RAM': 'Unknown',
        'GPU': 'Unknown',
        'Storage': 'Unknown',
        'Model': 'Unknown'
    }

    # Iterate over the rows to find relevant specs
    for index, row in data.iterrows():
        description = row['Description']
        
        # Extracting CPU information
        if 'Processor' in description:
            specs['CPU'] = description.split(',')[1] if ',' in description else description
        
        # Extracting RAM information
        elif 'DIMM' in description or 'Memory' in description:
            specs['RAM'] = description.split(',')[1] if ',' in description else description
        
        # Extracting GPU information
        elif 'Graphics' in description or 'NVIDIA' in description:
            specs['GPU'] = description.split(',')[1] if ',' in description else description
        
        # Extracting Storage information
        elif 'SSD' in description or 'HDD' in description:
            specs['Storage'] = description.split(',')[1] if ',' in description else description
        
        # Extracting Model information
        if row['Component'].startswith('Y3J2X'):
            specs['Model'] = 'Dell XPS 15 9560'

    return specs

specs = parse_dell_csv(csv_data)

print(f"Model: {specs['Model']}")
print(f"CPU: {specs['CPU']}")
print(f"RAM: {specs['RAM']}")
print(f"GPU: {specs['GPU']}")
print(f"Storage: {specs['Storage']}")

        return "File processed successfully"

@app.route('/upload-specs', methods=['POST'])
def upload_specs():
    if 'specs_csv' not in request.files:
        return "No CSV file part"
    
    specs_file = request.files['specs_csv']
    if specs_file.filename == '':
        return "No selected CSV file"
    
    if specs_file:
        csv_filepath = os.path.join('uploads', specs_file.filename)
        specs_file.save(csv_filepath)
        
        # Load the CSV data into a DataFrame
        data = pd.read_csv(csv_filepath, delimiter='\t', encoding='utf-8', header=None, names=['Component', 'Part Number', 'Description', 'Quantity'])
        print(data.columns) 
        
        # Extract the model information
        model_info = extract_model_from_component(data)

        # Generate the specification description
        description = create_description_from_specs(csv_filepath, model_info)
        
        return f"Specifications for {model_info}: {description}"

def extract_model_from_component(dataframe):
    # Pattern to identify the model (e.g., "9560,XPS15")
    model_pattern = re.compile(r'\d+,\w+')
    
    for component in dataframe['Component']:  # Corrected line
        if 'XPS' in component:
            # Find all matches of the model pattern
            matches = model_pattern.findall(component)
            if matches:
                # Assuming the first match is the model
                return matches[0].replace(',', ' ')
    return "Model not found"

def create_description_from_specs(csv_filepath, model_code):
    data = pd.read_csv(csv_filepath)
    
    print("Data loaded from CSV:")  # Debugging line
    print(data.head())  # Show the first few rows of the DataFrame

    model_data = data[data['Part Number'].str.contains(model_code, na=False)]

    print(f"Filtered data for model code {model_code}:")  # Debugging line
    print(model_data)  # Show the filtered DataFrame

    if model_data.empty:
        return "Specifications not found for the given model code."

    # Extract the relevant specs
    cpu = model_data[model_data['Description'].str.contains('Processor', na=False)]['Description'].iloc[0]
    ram = model_data[model_data['Description'].str.contains('RAM', na=False)]['Description'].iloc[0]
    ssd = model_data[model_data['Description'].str.contains('Solid State Drive', na=False)]['Description'].iloc[0]
    gpu = model_data[model_data['Description'].str.contains('NVIDIA', na=False)]['Description'].iloc[0]
    
    description = f"{cpu}, {ram}, {ssd}, {gpu}"
    return description

if __name__ == '__main__':
    app.run(debug=True)
