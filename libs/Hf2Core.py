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

# in case this guy is used somewhere else
# we need different loading of modules
try:
    from libs.CoreDevice import CoreDevice
except ImportError:
    from CoreDevice import CoreDevice

try:
    from libs import coreUtilities as coreUtils
except ImportError:
    import coreUtilities as coreUtils


class Hf2Core(CoreDevice):
    
    __deviceId__         = ['dev10', 'dev275']
    __deviceApiLevel__   = 1
        
    __recordingDevices__ = '/demods/*/sample'   # device ID is added later...
    
    __maxStrmFlSize__    = 10     # 10 MB
    __maxStrmTime__      = 0.5    # 0.5 min
    
    # supported stream modes
    __storageModes__     = ['fileSize', 'recTime', 'tilterSync']
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def __init__(self, baseStreamFolder='./mat_files', storageMode='fileSize', **flags):
        
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
        self._recordingDevices = ''
        
        self._recordString = 'Stopped.'
        
        # flags if somethign during recording went wrong
        self._recordFlags = {
                    'dataloss'        : False,
                    'invalidtimestamp': False
                }
        
        # variables to count streams (folder + files)
        self._baseStreamFolder = baseStreamFolder
        self._streamFolder     = baseStreamFolder
        self._strmFlCnt        = 0
        self._strmFldrCnt      = 0
        
        # check if folder is available, if not create
        coreUtils.SafeMakeDir(self._baseStreamFolder, self)
        
        if storageMode in self.__storageModes__:
            self._storageMode = storageMode
        else:
            raise Exception('Unsupported storage mode: %s' % storageMode)
        
        flags['detCallback'] = self.DetectDeviceAndSetupPort
        
        CoreDevice.__init__(self, **flags)
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def __del__(self):

        self.StopPoll()
        
        CoreDevice.__del__(self)
        
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def DetectDeviceAndSetupPort(self):
        
        for device in self.__deviceId__:
            
            self.logger.info('Try to detect %s...' % device)
            
            try:
                (daq, device, props) = zhinst.utils.create_api_session( device, self.__deviceApiLevel__ )
            except RuntimeError:
                self.logger.info('Could not be found')
            else:
                self.logger.info('Created API session for \'%s\' on \'%s:%s\' with api level \'%s\'' % (device, props['serveraddress'], props['serverport'], props['apilevel']))
                
                self.deviceName        = device
                self.comPort           = daq
                self.comPortStatus     = props['available']
                self.comPortInfo       = ['', '%s on %s:%s' % (device.capitalize(), props['serveraddress'], props['serverport'])]
                self._recordingDevices = '/' + device + self.__recordingDevices__
                
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
                self._streamFolder = sF
                useGivenStreamFolder = True
            
            # if not, try to create new folders
        if not sF or not useGivenStreamFolder:
            sF = self._baseStreamFolder
            if coreUtils.SafeMakeDir(sF, self):
                sF += '/session_' + self.coreStartTime + '/'
                if coreUtils.SafeMakeDir(sF, self):
                    sF += 'stream%04d/' % self.strmFldrCnt
                    if coreUtils.SafeMakeDir(sF, self):
                        # set new stream folder to class var
                        self._streamFolder = sF
                        # increment folder counter for multiple streams
                        self._strmFldrCnt += 1
                    else:
                        success = False
            

        if success:
            
            # initialize new thread
            self._pollThread = threading.Thread(target=self._PollData)
            # once polling thread is started loop is running till StopPoll() was called
            self._poll = True
            # start parallel thread
            self._pollThread.start()
            
            self._recordString = 'Recording...'
        
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def StopPoll(self, **flags):
        
        if self._poll:
            # end loop in _PollData method
            self._poll = False
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
        self._recordFlags = {
                        'dataloss':False,
                        'invTimeStamp':False
                    }
        
        # check status of device... start if OK
        if self.comPortStatus:
            
            self.comPort.subscribe(self._recordingDevices)
            
            # clear old data from polling buffer
            self.comPort.sync()
            
            while self._poll:
                
                # lock thread to savely process
                self._pollLocker.acquire()
                
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
                    if key not in self._demods.keys():
                        self._demods.update({key: self._GetStandardRecordStructure()})
                    
                    # fill structure with new data
                    for k in self._demods[key].keys():
                        if k in dataBuf[key].keys():
                            self._demods[key][k] = sp.concatenate( [self._demods[key][k], dataBuf[key][k]] )
                            
                            # save flags for later use in GUI
                            # look at dataloss and invalid time stamps
                            if k in ['dataloss', 'invalidtimestamp'] and dataBuf[key][k]:
                                self.logger.warning('%s was recognized! Data might be corrupted!' % k)
                                self._recordFlags[k] = True
                    
                    
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
                if ( time() - streamTime ) / 60 > self.__maxStrmTime__:
                    self.WriteMatFileToDisk()
                    streamTime = time()
                
                # critical stuff is done, release lock
                self._pollLocker.release()
                    
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
        return self._streamFolder
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def WriteMatFileToDisk(self):
        
        # create this just for debugging...
        outFileBuf = {'demods': []}
            
        for key in self.demods.keys():
            buf = {}
            for k in self.demods[key]:
                buf[k] = self.demods[key][k]
            outFileBuf['demods'].append(buf)
            
        sp.io.savemat(self._streamFolder+'stream_%05d.mat'%self._strmFlCnt, {'%s'%self.deviceName: outFileBuf})
        
        # memory leak was found...try to fix it
        del self._demods
        
        # clear buffer for next recording
        self._demods = {}

        # increment
        self._strmFlCnt += 1
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetRecordingString(self):
        return self._recordString
            
            
            
            
###############################################################################
###############################################################################
###                      --- YOUR CODE HERE ---                             ###
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    hf2 = Hf2Core()
    
    