#GRMON script to communicate with NOELV DUT
#Authors: Ilya Tuzov, Universitat Politecnica de Valencia
#         Gabriel Cobos Tello, Universitat Politecnica de Valencia



variable kernel "/home2/tuil/selene_redundant_hls/selene-hardware/accelerators/conv/software/main_conv2D.elf"





variable SYNC_BUF 0x1000000

proc DutReset { } {
    global kernel
    #if {[catch {[attach]} er]} { }
    #if {[catch {[reset]} er]} { }
    load $kernel
    after 1000
    if {[catch {[detach]} er]} { }
    #cont
    puts "DUT has been reset"
    return "Status: {OK}"
}





proc TestWorkload { goldenrun} {   
    global SYNC_BUF
    wmem [expr {$SYNC_BUF + 0}]  0x00
    wmem [expr {$SYNC_BUF + 40}] 0x00 0x00 0x00
    #if {[catch {[silent cont]} er]} { }
    wmem $SYNC_BUF 0x1
    after 2000
    
    if {$goldenrun==1} {
        return [format "Status: {Masked:t1=%d,t2=%d}" 0 0] 
    } else {       
        set agreement [silent mem [expr {$SYNC_BUF + 40}] 1]
        set timeout_1 [silent mem [expr {$SYNC_BUF + 44}] 1]
        set timeout_2 [silent mem [expr {$SYNC_BUF + 48}] 1]
        
        if {$agreement==0xA && $timeout_1==0x0 && $timeout_2==0x0} {
            return [format "Status: {Masked:t1=%d,t2=%d}" $timeout_1 $timeout_2]         
        } elseif { $timeout_1==0x1 || $timeout_2==0x1} {
            return [format "Status: {Timeout:t1=%d,t2=%d}" $timeout_1 $timeout_2]  
        } elseif {$agreement==0xB } {
            return [format "Status: {Fail:t1=%d,t2=%d}" $timeout_1 $timeout_2]  
        } elseif {$agreement==0x0} {
            return [format "Status: {Hang:t1=%d,t2=%d}" $timeout_1 $timeout_2]  
        } else {
            return [format "Status: {DataCorruption:t1=%d,t2=%d}" $timeout_1 $timeout_2]  
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
puts "DUT has been initialized"
TestWorkload 1
puts "DUT ready"


socket -server accept $port
vwait forever

