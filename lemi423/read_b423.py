from os import listdir, path
import matplotlib.pyplot as plt
import numpy as np
import time
import struct
from tkinter import Tk, filedialog
import os

from spectrum import *


def headerToCoeffs(coeff):
    import re
    global volts,curr,lat,lon,alt,kmx,kmy,kmz,ax,ay,az
    match_number = re.compile('-?\ [+-]?[0-9]+\.?[0-9]*(?:[Ee]\ *[+-]?\ *[0-9]+)?')
    f = [float(x) for x in re.findall(match_number, coeff)]
    volts=f[2]
    curr=f[3]
    lat=f[5]
    lon=f[6]
    alt=f[7]
    kmx=f[10]
    kmy=f[11]
    ax=f[13]
    ay=f[14]

    
if __name__ == "__main__":

    print("select first .B423 file!")
    root = Tk()
    root.withdraw() 
    root.attributes('-topmost', True)
    absfile = filedialog.askopenfilename()
    [subfolder, firstfile]=os.path.split(os.path.abspath(absfile))
    print(subfolder,"listing files: ")

    files = [f for f in listdir(subfolder) if (path.isfile(path.join(subfolder, f)) and path.join(subfolder, f).endswith('.B423'))]
    x=len(files)
    if (x>0):
        print("processing",str(x),"files")
    else:
        print("no files found")
        exit()

    #read in first file, determine sample rate and coefficients
    j=0
    smplr=-1
    fabs = path.join(subfolder,files[0])
    fsize = path.getsize(fabs)
    rformat='<LHiiiiixxxx' #must be 30 bytes
    #<..low endian byte order  L..long(4)  H..ushort(2)   i..int(4)  x..1 byte    
    if (fsize > 0+1024+30):
        with open(fabs,'rb') as fin:
            header = fin.read(1024)
            headerToCoeffs(header.decode())
            print("kmx=",kmx)
            print("kmy=",kmy)
            print("ax=",ax)
            print("ay=",ay)
            data_str = fin.read(struct.calcsize(rformat))
            data_tuple = struct.unpack(rformat,data_str)
            startdate = data_tuple[0]
            print("starting at: "+time.strftime("%Y/%m/%d  %H:%M:%S", time.gmtime(startdate))+" UTC")
            while (data_tuple[1] >= smplr):
                data_str = fin.read(struct.calcsize(rformat))
                data_tuple = struct.unpack(rformat,data_str)
                smplr=max(smplr,data_tuple[1])
            smplr=smplr+1
            print("sample rate "+str(smplr)+"Hz determined")
    
    datapoints=smplr*60*10  #buffer length
    hours, rem = divmod(datapoints, 3600*smplr)
    minutes, rem = divmod(rem, 60*smplr)
    seconds, samples = divmod(rem, smplr)
    print(f'datapoints = {datapoints} corresponding {hours:02d}:{minutes:02d}:{seconds:02d}+{samples:d}samples')
    
    t=np.arange(1,datapoints)
    T = np.arange(datapoints)
    D = np.zeros((2,datapoints))
    i=0
    for f in files:
        fabs = path.join(subfolder,f)
        fsize = path.getsize(fabs)
        fsize = fsize - 1024
        if (fsize < 0):
            print("file "+f+" size "+fsize+" -> skipping")
            continue
        with open(fabs,'rb') as fin:
            i=i+1
            print("processing "+str(i)+". file",f)
            header = fin.read(1024)
            j=0
            k=0
            while((k*datapoints*30)<fsize):
                while (j<datapoints and (k*datapoints*30 + j*30)<fsize):
                    data_str = fin.read(struct.calcsize(rformat))
                    data_tuple = struct.unpack(rformat,data_str)
                    if (j==0):
                        startdate = data_tuple[0]+data_tuple[1]/smplr
                        
                    D[0][j]=kmx*data_tuple[2]+ax #Bx = Kmx*adc+Ax
                    D[1][j]=kmy*data_tuple[3]+ay #By                    
                
                    j=j+1

                k=k+1
                j=0
                #for each block of datapoints
                print("starting at: "+time.strftime("%Y/%m/%d  %H:%M:%S", time.gmtime(startdate))+" UTC")

                enddate=data_tuple[0]+data_tuple[1]/smplr + 1/smplr
                #T=np.arange(startdate,enddate,(enddate-startdate)/datapoints)
                #plotTime(T,D)
                plotSpec(D,start=startdate,end=enddate,smplr=smplr, folder=subfolder)



