### sensors.py
import os

gSensorErrorValue = -0.062
gSensorHistorySize = 10

class Sensor:
  def __init__(self, sensorPath, sensorName):
    self.currentTemp = 20.0
    self.tempHistory = []
    self.name = sensorName
    self.path = sensorPath
    self.average = 0.0

  def extract_temp(self, filename):
    temp = 0.0
    lines = open(filename, 'r').readlines()
    if len(lines) is 0:
        return 20.0
    line = lines[1]
    tempstr = line[29:34]
    temp = float(tempstr)
    temp = temp/1000.0  
    return temp


  def calcAverage(self):
        self.average = 0.0
        for t in self.tempHistory:
                self.average += t
        self.average /= len(self.tempHistory)

  def measure(self):
    global gSensorErrorValue, gSensorHistorySize
    
    os.system("cat " + self.path + " > /tmp/interiortemp.txt")
    temp = self.extract_temp("/tmp/interiortemp.txt")
    if temp==gSensorErrorValue and abs(temp-self.currentTemp)>6:
      temp = self.currentTemp

    self.currentTemp = temp
      
    # remember temperatures in a buffer of up to gHistorySize
    if len(self.tempHistory) >= gSensorHistorySize:
      for i in range(1, gSensorHistorySize):
	self.tempHistory[i-1] = self.tempHistory[i]
      self.tempHistory[gSensorHistorySize-1] = temp
    else:
      self.tempHistory.append(temp)

    self.calcAverage()
    
    print 'Sensor ' + self.name + ': '+ str(temp)
    print '      history: '+ str(self.tempHistory) + '\r\n'


    

class VirtualSensor(Sensor):
  
  def update(self, temp):
    self.currentTemp = temp
    
    # remember temperatures in a buffer of up to gHistorySize
    if len(self.tempHistory) >= gSensorHistorySize:
      for i in range(1, gSensorHistorySize):
	self.tempHistory[i-1] = self.tempHistory[i]
      self.tempHistory[gSensorHistorySize-1] = temp
    else:
      self.tempHistory.append(temp)
    
    self.calcAverage()

    print 'Sensor ' + self.name + ': '+ str(temp)
    print '      history: '+ str(self.tempHistory) + '\r\n'
    
