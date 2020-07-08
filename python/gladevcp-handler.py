#!/usr/bin/env python

import hal
import hal_glib
import glib
import os
import linuxcnc
import time
import re
import pango

class HandlerClass:
    COL_COLOR = 3
    COLOR_SELECTED = "#41C718"
    COLOR_NOT_SELECTED = "#FFFFFF"
    
    COL_TOOL_NAME_WIDTH = 0.60
    COL_TOOL_OPERATION_WIDTH = 0.35
    
    commands = [
        'cmd-start-tool-change',
        'cmd-stop-tool-change',
        'cmd-disable-tool-change',
        'cmd-probing',
        'cmd-reference-length',
        'cmd-tool-offset',
    ]
    
    def update_current_tool(self, current_tool_index):
        # This does not work for some reason, the color is not redrawn
        for i in range(0, len(self.liststore1)):
            if i == current_tool_index:
                self.liststore1[current_tool_index][self.COL_COLOR] = self.COLOR_SELECTED
            else:
                self.liststore1[current_tool_index][self.COL_COLOR] = self.COLOR_NOT_SELECTED
    
    def get_tool_name(self, tool_number):
        info = self.tooledit1.get_toolinfo(tool_number)
        if info:
            name = info[16]
        else:
            name = None
        return name
        
    def update_tools_in_program(self, tool_list):
        self.tooledit1.reload(self.toolfile)
        self.liststore1.clear()
        i = 0
        for tool in tool_list:
            description = self.get_tool_name(tool[0])
            if i == self.current_tool_index:
                color = self.COLOR_SELECTED
            else:
                color = self.COLOR_NOT_SELECTED
            self.liststore1.append([tool[0], description, tool[1], color])
            i += 1
    
    def on_file_loaded(self, stat, data=None):
        s = linuxcnc.stat()
        s.poll()
        self.current_tool_index = -1
        self.tools_in_file = self.get_tools_from_file(s.file)
        self.update_tools_in_program(self.tools_in_file)
        self.ref_tool.set_state(True)
        
    def __init__(self, halcomp,builder,useropts):
        self.inifile = linuxcnc.ini(os.environ["INI_FILE_NAME"])
        self.configpath = os.environ['CONFIG_DIR']
        self.toolfile = os.path.join( self.configpath, self.inifile.find("EMCIO", "TOOL_TABLE") )
        self.builder = builder
        self.halcomp = halcomp
        self.change_text = builder.get_object("lbl_tool_change_info")
        self.ref_tool = builder.get_object("reftool")
        
        self.command_value_to_name = {}
        value = 1
        for command in self.commands:
            self.halcomp.newpin(command, hal.HAL_FLOAT, hal.HAL_IN)
            hal.set_p(halcomp.getprefix() + "." + command, str(value))
            self.command_value_to_name[value] = command
            value = value + 1
        
        self.gcode_command = hal_glib.GPin(halcomp.newpin("gcode-command", hal.HAL_FLOAT, hal.HAL_IN))
        self.gcode_param = hal_glib.GPin(halcomp.newpin("gcode-parameter", hal.HAL_FLOAT, hal.HAL_IN))
        self.gcode_command.connect("value-changed", self.command_from_gcode)
        self.gcode_param.connect("value-changed", self.parameter_from_gcode)
        
        self.parameter = None
        self.tools_in_file = []
        
        self.tooledit1 = self.builder.get_object("tooledit1")
        self.tooledit1.set_filename(self.toolfile)
        
        self.liststore1 = self.builder.get_object("liststore1")
        self.treeview1 = self.builder.get_object("treeview1")
        
        # Set tool table columns
        tool_table_width = self.treeview1.get_property("width_request")
        self.cell_desc = self.builder.get_object("cell_desc")
        self.cell_desc.props.wrap_mode = pango.WRAP_WORD
        self.cell_desc.props.wrap_width = int(self.COL_TOOL_NAME_WIDTH * tool_table_width)
        self.cell_operation = self.builder.get_object("cell_operation")
        self.cell_operation.props.wrap_mode = pango.WRAP_WORD
        self.cell_operation.props.wrap_width = int(self.COL_TOOL_OPERATION_WIDTH * tool_table_width)
        
        self.current_tool_index = -1

    def parameter_from_gcode(self, hal_pin, data = None):
        self.parameter = hal_pin.get()
    
    def command_from_gcode(self, hal_pin, data = None):
        value = hal_pin.get()
        
        if value in self.command_value_to_name:
            command = self.command_value_to_name[value]
            parameter = ""
            if self.parameter is not None:
                parameter = str(self.parameter)
            
            if command == 'cmd-start-tool-change':
                hal.set_p("gladevcp.tool_change_ui", 'TRUE')
                tool_num = int(self.parameter)
                tool_name = self.get_tool_name(tool_num)
                if self.current_tool_index > -1:
                    self.ref_tool.set_state(False)
                if not tool_name:
                    tool_name = ''
                self.change_text.set_label("Please insert tool #%d %s" % (tool_num, tool_name))
                if (self.current_tool_index + 1) < len(self.tools_in_file):
                    if self.tools_in_file[self.current_tool_index + 1][0] == tool_num:
                        self.current_tool_index += 1
                        self.update_tools_in_program(self.tools_in_file)
            elif command == 'cmd-stop-tool-change':
                hal.set_p("gladevcp.tool_change_ui", "FALSE")
                pass
            elif command == 'cmd-probing':
                self.change_text.set_label("")
                if self.parameter is not None and int(self.parameter) > 0:
                    pass
                    #hal.set_p("gladevcp.probing-led", "1")
                else:
                    pass
                    #hal.set_p("gladevcp.probing-led", "0")
            elif command == 'cmd-reference-length':
                if self.parameter is not None:
                    hal.set_p("gladevcp.reflen", str(self.parameter))
            elif command == 'cmd-tool-offset':
                if self.parameter is not None:
                    hal.set_p("gladevcp.currlen", str(self.parameter))
            self.parameter = None

    @staticmethod
    def get_tools_from_file(file):
        tools = []
        with open(file) as fp:
            operation = ''
            for line in fp:
                
                if '(' in line:
                    match = re.search('\((.*)\)', line)
                    if match and match.group(1):
                        operation = match.group(1)
                pattern = '.*\sT([0-9]+)\sM6'
                match = re.search(pattern, line)
                if match and match.group(1):
                    tool = int(match.group(1))
                    tools.append((tool, operation))
                    operation = ""
        return tools
                
def get_handlers(halcomp,builder,useropts):
    return [HandlerClass(halcomp,builder,useropts)]
