from time import sleep
import os


def main():


	while True:

		sleep(720)
		os.system("ps -eo pid,etime,comm | awk '$2~/^1.:../ && $3~/firefox/ { print $1 }' | xargs kill")
		os.system("ps -eo pid,etime,comm | awk '$2~/^2.:../ && $3~/firefox/ { print $1 }' | xargs kill")


main()
