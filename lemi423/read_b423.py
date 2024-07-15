from os import listdir, path
import matplotlib.pyplot as plt
import numpy as np
import time
from datetime import datetime, timedelta
import struct
from tkinter import Tk, filedialog
from tkinter.messagebox import askyesno
import os
from tkinter_ask import *
from pdb import *

from spectrum import *

#fext='.B423'
fext='.b423'

       
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

def time_to_next_hour(timestamp):
    current_time = datetime.datetime.fromtimestamp(timestamp, datetime.UTC)
    print("recording starts at:      "+str(current_time))
    if (current_time.second == 0 and current_time.minute == 0):
        next_hour = current_time
    else:
        next_hour = current_time.replace(microsecond=0, second=0, minute=0) + timedelta(hours=1)
    print("processing will start at: "+str(next_hour))
    time_diff = next_hour - current_time
    return int(time_diff.total_seconds())

    
if __name__ == "__main__":

    print("select first .B423 file!")    
    absfile = filedialog.askopenfilename()
    [subfolder, firstfile]=os.path.split(os.path.abspath(absfile))
    print(subfolder,"listing files: ")

    files = [f for f in listdir(subfolder) if (path.isfile(path.join(subfolder, f)) and path.join(subfolder, f).endswith(fext))]
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
            print("latitude="+str(lat/100)+" N longitude="+str(lon/100)+" E altitude="+str(alt))
            print("Battery: "+str(volts)+"V")
            data_str = fin.read(struct.calcsize(rformat))
            data_tuple = struct.unpack(rformat,data_str)
            startdate = data_tuple[0]
            while (data_tuple[1] >= smplr):
                data_str = fin.read(struct.calcsize(rformat))
                data_tuple = struct.unpack(rformat,data_str)
                smplr=max(smplr,data_tuple[1])
            smplr=smplr+1
            print("sample rate "+str(smplr)+"Hz determined")
            skip_s = time_to_next_hour(startdate)
            ss = int(skip_s * smplr)
            print(f'skipping {skip_s}s or ({round(skip_s/60,2)}min) or {ss}samples')

    duration = ask_duration("How many hours of data should each plot be made of?",
                    ["10min", "1h", "6h", "12h", "24h"])
    print (duration)
    answ_1 = askyesno("Display or background processing", "Do you want the plots to be displayed?")

    if ("10min" in duration):
        buf_size=smplr*60*10
    elif ("1h" in duration):
        buf_size=smplr*60*60*1
    elif ("6h" in duration):
        buf_size=smplr*60*60*6
    elif ("12h" in duration):
        buf_size=smplr*60*60*12
    else:
        buf_size=smplr*60*60*24

        
    D = np.zeros(buf_size)
    W = np.zeros(buf_size)

    i = 0       #file counter
    buf = 0     #buffer counter
    elem = 0
    for f in files:
        nextFile=False
        fabs = path.join(subfolder,f)
        fsize = path.getsize(fabs)
        fsize = fsize - 1024
        if (fsize < 30):
            print(f'file {f} size {fsize} -> skipping')
            continue
        with open(fabs,'rb') as fin:
            i=i+1
            est_sampl = fsize/30
            est_len = est_sampl/smplr/3600
            print(f'processing {i}. file \"{f}\" estimated length = {round(est_len,2)} hours')
            print(f'buffer has already {elem} elements, buf_size={buf_size}')
            
            header = fin.read(1024)     #throw away header
            if (i==1 and ss < fsize/30):
                fin.read(ss*30)         #throw away as many samples as to next full hour
                fsize = fsize - ss*30
                ss = 0

            while (elem < buf_size and not nextFile): 
                while (elem < buf_size): 
                    data_str = fin.read(30)
                    try:
                        data_tuple = struct.unpack(rformat,data_str)
                    except:
                        print("<30 bytes at EOF discarded")
                        print(f'buf:{buf} + elem:{elem} +ss:{ss} < buf_size:{buf_size}')
                        nextFile = True
                        break
                    if (elem==0):
                        startdate = data_tuple[0]+data_tuple[1]/smplr
                        print("\tstart: "+time.strftime("%H:%M:%S", time.gmtime(startdate)))
                           
                    D[elem] = 1.1704773628121347e-06 * (data_tuple[2] - 17223800) #mV calibrated
                    D[elem] = D[elem]*0.09837  #scale to nA
                    W[elem] = 1.1343332263852341e-07 * (data_tuple[3] - 18144000) #mV calibrated in +20dB setting
                    W[elem] = W[elem]*0.09837  #scale to nA since amplification 20dB
                            
                    elem=elem+1
                    if (elem >= fsize/30):  #EOF 
                        break

                
                if (elem >= buf_size or i==len(files)):   #evaluate only if buffer full
                    enddate=data_tuple[0]+data_tuple[1]/smplr + 1/smplr
                    print("\tend:   "+time.strftime("%H:%M:%S", time.gmtime(enddate)))
                    
                    D=np.trim_zeros(D, 'b')                  #remove trailing 0 elements
                    W=np.trim_zeros(W, 'b')

                    decimator1 = 50 #resample -> fnyquist = 2.5Hz
                    Dres = np.interp(np.arange(0, len(D), decimator1), np.arange(0, len(D)), D)

                    decimator2 = 50 #resample -> fnyquist = 2.5Hz
                    Wres = np.interp(np.arange(0, len(W), decimator2), np.arange(0, len(W)), W)

                    #convert aenometer impulses to wind speed
                    #W=W-np.mean(W)                    
                    #plotCurrentAndWind(Dres, W, start=startdate, disp=answ_1, smplr=smplr/decimator, folder=subfolder)
                    plotCurrentAndCurrent(D=Dres, fs1=smplr/decimator1, W=Wres, fs2=smplr/decimator2, start=startdate, disp=answ_1, folder=subfolder)


                    #print(f'mean(D)={np.mean(D)}, mean(W)={np.mean(W)}')
                    #print(f'200/mean(D)={200/np.mean(D)}, mean(W)={200/np.mean(W)}')
                    #figure
                    #plot(D)
                    #plot(W)
                    #plt.show()                    
                    #pdb.set_trace()

                    D = np.zeros(buf_size)
                    W = np.zeros(buf_size)
                    elem = 0
                
                



