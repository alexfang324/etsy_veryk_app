This application integrates the Etsy API and Veryk (third party shipment platform) to achieve the following goals:
1. Retrieve real-time inventory and monthly sales data to a summary file for convenient, any-time shop monitoring
2. Retrieves tracked and untracked shipping order information for bulk print out and automatically updates tracking generated on
Veryk back to Etsy so the user only has to print the two types of labels.
3. Automatically converts user preferred names instead of the full listing name in summary file and on shipment labels.
4. Handles multiple shop for the above functionalities with the same main script.

User Instruction:
1. Add your Etsy shop credential to the credential folder and name it to as your shop name. A template is given in the folder as 
shopName.csv. The application uses the credential in this file to connect with Etsy through OAuth2 authentication and a refresh
token will then be appended to this file for future connection.

2. Add your Veryk credential to the credential folder and name it veryk.csv. This is not mandatory, however, without this credential,
the application will not be able to generate shipping labels necessary. In this case, the user may use the shipping information in
"verykship_shipment.csv" file in the main directory and upload to the preferred shipping platform for label generation and update
the tracking number manually by hand.

3. Add your preferred item naming convention in the main directory as (your shop name)_naming_convention.csv. A template file
is provided as shopName_naming_convention.csv. This file is not mandatory. If it's not provided, all item names in the summary
page and shipping label will be the associated Etsy listing titles.

4. After the above files have been created. You can then run the application by running the main script. A simple example is provided
in the main script.

Useful Output File:
1. app_cache/label.pdf - contains shipping label of tracked orders. Can be printed directly with a printer.
2. app_cache/stamp_label.csv - contains shipping information of untracked orders. Recommand import into a label printer (e.g. Dymo) for bulk printing
3. data_file/yourShopName_summary.csv - contains real-time inventory and the current month sales data in sorted orders. 