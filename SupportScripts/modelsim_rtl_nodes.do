#do modelsim_rtl_nodes.do {Scope/*} {outfile.txt} {parse arrays: on/...} {injectable } {filter_expression}
#do modelsim_rtl_nodes.do /tb/mc8051_top/mc8051_core//* ./code/obs_instances_log.txt on on -internal 

quietly set allsignals {}


proc addElements {ielemList fp parsearrays injectable filter } {
	for {set it 0} {$it < [llength $ielemList]} {incr it} {
		if {[find signals $filter [lindex $ielemList $it].*] != ""}   {
				set sigList [lsort -dictionary [find signals $filter [lindex $ielemList $it].*]]
				for {set s 0} {$s < [llength $sigList]} {incr s} {
					addElements [lindex $sigList $s] $fp $parsearrays $injectable $filter
				}
		} elseif { $parsearrays == "on" && [find signals $filter [lindex $ielemList $it](*)] != ""}  {
				set sigList [lsort -dictionary [find signals $filter [lindex $ielemList $it](*)]]
				for {set s 0} {$s < [llength $sigList]} {incr s} {
					addElements [lindex $sigList $s] $fp $parsearrays $injectable $filter
				}
		} else {
            set tci [lindex $ielemList $it]
			if { $injectable == "on" } {
				#filter-out non-logic types (where 0/1 can not be forced)
				if {([catch {force -freeze $tci 1}] == 0) && ([catch {force -freeze $tci 0}] == 0)} {            
					puts $fp "{$tci}"
				} 
			} else {
				puts $fp "{$tci}"
			}			
		}
	}
}


 

quietly set inst $1
quietly set fout $2
quietly set parsearrays $3
if { $argc > 3} {
	quietly set injectable $4
} else {
	quietly set injectable ""
}
if { $argc > 4} {
	quietly set filter $5
} else {
	quietly set filter ""
}

quietly set allsignals [lsort -dictionary [find signals -r $filter $inst]]
quietly set fp [open $fout w]
addElements $allsignals $fp $parsearrays $injectable $filter

close $fp



