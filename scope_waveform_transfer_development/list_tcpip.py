import pyvisa
rm = pyvisa.ResourceManager()

scope = rm.open_resource("VICP::192.168.1.12::INSTR")
print(scope.query("*IDN?"))




