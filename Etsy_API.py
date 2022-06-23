import requests
import random
import base64
import hashlib #used for SHA256 encoding
import re #regular expression
import webbrowser
import datetime
import sys
import os
import openpyxl
from DataProcessor import *

redirect_uri = "https://localhost:8000"

class Etsy_API:
###############################################################################
    #shopName is the lower case name of your shop and also name of the credential
    #file in path ./credential/shopName.csv
    def __init__(self,shopName):
        self.__code_challenge = None
        self.__code_verifier = None
        self.__authorization_code = None
        self.__access_token = None
        self.__refresh_token = None
        self.__api_key = None
        self.__api_secret = None
        self.__shop_id = None
        self.__shop_name = shopName.lower()
        
        #check if credential file exist
        filename ='credential/'+self.__shop_name.lower()+'.csv'
        if not os.path.isfile(filename):
            sys.exit('Either the input shop name is incorrect, the file in the path'\
                     './credential/your_shop_name.csv doesn\'t exist or '\
                     'the credential file name isn\'t all in lower cases')      
        #retrieve user credentials
        creDict={}
        with open(filename,'r') as f:
            lines = f.read().split('\n') #create a list of rows of the file data
            for line in lines:
                if not line == '':
                    column = line.split(',')
                    creDict[column[0].strip()]=column[1].strip()           
            #store credential to class instance
            self.__api_key = creDict["api_key"]
            self.__api_secret = creDict["api_secret"]
            self.__shop_id = creDict["shop_id"]
            self.__refresh_token = creDict["refresh_token"]
        
        #renew refresh token and get a new access token()
        self.getRefreshToken()

###############################################################################    
    def OAuthenticate(self):
        self.generateCodeChallenge()
        self.getAuthorizationCode()
        self.getAccessToken()

###############################################################################     
    def generateCodeChallenge(self):
        #Generate "verifier code" and "code challenge" for OAuth purpose and send the code challenge to Etsy
        rand_Octet_Seq = bytearray([random.randrange(256) for i in range(32)]) #array of 32 random byte-long number in binary format
        code_verifier = base64.urlsafe_b64encode(rand_Octet_Seq) #encode with base64
        
        #it turns out urlsafe_b64encode might still have "=" in the output so we have to remove it ourself
        code_verifier = code_verifier.decode('utf-8').replace("=","").encode('utf-8')
        intermediate_step = hashlib.sha256(code_verifier) #encode with SHA256
        intermediate_step = intermediate_step.digest() #convert SHA object to byte
        code_challenge = base64.urlsafe_b64encode(intermediate_step) #encode with base64
        code_challenge = code_challenge.decode('utf-8').replace("=","").encode('utf-8') #remove "=" from challenge       
        self.__code_verifier = code_verifier
        self.__code_challenge = code_challenge

###############################################################################
    #Get Authorization Token
    def getAuthorizationCode(self):
        with requests.Session() as session:
            authorizationURL = "https://www.etsy.com/oauth/connect"
            payload = {"response_type": "code",
                     "client_id":self.__api_key,
                     "redirect_uri":redirect_uri,
                     #note that the scope are space separated which will get a %2B (plus sign) when encoded into url
                     #it works even when Etsy ask for %20(space) encoding
                     "scope":"address_r address_w listings_r listings_w transactions_r transactions_w", 
                     "state":"superstate",
                     "code_challenge":self.__code_challenge,
                     "code_challenge_method":"S256"}
            authorizationResponse = session.get(authorizationURL,params=payload)
            
            print('Copy and run the below link to log in and grant app access, '\
                  'then in the redirected url, find and copy the authorization code '\
                  'into the console\n')
            print(authorizationResponse.url)
            self.__authorization_code = str(input('Enter Authorization code and press enter:\n'))
        
###############################################################################
    #Request OAuth Acess token
    def getAccessToken(self):
        accessTokenURL = "https://api.etsy.com/v3/public/oauth/token"
        data = {"grant_type":"authorization_code",
                   "client_id":self.__api_key,
                   "redirect_uri":redirect_uri,
                   "code":self.__authorization_code,
                   "code_verifier":self.__code_verifier}
        accessTokenResponse = requests.post(accessTokenURL, data=data)
        accessTokenJSON = accessTokenResponse.json()  
        self.__access_token = accessTokenJSON["access_token"]
        self.__refresh_token = accessTokenJSON["refresh_token"]
        self.updateRefreshTokenToFile()
        print(self.__shop_name+': OAuth2 Authentication Complete, Access Token Retrieved\n')
###############################################################################
    #Get refresh token
    def getRefreshToken(self):
        refreshTokenURL = "https://api.etsy.com/v3/public/oauth/token"       
        data = {"grant_type":"refresh_token",
           "client_id":self.__api_key,
           "refresh_token":self.__refresh_token}

        refreshTokenResponse = requests.post(refreshTokenURL, data=data)
        refreshTokenJSON = refreshTokenResponse.json()
        if '200' not in str(refreshTokenResponse):
            print(refreshTokenResponse.text)
            print('Going Re-Oauthenticate the app now...\n')
            self.OAuthenticate()
            print('Successfully Retrieving New Access and Refresh Tokens\n')
            return
        self.__access_token = refreshTokenJSON["access_token"]
        self.__refresh_token = refreshTokenJSON["refresh_token"]        
        self.updateRefreshTokenToFile()
        print(self.__shop_name+': Successfully Retrieving New Access and Refresh Tokens')
###############################################################################
    #update refresh token to credential file by rewriting the entire file with 
    #appropraite update
    def updateRefreshTokenToFile(self):                
        lines = open('credential/'+self.__shop_name.lower()+'.csv','r').read().split('\n')
        with open('credential/'+self.__shop_name.lower()+'.csv','w') as fout:
                for line in lines:
                    column = line.split(',')
                    if column[0].strip() != "refresh_token":
                        fout.write(line+'\n')
                    else:
                        fout.write(column[0]+', '+self.__refresh_token)                
###############################################################################
    #GET all active and sold out listings and for each listing, GET the variations
    #and inventory data and write to a file
    def getInventory(self): 
        print(self.__shop_name+': Retrieving Inventory (inventory_data.csv)')
        #######################
        #GET all active listings
        #######################
        queryItr = 0 #starting point offset of the http GET data query
        while(True):
            #Etsy getListingsByShop request
            endpoint = "https://openapi.etsy.com/v3/application/shops/{shop_id}/listings"
            endpoint = endpoint.replace("{shop_id}",self.__shop_id)  
            header = {"x-api-key":self.__api_key, "Authorization":"Bearer "+self.__access_token}
            query = {"limit":100,"offset":100*queryItr}
            activeListingsResponse = requests.get(endpoint, headers=header, params=query)
            activeListingsJSON = activeListingsResponse.json()

            if "200" not in str(activeListingsResponse):
                print(str(activeListingsResponse)+" in active listings of getInventory() function")
                sys.exit(activeListingsResponse.text)
            
            #stop query further if no result is found. Note that checking if
            #the "count" parameter of JSON is zero won't work here as it always
            #shows the numbers available for retrival not the number retrieved sucessfully
            if not len(activeListingsJSON["results"]):
                break

            #save the ID and title of each active listing into two arrays
            listingID = []
            listingTitles = []
            for i in range(len(activeListingsJSON["results"])):
                listingID.append(str(activeListingsJSON["results"][i]["listing_id"]))
                listingTitles.append(activeListingsJSON["results"][i]["title"])
                
            queryItr+=1
        
        #######################
        #GET all sold out listings
        #######################
        header = {"x-api-key":self.__api_key, "Authorization":"Bearer "+self.__access_token}
        query = {"limit":100, "state":"sold_out"}
        soldOutListingsResponse = requests.get(endpoint, headers=header, params=query)
        soldOutListingsJSON = soldOutListingsResponse.json()
        
        if "200" not in str(soldOutListingsResponse):
            print(str(soldOutListingsResponse)+" in sold out listings of getInventory() function")
            print(soldOutListingsResponse.text)   
            return
            
        #add to list
        for i in range(len(soldOutListingsJSON["results"])):
            listingID.append(str(soldOutListingsJSON["results"][i]["listing_id"]))
            listingTitles.append(soldOutListingsJSON["results"][i]["title"])
        
        #############################
        #GET each listing information
        #############################   
        #Etsy getListingInventory request
        dataHeader = ["Item Name","Variations","Quantity"] #output data header
        inventoryData = [] #used to save inventory data
        #for each request, save inventory data to inventoryData array
        for i in range(len(listingID)):
            endpoint = "https://openapi.etsy.com/v3/application/listings/{listing_id}/inventory"
            endpoint = endpoint.replace("{listing_id}",listingID[i])
            header = {"x-api-key":self.__api_key, "Authorization":"Bearer "+self.__access_token}
            listingResponse = requests.get(endpoint, headers=header)
            listingJSON = listingResponse.json()

            if "200" not in str(listingResponse):
                print(str(listingResponse)+" occured when retrieving listing with listingID=%s in the retrieveInventory function"%(activeListingID[i]))
                print(listingResponse.text)
                return
            
            #for each SKU in the listing, find its property field and inventory quantity
            for j in range(len(listingJSON["products"])):
                #check if an variation in a listing is turned on, if it's not we
                #shouldn't consider the values there as it's not available to buyers
                if listingJSON["products"][j]["offerings"][0]["is_enabled"]:
                    variation=''                
                    #for each property field in product listing, concatenate into one "variation" string
                    for k in range(len(listingJSON["products"][0]["property_values"])):
                        variation += listingJSON["products"][j]["property_values"][k]["property_name"]
                        variation += ':'
                        variation += listingJSON["products"][j]["property_values"][k]["values"][0]
                        variation += ', '
                    variation=variation[:-2] #remove the extra comma and space at the end
                    #handle last property field
                    quantity = listingJSON["products"][j]["offerings"][0]["quantity"] #index 0 because we never have more than one offering per variation
                    #append double quote to prevent csv file from splitting the comma in the content
                    inventoryData.append(['"'+listingTitles[i]+'"','"'+variation+'"', quantity]) 
        inventoryData = DataProcessor.getPreferredName(inventoryData,0,self.__shop_name+'_naming_convention.csv') #convert listing name to shorter preferred names
        inventoryData.sort(key=lambda x:x[0]) #sort data by name (first element in each list of list)
        inventoryData.insert(0,dataHeader) #append header to top of list and write to file
        DataProcessor.writeToFile(inventoryData,writeType='w',inputFile='data_file/'+self.__shop_name+'_inventory_data.csv')

###############################################################################
    #retrieve this month's "ordered item" data from Etsy with queries cap at 100
    #lines at a time. The retrival process stops when a particular query doesn't
    #provide a single line of relevant data. The data is then written to sales_data.csv    
    def getSalesData(self):
        print(self.__shop_name+': Retrieving Sales Data (sales_data.csv)')
        dataSeen = True #initialize dummy holder to record if relevant data is seen in the particular query
        queryItr = 0 #starting point offset of the http GET data query
        dataHeader = ["Sale Date", "Item Name", "Variations", "Quantity"]
        data = [] #output data array
        
        while(dataSeen):
            dataSeen = False #reset holder for seeing relevant data
            salesJSON = self.sendSalesDataRequest(queryItr*100) #request data in multiples of 100
            queryItr += 1 #increament offset for next query starting point
            if not salesJSON:
                print('No data retrieved from getSalesData function')
                return
            
            #copy this month's sales data to array
            thisMonth = datetime.datetime.now().strftime("%m")           
            for i in range(len(salesJSON["results"])):
                created_timestamp = salesJSON["results"][i]["created_timestamp"] #epoch time
                salesMonth = datetime.datetime.fromtimestamp(created_timestamp).strftime("%m") #sales month of the transaction
                
                #if data belong to this month, copy data to output array
                if salesMonth == thisMonth:
                    dataSeen = True #seeing relevant data in this query JSON           
                    time = datetime.datetime.fromtimestamp(created_timestamp).strftime("%Y-%m-%d") #get calander time           
                    title = salesJSON["results"][i]["title"]
                    quantity = salesJSON["results"][i]["quantity"]
                    variation = ''
                    for j in range(len(salesJSON["results"][i]["variations"])):
                        variation += salesJSON["results"][i]["variations"][j]["formatted_name"]
                        variation += ':'
                        variation += salesJSON["results"][i]["variations"][j]["formatted_value"]
                        variation += ', '
                    variation=variation[:-2] #remove the extra comma and space at the end
                    #append double quote to prevent csv file from splitting the comma in the content
                    data.append([time,'"'+title+'"','"'+variation+'"',quantity])
        data = DataProcessor.getPreferredName(data, 1,self.__shop_name+'_naming_convention.csv') #convert listing name to shorter preferred names
        data.sort(reverse=True,key=lambda x:x[0]) #sort data in descending order and by first element in list of list
        data.insert(0,dataHeader) #append header to top of list and write to file
        DataProcessor.writeToFile(data, writeType='w',inputFile='data_file/'+self.__shop_name+'_sales_data.csv')

###############################################################################
    #retrieve 100 lines "ordered item" data from Etsy starting at index offset
    def sendSalesDataRequest(self,offset):
        #using getShopReceiptTransactionsByShop request from Etsy API
        endpoint = "https://openapi.etsy.com/v3/application/shops/{shop_id}/transactions"
        endpoint = endpoint.replace("{shop_id}",self.__shop_id)  
        header = {"x-api-key":self.__api_key, "Authorization":"Bearer "+self.__access_token}
        query = {"limit":100,"offset":offset}
        salesResponse = requests.get(endpoint, headers=header, params=query)
        salesJSON = salesResponse.json()
        
        if "200" not in str(salesResponse):
            print(str(salesResponse)+" occured when retrieving sales Data in the sendSalesDataRequest function")
            print(salesResponse.text)
            return None
        else:
            return salesJSON

###############################################################################
    #Takes the inventory_data.csv output from getInventory function and the
    #sales_data.csv output from getSalesData function and combine them into
    #a summary file. The file has below column structure:
    #sales_data = ["Sales Date","Item Name","Variation","Quantity"]
    #inventory_data = ["Item Name","Variation","Quantity"]
    #output array = ["Item Name","Variation","Sales Quantity","After sale Inventory Quantity", "Unit]
    
    def getSummary(self):
        print(self.__shop_name+': Preparing summary File (data_summary.csv)')
        unitWanted = ['pair','pcs','beads'] #Used in the priority given to identify per package quantity in "Variations" column to calculate actual quantity sold
        specWanted = ['Size','Color','Style'] #Used to combine quantities of items with same specs

        ###################################
        #Read in and Process Inventory Data
        ###################################
        #read in inventory data file
        inventoryHeader, inventoryData = DataProcessor.readInFile('data_file/'+self.__shop_name+'_inventory_data.csv')
        
        #find column index of variables wanted with a search in case data file structure changed
        invNameInd = inventoryHeader.index("Item Name")
        invQuanInd = inventoryHeader.index("Quantity")
        invVarInd = inventoryHeader.index("Variations")

        #find package quantity hidden in "Variations" column and calculate total quantity
        #output array struct is ["Item Name","Spec", "Quantity", "Unit"]
        inventoryData = DataProcessor.updateQuantityUsingVariations(inventoryData,invNameInd,invVarInd,invQuanInd,unitWanted,specWanted)

        ################################
        #Read in and Process Sales Data
        ################################
        #read in sales data file
        salesHeader, salesData = DataProcessor.readInFile('data_file/'+self.__shop_name+'_sales_data.csv')

        #find column index of variables wanted with a search in case data file structure changed
        salesNameInd = salesHeader.index("Item Name")
        salesQuanInd = salesHeader.index("Quantity")
        salesVarInd = salesHeader.index("Variations")

        #find package quantity hidden in "Variations" column and calculate total quantity
        #output array struct is ["Item Name","Spec", "Quantity", "Unit"]
        salesData = DataProcessor.updateQuantityUsingVariations(salesData,salesNameInd,salesVarInd,salesQuanInd,unitWanted,specWanted)

        #insert sales quantity to corresponding row of inventory data
        for i in range(len(inventoryData)):
            matched = False #record if we see a match
            for j in range(len(salesData)):
                #check if they have same name and spec
                if inventoryData[i][0:2] == salesData[j][0:2]:
                    #check if they have the same units
                    if not inventoryData[i][-1] == salesData[j][-1]:
                        print('getSummary(): below inventory and sales item parsed from inventory_data.csv and sales_data.csv'
                              ', respectively, have different units. Will not update sales quantitiy of this item')
                        print('\n',inventoryData[i])
                        print('\n',salesData[j])
                        break
                    matched = True
                    inventoryData[i].insert(2,salesData[j][2])
                    salesData.pop(j) #remove salesData that has been recorded
                    break
            #if no match is found  
            if not matched:
                inventoryData[i].insert(2,'') #insert blank sale quantity for current inventory
        #if there is order sold that had its listing deleted we will append to the end of file
        if salesData:
            for data in salesData:
                inventoryData.append([data[0],data[1],data[2],0,data[3]])
        #append header to data and write to file
        newHeader = ["Item Name", "Specs", "Sales Quantity", "Aft. Sale Inventory Quantity", "Unit"]
        inventoryData = [newHeader] + inventoryData
        DataProcessor.writeToFile(inventoryData, writeType='w', inputFile='data_file/'+self.__shop_name+'_data_summary.csv')

###############################################################################
    def updateSummaryFile(self):
        if not os.path.isfile('data_file/'+self.__shop_name+'_data_summary.csv'):
            print('data file doesn\'t exist, aborting function')
            return
        newHeader, newData = DataProcessor.readInFile('data_file/'+self.__shop_name+'_data_summary.csv')
        
        outputfile = self.__shop_name+'_summary.xlsx'
        wb = openpyxl.workbook.Workbook()
        page = wb.active
        Date = datetime.datetime.now().strftime("%m-%d") 
        #if output file doens't exist, modify new data file into output file format
        if not os.path.isfile(outputfile):
            page.append(["Item Name","Unit","Specs",Date,"Current Stock"])
            for row in newData:
                page.append(row)

        #if there is an existing output file, append new data to it
        else:
            #read in existing file as 2D list then store into a dict
            oldHeader, oldData = DataProcessor.readInFile(outputfile)
            dataDict = {}
            #remove empty cells at the end of row captured by python
            head = []
            for item in oldHeader:
                if item != None and item != " ":
                    head.append(item)
            oldHeader = head
            
            for data in oldData:
                key = tuple([data[0],data[1],data[2]]) #name and spec as key
                values=[]
                #remove empty cells at the end of a row that was captured by python
                for val in data[3:]:
                    if val != None and val != " ":
                        values.append(val)
                dataDict[key] = values #store rest of data as values

            #add new data to dict
            for data in newData:
                key = tuple([data[0].strip("\""),data[4],data[1]])
                if key in dataDict:
                    newVal = dataDict[key]
                    newVal.extend(data[2:4])
                    dataDict[key]= newVal
                    print("matched"+key[0])
                #if item is not in dict, create a new row for it with appropriate spaces in front
                else:
                    newVal = ["0" for i in range(len(oldData[0])-3)]
                    newVal.extend(data[2:4])
                    dataDict[key] = newVal
                    print("NO")
            
            #update header and write header and data to file
            oldHeader.extend([Date,"Current Stock"])
            page.append(oldHeader)
            for key,val in dataDict.items():
                values = [key[0],key[1],key[2]]
                values.extend([v for v in val])
                page.append(values)
        
        wb.save(filename=outputfile)
            
                
###############################################################################
    #get new and unshipped order from Etsy and pass it to another function to
    #generate template for creating shipping labels and output file of 
    #receipt data in etsy_receipt_data.csv.
    def getNewOrders(self):
        #using getShopReceipts request from Etsy API
        endpoint = "https://openapi.etsy.com/v3/application/shops/{shop_id}/receipts"
        endpoint = endpoint.replace("{shop_id}",self.__shop_id)  
        header = {"x-api-key":self.__api_key, "Authorization":"Bearer "+self.__access_token}
        query = {"was_shipped":False}
        orderResponse = requests.get(endpoint, headers=header, params=query)
        orderJSON = orderResponse.json()
        
        if "200" not in str(orderResponse):
            print(str(orderResponse)+" occured when retrieving new order details in the getNewOrders function")
            print(orderResponse.text)
            return None
        #filter out eligible orders and generate verykship template and stamp shipping labels
        print(self.__shop_name+': Retrieved New Orders')
        eligibleOrders, nonEligibleOrders = self.eligibleForTracking(orderJSON["results"])
        receiptData = self.generateVerykTemplate(eligibleOrders)
        self.generateStampLabels(nonEligibleOrders)
                
        #write receipt data into file for veryk object to udpate tracking
        DataProcessor.writeToFile(receiptData,writeType='w',inputFile=self.__shop_name+'_etsy_receipt_data.csv')
 
###############################################################################  
    #takes an Etsy order JSON and filter the shipping information into two eligible
    #and non-eligible orders.      
    def eligibleForTracking(self,orders):
        eligibleOrders = [] #holds eligible orders
        nonEligibleOrders = [] #holds non-eligible orders
        for order in orders:
            #get subtotal amount
            subtotal = order["subtotal"]["amount"]/order["subtotal"]["divisor"]
            #get shipping cost
            shippingCost = order["total_shipping_cost"]["amount"]/order["total_shipping_cost"]["divisor"]
            
            if self.__shop_name.lower() == 'sunmertime':
                #eligible if US order > $40 or CA order > $60
                if order["country_iso"]=="US" and subtotal>=40 or order["country_iso"]=="CA" and subtotal>=60:
                    eligibleOrders.append(order)
                #else eligible if shipping was paid
                elif shippingCost>0:
                    eligibleOrders.append(order)
                #non-eligible
                else:
                    nonEligibleOrders.append(order)
            elif self.__shop_name.lower() == 'sparkleland':
                #eligible if US order > 40 or CA order > $100
                if order["country_iso"]=="US" and subtotal>=40 or order["country_iso"]=="CA" and subtotal>=100:
                    eligibleOrders.append(order)
                #else eligible if shipping was paid
                elif shippingCost>5:
                    eligibleOrders.append(order)
                #non-eligible
                else:
                    nonEligibleOrders.append(order)
            else:
                sys.exit("Invalid shopName is given in eligibleForTracking function")
        print(self.__shop_name+': Checked Orders Against Tracking Eligibility')
        return eligibleOrders, nonEligibleOrders
###############################################################################
    #Takes an array of shipping information from Etsy and generate a template needed
    #by Veryshipk for batch shipment label creation in veryk_shipment.csv
    def generateVerykTemplate(self, newOrders):
        if not newOrders:
            print(self.__shop_name+': No eligible tracked order is seen')
            return
        
        #dict between ISO-3166 country code and veryshipk courier service code
        postalDict={"CA":"180", #CP Expedited
                    "US":"151" #CP US Tracked Shipping
                    }
        personSet =set() #hashset to hold repicient name and zipcode
        data = [] #used to hold all order information
        receiptData = [["receipt_id","name","zipcode"]] #used to hold Etsy receipe id and name for updating tracking in another function
        for order in newOrders:
            #make sure the order in "New Order section" is paid
            if not order["status"]:
                print("customer %s hasn't paid, skipping his/her shipment label generation"%(order["name"]))
                break;
                
            #append order detail to receiptData    
            receiptData.append([str(order["receipt_id"]),order["name"],order["zip"]])
            
            #add every new recipient to personSet. if a buyer placed multiple orders
            #we will only add the first order to shipment template for tracking generation
            #then update all order with the same tracking using receiptData information
            personInfo = tuple([order["name"],order["zip"]])
            if personInfo in personSet:
                continue #person already placed an order, do not generate another shipment, move on to next order
            personSet.add(personInfo)
            label = [] # holds details of a single order
            label.append(postalDict[order["country_iso"]]) #template column A
            #shipper information from column B to N
            label.extend(["open","","","Audrey Xu","","7783179726","3302-4670 Assembly Way","","","Burnaby","BC","CA","V5H 0H3"])
            #recipient information from column O to Y
            label.extend([order["name"],"","7788386913","Y",order["first_line"],order["second_line"],"",order["city"],order["state"],order["country_iso"],order["zip"]])
            #package information from column Z to AE
            label.extend(["Pak","0.1","","",'"'+order["transactions"][0]["title"]+'"',"1"])
            #package unit price column AF
            label.append("{:.2f}".format(order["subtotal"]["amount"]/order["subtotal"]["divisor"]))
            #product information from column AG to AJ
            label.extend(["","","",""])
            data.append(label)
        data = DataProcessor.getPreferredName(data, 29, self.__shop_name+'_naming_convention.csv') #convert listing name to shorter preferred names
        DataProcessor.writeToFile(data,writeType='a',inputFile='verykship_template.xlsx',outputFile=self.__shop_name+'_verykship_shipment.xlsx')
        print(self.__shop_name+': Shipment Template Generated (verykship_shipment.xlsx)')
        return receiptData
###############################################################################
    #Updates tracking to appropriate order using etsy_receipt_data.csv
    # and veryk_tracking_data.csv
    def updateTracking(self):
        #read in veryk tracking data
        trackingFile = self.__shop_name + '_veryk_tracking_data.csv'
        if os.path.isfile(trackingFile):
            trackingDataHeader,trackingData = DataProcessor.readInFile(trackingFile)
            #move file to cache folder
            if os.path.isfile('app_cache/'+trackingFile):
                os.remove('app_cache/'+trackingFile)
            os.rename(trackingFile,'app_cache/'+trackingFile)
        else:
            print(self.__shop_name+': tracking_data file is not available: nothing to update')
            return
        
        #read in etsy receipt data
        receiptFile = self.__shop_name + '_etsy_receipt_data.csv'
        if os.path.isfile(receiptFile):
            receiptDataHeader,receiptData = DataProcessor.readInFile(receiptFile)
            #move file to cache folder
            if os.path.isfile('app_cache/'+receiptFile):
                os.remove('app_cache/'+receiptFile)
            os.rename(receiptFile,'app_cache/'+receiptFile)
        else:
            print(self.__shop_name+':No receipt data is provided to Etsy_API.updateTracking()')
            return
        
        print('\n'+self.__shop_name+': Updated tracking for:')
        for receipt in receiptData:
            for tracking in trackingData:
                if tracking[1:3]==receipt[1:3]:
                    receipt_id = receipt[0]
                    trackNum = tracking[0]
                    print(tracking[1]+' '+tracking[0])

                    #using createReceiptShipment request from Etsy API
                    endpoint = "https://openapi.etsy.com/v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking"
                    endpoint = endpoint.replace("{shop_id}",self.__shop_id)
                    endpoint = endpoint.replace("{receipt_id}",receipt_id)
                    header = {"x-api-key":self.__api_key, "Authorization":"Bearer "+self.__access_token}
                    data = {"tracking_code":trackNum,"carrier_name":"canada-post"}
                    updateResponse = requests.post(endpoint, headers=header, data=data)           
                    
                    if "200" not in str(updateResponse):
                        print(str(updateResponse)+" occured when updating tracking for client %s in the updateTracking function"%(tracking[1].upper()))
                        print(updateResponse.text)
                        return None
        print(self.__shop_name+': Tracking Updated')

###############################################################################
    #takes a etsy order JSON and writes need shipping information to a csv file
    def generateStampLabels(self,orders):
        if not orders:
            print(self.__shop_name+": No stamp label is seen")
            return
        print(self.__shop_name+": Generating stamp labels")
        personSet =set() #hashset to hold repicient name and zipcode
        label = [] #used to hold all order information       
        for order in orders:
            if not order["status"]:
                print("customer %s hasn't paid, skipping his/her shipment label generation"%(order["name"]))
                break;
            content = [order["name"],order["first_line"],order["second_line"],order["city"],order["state"],order["country_iso"],order["zip"]]
            #if address 2 field is explicity written as None, replace it with a space
            if content[2] == None:
                content[2] = " "
            label.append(content)
        DataProcessor.writeToFile(label,writeType='a',inputFile='stamp_label.csv')

###############################################################################
    def getShippingCarriers(self):
        #Etsy getShippingCarriers request
        endpoint = "https://openapi.etsy.com/v3/application/shipping-carriers"
        header = {"x-api-key":self.__api_key}
        query = {"origin_country_iso":"CA"}
        carrierResponse = requests.get(endpoint, headers=header, params=query)
        if "200" not in str(carrierResponse):
            sys.exit(carrierResponse.text)
        carrierJSON = carrierResponse.json()
        return carrierJSON

###############################################################################
    #move files to app_cache folder
    def moveToCacheFolder(self):
        #if new file exist, delete the one in app_cache folder then move new file to folder
        filename = 'stamp_label.csv'
        if os.path.isfile(filename):
            if os.path.isfile('app_cache/'+filename):
                os.remove('app_cache/'+filename)           
            os.rename(filename,'app_cache/'+filename)

        filename = 'ship_label.pdf'
        if os.path.isfile(filename):
            if os.path.isfile('app_cache/'+filename):
                os.remove('app_cache/'+filename)           
            os.rename(filename,'app_cache/'+filename)