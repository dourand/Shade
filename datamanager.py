#DataManager

import smbus
import time
import ms5803py
import mag3110
import serial
import Paths as paths

class DataManager:
    #constructor data
        def __init__(self,master,infologger,datalogger):
                self.master = master
                self.infologger = infologger
                self.datalogger = datalogger
                self.gps_port = "/dev/ttyACM0"
                self.imu_port = "/dev/ttyACM1"
                self.bus = smbus.SMBus(1)
                self.P0 = 1015
                self.dictionary = dict()
                try:
                        self.compass = mag3110.compass()
                        self.master.status_vector["COMPASS"] = 1			
                except:
                        self.infologger.write_error("DataManager: Can't connect to compass.")
                        self.master.status_vector["COMPASS"] = 0
                try:		
                        self.compass.loadCalibration()
                except FileNotFoundError:	
                        self.infologger.write_error("DataManager: Can't locate the calibration file.")
                        self.master.status_vector["COMPASS"] = 0
                try:			
                        self.altimeter = ms5803py.MS5803()
                        self.master.status_vector["ALTIMETER"] = 1			
                except:
                        self.infologger.write_error("DataManager: Can't connect to altimeter.")
                        self.master.status_vector["ALTIMETER"] = 0		
                try:			
                        self.ser_gps = serial.Serial(self.gps_port, baudrate=9600, timeout=0.5)
                        self.master.status_vector["GPS"] = 1			
                except:
                        self.infologger.write_error("DataManager: Can't connect to GPS.")
                        self.master.status_vector["GPS"] = 0		
                try:    			
                        self.ser_imu = serial.Serial(self.imu_port, baudrate=9600, timeout=0.5)
                        self.master.status_vector["IMU"] = 1			
                except:
                        self.infologger.write_error("DataManager: Can't connect to IMU.")
                        self.master.status_vector["IMU"] = 0
                        		
        def start(self):
                self.init_dict()
                while True:
                        self.read_temp()
                        self.read_altitude(self.P0)
                        self.read_gps()
                        self.read_compass()
                        self.read_imu()
                        self.write_tx_file()
                        self.infologger.write_info("DataManager: Saving data...")
                        self.datalogger.write_info(self.get_log_data())
                        self.infologger.write_info("DataManager: Finished saving data.")
                        time.sleep(3)
   
        def get_log_data(self):
                return_string = "{} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {} , {}"
                return return_string.format(
                 self.dictionary["ext_temp"],
                 self.dictionary["int_temp"],
                 self.dictionary["pressure"],
                 self.dictionary["altitude"],
                 self.dictionary["time_gps"],
                 self.dictionary["gps_y"],
                 self.dictionary["gps_x"],
                 self.dictionary["altitude_gps"],
                 self.dictionary["angle_c"],
                 self.dictionary["time_imu"],
                 self.dictionary["accelX"],
                 self.dictionary["accelY"],
                 self.dictionary["accelZ"],
                 self.dictionary["gyroX"],
                 self.dictionary["gyroY"],
                 self.dictionary["gyroZ"],
                 self.dictionary["magX"],
                 self.dictionary["magY"],
                 self.dictionary["magZ"]
               )

        def init_dict(self):
                self.dictionary["ext_temp"] = None
                self.dictionary["int_temp"] = None
                self.dictionary["pressure"] = None
                self.dictionary["altitude"] = None
                self.dictionary["time_gps"] = None
                self.dictionary["gps_y"] = None
                self.dictionary["gps_x"] = None
                self.dictionary["altitude_gps"] = None
                self.dictionary["angle_c"] = None
                self.dictionary["time_imu"] = None
                self.dictionary["accelX"] = None
                self.dictionary["accelY"] = None
                self.dictionary["accelZ"] = None
                self.dictionary["gyroX"] = None
                self.dictionary["gyroY"] = None
                self.dictionary["gyroZ"] = None
                self.dictionary["magX"] = None
                self.dictionary["magY"] = None
                self.dictionary["magZ"] = None
       
        def get_data(self, name):
                try:
                        return self.dictionary[name]
                except:
                        return None
                
        def read_temp(self):
                try:
                        self.infologger.write_info("DataManager: Reading external temperature...")
                        # TCN75A address, 0x48(72)
                        # Select configuration register, 0x01(01)
                        #       0x60(96)    12-bit ADC resolution
                        self.bus.write_byte_data(0x48, 0x01, 0x60)

                        time.sleep(0.5)

                        # TCN75A address, 0x48(72)
                        # Read data back from 0x00(00), 2 bytes
                        # temp MSB, temp LSB
                        data = self.bus.read_i2c_block_data(0x48, 0x00, 2)
                        # Convert the data to 12-bits
                        temp = ((data[0] * 256) + (data[1] & 0xF0)) / 16
                        if temp > 2047:
                                temp -= 4096
                        cTemp = temp * 0.0625
                        self.dictionary['ext_temp'] = cTemp
                        self.master.status_vector["TEMP"] = 1
                        self.infologger.write_info("DataManager: Finished reading external temperature.")
                except: 
                        self.infologger.write_error("DataManager: Cannot connect to the I2C device.")
                        self.infologger.write_error("DataManager: Cannot read external temperature.")
                        self.master.status_vector["TEMP"] = 0

        def read_altitude(self, p0):
                try:
                        self.infologger.write_info("DataManager: Reading altimeter...")
                        raw_temperature = self.altimeter.read_raw_temperature(osr=4096)
                        raw_pressure = self.altimeter.read_raw_pressure(osr=4096)
                        press, temp = self.altimeter.convert_raw_readings(raw_pressure, raw_temperature)
                        alt = (44330.0 * (1 - pow(press / p0, 1 / 5.255)))
                        self.dictionary['int_temp']= temp
                        self.dictionary['pressure'] = press
                        self.dictionary['altitude'] = alt
                        self.master.status_vector["ALTIMETER"] = 1
                        self.infologger.write_info("DataManager: Finished reading altimeter.")
                except:
                        self.infologger.write_error("DataManager:  Cannot connect to the I2C device.")
                        self.infologger.write_error("DataManager: Cannot read altimeter.")
                        self.master.status_vector["ALTIMETER"] = 0

        def read_gps(self):
                try:
                        self.infologger.write_info("DataManager: Reading GPS...")
                        while True:
                                data = self.ser_gps.readline()
                                s = b' '
                                if data[0:6] == b'$GNGGA':
                                        s = data.decode().split(",")
                                        if s[12] == '0':
                                                print("no satellite data available")
                                        #time = s[1]
                                        #lat = s[2]
                                        #dirLat = s[3]
                                        #lon = s[4]
                                        #dirLon = s[5]
                                        #numsat = s[6]
                                        #alt = s[9]
                                        #checksum = s[12]
                                        lat = float(s[2])/100
                                        if s[3] == 'S':
                                                lat = -lat
                                        lon = float(s[4])/100
                                        if s[5] == 'W':
                                                lon = -lon
                                        self.dictionary['time_gps'] = s[1]
                                        self.dictionary['gps_y'] = lat
                                        self.dictionary['gps_x'] = lon
                                        alt = float(s[9])
                                        self.dictionary['altitude_gps'] = alt
                                        break
                        self.infologger.write_info("DataManager: Finished reading GPS.")
                        self.master.status_vector["GPS"] = 1		
                except:
                        self.infologger.write_error("DataManager:  Cannot connect to the Serial device.")
                        self.infologger.write_error("DataManager:  Cannot read GPS receiver.")
                        self.master.status_vector["GPS"] = 0	

        def read_compass(self):
                try:
                        self.infologger.write_info("DataManager: Reading compass...")
                        angle = self.compass.getBearing()
                        self.dictionary['angle_c'] = angle
                        self.infologger.write_info("DataManager: Finished reading compass.")
                        self.master.status_vector["COMPASS"] = 1
                except:
                        self.infologger.write_error("DataManager:  Cannot connect to the I2C device.")
                        self.infologger.write_error("DataManager: Cannot read compass.")
                        self.master.status_vector["COMPASS"] = 0

        def read_imu(self):
                try:
                        self.infologger.write_info("DataManager: Reading IMU...")
                        data = self.ser_imu.readline()
                        s = data.decode().split(",")
                        self.dictionary['time_imu'] = s[0]
                        self.dictionary['accelX'] = s[1]
                        self.dictionary['accelY'] = s[2]
                        self.dictionary['accelZ'] = s[3]
                        self.dictionary['gyroX'] = s[4]
                        self.dictionary['gyroY'] = s[5]
                        self.dictionary['gyroZ'] = s[6]
                        self.dictionary['magX'] = s[7]
                        self.dictionary['magY'] = s[8]
                        self.dictionary['magZ'] = s[9].strip("\r\n")
                        self.infologger.write_info("DataManager: Finished reading IMU.")
                        self.master.status_vector["IMU"] = 1
                except:
                        self.infologger.write_error("DataManager: Cannot connect to the Serial device.")
                        self.infologger.write_error("DataManager: Cannot read IMU.")
                        self.master.status_vector["IMU"] = 0
			
        def write_tx_file(self):
                try:
                        f = open(paths.Paths().tx_file,"w")
                        #time = self.dictionary['time_gps']
                        temp = self.dictionary['ext_temp']
                        str = self.get_tx_str()
                        f.write(str)
                        f.close()
                except:
                        self.infologger.write_error("DataManager: Handling TX file.")
	
        def get_tx_str(self):
                return_string = "(UTC):  ,External temperature {}"
                return return_string.format(
                 self.dictionary["ext_temp"],
                 #self.dictionary["time_gps"],
                )
        
        	
if __name__ == '__main__':
	data_obj = DataManager()
	data_obj.start()
