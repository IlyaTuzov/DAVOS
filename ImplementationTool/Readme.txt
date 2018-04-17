A tool for implementation of factorial designs in Xilinx ISE toolkit.

Note: this readme is for old version of this tool. Although it is valid, new features to be documented later.
_______________________________________________________________________________________________________________

Requirements: python 2.X basic distrubution. For windows: https://www.python.org/downloads/release/python-2712/

1. Create the template project folder, including:
	1.1. *.prj file containing a list of design files (.vhd)
	1.2. testbench to simulate post-par netlist (.vhd)
	1.3. [optional] *.prj file, containing a list of files comprising test environment, may be empty
	1.4. [optional] *.ucf file, containing implementation constraints (except for clock period), may be empty
	
2. Create the fractional factorial design (table of configurations, *.csv file)

3. Create/Edit the script configuration file (*.xml ). Switch-on the required phases:
	- implement_design - implements the disign, iteratively approaching the maximum clock frequency; produces the post-par netlist.
	- build_testbench_random_inputs - build the testbench with randomized inputs, USE this option ONLY WHEN functional testbench is not available
	- simulate_switching_activity - simulates the post-par netlist with the testbench previously provided; produces the SAIF file (switching activity)
	- summarize_report_data - build final report files:
		+ summary_power_estimated.csv, where dynamic power is estimated without SAIF file (approx.);
		+ summary_power_simulated.csv, where the dynamic power is estimated accurately, feeding the SAIF file to xpower tool;
		
4. Run the script, command line: python xilinx_synt.py configuration.xml

Resulting files:
		+ in the [netlist_dir/par] dir: 
			_timesim.vhd (+sdf) post-par netlist, 
			_map.vhd - post-map netlist,
			_synthesis.vhd - post-synthesis netlist,
		+ in the [log_dir] dir:
			raw logs and reports produced by implementation tools (xst/ngbuild/map/par/trace/xpower/...)
		+ in the [call_directory/{design_label}] dir: 
			summary_estimated_power.csv - table of properties for each configuration of factorial design: utilization, frequency, power consumption (estimated without SAIF file)
			SAIF_{top_design_unit}.csv - table of properties for each configuration of factorial design: utilization, frequency, power consumption (estimated after simulation of the design, with SAIF file)
			set of log files, produced by the script for each configuration (each process): iterations performed, process statistics, netlist statistics
	