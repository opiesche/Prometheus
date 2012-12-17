import numpy

def sanitize(myList):
        # sanitize the data (to filter out dropouts in the sensor)
        size = len( myList )
        for idx in range(0, size):
                val = myList[idx]
                prevVal = val
		nextVal = val
                if idx>0:
                        prevVal = myList[idx-1]
		if idx<size-1:
	                nextVal = myList[idx+1]

                dv1 = float(val-prevVal)
                dv2 = float(nextVal-val)
                minChange = numpy.float(5.0)
                maxVal = numpy.float(18.0)
                if numpy.abs(val)<maxVal:
                        if -dv1>minChange:
                                if dv2>minChange:
                                        myList[idx] = (prevVal+nextVal)/2.0
                                else:
                                        myList[idx] = prevVal;
                        if dv2>minChange:
                                myList[idx] = (prevVal+nextVal)/2.0

        return myList


def smooth(list):
        size = len(list)
	if size<3:
		return 

        for idx in range(1, size-1):
                d1 = (list[idx]+list[idx+1])/2
                d2 = (list[idx-1]+list[idx])/2
                list[idx] = ( (d1+d2)/2 )



def smooth_gauss(list, width):
	size = len(list)
	newlist = []
	for idx in range(0, size):
		newlist.append(0.0)

	for passIdx in range(0,5):
		for idx in range(0, size):
			left = idx-width
			right = idx+width
			left = min(max(left, 0), size)
			right = min(max(right, 0), size)
			accum = 0.0

			for n in range(left, right):
				accum += list[n]

			accum = accum / (width*2+1)
			newlist[idx] = accum

	for idx in range(0, size):
		list[idx] = newlist[idx]


def getDeltas(list):
	size = len(list)
	deltaList = []
	for idx in range(0, size-1):
		dv = list[idx+1] - list[idx]
		deltaList.append(dv)

	return deltaList

