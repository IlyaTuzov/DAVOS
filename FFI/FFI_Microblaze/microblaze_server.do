#XSCT App to communicate with microblaze-based injector
#Authors: Ilya Tuzov, Universitat Politecnica de Valencia
#         Gabriel Cobos Tello, Universitat Politecnica de Valencia

variable micapp ""
variable CLKBUFADR 0x44A00000

proc restart {bitstream} {
    global CLKBUFADR
    connect 
    target 1
    fpga -file $bitstream
    after 1000
    target 3
    #CLKBUF: free clocking mode
    mwr [expr $CLKBUFADR + 0x4] 0x2
    #configure reset duration for 110 clk cycles
    mwr [expr $CLKBUFADR + 0x8] 0x6E 
}


proc dut_reset { } {
    global CLKBUFADR
    mwr [expr $CLKBUFADR + 0x4] 0x3
    after 1
    mwr [expr $CLKBUFADR + 0x4] 0x2
    return "Status: {ok reset_done}"
}


proc run_kernel { } {
    global micapp
    after 2000
    target 3
    rst -processor
    after 2000
    if {[catch {dow $micapp} er]} { }
    if {[catch {target 3} er]} { }
    if {[catch {con} er]} { }  
    if {[catch {con} er]} { }      
    return "Status: {ok $micapp}"    
}


proc loadfaultlist { fname } {
    dow -data $fname 0x20200
    if {[catch {rst} er]} { }
    if {[catch {con} er]} { }
    if {[catch {con} er]} { }
    puts "Loaded faultlist: $fname"
    return "Status: {ok $fname}"
}





#arg1 command:  0-NoP, 
#               1-Inject and wait for ack,  
#               2-Recover and wait for ack,
#               3-Inject (async) without ack
proc excmd {arg1 arg2} {
    scan $arg1 %d cmd
    scan $arg2 %d data

    set status [mrd -value 0x20008]
    # 0-ok, 1-hang, 2-error
    if {$status != 0} {
        return "Status: {$status [mrd -value 0x2000C]}"
    } else { 
        mwr 0x20004 $data
        after 1
        mwr 0x20000 $cmd
        if {[catch {con} er]} { }
        if {$cmd == 3} {
            return "Status: {0 $data}"
        } else {
            after 100
            return "Status: {[mrd -value 0x20008 2]}"
        }
    }
}




proc accept {chan addr port} {          
    set inp [gets $chan]
    set arg [regexp -all -inline {\S+} $inp]
    set arg1 [lindex $arg 0]
    set arg2 [lindex $arg 1]
    
    if { $arg1 == "10" } {
        set res [loadfaultlist $arg2]
    } elseif { $arg1 == "11" } {
        set res [run_kernel]
    } elseif { $arg1 == "12"} {
        set res [dut_reset]
    } else {    
        set res [excmd $arg1 $arg2]
    }
    puts "$addr:$port says $res"
    puts $chan "Test result : $res"
    close $chan                          
}   
       




set port        [lindex $argv 0]
set bitfile     [lindex $argv 1]
set micapp      [lindex $argv 2]
puts "Microblaze host script started at port=$port\n\tbitfile=$bitfile\n\tmicapp=$micapp"


restart $bitfile 
#dut_reset
run_kernel

puts "XSCT Connected"

socket -server accept $port              ;# Create a server socket
vwait forever                            ;# Enter the event loop
