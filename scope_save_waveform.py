import pdb
import numpy as np
import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

import pyvisa
rm = pyvisa.ResourceManager('@py')

ip = "192.168.1.12"

def getInt(string):
    import re
    match = re.search(r"\d+", string)

    if match:
        return int(match.group())
    else:
        raise ValueError("No numberical value found in the string: "+string)

def getFloat(string):
    import re
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", string)

    if match:
        return float(match.group())
    else:
        raise ValueError("No numberical value found in the string: "+string)

def get_param_value(channel, parameter):
    s = scope.query(channel+":PAVA? "+parameter)
    # "MAX,3.211,OK\n"
    resp = s.split(',')[2].rstrip('\n')
    if (resp == 'OK' or resp == 'AV'): #for some parameters OK is reported, for others "Averaged over several periodes"
        return getFloat(s)
    else:
        return resp

def get_wavedesc_value(channel, parameter):
    s = scope.query(channel+":INSP? '"+parameter+"'")
    # "VERTICAL_GAIN      : 2.4414e-05"
    try:
        return getFloat(s)
    except: 
        print("response to query: "+s)
        raise ValueError("could not read "+parameter)
    
    
try:
    scope = rm.open_resource("VICP::"+ip+"::INSTR")
    print(scope.query("*IDN?"))
    scope.write("MSG 'running "+__file__+"'")
    scope.write("COMM_HEADER OFF")

except TimeoutError as error:
    print(error)
    print("consider rebooting the scope!")
    rm.close()
    exit()
except Exception as e:
    print("could not connect on "+ip)
    print(e)
    rm.close()
    exit()

try:
    #determine first, which trace is turned on.
    traces=0
    if (scope.query("C4:TRACE?").rstrip('\n') == 'ON'):    
        c4 = scope.query_binary_values("C4:WF? DAT1", datatype='h', container=np.array, is_big_endian=True)
        cn="C4"
        traces+=1
    if (scope.query("C3:TRACE?").rstrip('\n') == 'ON'):    
        c3 = scope.query_binary_values("C3:WF? DAT1", datatype='h', container=np.array, is_big_endian=True)
        cn="C3"
        traces+=1
    if (scope.query("C2:TRACE?").rstrip('\n') == 'ON'):    
        c2 = scope.query_binary_values("C2:WF? DAT1", datatype='h', container=np.array, is_big_endian=True)
        cn="C2"
        traces+=1
    if (scope.query("C1:TRACE?").rstrip('\n') == 'ON'):        
        c1 = scope.query_binary_values("C1:WF? DAT1", datatype='h', container=np.array, is_big_endian=True)
        cn="C1"
        traces+=1

        
except:
    rm.close()
    print("could not transfer waveform")
    pdb.set_trace()
    exit()

try:
    if ('c1' in locals()):
        offs = get_wavedesc_value("C1", "VERTICAL_OFFSET")    
        gain = get_wavedesc_value("C1", "VERTICAL_GAIN")
        c1 = gain * c1 - offs        
    if ('c2' in locals()):
        offs = get_wavedesc_value("C2", "VERTICAL_OFFSET")    
        gain = get_wavedesc_value("C2", "VERTICAL_GAIN")
        c2 = gain * c2 - offs
    if ('c3' in locals()):
        offs = get_wavedesc_value("C3", "VERTICAL_OFFSET")    
        gain = get_wavedesc_value("C3", "VERTICAL_GAIN")
        c3 = gain * c3 - offs        
    if ('c4' in locals()):
        offs = get_wavedesc_value("C4", "VERTICAL_OFFSET")    
        gain = get_wavedesc_value("C4", "VERTICAL_GAIN")
        c4 = gain * c4 - offs        

        
    c_size = int(get_wavedesc_value(cn, "WAVE_ARRAY_COUNT"))
    dt = get_wavedesc_value(cn, "HORIZ_INTERVAL")
    t_offs = get_wavedesc_value(cn, "HORIZ_OFFSET")

    t = np.linspace(0-t_offs, (c_size*dt)-t_offs, c_size)

    string = scope.query(cn+":INSP? 'TRIGGER_TIME'")
    # Use regex to extract the HH:MM format
    match = re.search(r"Time = (\d{2}:\d{2}):\d{2}.\d+", string)
    if (match):
        time_string = match.group(1)
    else:
        time_string = ""

    bwl = ""
    if ('on' in scope.query("INSP? 'BANDWIDTH_LIMIT'")):
        bwl = "[BWL]"

    overflow = ""
    if ('c1' in locals()):        
        c1_max = get_param_value("C1", "MAX")
        c1_min = get_param_value("C1", "MIN")
        c1_mean = get_param_value("C1", "MEAN")
        c1_rms = get_param_value("C1", "RMS")
        if (type(c1_max) == str or
            type(c1_min) == str or
            type(c1_mean) == str or
            type(c1_rms) == str):
            overflow = "[OVERFLOW]"
        print("c1_min: "+str(c1_min))
        print("c1_max: "+str(c1_max))
        print("c1_mean: "+str(c1_mean))
        print("c1_rms: "+str(c1_rms))

        c1_duty = get_param_value("C1", "DUTY")
        c1_frq = get_param_value("C1", "FREQ")
        c1_period = get_param_value("C1", "PER")
        c1_sdev = get_param_value("C1", "SDEV")
        print("c1_duty: "+str(c1_duty))
        print("c1_frq: "+str(c1_frq))
        print("c1_period: "+str(c1_period))
        print("c1_sdev: "+str(c1_sdev))
        print("")        
        
    if ('c2' in locals()):
        c2_max = get_param_value("C2", "MAX")
        c2_min = get_param_value("C2", "MIN")
        c2_mean = get_param_value("C2", "MEAN")
        c2_rms = get_param_value("C2", "RMS")
        if (type(c2_max) == str or
            type(c2_min) == str or
            type(c2_mean) == str or
            type(c2_rms) == str):
            overflow = "[OVERFLOW]"
        print("c2_min: "+str(c2_min))
        print("c2_max: "+str(c2_max))
        print("c2_mean: "+str(c2_mean))
        print("c2_rms: "+str(c2_rms))

        c2_duty = get_param_value("C2", "DUTY")
        c2_frq = get_param_value("C2", "FREQ")
        c2_period = get_param_value("C2", "PER")
        c2_sdev = get_param_value("C2", "SDEV")
        print("c2_duty: "+str(c2_duty))
        print("c2_frq: "+str(c2_frq))
        print("c2_period: "+str(c2_period))
        print("c2_sdev: "+str(c2_sdev))
        print("")

    if ('c3' in locals()):
        c3_max = get_param_value("C3", "MAX")
        c3_min = get_param_value("C3", "MIN")
        c3_mean = get_param_value("C3", "MEAN")
        c3_rms = get_param_value("C3", "RMS")
        if (type(c3_max) == str or
            type(c3_min) == str or
            type(c3_mean) == str or
            type(c3_rms) == str):
            overflow = "[OVERFLOW]"
        print("c3_min: "+str(c3_min))
        print("c3_max: "+str(c3_max))
        print("c3_mean: "+str(c3_mean))
        print("c3_rms: "+str(c3_rms))

        c3_duty = get_param_value("C3", "DUTY")
        c3_frq = get_param_value("C3", "FREQ")
        c3_period = get_param_value("C3", "PER")
        c3_sdev = get_param_value("C3", "SDEV")
        print("c3_duty: "+str(c3_duty))
        print("c3_frq: "+str(c3_frq))
        print("c3_period: "+str(c3_period))
        print("c3_sdev: "+str(c3_sdev))
        print("")

    if ('c4' in locals()):
        c4_max = get_param_value("C4", "MAX")
        c4_min = get_param_value("C4", "MIN")
        c4_mean = get_param_value("C4", "MEAN")
        c4_rms = get_param_value("C4", "RMS")
        if (type(c4_max) == str or
            type(c4_min) == str or
            type(c4_mean) == str or
            type(c4_rms) == str):
            overflow = "[OVERFLOW]"
        print("c4_min: "+str(c4_min))
        print("c4_max: "+str(c4_max))
        print("c4_mean: "+str(c4_mean))
        print("c4_rms: "+str(c4_rms))

        c4_duty = get_param_value("C4", "DUTY")
        c4_frq = get_param_value("C4", "FREQ")
        c4_period = get_param_value("C4", "PER")
        c4_sdev = get_param_value("C4", "SDEV")
        print("c4_duty: "+str(c4_duty))
        print("c4_frq: "+str(c4_frq))
        print("c4_period: "+str(c4_period))
        print("c4_sdev: "+str(c4_sdev))
        print("")        
    
except Exception as e:
    print(e)
    rm.close()
    pdb.set_trace()

rm.close()

fig, axs = plt.subplots(nrows=traces, ncols=1, squeeze=False, sharex=True, figsize=(10,8))
fm=plt.get_current_fig_manager()
fm.window.wm_geometry('1200x1000+0+0') #place the window on top left corner of screen

plt.ion() #disp fig without blocking
ind=0
if ('c1' in locals()):
    axs[ind][0].plot(t, c1, color='gold')
    plt.pause(1) # Introduce a short delay for the plot to display
if ('c2' in locals()):
    ind+=1
    axs[ind][0].plot(t, c2, color='maroon')
    plt.pause(1) # Introduce a short delay for the plot to display
if ('c3' in locals()):
    ind+=1
    axs[ind][0].plot(t, c3, color='royalblue')
    plt.pause(1) # Introduce a short delay for the plot to display
if ('c4' in locals()):
    ind+=1
    axs[ind][0].plot(t, c4, color='limegreen')
    plt.pause(1) # Introduce a short delay for the plot to display

# Set the y-axis formatter to display values in ms, us, ns, or ps
formatter = ticker.EngFormatter()

# Apply the formatter to the y-axis
axs[ind][0].xaxis.set_major_formatter(formatter)

axs[ind][0].set(xlabel='time (s)', ylabel='Amplitude (V)')
axs[0][0].set_title("<enter title>   "+overflow +" "+ bwl +" @"+ time_string)
axs[ind][0].grid()
plt.xlim(min(t), max(t))
plt.pause(1) # Introduce a short delay for the plot to display

plt.show(block=False)  # Show plot in a non-blocking way
plt.pause(1) # Introduce a short delay for the plot to display

print("enter figure title (=filename) to save png! (c to cancel, d to debug)")
fn = input(">")
if (fn == 'd'):
    pdb.set_trace()
elif (fn != 'c'):
    axs[0][0].set_title(fn +"  "+ overflow +" "+ bwl +" @"+ time_string)
    fig.savefig(fn)


plt.pause(1) # Resume the program to exit the plot window
    
