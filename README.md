Prometheus radiant heating controller

Prerequisites:

-A Raspberry Pi with Debian from the RPi foundation's website installed

-Python-bottle and python-paste ($sudo apt-get install python-bottle python-paste)


To start the controller, cd to the Prometheus directory, then

$./prometheus-controller.py &

To start the web backend

$./prometheus.py


Alternatively, set up boot scripts to start the two automatically. Webmin is recommended for administration.

The reference system uses DS18B20 temperature sensors, the code currently supports one interior sensor connected to
GPIO3. Sensor ID is currently hardcoded, so you'll have to change it in prometheus_controller.py.
A solid state relay is connected to GPIO7 to switch the circulation pump. Any relay switching with 3.3V and able
to handle your pump's power draw should work.

To connect to the web interface, point your browser to

http://[IP]:8080/index.html#1

where [IP] is the Raspberry Pi's IP address.


