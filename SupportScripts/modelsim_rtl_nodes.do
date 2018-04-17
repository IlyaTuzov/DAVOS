#do dadse_rtl_nodes.do {Scope/*} {outfile.txt} {parse arrays: on/...} {filter_expression}
#do dadse_rtl_nodes.do /tb/mc8051_top/mc8051_core//* ./code/obs_instances_log.txt on -internal

quietly set allsignals {}


proc addElements {ielemList fp parsearrays filter} {
	for {set it 0} {$it < [llength $ielemList]} {incr it} {
		if {[find signals $filter [lindex $ielemList $it].*] != ""}   {
				set sigList [lsort -dictionary [find signals $filter [lindex $ielemList $it].*]]
				for {set s 0} {$s < [llength $sigList]} {incr s} {
					addElements [lindex $sigList $s] $fp $parsearrays $filter
				}
		} elseif { $parsearrays == "on" && [find signals $filter [lindex $ielemList $it](*)] != ""}  {
				set sigList [lsort -dictionary [find signals $filter [lindex $ielemList $it](*)]]
				for {set s 0} {$s < [llength $sigList]} {incr s} {
					addElements [lindex $sigList $s] $fp $parsearrays $filter
				}
		} else {
            set tci [lindex $ielemList $it]
            #filter-out non-logic types (where 0/1 can not be forced)
            if {([catch {force -freeze $tci 1}] == 0) && ([catch {force -freeze $tci 0}] == 0)} {            
                puts $fp "{$tci}"
            }				
		}
	}
}


 

quietly set inst $1
quietly set fout $2
quietly set parsearrays $3
if { $argc > 3} {
	quietly set filter $4
} else {
	quietly set filter ""
}


quietly set allsignals [lsort -dictionary [find signals $filter -recursive  $inst]]
quietly set fp [open $fout w]
addElements $allsignals $fp $parsearrays $filter

close $fp



