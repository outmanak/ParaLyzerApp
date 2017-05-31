# -*- coding: utf-8 -*-
"""
Created on Wed May 31 14:31:42 2017

@author: localadmin
"""

import logging as log

try:
    from libs import coreUtilities as coreUtils
except ImportError:
    import coreUtilities as coreUtils

class Logger:
    
    def __init__(self, logFile=None, logToFile=False, logLevel=log.DEBUG, datefmt='%m/%d/%Y %I:%M:%S %p'):
            
        self._logFile    = logFile
        self._logToFile  = logToFile
        self._caller     = self.__class__.__name__        # use parent name for logger init
        self._logLevel   = logLevel
        
        # write anyway to file
        if self._logFile:
            self._logToFile = True
        # do we need to create a new name?
        elif self._logToFile:
            self._logFile = 'session_' + coreUtils.GetDateTimeAsString() + '.log'
            
        # initialize logger
        # create logger with callers name
        self.logger = log.getLogger(self._caller)
        self.logger.setLevel(self._logLevel)
        
        # create formatter
        formatter = log.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt=datefmt)
        
        # create file handler and set level to debug
        # all messages higher in priority are written to file
        if self._logToFile:
            
            # create folder, if necessary and store result
            # if something went wrong, use command prompt
            self._logToFile = coreUtils.SafeMakeDir('./log/')
            
            # folder should exist
            # if something went wrong before it's still save to try
            # two errors will be visible
            if not coreUtils.IsAccessible('./log/' + logFile, 'write'):
                # write file
                # later on used by logger
                # -> close immediately
                try:
                    open('./log/' + logFile, 'wt').close()
                except PermissionError:
                    print('ERROR: Could not create log file!\nCheck permission...')
                    self._logToFile = False
                    
            # create handler for writing logs to file
            ch = log.FileHandler('./log/' + logFile)
            ch.setLevel(log.DEBUG)
        
        # or just write them to prompt
        else:
            ch = log.StreamHandler()
            ch.setLevel(log.DEBUG)
                    
            
        # add formatter to ch
        ch.setFormatter(formatter)
        
        print('__init__ self.logger.handlers: %s' % self.logger.handlers)
        
        # add ch to logger
        # apparently Spyder messes up, so let's check if something is already there
        if self.logger.handlers == []:
            self.logger.addHandler(ch)
    
### -------------------------------------------------------------------------------------------------------------------------------

    def __del__(self):
        
        print('__del__ self.logger.handlers: %s' % self.logger.handlers)
            
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)
        
        del self.logger