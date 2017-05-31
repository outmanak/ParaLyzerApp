# -*- coding: utf-8 -*-
"""
Created on Tue May  9 17:23:26 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

import threading
import zhinst.utils
#import numpy as np
import scipy as sp

from time import sleep, time, perf_counter

from libs import coreUtilities as coreUtils
from libs.CoreDevice import CoreDevice


class ziHf2Core(CoreDevice):
    
    _deviceId       = ['dev10', 'dev275']
    _deviceApiLevel = 1
        
    _recordingDevices = '/demods/*/sample'   # device is added later...
    
    _maxStrmFlSize = 10     # 10 MB
    _maxStrmTime   = 0.5    # 0.5 min
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def __init__(self, baseStreamFolder='./mat_files', **flags):
        
        # store chosen device name here
        self.deviceName = None
        
        # dictionary to store all demodulator results
        self._demods = {}
        
        # to stop measurement
        # initially no measurement is running
        self._poll       = False
        self._pollThread = None
        # create locker to savely run parallel threads
        self._pollLocker = threading.Lock()
        
        # not know so far, cause no device is connected
        self.recordingDevices = ''
        
        self.recordString = 'Stopped.'
        
        # flags if somethign during recording went wrong
        self.recordFlags = {
                    'dataloss'        : False,
                    'invalidtimestamp': False
                }
        
        # variables to count streams (folder + files)
        self.baseStreamFolder = baseStreamFolder
        self.streamFolder     = baseStreamFolder
        self.strmFlCnt        = 0
        self.strmFldrCnt      = 0
        
        flags['detCallback'] = self.DetectDeviceAndSetupPort
        
        CoreDevice.__init__(self, **flags)
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def __del__(self):
        
#        self.stopMeas = True
#        
#        sleep(50e-3)
#        
#        if self.pollThread:
#            self.pollThread.join()

        self.StopPoll()
        
        CoreDevice.__del__(self)
        
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def DetectDeviceAndSetupPort(self):
        
        for device in self._deviceId:
            
            self.logger.info('Try to detect %s...' % device)
            
            try:
                (daq, device, props) = zhinst.utils.create_api_session( device, self._deviceApiLevel )
            except RuntimeError:
                self.logger.info('Could not be found')
            else:
                self.logger.info('Created API session for \'%s\' on \'%s:%s\' with api level \'%s\'' % (device, props['serveraddress'], props['serverport'], props['apilevel']))
                
                self.deviceName       = device
                self.comPort          = daq
                self.comPortStatus    = props['available']
                self.comPortInfo      = ['', '%s on %s:%s' % (device.capitalize(), props['serveraddress'], props['serverport'])]
                self.recordingDevices = '/' + device + self._recordingDevices
                
                # no need to search further
                break
                
        return self.comPortStatus
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StartPoll(self, sF=None):
        
        success              = True
        useGivenStreamFolder = False
        
        # check if stream folder was given
        if sF:
            if coreUtils.IsAccessible(sF, 'write'):
                self.streamFolder = sF
                useGivenStreamFolder = True
            
            # if not, try to create new folders
        if not sF or not useGivenStreamFolder:
            sF = self.baseStreamFolder
            if coreUtils.SafeMakeDir(sF):
                sF += '/session_' + self.coreStartTime + '/'
                if coreUtils.SafeMakeDir(sF):
                    sF += 'stream%04d/' % self.strmFldrCnt
                    if coreUtils.SafeMakeDir(sF):
                        # set new stream folder to class var
                        self.streamFolder = sF
                        # increment folder counter for multiple streams
                        self.strmFldrCnt += 1
                    else:
                        success = False
            

        if success:
            
            # initialize new thread
            self.pollThread = threading.Thread(target=self.PollDataFromHF2)
            # once polling thread is started loop is running till StopPoll() was called
            self._poll = True
            # start parallel thread
            self.pollThread.start()
            
            self.recordString = 'Recording...'
        
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StopPoll(self, **flags):
        
        if self._poll:
            self._poll = True
            # end poll thread
            self.pollThread.join()
            
            # write last part of the data to disk
            self.WriteMatFileToDisk()
            # reset file counter for next run
            self.strmFlCnt = 0
            
            if 'prc' in flags:
                if flags['prc']:
                    self.recordString = 'Paused...'
                else:
                    self.recordString = 'Stopped.'
            else:
                self.recordString = 'Stopped.'
            
#            plt.plot(self.timer['idx'], self.timer['elt'])
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def IsPolling(self):
        return self._poll
        
### -------------------------------------------------------------------------------------------------------------------------------

    def _PollData(self):
        
        # for lag measurement
        idx   = 0
        start = perf_counter()
        self.timer = {'idx':[], 'elt':[]}
                
        # get stream time
        streamTime = time()

        # clear from last run
        self.dataloss     = False
        self.invTimeStamp = False
        
        # check status of device... start if OK
        if self.comPortStatus:
            
            self.comPort.subscribe(self.recordingDevices)
            
            # clear old data from polling buffer
            self.comPort.sync()
            
            while self._poll:
                
                # lock thread to savely process
                self.pollLocker.acquire()
                
                # for lag debugging
                self.timer['idx'].append(idx)
                idx += 1
                self.timer['elt'].append(perf_counter()-start)
                
                # for lag debugging
                start = perf_counter()

                # fetch data
                # block for 1 ms, timeout 10 ms, throw error if data is lost and return flat dictionary
                # NOTE: poll downloads all data since last poll, sync or subscription
                dataBuf = self.comPort.poll(1e-3, 10, 0x04, True)
                
                # get all demods in data stream
                for key in dataBuf.keys():
                    
                    # check if demodulator is already in dict, add if not (with standard structure)
                    if key not in self.demods.keys():
                        self.demods.update({key: self.GetStandardRecordStructure()})
                    
                    # fill structure with new data
                    for k in self.demods[key].keys():
                        if k in dataBuf[key].keys():
                            self.demods[key][k] = sp.concatenate( [self.demods[key][k], dataBuf[key][k]] )
                            
                            # save flags for later use in GUI
                            # look at dataloss and invalid time stamps
                            if k in ['dataloss', 'invalidtimestamp'] and dataBuf[key][k]:
                                self.logger.warning('%s was recognized! Data might be corrupted!' % k)
                                self.recordFlags[k] = True
                    
                    
########################################################
#   --- THIS IS HERE FOR SIMPLE PLOTTING REASONS ---   #
########################################################
                    
#                    # get data from current demodulator
#                    x = dataBuf[key]['x']
#                    y = dataBuf[key]['y']
#                    # calc abs value from real+imag
#                    r = np.sqrt(x**2 + y**2)
#                    
#                    # check if demodulator is already in dict, add if not (with standard structure)
#                    if key not in self.demods.keys():
#                        self.demods.update({key: self.GetStandardHf2Dict()})
#                    
#                        # store first timestamp as a reference, if not available
#                        if self.demods[key]['timeRef'] == -1:
#                            self.demods[key]['timeRef'] = dataBuf[key]['timestamp'][0]
#                    
#                    # calculate real time with reference and clock base and append to array
#                    self.demods[key]['time'] = np.concatenate([self.demods[key]['time'], (dataBuf[key]['timestamp'] - self.demods[key]['timeRef']) / 210e6])
#                    
#                    # append data points
#                    self.demods[key]['r'] = np.concatenate([self.demods[key]['r'], r])
                    
                
                # if file size is around 10 MB create a new one
#                if (self.total_size(self.demods) // 1024**2) > (self._maxStrmFlSize-1):
                if ( time() - streamTime ) / 60 > self._maxStrmTime:
                    self.WriteMatFileToDisk()
                    streamTime = time()
                
                # critical stuff is done, release lock
                self.pollLocker.release()
                    
                    # unsubscribe after finished record event
            self.comPort.unsubscribe('*')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetRecordFlags(self):
        return self.recordFlags
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def _GetStandardRecordStructure(self):
        return {
                    'x':         sp.array([]),
                    'y':         sp.array([]),
                    'timestamp': sp.array([]),
                    'frequency': sp.array([]),
#                    'phase':     np.array([]),
                    'dio':       sp.array([])
#                    'auxin0':    np.array([]),
#                    'auxin1':    np.array([])
                    
# just for the test with plotting
#                    'r': np.array([]),
#                    'time': np.array([]),
#                    'timeRef': -1
                }
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetCurrentStreamFolder(self):
        return self.streamFolder
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def _WriteMatFileToDisk(self):
        
        # create this just for debugging...
        outFileBuf = {'demods': []}
            
        for key in self.demods.keys():
            buf = {}
            for k in self.demods[key]:
                buf[k] = self.demods[key][k]
            outFileBuf['demods'].append(buf)
            
        sp.io.savemat(self.streamFolder+'stream_%05d.mat'%self.strmFlCnt, {'%s'%self.deviceName: outFileBuf})
        
        # memory leak was found...try to fix it
        del self.demods
        
        # clear buffer for next recording
        self.demods = {}

        # increment
        self.strmFlCnt += 1
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetRecordingString(self):
        return self.recordString