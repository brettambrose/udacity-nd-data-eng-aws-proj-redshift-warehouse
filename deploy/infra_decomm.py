import boto3
import configparser
import os
import sys
from util.config_functions import modify_config_file

"""
Imperative Provisioning Script (not IaC) providing step-by-step
 commands to spin down the AWS environment for this project
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

    print("Waiting for cluster deletion to complete...")
    waiter = redshift.get_waiter('cluster_deleted')
    waiter.wait(
        ClusterIdentifier=CLUSTER_IDENTIFIER,
        WaiterConfig={'Delay': 15, 'MaxAttempts': 60}  # up to 15 min
    )
    print(f"Cluster {CLUSTER_IDENTIFIER} successfully deleted")

except redshift.exceptions.ClusterNotFoundFault:
    print(f"Cluster {CLUSTER_IDENTIFIER} does not exist, skipping deletion")

print("**********************************************")
print("Detatching IAM Role policies...")

try:
    iam_client.detach_role_policy(
        RoleName=IAM_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
        )

except iam_client.exceptions.NoSuchEntityException:
    print(f"Role {IAM_ROLE_NAME} or policy attachment not found, skipping detach")

print("**********************************************")
print("Deleting IAM Role")

try:
    iam_client.delete_role(RoleName=IAM_ROLE_NAME)

except iam_client.exceptions.NoSuchEntityException:
    print(f"IAM role {IAM_ROLE_NAME} already deleted, skipping")
except iam_client.exceptions.DeleteConflictException as e:
    print(f"Role {IAM_ROLE_NAME} still has attached policies/resources: {e}")
    raise

print("**********************************************")
print("Removing Cluster endpoint to dwh.cfg file...")

main_config_section = "DB"
main_config_key = "DB_HOST"

modify_config_file (
    config_file=main_config_path,
    config_obj=main_config,
    config_section=main_config_section,
    config_key=main_config_key,
    config_val=""
    )