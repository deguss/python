import numpy as np

def calibrate_hyl(Bx, By):
    a1_mVnT = 71.0 # [mV/nT] konverziós tényező
    a2_mVnT = 71.0 # [mV/nT]

    a1 = a1_mVnT * 1e-3 / 1e3 # [V/pT]
    a2 = a2_mVnT * 1e-3 / 1e3 # [V/pT]
    ku = 4.26 # erősítés a vevőben
    
    c1 = a1 * ku # rendszerérzékenység
    c2 = a2 * ku 
    
    d = 2**18 # 18-bites DAC
    V = 4.096 * 2.0 # [V] feszültségtartomány

    scale1 = c1 * d / V
    scale2 = c2 * d / V

    Bx = Bx / scale1
    By = By / scale2 # [pT]

    return Bx, By
