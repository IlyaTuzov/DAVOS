# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       A Vivado script to parse the layout of Xilinx FPGAs
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------


#Run example: 
#    vivado -mode batch -source C:/GitHub/DAVOS/SupportScripts/VivadoParseLayout.do -tclargs C:/Projects/FFIMIC/FFIMIC.xpr "*" "*" C:/GitHub/DAVOS/FFI/DeviceSupport
#    vivado -mode batch -source C:/GitHub/DAVOS/SupportScripts/VivadoParseLayout.do -tclargs "*" "xc7a100tcsg324-1" "*" C:/GitHub/DAVOS/FFI/DeviceSupport
if {$argc < 4} {
    puts "not enough arguments"
    return
}

set proj        [lindex $argv 0]
set device      [lindex $argv 1]
set run         [lindex $argv 2]
set exportdir   [lindex $argv 3]
puts "proj=$proj, run=$run, exportdir=$exportdir"

if {$proj != "*"} {
    open_project $proj
    puts "Project opened: [current_project]"
} else {
    create_project project_1 $exportdir/project_1 -part $device
    set_property target_language VHDL [current_project]
    add_files -norecurse $exportdir/template.vhd
    update_compile_order -fileset sources_1
    launch_runs synth_1 -jobs 8
    wait_on_run -timeout 360 synth_1
    launch_runs impl_1 -jobs 8
    wait_on_run -timeout 360 impl_1
}


if {$run != "*" } {
    open_run [get_runs $run]
} else {
    open_run [get_runs -filter {CURRENT_STEP == route_design || CURRENT_STEP == write_bitstream}]
}
puts "Implementation opened: [current_run]"
set devicepart [lindex  [get_parts -of_objects [current_project]] 0]
set devicefamily [lindex [split [get_property ARCHITECTURE_FULL_NAME $devicepart]] 0]
set deviceseries [lindex [split [get_property ARCHITECTURE_FULL_NAME $devicepart]] 1]


set_property BITSTREAM.General.UnconstrainedPins {Allow} [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]
set_property SEVERITY {Warning} [get_drc_checks NSTD-1]
set_property SEVERITY {Warning} [get_drc_checks UCIO-1]
write_bitstream $exportdir/$devicepart.bit
puts "Debug Bitsream Generated"



set fout [open $exportdir/LAYOUT.xml w]
puts $fout "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
puts $fout [format "<DEVICE part=\"%s\" family=\"%s\" series=\"%s\" >" $devicepart $devicefamily $deviceseries]


foreach slr [get_slrs] {
    puts $fout [format "\t<Slr\n\t\tname=\"%s\"" [get_property NAME $slr]]
    puts $fout [format "\t\tslr_index=\"%s\"" [get_property SLR_INDEX $slr]]
    puts $fout [format "\t\tconfig_order_index=\"%s\">" [get_property CONFIG_ORDER_INDEX $slr]]
    
    
    foreach cr [get_clock_regions -of_objects $slr] {
        puts $fout [format "\n\t\t<ClockRegion name=\"%s\">" [get_property NAME $cr]]
        puts "Processing Tiles in SRL: $slr, ClockRegion: $cr"
        foreach tile [get_tiles -of_objects $cr ] {
            puts $fout [format "\t\t<Tile name=\"%s\" type=\"%s\" column=\"%s\">" [get_property NAME $tile] [get_property TYPE $tile] [get_property COLUMN $tile]]
            foreach site [get_sites -of_objects $tile] {
                puts $fout [format "\t\t\t<Slice name=\"%s\" type=\"%s\" />" [get_property NAME $site] [get_property SITE_TYPE $site]]
            }
            puts $fout "\t\t</Tile>"

        }
        puts $fout "\n\t\t</ClockRegion>"
    }
    puts $fout "\n\t</Slr>"
    flush $fout
}
puts $fout "</DEVICE>"
close $fout




