from flask import Flask, render_template
import glob
import time
import datetime
import RPi.GPIO as GPIO  # Add GPIO import


app = Flask(__name__)

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(25, GPIO.IN)

def read_power_status():
    pin = 25
    #first, configure the pin as an input with a pull-down resistor
    #this is so that the pin is LOW when the power is on (~0.81)
    #and HIGH when the power is off (~1.5v)

    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    time.sleep(0.5)

    #now read the state of the pin

    state = GPIO.input(pin)
    print(f"Power status: {state}")
    is_on = state != GPIO.HIGH
    return {
        "text": "POWER=ON" if is_on else "POWER=OFF",
        "is_on": is_on
    }

# Function to read raw temperature data from DS18B20 sensor
def read_temp_raw():
    base_dir = '/sys/bus/w1/devices/'
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
    with open(device_file, 'r') as f:
        lines = f.readlines()
    return lines

# Function to process the raw data and extract the temperature
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
    # Configure pins as outputs
    GPIO.setup(17, GPIO.OUT)
    GPIO.setup(18, GPIO.OUT)

    # Sequence for power on
    GPIO.output(17, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(17, GPIO.LOW)

    GPIO.output(18, GPIO.HIGH)
    time.sleep(5)
    GPIO.output(18, GPIO.LOW)

# Route to display temperature
@app.route('/')
def index():
    temperature = read_temp()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    power_status = read_power_status()
    
    button_text = "Turn Off Power" if power_status["is_on"] else "Turn On Power"
    
    return render_template('index.html', 
                         temperature=temperature, 
                         current_time=current_time,
                         power_status=power_status,
                         button_text=button_text)

@app.route('/toggle_power', methods=['POST'])
def handle_power_toggle():
    power_status = read_power_status()
    if not power_status["is_on"]:
        toggle_power()
    return {"success": True}


if __name__ == '__main__':
    setup_gpio()  # Initialize GPIO
    try:
        app.run(host='0.0.0.0', port=5000)
    finally:
        GPIO.cleanup()  # Clean up GPIO on exit

