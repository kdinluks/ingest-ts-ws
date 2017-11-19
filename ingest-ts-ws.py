import pandas
import websocket
import thread
import time
import calendar
import sys
import csv
import os
import argparse
import textwrap
import requests
import json
import yaml
import logging
import math
from collections import defaultdict

# Global variables
PAYLOADS = []

def on_message(ws, message):
    if json.JSONDecoder().decode(message)["statusCode"] != 202:
        print("Error sending packet to time-series service")
        print(message)
        #sys.exit(1)
    else:
        print("Packet Sent")

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("--- Socket Closed ---")

def prepareData(payloads, tsUri, tsZone, uaaToken, uaaUri, uaaClient, uaaSecret, uaaUsername, uaaPassword, delimiter, timestamp, dpsize, eni, tni, tsi, vi, concat, metername):
    if os.path.isfile(data):
        df = pandas.read_csv(data, sep=delimiter, header=None)
        if eni == -1:
            df.sort_values(by=[tni], ascending=True, inplace=True)
        else:
            df.sort_values(by=[eni, tni], ascending=True, inplace=True)

        i = 0
        m = 1
        datapoints = []
        #tagname = data.rsplit('/',1)[1].replace('.csv', '')
        #equipname = "AT-PBE-3152"
        if eni == -1 and metername == -1:
            equipname = raw_input('Enter the equipment name for file ' + data + ': ' )
        meter = ""
        # payloads = []

        print("Generating packets with " + str(dpsize) + " data points...")

        for index, row in df.iterrows():
            # Create the packets to send it over WS
            # Define the tag name if none exists
            tagname = row[tni]
            
            if eni != -1:
                equipname = row[eni]

            if metername == -1:
                if meter == "":
                    meter = equipname + concat + tagname
                    print("Meter name: " + meter)

                # If current tag name is different than the tag name from the file, define another tag name
                elif meter != equipname + concat + tagname:
                    payloads.append(payload(meter, datapoints, m))
                    meter = equipname + concat + tagname
                    print("Meter name: " + meter)
                    m += 1
                    i = 0
                    datapoints = []

            else:
                if meter == "":
                    if type(metername) is str:
                        meter = metername
                        print("Meter name: " + meter)
                    else:
                        meter = row[metername]
                        print("Meter name: " + meter)

                # If current tag name is different than the tag name from the file, define another tag name
                elif type(metername) is not str:
                    if meter != row[metername]:
                        payloads.append(payload(meter, datapoints, m))
                        meter = row[metername]
                        print("Meter name: " + meter)
                        m += 1
                        i = 0
                        datapoints = []
                        
            # Add the last point in the packet and exit the loop
            if i >= dpsize:
                payloads.append(payload(meter, datapoints, m))
                m += 1
                i = 0
                datapoints = []

            # Verifies if the value is a valid number or don't add the point
            try:
                value = float(row[vi])
                if math.isnan(value):
                    continue
            except:
                print("Invalid reading: " + row)
                value = 0.0
                i += 1
                continue

            try:
                tstamp = calendar.timegm(time.strptime(row[tsi], timestamp)) * 1000
            except:
                try:
                    tstamp = calendar.timegm(time.strptime(row[tsi], timestamp+".%f")) * 1000
                except:
                    print("Error converting date " + row[tsi] + " using the provided time stamp " + timestamp)
                    print("Terminating...")
                    sys.exit(1)

            datapoints.append([tstamp, value])

            i += 1

        # Append last packet to payload list
        if i > 0:
            payloads.append(payload(meter, datapoints, m+1))

        return payloads

    else:
        print("Time-series csv data file not found")
        print("Please make sure the file " + data + " exists and you have access")
        print("Terminating...")
        sys.exit(1)


def payload(meter, datapoints, m):
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

def sendPayload(ws):
    global PAYLOADS
    def run(*args):
        i = 0
        it = len(PAYLOADS)
        for p in PAYLOADS:
            i += 1
            ws.send(p)
            print("Sending packet " + str(i) + " of " + str(it))
            time.sleep(1)

        time.sleep(1)
        ws.close()
        print(str(i) + " packets sent.")
        print("Thread terminating...")

    thread.start_new_thread(run, ())

def getToken(uaaUri, uaaUsername, uaaPassword, uaaClient, uaaSecret):
    uri = uaaUri
    payload = {"grant_type": "password", "username": uaaUsername, "password": uaaPassword}
    auth = requests.auth.HTTPBasicAuth(uaaClient, uaaSecret)
    request = requests.post(uri, data=payload, auth=auth)
    if request.status_code == requests.codes.ok:
        return json.JSONDecoder().decode(request.text)["access_token"]
    else:
        print("Error requesting token")
        request.raise_for_status()

def openWSS(uaaToken, uaaUsername, uaaPassword, uaaClient, uaaSecret, tsUri):
    if uaaToken == '':
        uaaToken = getToken(uaaUri, uaaUsername, uaaPassword, uaaClient, uaaSecret)
        
    #websocket.enableTrace(False)
    host = tsUri
    headers = {
                'Authorization:bearer ' + uaaToken,
                'Predix-Zone-Id:' + tsZone,
                'Origin:http://127.0.0.1/'
    }
    ws = websocket.WebSocketApp(
                                host,
                                header = headers,
                                on_message = on_message,
                                on_error = on_error,
                                on_close = on_close
    )
    ws.on_open = sendPayload
    ws.run_forever()

def loadFromYaml(yamlFile, tsUri, tsZone, uaaToken, uaaUri, uaaClient, uaaSecret, uaaUsername, uaaPassword, delimiter, timestamp, dpsize, eni, tni, tsi, vi, concat, metername, filename):
    if yamlFile != '':
        if os.path.isfile(yamlFile):
            with open(yamlFile, 'r') as stream:
                config = yaml.load(stream)
                tsUri = config["time-series"]["uri"]
                tsZone = config["time-series"]["zone"]
                uaaToken = config["uaa"]["token"]
                uaaUri = config["uaa"]["uri"]
                uaaClient = config["uaa"]["client"]
                uaaSecret = config["uaa"]["secret"]
                uaaUsername = config["uaa"]["username"]
                uaaPassword = config["uaa"]["password"]
                if "csv" in config.keys():
                    csvConfig = config["csv"]
                    if "delimiter" in csvConfig.keys():
                        delimiter = csvConfig["delimiter"]
                    if "timestamp" in csvConfig.keys():
                        timestamp = csvConfig["timestamp"]
                    if "packetsize" in csvConfig.keys():
                        dpsize = int(csvConfig["packetsize"])
                    if "indexes" in csvConfig.keys():
                        eni = int(csvConfig["indexes"]["equipment"])
                        tni = int(csvConfig["indexes"]["tag"])
                        tsi = int(csvConfig["indexes"]["timestamp"])
                        vi = int(csvConfig["indexes"]["value"])
                    if "concatchar" in csvConfig.keys():
                        concat = csvConfig["concatchar"]
                    if "metername" in csvConfig.keys():
                        metername = csvConfig["metername"]
                if "meters" in config.keys():
                    metersConfig = config["meters"]
                    if filename.split('_')[1] in metersConfig.keys():
                        metername = metersConfig[filename.split('_')[1]]["metername"]

                print("Configuration file " + yamlFile + " loaded")
        else:
            print("The file " + yamlFile + " doesn't exist or you don't have permission to access it")
            print("Terminating...")
            sys.exit(1)
    elif tsUri == '' or tsZone == '' or uaaUri == '' or uaaClient == '' or uaaSecret == '' or uaaUsername == '' or uaaPassword == '':
        print("Please either use a yaml file with option -y")
        print("or specify the parements -tss -zone -uaa -client -secre -username -password")
        print("Terminating...")
        sys.exit(1)

    return tsUri, tsZone, uaaToken, uaaUri, uaaClient, uaaSecret, uaaUsername, uaaPassword, delimiter, timestamp, dpsize, eni, tni, tsi, vi, concat, metername

if __name__ == "__main__":
    global PAYLOADS
    logging.basicConfig()
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

    parser.add_argument("data", nargs='*', help="csv file with time-series data")
    parser.add_argument("--tss", dest='tss', default='', help="time-series wss url")
    parser.add_argument("--zone", dest='zone', default='', help="time-series service instance id")
    parser.add_argument("--uaa", dest='uaa', default='', help="predix UAA issuerId (Token URI)")
    parser.add_argument("--client", dest='client', default='', help="predix UAA Client")
    parser.add_argument("--secret", dest='secret', default='', help="predix UAA Client secret")
    parser.add_argument("--username", dest='username', default='', help="username from Predix UAA with access to time-series")
    parser.add_argument("--password", dest='password', default='', help="password from Predix UAA with access to time-series")
    parser.add_argument("--token", dest='token', default='', help="specify the predix UAA token with access to time-series")
    parser.add_argument("-d", "--delimiter", dest='delimiter', default=';', help="specify the delimiter character. Default is ;")
    parser.add_argument("-t", "--timestamp", dest='timestamp', default="%m/%d/%Y %I:%M:%S %p", help="specify the timestamp format following strftime(3) documentation")
    parser.add_argument("-s", "--datapoints", dest='dpsize', default='500', help="specify the number of points per message")
    parser.add_argument("--ei", dest='eni', default='1', help="specify the index of the equipment name column in the csv")
    parser.add_argument("--ti", dest='tni', default='2', help="specify the index of the tag name column in the csv")
    parser.add_argument("--di", dest='tsi', default='3', help="specify the index of the timestamp column in the csv")
    parser.add_argument("--vi", dest='vi', default='4', help="specify the index of the value column in the csv")
    parser.add_argument("-c", dest='concat', default='_', help="specify the character used in the concatenation for the meter name")
    parser.add_argument("-k", dest='skipmeter', default='-1', help="specify the index for the meter name. (Don't need to specify equipment and tag columns)")
    parser.add_argument("-y", dest='yaml', default='', help="specify a yaml file with the configuration")
    args = parser.parse_args()

    files = args.data
    tsUri = args.tss
    tsZone = args.zone
    uaaUri = args.uaa
    uaaUsername = args.username
    uaaSecret = args.secret
    uaaClient = args.client
    uaaPassword = args.password
    uaaToken = args.token
    delimiter = args.delimiter
    timestamp = args.timestamp
    dpsize = int(args.dpsize)
    eni = int(args.eni)
    tni = int(args.tni)
    tsi = int(args.tsi)
    vi = int(args.vi)
    yamlFile = args.yaml
    concat = args.concat
    metername = int(args.skipmeter)

    #Check if input is a file/list of files or a folder
    #If csv files pass it along
    if files[0][len(files[0])-4:len(files[0])] == '.csv':
        iterfiles = files
    #If folder, get folder files and pass only csv files
    else:
        iterfiles = []
        tempFiles = os.listdir(files[0])
        for f in tempFiles:
            try:
                fExt = os.path.splitext(f)[1]
                if fExt == '.csv':
                    iterfiles.append(os.path.join(files[0],f))
            except:
                continue
        
    for data in iterfiles:
        filename = os.path.split(data)[1]
        PAYLOADS = []
        print("Ingesting file: " + data)
        tsUri, tsZone, uaaToken, uaaUri, uaaClient, uaaSecret, uaaUsername, uaaPassword, delimiter, timestamp, dpsize, eni, tni, tsi, vi, concat, metername =  loadFromYaml(yamlFile, tsUri, tsZone, uaaToken, uaaUri, uaaClient, uaaSecret, uaaUsername, uaaPassword, delimiter, timestamp, dpsize, eni, tni, tsi, vi, concat, metername, filename)
        PAYLOADS = prepareData(PAYLOADS, tsUri, tsZone, uaaToken, uaaUri, uaaClient, uaaSecret, uaaUsername, uaaPassword, delimiter, timestamp, dpsize, eni, tni, tsi, vi, concat, metername)
        openWSS(uaaToken, uaaUsername, uaaPassword, uaaClient, uaaSecret, tsUri)
    print("All " + str(len(files)) + " files ingested")
