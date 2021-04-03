import argparse
import sys
import re
import paramiko
from scp import SCPClient
import os
import ntpath
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

pd.options.mode.chained_assignment = None  # default='warn'

def copyFile(fname, localpath):

    remote_path = '/home/pi/Documents/'

    file_path = remote_path + fname
    scp.get(remote_path=file_path, local_path=localpath)
    print('File {} copied.'.format(fname))

if __name__ == '__main__':

    # optional last argument

    lastarg = sys.argv[-1]
    if len(sys.argv) > 3 and lastarg[0] != '-':
        sys.argv[-1] = '-fname'
        sys.argv.append(lastarg)


    # parsing

    parser = argparse.ArgumentParser(description='Management application for manipulating data in COPIS')
    parser.add_argument("ip", type=str, help="Your Pi IP address (string).")
    parser.add_argument("plot", choices=[0, 1], type=int, nargs='+', help="Whether to plot the data or not (“0”: simply transfer the file/s, “1”: transfer & plot the data).")
    parser.add_argument("-fname", type=str, help="Specify which file should be transferred from the pi to your machine.")

    args = parser.parse_args()

    server = args.ip
    plot = args.plot[0]
    fname = args.fname

    # Input type validation with regex

    reg_IP = '^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    reg_txt = '\w+.(txt)$'

    if not re.match(reg_IP, server):
        print("Incorrect IP Address format for first argument. Please use standard IP format with three decimals.")
        exit(-1)

    if fname is not None:
        if not re.match(reg_txt, fname):
            print("Incorrect file name for third argument. Please use string ending in '.txt'.")
            exit(-1)

    # Prompt user for input
    username = input('Username for ssh: ')
    password = input('Password for ssh: ')

    # Code local path based on operating system

    localpath = './DataFiles/'
    localpath.replace(os.sep, ntpath.sep)

    # Track local files, to avoid overwriting

    local_files = os.listdir(localpath)

    # Establish SSH connection

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print('Connecting to server...')

    try: ssh.connect(server, username=username, password=password)
    except:
        print("\nERROR: Couldn't find the server: ", server)
        exit(-1)
    scp = SCPClient(ssh.get_transport())

    print('Connected.')

    # Import files

    try:

        # If importing all files
        if fname is None:

            # Check file names for over writing
            ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command('ls Documents')

            for file in ssh_stdout:
                file = file.strip()
                # Check if it is a .txt file
                if not re.match(reg_txt, file):
                    continue
                # Avoid overwriting
                if file in local_files:
                    print('File {} already in local files. Not overwriting.'.format(file))
                    continue
                # Copy the file
                else:
                    copyFile(file, localpath)

        # If importing with given file name
        else:
            if fname in local_files:
                print('WARNING: {} already in local files. Not overwriting.'.format(fname))
            else: copyFile(fname, localpath)

    # Print exception
    except Exception as e:
        print("\nERROR: Issue occurred while importing files.  Returned error: {}" + str(e))
        exit(-1)

    ssh.close()

    # Plotting mode

    if plot == 1:

        #  Plotting mode must only work with given file name.

        if fname is None:
            print('ERROR:  Plotting mode requires file name. Please provide file name as argument.')
            exit(-1)

        else:

            # Read csv with pandas.
            # Convert time to datetime datatype

            df = pd.read_csv(localpath + fname, names=["Sensor", "Time", "Value"])
            date = df.iloc[0]['Time'][0:10]
            df.Time = pd.to_datetime(df.Time).dt.time

            # Seperate dataframes based on sonic / SPI sensor
            df_sonic = df.query('Sensor.str.contains("Sonic").values')
            df_spi = df.query('Sensor.str.contains("SPI").values')

            # Threshold sonic values at 100
            df_sonic['Value'] = df_sonic['Value'].clip(0,100)

            # Create subplots, add parsed date as title
            fig, (ax1, ax2) = plt.subplots(2, figsize=(9.0, 6.0))
            fig.suptitle('Sensor Data for {}'.format(date))

            # Plot and label suplots
            df_sonic.plot(kind='line', x='Time', y='Value', ax=ax1)
            ax1.set_ylabel('Sonic (cm, max:100)')
            ax1.set_xlabel('')

            df_spi.plot(kind='line', x='Time', y='Value', ax=ax2)
            ax2.set_ylabel('SPI (% turned)')

            # Save figure before showing plot ... then give user the option to keep or discard .png
            # Chose this method to save computation time. As the plt.show() method erases instance.
            plt.savefig(fname[:-4] + '.png')
            plt.show()

            ans = input("Enter 's' to keep saved plot; Press enter to discard: ")
            if ans == 's':
                print("Plot saved to: ", os.getcwd())
            else:
                os.remove(fname[:-4] + '.png')
                print("Plot discarded.")