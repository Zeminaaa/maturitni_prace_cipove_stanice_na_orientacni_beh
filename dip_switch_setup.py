import machine

bit1 = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
bit2 = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
bit3 = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
bit4 = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)

list_of_bits=[bit1,bit2,bit3,bit4]

binary_list=[]
for i in range(4):
    binary_list.append("*")
index=0  
for bit in binary_list:
    binary_list[index]=list_of_bits[index].value()
    index+=1
    
binary_string = "".join(map(str, binary_list))
decimal_num = int(binary_string, 2)

print(decimal_num)