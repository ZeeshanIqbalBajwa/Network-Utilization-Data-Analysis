import logging
import re
import pathlib
import numpy as np
import pandas as pd
import sqlalchemy as db
from sqlalchemy_utils import create_database, database_exists
from datetime import datetime, timedelta
from functools import wraps
import configparser

logging.basicConfig(filename='./log.log', format="%(levelname)s:%(asctime)s - %(message)s",
                    level=logging.DEBUG, datefmt="%d-%b-%y %H:%M:%S")

def log_function_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"Calling function: {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@log_function_call
def establish_connection(username, password, database, host='localhost', port=3306):
    try:
        db_conn = db.create_engine(
            f"mariadb+pymysql://{username}:{password}@{host}/{database}")
        if not database_exists(db_conn.url):
            create_database(db_conn.url)
        connection = db_conn.connect()
        logging.info(f"Connected to DB.")
        return db_conn, connection
    except Exception as e:
        logging.error("Failed to connect to DB.")
        raise e

@log_function_call
def create_table(db_conn, table_name, fields):
    metadata = db.MetaData()
    columns = [db.Column(field_name, field_type) for field_name, field_type in fields]
    port_data_table = db.Table(table_name, metadata, *columns)
    metadata.create_all(db_conn, checkfirst=True)
    logging.info(f"Database table '{table_name}' has been created")

@log_function_call
def read_fields_from_ini(filename):
    config = configparser.ConfigParser()
    config.read(filename)
    database_section = config['Database']
    username = database_section['username']
    password = database_section['password']
    database = database_section['database']

    table_section = config['Table']
    table_name = table_section['table_name']

    fields = []
    type_map = {
        'String': db.String,
        'Integer': db.Integer,
        'Float': db.Float,
        'DateTime': db.DateTime,
        'INT': db.Integer
    }
    for field_name, field_type_str in config.items('Fields'):
        field_type_parts = field_type_str.split('(')
        field_type_name = field_type_parts[0]
        field_type_args = ()
        if len(field_type_parts) > 1:
            field_type_args = tuple(map(int, re.findall(r'\d+', field_type_parts[1])))
        field_type = type_map.get(field_type_name)
        if field_type is None:
            logging.error(f"Unknown field type: {field_type_name}")
            continue
        fields.append((field_name, field_type(*field_type_args)))

    return username, password, database, table_name, fields

@log_function_call
def load_port_data(db_conn, connection,table_name):
    try:
        date_offset = 0
        # Data Reading and Manipulation
        for input_file in pathlib.Path("./Input_Data").glob("**/*"):
            input_data = pd.read_excel(input_file.absolute())
            time_stamp = str(datetime.now() - timedelta(date_offset)) + " WEST"
            input_data.columns = input_data.iloc[10]
            input_data = input_data.drop(list(range(0, 11)))
            input_data = input_data[['Direction', 'NE Name', 'NE ID', 'Port/LAG', 'Port Speed \n (Mbps)', 'Port Mode', 'Description', 'Minimum\n(Mbps)',
                                     'Average\n(Mbps)', 'Maximum\n(Mbps)', '95\nPCTL\n(Mbps)', 'Average Utilization(%)', '#Errors', 'Maximum\n(Time)', 'Max\nCount']]

            input_data = input_data.rename({'Port Speed \n (Mbps)': 'Port Speed (Mbps)', 'Port Speed \n (Mbps)': 'Port Speed (Mbps)', 'Average\n(Mbps)': 'Average (Mbps)',
                                                'Maximum\n(Mbps)': 'Maximum (Mbps)', 'Minimum\n(Mbps)': 'Minimum (Mbps)', '95\nPCTL\n(Mbps)': '95 PCTL (Mbps)', 'Maximum\n(Time)': 'Maximum (Time)', 'Max\nCount': 'Max Count','#Errors': 'Errors'}, axis=1)

            input_data.insert(loc=3, column='Area Code', value=None)
            input_data['Source Desc'] = input_data["Description"].str.extract(
                r"(.*?)<>")
            input_data['Destination Desc'] = input_data["Description"].str.extract(
                r".*?<>(.*?)=")
            time_stamp = re.search(
                r"(.*) [aA-zZ]", time_stamp).group(1)
            time_stamp = datetime.strptime(
                time_stamp, "%Y-%m-%d %H:%M:%S.%f")
            input_data['Report Time'] = time_stamp
            input_data['Report Time'] = pd.to_datetime(
                input_data['Report Time'], format="%Y-%m-%d %H:%M:%S")

            area_code_map = pd.read_excel("./data_sheets/Area_Code_Map.xlsx")

            input_data['Area Code'] = input_data['NE Name'].str.extract(
                r"^(\D{3}|\D{2})-")[0]

            input_data = input_data.merge(area_code_map, how='inner',
                                          right_on='Area Code', left_on='Area Code')
            input_data.drop_duplicates(inplace=True)
            input_data['Maximum (Time)'] = input_data['Maximum (Time)'].str.extract(
                r'(.*) [aA-zA]')
            input_data['Maximum (Time)'] = pd.to_datetime(
                input_data['Maximum (Time)'], format="%m-%d-%Y %H:%M")
            input_data = input_data.query(" ~`Source Desc`.isna() ")
            # Generate unique IDs
            input_data.loc[:, 'id'] = np.arange(len(input_data)) + 1
            input_data.loc[:, 'Vendor'] = 'Nokia'
            # insert data
            input_data_df = pd.DataFrame(input_data)
            input_data_df.to_sql(table_name, db_conn, if_exists='append', index=False)

            date_offset += 1
        logging.info(f"Final Input file: {input_file}")
        connection.close()
        db_conn.dispose()
    except Exception as e:
        logging.error(f"An error occurred during data processing: {str(e)}")
        return
    finally:
        if 'connection' in locals():
            connection.close()
        if 'db_conn' in locals():
            db_conn.dispose()


@log_function_call
def main():
    try:
        username, password, database, table_name, fields = read_fields_from_ini('C:/Users/zeiqbal/PycharmProjects/GrafanaDashboards/PortDashboard/scripts/config.ini')
        db_conn, connection = establish_connection(username, password, database)
        create_table(db_conn, table_name, fields)
        load_port_data(db_conn, connection,table_name)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

if __name__ == '__main__':
    main()