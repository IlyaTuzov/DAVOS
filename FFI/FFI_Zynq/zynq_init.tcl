#set p_bitfile /home/tuil/Lenet5/MiniLenetFloat_22/design_1_wrapper.bit
#set p_hw_config /home/tuil/Lenet5/MiniLenetFloat_22/design_1_wrapper.xsa
#set p_fsbl_file /home/tuil/Lenet5/Vitis/design_1_wrapper/export/design_1_wrapper/sw/design_1_wrapper/boot/fsbl.elf
#set p_injector_app /home/tuil/Lenet5/Vitis/CNNFI/Debug/CNNFI.elf
#set p_faultlist /home/tuil/Lenet5/MiniLenetFloat_22/DavosGenerated/Faultlist_0.bin

set p_bitfile       [lindex $argv 0]
set p_hw_config     [lindex $argv 1]   
set p_fsbl_file     [lindex $argv 2]   
set p_injector_app   [lindex $argv 3]   
set p_faultlist     [lindex $argv 4]   


connect
targets -set -nocase -filter {name =~"APU*"}
rst -system
after 3000
targets -set -nocase -filter {name =~"APU*"}
rst -cores
targets -set -filter {name =~"PS*TAP"}
fpga -file $p_bitfile
targets -set -nocase -filter {name =~"APU*"}
loadhw -hw $p_hw_config -mem-ranges [list {0x80000000 0xbfffffff} {0x400000000 0x5ffffffff} {0x1000000000 0x7fffffffff}] -regs
configparams force-mem-access 1
targets -set -nocase -filter {name =~"APU*" }
set mode [expr [mrd -value 0xFF5E0200] & 0xf]
targets -set -nocase -filter {name =~ "*A53*#0"}
rst -processor
dow $p_fsbl_file
con
after 6000
targets -set -nocase -filter {name =~ "*A53*#0" }
rst -processor
dow $p_injector_app
configparams force-mem-access 0
dow -data $p_faultlist 0x7DF00200
targets -set -nocase -filter {name =~ "*A53*#0" }
con