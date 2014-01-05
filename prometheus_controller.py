#!/usr/bin/python
import time
import datetime
import os
import arrayops
import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.mlab as mlab
import RPi.GPIO as GPIO

import numpy
from sensors import Sensor, VirtualSensor


gInteriorSensorArray = []
gExteriorSensor = Sensor('','Exterior')
gVirtualInteriorSensor = VirtualSensor('', 'Average Interior')
gVirtualHeatgainSensor = VirtualSensor('', 'Heat gain')

# config values
gTargetTemp = 21.5
gSampleIntervalMin = 1
gSensorErrorValue = -0.062

# from building configuration
gTotalAirWeightInPounds = 1386.0

# weights various values have for confidence score computation
gDtITWeight = 1.0
gHeatGainWeight = 0.0018
gTimeConfidenceWeight = 0.004
gDirectionWeight = 0.3



# current values
gMeasuredLagMin = 5
gMeasuredRetainmentMin = 5
gLastPumpOnTime = datetime.datetime.now()
gLastPumpOffTime = datetime.datetime.now()
gPumpConfidence = 0.0
gLastPumpOnMinutesAgo = 0
gLastPumpOffMinutesAgo = 0
gMinutesToTarget = 5.0
gDateStr = ''
gTimeStr = ''
gTotalPumpOnTime = 0.0
gTotalPumpOffTime = 0.0


############################################################################################
def read_config():
  global gInteriorSensorNames, gExteriorSensorName, gInteriorSensorNames, gExteriorSensor, gInteriorSensorArray
  
  sensor1 = Sensor('/sys/bus/w1/devices/w1_bus_master1/28-0000040df025/w1_slave', 'Living Room')
  gInteriorSensorArray.append(sensor1)
  
  gExteriorSensor = Sensor('/sys/bus/w1/devices/w1_bus_master1/28-0000040df025/w1_slave',
  'Exterior')
  
  gVirtualHeatgainSensor.currentTemp = 0.0
  

  # setup GPIO pins
  GPIO.setmode(GPIO.BCM)
  GPIO.setup(7, GPIO.OUT)


############################################################################################
# negative values mean we should turn the pump off, positive on
# the larger the magnitude of the values, the more likely a switch is needed
#
# this function builds a confidence score based on measurements and known data
# 
def getPumpConfidence():
  global gVirtualHeatgainSensor, gHeatGainWeight, gTimeConfidenceWeight, gDirectionWeight, gDtIEWeight, gMinutesToTarget, gMeasuredLagMin, gMeasuredRetainmentMin, gTargetTemp
  
  # the difference between internal and target is our first value
  print "Temperatures internal/target: " + str(gVirtualInteriorSensor.currentTemp) + ", " + str(gTargetTemp)
  tempConfidence = (gTargetTemp-gVirtualInteriorSensor.currentTemp) * gDtITWeight
  
  # next, the heat loss - the larger negative magnitude, the more likely we need heat
  heatLossConfidence = -gVirtualHeatgainSensor.currentTemp * gHeatGainWeight
  
  # this gives us a timing confidence - the closer time to target is to the measured
  # lag, the more likely we need to turn on or off the pump 
  deltaTPerMin = 0.0
  gMinutesToTarget = getTimeToTarget(deltaTPerMin)
    
  timeConfidence = 0.0
  
  if gMeasuredLagMin==0:
    gMeasuredLagMin = 5
  if gMeasuredRetainmentMin==0:
    gMeasuredRetainmentMin = 5
  
  if gVirtualInteriorSensor.currentTemp<gTargetTemp:
    timeConfidence = gMeasuredLagMin*abs(gMinutesToTarget) * gTimeConfidenceWeight
  else:
    timeConfidence = -gMeasuredRetainmentMin*abs(gMinutesToTarget) * gTimeConfidenceWeight
  
  
  
  print "Confidences - temp: " + str(tempConfidence) + ",  loss: " + str(heatLossConfidence) + ",  time: " + str(timeConfidence) + ",  direction: "
  return tempConfidence+heatLossConfidence+timeConfidence







############################################################################################
# estimates the time it will take for the internal temperature to reach target tempConfidence
# the sign shows whether we're moving towards or away from target and should be used accordingly
def getTimeToTarget(deltaTPerMin):
  global gVirtualHeatgainSensor, gTotalAirWeightInPounds, gSampleIntervalMin, gTargetTemp, gVirtualInteriorSensor
  
  # if we have no heat gain, signal no change in time to target
  if gVirtualHeatgainSensor.average==0.0:
    return 0.0
  
  deltaTInterval =  gVirtualHeatgainSensor.average / (0.24*gTotalAirWeightInPounds*(60/gSampleIntervalMin))
  deltaTPerMin = deltaTInterval/gSampleIntervalMin	### so this is per minute
  
  if deltaTPerMin == 0.0:
    return 0.0
  
  minutesToTarget = (gTargetTemp-gVirtualInteriorSensor.currentTemp) / deltaTPerMin
  print "At current heat loss, target temperature will be reached in " + str(minutesToTarget) + " minutes."
  return minutesToTarget



############################################################################################
def calcHeatLoss():
	global gVirtualInteriorSensor, gVirtualHeatgainSensor, gTotalAirWeightInPounds
	

        size = len( gVirtualInteriorSensor.tempHistory )
        
        # we can't calculate heatloss if we don't have history
	if size<2:
	  return
	  
        workingHistory = gVirtualInteriorSensor.tempHistory[:]
        arrayops.sanitize(workingHistory)
#        if len(workingHistory) >= 3:
#	  arrayops.smooth_gauss(workingHistory, 3)

	interiorDerivList = arrayops.getDeltas(workingHistory)

        #arrayops.smooth_gauss(interiorDerivList, 3)
        print "Interior temperature changes: ", str(interiorDerivList)

        scale = 60 / gSampleIntervalMin;   # 5 minute samples, but we need BTU/h
        celsiusToFahrenheit = 1.8
        averageHeatGain = 0.0

        size = len( interiorDerivList )
        for idx in range(0, size):
                dv1i = interiorDerivList[idx] * celsiusToFahrenheit
                heatloss = 0.24*gTotalAirWeightInPounds*dv1i * scale
                averageHeatGain += heatloss

        averageHeatGain /= size
        
        gVirtualHeatgainSensor.update(averageHeatGain)



############################################################################################
# estimates the lag of the heating system as well as the heat retainment. Looks for an increase
# in heat gain, or loss, respectively, over the average, based on when the pump
# was last turned on or off
#
def estimateLag():
  global gLastPumpOffMinutesAgo, gLastPumpOnMinutesAgo, gMeasuredLagMin, gMeasuredRetainmentMin, gVirtualHeatgainSensor
  
  if len(gVirtualHeatgainSensor.tempHistory) is 0:
    return
  
  #we've turned the pump on recently, so check for an increase in heat gain
  if gLastPumpOnMinutesAgo<gLastPumpOffMinutesAgo and gLastPumpOnMinutesAgo<50 and gLastPumpOnMinutesAgo>5:
    div = 1.0 / len(gVirtualHeatgainSensor.tempHistory)
    avgGain = 0.0
    for gain in gVirtualHeatgainSensor.tempHistory:
      avgGain += gain*div
    if gain > avgGain*2.0:
      MeasuredLagMin = gLastPumpOnMinutesAgo
      print "Lag estimated as " + str(gMeasuredLagMin) + " Minutes"
      return

  # or off, so check for a decrease
  if gLastPumpOffMinutesAgo<gLastPumpOnMinutesAgo and gLastPumpOffMinutesAgo<50 and gLastPumpOffMinutesAgo>5:
    div = 1.0 / len(gVirtualHeatgainSensor.tempHistory)
    avgGain = 0.0
    for gain in gVirtualHeatgainSensor.tempHistory:
      avgGain += gain*div
    if gain < avgGain/2.0:
      gMeasuredRetainmentMin = gLastPumpOffMinutesAgo
      print "Retainment estimated as " + str(gMeasuredRetainmentMin) + " Minutes"
      return
	





############################################################################################
def plotGraphs():
  global gDateStr, gTimeStr
  
  print "Plotting..." 
  print "temperatures"
  filename = "./data/" + gDateStr + "_temperatures.csv";
  r = mlab.csv2rec(filename, delimiter=',')

  fig = Figure(figsize=(6,6))
  canvas = FigureCanvas(fig)

  ax = fig.add_subplot(111)
  ax.set_title('Temperatures '+gDateStr,fontsize=14)

  ax.set_xlabel('Time',fontsize=6)
  ax.set_ylabel('Temperature (C)',fontsize=6)

  ax.grid(True,linestyle='-',color='0.75')

  # run two sanitize passes over the data
  r[r.dtype.names[1]] = arrayops.sanitize( r[r.dtype.names[1]] )
  r[r.dtype.names[2]] = arrayops.sanitize( r[r.dtype.names[2]] )


  # Generate the plot.
  ax.plot(r[r.dtype.names[0]],r[r.dtype.names[1]],color='tomato');
  ax.plot(r[r.dtype.names[0]],r[r.dtype.names[2]],color='green');

  # plot pump on times
  print "pump on"
  filename = "./data/" + gDateStr + "_pumpON.csv";
  if os.path.exists(filename):
    r = mlab.csv2rec(filename, delimiter=',')
    ax.scatter(r[r.dtype.names[0]],r[r.dtype.names[1]],color='orange');

  # plot pump off times
  print "pump off"
  filename = "./data/" + gDateStr + "_pumpOFF.csv";
  if os.path.exists(filename):
    r = mlab.csv2rec(filename, delimiter=',')
    ax.scatter(r[r.dtype.names[0]],r[r.dtype.names[1]],color='blue');


  for tick in ax.xaxis.get_major_ticks():
	  tick.label.set_fontsize(6)

  for tick in ax.yaxis.get_major_ticks():
	  tick.label.set_fontsize(6)

  ax.set_ylim(-5, 35)

  # Save the generated Plot to a PNG file.
  filename = "/var/www/Prometheus/data/"+gDateStr+"_temperatures.png"
  canvas.print_figure(filename,dpi=100)
  os.system('ln -sf '+filename+' /var/www/Prometheus/data/current_temperatures.png')
  


############################################################################################
def extract_temp(filename):
  temp = 0.0
  lines = open(filename, 'r').readlines()
  line = lines[1]
  tempstr = line[29:34]
  temp = float(tempstr)
  temp = temp/1000.0  
  return temp




############################################################################################
def measureSensors():
  global gDateStr, gTimeStr, gHistorySize, gInteriorSensorArray, gExteriorSensor, gVirtualInteriorSensor
  
  

  #new class based approach
  print "measuring sensor classes"
  avgTemp = 0.0
  for sensor in gInteriorSensorArray:
    sensor.measure()
    avgTemp += sensor.currentTemp
    
  avgTemp /= len(gInteriorSensorArray)
  gVirtualInteriorSensor.update(avgTemp)


  gExteriorSensor.measure()  

  # append the values to csv file
  headerStr = 'Time, '
  for n in gInteriorSensorArray:
    headerStr += n.name + ', '
  headerStr += gExteriorSensor.name + '\r\n'
  
  strn = gTimeStr
  for v in gInteriorSensorArray:
    strn += ', ' + str(v.currentTemp)

  strn += ', ' + str(gExteriorSensor.currentTemp)

  filename = '/var/www/Prometheus/data/' + gDateStr + '_temperatures.csv'
  if os.path.exists(filename):
    headerStr = ''
    
  print "Writing to " + filename
  with open(filename, 'a') as outfile:
    outfile.write(headerStr)
    outfile.write(strn + '\r\n')

  os.system('ln -sf '+filename+' /var/www/Prometheus/data/current_temperatures.csv')




############################################################################################
# turn on the pump, write time stamp and confidence to csv file
# note that, if the csv file is new, we write the first line twice. This is to get around
# a bug in mlab's CSV parser, that insists that it can't find valid data in this file if it
# has only one line
def pumpOn(confidence):
	global gLastPumpOffMinutesAgo, gLastPumpOnMinutesAgo, gTimeStr

  	# if pump is currently off
	if gLastPumpOffMinutesAgo<=gLastPumpOnMinutesAgo:	
		# write pump on times to csv file
		strn = gTimeStr + ', '
		strn += str(confidence)
		newfile = False
  
		filename = '/var/www/Prometheus/data/' + gDateStr + '_pumpON.csv'
		if os.path.exists(filename) is False:		### if it's a new file, insert the line twice below
			newfile = True

		with open(filename, 'a') as outfile:
			outfile.write(strn + '\r\n')
			if newfile is True:
				outfile.write(strn + '\r\n')

		os.system('ln -sf '+filename+' /var/www/Prometheus/data/current_pumpOn.csv')

      
	print "Turning pump ON with a confidence of " + str(confidence)
	#set GPIO pin 7 to high (pump on)
	GPIO.output(7, True)





  
############################################################################################
# turn off the pump, write time stamp and confidence to csv file
# note that, if the csv file is new, we write the first line twice. This is to get around
# a bug in mlab's CSV parser, that insists that it can't find valid data in this file if it
# has only one line
def pumpOff(confidence):
  global gLastPumpOffMinutesAgo, gLastPumpOnMinutesAgo, gTimeStr

  if gLastPumpOnMinutesAgo<=gLastPumpOffMinutesAgo:	
	  # write pump off times to csv file
	  strn = gTimeStr + ', '
	  strn += str(-confidence)
	  newfile = False

	  filename = '/var/www/Prometheus/data/' + gDateStr + '_pumpOFF.csv'
	  if os.path.exists(filename) is False:
	    newfile = True
  
	  with open(filename, 'a') as outfile:
	    outfile.write(strn + '\r\n')
	    if newfile is True:
	      outfile.write(strn + '\r\n')

	  os.system('ln -sf '+filename+' /var/www/Prometheus/data/current_pumpOff.csv')

	
  print "Turning pump OFF with a confidence of " + str(confidence)
  #set GPIO pin 7 to low (pump off)
  GPIO.output(7, False)


############################################################################################
def readTargetTemp():
	global gTargetTemp
	keyVal = {}
	with open("target_temperature_value.conf", "r") as f:
		line = f.readlines()[0]
		k, v = line.strip().split('=')
		gTargetTemp =  float( v.strip() )
		print "Target temperature configured as " + str(gTargetTemp)
		f.close()


	
############################################################################################
def writeValues():
  global gDateStr, gTimeStr, gSampleIntervalMin, gLastPumpOffMinutesAgo, gLastPumpOnMinutesAgo, gLastPumpOnTime, gLastPumpOffTime, gPumpConfidence, gTotalPumpOnTime, gTotalPumpOffTime

  try:
	f = open("current_values.dat", 'w')
	f.write( gTimeStr + '\n')
	f.write( str( round(gVirtualInteriorSensor.currentTemp, 1) ) + '\n' )
	if gLastPumpOnMinutesAgo < gLastPumpOffMinutesAgo:
		f.write( '1'  + '\n')
		f.write(str(gLastPumpOnTime) + '\n')
	else:
		f.write( '0'  + '\n')
		f.write(str(gLastPumpOffTime) + '\n')

	f.write(str(gPumpConfidence) + '\n')
	f.write(str( round(gMeasuredRetainmentMin, 1) ) + '\n')
	f.write(str( round(gMeasuredLagMin, 1) ) + '\n')
	f.write(str( round(gMinutesToTarget, 1) ) + '\n')
	f.write(str( round(gTotalPumpOnTime, 1) ) + '\n')
	f.write(str( round(gTotalPumpOffTime, 1) ) + '\n')

  except IOError:
	print "Error opening file current_values.dat."  



############################################################################################
def controllerLoop():
  global gDateStr, gTimeStr, gSampleIntervalMin, gLastPumpOffMinutesAgo, gLastPumpOnMinutesAgo, gLastPumpOnTime, gLastPumpOffTime, gPumpConfidence, gTotalPumpOnTime, gTotalPumpOffTime, gPumpConfidence
  
  
  print "Prometheus controller running."
  
  read_config()

  while True:
    gDateStr = str(datetime.datetime.today())[0:10]
    gTimeStr = str(datetime.datetime.now())[11:19]

    print gDateStr+" - "+gTimeStr + ": Measuring and adjusting."

    readTargetTemp()    
    measureSensors()
    calcHeatLoss()
    estimateLag()
    gPumpConfidence = getPumpConfidence()

    if gPumpConfidence>0.5:
      pumpOn(gPumpConfidence)
      gLastPumpOnTime = datetime.datetime.now()
    if gPumpConfidence<-0.5:
      pumpOff(gPumpConfidence)
      gLastPumpOffTime = datetime.datetime.now()


    # reset pump time counters at midnight
    if datetime.datetime.now().hour==0 and datetime.datetime.now().minute==0:
	gTotalPumpOffTime = 0.0
	gTotalPumpOnTime = 0.0


    pumpTime = (datetime.datetime.now() - gLastPumpOffTime)
    gLastPumpOffMinutesAgo = pumpTime.seconds/60.0
    if gLastPumpOffMinutesAgo<gLastPumpOnMinutesAgo:
	    gTotalPumpOffTime = gTotalPumpOffTime + gLastPumpOffMinutesAgo;
    pumpTime = (datetime.datetime.now() - gLastPumpOnTime) 
    gLastPumpOnMinutesAgo = pumpTime.seconds/60.0
    if gLastPumpOnMinutesAgo<gLastPumpOffMinutesAgo:
	    gTotalPumpOnTime = gTotalPumpOnTime + gLastPumpOnMinutesAgo;


    writeValues()
    #plotGraphs()
    print "Pump on time: " + str(gTotalPumpOnTime) + "; off: " + str(gTotalPumpOffTime)
    print "Sleeping."
    time.sleep(gSampleIntervalMin*60)
    
    
    
    
############################################################################################
controllerLoop()    
