import websocket
import thread
import time
import calendar
import sys
import csv
import os
import argparse
import textwrap
from collections import defaultdict

# Parser for input arguments

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
                Script to ingest data from a csv file into Predix time-series service in
            Predix Cloud.

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
        '''),
    epilog=textwrap.dedent('''\
        -------------------------------------------------------------------------------
                           Developed by Ricardo Breder
        '''))

parser.add_argument("data", help="csv file with time-series data")
parser.add_argument("tss", help="time-series wss url")
parser.add_argument("zone", help="time-series service instance id")
parser.add_argument("token", help="predix cloud UAA token")
parser.add_argument("-d", "--delimiter", dest='delimiter', default=';', help="specify the delimiter character. Default is ;")
parser.add_argument("-t", "--timestamp", dest='timestamp', default="%m/%d/%Y %I:%M:%S %p", help="specify the timestamp format following strftime(3) documentation. Default is '%m/%d/%Y %I:%M:%S %p'")
parser.add_argument("-s", "--datapoints", dest='dpsize', default='500', help="specify the number of points per message. Default is 500")
parser.add_argument("-ei", dest='eni', default='1', help="specify the index of the equipment name column in the csv")
parser.add_argument("-ti", dest='tni', default='2', help="specify the index of the tag name column in the csv")
parser.add_argument("-di", dest='tsi', default='3', help="specify the index of the timestamp column in the csv")
parser.add_argument("-vi", dest='vi', default='4', help="specify the index of the value column in the csv")
args = parser.parse_args()

data = args.data
tss = args.tss
zone = args.zone
token = args.token
delimiter = args.delimiter
timestamp = args.timestamp
dpsize = int(args.dpsize)
eni = int(args.eni)
tni = int(args.tni)
tsi = int(args.tsi)
vi = int(args.vi)

def on_message(ws, message):
    if message["statuscode"] != 202:
        print("Error sending packet to time-series service")
        print("Message: " + message)
        sys.exit(1)
    else:
        print("Message: " + message)

def on_error(ws, error):
    print("Error: " + error)

def on_close(ws):
    print("--- Socket Closed ---")

def on_open(ws):
    if os.path.isfile(data):
        with open(data, 'rb') as tsdata:
            reader = csv.reader(tsdata, delimiter=delimiter)
            i = 0
            m = 1
            datapoints = []
            tagname = ""
            equipname = ""
            meter = ""
            payloads = []

            print("Generating packets with " + str(dpsize) + " data points...")

            for row in reader:
                # Create the packets to send it over WS
                # Define the tag name if none exists
                if meter == "":
                    tagname = row[tni]
                    equipname = row[eni]
                    meter = equipname + "_" + tagname

                # If current tag name is different than the tag name from the file, define another tag name
                elif meter != equipname + "_" + tagname:
                    payloads.append(payload(ws, meter, datapoints, m))
                    tagname = row[tni]
                    equipname = row[eni]
                    meter = equipname + "_" + tagname
                    m += 1
                    i = 0
                    datapoints = []

                # Add the last point in the packet and exit the loop
                if i >= dpsize:
                    payloads.append(payload(ws, meter, datapoints, m))
                    m += 1
                    i = 0
                    datapoints = []

                # Verifies if the value is a valid number or don't add the point
                try:
                    value = float(row[vi])
                    tstamp = calendar.timegm(time.strptime(row[tsi], timestamp)) * 1000
                    datapoints.append([tstamp, value])
                except:
                    value = 0.0
                    i += 1
                    continue

                i += 1

            # Append last packet to payload list
            if i > 0:
                payloads.append(payload(ws, meter, datapoints, m+1))

            # Send payloads
            sendPayload(ws, payloads)

    else:
        print("Time-series csv data file not found")
        print("Please make sure the file " + data + "exists and you have access")
        print("Terminating...")
        sys.exit(1)


def payload(ws, meter, datapoints, m):
    datapointsstr = ""
    for d in datapoints:
        datapointsstr += "[" + str(d[0]) + "," + str(d[1]) + "],"

    datapointsstr = datapointsstr[:-1]

    payload = '''{  
                   "messageId": ''' + str(m) + ''',
                   "body":[  
                      {  
                         "name":"''' + meter + '''",
                         "datapoints": [''' + datapointsstr + '''],
                         "attributes":{  
                         }
                      }
                   ]
                }'''
    return payload

def sendPayload(ws, payloads):
    def run(*args):
        i = 0
        it = len(payloads)
        for p in payloads:
            i += 1
            ws.send(p)
            print("Sending packet " + str(i) + " of " + str(it))
            time.sleep(1)

        time.sleep(1)
        ws.close()
        print(str(i) + " packets sent.")
        print("Thread terminating...")

    thread.start_new_thread(run, ())

def sendExcursions(excursions):
    print excursions
    pass


if __name__ == "__main__":
    websocket.enableTrace(True)
    host = tss
    headers = {
                'Authorization:bearer ' + token,
                'Predix-Zone-Id:' + zone,
                'Origin:http://localhost/'
    }
    ws = websocket.WebSocketApp(
                                host,
                                header = headers,
                                on_message = on_message,
                                on_error = on_error,
                                on_close = on_close
    )
    ws.on_open = on_open
    ws.run_forever()
