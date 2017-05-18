# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:44:04 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

# size estimation stuff
from sys import getsizeof, stderr
from itertools import chain
from collections import deque

import os
import logging as log
import binascii
import textwrap
import json
from datetime import datetime

_logger = None

    
### -------------------------------------------------------------------------------------------------------------------------------
    
def InitLogger(logFile='', caller='coreUtilities'):
    
    global _logger
    
    usePrompt = False
    
    # if _logger == None:
    
    # create logger with module name
    _logger = log.getLogger(caller)
    _logger.setLevel(log.DEBUG)
    
    # create formatter
    formatter = log.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    
    # create file handler and set level to debug
    # all messages higher in priority are written to file
    if logFile != '':
        
        # create folder, if necessary
        if not os.path.exists('./log/'):
            try:
                os.makedirs('./log/')
            except OSError:
                SafeLogger('error', 'Could not create folder for log file!\n...use Command prompt instead.')
                usePrompt = True
    
        # folder should exist
        # if something went wrong before it's still save to try
        # two errors will be visible
        if not IsAccessible('./log/' + logFile, 'write'):
            # write file
            # later on used by logger
            # -> close immediately
            try:
                open('./log/' + logFile, 'wt').close()
            except PermissionError:
                SafeLogger('error', 'Could not create log file!\nCheck permission...')
                usePrompt = True
    else:
        usePrompt = True
    
    # use command prompt in case something doesnt work with the files
    if usePrompt:
        ch = log.StreamHandler()
        ch.setLevel(log.DEBUG)
    else:
        ch = log.FileHandler('./log/' + logFile)
        ch.setLevel(log.DEBUG)
        
    # add formatter to ch
    ch.setFormatter(formatter)
    
    # add ch to logger
    _logger.addHandler(ch)
    
    return _logger

### -------------------------------------------------------------------------------------------------------------------------------

def TerminateLogger(caller='coreUtilities'):
    
    logger = log.getLogger(caller)
        
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)
            
    del logger

### -------------------------------------------------------------------------------------------------------------------------------

def SafeLogger(level, msg):
    
    if _logger:
        if level == 'debug':
            _logger.debug(msg)
        elif level == 'info':
            _logger.info(msg)
        elif level == 'warning':
            _logger.warning(msg)
        elif level == 'error':
            _logger.error(msg)
    else:
        if level == 'debug':
            print('DEBUG: %s' % msg)
        elif level == 'info':
            print('INFO: %s' % msg)
        elif level == 'warning':
            print('WARNING: %s' % msg)
        elif level == 'error':
            print('ERROR: %s' % msg)

### -------------------------------------------------------------------------------------------------------------------------------

def LoadJsonFile(fName):
    
    jsonStruct = {}
    
    if IsAccessible(fName):
        try:
            # file is opened, read and automatically closed
            with open(fName, 'rt') as f:
                jsonStruct = json.load(f)
        except PermissionError:
            _logger.error('Could not access file: \'%s\'! Please check permissions...' % fName)
        except FileNotFoundError:
            _logger.error('Could not find file: \'%s\'!' % fName)
        except IOError:
            _logger.error('Could not read file: \'%s\'!' % fName)
        except ValueError:
            _logger.error('Could not encode JSON structure from file: \'%s\'!' % fName)
    
    return jsonStruct

### -------------------------------------------------------------------------------------------------------------------------------

def DumpJsonFile(jsonStruct, fName):
    
    success = True
    
    try:
        # file is opened, read and automatically closed
        with open(fName, 'wt') as f:
            json.dump(jsonStruct, f)
    except PermissionError:
        _logger.error('Could not access file: \'%s\'! Please check permissions...' % fName)
        success = False
        raise
    except FileNotFoundError:
        _logger.error('Could not find file: \'%s\'!' % fName)
        success = False
        raise
        
    return success
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def IsIdentical(f1, f2):
    return os.path.samefile(f1, f2)
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def IsAccessible(f, flag='read'):
    
    result = False
    
    if flag == 'read':
        result = os.access(f, os.R_OK)
    elif flag == 'write':
        result = os.access(f, os.W_OK)
    
    return result
        
### -------------------------------------------------------------------------------------------------------------------------------
    
def GetFolderFromFilePath(p):
    return os.path.dirname(p)
        
### -------------------------------------------------------------------------------------------------------------------------------
    
def GetRelativePath(absPath):
    
    if os.path.isfile(absPath):
        try:
            relPath = './' + os.path.relpath(absPath).replace('\\', '/')
        except ValueError:
            SafeLogger('error', 'Invalid path \'%s\'' % absPath)
    else:
        try:
            relPath = './' + os.path.split(absPath)[-1] + '/'
        except TypeError:
            SafeLogger('error', 'Invalid path \'%s\'' % absPath)
        
    return relPath
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def SafeMakeDir(folder):
    
    success = True
    
    # in case user passed file instead of folder...
    if os.path.isfile(folder):
        folder = os.path.dirname(folder)
    
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
            
            # try logger, if initialized
            SafeLogger('info', 'Created folder \'%s\'' % folder)
                
        except OSError:
            # try logger, if initialized
            SafeLogger('error', 'Could not create folder \'%s\'!' % folder)
            
    return success
    
### -------------------------------------------------------------------------------------------------------------------------------
    
def ToBool(val):
    if val:
        return True
    else:
        return False
                
### -------------------------------------------------------------------------------------------------------------------------------
    
def GetDateTimeAsString():
    return datetime.now().strftime('%Y%m%d_%H%M%S')
    
### -------------------------------------------------------------------------------------------------------------------------------

def GetMinSecFromString(tString):
    
    secs = 0
    mins = 0
    
    # just seconds
    if tString.find(':') == -1:
        try:
            secs = int(tString)
        except ValueError:
            pass
        else:
            if secs > 59:
                secs = secs-60
                mins = 1
                
    # minutes and seconds
    else:
        tString = tString.split(':')
        
        try:
            mins = int(tString[0])
            secs = int(tString[1])
        except ValueError:
            pass
    
    return mins, secs

### -------------------------------------------------------------------------------------------------------------------------------
    
def GetTextFromByteStream(bStream, group=2):
    if isinstance(bStream, str):
        return textwrap.wrap(binascii.b2a_hex(bStream.encode('latin-1')).decode('latin-1'), group)
    else:
        return textwrap.wrap(binascii.b2a_hex(bStream).decode('latin-1'), group)
        
### -------------------------------------------------------------------------------------------------------------------------------

def GetTotalSize(o, handlers={}, verbose=False):
    """ Returns the approximate memory footprint an object and all of its contents.

    Automatically finds the contents of the following builtin containers and
    their subclasses:  tuple, list, deque, dict, set and frozenset.
    To search other containers, add handlers to iterate over their contents:

        handlers = {SomeContainerClass: iter,
                    OtherContainerClass: OtherContainerClass.get_elements}

    """
    dict_handler = lambda d: chain.from_iterable(d.items())
    all_handlers = {tuple: iter,
                    list: iter,
                    deque: iter,
                    dict: dict_handler,
                    set: iter,
                    frozenset: iter,
                }
    all_handlers.update(handlers)     # user handlers take precedence
    seen = set()                      # track which object id's have already been seen
    default_size = getsizeof(0)       # estimate sizeof object without __sizeof__

    def sizeof(o):
        if id(o) in seen:       # do not double count the same object
            return 0
        seen.add(id(o))
        s = getsizeof(o, default_size)

        if verbose:
            _logger.info(s, type(o), repr(o), file=stderr)

        for typ, handler in all_handlers.items():
            if isinstance(o, typ):
                s += sum(map(sizeof, handler(o)))
                break
        return s

    return sizeof(o)