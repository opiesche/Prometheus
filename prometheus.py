#!/usr/bin/python

import sys, os, datetime
from bottle import get, post, request, route, run, static_file
from bottle import Bottle




pageroot = '/var/www/Prometheus/'

app = Bottle()



@app.post('/set_target_temp')
def set_target_temp_submit():
	target_temp = request.forms.get('target_temp')
	tempInC = (float(target_temp)-32.0)/1.8
	try:
		outfile= open(pageroot+"target_temperature_value.conf", 'w')
        	outfile.write("target_temperature = " + str(tempInC) + "\n")
		outfile.close()
		return "Temperature set to "+target_temp+" degrees."
	except IOError:
		return "Can't save value. Permissions error?"


@app.get('/get_target_temp')
def get_target_temp():
        keyVal = {}
	try:
	        f = open(pageroot+"target_temperature_value.conf", "r")
		line = f.readlines()[0]
                k, v = line.strip().split('=')
                targetTemperature =   float(v.strip())
		tempInF = targetTemperature*1.8+32.0
		f.close()
		return str(tempInF)
	except IOError:
	        return "Error getting value from server"

@app.get('/get_current_temp')
def get_current_temp():
	values = {}

	f = open(pageroot+"current_values.dat", "r")
	lines = f.readlines()

	values['time'] = lines[0]

	temp = str( float(lines[1])*1.8+32.0 )
	values['currentTemp'] = temp
	
	values['pumpStatus'] = lines[2]
	values['pumpTime'] = lines[3]
	values['pumpConfidence'] = lines[4]
	values['retainment'] = lines[5]
	values['lag'] = lines[6]
	values['timeToTarget'] = lines[7]

	f.close()
	return  values



@app.get('/get_temp_history')
def get_temp_history():
	f = open(pageroot+'data/current_temperatures.csv', "r")
	lines = f.readlines()
	history = {}
	del lines[0]
	i = 0
	for line in lines:
		newline = []
		values = line.split(',')
		curtime = datetime.datetime.now()
		newline.append(curtime.year)
		newline.append(curtime.month)
		newline.append(curtime.day)
		hour, minute, second = values[0].split(':')
		newline.append(hour)
		newline.append(minute)
		newline.append(second)

		for v in range(1, len(values)):
			temp = float(values[v])
			tempInF = temp*1.8+32.0
			newline.append( str(tempInF) )

		history[i] = newline
		i += 1

	return history



@app.get('/get_pump_on_history')
def get_pump_on_history():
        f = open(pageroot+'data/current_pumpOn.csv', "r")
        lines = f.readlines()
        history = {}
        del lines[0]
        i = 0
        for line in lines:
                newline = []
                values = line.split(',')
                curtime = datetime.datetime.now()
                newline.append(curtime.year)
                newline.append(curtime.month)
                newline.append(curtime.day)
                hour, minute, second = values[0].split(':')
                newline.append(hour)
                newline.append(minute)
                newline.append(second)

		conf = values[1]
                newline.append( str(conf) )

                history[i] = newline
                i += 1

        return history





@app.post('/set_building_values')
def set_building_values():
	building_area_sqft = request.forms.get('area')
	building_height_ft = request.forms.get('height')

	with open(pageroot+"building_parms_values.py", 'w') as outfile:
		outfile.write("building_area = " + building_area_sqft + '\n')
		outfile.write("building_height = " + building_height_ft + '\n')

	outfile.close()
	return "Building parameters set."



@app.post("/set_settings")
def set_settings():
	use_temp_prediction = request.forms.get("use_temp_prediction")
	use_heatloss_prediction = request.forms.get("use_heatloss_prediction")
	learn_heating_delay = request.forms.get("learn_heating_delay")
	ignore_heatloss_spikes = request.forms.get("ignore_heatloss_spikes")

	with open(pageroot+"settings.py", 'w') as outfile:
		outfile.write("use_temp_prediction = "+use_temp_prediction+"\n")
		outfile.write("use_heatloss_prediction = "+use_heatloss_prediction+"\n")
		outfile.write("learn_heating_delay = "+learn_heating_delay+"\n")
		outfile.write("ignore_heatloss_spikes = "+ignore_heatloss_spikes+"\n")

	outfile.close()
	return "Settings saved."

		

@app.route('/<filename:path>')
def send_static(filename):
    return static_file(filename, root=pageroot)


#request_preflight_plugin = RequestPreflightPlugin( allow_origin = '*', preflight_methods = [ 'GET', 'POST', 'PUT', 'DELETE' ], ttl = 10000 )
#app.install( request_preflight_plugin )

	
run(app, host='192.168.1.50', port=8080, server='paste')  ### server='paste'

