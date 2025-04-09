from picamera2 import Picamera2
import os
import time
import glob
import subprocess
import requests
import json

home_dir = os.environ['HOME']
output_dir = f"{home_dir}/projet-iot-cam"
max_images = 50  # Maximum number of images to keep

# Ensure the output directory exists
os.makedirs(output_dir, exist_ok=True)

# Function to clean up old images
def cleanup_images(directory, max_files):
    # List all jpg files in the directory
    files = glob.glob(os.path.join(directory, "test-sequence_*.jpg"))
    # Sort by modification time (oldest first)
    files.sort(key=os.path.getmtime)
    
    # Delete oldest files if we exceed the maximum
    if len(files) > max_files:
        for file_to_remove in files[:(len(files) - max_files)]:
            os.remove(file_to_remove)
            print(f"Removed old image: {file_to_remove}")

# Function to get approximate location without GPS
def get_location():
    try:
        # Try to get location using IP geolocation
        response = requests.get('https://ipinfo.io/json', timeout=5)
        if response.status_code == 200:
            data = response.json()
            location = {
                'source': 'ip',
                'ip': data.get('ip', 'unknown'),
                'city': data.get('city', 'unknown'),
                'region': data.get('region', 'unknown'),
                'country': data.get('country', 'unknown'),
                'loc': data.get('loc', 'unknown')
            }
            return location
    except Exception as e:
        print(f"IP geolocation failed: {e}")
    
    try:
        # Alternatively, try to get connected WiFi networks as a location hint
        result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return {
                'source': 'wifi',
                'ssid': result.stdout.strip()
            }
    except Exception as e:
        print(f"WiFi identification failed: {e}")
    
    return {'source': 'unknown', 'message': 'Location could not be determined'}

# Initialize camera
picam2 = Picamera2()
config = picam2.create_still_configuration()
picam2.configure(config)
picam2.start()

# Wait for camera to initialize
time.sleep(2)

i = 0
try:
    # Capture multiple images
    while True:
        # Get location information
        location = get_location()
        location_info = json.dumps(location)
        
        # Capture image
        output_path = f"{output_dir}/test-sequence_{i}.jpg"
        picam2.capture_file(output_path)
        
        # Create a metadata file for this image with location info
        metadata_path = f"{output_dir}/test-sequence_{i}.json"
        with open(metadata_path, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'datetime': time.strftime('%Y-%m-%d %H:%M:%S'),
                'image': output_path,
                'location': location
            }, f, indent=2)
        
        print(f"Captured image {i+1} with location: {location_info}")
        
        # Clean up old images periodically
        if i % 10 == 0:
            cleanup_images(output_dir, max_images)
        
        i += 1
        time.sleep(2)
except KeyboardInterrupt:
    print("Stopping capture...")
finally:
    picam2.stop()
    print("Capture complete")
    # Final cleanup
    cleanup_images(output_dir, max_images)
