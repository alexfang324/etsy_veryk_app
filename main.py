from Etsy_API import *
from Verykship_API import *

obj = Etsy_API('sparkleland')
obj.getInventory()
obj.getSalesData()
obj.getSummary()
receiptData = obj.getNewOrders()

# kobj = Verykship_API()
# receiptData = obj.getNewOrders()
# orderIDs,trackingData = kobj.createOrders('verykship_shipmen.xlsx')
# obj.updateTracking(receiptData,trackingData)





