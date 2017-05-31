# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:44:04 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

from time import sleep

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
    



class ArduinoCore(CoreDevice):
    
    # serial port flags
    _baudrate = 115200
    _dtr      = False       # avoid pull-down of reset upon serial port opening
    
    # name for auto detection
    _usbName = 'Arduino Uno'
    
    # message for detection
    _detMsg = 'Try to detect Arduino Uno...'
    
    def __init__(self, ePairCallback=None, **flags):
        
        self.selectElectrodePairs = ePairCallback
            
        # setup com port
        flags['baudrate'] = self._baudrate
        flags['dtr']      = self._dtr
        
        CoreDevice.__init__(self, **flags)


            
        # use given chipConfig file or use default one
        self._chipConfigFile   = flags.get( 'chipConfigFile'  , './cfg/ChipConfig.json'   )
        
        # use given switchConfig file or use default one
        self._switchConfigFile = flags.get( 'switchConfigFile', './cfg/SwitchConfig.json' )
        
        # contains chamber-electrode connections, counting from 0 to 29
        # each two are one chamber with two different electrode pairs for counting and measuring viability
        # so 60 entries are in this file
        self.UpdateConfig( 'chc', self._chipConfigFile )
        
        # contains switch-electrode assignment, counting from -2 to 29
        # 64 switches are availble in total, for flexibility 32 can be used in both directions (stim+rec)
        # two of them are used for debugging on current PCB (v4.0 Ketki) ... -2,-1 are not accessible as array index
        # the order is related to the IC on the PCB, starting with 0 from the connector (Sebastian counted the pad IDs descending from 29 in the same direction)
        self.UpdateConfig( 'swc', self._switchConfigFile )
        
        # define empty electrode pair dictionary
        self._activeElectrodes = {
        # this dictionary contains several standard structures depending on the chamber that was selected
#                'ID': {
#                     'ePair': -1,
#                     'int'  : -1
#                }
            }
            
        self._debugMode = False

### -------------------------------------------------------------------------------------------------------------------------------

    def __del__(self):
        
        CoreDevice.__del__(self)
        
        
            
            
            
            
### -------------------------------------------------------------------------------------------------------------------------------

    def UpdateConfig(self, key, fName):
        
        success = True
        
        if key == 'chc':
            self.chipConfig = coreUtils.LoadJsonFile( fName, __name__ )
            
            if self.chipConfig != {}:
                self.chipConfigStatus = True
            else:
                self.chipConfigStatus = False
                success = False
                self.logger.error('Could not find chip config file: %s' % fName)
                
        elif key == 'swc':
            self.switchConfig = coreUtils.LoadJsonFile( fName, __name__ )
            
            if self.switchConfig != {}:
                self.switchConfigStatus = True
            else:
                self.switchConfigStatus = False
                success = False
                self.logger.error('Could not find switch config file: %s' % fName)
                
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------

    def SendMessage(self, msg):
        """ Send binary data to Arduino Uno.
            Line ending is \r.
            Serial port is kept open in case debug is enabled till answer from Arduino was received.
        """
        
        success = False
        
        if self.SaveOpenComPort():
            
            # write message
            # NOTE: encoding as byte is required by pySerial
            # do not forget '\n' (newline) for command recognition
            # NOTE: flush is deprecated with pySerial > v3.0
            msg += '\r'
            
            success = self.SaveWriteToComPort(msg.encode('latin-1'), leaveOpen=True)
            
            if success:
                if self._debugMode:
                    
                    inMsg = self.SaveReadFromComPort(mode='waiting', waitFor=1, bePatient=25, decode=True).replace('\n', ', ')
                    
                    self.logger.debug('Received message from Arduino: %s' % inMsg)
                        
        return success
    
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetActiveSwitchIndices(self, activeElectrodePair):
        '''gets the switch indices which are to be activated when the indicated chamber is active'''
        
        # init return value
        switchesToActivate = []
        
        if isinstance(activeElectrodePair, str):
            
            if 'res' in activeElectrodePair:
                switchesToActivate = [62, 63]
            elif 'short' in activeElectrodePair:
                switchesToActivate = [60, 61]
        else:
            # find corresponding electrode pair in chip config file
            padIdx = 0
            while padIdx < len(self.chipConfig['chamberToPad']):
                # get next pad setup
                pads = self.chipConfig['chamberToPad'][padIdx]
                # stop loop when correct electrode pair setup was found
                # use pads in subsequent code
                if pads['ePairId'] == activeElectrodePair:
                    break
                else:
                    padIdx += 1
                
            # in case loop left withput any results
            # e.g. an old file setup was used
            # just use the given variable as index
            if padIdx == len(self.chipConfig['chamberToPad']):
                pads = self.chipConfig['chamberToPad'][activeElectrodePair]
            
            self.logger.debug('pads: %s' % pads)
            
            # get switch index to close connection to stimulation/recording pad
            for switchId in range(len(self.switchConfig)):
                if (self.switchConfig[switchId]['padId'] == pads['stimPadId'] and self.switchConfig[switchId]['padType'] == 'stim'):
                    switchesToActivate.append(switchId)
                if (self.switchConfig[switchId]['padId'] == pads['recPadId']  and self.switchConfig[switchId]['padType'] == 'rec'):
                    switchesToActivate.append(switchId)
                    
        # make sure Arduino receives sorted list
        # otherwise daisy chaining might not work
        switchesToActivate.sort()
                    
        return switchesToActivate
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GenerateSendStream(self, activeElectrodePair, residenceTime=0):
        '''converts chosen chamber and electrode pair to bytes for sending via serial interface
           NOTE: all switches are updated at once (8 bytes + 1 byte for chamber and electrode encoding)
        '''
        
        sendBytes = bytes()
        
        if self.chipConfigStatus and self.switchConfigStatus:
        
            # support the two debugging switches on current PCB (v4.0 Ketki)
            # one with a resister (1k)
            # and the other with a short
            # NOTE: set DIO lines and residence time to zero
            if isinstance(activeElectrodePair, str):
                activeSwitches  = self.GetActiveSwitchIndices(activeElectrodePair)
                electrodeCoding = (0x00).to_bytes(1, 'big')
                
            elif isinstance(activeElectrodePair, int):
                
                # index in PcbConfig file, starting from 0 independent from routing
                activeSwitches = self.GetActiveSwitchIndices(activeElectrodePair)
                
                # chamber and electrode coding
                electrodeCoding = (activeElectrodePair & 0x1F).to_bytes(1, 'big')
                
            # first switch bytes
            # use switch index and convert to bytes
            for sw in activeSwitches:
                sendBytes += sw.to_bytes(1, 'big')
            
            # then chamber number, electrode pair as MSB (NOTE: only five bits are used)
            # append residence time encoded in four bytes
            sendBytes += electrodeCoding 
            sendBytes += residenceTime.to_bytes(4, 'big')
            
            self.logger.debug( 'Active electrode pair: %s' % activeElectrodePair                                                     )
            self.logger.debug( 'Active switches (abs): %s' % activeSwitches                                                          )
            self.logger.debug( 'Active switches: %s on device: %s' % ([i%8 for i in activeSwitches], [i//8 for i in activeSwitches]) )
            
            # wrap the text generated from sendBytes every two half-bytes and print it
            self.logger.debug( 'Prepare %s bytes for storing on Arduino: %s' % (len(activeSwitches)+5, coreUtils.GetTextFromByteStream(sendBytes)) )
    
        return sendBytes.decode('latin-1')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SetupArduino(self, **flags):
        
        success = True
        
        # check debug flag
        # it's also possible to set self.debugMode directly
        self.debugMode = flags.get('dbg', False)
        
        # empty stream
        sendStream = []

        ePairs = self.SelectElectrodePairs(**flags)
        
        if len(ePairs) == 0:
            success = False
        
            
        if success:
            
            # generate byte stream for all electrode pairs
            for ePair in ePairs:
                    
                stream = self.GenerateSendStream(ePair['ePair'], ePair['int'])
                
                # check for valid stream
                # otherwise stop loop
                if len(stream) != 0:
                    sendStream.append( stream )
                else:
                    success = False
                    break
            
                
        if success:
            
            # enable/disable debug for Arduino
            if self.debugMode:
                success = self.SendMessage('debug 1')
            else:
                success = self.SendMessage('debug 0')
                    
            
            # check if something is in stream
            if success and len(sendStream) != 0:
                # send byte stream for setting electrode pair setup
                # Arduino will just call the setups one by one
                # according to the defined timings
                sendStream = ''.join(sendStream)
                
                self.logger.debug('Sending %s bytes to Arduino... %s' % (len(sendStream), coreUtils.GetTextFromByteStream(sendStream)))
                
                success = self.SendMessage('setelectrodes %s %s' % (len(ePairs), sendStream))
                
                if not success:
                    self.logger.error('Failed.')
        
        return success
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def Start(self):
        return self.SendMessage('start')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def Stop(self):
        return self.SendMessage('stop')
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def EnableDebug(self):
        self._debugMode = True
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DisableDebug(self):
        self._debugMode = False
            
### -------------------------------------------------------------------------------------------------------------------------------
    
    def DefineElectrodePair(self, ePair, interval):
        
        # if key is all set new timings for all exisiting chambers
        # coming ones will have directly the timings according to the setup
        
        key = str(ePair)
        
        # but only if not already exists
        if key not in self.activeElectrodes.keys():
            self.activeElectrodes[key] = (self.GetStandardElectrodePair())
        
        self.activeElectrodes[key]['ePair'] = ePair
        self.activeElectrodes[key]['int']   = interval

        self.logger.debug('Selected electrode pair %s with interval %s us.' % (ePair, interval))
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def UndefineAllElectrodePairs(self):
        self.activeElectrodes = {}
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def SelectElectrodePairs(self, **flags):
        
        ePairs = []
        
        # use callback to select electrode pairs
        if self.selectElectrodePairs:
            ePairs = self.selectElectrodePairs(self.activeElectrodes, **flags)
            
        # otherwise just sort the list in ascending fashion
        else:
            for key, val in sorted(self.activeElectrodes.items()):
                ePairs.append( val )
                
        return ePairs
        
### -------------------------------------------------------------------------------------------------------------------------------
    
    def GetStandardElectrodePair(self):
        return {
                'ePair': -1,
                'int'  : -1
            }
            
            
            
            
###############################################################################
###############################################################################
###                     --- DEBUG CODE HERE ---                             ###
###############################################################################
###############################################################################

if __name__ == '__main__':
    
    # create Arduino instance
    arduino = ArduinoCore()
    
    # enable debug mode here to catch incoming messages
    arduino._debugMode = True
    
    # execute blinking test to check the connection and proper running of Arduino code
    arduino.SendMessage('test')
    
    # test might take a while...so better sleep
    sleep(4)
    
    # print all available commands
    arduino.SendMessage('help')
    
    # enable debug mode for Arduino
    arduino.SendMessage('debug 1')
    
    # generate debug stream and send command
    arduino.SendMessage( 'setelectrodes 1 %s' % arduino.GenerateSendStream('short') )
    
    # generate byte stream to select first electrode pair
    arduino.SendMessage( 'setelectrodes 1 %s' % arduino.GenerateSendStream(0)       )
    
    # disable debug mode for Arduino
    arduino.SendMessage('debug 0')