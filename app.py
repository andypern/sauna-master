from flask import Flask, render_template
import glob
import time
import datetime

app = Flask(__name__)

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

# Route to display temperature
@app.route('/')
def index():
    temperature = read_temp()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template('index.html', temperature=temperature, current_time=current_time)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
