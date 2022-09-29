# DAVOS - a fault Injection toolkit for dependability assessment, verification, optimization and selection of hardware desings. #



DAVOS is an open-source fault injection toolkit that automates dependability-driven processes of the semicustom design flow, 
including:
- *Dependability assessment* of HW designs at different stages of design flow:
    - RTL and gate-level models by means of simulation-based fault injection (*SBFI*);
    - FPGA prototypes by means of FPGA-based fault injection (*FFI*).
- *Verification* of fault tolerance mechanisms.
- *Dependability Benchmarking* of IP cores, EDA tools, and implementation technologies for the selection of most suitable (robust) alternatives.
- *Dependability-driven design space exploration (DSE)* for optimally tuning/configuring IP cores and EDA tools, in order to reach the best possible robustness features of HW implementations. 

DAVOS comprises a set of standalone tools and supplementary modules, as depicted below: 

![DAVOS architecture](doc/DAVOS_architecture.png) 



### 1. FPGA fault injection tool (DAVOS-FFI)
   A bit-precise FFI tool for automated dependability/security assessment of FPGA prototypes.
   Supports hierarchical FFI experiments where any node in the DUT tree can be targeted at the granularity of individual 
   netlist cells (LUTs, registers, BRAM/LUTRAM cells, etc). Implements the bit-accurate FFI methodology described in [1]. 
   
   Main features:
 - Basic FFI approach: runtime reconfiguration - faults are emulated by manipulating the content of configuration memory (CM)
   through the ICAP (Artix/Kintex/Virtex) or PCAP (Zynq) ports;
 - Uses Xilinx Microblaze or Zynq IPs as an on-chip FFI controller; 
 - Fault models:
    - Bit-flips in changeable memory cells (registers, BRAM, LUTRAM): transient faults (soft-errors);
    - Bit-flips in non-changeable CM (essential bits): in the absence of CM scrubbing manifest as permanent faults in combinational logic and routing 
      (stuck-at, short, open, bridging);
 - Fault targets are selected attending to a set of filters: hierarchical design scope, Pblock/area (floorplan coordinates), 
   type of netlist cells;
 - Two preconfigured FFI setups: 
    - Controlled from the host PC, suitable for DUTs requiring debug link wih the host (e.g. Cobham Gaisler NOELV SoC debugged using GRMON tool)
    - Controlled from the target FPGA for fully embedded FFI experiments, suitable for those DUTs that can be tested without host support;
 - More custom FFI setups can be easily o the basis of modular DAVOS FFI library;
 - Supports Xilinx 7-series, Ultrascale and Ultrascale+ FPGAs and Zynq SoCs;
 - Provides interactive reporting interface for visualization and analysis of FFI results.
 - Supported speed-up techniques: iterative statistical fault injection, and multiprocessing on the stacks of FPGA evaluation boards.



### 2. Simulation-based fault injection tool (DAVOS-SBFI): 

  Automates dependability assessment and verification of HDL models at RTL and gate-level (post-synthesis / post-place-route) 
  after the SBFI methodolofy described in [1]. 
    Preconfigured for Mentor Graphics' ModelSim/QuestaSim simulator.
    Supports custom fault dictionaries for any third-party library of technology-specific macrocells.
    Speeds-up SBFI experiments by means of iterative statistical fault injection, checkpointing, 
    multi-level fault injection, multi-core and GRID-based multiprocessing.
    

### 3. Implementation support tool: 

  Automates translation of RTL designs into the target implementation technology (e.g. FPGA bitstream) by running any custom implementation flow defined by the designer.
  For each obtained implementation it retrieves the performance, power consumption, and area/utilization (PPA) features.


### 4. Supplementary DAVOS modules  

#### 4.1. PPAD evaluation engine: 

  Automates evaluation of PPA and dependability features of multiple parameterized HW design alternatives.
  Provides customizable PPAD evaluation pipeline, based on DAVOS-FFI, DAVOS-SBFI and implementation support tools.
  Multiple designs are evaluated in parallel using multicore/GRID systems, and stacks of FPGA evaluation boards.

  
#### 4.2. Decision support tool: 

Automates those dependability-driven processes that evaluate multiple design alternatives, such as 
dependability benchmarking and dependability-driven design space exploration (DSE). 
  Implements DSE approaches describes in chapter 7 of [1], including:
    - DSE based on genetic algorithms (GA/NSGA), accelerated by means of iterative dependability-driven selection;
    - DSE based on the design of experiments (DoE), accelerated by means of iterative refinement of D-optimal designs.

    
#### 4.3. Data Controller: 

 Manages internal data model of the DAVOS toolkit, being in charge of:
    - Synchronizing the dataflow between DAVOS modules;
    - Collecting experimental results; 
    - Performing object-relational mapping (ORM) between the internal data model and SQLite database; 
    - Providing an interface for querying experimental results from the datasets attending to a set of filters.


#### 4.4  DAVOS Web-interface: 

 DAVOS UI is a collection of HTML5 and Javascript files (front-end) as well as python scripts (at the back-end) that 
 implement an interactive web interface for:
    - monitoring the status of each task executed by DAVOS, 
    - querying the results from the dataset, collected by DAVOS during SBFI/FFI experiments, attending to a set of filters configured by user;
    - visualizing obtained SBFI/FFI results within interactive web-based widgets that allow:
      - highlight the distribution of failure modes along the design tree;
      - indicate the weak points of the design (from the robustness viewpoint);
      - visualize the detailed FI traces, allowing to analyze the fault propagation path in the design.  

#### 4.5 FPGA design parser
   
   Parses the bitstream, essential bits mask, logic location file, and the netlist of the Vivado design, relating them under an internal design model.
   Performs the bit-accurate mapping of essential bits with the hierarchical netlist to support bit-precise FFI.

## Compatibility and System Requirements
DAVOS supports Linux and Windows OS.

All DAVOS tools require a basic python 2.x distribution. Note: DAVOS is currently not compatible with python 3.x. 

Depending on use case following third-party tools are required:
- Simulation-based fault injection tool requires ModelSim/Questa simulator;
- Bit-accurate FPGA-based fault injection tool requires Xilinx Vivado suite; 
- Design Space Exploration based on statistical techniques (DoE) requires a Matlab statistical toolkit;
- Scenarios involving automated design implementation require corresponding EDA tools (e.g. Xilinx Vivado, ISE, etc);
- FPGA-based fault injection tool has been verified to work properly on a wide range of Xilinx 7-series FPGAs and Zynq SoC FPGAs;   

## Installation
Clone DAVOS repository to the working directory.
Interactive DAVOS UI requires to configure a web-server (Apache preferred). 
Ensure that Web-server is configured to execute CGI scripts, particularly python-scripts. In the 'httpd.conf' file (XAMMP control panel – button config in front of apache module):

– search for line Options Indexes FollowSymLinks and add ExecCGI, so the resulting line looks like this: *Options Indexes FollowSymLinks ExecCGI*

– search for #AddHandler cgi-script .cgi, uncomment (remove #), and append “.py” to this line, so the results looks like: *AddHandler cgi-script .cgi .pl .asp .py*

For more details refer to the user manual.
>User manual will be published soon


## Branches
- "master" branch contains the latest DAVOS version that integrates all recently added features;
- "DSE" branch contains the stable version of the DAVOS toolkit as it has been presented in the thesis https://doi.org/10.4995/Thesis/10251/159883. 



## Copyright
Copyright (c) 2018 Universitat Politècnica de València

Author / Developer: Ilya Tuzov (Universitat Politècnica de València)

DAVOS is released under the "MIT license agreement". 
Please check the LICENSE.txt file (that is included as a part of this package) for the license details.




## References

[1]. A PhD thesis describing the new fault injection methods used in the DAVOS toolkit, as well as the toolkit itself: https://doi.org/10.4995/Thesis/10251/159883

[2]. A tool description paper presented at the 48th Annual IEEE/IFIP International Conference on Dependable Systems and Networks (DSN'2018): https://doi.org/10.1109/DSN.2018.00042

[3]. A dataset illustrating the basic DAVOS use cases:   https://doi.org/10.5281/zenodo.891316


## Acknowledgement

- This work has been carried-out under the support of the "Programa de Ayudas de Investigación y Desarrollo" (PAID) de la Universitat Politècnica de València.
- Adaptation to the NOEL-V RISCV platform is currently supported by the:
  * SELENE project (www.selene-project.eu) funded by the European Unions Horizon 2020 research and innovation programme under grant agreement No. 871467, and
  * FRACTAL project (https://fractal-project.eu/) funded by the ECSEL Joint Undertaking (JU) under grant agreement No. 877056
    
