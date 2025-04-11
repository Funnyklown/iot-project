from picamera2 import Picamera2
import os
import time
import glob
import subprocess
import requests
import json
import cv2
import numpy as np

# Configuration
home_dir = os.environ['HOME']
output_dir = f"/home/pi/projet-iot-cam"
max_images = 50

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Clean up old images
def cleanup_images(directory, max_files):
    files = glob.glob(os.path.join(directory, "test-sequence_*.jpg"))
    files.sort(key=os.path.getmtime)
    while len(files) > max_files:
        file_to_remove = files.pop(0)
        os.remove(file_to_remove)
        meta_file = file_to_remove.replace('.jpg', '.json')
        if os.path.exists(meta_file):
            os.remove(meta_file)
        annotated_file = file_to_remove.replace('test-sequence_', 'annotated_test-sequence_')
        if os.path.exists(annotated_file):
            os.remove(annotated_file)
        print(f"Removed old file: {file_to_remove}")

# Get approximate location
def get_location():
    try:
        response = requests.get('https://ipinfo.io/json', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                'city': data.get('city', 'unknown'),
                'region': data.get('region', 'unknown'),
                'country': data.get('country', 'unknown'),
                'loc': data.get('loc', 'unknown')
            }
    except Exception as e:
        print(f"IP geolocation failed: {e}")
    try:
        result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return {'source': 'wifi', 'ssid': result.stdout.strip()}
    except Exception:
        print("WiFi identification not available")
    return {'source': 'unknown', 'message': 'Location could not be determined'}

# Detect license plates using Docker
def detect_license_plates_docker(image_path):
    try:
        # Run OpenALPR in Docker, mounting the output_dir as /data
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{output_dir}:/data",
            "openalpr/openalpr",
            "alpr", "-c", "us", "-j", f"/data/{os.path.basename(image_path)}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"error": f"Docker ALPR failed: {result.stderr}"}
        
        # Parse JSON output from OpenALPR
        alpr_output = json.loads(result.stdout)
        plates = []
        for plate in alpr_output.get('results', []):
            plate_info = {
                'plate': plate['plate'],
                'confidence': plate['confidence'],
                'coordinates': plate['coordinates'],
                'candidates': [{'plate': c['plate'], 'confidence': c['confidence']} 
                              for c in plate['candidates']]
            }
            plates.append(plate_info)
        
        return {
            'total_plates': len(plates),
            'processing_time_ms': alpr_output.get('processing_time_ms', 0),
            'plates': plates
        }
    except Exception as e:
        return {"error": f"Failed to process image with Docker: {str(e)}"}

# Main execution
def main():
    # Check if Docker is available and image is pulled
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["docker", "pull", "openalpr/openalpr"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Docker and OpenALPR image ready")
    except subprocess.CalledProcessError as e:
        print(f"Error setting up Docker: {e}")
        return

    # Initialize camera
    try:
        picam2 = Picamera2()
        config = picam2.create_still_configuration()
        picam2.configure(config)
        picam2.start()
        time.sleep(2)  # Camera warmup
    except Exception as e:
        print(f"Failed to initialize camera: {e}")
        return

    i = 0
    try:
        while True:
            output_path = f"{output_dir}/test-sequence_{i:04d}.jpg"
            picam2.capture_file(output_path)
            location = get_location()
            alpr_results = detect_license_plates_docker(output_path)
            
            if alpr_results.get('plates'):
                print(f"Detected license plates in image {i}:")
                img = cv2.imread(output_path)
                for idx, plate in enumerate(alpr_results['plates']):
                    print(f"  {idx+1}. {plate['plate']} (confidence: {plate['confidence']:.2f}%)")
                    coords = plate['coordinates']
                    pts = np.array([[c['x'], c['y']] for c in coords], np.int32)
                    cv2.polylines(img, [pts], True, (0, 255, 0), 2)
                    cv2.putText(img, plate['plate'], (pts[0][0], pts[0][1] - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                annotated_path = f"{output_dir}/annotated_test-sequence_{i:04d}.jpg"
                cv2.imwrite(annotated_path, img)
            
            metadata_path = f"{output_dir}/test-sequence_{i:04d}.json"
            with open(metadata_path, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'datetime': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'image': output_path,
                    'location': location,
                    'alpr_results': alpr_results
                }, f, indent=2)
            
            print(f"Captured and processed image {i+1}")
#            if i % 10 == 0:
#                cleanup_images(output_dir, max_images)
            
            i += 1
            time.sleep(2)

    except KeyboardInterrupt:
        print("Stopping capture...")
    finally:
        picam2.stop()
#        cleanup_images(output_dir, max_images)
        print("Capture complete")

if __name__ == "__main__":
    main()
