# -*- coding: utf-8 -*-
"""
Created on Tue May  9 18:44:04 2017

@author: Martin Leonhardt (martin.leonhardt87@gmail.com)
"""

import tkinter as tk
        
class StatusBar(tk.Frame):
    
    def __init__(self, master, dLS='', dMS='', dRS=''):
        
        tk.Frame.__init__(self, master)
        
        self.pack(fill=tk.X, anchor=tk.S, side=tk.BOTTOM)
        
        self.defaultLeftStatus  = dLS
        self.defaultMidStatus   = dMS
        self.defaultRightStatus = dRS
        
        self.leftStatus  = tk.StringVar( value=self.defaultLeftStatus  )
        self.midStatus   = tk.StringVar( value=self.defaultMidStatus   )
        self.rightStatus = tk.StringVar( value=self.defaultRightStatus )
        
        kw = {
            'bd'     : 1,
            'relief' : tk.SUNKEN,
            'font'   : ('Helvetica',8,'normal'),
            'anchor': tk.W
        }
        
        self.leftStatusLabel  = tk.Label( master, textvariable=self.leftStatus , **kw )
        self.midStatusLabel   = tk.Label( master, textvariable=self.midStatus  , **kw )
        self.rightStatusLabel = tk.Label( master, textvariable=self.rightStatus, **kw )
        
        self.leftStatusLabel.pack ( pady=1, expand=tk.YES, side=tk.LEFT, fill=tk.X, anchor=tk.W )
        self.midStatusLabel.pack  ( pady=1, expand=tk.YES, side=tk.LEFT, fill=tk.X              )
        self.rightStatusLabel.pack( pady=1, expand=tk.YES, side=tk.LEFT, fill=tk.X, anchor=tk.E )
    
### -------------------------------------------------------------------------------------------------------------------------------
        
    def UpdateLeftStatus(self, txt):
        
        txt = self.defaultLeftStatus + txt
        
        self.leftStatus.set(txt)
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def UpdateMidStatus(self, txt):
        
        txt = self.defaultMidStatus + txt
        
        self.midStatus.set(txt)
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def UpdateRightStatus(self, txt):
        
        txt = self.defaultRightStatus + txt
        
        self.rightStatus.set(txt)
        
### -------------------------------------------------------------------------------------------------------------------------------
        
    def UpdateStatusBar(self, lT, mT, rT, default=True):
        
        if default:
            self.leftStatus.set ( self.defaultLeftStatus  + lT )
            self.midStatus.set  ( self.defaultMidStatus   + mT )
            self.rightStatus.set( self.defaultRightStatus + rT )
        else:
            self.leftStatus.set ( lT )
            self.midStatus.set  ( mT )
            self.rightStatus.set( rT )