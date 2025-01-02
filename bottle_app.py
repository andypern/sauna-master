from bottle import route, run, template, static_file, post, request, response, Bottle, TEMPLATE_PATH
import os
import json
import time
import datetime
import RPi.GPIO as GPIO
import glob
import threading
from datetime import datetime, timedelta

app = Bottle()

# Constants
SCHEDULE_FILE = "sauna_schedule.json"
INCREASE_TIME_MINUTES = 60  # 60 minutes when increasing time
scheduled_time = None
schedule_thread = None

# Function to save schedule to JSON
def save_schedule(scheduled_time):
    schedule_data = {
        "scheduled_time": scheduled_time.isoformat() if scheduled_time else None
    }
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule_data, f)

# Function to load schedule from JSON
def load_schedule():
    try:
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, 'r') as f:
                schedule_data = json.load(f)
                if schedule_data["scheduled_time"]:
                    return datetime.fromisoformat(schedule_data["scheduled_time"])
    except Exception as e:
        print(f"Error loading schedule: {e}")
    return None

def schedule_power_on(target_time):
    global scheduled_time
    while datetime.now(datetime.now().tzinfo) < target_time:
        time.sleep(1)
        # Check if schedule was cancelled
        current_schedule = load_schedule()
        if current_schedule != target_time:
            return
    
    if load_schedule() == target_time:  # Final check before triggering
        toggle_power()
        scheduled_time = None
        save_schedule(None)  # Clear the schedule after execution

# Modified increase_time function
def increase_sauna_time():
    power_status = read_power_status()
    if not power_status["is_on"]:
        return False
    # Here you would implement the actual time increase logic
    # For now, we'll just return True to indicate success
    return True

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(25, GPIO.IN)

def read_power_status():
    pin = 25
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    # Take samples over 3 seconds
    samples = []
    num_samples = 12  # One sample every 0.25 seconds for 3 seconds
    
    for _ in range(num_samples):
        time.sleep(0.25)
        state = GPIO.input(pin)
        samples.append(state != GPIO.HIGH)
    
    # Calculate the majority value
    is_on = sum(samples) > len(samples) / 2
    
    return {
        "text": "POWER=ON" if is_on else "POWER=OFF",
        "is_on": is_on
    }


def read_temp_raw():
    base_dir = '/sys/bus/w1/devices/'
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
    with open(device_file, 'r') as f:
        lines = f.readlines()
    return lines

def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos + 2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_f


def toggle_power():
    GPIO.setup(17, GPIO.OUT)
    GPIO.setup(18, GPIO.OUT)
    
    GPIO.output(17, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(17, GPIO.LOW)
    
    GPIO.output(18, GPIO.HIGH)
    time.sleep(5)
    GPIO.output(18, GPIO.LOW)

# Web routes
@app.route('/')
def index():
    return template('index.html')

@app.route('/simple')
def simple():
    return template('simple.html')

@app.route('/static/<filepath:path>')
def serve_static(filepath):
    return static_file(filepath, root='./static')

# API routes
@app.route('/api/status')
def get_status():
    response.content_type = 'application/json'
    power_status = read_power_status()
    current_schedule = load_schedule()
    
    try:
        temperature = read_temp()
    except Exception as e:
        print(f"Error reading temperature: {e}")
        temperature = 75.0  # fallback value
    
    return json.dumps({
        'temperature': temperature,
        'power_status': power_status,
        'power_on_duration': 1800 if power_status["is_on"] else 0,
        'time_remaining': 1800 if power_status["is_on"] else 0,
        'current_time': datetime.now().isoformat(),
        'scheduled_time': current_schedule.isoformat() if current_schedule else None
    })

@app.route('/api/power', method='POST')
def power_control():
    response.content_type = 'application/json'
    try:
        data = request.json
        if data and 'power' in data:
            current_status = read_power_status()
            if data['power'] != current_status["is_on"]:
                toggle_power()
                new_status = read_power_status()
                return json.dumps({
                    'success': True,
                    'message': f'Power turned {"on" if new_status["is_on"] else "off"} successfully'
                })
            return json.dumps({
                'success': True,
                'message': 'Power state unchanged'
            })
    except Exception as e:
        response.status = 500
        return json.dumps({'error': str(e)})

@app.route('/api/increase-time', method='POST')
def increase_time():
    response.content_type = 'application/json'
    if increase_sauna_time():
        return json.dumps({
            'success': True,
            'message': f'Time increased to {INCREASE_TIME_MINUTES} minutes'
        })
    else:
        response.status = 400
        return json.dumps({'error': 'Cannot increase time while sauna is off'})

@app.route('/api/schedule', method='POST')
def set_schedule():
    global scheduled_time, schedule_thread
    response.content_type = 'application/json'
    
    try:
        data = request.json
        if data and 'datetime' in data:
            scheduled_datetime = datetime.fromisoformat(data['datetime'].replace('Z', '+00:00'))
            
            if scheduled_datetime <= datetime.now(datetime.now().tzinfo):
                response.status = 400
                return json.dumps({'error': 'Please select a future time'})
            
            scheduled_time = scheduled_datetime
            save_schedule(scheduled_datetime)
            
            # Start new schedule thread
            if schedule_thread and schedule_thread.is_alive():
                scheduled_time = None
                save_schedule(None)
                schedule_thread.join()
            
            schedule_thread = threading.Thread(target=schedule_power_on, args=(scheduled_datetime,))
            schedule_thread.start()
            
            return json.dumps({
                'success': True,
                'message': f'Sauna scheduled for {scheduled_datetime.isoformat()}'
            })
    except Exception as e:
        response.status = 500
        return json.dumps({'error': str(e)})

@app.route('/api/schedule', method='DELETE')
def cancel_schedule():
    global scheduled_time, schedule_thread
    response.content_type = 'application/json'
    
    try:
        scheduled_time = None
        save_schedule(None)
        return json.dumps({
            'success': True,
            'message': 'Schedule cancelled successfully'
        })
    except Exception as e:
        response.status = 500
        return json.dumps({'error': str(e)})

# Template path setup
TEMPLATE_PATH.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "views")))

if __name__ == '__main__':
    try:
        # Load any existing schedule on startup
        scheduled_time = load_schedule()
        if scheduled_time and scheduled_time > datetime.now(datetime.now().tzinfo):
            schedule_thread = threading.Thread(target=schedule_power_on, args=(scheduled_time,))
            schedule_thread.start()
        
        run(app, host='0.0.0.0', port=8080, debug=True)
    finally:
        GPIO.cleanup()
        if schedule_thread and schedule_thread.is_alive():
            scheduled_time = None
            save_schedule(None)
            schedule_thread.join()
