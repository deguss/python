#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
   author daniel.piri@artesyn.com
"""

from __future__ import print_function
import visa


def do_list():
    rm = visa.ResourceManager()
    dd = rm.list_resources_info()
    #import pdb; pdb.set_trace()
    print("  devices/interfaces and aliases")
    print("==================================")
    for x in dd:
        print("%20s \t%s" %(x,dd[x][4]))
    print("\n")
    return dd
    
def do_ask(dd):
    rm = visa.ResourceManager()
    for x in dd:
        if (x.startswith('GPIB')):
            print("%s: " %(x), end="")
            #import pdb; pdb.set_trace()

            try:
                device=rm.open_resource(x)
                print("\t%s" %(device.ask('*IDN?')))
                device.close()
            except :
                pass
if __name__ == "__main__":
    dd=do_list()
    do_ask(dd)
