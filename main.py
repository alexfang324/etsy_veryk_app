from Etsy_API import *
from Verykship_API import *

obj = Etsy_API('sunmertime')
# obj.getInventory()
# obj.getSalesData()
# obj.getSummary()
receiptData = obj.getNewOrders()

# kobj = Verykship_API()
# orderIDs,trackingData = kobj.createOrders('verykship_shipment.xlsx')
# obj.updateTracking(receiptData,trackingData)





