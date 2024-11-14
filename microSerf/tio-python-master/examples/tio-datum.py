#!/usr/bin/env python3
"""
..
    Copyright: 2017 Twinleaf LLC
    Author: kornack@twinleaf.com

Log data!

"""

import tldevice
import argparse

parser = argparse.ArgumentParser(prog='tio_log', 
                                 description='Very simple logging utility.')

parser.add_argument("url", 
                    nargs='?',
                    default='tcp://localhost/', #default='COM13',
                    help='URL: tcp://localhost')
parser.add_argument("logfile", 
                    nargs='?', 
                    default='log.tsv',
                    help='Log filename: log.tsv')
parser.add_argument("--rpc", 
                    action='append', 
                    default=[],
                    type=lambda kv: kv.split(":"), 
                    help='Commands to be run on start; rpc:type:val')
args = parser.parse_args()

device = tldevice.Device(url=args.url, rpcs=args.rpc)

if device.data.stream_columns() != []:
  datadict = {}
  for datum, column in zip(device.data.stream(), device.data.stream_columns()):
    datadict[column] = datum

  print(f"Data: {datadict}")

