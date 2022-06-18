#GRMON script to communicate with SELENE DUT
#Author: Ilya Tuzov, Universitat Politecnica de Valencia


variable kernel "/home2/tuil/selene_axi4/selene-hardware/FFI/workloads/main/obj_1_matmult.out"
variable refres 0x1f20398a
variable SYNC_BUF 0x1000000


proc DutReset { } {
    global kernel
    #if {[catch {[attach]} er]} { }
    if {[catch {[reset]} er]} { }
    load $kernel
    if {[catch {[detach]} er]} { }
    puts "DUT has been reset"
    return "Status: {OK}"
    after 1000
}



proc TestWorkload { goldenrun} { 
    global SYNC_BUF  
    global refres
    #clean-up results buffer
    wmem [expr {$SYNC_BUF + 40}] 0x00 0x00
    #unlock the semaphore
    wmem [expr {$SYNC_BUF + 0}]  0x1
    #wait for wokload completion (200 ms as timeout)
    after 200
    #read-back ready flag and processing results (checksum)
    set token  [silent mem [expr {$SYNC_BUF + 40}] 1]
    set runres [silent mem [expr {$SYNC_BUF + 44}] 1]
        
    if {$goldenrun==1} {
        #Uncomment following to line to obtain golden-run results automatically
        #set refres $runres
        puts $token
        puts $runres
        return "Status: {Pass}"
    } else {
        puts $token
        puts $runres
        #Check responce from the DUT and forward it to DAVOS host
        if {$token=="0xabcdabcd"} {
            if { $runres==$refres} {
                return "Status: {Masked: token=$token:runres=$runres}"                
            } else {
                return "Status: {Fail: token=$token:runres=$runres}"
            }
        } else {
            return "Status: {Hang: token=$token:runres=$runres}"
        }
    }
}



# The code below implements communication with the DAVOS tool
# by means of command-responce interface (via sockets)
# This code is valid for any testbench 
# and SHOULD BE KEPT UNCHANGED

#Process connection request
 proc accept {chan addr port} {           
    scan [gets $chan] %d cmd
    if {$cmd == 1} {
        puts "Running Workload"
        set inf "GRMON: TestWorkload"
        set res [TestWorkload 0]
    } elseif {$cmd == 2} {
        puts "Reset"
        set inf "GRMON: DutReset"
        set res [DutReset]        
    } else {
        set inf "GRMON: Unknown cmd $cmd"
        set res "Status: {Error}"           
    }
    puts $inf
    puts $chan $res
    close $chan                          
 }          


set grmon::settings::echo_result 1
set port 12345
puts "GRMON script started at port=$port"

DutReset
puts "DUT has been initialized"
TestWorkload 1
puts "DUT ready"


socket -server accept $port
vwait forever
