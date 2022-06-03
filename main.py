from Etsy_API import *
from Verykship_API import *

#create object
sunmertime = Etsy_API('sunmertime')
sparkleland = Etsy_API('sparkleland')
kobj = Verykship_API()

#Retrieve Report
# sunmertime.getInventory()
# sunmertime.getSalesData()
# sunmertime.getSummary()
# sparkleland.getInventory()
# sparkleland.getSalesData()
# sparkleland.getSummary()

#Get and create Shipment
sunmertime.getNewOrders()
# kobj.createOrders('sunmertime')
# sunmertime.updateTracking()
sparkleland.getNewOrders()
# kobj.createOrders('sparkleland')
# sparkleland.updateTracking()






