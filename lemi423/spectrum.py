import matplotlib.pyplot as plt
import time
import numpy as np
import csv
import os
import pdb

labels=["Bx","By","Bz","Ex","Ey"]

#returns the next power of 2
def next_pow_2(x):
    return 1<<(x-1).bit_length()

def plotTime(T, D):

    #data is a matrix with as many rows as subplots needed
    n=D.shape[0]
    fig, ax = plt.subplots(n, figsize=(12,7), sharex=True)
    ax[0].set_title("recording of the magnetic field")

    startdate=time.strftime("%H:%M:%S",time.gmtime(T[0]))
    enddate=time.strftime("%H:%M:%S",time.gmtime(T[-1]))
    
    for i in range(0,n):
        ax[i].plot(T, D[i],  linewidth=0.2)
        #ax[i].scatter(T[::11], D[i][::11], s=0.2)
        #ax[i].scatter(T, D[i], s=0.2)
        ax[i].grid(True)
        ax[i].set_ylabel(labels[i])
        ax[i].set_ylim([-5000,5000])
        ax[i].set_xlim([T[0],T[-1]])
     
    ax[-1].set_xlabel('time (UTC)')
    xt=ax[-1].get_xticks()
    xtt=[]
    for x in xt:
        xtt.append(time.strftime("%H:%M:%S",time.gmtime(x)))
    ax[-1].set_xticks(xt)
    ax[-1].set_xticklabels(xtt)

    

    plt.tight_layout()    
    plt.pause(0.001)
    plt.show()
    
    

def plotSpec(D, start, end, smplr, folder):

    #data is a matrix with as many rows as subplots needed
    n=D.shape[0]
    fig, ax = plt.subplots(n, figsize=(12,7), sharex=True)
    ax[0].set_title("Magnetic field spectrum")

    startdate=time.strftime("%Y%m%d_%H%M%S",time.gmtime(start))
    
    span=end-start
    nfft=next_pow_2(smplr*10)
    print(f'span = {span}s, Fs={smplr}Hz, nfft={nfft}')
    #f = np.fft.rfftfreq(nfft, 1.0/smplr) # prepare the frequency array



    for i in range(0,n):
        Pxx, freqs, bins, im = ax[i].specgram(D[i], NFFT=nfft, Fs=smplr, noverlap=nfft/2)
        ax[i].set_ylabel(labels[i])
        #ax[i].set_xlim([start,end])
     
    ax[-1].set_xlabel('time (UTC)')
    xt=ax[-1].get_xticks()
    xtt=[]
    for x in xt:
        xtt.append(time.strftime("%H:%M:%S",time.gmtime(x+start)))
    ax[-1].set_xticks(xt)
    ax[-1].set_xticklabels(xtt)

    
    try:
        filename=os.path.join(folder,"sp"+startdate+".png")
        fig.savefig(filename, dpi=100)
    except:
        print("save error!")
    else:
        print(filename,"saved!")
    
    
    #plt.tight_layout()    
    #plt.pause(0.001)
    #plt.show()
    

if __name__ == "__main__":
    l=100000
    t=np.arange(1,l)
    T = np.arange(l)
    D = np.zeros((2,l))
    D[0] = 3000*np.sin(40*T)
    D[1] = 1000*np.sin(12*T)
    #plotTime(T,D)
    plotSpec(D,0,1,500,"E:\\")
    

