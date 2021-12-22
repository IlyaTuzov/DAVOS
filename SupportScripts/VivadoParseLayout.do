#DEVICE LAYOUT PARSE SCRIPT FOR VIVADO
#Run example: 
#    vivado -mode batch -source C:/GitHub/DAVOS/SupportScripts/VivadoParseLayout.do -tclargs C:/Projects/FFIMIC/FFIMIC.xpr * C:/GitHub/DAVOS/FFI/DeviceSupport

if {$argc < 3} {
    puts "not enough arguments"
    return
}

set proj        [lindex $argv 0]
set run         [lindex $argv 1]
set exportdir   [lindex $argv 2] 
puts "proj=$proj, run=$run, exportdir=$exportdir"

open_project $proj
puts "Project opened: [current_project]"

if {$run != "*" } {
    open_run [get_runs $run]
} else {
    open_run [get_runs -filter {CURRENT_STEP == route_design || CURRENT_STEP == write_bitstream}]
}
puts "Implementation opened: [current_run]"


set devicepart [lindex  [get_parts -of_objects [current_project]] 0]
set fout [open $exportdir/LAYOUT_$devicepart.xml w]

puts $fout "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
puts $fout "<DEVICE part=\"$devicepart\">"

foreach slr [get_slrs] {
    puts $fout [format "\t<SLR\n\t\tname=\"%s\"" [get_property NAME $slr]]
    puts $fout [format "\t\tslr_index=\"%s\"" [get_property SLR_INDEX $slr]]
    puts $fout [format "\t\tconfig_order_index=\"%s\">" [get_property CONFIG_ORDER_INDEX $slr]]
    
    
    foreach cr [get_clock_regions -of_objects $slr] {
        puts $fout [format "\n\t\t<CLOCK_REGION name=\"%s\">" [get_property NAME $cr]]
    
        puts "Processing Tiles in SRL: $slr, ClockRegion: $cr"
        set columndict [dict create]
        foreach tile [get_tiles -of_objects $cr -filter {TYPE==CLBLM_L || TYPE==CLBLM_R || TYPE==CLEL_R || TYPE==CLEM}] {
            lassign [regexp -all -inline X([0-9]+)Y([0-9]+) [get_property NAME $tile]] S X Y
            if { [dict exists $columndict $X] } { 
                set v [dict get $columndict $X] 
                if { $Y < [lindex $v 0] } { 
                    #puts "replace Min: $Y"
                    set v [lreplace $v 0 0 $Y]  
                }
                if { $Y > [lindex $v 1] } { 
                    #puts "replace Max: $Y"
                    set v [lreplace $v 1 1 $Y]
                }
                dict set columndict $X $v
            } else {
                #puts "Appending $X : $Y : $Y"
                set tiletype [get_property TYPE $tile]
                dict append columndict $X [list $Y $Y $tiletype]
            }
        }    

        dict for {key val} $columndict {
            puts $fout [format "\t\t\t<COLUMN type=\"%s\" X=\"%s\" MinY=\"%s\" MaxY=\"%s\"> </COLUMN>" [lindex $val 2] $key [lindex $val 0] [lindex $val 1]]
        }
        puts $fout "\n\t\t</CLOCK_REGION>"      
    }
    puts $fout "\n\t</SLR>"
    flush $fout
}
puts $fout "</DEVICE>"
close $fout




