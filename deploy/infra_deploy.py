import boto3
import json
import psycopg2
import configparser
import os
import sys
import time
import requests
from util.config_functions import modify_config_file

"""
Imperative Provisioning Script (not IaC) providing step-by-step
 commands to set up the AWS environment for this project
"""




main_config_path = "dwh.cfg"
main_config = configparser.ConfigParser()
main_config.read(main_config_path)

aws_creds_path = os.path.expanduser(os.path.join("~", ".aws", "credentials"))
aws_creds = configparser.ConfigParser()
aws_creds.read(aws_creds_path)

aws_config_path = os.path.expanduser(os.path.join("~", ".aws", "config"))
aws_config = configparser.ConfigParser()
aws_config.read(aws_config_path)

# CLUSTER
CLUSTER_IDENTIFIER    = main_config.get("CLUSTER","CLUSTER_IDENTIFIER")
CLUSTER_TYPE          = main_config.get("CLUSTER","CLUSTER_TYPE")
NODE_TYPE             = main_config.get("CLUSTER","NODE_TYPE")
NUM_NODES             = main_config.get("CLUSTER","NUM_NODES")

# DATABASE
DB_NAME               = main_config.get("DB","DB_NAME")
DB_USER               = main_config.get("DB","DB_USER")
DB_PASSWORD           = main_config.get("DB","DB_PASSWORD")
DB_PORT               = main_config.get("DB","DB_PORT")

# IAM
IAM_ROLE_NAME         = main_config.get("IAM_ROLE","IAM_ROLE_NAME")

# AWS CREDENTIALS & CONFIG
KEY                   = aws_creds.get("default", "aws_access_key_id")
SECRET                = aws_creds.get("default", "aws_secret_access_key")
REGION                = aws_config.get("default", "region")

print("**************************************************************")
print("Establishing boto3 resources and clients...")

iam_client = boto3.client('iam',
                          aws_access_key_id=KEY,
                          aws_secret_access_key=SECRET,
                          region_name=REGION
                         )

redshift = boto3.client('redshift',
                       aws_access_key_id=KEY,
                       aws_secret_access_key=SECRET,
                       region_name=REGION
                       )

ec2 = boto3.resource('ec2',
                     aws_access_key_id=KEY,
                     aws_secret_access_key=SECRET,
                     region_name=REGION
                     )

ec2_client = boto3.client("ec2",
                          aws_access_key_id=KEY,
                          aws_secret_access_key=SECRET,
                          region_name=REGION
                          )

print("**************************************************************")
print("Creating IAM Role")

try:
    dwhRole = iam_client.create_role(
        Path='/',
        RoleName=IAM_ROLE_NAME,
        Description = "Allows Redshift clusters to call AWS services on your behalf.",
        AssumeRolePolicyDocument=json.dumps(
            {'Statement': [{'Action': 'sts:AssumeRole',
               'Effect': 'Allow',
               'Principal': {'Service': 'redshift.amazonaws.com'}}],
             'Version': '2012-10-17'})
    )    
except Exception as e:
    print(e)

print("**************************************************************")
print("Updating local .aws/config file with Role ARN")

aws_profile = "profile Redshift"
aws_config_key = "role_arn"
role_arn = iam_client.get_role(RoleName=IAM_ROLE_NAME)['Role']['Arn']

modify_config_file(
    config_file=aws_config_path,
    config_obj=aws_config,
    config_section=aws_profile,
    config_key=aws_config_key,
    config_val=role_arn
)

print("**************************************************************")
print("Attaching policies to IAM Role")

try:
    iam_client.attach_role_policy(RoleName=IAM_ROLE_NAME,
                                  PolicyArn="arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
                                 )

except Exception as e:
    print(e)

print("**************************************************************")
print("Creating cluster...")

try:
    response = redshift.create_cluster(
        ClusterType=CLUSTER_TYPE,
        NodeType=NODE_TYPE,
        NumberOfNodes=int(NUM_NODES),
        DBName=DB_NAME,
        ClusterIdentifier=CLUSTER_IDENTIFIER,
        MasterUsername=DB_USER,
        MasterUserPassword=DB_PASSWORD,
        PubliclyAccessible=True,
        IamRoles=[role_arn]
    )
    
except Exception as e:
    print(e)

print("**************************************************************")
print("Waiting for cluster availability...")

waiter = redshift.get_waiter('cluster_available')
waiter.wait(
    ClusterIdentifier=CLUSTER_IDENTIFIER,
    WaiterConfig={'Delay': 15, 'MaxAttempts': 60}  # up to 15 min
)

clusterProps = redshift.describe_clusters(ClusterIdentifier=CLUSTER_IDENTIFIER)['Clusters'][0]
clusterHost = clusterProps['Endpoint']['Address']
print(f"{clusterHost} now available")

print("**************************************************************")
print("Adding Cluster endpoint to dwh.cfg file...")

main_config_section = "DB"
main_config_key = "DB_HOST"

try:
    modify_config_file(
        config_file=main_config_path,
        config_obj=main_config,
        config_section=main_config_section,
        config_key=main_config_key,
        config_val=clusterHost
        )
    
except Exception as e:
    print(e)
    
print("**************************************************************")
print("Specifying ingress rules to default sec group")

my_ip = requests.get("https://checkip.amazonaws.com").text.strip()
cidr = f"{my_ip}/32"

try:
    group_id = ec2_client.describe_security_groups()["SecurityGroups"][0]["GroupId"]
    defaultSg = ec2.SecurityGroup(group_id)
    defaultSg.authorize_ingress(
        GroupName=defaultSg.group_name,
        CidrIp=cidr,
        IpProtocol='TCP',
        FromPort=int(DB_PORT),
        ToPort=int(DB_PORT)  
    )

except ec2_client.exceptions.ClientError as e:
    if "InvalidPermission.Duplicate" in str(e):
        print("Ingress rule already exists, skipping")
    else:
        raise
    
print("**************************************************************")
print("Validating cluster availability...")

for attempt in range(30):

    try:
        conn = psycopg2.connect("host={} dbname={} user={} password={} port={} connect_timeout=10".format(clusterHost, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT))
        conn.close()

        print("Successfully connected to cluster")
        break

    except Exception as e:
        print(f"Attempt {attempt+1}: {e}")
        time.sleep(10)