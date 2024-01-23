import pyvisa
rm = pyvisa.ResourceManager()

ip = "192.168.1.12"

try:
    scope = rm.open_resource("VICP::"+ip+"::INSTR")
    print(scope.query("*IDN?"))
    scope.write("MSG 'running "+__file__+"'")
    scope.write("COMM_HEADER OFF")
except:
    print("could not connect on "+ip)
    rm.close()
    exit()

print("Enter one SCPI command at a time! (c to cancel)")

while True:
    i = input("SCPI>")
    if (i == "c"):
        break
    try:
        if ('?' in i):
            print(scope.query(i))
        else:
            scope.write(i)
            print()

        r = int(scope.query("CMR?"))
        if (r > 0):
            if (r == 1):
                print("unrecognized command")
            elif(r == 2):
                print("illegal header path")
            elif(r==3):
                print("illegal number")
            elif(r==4):
                print("illegal number suffix")
            elif(r==5):
                print("unrecognized keyword")
            elif(r==6):
                print("string error")
            else:
                print("other error")
            
            
    except:
        print("command error / no response!")
        print(scope.query("CHL?"))

    
rm.close()




