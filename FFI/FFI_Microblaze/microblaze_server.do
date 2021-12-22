


proc restart {bitstream elf} {
    connect 
    target 1
    fpga -file $bitstream
    after 1000
    target 3
    rst -system
    after 3000
    if {[catch {dow $elf} er]} { }
    if {[catch {target 3} er]} { }
    if {[catch {con} er]} { }
}

proc loadfaultlist { fname } {
    dow -data $fname 0x20200
    if {[catch {rst} er]} { }
    if {[catch {con} er]} { }
    puts "Loaded faultlist: $fname"
    return "Status: {ok $fname}"
}



proc excmd {arg1 arg2} {
    scan $arg1 %d cmd
    scan $arg2 %d data
    mwr 0x20004 $data
    after 1
    mwr 0x20000 $cmd
    if {[catch {con} er]} { }
    after 10
    return "Status: {[mrd -value 0x20008 2]}"
}




proc accept {chan addr port} {          
    set inp [gets $chan]
    set arg [regexp -all -inline {\S+} $inp]
    set arg1 [lindex $arg 0]
    set arg2 [lindex $arg 1]
    
    if { $arg1 == "10" } {
        set res [loadfaultlist $arg2]
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


restart $bitfile $micapp

puts "XSCT Connected"

socket -server accept $port              ;# Create a server socket
vwait forever                            ;# Enter the event loop
 