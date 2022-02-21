#GRMON script to communicate with NOELV DUT
#Authors: Ilya Tuzov, Universitat Politecnica de Valencia
#         Gabriel Cobos Tello, Universitat Politecnica de Valencia

variable refres 0
variable refreg 0
variable kernel "/workloads/obj_1_matmult.out"
variable resadr 0x10000

proc DutReset { } {
    global kernel
    attach
    reset
    load $kernel
    detach
    #cont
    puts "DUT has been reset"
    return "Status: {OK}"
}





proc TestWorkload { goldenrun} {   
    global refres
    global refreg 
    global resadr
    wmem $resadr 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
    #if {[catch {[silent cont]} er]} { }
    wmem 0x1000000 0x1
    after 100
    if {$goldenrun==1} {
        set refres [silent mem $resadr 128]
        puts $refres
        return "Status: {Pass}"
    } else {
        set runres [silent mem $resadr 128]
        puts $runres
        if {$runres == $refres} {
            return "Status: {Pass}"
        } else {
            return "Status: {SDC}"
        }
    }
}



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
TestWorkload 1
puts "DUT has been initialized"


socket -server accept $port
vwait forever

