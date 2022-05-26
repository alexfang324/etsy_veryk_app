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
    #Takes in the Verykship shipping tempalte and create shipment
    #order in verykship server. Returns array of verykship order ID and array of
    # [tracking number, name, zipcode]
    def createOrders(self,filename):
        headerData,orderData = DataProcessor.readInFile('verykship_shipment.xlsx')
        orderIDs =[]
        trackingData = []
        for order in orderData:
            orderID, trackNum = self.createOrder(order)
            orderIDs.append(orderID)
            #append trackNum, Name, zipcode
            trackingData.append([trackNum,order[14],order[24]])
        self.generateShipmentLabels(orderIDs) #generate shipment labels
        return orderIDs,trackingData
    
###############################################################################
    #Takes in a row of data from Verykship shipping tempalte and create a shipment
    #order in verykship server. The order gets submitted automatically on server
    #unless the "state" parameter is set to "open.
    #Returns verykship order ID and tracking number
    def createOrder(self,order):
        action="shipment/create" #action specified in veryk API
        timestamp, signature = self.generateSignature(action)
        
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
        data["product"]=[{"name":order[29],"qty":order[30],"price":order[31],
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
               
        return orderJSON["response"]["id"], orderJSON["response"]["waybill_number"]

###############################################################################
    #Takes in a list of orderID (eg.C010046409) and retrieve the shipment labels
    #to label.pdf file
    def generateShipmentLabels(self,orderIDs):
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
            b64Label = labelJSON["response"]["label"]
            pdfContent.append(b64Label)
        DataProcessor.createPDF('label.pdf',pdfContent) #create shipping label

