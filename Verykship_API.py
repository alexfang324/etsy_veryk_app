import requests
import base64
import hashlib #used for SHA256 encoding
import urllib
import hmac
import time
import json
import sys
from DataProcessor import *

class Verykship_API:
    def __init__(self):
        filename = 'credential/veryk.csv' #name of the credential file
        if not os.path.isfile(filename):
            sys.exit('Either the filename veryk.csv is mistyped or it is not'\
                     'in the "credential" folder')      
        #retrieve user credentials
        creDict={}
        with open(filename,'r') as f:
            lines = f.read().split('\n') #create a list of rows of the file data
            for line in lines:
                if not line == '':
                    column = line.split(',')
                    creDict[column[0].strip()]=column[1].strip()           
            #store credential to class instance
            self.__appID = creDict["appID"]
            self.__secret = creDict["secret"]

###############################################################################         
    def generateSignature(self, action):
        action = urllib.parse.quote_plus(action) #url encode the action
        timestamp = int(time.time()) #get unix timestamp
        message = 'action={}&id={}&timestamp={}'.format(action, self.__appID, timestamp)

        signature = hmac.new(
            self.__secret.encode('utf-8'),
            msg = message.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        signature = base64.b64encode(signature) #encode with base64      
        return timestamp, signature

###############################################################################             
    #Takes in a row of order data as specified in the verykship shipment upload
    #template and returns a JSON of available service.
    def getQuote(self,order):
        action="shipment/quote" #action specified in veryk API  
        timestamp, signature = self.generateSignature(action)
        
        #Prepare JSON for query
        query = {"initiation":{"region_id":order[12],"postalcode":order[13]},
                 "destination":{"region_id":order[23],"postalcode":order[24]},
                 "package":{"type":order[25],
                             "packages":[{"weight":order[26]}]}}
        query = json.dumps(query) #convert dictionary to json
       
        endpoint = "https://www.verykship.com/api"
        payload = {"id":self.__appID,
                   "timestamp":timestamp,
                   "action":action,
                   "sign":signature}
        quoteResponse = requests.post(endpoint,params=payload,data=query)
        if "200" not in str(quoteResponse):
            print(str(quoteResponse)+" in getQuote() function")
            sys.exit(quoteResponse.text)

        quoteJSON = quoteResponse.json()
        return quoteJSON

###############################################################################
    #Takes in the Verykship shipping tempalte filename and create shipment
    #order in verykship server. Output veryk_tracking_data.csv file
    def createOrders(self,shopName):
        #if input file is absent
        if not os.path.isfile(shopName + '_verykship_shipment.xlsx'):
            return [],[]
        print(shopName+': creating veryk orders')
        headerData,orderData = DataProcessor.readInFile(shopName + '_verykship_shipment.xlsx')
        orderIDs =[]
        trackingData = [["tracking_id","name","zipcode"]]
        for order in orderData:
            orderID, trackNum = self.createOrder(order)
            if orderID != None and trackNum != None:
                orderIDs.append(orderID)
                #append trackNum, Name, zipcode
                trackingData.append([trackNum,order[14],order[24]])
      
        #move current shipment template to cache folder for record and prevent duplicate
        #order generation by re-running this method again
        filename = shopName + '_verykship_shipment.xlsx'
        if os.path.isfile('app_cache/'+filename):
            os.remove('app_cache/'+filename)
        os.rename(filename,'app_cache/'+filename)
        
        self.generateShipmentLabels(orderIDs,shopName) #generate shipment labels
        
        #write tracking data to file for etsy object to update it on etsy website
        DataProcessor.writeToFile(trackingData,writeType='w',inputFile=shopName+'_veryk_tracking_data.csv')
           
###############################################################################
    #Takes in a row of data from Verykship shipping tempalte and create a shipment
    #order in verykship server. The order gets submitted automatically on server
    #unless the "state" parameter is set to "open.
    #Returns verykship order ID and tracking number
    def createOrder(self,order):
        action="shipment/create" #action specified in veryk API
        timestamp, signature = self.generateSignature(action)
        
        #if product name is more than 35 char long, truncate it to 35
        pname = order[29]
        if len(pname) > 35:
            pname = pname[:35]

        #Prepare JSON to send to server
        data = {"service_id":order[0]}
        data["payment_method"]="account"
        data["state"]="order"
        data["initiation"]={"region_id":order[12],"postalcode":order[13],"city":order[10],
                             "province":order[11],"name":order[4],"mobile_phone":order[6],
                             "address":order[7],"address2":order[8]}
        data["destination"]={"region_id":order[23],"postalcode":order[24],"city":order[21],
                              "province":order[22],"name":order[14],"mobile_phone":order[16],
                              "address":order[18],"address2":order[19]}
        data["package"]={"type":order[25],"packages":[{"weight":order[26]}]}
        data["product"]=[{"name":pname,"qty":order[30],"price":order[31],
                               "unit":"EA","origin":"CA"}]
        
        data = json.dumps(data) #convert dictionary to json
        
        endpoint = "https://www.verykship.com/api"
        payload = {"id":self.__appID,
                   "timestamp":timestamp,
                   "action":action,
                   "sign":signature}
        orderResponse = requests.post(endpoint,params=payload,data=data)
        if "200" not in str(orderResponse):
            print(str(orderResponse)+" in createOrder() function")
            sys.exit(orderResponse.text)
        orderJSON = orderResponse.json()

        #if orderJSON exist but has no response field, application will simply move on
        if "response" not in orderJSON:
            print("Error occured when creating veryk order for"+order[14])
            print("orderJSON returned :\n")
            print(orderJSON)
            print("Moving on......\n\n")
            return None, None
        return orderJSON["response"]["id"], orderJSON["response"]["waybill_number"]

###############################################################################
    #Takes in a list of orderID (eg.C010046409) and retrieve the shipment labels
    #to label.pdf file
    def generateShipmentLabels(self,orderIDs, shopName):
        if not orderIDs:
            print('no order ID given in Verykship_API.generateShipmentLabels()')
            return
        pdfContent = [] #holder for list of base64 pdf shipment lables
        for orderID in orderIDs:
            action="shipment/label" #action specified in veryk API
            timestamp, signature = self.generateSignature(action)
            data={"id":orderID}
            data = json.dumps(data) #convert dictionary to json
            
            endpoint = "https://www.verykship.com/api"
            payload = {"id":self.__appID,
                       "timestamp":timestamp,
                       "action":action,
                       "sign":signature}
            labelResponse = requests.post(endpoint,params=payload,data=data)
            if "200" not in str(labelResponse):
                print(str(labelResponse)+" in getLabel() function")
                sys.exit(labelResponse.text)
            labelJSON = labelResponse.json()
            #if there is no response in JSON, we will notify user and move on
            if "response" not in labelJSON:
                print("Error occured when getting ship label for order ID: "+orderID)
                print("label JSON returned :\n")
                print(labelJSON)
                print("Moving on......\n\n")
            b64Label = labelJSON["response"]["label"]
            pdfContent.append(b64Label)
            
        #create shipping label
        DataProcessor.createPDF(shopName + '_label.pdf',pdfContent)
        DataProcessor.appendPDF(shopName + '_label.pdf','ship_label.pdf')
        DataProcessor.deletePDF(shopName + '_label.pdf')


