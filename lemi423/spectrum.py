import matplotlib.pyplot as plt
from pylab import *
import time
import numpy as np
import scipy.stats as sps
import matplotlib.pyplot as plt
import os
import pdb

labels=["Bx","By","Bz","Ex","Ey"]

#returns the next power of 2
def next_pow_2(f):
    x=int(f)
    return 1<<(x-1).bit_length()

def plotTimeSpectroHisto(D, start, disp, smplr, folder):
    try:
        gs_kw = dict(width_ratios=[3, 1])
        fig, ax = plt.subplots(ncols=2, nrows=2, sharey='row', figsize=(16,8), constrained_layout=True, gridspec_kw=gs_kw)
        
        startdate=time.strftime("%Y%m%d_%H%M",time.gmtime(start))
        day=time.strftime("%Y/%m/%d",time.gmtime(start))
        M = len(D)
        span = M/smplr
        T=np.linspace(0, span, M)
        xhours=span/3600

        #------------ timeseries plot -----------------
        ax[0][0].set_title(f'40m wire current on {day} {round(xhours,2)} hour plots')
        ax[0][0].plot(T, D,  linewidth=0.4)
        ax[0][0].set_ylabel("Amplitude pA")
        ax[0][0].set_xlim([T[0],T[-1]])
        ax[0][0].grid()

        if (True):
            xt=ax[0][0].get_xticks()
            xtt=[]
            for x in xt:
                xtt.append(time.strftime("%H:%M:%S",time.gmtime(x+start)))
            ax[0][0].set_xticks(xt)
            ax[0][0].set_xticklabels(xtt)
        ax[0][0].autoscale(enable=True, axis='x', tight=True)

        #------------ spectrogram plot -----------------
        nfft=next_pow_2(M/200)
        s_span = time.strftime("%H:%M:%S",time.gmtime(span))
        Pxx, freqs, bins, im = ax[1][0].specgram(D, NFFT=nfft, Fs=smplr, mode='psd',  window=mlab.window_hanning, noverlap=nfft//2)
        ax[1][0].set_ylabel("Frequency in Hz")
        ax[1][0].set_title(f'Spectrogram [span = {s_span}, Fs={smplr}Hz, nfft={nfft}, overlap={nfft//2}, window=\"hanning\"]')

        if (True):
            ax[1][0].set_xlabel('time (UTC)')    
            xt=ax[1][0].get_xticks()
            xtt=[]
            for x in xt:
                xtt.append(time.strftime("%H:%M:%S",time.gmtime(x+start)))
            ax[1][0].set_xticks(xt)
            ax[1][0].set_xticklabels(xtt)
        ax[1][0].autoscale(enable=True, axis='x', tight=True)

        #------------ histogram of timeseries -----------
        ax[0][1].hist(D, bins=20, orientation="horizontal", density=True, alpha=0.4, edgecolor='none')
        # get X limits and fix them
        mn, mx = ax[0][1].get_ylim()
        y = np.linspace(mn, mx, 301)
        # estimate Kernel Density and plot
        kde = sps.gaussian_kde(D)
        ax[0][1].plot(kde.pdf(y), y, label='KDE')
        ax[0][1].set_title("Probability Density Function")
        ax[0][1].grid()
        

        #------------ accumulated spectrum -----------
        window = np.hanning(M)
        fu = np.fft.rfft(D*window);
        faxis = np.fft.rfftfreq(M, 1/smplr)
        ax[1][1].semilogx(np.abs(fu), faxis, color='r')
        #ax[1][1].set_xlim([10,1000])
        ax[1][1].set_title("Power Spectral Density")
        ax[1][1].grid()

      

    except Exception as e:
        print(e)
        pdb.set_trace()
        

    if (disp):
        plt.pause(0.001)
        plt.show()
    else:
        try:
            filename=os.path.join(folder,str(round(xhours))+"h_"+startdate+".png")
            fig.savefig(filename, dpi=100)
            plt.close()
        except:
            print("save error!")
        else:
            print(filename,"saved!")
            



    

if __name__ == "__main__":
    length=600
    T = np.linspace(0,600,length*250)
    D = 3000*np.sin(2*np.pi*8*T) + 200*np.sin(2*np.pi*50*np.clip(T-300,0,300))
    #plotTime(T,D)
    #plotSpec(D,0,1,500,"E:\\")
    plotCombined(D,0,length,250,"E:\\")
    

