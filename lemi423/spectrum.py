import matplotlib.pyplot as plt
from pylab import *
import time
import numpy as np
import scipy.stats as sps
import matplotlib.pyplot as plt
from tkinter import Tk, filedialog
import os
import pdb
from tempfile import TemporaryFile

#returns the next power of 2
def next_pow_2(f):
    x=int(f)
    return 1<<(x-1).bit_length()

#------------------------------------------------------------------------------------------
def winSpeed(W, plot=None):
#------------------------------------------------------------------------------------------
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

def cumsum_sma(array, period):
    ret = np.cumsum(array, dtype=float)
    ret[period:] = ret[period:] - ret[:-period]
    return ret[period - 1:] / period

#------------------------------------------------------------------------------------------
def plotCurrentAndCurrent(D, fs1, W, fs2, start, disp, folder):
#------------------------------------------------------------------------------------------    
    try:
        gs_kw = dict(width_ratios=[3, 1])
        fig, ax = plt.subplots(ncols=2, nrows=4, figsize=(16,8), constrained_layout=True, gridspec_kw=gs_kw)
        
        startdate=time.strftime("%Y%m%d_%H%M",time.gmtime(start))
        day=time.strftime("%Y/%m/%d",time.gmtime(start))
        spanD = len(D)/fs1
        TD=np.linspace(0, spanD, len(D))
        spanW = len(W)/fs2
        TW=np.linspace(0, spanW, len(W))
        if (spanD != spanW):
            print(f'length of D ({spanD}) not equal to length of W ({spanW})')
        xhours=spanD/3600

        #------------ current timeseries plot -----------------
        a = ax[0][0]
        a.set_title(f'DC current on {day} span={round(xhours,2)} hour timeseries plot')
        a.plot(TD, D,  linewidth=0.4, color='C1')
        a.set_ylabel("Amplitude nA")
        a.set_xlim([TD[0],TD[-1]])

        
        #------------ current spectrogram plot -----------------
        a = ax[1][0]
        nfft=next_pow_2(len(D)/200)
        s_span = time.strftime("%H:%M:%S",time.gmtime(spanD))
        Pxx, freqs, t1, im = a.specgram(D, NFFT=nfft, Fs=fs1, mode='psd',  window=mlab.window_hanning, noverlap=nfft//2)
        a.set_ylabel("Frequency in Hz")
        a.set_title(f'Spectrogram [span = {s_span}, Fs={fs1}Hz, nfft={nfft}, overlap={nfft//2}, window=\"hanning\"]')


        #------------ current2 timeseries plot -----------------
        a = ax[2][0]
        a.set_title(f'averaged current timeseries plot')
        #a.plot(TW, W,  linewidth=0.3, color='C2', label='+40dB amplified current')
        Wf = cumsum_sma(W, round(60*fs2*5))
        Wff = cumsum_sma(W, round(60*fs2*15))
        TWf = np.linspace(0, spanW, len(Wf))
        TWff = np.linspace(0, spanW, len(Wff))
        a.plot(TWf, Wf, linewidth=0.5, color='C3', label='5-min moving average filter')
        a.plot(TWff, Wff, linewidth=1.2, color='C4', label='15-min moving average filter')        
        a.legend()
        a.set_ylabel("Amplitude nA")
        a.set_xlim([TW[0],TW[-1]])

        
        #------------ current2 cumsum plot -----------------
        a = ax[3][0]
        a.set_title(f'cumulative charge')
        a.plot(TD, np.cumsum(D*1E-6), color='C1', label='charge(DC)')
        a.plot(TW, np.cumsum(W*1E-6), color='C2', label='charge(BUF)')
        a.legend()
        a.set_ylabel("Charge mC")
    

        

        #----------- label axes, grid, autoscale...
        xt = np.linspace(0,spanD,13)
        xt_str = [''] * len(xt)
        for a in ax[:,0]:
            a.autoscale(enable=True, axis='x', tight=True)
            a.grid()        
            a.set_xticks(xt)
            a.set_xticklabels(xt_str)
            
        xtt=[]
        for x in xt:
            xtt.append(time.strftime("%H:%M",time.gmtime(x+start)))
        a.set_xticklabels(xtt)
        a.set_xlabel('time (UT)')
            
        
        #------------ histogram of timeseries D -----------
        a=ax[0][1]
        a.hist(D, bins=20, weights=1/len(D) * np.ones(len(D)),
               orientation="horizontal", density=True, alpha=0.4, color='C1', edgecolor='none')
        mn, mx = a.get_ylim()
        y = np.linspace(mn, mx, 301)
        mu = np.mean(D)
        var = np.std(D)**2
        fr = r'$\mu$={}, $\sigma$^2={}'.format(round(mu,2), round(var,2))
        a.plot(sps.norm.pdf(y, mu, np.sqrt(var)), y, alpha=0.6, color='C3', label=f'Normal distribution {fr}')
        a.set_title("DC output distribution")        
        a.legend()
        a.grid()

        #------------ histogram of timeseries W -----------
        a=ax[2][1]
        a.hist(W, bins=20, weights=1/len(W) * np.ones(len(W)),
               orientation="horizontal", density=True, alpha=0.4, color='C2', edgecolor='none')
        mn, mx = a.get_ylim()
        y = np.linspace(mn, mx, 301)
        mu = np.mean(W)
        var = np.std(W)**2        
        fr = r'$\mu$={}, $\sigma$^2={}'.format(round(mu,2), round(var,2))
        a.plot(sps.norm.pdf(y, mu, np.sqrt(var)), y, alpha=0.6, color='C3',  label=f'Normal distribution {fr}')
        a.legend()
        a.set_title("BUF output (amplified current) distribution")
        a.grid()        

        #------------ histogram of timeseries Wf -----------
        a=ax[3][1]
        a.hist(Wff, bins=20, weights=1/len(Wff) * np.ones(len(Wff)),
               orientation="horizontal", density=True, alpha=0.4, color='C4', edgecolor='none')
        mn, mx = a.get_ylim()
        y = np.linspace(mn, mx, 301)
        mu = np.mean(Wf)
        var = np.std(Wf)**2
        fr = r'$\mu$={}, $\sigma$^2={}'.format(round(mu,2), round(var,2))
        a.plot(sps.norm.pdf(y, mu, np.sqrt(var)), y, alpha=0.6, color='C4',  label=f'Normal distribution {fr}')
        a.legend()
        a.set_title("filtered current distribution")
        a.grid()
        
        filename=os.path.join(folder,f'{round(xhours)}h_{startdate}.npz')
        with open(filename, 'wb') as f:
            np.savez(f, D=D, fs1=fs1, W=W, fs2=fs2, start=start, disp=disp, folder=folder)
            
    except Exception as e:
        print(e)    
        pdb.set_trace()
        

    if (disp):
        plt.ion()
        plt.pause(2)
        plt.show()
        
    else:
        try:
            filename=os.path.join(folder,f'{round(xhours)}h_{startdate}.png')
            fig.savefig(filename, dpi=100)
            plt.close()
        except:
            print("save error!")
        else:
            print(filename,"saved!")

    if __name__ == "__main__":
        plt.ion()
        plt.pause(2)
        plt.show()
        pdb.set_trace()
        
        
#------------------------------------------------------------------------------------------
def plotCurrentAndWind(D, fs1, W, fs2, start, disp, folder):
#------------------------------------------------------------------------------------------
    try:
        gs_kw = dict(width_ratios=[3, 1])
        fig, ax = plt.subplots(ncols=2, nrows=3, sharey='row', sharex='col', figsize=(16,8), constrained_layout=True, gridspec_kw=gs_kw)
        
        startdate=time.strftime("%Y%m%d_%H%M",time.gmtime(start))
        day=time.strftime("%Y/%m/%d",time.gmtime(start))
        spanD = len(D)/fs1
        TD=np.linspace(0, spanD, len(D))
        spanW = len(W)/fs2
        TW=np.linspace(0, spanW, len(W))
        if (spanD != spanW):
            print(f'length of D ({spanD}) not equal to length of W ({spanW})')
        xhours=spanD/3600

        #------------ current timeseries plot -----------------
        a = ax[0][0]
        a.set_title(f'40m-wire LP-filtered current on {day} {round(xhours,2)} hour timeseries plot')
        a.plot(TD, D,  linewidth=0.4)
        a.set_ylabel("Amplitude pA")
        a.set_xlim([TD[0],TD[-1]])

        
        #------------ current spectrogram plot -----------------
        a = ax[1][0]
        nfft=next_pow_2(len(D)/200)
        s_span = time.strftime("%H:%M:%S",time.gmtime(spanD))
        Pxx, freqs, t1, im = a.specgram(D, NFFT=nfft, Fs=fs1, mode='psd',  window=mlab.window_hanning, noverlap=nfft//2)
        a.set_ylabel("Frequency in Hz")
        a.set_title(f'Spectrogram [span = {s_span}, Fs={fs1}Hz, nfft={nfft}, overlap={nfft//2}, window=\"hanning\"]')

  
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

        
        

        

        #------------ accumulated spectrum -----------
        """window = np.hanning(M)
        fu = np.fft.rfft(D*window)
        faxis = np.fft.rfftfreq(M, 1/smplr)
        ax[1][1].semilogx(np.abs(fu), faxis, color='r')
        #ax[1][1].set_xlim([10,1000])
        ax[1][1].set_title("Power Spectral Density")
        """
        #------------ histogram of timeseries D -----------
        a=ax[0][1]
        a.hist(D, bins=20, orientation="horizontal", density=True, alpha=0.4, edgecolor='none')
        mn, mx = a.get_ylim()
        y = np.linspace(mn, mx, 301)
        # estimate Kernel Density and plot
        kde = sps.gaussian_kde(D)
        a.plot(kde.pdf(y), y, label='KDE')
        a.set_title("Probability Density Function")
        a.grid()
        

        with open('spectrum.npz', 'wb') as f:
            np.savez(f, D=D, fs1=fs1, W=W, fs2=fs2, start=start, disp=disp, folder=folder)
            
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
    print("select an .npz file!")
    absfile = filedialog.askopenfilename()    
    with np.load(absfile) as d:
        plotCurrentAndCurrent(d['D'], d['fs1'].item(), d['W'], d['fs2'].item(), d['start'].item(), True, d['folder'].item())

    

