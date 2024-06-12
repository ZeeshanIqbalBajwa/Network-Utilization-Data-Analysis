#!/usr/bin/python3
import os
import csv
import logging
import configparser
from port_throughput_transformation import main as transformation_main
from ftplib import FTP
import os

# ------VARS--------------------
config = configparser.ConfigParser()
config.read('config.ini')
ftp_host = config['ftp']['ftp_host']
ftp_user = config['ftp']['ftp_user']
ftp_password = config['ftp']['ftp_password']
remote_directory = config['ftp']['remote_directory']
file_name = config['ftp']['file_name']
local_directory = config['ftp']['local_directory']


logging.basicConfig(filename='./log.log', format="%(levelname)s:%(asctime)s - %(message)s",
                    level=logging.DEBUG, datefmt="%d-%b-%y %H:%M:%S")

def get_data_file():
    try:
        all_data = fetch_ftp_file(ftp_host, ftp_user, ftp_password, remote_directory, file_name, local_directory)
    except Exception as e:
        logging.error("An error occurred while fetching or processing data: %s", e)


def fetch_ftp_file(ftp_host, ftp_user, ftp_password, remote_directory, file_name, local_directory):
    with FTP(ftp_host, ftp_user, ftp_password) as ftp:
        ftp.cwd(remote_directory)
        with open(os.path.join(local_directory, file_name), 'wb') as local_file:
            ftp.retrbinary(f'RETR {file_name}', local_file.write)
    print(f"File '{file_name}' downloaded successfully to '{local_directory}'")


if __name__ == '__main__':
    get_nes()
    transformation_main()
