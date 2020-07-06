#!/usr/bin/env python

import hal
import hal_glib
import os
import linuxcnc
import time

class HandlerClass:
    commands = [
        'cmd-start-tool-change',
        'cmd-stop-tool-change',
        'cmd-disable-tool-change',
        'cmd-probing',
        'cmd-reference-length',
        'cmd-tool-offset',
    ]
    
    def on_led_change(self,hal_led,data=None):
        '''
        the gladevcp.change led had a transition
        '''
        if hal_led.hal_pin.get():
            if self.halcomp["number"] > 0.0:
                self.change_text.set_label("Insert too number %d" % (int(self.halcomp["number"])))
            else:
                self.change_text.set_label("Remove tool")
        else:
            self.change_text.set_label("")

    def __init__(self, halcomp,builder,useropts):
        self.inifile = linuxcnc.ini(os.environ["INI_FILE_NAME"])
        self.halcomp = halcomp
        self.change_text = builder.get_object("change-text")
        self.ref_tool = builder.get_object("reftool")
        
        self.command_value_to_name = {}
        value = 1
        for command in self.commands:
            self.halcomp.newpin(command, hal.HAL_FLOAT, hal.HAL_IN)
            hal.set_p(halcomp.getprefix() + "." + command, str(value))
            self.command_value_to_name[value] = command
            value = value + 1
        
        din_pin = self.inifile.find("TOOL_CHANGE_PINS", "DIN_UI_PIN")
        self.din_pin = "motion.digital-in-0" + str(din_pin)
        self.halcomp.newpin('din-pin-num', hal.HAL_FLOAT, hal.HAL_IN)
        hal.set_p(halcomp.getprefix() + "." + 'din-pin-num', din_pin)
        
        self.gcode_command = hal_glib.GPin(halcomp.newpin("gcode-command", hal.HAL_FLOAT, hal.HAL_IN))
        self.gcode_param = hal_glib.GPin(halcomp.newpin("gcode-parameter", hal.HAL_FLOAT, hal.HAL_IN))
        self.gcode_command.connect("value-changed", self.command_from_gcode)
        self.gcode_param.connect("value-changed", self.parameter_from_gcode)
        
        self.parameter = None

    def parameter_from_gcode(self, hal_pin, data = None):
        self.parameter = hal_pin.get()
        print "####### Got parameter " + str(self.parameter)
    
    def command_from_gcode(self, hal_pin, data = None):
        value = hal_pin.get()
        
        if value in self.command_value_to_name:
            command = self.command_value_to_name[value]
            parameter = ""
            if self.parameter is not None:
                parameter = str(self.parameter)
            print "##### Command from gcode: " + str(command) + ", parameter: " + parameter
            
            if command == 'cmd-start-tool-change':
                hal.set_p("gladevcp.enable", "TRUE")
                if self.parameter is not None:
                    self.change_text.set_label("Insert tool number %d" % int(self.parameter))
            elif command == 'cmd-stop-tool-change':
                hal.set_p("gladevcp.enable", "FALSE")
            elif command == 'cmd-probing':
                if self.parameter is not None and int(self.parameter) > 0:
                    hal.set_p("gladevcp.probing-led", "1")
                else:
                    hal.set_p("gladevcp.probing-led", "0")
            elif command == 'cmd-reference-length':
                if self.parameter is not None:
                    hal.set_p("gladevcp.reflen", str(self.parameter))
            elif command == 'cmd-tool-offset':
                if self.parameter is not None:
                    hal.set_p("gladevcp.currlen", str(self.parameter))
            self.parameter = None
                
def get_handlers(halcomp,builder,useropts):
    return [HandlerClass(halcomp,builder,useropts)]
