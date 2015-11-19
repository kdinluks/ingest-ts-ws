# ingest-ts-ws
Python script to ingest data from a csv file into Predix time-series service in Predix Cloud.

            The csv file must have the following columns:
              - Equipment name
                The default column index is 1
                You can specify a new column index using the option -ei
                Keep in mind the columns index start at 0
              - Tag name
                The default column index is 2
                You can specify a new column index using the option -ti
              - Timestamp in the format month / day / year hour:minute:seconds AM/PM
                The default column index is 3
                You can specify a new column index using the option -di
                You can also specify a new timestamp format by using the option -t
              - Value
                The default column index is 4
                You can specify a new column index using the option -vi

To run the script simple run 
	python ingest-ts-ws.py <csv-file> <wss-url> <instance-id> <token>
Where:
	- <csv-file> the csv file with the time-series data, please see the comments above.
	- <wss-url> the time-series service websockets url
	- <instance-id> the instance id of your instance of the time-series service
	- <token> the Bearer token from the UAA instance used by the time-series service

Optionally you can pass the following arguments:
	-d or --delimiter : used to specify the delimiter used in the csv file. The default is ";".
	-t or --timestamp : used to specify the timestamp format following the python documentation for the function  strptime(). The default is '%m/%d/%Y %I:%M:%S %p'.
	-s or --datapoints : used to specify the number of points per message to be sent over the wss connection. The default is 500.
	-ei : used to specify the equipment name column index as explained above.
	-ti : used to specify the tag name column index as explained above.
	-di : used to specify the timestamp column index as explained above.
	-vi : used to specify the value column index as explained above.
