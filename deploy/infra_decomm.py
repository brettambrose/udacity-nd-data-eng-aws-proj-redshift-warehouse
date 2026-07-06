import boto3
import configparser
import os
import sys

"""
Imperative Provisioning Script (not IaC) providing step-by-step
 commands to spin down the AWS environment for this project
"""

sys.path.append(os.getcwd())
from util.config_functions import modify_config_file

main_config_path = "dwh.cfg"
main_config = configparser.ConfigParser()
main_config.read(main_config_path)

aws_creds_path = os.path.expanduser("~\\.aws\\credentials")
aws_creds = configparser.ConfigParser()
aws_creds.read(aws_creds_path)

aws_config_path = os.path.expanduser("~\\.aws\\config")
aws_config = configparser.ConfigParser()
aws_config.read(aws_config_path)

# CLUSTER
CLUSTER_IDENTIFIER    = main_config.get("CLUSTER","CLUSTER_IDENTIFIER")

# IAM
IAM_ROLE_NAME         = main_config.get("IAM_ROLE","IAM_ROLE_NAME")

# AWS CREDENTIALS & CONFIG
KEY                   = aws_creds.get("default", "aws_access_key_id")
SECRET                = aws_creds.get("default", "aws_secret_access_key")
REGION                = aws_config.get("default", "region")

print("**********************************************")
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

print("**********************************************")
print("Deleting Cluster...")

try:
    redshift.delete_cluster(
        ClusterIdentifier=CLUSTER_IDENTIFIER,
        SkipFinalClusterSnapshot=True
        )
    
    print(redshift.describe_clusters(ClusterIdentifier=CLUSTER_IDENTIFIER)['Clusters'][0])

except Exception as e:
    print(e)

print("**********************************************")
print("Detatching IAM Role policies...")

try:
    iam_client.detach_role_policy(
        RoleName=IAM_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
        )

except Exception as e:
    print(e)

print("**********************************************")
print("Deleting IAM Role")

try:
    iam_client.delete_role(RoleName=IAM_ROLE_NAME)

except Exception as e:
    print(e)

print("**********************************************")
print("Removing Cluster endpoint to dwh.cfg file...")

main_config_section = "DB"
main_config_key = "DB_HOST"

try:
    modify_config_file (
        config_file=main_config_path,
        config_obj=main_config,
        config_section=main_config_section,
        config_key=main_config_key,
        config_val=""
        )
    
except Exception as e:
    print(e)

# TODO: remove role arn from aws.cfg file