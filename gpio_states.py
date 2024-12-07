import RPi.GPIO as GPIO

# List of GPIO pins to configure
PINS = [17, 18, 25]

# Setup GPIO
GPIO.setmode(GPIO.BCM)  # Use Broadcom (BCM) pin numbering




print("Pre-script Pin States:")
for pin in PINS:
    GPIO.setup(pin, GPIO.IN)
    state = GPIO.input(pin)  # Read pin state
    print(f"GPIO {pin}: {'HIGH' if state == GPIO.HIGH else 'LOW'}")



# Configure each pin as input with pull-down resistor
for pin in PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Read and print the state of each pin
try:
    print("post script Pin States:")
    for pin in PINS:
        state = GPIO.input(pin)  # Read pin state
        print(f"GPIO {pin}: {'HIGH' if state == GPIO.HIGH else 'LOW'}")
finally:
    # Clean up GPIO on exit
    GPIO.cleanup()