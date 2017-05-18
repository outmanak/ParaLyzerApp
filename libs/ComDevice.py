# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:46:57 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

import serial
import serial.tools.list_ports

from time import sleep

from libs import coreUtilities as coreUtils

class ComDevice:
    def __init__(self, comPortName='', comPortFlags={}, userMsg='', logger=None, detectCallback=None):
        
        self.comPortList           = []
        self.comPortListIdx        = 0          # in case multiple devices were found use this
        self.comPortInfo           = None
        self.comPort               = None
        self.comPortStatus         = False
        self.comPortName           = comPortName
        self.comPortLogger         = logger
        self.comPortDetectCallback = detectCallback
        
        if comPortName != '':
            self.DetectDeviceAndSetupPort(comPortName, comPortFlags, userMsg, detectCallback)
        
### -------------------------------------------------------------------------------------------------------------------------------

    def __del__(self, caller=__name__):
        if isinstance(self.comPort, serial.serialwin32.Serial):
            if self.comPort.isOpen():
                self.comPort.close()
                
        coreUtils.TerminateLogger(__name__)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DetectDeviceAndSetupPort(self, comPortName='', flags={}, msg='', cb=None):
        
        self.DetectDevice(comPortName, msg)
        self.SetupSerialPort(flags)
        
        if self.comPortStatus and cb:
            cb()
        
        return self.comPortStatus
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DetectDevice(self, comPortName='', msg=''):
        # try to detect com device
        
        found = False
        
        # put message to the logger
        if msg != '':
            coreUtils.SafeLogger('info', msg)
        
        # NOTE: serial.tools.list_ports.grep(name) does not seem to work...
        for p in serial.tools.list_ports.comports():
            if comPortName in p.description:
                self.comPortList.append(p)
                
                found = True
                
                coreUtils.SafeLogger('info', 'Found device \'%s\' on \'%s\'.' % (p[1], p[0]))
                
        if len(self.comPortList) == 1:
            self.comPortInfo = self.comPortList[0]
        else:
            None
            # multiple ones found...user needs to choose the correct port...
        
        if not found:
            coreUtils.SafeLogger('info', 'Could not be found!')
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetupSerialPort(self, flags={}):
    
        if isinstance(self.comPortInfo, serial.tools.list_ports_common.ListPortInfo):
            
            coreUtils.SafeLogger('info', 'Initializing serial port.')
            
            # do it step by step to avoid reset of Arduino by DTR HIGH signal (pulls reset pin)
            # NOTE: some solutions use hardware to solve this problem...
            try:
                self.comPort      = serial.Serial()
                self.comPort.port = self.comPortInfo.device
            except serial.SerialException:
                coreUtils.SafeLogger('error', 'Could not initialize serial port!')
            else:
                try:
                    if 'baudrate' in flags.keys():
                        self.comPort.baudrate = flags['baudrate']
                    else:
                        self.comPort.baudrate = 9600
                    
                    if 'bytesize' in flags.keys():
                        self.comPort.bytesize = flags['bytesize']
                    else:
                        self.comPort.bytesize = serial.EIGHTBITS
                    
                    if 'parity' in flags.keys():
                        self.comPort.parity = flags['parity']
                    else:
                        self.comPort.parity = serial.PARITY_NONE
                    
                    if 'stopbits' in flags.keys():
                        self.comPort.stopbits = flags['stopbits']
                    else:
                        self.comPort.stopbits = serial.STOPBITS_ONE
                    
                    if 'timeout' in flags.keys():
                        self.comPort.timeout = flags['timeout']
                    else:
                        self.comPort.timeout = 0
                    
                    if 'xonxoff' in flags.keys():
                        self.comPort.xonxoff = flags['xonxoff']
                    else:
                        self.comPort.xonxoff = False
                    
                    if 'rtscts' in flags.keys():
                        self.comPort.rtscts = flags['rtscts']
                    else:
                        self.comPort.rtscts = False
                    
                    if 'dsrdtr' in flags.keys():
                        self.comPort.dsrdtr = flags['dsrdtr']
                    else:
                        self.comPort.dsrdtr = False
                    
                    if 'dtr' in flags.keys():
                        self.comPort.dtr = flags['dtr']
                    else:
                        self.comPort.dtr = False
            
                except ValueError:
                    coreUtils.SafeLogger('error', 'Com port initialization: value out of range!')
                else:
                    self.comPortStatus = True
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SaveOpenComPort(self):
        
        success = False
        
        if self.comPortStatus:
            try:
                if not self.comPort.isOpen():
                    self.comPort.open()
            except serial.SerialException:
                
                # to avoid any contact afterwards
                self.comPortStatus = False
            
                coreUtils.SafeLogger('error', 'Could not open serial port!')
            else:
                success = True
            
        return success
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SaveCloseComPort(self):
        
        success = False
        
        if self.comPortStatus:
            try:
                if self.comPort.isOpen():
                    self.comPort.close()
            except serial.SerialException:
                
                # to avoid any contact afterwards
                self.comPortStatus = False
                
                coreUtils.SafeLogger('error', 'Could not close serial port!')
            else:
                success = True
                
        return success
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SaveWriteToComPort(self, outData, **flags):
        
        success = False
        
        if self.SaveOpenComPort():
            
            try:
                self.comPort.write(outData)
            except (serial.SerialException, serial.SerialTimeoutException) as e:
                coreUtils.SafeLogger('error', 'Could not write: \'%s\' to port \'%s\'!' % (outData, self.comPortInfo[0]))
                    
            try:
                if not flags['leaveOpen']:
                    success = self.SaveCloseComPort()
            except KeyError:
                success = self.SaveCloseComPort()
            else:
                success = True
                
        return success
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SaveReadFromComPort(self, mode='', **flags):
        
        inData = bytes()
        
        if self.SaveOpenComPort():
            
            try:
                if mode == '':
                    inData = self.comPort.read()
                elif mode == 'line':
                    inData = self.comPort.readline()
                elif mode == 'waiting':
                    
                    if 'waitFor' and 'bePatient' in flags.keys():
                        waitingFor = 0
                        try:
                            maxTime    = int(flags['waitFor'])*1e3
                        except ValueError:
                            coreUtils.SafeLogger('error', 'Could not convert waiting time %s' % flags['waitFor'])
                        try:
                            patience    = int(flags['bePatient'])
                        except ValueError:
                            coreUtils.SafeLogger('error', 'Could not convert waiting time %s' % flags['bePatient'])
                            
                        while self.comPort.in_waiting == 0 and waitingFor < maxTime:
                            waitingFor += 1
                            sleep(1e-3)
                            
                        # collecting incoming bytes and wait max 'patience' ms for the next one
                        waitingFor = 0
                            
                        while self.comPort.in_waiting != 0 or waitingFor < patience:
                            inData += self.comPort.read(self.comPort.in_waiting)
                            
                            # in case there's something more just wait a bit...
                            if self.comPort.in_waiting == 0:
                                waitingFor += 1
                                sleep(1e-3)
                            
                    else:
                        while self.comPort.in_waiting != 0:
                            inData += self.comPort.read(self.comPort.in_waiting)
                            
            except (serial.SerialException, serial.SerialTimeoutException) as e:
                coreUtils.SafeLogger('error', 'Could not read bytes from port \'%s\'!' % self.comPortInfo[0])
                    
            try:
                if not flags['leaveOpen']:
                    self.SaveCloseComPort()
            except KeyError:
                self.SaveCloseComPort()
            
            if 'decode' in flags.keys():
                if flags['decode']:
                    inData = inData.decode('latin-1')
                
        return inData
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetPortStatus(self):
        return self.comPortStatus
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetPortInfo(self):
        return self.comPortInfo[1]
                