import os as OS
import os
import sys
import time
import datetime

import boto3
import botocore

import glob
import sh
import shutil
import re
import json
import simplejson
import decimal

import smtplib
import syslog
import subprocess

from pymongo import MongoClient

from sh import aws
from sh import mongoimport
from sh import mongoexport
#import pandas as pd
import psycopg2
import ast

import ConfigParser

reload(sys)
sys.setdefaultencoding('UTF8')

def sendSyslog(msg):
     syslog.syslog('MOGEAN-DATA-ENHANCEMENT (' + sys.argv[1] + '): ' + msg)

def sendFailureNote(msg):
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('support@mogean.com', 'Bug3Bug4Bug5')
    msg = '\nMOGEAN-DATA-ENHANCEMENT (' + sys.argv[1] + ')' + msg
    for phone in phoneList:
        server.sendmail('support@mogean.com', phone, msg)

def getEnvVarValue(envVar):
    tmpVal = os.getenv(envVar)
    if not tmpVal:
        print("Environment variable: [%s] not set." % (envVar))
        sys.exit(1)
    env = tmpVal.strip("'") 
    return env

environment = getEnvVarValue('env')

if environment == 'production':
    phoneList = ['4083943360@txt.att.net', 'reid@mogean.com',
             'appdevmasters@prosperasoft.com']
    # Initialize boto3 and aws sh connectors
    boto3.setup_default_session(profile_name = 'mogean')
    s3 = boto3.client('s3')
    emr = boto3.client('emr')
    s3cli = aws.bake('--profile', 'mogean', 's3')
    firehose = boto3.client('firehose')
else:
    phoneList = ['prospera-user10@gmail.com']

def checkS3Buckets():
    sendSyslog('Testing for S3 buckets being present....Checking!')
    try:
        response = s3.head_bucket(Bucket = EMR_BOOTSTRAP_BUCKET)
        response = s3.head_bucket(Bucket = EMR_CODE_BUCKET)
        response = s3.head_bucket(Bucket = EMR_LOGS_BUCKET)
        response = s3.head_bucket(Bucket = EMR_MISC_BUCKET)
        response = s3.head_bucket(Bucket = LASTPOINTS_BUCKET)
        response = s3.head_bucket(Bucket = FIREHOSE_PRIMARY_STREAM)
        response = s3.head_bucket(Bucket = OUTPUT_BUCKET)
        response = s3.head_bucket(Bucket = BEACON_BUCKET)
        response = s3.head_bucket(Bucket = LOCATION_BUCKET)
        response = s3.head_bucket(Bucket = PROCESSED_STREAM_BUCKET)
        response = s3.head_bucket(Bucket = PROCESSING_STREAM_BUCKET)
        response = s3.head_bucket(Bucket = FIREHOSE_SECONDARY_STREAM)
    except botocore.exceptions.ClientError as e:
        error_code = int(e.response['ResponseMetadata']['HTTPStatusCode'])
        if error_code == 403 or error_code == 404:
            sendSyslog('Necessary S3 buckets don\'t exist...Exiting!')
            sendFailureNote('Necessary S3 buckets don\'t' +
                            ' exist...Exiting!')
            sys.exit()
    sendSyslog('All S3 buckets SUCCEEDED checks...Continuing!')

def getFirehoseStream(streamName):
    try:
        response = firehose.describe_delivery_stream(
            DeliveryStreamName = streamName
            )
    except botocore.exceptions.ClientError as e:
        sendSyslog('Get firehose stream detail FAILED...Exiting!')
        sendFailureNote('Get firehose stream detail FAILED...Exiting!')
        sys.exit()
    return response['DeliveryStreamDescription']

def switchFirehoseStreamDestination(streamName):
    stream = getFirehoseStream(streamName)

    destId = stream['Destinations'][0]['DestinationId']
    s3Dest = stream['Destinations'][0]['S3DestinationDescription']
    if s3Dest['BucketARN'].endswith(FIREHOSE_PRIMARY_STREAM):
        s3Dest['BucketARN'] = FIREHOSE_SECONDARY_S3_ARN
    else:
        s3Dest['BucketARN'] = FIREHOSE_PRIMARY_S3_ARN

    try:
        response = firehose.update_destination(
                       DeliveryStreamName = stream['DeliveryStreamName'],
                       CurrentDeliveryStreamVersionId = stream['VersionId'],
                       DestinationId = destId,
                       S3DestinationUpdate = s3Dest
                       )
    except botocore.exceptions.ClientError as e:
        sendSyslog('Update firehose stream destination FAILED...Exiting!')
        sendFailureNote('Update firehose stream destination FAILED...Exiting!')
        sys.exit()

    # Stream switching can take up to 5 minutes. WAIT!
    # Return the bucket stream was PREVIOUSLY filling
    time.sleep(FIREHOSE_SWITCH_WAIT)
    if s3Dest['BucketARN'].endswith(FIREHOSE_SECONDARY_STREAM):
        return FIREHOSE_PRIMARY_STREAM
    else:
        return FIREHOSE_SECONDARY_STREAM

def prepareInputData():
    sendSyslog('Update firehose stream destination processing...Checking!')
    inputStreamBucket = switchFirehoseStreamDestination(FIREHOSE_STREAM_NAME)
    sendSyslog('Update firehose stream destination SUCCEEDED...Continuing!')

    sendSyslog('Moving data from input to processing...Checking!')
    response = s3cli.sync('s3://' + inputStreamBucket,
                          's3://' + PROCESSING_STREAM_BUCKET)
    if response.exit_code:
        sendSyslog('S3 sync FAILED from input to processing bucket...Exiting!')
        sendFailureNote('S3 sync FAILED from input to processing bucket' +
                        '...Exiting!')
        sys.exit()

    sendSyslog('S3 sync SUCCEEDED from input to processing bucket' +
               '...Continuing!')
    response = s3cli.rm('--recursive', 's3://' + inputStreamBucket)
    if response.exit_code:
        sendSyslog('S3 remove FAILED on input bucket...Exiting!')
        sendFailureNote('S3 remove FAILED on input bucket...Exiting!')
        sys.exit()
    sendSyslog('S3 remove SUCCEEDED on input bucket...Continuing!')

def archiveInputData(keepData = True):
    if environment == 'production':
        if keepData:
            sendSyslog('Moving data from processing to processed...Checking!')
            response = s3cli.sync('s3://' + PROCESSING_STREAM_BUCKET,
                                's3://' + PROCESSED_STREAM_BUCKET + '/' +
                                (str(datetime.datetime.now())
                                 .replace(' ', ':').replace(':', '-')))
            if response.exit_code:
                sendSyslog('S3 sync FAILED from processing to processed bucket' +
                           '...Exiting!')
                sendFailureNote('S3 sync FAILED from processing to processed' +
                                ' bucket...Exiting!')
                sys.exit()

        sendSyslog('S3 sync SUCCEEDED from processing to processed bucket' +
                   '...Continuing!')
        response = s3cli.rm('--recursive', 's3://' + PROCESSING_STREAM_BUCKET)
        if response.exit_code:
            sendSyslog('S3 remove FAILED on processing bucket...Exiting!')
            sendFailureNote('S3 remove FAILED on processing bucket...Exiting!')
            sys.exit()
        sendSyslog('S3 remove SUCCEEDED on processing bucket...Continuing!')
    else:
        if keepData:
            sendSyslog('MOGEAN-DATA-ENHANCEMENT: Moving data from processing to processed...Checking!')
            response = shutil.copytree(LOCAL_BASE_FOLDER + '/' +PROCESSING_STREAM_BUCKET,
                                LOCAL_BASE_FOLDER + '/' + PROCESSED_STREAM_BUCKET + '/' +
                                (str(datetime.datetime.now())
                                 .replace(' ', ':').replace(':', '-')))
        sendSyslog('MOGEAN-DATA-ENHANCEMENT: S3 sync SUCCEEDED from processing to processed bucket...Continuing!')


def prepareRerunData():
    sendSyslog('Moving data from processed to processing...Checking!')
    response = s3cli.sync('s3://' + PROCESSED_STREAM_BUCKET,
                          's3://' + PROCESSING_STREAM_BUCKET)
    if response.exit_code:
        sendSyslog('S3 sync FAILED from processed to processing bucket' +
                   '...Exiting!')
        sendFailureNote('S3 sync FAILED from processed to processing bucket' +
                        '...Exiting!')
        sys.exit()
    sendSyslog('S3 sync SUCCEEDED from input to processing bucket' +
               '...Continuing!')

def writeStepOutputToRDS(s3FolderName, mongoFolderName,
                         successBucket, errorBucket):
    sendSyslog('Parameters:')
    sendSyslog('s3FolderName: ' + s3FolderName)
    sendSyslog('mongoFolderName: ' + mongoFolderName)
    sendSyslog('successBucket: ' + successBucket)
    sendSyslog('errorBucket: ' + errorBucket)
    sendSyslog('Creating Postgres connection object..Continuing')
    try:
        conn = psycopg2.connect(database=RDS_DB, user=RDS_USER,
                                password=RDS_PASSWORD, host=RDS_HOST,
                                port=RDS_PORT)
        cur = conn.cursor()
        sendSyslog('Connection object creation successful')
    except:
        sendSyslog('Connection object creation failed. Hence exiting!')
        sys.exit()

    if environment == 'production':
        date = '-'.join(s3FolderName.split('/')[3].split('-')[2:5])
    else:
        date = '-'.join(s3FolderName.split('/')[6].split('-')[2:5])
    sendSyslog('DATE: ' + str(date))
    outputBucket = '/'.join(s3FolderName.split('/')[2:])
    sendSyslog('outputBucket: ' + str(outputBucket))
    ERRORED_FILES = []

    if environment == 'production':
        response = s3cli.cp('--recursive', s3FolderName, mongoFolderName)
        if response.exit_code:
            sendSyslog('S3 copy FAILED on output to local folder name...!')
            sendFailureNote('S3 copy FAILED on output to local folder...!')
    else:
        try:
            shutil.rmtree(mongoFolderName)
            response = shutil.copytree(s3FolderName,mongoFolderName)
        except IOError, e:
            sendSyslog("Unable to copy file. %s" % e)
    fileList = glob.glob(mongoFolderName + '/part*')
    fileList = sorted(fileList)
    sendSyslog('FileList: ' + str(fileList))

    for file in fileList:
        filename = file.split('/')[6]
        sendSyslog('Sending data from file: ' + file + ' to RDS started')
        try:
            with open(file) as f:
                for line in f:
                    line = line.replace('"adTrackingEnabled":true',
                                        '"adTrackingEnabled":True')
                    line = line.replace('"adTrackingEnabled":false',
                                        '"adTrackingEnabled":False')
                    l = ast.literal_eval(line)
                    columns = []
                    for key,val in l.items():
                        columns.append(key)            
                    _id = l['_id']
                    adId = l['adId']
                    adTrackingEnabled = l['adTrackingEnabled']
                    if 'carrier' in columns:
                        carrier = l['carrier']
                    createdAt = l['createdAt']
                    deviceModel = l['deviceModel']
                    eventType = l['eventType']
                    loc = json.dumps(l['loc'])
                    location = json.dumps(l['location'])
                    os = l['os']
                    osVer = l['osVer']
                    peelID = l['peelID']
                    pktId = l['pktId']
                    sdkVer = l['sdkVer']
                    timestamp = l['timestamp']
                    type = l['type']
                    ver = l['ver']
                    isFirstDataPoint = l['isFirstDataPoint']
                    query = '''INSERT INTO lastpoints("_id", "adId", "adTrackingEnabled", "carrier", "createdAt", "deviceModel",
                               "eventType", "loc", "location", "os", "osVer", "peelID", "pktId", "sdkVer", "timestamp", "type", 
                               "ver", "isFirstDataPoint") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) 
                               ON CONFLICT (_id)  DO UPDATE SET 
                                 "adId" = EXCLUDED."adId",
                                 "adTrackingEnabled" = EXCLUDED."adTrackingEnabled",
                                 "carrier" = EXCLUDED."carrier",
                                 "createdAt" = EXCLUDED."createdAt",
                                 "deviceModel" = EXCLUDED."deviceModel",
                                 "eventType" = EXCLUDED."eventType",
                                 "loc" = EXCLUDED."loc",
                                 "location" = EXCLUDED."location",
                                 "os" = EXCLUDED."os",
                                 "osVer" = EXCLUDED."osVer",
                                 "peelID" = EXCLUDED."peelID",
                                 "pktId" = EXCLUDED."pktId",
                                 "sdkVer" = EXCLUDED."sdkVer",
                                 "timestamp" = EXCLUDED."timestamp",
                                 "type" = EXCLUDED."type",
                                 "ver" = EXCLUDED."ver",
                                 "isFirstDataPoint" = EXCLUDED."isFirstDataPoint"'''
                    data = (_id, adId, adTrackingEnabled, carrier, createdAt, deviceModel, eventType, loc, location, 
                             os, osVer, peelID, pktId, sdkVer, timestamp, type, ver, isFirstDataPoint,)
                    cur.execute(query, data)
            conn.commit()
            sendSyslog('Sending data from file: ' + file + ' to RDS completed')
            sendSyslog('Environment: ' + environment)
            if environment == 'production':
                sendSyslog('Copying file ' + file + ' to ' + successBucket +
                           ' bucket')
                response = s3cli.cp(s3FolderName + '/' + filename, 's3://' +
                                    successBucket + '/' + date + '/'+
                                    filename + '-' +
                                    (str(datetime.datetime.now())
                                     .replace(' ', ':').replace(':', '-')))
                if response.exit_code:
                    sendSyslog('S3 copy FAILED for file ' + filename +
                               ' from output bucket ' + outputBucket +
                               ' to success bucket '+successBucket)
                    sendFailureNote('S3 copy FAILED for file ' + filename +
                                    ' from output bucket ' + outputBucket +
                                    ' to success bucket ' + successBucket)
            else:
                sendSyslog("Copying file " + file + " to " + LOCAL_BASE_FOLDER + '/' + successBucket + 
                           " bucket")
                try:
                    if not OS.path.isdir(LOCAL_BASE_FOLDER + '/' + successBucket + "/"+date):
                        OS.mkdir(LOCAL_BASE_FOLDER + '/' + successBucket + "/"+date)
                    response = shutil.copy2(s3FolderName + "/" + filename, LOCAL_BASE_FOLDER + 
                                            '/' + successBucket + "/"+date+"/"+
                                            filename+"-"+
                                            (str(datetime.datetime.now())
                                             .replace(' ', ':').replace(':', '-')))
                except e:
                    sendSyslog("Unable to copy file. %s" % e)
                    sendSyslog('S3 copy FAILED for file ' + filename + 
                               ' from output bucket ' + outputBucket + 
                               ' to success bucket '+ LOCAL_BASE_FOLDER + '/' +successBucket)
                    sendFailureNote('S3 copy FAILED for file ' + filename + 
                                    ' from output bucket ' + outputBucket + 
                                    ' to success bucket '+ LOCAL_BASE_FOLDER + '/' +successBucket)
                    sys.exit(1)
        except:
            ERRORED_FILES.append( filename )
            sendSyslog('RDS Import failed for file: ' + file)
            if environment == 'production':
                sendSyslog('Copying file ' + file + ' to ' + errorBucket +
                           ' bucket')
                response = s3cli.cp(s3FolderName + '/' + filename, 's3://' +
                                    errorBucket + '/' + date + '/' + filename +
                                    '-' + (str(datetime.datetime.now())
                                           .replace(' ', ':').replace(':', '-')))

                if response.exit_code:
                    sendSyslog('S3 copy FAILED for file ' + filename +
                               ' from output bucket ' + outputBucket +
                               ' to error bucket '+errorBucket)
                    sendFailureNote('S3 copy FAILED for file ' + filename +
                                    ' from output bucket ' + outputBucket +
                                    ' to error bucket '+errorBucket)
            else:
                sendSyslog("Copying file " + file + " to " + LOCAL_BASE_FOLDER + '/' + errorBucket + 
                           " bucket")
                try:
                    if not OS.path.isdir(LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date):
                        OS.mkdir(LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date)
                    response = shutil.copy2(s3FolderName + '/' + filename, LOCAL_BASE_FOLDER + '/' + 
                                            errorBucket + '/'+date+"/"+filename+
                                            "-"+(str(datetime.datetime.now())
                                                .replace(' ', ':').replace(':', '-')))
                except IOError,e:
                    sendSyslog('S3 copy FAILED for file ' + filename + 
                               ' from output bucket ' + LOCAL_BASE_FOLDER + '/' + outputBucket + 
                               ' to error bucket '+ LOCAL_BASE_FOLDER + '/' +errorBucket)
                    sendFailureNote('S3 copy FAILED for file ' + filename + 
                                    ' from output bucket ' + LOCAL_BASE_FOLDER + '/' + outputBucket + 
                                    ' to error bucket '+ LOCAL_BASE_FOLDER + '/' +errorBucket)        
    if len(ERRORED_FILES) > 0:
        failedFiles = ','.join(ERRORED_FILES)
        sendSyslog('RDS import FAILED for files ' + failedFiles +
                   ' for output bucket ' + outputBucket)
        sendFailureNote('RDS import FAILED for files ' + failedFiles +
                        ' for output bucket ' + outputBucket)
    cur.close()
    conn.close()
    sendSyslog('Removing files from local folder on host server')
    shutil.rmtree(mongoFolderName)
    sendSyslog('RDS import SUCCEEDED on all output files...Continuing!')

def writeStepOutputToRDSFirstpoints(s3FolderName, mongoFolderName):
    sendSyslog('Parameters:')
    sendSyslog('s3FolderName: ' + s3FolderName)
    sendSyslog('mongoFolderName: ' + mongoFolderName)    
    sendSyslog('Creating Postgres connection object..Continuing')

    try:
        conn = psycopg2.connect(database=RDS_DB, user=RDS_USER,
                                password=RDS_PASSWORD, host=RDS_HOST,
                                port=RDS_PORT)
        cur = conn.cursor()
        sendSyslog('Connection object creation successful')
    except:
        sendSyslog('Connection object creation failed. Hence exiting!')
        sys.exit()

    if environment == 'production':
        date = '-'.join(s3FolderName.split('/')[3].split('-')[2:5])
    else:
        date = '-'.join(s3FolderName.split('/')[6].split('-')[2:5])
    sendSyslog('DATE: ' + str(date))
    outputBucket = '/'.join(s3FolderName.split('/')[2:])
    sendSyslog('outputBucket: ' + str(outputBucket))

    if environment == 'production':
        response = s3cli.cp('--recursive', s3FolderName, mongoFolderName)
        if response.exit_code:
            sendSyslog('S3 copy FAILED on output to local folder name...!')
    else:
        try:
            shutil.rmtree(mongoFolderName)
            response = shutil.copytree(s3FolderName,mongoFolderName)
        except IOError, e:
            sendSyslog("Unable to copy file. %s" % e)
    fileList = glob.glob(mongoFolderName + '/part*')
    fileList = sorted(fileList)
    sendSyslog('FileList: ' + str(fileList))

    sendSyslog('Creating a single firstpoints loadfile...Continuing')
    with open(mongoFolderName + '/part#00000' , 'wb') as outfile:
        for f in fileList:
            with open(f, 'rb') as infile:
                outfile.write(infile.read())
    sendSyslog('Creation of single loadfile is successful...Continuing')

    fileList = glob.glob(mongoFolderName + '/part#*')
    fileList = sorted(fileList)
    sendSyslog('FileList: ' + str(fileList))

    for file in fileList:
        filename = file.split('/')[6]
        sendSyslog('Sending data from file: ' + file +
                   ' to RDS firstpoints table started')
        try:
            with open(file) as f:
                for line in f:
                    line = line.replace('"adTrackingEnabled":true',
                                        '"adTrackingEnabled":True')
                    line = line.replace('"adTrackingEnabled":false',
                                        '"adTrackingEnabled":False')
                    l = ast.literal_eval(line)
                    _id = l['_id']
                    adId = l['adId']
                    customerID = l['customerID']
                    timestamp = l['timestamp']
                    l = json.dumps(l)
                    query = '''INSERT INTO firstpoints("_id", "customerID", "adId", "timestamp", "datapoint") 
                               VALUES (%s,%s,%s,%s,%s) 
                               ON CONFLICT (_id) 
                               DO UPDATE SET 
                                 "adId" = EXCLUDED."adId",
                                 "customerID" = EXCLUDED."customerID",
                                 "timestamp" = EXCLUDED."timestamp",
                                 "datapoint" = EXCLUDED."datapoint"'''
                    data = (_id, customerID, adId, timestamp, l,)
                    cur.execute(query, data)
            conn.commit()
            sendSyslog('Sending data from file: ' + file +
                       ' to RDS firstpoints table completed')
        except:
            sendSyslog('RDS firstpoints table Import failed for file: ' + file)
            sendFailureNote('RDS firstpoints table Import failed ' +
                                    'for file: ' + file +
                                    ' for s3FolderName: ' + s3FolderName)
    cur.close()
    conn.close()

    sendSyslog('Removing files from local folder on host server')
    shutil.rmtree(mongoFolderName)
    sendSyslog('Creating Local mongo folder...')
    os.makedirs(mongoFolderName)
    sendSyslog('RDS import SUCCEEDED on all output files...Continuing!')

def splitBigESFiles(path, s3FolderName, lines):
    sendSyslog('Inside splitBigESFiles function...')
    fileList = glob.glob(path+'/part#*')
    sendSyslog('FileList: ' + str(fileList))
    for file in fileList:
        filename = file.split('/')[6]
        size = os.path.getsize(file)/(1024*1024)
        if size >= 100:
            sendSyslog('Splitting ES output file ' + file)
            os.chdir(path)
            cmd = ('split -l ' + str(lines) + ' -d ' + file + ' ' +
                   filename + '-')
            try:
                subprocess.check_call(cmd, shell=True)
                os.remove(file)
            except:
                sendSyslog('Failed to split ES output file ' + filename)

            os.chdir('/home/ec2-user')
            sendSyslog('Splitting of file ' + file + ' is completed')


def writeStepOutputToES(s3FolderName, mongoFolderName,
                        successBucket, errorBucket):
    sendSyslog('Parameters:')
    sendSyslog('s3FolderName: ' + s3FolderName)
    sendSyslog('mongoFolderName: ' + mongoFolderName)
    sendSyslog('successBucket: ' + successBucket)
    sendSyslog('errorBucket: ' + errorBucket)

    if environment == 'production':
        date = '-'.join(s3FolderName.split('/')[3].split('-')[1:4])
    else:
        date = '-'.join(s3FolderName.split('/')[6].split('-')[1:4])
    sendSyslog('DATE: ' + str(date))
    outputBucket = '/'.join(s3FolderName.split('/')[2:])
    sendSyslog('outputBucket: ' + str(outputBucket))
    ERRORED_FILES = []

    if environment == 'production':
        response = s3cli.cp('--recursive', s3FolderName, mongoFolderName)
        if response.exit_code:
            sendSyslog('S3 copy FAILED on output to local folder name...!')
            sendFailureNote('S3 copy FAILED on output to local folder...!')
    else:
        try:
            shutil.rmtree(mongoFolderName)
            response = shutil.copytree(esOutputFolderName,LOCAL_MONGO_FOLDER)
        except IOError, e:
            sendSyslog( "Unable to copy file. %s" % e)
            sys.exit(1)
    fileList = glob.glob(mongoFolderName + '/part*')
    fileList = sorted(fileList)
    sendSyslog('FileList: ' + str(fileList))

    sendSyslog('Creating a single ES loadfile...Continuing')
    with open(mongoFolderName + '/part#00000' , 'wb') as outfile:
        for f in fileList:
            with open(f, 'rb') as infile:
                outfile.write(infile.read())
    sendSyslog('Creation of single ES loadfile is successful...Continuing')
    splitBigESFiles(mongoFolderName, s3FolderName, 30000)
    fileList = glob.glob(mongoFolderName + '/part#*')
    fileList = sorted(fileList)
    sendSyslog('FileList: ' + str(fileList))

    for file in fileList:
        filename = file.split('/')[6]
        sendSyslog('Sending data from file: ' + file + ' to ES started')
        res = subprocess.check_output('curl -XPOST -s ' + ES_URL +
                                      ' --data-binary @' + file, shell=True)
        if res:
            if simplejson.loads(res).has_key('errors'):
                if simplejson.loads(res)['errors'] == True:
                    ERRORED_FILES.append( filename )
                    sendSyslog('ES Import failed for file: ' + file)
                    if environment == 'production':
                        sendSyslog('Copying file ' + file + ' to ' +
                                   errorBucket + ' bucket')
                        response = s3cli.cp(file, 's3://' + errorBucket +
                                            '/' + date + '/' + filename + '-' +
                                            (str(datetime.datetime.now())
                                             .replace(' ', ':').replace(':', '-')))
                        if response.exit_code:
                            sendSyslog('S3 copy FAILED for file ' + filename +
                                       ' from local folder ' + mongoFolderName +
                                       ' to error bucket ' + errorBucket)
                            sendFailureNote('S3 copy FAILED for file ' +
                                            filename + ' from local folder ' +
                                            mongoFolderName + ' to error bucket ' +
                                            errorBucket)
                    else:
                        sendSyslog("Copying file " + file + " to " +
                                   LOCAL_BASE_FOLDER + '/' + errorBucket + " bucket")
                        try:
                            if not os.path.exists(LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date):
                                os.mkdir(LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date)
                            response = shutil.copy(file, LOCAL_BASE_FOLDER + '/' + errorBucket +
                                                   "/"+date+"/"+filename+"-"+
                                                   (str(datetime.datetime.now())
                                                    .replace(' ', ':').replace(':', '-')))
                        except IOError,e:
                            sendSyslog("Unable to copy file. %s" % e)
                            sendSyslog('S3 copy FAILED for file ' + filename + 
                                       ' from local folder ' + mongoFolderName + 
                                       ' to error bucket '+ LOCAL_BASE_FOLDER + '/' +
                                        errorBucket)
                            sendFailureNote('S3 copy FAILED for file ' + 
                                            filename + ' from local folder ' +
                                            mongoFolderName + ' to error bucket '+
                                             LOCAL_BASE_FOLDER + '/' + errorBucket)
                else:
                    sendSyslog('Sending data from file: ' + file +
                               ' to ES completed')
                    if environment == 'production':
                        sendSyslog('Copying file ' + file + ' to ' +
                                   successBucket + ' bucket')
                        response = s3cli.cp(file, 's3://' + successBucket + '/' +
                                            date + '/' + filename + '-' +
                                            (str(datetime.datetime.now())
                                             .replace(' ', ':').replace(':', '-')))
                        if response.exit_code:
                            sendSyslog('S3 copy FAILED for file ' + filename +
                                       ' from local folder ' + mongoFolderName +
                                       ' to success bucket ' + successBucket)
                            sendFailureNote('S3 copy FAILED for file ' + filename +
                                            ' from local folder ' +
                                            mongoFolderName +
                                            ' to success bucket ' + successBucket)
                    else:
                        sendSyslog("Copying file " + file + " to " + LOCAL_BASE_FOLDER + '/' + 
                                    successBucket + " bucket")
                        try:
                            if not os.path.exists(LOCAL_BASE_FOLDER + '/' + successBucket + "/"+date):
                                os.mkdir(LOCAL_BASE_FOLDER + '/' + successBucket + "/"+date)
                            response = shutil.copy(file, LOCAL_BASE_FOLDER + '/' 
                                                   + successBucket + "/"+
                                                   date+"/"+filename+"-"+
                                                   (str(datetime.datetime.now())
                                                    .replace(' ', ':').replace(':', '-')))
                        except IOError,e:
                            sendSyslog("Unable to copy file. %s" % e)
                            sendSyslog('S3 copy FAILED for file ' + filename + 
                                       ' from local folder ' + mongoFolderName + 
                                       ' to success bucket '+ LOCAL_BASE_FOLDER + '/' + successBucket)
                            sendFailureNotification('S3 copy FAILED for file ' + filename + 
                                                    ' from local folder ' + mongoFolderName +
                                                     ' to success bucket '+ LOCAL_BASE_FOLDER + '/' + successBucket)
            else:
                sendSyslog('ES Import failed for file: ' + file +
                           ' . CURL response does not have key ERROR')
                if environment == 'production':
                    sendSyslog('Copying file ' + file + ' to ' + errorBucket +
                               ' bucket')
                    response = s3cli.cp(file, 's3://' + errorBucket + '/' + date +
                                        '/' + filename + '-' +
                                        (str(datetime.datetime.now())
                                         .replace(' ', ':').replace(':', '-')))
                    if response.exit_code:
                        sendSyslog('S3 copy FAILED for file ' + filename +
                                   ' from local folder ' + mongoFolderName +
                                   ' to error bucket '+errorBucket)
                        sendFailureNote('S3 copy FAILED for file ' + filename +
                                        ' from local folder ' + mongoFolderName +
                                        ' to error bucket ' + errorBucket)
                else:
                    sendSyslog("Copying file " + file + " to " + LOCAL_BASE_FOLDER + '/' +errorBucket +
                               " bucket")
                    try:
                        if not os.path.exists(LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date):
                            os.mkdir(LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date)
                        response = shutil.copy(file, LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date+
                                              "/"+filename+"-"+
                                              (str(datetime.datetime.now())
                                               .replace(' ', ':').replace(':', '-')))
                    except IOError,e:
                        sendSyslog("Unable to copy file. %s" % e)
                        sendSyslog('S3 copy FAILED for file ' + filename +
                                   ' from local folder ' + mongoFolderName + 
                                   ' to error bucket '+ LOCAL_BASE_FOLDER + '/' + errorBucket)
                        sendFailureNotification('S3 copy FAILED for file ' + filename + 
                                                ' from local folder ' + mongoFolderName + 
                                                ' to error bucket '+ LOCAL_BASE_FOLDER + '/' + errorBucket)
        else:
            sendSyslog('ES Import failed for file: ' + file +
                       ' . CURL command did not return any response')
            if environment == 'production':
                sendSyslog('Copying file ' + file + ' to ' + errorBucket +
                           ' bucket')
                response = s3cli.cp(file, 's3://' + errorBucket + '/' + date +
                                    '/' + filename + '-' +
                                    (str(datetime.datetime.now())
                                     .replace(' ', ':').replace(':', '-')))
                if response.exit_code:
                    sendSyslog('S3 copy FAILED for file ' + filename +
                               ' from local folder ' + mongoFolderName +
                               ' to error bucket '+errorBucket)
                    sendFailureNote('S3 copy FAILED for file ' + filename +
                                    ' from local folder ' + mongoFolderName +
                                    ' to error bucket '+errorBucket)
            else:
                sendSyslog("Copying file " + file + " to " + LOCAL_BASE_FOLDER + '/' + errorBucket + " bucket")
                try:
                    if not os.path.exists(LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date):
                        os.mkdir(LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date)
                    response = shutil.copy(file, LOCAL_BASE_FOLDER + '/' + errorBucket + "/"+date+
                                            "/"+filename+"-"+
                                            (str(datetime.datetime.now())
                                            .replace(' ', ':').replace(':', '-')))            
                except IOError,e:
                    sendSyslog("Unable to copy file. %s" % e)
                    sendSyslog('S3 copy FAILED for file ' + filename + 
                               ' from local folder ' + mongoFolderName + 
                               ' to error bucket '+ LOCAL_BASE_FOLDER + '/' + errorBucket)
                    sendFailureNote('S3 copy FAILED for file ' + filename + 
                                    ' from local folder ' + mongoFolderName +
                                    ' to error bucket '+ LOCAL_BASE_FOLDER + '/' + errorBucket)
    if len(ERRORED_FILES) > 0:
        failedFiles = ','.join(ERRORED_FILES)
        sendSyslog('ES import FAILED for files ' + failedFiles +
                   ' for output bucket ' + outputBucket)
        sendFailureNote('ES import FAILED for files ' + failedFiles +
                        ' for output bucket ' + outputBucket)

    sendSyslog('Deleting Local mongo folder...')
    shutil.rmtree(mongoFolderName)
    sendSyslog('Creating Local mongo folder...')
    os.makedirs(mongoFolderName)
    sendSyslog('ES import SUCCEEDED on all output files...Continuing!')

# Instance definitions and configurations. Using spot instances with bid.
def createInstanceGroups():
    instanceGroups = []
    instanceGroups.append(
        {
            'Name': 'Master instance group - 1',
            'Market': 'ON_DEMAND',
            'InstanceRole': 'MASTER',
            'InstanceType': 'm4.xlarge',
            'InstanceCount': 1,
        })
    instanceGroups.append(
        {
            'Name': 'Core instance group - 2',
            'Market': 'ON_DEMAND',
            'InstanceRole': 'CORE',
            'InstanceType': 'm4.xlarge',
            'InstanceCount': 2,
        })
    return instanceGroups

def emrCreateCluster():
    instanceGroups = createInstanceGroups()
    clusterName = re.search('production', sys.argv[1])
    if clusterName is None:
        clusterName = re.search('test', sys.argv[1]).group(0)
    else:
        clusterName = clusterName.group(0)
    
    try:
        emrCreateResponse = emr.run_job_flow(
            Name = 'mogean-dataenhancement-' + clusterName,
            LogUri = 's3n://' + EMR_LOGS_BUCKET,
            ReleaseLabel = 'emr-4.7.2',
            Instances = {
                'InstanceGroups': instanceGroups,
                'Ec2KeyName': EC2_KEY,
                'KeepJobFlowAliveWhenNoSteps': True,
                'TerminationProtected': True,
                'Ec2SubnetId': EC2_SUBNET_ID
            },
            BootstrapActions = [
                {
                    'Name': 'Custom action',
                    'ScriptBootstrapAction': {
                        'Path': ('s3://' + EMR_BOOTSTRAP_BUCKET +
                                 EMR_BOOTSTRAP_FILE),
                    }
                },
            ],
            Applications = [
                {
                    'Name': 'Hadoop',
                },
                {
                    'Name': 'Hive',
                },
                {
                    'Name': 'Pig',
                },
                {
                    'Name': 'Hue',
                },
                {
                    'Name': 'Spark',
                }
            ],
            VisibleToAllUsers = True,
            JobFlowRole = 'EMR_EC2_DefaultRole',
            ServiceRole = 'EMR_DefaultRole',
        )
    except botocore.exceptions.ClientError as e:
        sendSyslog('Create cluster FAILED...Exiting!')
        sendFailureNote('Create cluster FAILED...Exiting!')
        sys.exit()

    sendSyslog('EMR cluster status...Checking!')
    emrClusterStatus = emrCheckClusterStatus(emrCreateResponse['JobFlowId'])
    assert(emrClusterStatus['Cluster']['Status']['State'] == 'WAITING')

    sendSyslog('Create cluster SUCCEEDED...Continuing!')
    return emrCreateResponse['JobFlowId']

def emrAddStep(jobFlowId, outputFolderName,
               lastpointsFolderName, beaconFolderName, esOutputFolderName,
               locationFolderName, esLastpointsFolderName,
               clusteringFolderName, firstpointsFolderName,
               commuteFolderName, rerun = False):
    sendSyslog('Adding EMR Step to cluster...Checking!')
    sendSyslog('Adding output folder name: ' + outputFolderName +
               '...Continuing!')
    sendSyslog('Adding beacon folder name: ' + beaconFolderName +
               '...Continuing!')
    sendSyslog('Adding es folder name: ' + esOutputFolderName +
               '...Continuing!')
    sendSyslog('Adding location folder name: ' + locationFolderName +
               '...Continuing!')
    sendSyslog('Adding ES-LASTPOINTS folder name: ' + esLastpointsFolderName +
               '...Continuing!')
    sendSyslog('Adding CLUSTERING folder name: ' + clusteringFolderName +
               '...Continuing!')
    sendSyslog('Adding COMMUTE folder name: ' + commuteFolderName +
               '...Continuing!')
    sendSyslog('Adding FIRSTPOINTS folder name: ' + firstpointsFolderName +
               '...Continuing!')
    try:
        if environment == 'production':
            emrStepResponse = emr.add_job_flow_steps(
                JobFlowId = jobFlowId,
                Steps = [
                    {
                        'Name': 'Spark Data Enhancement Program',
                        'ActionOnFailure': 'CONTINUE',
                        'HadoopJarStep': {
                            'Jar': 'command-runner.jar',
                            'Args': [
                                'spark-submit',
                                '--deploy-mode',
                                'cluster',
                                '--master',
                                'yarn',
                                '--py-files',
                                ('s3://' + EMR_CODE_BUCKET +
                                 EMR_POI_MATCHING_CODE_FILE),
                                ('s3://' + EMR_CODE_BUCKET +
                                 EMR_DATA_ENHANCEMENT_CODE_FILE),
                                ('s3://' + PROCESSING_STREAM_BUCKET +
                                 ('/*/*/*/*/*/*' if rerun else '/*/*/*/*/*')),
                                ('s3://' + LASTPOINTS_BUCKET +
                                 EMR_LASTPOINTS_DATA_FILE),
                                ('s3://' + EMR_MISC_BUCKET + EMR_POI_DATA_FILE),
                                outputFolderName,
                                esOutputFolderName,
                                lastpointsFolderName,
                                esLastpointsFolderName,
                                beaconFolderName,
                                locationFolderName,
                                clusteringFolderName,
                                firstpointsFolderName,
                                commuteFolderName
                            ]
                        }
                    },
                ]
            )
        else:
            cmd = 'spark-submit --master local[*] --py-files ' + LOCAL_BASE_FOLDER + '/' + EMR_CODE_BUCKET + EMR_POI_MATCHING_CODE_FILE + ' ' +
                   LOCAL_BASE_FOLDER + '/' + EMR_CODE_BUCKET + EMR_DATA_ENHANCEMENT_CODE_FILE + ' ' +  "\'" + 
                   LOCAL_BASE_FOLDER + '/' + PROCESSING_STREAM_BUCKET + '/*/*/*/*/*'+"\'" + ' ' + 
                   LOCAL_BASE_FOLDER + '/' + LASTPOINTS_BUCKET + EMR_LASTPOINTS_DATA_FILE + ' ' + 
                   LOCAL_BASE_FOLDER + '/' + EMR_MISC_BUCKET + EMR_POI_DATA_FILE + ' ' + outputFolderName + ' ' + esOutputFolderName + ' ' + 
                   lastpointsFolderName + ' ' + esLastpointsFolderName + ' ' + beaconFolderName + ' ' + locationFolderName + ' ' + 
                   clusteringFolderName + ' ' + firstpointsFolderName + ' ' + commuteFolderName
            sendSyslog("Spark command: " + cmd)

            emrStepResponse = subprocess.check_call(cmd, shell=True)

    except botocore.exceptions.ClientError as e:
        sendSyslog('Add step to cluster FAILED...Exiting!')
        sendFailureNote('Add step to cluster FAILED...Exiting!')
        sys.exit()
    sendSyslog('Add step to cluster SUCCEEDED...Continuing!')
    return emrStepResponse

def emrCheckClusterStatus(jobFlowId):
    checkCount = 0
    while checkCount < EMR_NUM_CHECKS:
        sendSyslog('EMR cluster status check # ' + str(checkCount) +
                   '...Checking!')
        clusterState = emr.describe_cluster(ClusterId = jobFlowId)
        if clusterState['Cluster']['Status']['State'] == 'WAITING':
            return clusterState
        if clusterState['Cluster']['Status']['State'] == 'BOOTSTRAPPING':
            checkCount = 0
        time.sleep(EMR_WAIT_TO_CHECK)
        checkCount += 1

    sendSyslog('EMR cluster status check FAILED after waiting limit...Exiting!')
    emrTerminateCluster(jobFlowId)
    sendFailureNote('EMR Cluster never came up...Exiting!')
    sys.exit()

def emrCheckStepStatus(jobFlowId, stepId, stepNum):
    checkCount = 0
    while checkCount < EMR_NUM_CHECKS:
        sendSyslog(('EMR step ' + str(stepNum) + ' status check # ' +
               str(checkCount) + '...Checking!'))
        stepState = emr.describe_step(ClusterId = jobFlowId, StepId = stepId)
        if (stepState['Step']['Status']['State'] == 'FAILED' or
            stepState['Step']['Status']['State'] == 'COMPLETED'):
            return stepState
        time.sleep(EMR_WAIT_TO_CHECK)
        checkCount += 1

    sendSyslog('EMR step status check FAILED after waiting limit...Exiting!')
    sendFailureNote('EMR step status check FAILED after waiting limit' +
                    '...Exiting!')
    sys.exit()

def isProcessingBucketEmpty():
    try: 
        processing = s3.list_objects(Bucket = PROCESSING_STREAM_BUCKET)
    except botocore.exceptions.ClientError as e:
        error_code = int(e.response['ResponseMetadata']['HTTPStatusCode'])
        if error_code == 403 or error_code == 404:
            sendSyslog('Processing bucket listing FAILED...Exiting!')
            sendFailureNote('Processing bucket listing FAILED...Exiting!')
            sys.exit()
    if processing['ResponseMetadata']['HTTPStatusCode'] != 200:
        sendSyslog('Processing bucket listing FAILED...Exiting!')
        sendFailureNote('Processing bucket listing FAILED...Exiting!')
        sys.exit()

    if 'Contents' in processing.keys() and len(processing['Contents']):
        return False
    return True

def createLoadfiles(s3OutputFolderName, s3LoadBucket, mongoFolderName):
    sendSyslog('Parameters:')
    sendSyslog('s3OutputFolderName: ' + s3OutputFolderName)
    sendSyslog('s3LoadBucket: ' + s3LoadBucket)
    sendSyslog('mongoFolderName: ' + mongoFolderName)

    if environment == 'production':
        date = '-'.join(s3OutputFolderName.split('/')[3].split('-')[1:4])
    else:
        date = '-'.join(s3OutputFolderName.split('/')[6].split('-')[1:4])
    sendSyslog('DATE: ' + str(date))
    outputBucket = '/'.join(s3OutputFolderName.split('/')[2:])
    sendSyslog('outputBucket: ' + str(outputBucket))

    if environment == 'production':
        response = s3cli.cp('--recursive', s3OutputFolderName, mongoFolderName)
        if response.exit_code:
            sendSyslog('S3 copy FAILED on output to local folder name...!')
            sendFailureNote('S3 copy FAILED on output to local folder...!')
    else:
        try:
            shutil.rmtree(mongoFolderName)
            response = shutil.copytree(s3OutputFolderName,mongoFolderName)
        except IOError, e:
            sendSyslog("Unable to copy file. %s" % e)
    fileList = glob.glob(mongoFolderName + '/part-*')
    fileList = sorted(fileList)
    sendSyslog('FileList: ' + str(fileList))

    sendSyslog('Creating a single Cluster loadfile...Continuing')
    with open(mongoFolderName + '/part#00000' , 'wb') as outfile:
        for f in fileList:
            with open(f, 'rb') as infile:
                outfile.write(infile.read())
    sendSyslog('Creation of single loadfile is successful...Continuing')
    fileList = glob.glob(mongoFolderName + '/part#*')
    fileList = sorted(fileList)

    for file in fileList:
        filename = file.split('/')[6]
        if environment == 'production':
            sendSyslog('Copying file ' + file + ' to ' + s3LoadBucket + ' bucket')
            response = s3cli.cp(mongoFolderName + '/' + filename, 's3://' +
                                s3LoadBucket + '/' + date + '/' + filename + '-' +
                                (str(datetime.datetime.now())
                                 .replace(' ', ':').replace(':', '-')))
            if response.exit_code:
                    sendSyslog('S3 copy FAILED for file ' + filename +
                               ' from local folder ' + mongoFolderName +
                               ' to cluster bucket '+s3LoadBucket)
                    sendFailureNote('S3 copy FAILED for file ' + filename +
                                    ' from local folder ' + mongoFolderName +
                                    ' to cluster bucket ' + s3LoadBucket)
        else:
            sendSyslog("Copying file " + file + " to " + LOCAL_BASE_FOLDER + '/'+ s3LoadBucket + " bucket")
            try:
                if not os.path.exists(LOCAL_BASE_FOLDER + '/' + s3LoadBucket + "/"+date):
                    os.mkdir(LOCAL_BASE_FOLDER + '/' + s3LoadBucket + "/"+date)
                response = shutil.copy2(mongoFolderName + '/' + filename, LOCAL_BASE_FOLDER + '/' +
                                        s3LoadBucket + "/"+ date +"/"+filename+"-"+
                                        (str(datetime.datetime.now())
                                         .replace(' ', ':').replace(':', '-')))
            except IOError, e:
                sendSyslog( "Unable to copy file. %s" % e)
                sendSyslog('S3 copy FAILED for file ' + filename + 
                           ' from local folder ' + mongoFolderName + 
                           ' to cluster bucket '+ LOCAL_BASE_FOLDER + '/'+ s3LoadBucket)
                sendFailureNote('S3 copy FAILED for file ' + filename + 
                                ' from local folder ' + mongoFolderName + 
                                ' to cluster bucket '+ LOCAL_BASE_FOLDER + '/'+ s3LoadBucket)

    sendSyslog('Deleting Local mongo folder...')
    shutil.rmtree(mongoFolderName)
    sendSyslog('Creating Local mongo folder...')
    os.makedirs(mongoFolderName)
    sendSyslog('Creation of Cluster loadfiles SUCCEEDED on all output files' +
               '...Continuing!')

def runOneEmrStep(jobFlowId, stepNum = 0, rerun = False):
    if environment == 'local':
        base = LOCAL_BASE_FOLDER + '/'
    else:
        base = 's3://'
        sendSyslog('EMR step number ' + str(stepNum) + ' starting...Checking!')
    outputFolderName = (base + OUTPUT_BUCKET + '/output-' +
                        (str(datetime.datetime.now())
                         .replace(' ', ':').replace(':', '-')))
    lastpointsFolderName = (base + LASTPOINTS_BUCKET +
                            '/lastpoints-output-' +
                            (str(datetime.datetime.now())
                             .replace(' ', ':').replace(':', '-')))
    beaconFolderName = (base + BEACON_BUCKET + '/beacon-' +
                        (str(datetime.datetime.now())
                         .replace(' ', ':').replace(':', '-')))
    esFolderName = (base + ES_BUCKET + '/es-' +
                        (str(datetime.datetime.now())
                         .replace(' ', ':').replace(':', '-')))
    locationFolderName = (base + LOCATION_BUCKET + '/location-' +
                        (str(datetime.datetime.now())
                         .replace(' ', ':').replace(':', '-')))
    esLastpointsFolderName = (base + ES_LASTPOINTS_BUCKET + '/lastpoints-' +
                        (str(datetime.datetime.now())
                         .replace(' ', ':').replace(':', '-')))
    clusteringFolderName = (base + OUTPUT_CLUSTERING_BUCKET + '/cluster-' +
                        (str(datetime.datetime.now())
                         .replace(' ', ':').replace(':', '-')))
    commuteFolderName = (base + OUTPUT_COMMUTE_BUCKET + '/commute-' +
                        (str(datetime.datetime.now())
                         .replace(' ', ':').replace(':', '-')))
    firstpointsFolderName = (base + FIRSTPOINTS_BUCKET +
                            '/firstpoints-output-' +
                            (str(datetime.datetime.now())
                             .replace(' ', ':').replace(':', '-')))

    cmd = ('''PGPASSWORD=''' + RDS_PASSWORD + ''' psql -X --host=''' +
           RDS_HOST + ''' --port=''' + RDS_PORT + ''' --username=''' +
           RDS_USER + ''' ''' + RDS_DB +
           ''' -c '\copy (SELECT row_to_json(t) FROM ''' + RDS_TABLE +
           ''' as t) to stdout' > ''' + LOCAL_MONGO_FOLDER +
           EMR_LASTPOINTS_DATA_FILE)
    try:
        subprocess.check_call(cmd, shell = True, stderr = subprocess.PIPE,
                              stdout = subprocess.PIPE)
        sendSyslog('RDS lastpoints table dump is successfully taken to' +
                   ' EC2 host server..Continuing!')
    except:
        sendSyslog('RDS lastpoints table dump command FAILED to get data to' +
                   ' EC2 host server..Exiting!')
        sendFailureNote('RDS lastpoints table dump command FAILED to get' +
                        ' data to EC2 host server..Exiting!')
        sys.exit()
   
    tmp = LOCAL_MONGO_FOLDER + '/tmp_file.json'
    with open(tmp,'a') as wfile:
        with open(LOCAL_MONGO_FOLDER+EMR_LASTPOINTS_DATA_FILE) as f:
            for line in f:
                line = re.sub(r'\\+', r'\\',line)
                wfile.write(line)    
    os.rename(tmp, LOCAL_MONGO_FOLDER+EMR_LASTPOINTS_DATA_FILE)
    if environment == 'production':
        response = s3cli.cp(LOCAL_MONGO_FOLDER + EMR_LASTPOINTS_DATA_FILE,
                            's3://' + LASTPOINTS_BUCKET)
        if response.exit_code:
            sendSyslog('S3 copy FAILED on lastpoints RDS to S3 bucket...Exiting!')
            sendFailureNote('S3 copy from RDS to S3 FAILED on lastpoints' +
                            '...Exiting!')
            sys.exit()
    else:
        response = shutil.copy(LOCAL_MONGO_FOLDER + EMR_LASTPOINTS_DATA_FILE, 
                                LOCAL_BASE_FOLDER + LASTPOINTS_BUCKET)

    if environment == 'production':
        response = s3cli.cp(LOCAL_CODE_FOLDER + EMR_DATA_ENHANCEMENT_CODE_FILE,
                           's3://' + EMR_CODE_BUCKET)
        if response.exit_code:
            sendSyslog('S3 copy FAILED on Python file ' + 
                        EMR_DATA_ENHANCEMENT_CODE_FILE + ' from local to S3 bucket...Exiting!')
            sendFailureNote('S3 copy FAILED on Python file ' + 
                        EMR_DATA_ENHANCEMENT_CODE_FILE + ' from local to S3 bucket...Exiting!')
            sys.exit()

        response = s3cli.cp(LOCAL_CODE_FOLDER + 
                         EMR_POI_MATCHING_CODE_FILE, 's3://' + EMR_CODE_BUCKET)
        if response.exit_code:
            sendSyslog('S3 copy FAILED on Python file ' + 
                        EMR_POI_MATCHING_CODE_FILE + ' from local to S3 bucket...Exiting!')
            sendFailureNote('S3 copy FAILED on Python file ' + 
                        EMR_POI_MATCHING_CODE_FILE + ' from local to S3 bucket...Exiting!')
            sys.exit()

    emrStepResponse = emrAddStep(jobFlowId,
                                 outputFolderName,
                                 lastpointsFolderName,
                                 beaconFolderName,
                                 esFolderName,
                                 locationFolderName,
                                 esLastpointsFolderName,
                                 clusteringFolderName,
                                 firstpointsFolderName,
                                 commuteFolderName,
                                 rerun)
    if environment == 'production':
        emrStepStatus = emrCheckStepStatus(jobFlowId,
                                           emrStepResponse['StepIds'][0],
                                           stepNum)
        assert(emrStepStatus['Step']['Status']['State'] == 'FAILED' or
               emrStepStatus['Step']['Status']['State'] == 'COMPLETED')

        if emrStepStatus['Step']['Status']['State'] == 'FAILED':
            sendSyslog('EMR step FAILED (NOT TERMINATING)...Exiting!')
            sendFailureNote('EMR step FAILED (NOT TERMINATING)...Exiting!')
            sys.exit()

        if rerun:
            mongo = MongoClient(MONGO_HOST_PORT)
            mongo.test.geoActivity_enhanced.rename(
                (MONGO_COLLECTION + '_' +
                 str(datetime.datetime.now().date()).replace('-', '_')),
                dropTarget = True
                )

    sendSyslog('EMR step number ' + str(stepNum) + ' SUCCEEDED...Continuing!')
    writeStepOutputToES(esFolderName, LOCAL_MONGO_FOLDER, 
                        LOADFILES_ES_GEO_BUCKET, LOADFILES_ES_GEO_ERROR_BUCKET)
    sendSyslog('Writing data to ES SUCCEEDED...Continuing!')
    writeStepOutputToES(esLastpointsFolderName, LOCAL_MONGO_FOLDER, 
                        LOADFILES_ES_LASTPOINTS_BUCKET,
                        LOADFILES_ES_LASTPOINTS_ERROR_BUCKET)
    sendSyslog('Writing lastpoints data to ES SUCCEEDED...Continuing!')

    writeStepOutputToRDS(lastpointsFolderName, LOCAL_MONGO_FOLDER, 
                        LOADFILES_RDS_LASTPOINTS_BUCKET,
                        LOADFILES_RDS_LASTPOINTS_ERROR_BUCKET)
    os.makedirs(LOCAL_MONGO_FOLDER)
    sendSyslog('Writing lastpoints data to RDS SUCCEEDED...Continuing!')

    # Create loadfiles from cluster-output files
    createLoadfiles(clusteringFolderName, LOADFILES_CLUSTERING_BUCKET,
                    LOCAL_MONGO_FOLDER)
    sendSyslog('Creation of Cluster Input loadfiles SUCCEEDED...Continuing!')

    # Create loadfiles from commute-output files
    createLoadfiles(commuteFolderName, LOADFILES_COMMUTE_BUCKET,
                    LOCAL_MONGO_FOLDER)
    sendSyslog('Creation of Commute Input loadfiles SUCCEEDED...Continuing!')

    # Pushing firstpoints to RDS
    writeStepOutputToRDSFirstpoints(firstpointsFolderName, LOCAL_MONGO_FOLDER)
    sendSyslog('Writing firstpoints data to RDS SUCCEEDED...Continuing!')

def emrTerminateCluster(jobFlowId):
    # All done...terminate the cluster
    sendSyslog('EMR all steps COMPLETED...Terminating!')
    emr.set_termination_protection(
        JobFlowIds = [jobFlowId],
        TerminationProtected = False
        )
    emr.terminate_job_flows(JobFlowIds = [jobFlowId])

def main():
    if environment == 'production':
        checkS3Buckets()
        if not isProcessingBucketEmpty():
            sendSyslog('Processing bucket empty check FAILED...Exiting!')
            sendFailureNote('Processing bucket empty check FAILED...Exiting!')
            sys.exit()

        jobFlowId = emrCreateCluster()
    else:
        jobFlowId = 'Local12345'

    stepNum = 0
    if environment == 'production':
        while stepNum < EMR_NUM_STEPS:
            try: 
                clusterState = emr.describe_cluster(ClusterId = jobFlowId)
            except botocore.exceptions.ClientError as e:
                sendSyslog('Cluster available check FAILED...Exiting!')
                sendFailureNote('Cluster available check FAILED...Exiting!')
                sys.exit()
                
            prepareInputData()
            if isProcessingBucketEmpty():
                sendSyslog('Processing bucket IS EMPTY (NO NEW DATA)...Continuing!')
                time.sleep(EMR_STEP_WAIT)
                stepNum += 1
                continue
        
            emrStepStatus = runOneEmrStep(jobFlowId, stepNum)
            archiveInputData()

            stepNum += 1
            if stepNum < EMR_NUM_STEPS:
              time.sleep(EMR_STEP_WAIT)

        emrTerminateCluster(jobFlowId)
    else:                                                                                                
        emrStepStatus = runOneEmrStep(jobFlowId, stepNum)
        archiveInputData()

        stepNum += 1
        if stepNum < EMR_NUM_STEPS:
            time.sleep(EMR_STEP_WAIT)

def rerun():
    checkS3Buckets()
    if not isProcessingBucketEmpty():
        sendSyslog('Processing bucket empty check FAILED...Exiting!')
        sendFailureNote('Processing bucket empty check FAILED...Exiting!')
        sys.exit()
    
    jobFlowId = emrCreateCluster()

    prepareRerunData()
    emrStepStatus = runOneEmrStep(jobFlowId, 0, True)
    archiveInputData(False)

    emrTerminateCluster(jobFlowId)

def recovery(jobFlowId):
    checkS3Buckets()
    if isProcessingBucketEmpty():
        sendSyslog('Processing bucket empty and recovery FAILED ..Exiting!')
        sendFailureNote('Processing bucket empty & recovery FAILED...Exiting!')
        sys.exit()
    
    emrStepStatus = runOneEmrStep(jobFlowId)
    archiveInputData()
    emrTerminateCluster(jobFlowId)

if len(sys.argv) < 3:
    print 'Missing arguments. Usage:'
    print 'program <config file> <main | recovery [cluster id] | rerun>'
    sys.exit()

# if environment == 'local':
#     config_file =  'local-config.ini'
#     print "config_file: " + config_file
# elif environment == 'production':
#     config_file = 'production-config.ini'
#     print "config_file: " + config_file
# else:
#     print 'env not recognised'
#     sys.exit(1)

# Invoke the main script and run!
sendSyslog('Script starting at....' +
       datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

config = ConfigParser.ConfigParser()
config.read(sys.argv[1])

# List of firehose s3 buckets and ARNs:
FIREHOSE_STREAM_NAME = config.get('firehose', 'firehoseStreamName')
FIREHOSE_PRIMARY_STREAM = config.get('firehose', 'firehosePrimaryStream')
FIREHOSE_SECONDARY_STREAM = config.get('firehose', 'firehoseSecondaryStream')
FIREHOSE_PRIMARY_S3_ARN = config.get('firehose', 'firehosePrimaryS3ARN')
FIREHOSE_SECONDARY_S3_ARN = config.get('firehose', 'firehoseSecondaryS3ARN')
FIREHOSE_SWITCH_WAIT = config.getint('firehose', 'firehoseSwitchWait')

PROCESSING_STREAM_BUCKET = config.get('s3', 'processingBucket')
PROCESSED_STREAM_BUCKET = config.get('s3', 'processedBucket')
OUTPUT_BUCKET = config.get('s3', 'outputBucket')
LASTPOINTS_BUCKET = config.get('s3', 'lastpointsBucket')
BEACON_BUCKET = config.get('s3', 'beaconBucket')
LOCATION_BUCKET = config.get('s3', 'locationBucket')
ES_BUCKET = config.get('s3', 'esBucket')
ES_LASTPOINTS_BUCKET = config.get('s3', 'esLastpointsBucket')
EMR_LOGS_BUCKET = config.get('s3', 'emrLogsBucket')
EMR_BOOTSTRAP_BUCKET = config.get('s3', 'emrBootstrapBucket')
EMR_CODE_BUCKET = config.get('s3', 'emrCodeBucket')
EMR_MISC_BUCKET = config.get('s3', 'emrMiscBucket')
LOADFILES_ES_GEO_BUCKET = config.get('s3', 'loadfileESGeoBucket')
LOADFILES_ES_GEO_ERROR_BUCKET = config.get('s3', 'loadfileESGeoErrorBucket')
LOADFILES_ES_LASTPOINTS_BUCKET = config.get('s3', 'loadfileESLastpointsBucket')
LOADFILES_ES_LASTPOINTS_ERROR_BUCKET = config.get(
    's3', 'loadfileESLastpointsErrorBucket'
    )
LOADFILES_RDS_LASTPOINTS_BUCKET = config.get(
    's3', 'loadfileRDSLastpointsBucket'
    )
LOADFILES_RDS_LASTPOINTS_ERROR_BUCKET = config.get(
    's3', 'loadfileRDSLastpointsErrorBucket'
    )
OUTPUT_CLUSTERING_BUCKET = config.get('s3', 'outputClusteringBucket')
LOADFILES_CLUSTERING_BUCKET = config.get('s3', 'loadfileClusteringBucket')
OUTPUT_COMMUTE_BUCKET = config.get('s3', 'outputCommuteBucket')
LOADFILES_COMMUTE_BUCKET = config.get('s3', 'loadfileCommuteBucket')
FIRSTPOINTS_BUCKET = config.get('s3', 'firstpointsBucket')

if environment == 'production':
    LOCAL_CODE_FOLDER = config.get('files', 'localCodeFolder')
else:
    LOCAL_BASE_FOLDER = config.get('files', 'localBaseFolder')

EMR_BOOTSTRAP_FILE = config.get('files', 'emrBootstrapFile')
EMR_DATA_ENHANCEMENT_CODE_FILE = config.get(
    'files', 'emrDataEnhancementCodeFile'
    )
EMR_POI_MATCHING_CODE_FILE = config.get('files', 'emrPOIMatchingCodeFile')
EMR_LASTPOINTS_DATA_FILE = config.get('files', 'emrLastpointsDataFile')
EMR_POI_DATA_FILE = config.get('files', 'emrPOIDataFile')

EC2_SUBNET_ID = config.get('security', 'ec2SubnetId')
EC2_KEY = config.get('security', 'ec2Key')

EMR_WAIT_TO_CHECK = config.getint('emr', 'emrWaitToCheck')
EMR_NUM_CHECKS = config.getint('emr', 'emrNumChecks')
EMR_STEP_WAIT = config.getint('emr', 'emrStepWait')
EMR_NUM_STEPS = config.getint('emr', 'emrNumSteps')

LOCAL_MONGO_FOLDER = config.get('mongo', 'localMongoFolder')
MONGO_HOST_PORT = config.get('mongo', 'mongoHostPort')
MONGO_COLLECTION = config.get('mongo', 'mongoCollection')
MONGO_LASTPOINTS_COLLECTION = config.get('mongo', 'mongoLastpointsCollection')

RDS_USER = config.get('rds', 'rds_user')
RDS_PASSWORD = config.get('rds', 'rds_password')
RDS_HOST = config.get('rds', 'rds_host')
RDS_DB = config.get('rds', 'rds_db')
RDS_PORT = config.get('rds', 'rds_port')
RDS_TABLE = config.get('rds', 'rds_table')

#ES_TABLE = config.get('es', 'esGeoTable')
ES_URL = config.get('es', 'esURL')

if sys.argv[2] == 'main':
    main()
elif sys.argv[2] == 'rerun':
    rerun()
elif sys.argv[2] == 'recovery':
    if len(sys.argv) < 4:
        print 'Bad arguments. Usage:'
        print 'program <config file> <main | recovery [cluster id] | rerun>'
        print 'Cluster ID required in recovery mode'
        sys.exit()
    sendSyslog('Recovery from failed step starting...Continuing!')
    jobFlowId = sys.argv[3]

    try:
        emrCluster = emr.describe_cluster(ClusterId = jobFlowId)
        assert(emrCluster['Cluster']['Status']['State'] == 'WAITING')
    except botocore.exceptions.ClientError as e:
        print 'Invalid cluster ID and recovery FAILED...Exiting!'
        sendFailureNote('Invalid cluster ID and recovery FAILED...Exiting!')
        sys.exit()
    recovery(jobFlowId)
else:
    print 'Bad arguments. Usage:'
    print 'program <config file> <main | recovery [cluster id] | rerun>'
    sys.exit()

if environment == 'production':
    sendSyslog('MOGEAN-DATA-ENHANCEMENT: Clearing logs from EMR log bucket' +
               '...Continuing!')
    response = s3cli.rm('--recursive', 's3://' + EMR_LOGS_BUCKET)
    if response.exit_code:
        sendSyslog('MOGEAN-DATA-ENHANCEMENT: S3 remove FAILED on logs bucket' +
                   '...Still continuing')
    else:
        sendSyslog('MOGEAN-DATA-ENHANCEMENT: S3 remove SUCCESSFUL on EMR logs' +
                   ' bucket')

    sendSyslog('Full script ended SUCCEEDED...Exiting!')
else:
    sendSyslog('MOGEAN-DATA-ENHANCEMENT: Full script ended SUCCEEDED...Exiting!')
