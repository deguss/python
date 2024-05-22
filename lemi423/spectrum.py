import matplotlib.pyplot as plt
from pylab import *
import time
import numpy as np
import scipy.stats as sps
import matplotlib.pyplot as plt
import os
import pdb
from tempfile import TemporaryFile

#returns the next power of 2
def next_pow_2(f):
    x=int(f)
    return 1<<(x-1).bit_length()

def winSpeed(W, plot=None):
    try:
        nfft=next_pow_2(len(W)/200)
        len_s = (len(W)-1)/250
        if (plot is True):
            fig, ax = plt.subplots(ncols=1, nrows=3, figsize=(16,8), constrained_layout=True)
            Pxx, freqs, t, im = ax[0].specgram(W, NFFT=nfft, Fs=250, mode='magnitude',  window=mlab.window_hanning, noverlap=nfft//2)
        else:
            fig, ax = plt.subplots()
            Pxx, freqs, t, im = ax.specgram(W, NFFT=nfft, Fs=250, mode='magnitude',  window=mlab.window_hanning, noverlap=nfft//2)
            plt.close()

        f_low = np.argwhere(np.logical_and(freqs>1, freqs<=100)).squeeze()
        P=Pxx[f_low, :]
        [fi, ti] = np.shape(Pxx)
        print(f'{ti} time segments, each {round(len_s/ti,2)}s, nfft={nfft}-point FFT')
        print(f'f = [{freqs[f_low[0]]} .. {freqs[f_low[-1]]}]')

            
        avgs=P.mean(axis=0)
        print(f'np.max(avgs) = {np.max(avgs)}')
        scaling_factor = 5E3#np.max(avgs) / (nfft * len_s)
        avgs = avgs / scaling_factor
        avg_th = 1
        print(f'after scaling: np.max(avgs) = {np.max(avgs)}, avg_th = {avg_th}')
        
        windy = np.argwhere(avgs > avg_th)
        if (plot is True):        
            ax[1].scatter(t, avgs, s=10, c='g', label='quiet')
            ax[1].scatter(t[windy], avgs[windy], s=10, c='r', label='windy')
            ax[1].legend()
            ax[2].plot(W)
          
            #for e in windy:
            #    ax[0].axvline(x=t[e], c='r')
                #ax[2].loglog(freqs[f_low], P[:, e])

            #ax[3].scatter(freqs[f_low], P[:, 3], s=5, label='average of spectra #3')
            #ax[3].scatter(freqs[f_low], P[:, 15], s=5, label='average of spectra #10')
            

            for a in ax:
                a.autoscale(enable=True, axis='x', tight=True)
                a.grid()

  
            plt.pause(0.001)
            plt.show()
            
        return [t, avgs]
        
    except Exception as e:
        print(e)    
        pdb.set_trace()
        
        

def plotTimeSpectroHisto(D, W, start, disp, smplr, folder):
    try:
        gs_kw = dict(width_ratios=[3, 1])
        fig, ax = plt.subplots(ncols=2, nrows=3, sharey='row', sharex='col', figsize=(16,8), constrained_layout=True, gridspec_kw=gs_kw)
        
        startdate=time.strftime("%Y%m%d_%H%M",time.gmtime(start))
        day=time.strftime("%Y/%m/%d",time.gmtime(start))
        M = len(D)
        span = M/smplr
        T=np.linspace(0, span, M)
        xhours=span/3600

        #------------ timeseries plot -----------------
        a = ax[0][0]
        a.set_title(f'40m wire current on {day} {round(xhours,2)} hour plots')
        a.plot(T, D,  linewidth=0.4)
        a.set_ylabel("Amplitude pA")
        a.set_xlim([T[0],T[-1]])

        
        #------------ spectrogram plot -----------------
        nfft=next_pow_2(M/200)
        s_span = time.strftime("%H:%M:%S",time.gmtime(span))
        Pxx, freqs, t1, im = ax[1][0].specgram(D, NFFT=nfft, Fs=smplr, mode='psd',  window=mlab.window_hanning, noverlap=nfft//2)
        ax[1][0].set_ylabel("Frequency in Hz")
        ax[1][0].set_title(f'Spectrogram [span = {s_span}, Fs={smplr}Hz, nfft={nfft}, overlap={nfft//2}, window=\"hanning\"]')

        
        #------------ windspeed plot -----------------
        [t, avgs] = winSpeed(W)
        a = ax[2][0]
        a.scatter(t, avgs, s=10, c='g', label='quiet')
        wind_th = 1
        windy = np.argwhere(avgs > wind_th).squeeze()
        a.scatter(t[windy], avgs[windy], s=10, c='r', label='windy')
        a.legend()
        a.set_ylabel("wind speed a.u.")
        a.set_xlim([t[0],t[-1]])

        #----------- label axes, grid, autoscale...
        for a in ax[:,0]:
            a.autoscale(enable=True, axis='x', tight=True)
            a.grid()
            
        a.set_xlabel('time (UTC)')
        xt=a.get_xticks()
        xtt=[]
        for x in xt:
            xtt.append(time.strftime("%H:%M:%S",time.gmtime(x+start)))
        a.set_xticks(xt)
        a.set_xticklabels(xtt)

        ax[0][0].set_ylim(ax[0][0].get_ylim())
        ax[0][0].fill_between(t, *ax[0][0].get_ylim(), where=avgs>wind_th, facecolor='red', alpha=.2)

        
        
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
        """window = np.hanning(M)
        fu = np.fft.rfft(D*window)
        faxis = np.fft.rfftfreq(M, 1/smplr)
        ax[1][1].semilogx(np.abs(fu), faxis, color='r')
        #ax[1][1].set_xlim([10,1000])
        ax[1][1].set_title("Power Spectral Density")
        """

        with open('spectrum.npz', 'wb') as f:
            np.savez(f, D=D, W=W, start=start, disp=disp, smplr=smplr, folder=folder)
            
    except Exception as e:
        print(e)    
        pdb.set_trace()
        

    if (disp):
        plt.ion()
        plt.pause(2)
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
        pdb.set_trace()

    

if __name__ == "__main__":
    with np.load('spectrum.npz') as d:
        plotTimeSpectroHisto(d['D'], d['W'], d['start'].item(), True, d['smplr'].item(), d['folder'].item())
        #winSpeed(d['W'], plot=True)
        if (False):
            [t, avgs] = winSpeed(d['W'])
            clf()
            scatter(t, avgs, s=10, c='g', label='quiet')
            plt.pause(1)
            plt.show()
    

