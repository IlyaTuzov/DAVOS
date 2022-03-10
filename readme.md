# DAVOS - a fault Injection toolkit for dependability assessment, verification, optimization and selection of hardware desings. #

## Branches
- "master" branch contains the latest DAVOS version that integrates all recently added features;
- "DSE" branch contains the stable version of the DAVOS toolkit as it has been presented in the thesis https://doi.org/10.4995/Thesis/10251/159883. 

## Overview 

DAVOS is an open-source fault injection toolkit that automates dependability-driven processes of the semicustom design flow, including:
- *Robustness evaluation of HW designs* :
    - At the level of HDL model (RTL and gate-level) by means of Simulation-based fault injection (*SBFI*);
    - At the level of FPGA prototype by means of FPGA-based fault injection (*FFI*).
- *Dependabilty Benchmarking* of IP cores, EDA tools, and implementation technologies for the selection of most suitable (robust) alternatives.
- *Dependability-driven design space exploration (DSE)* for optimally tuning/configuring IP cores and EDA tools, in order to reach the best possible robustness features of HW implementations. 


 **Main features:** 
 - Bit-accurate FPGA-based fault injection (FFI) for Xilinx 7-series FPGAs,
 - Simulation-based fault injection (SBFI) at RTL and implementation-level (technology-specific netlsits),
 - Provides a python-based framework for implementing custom bit-accurate fault injectors for Xilinx 7-series FPGAs,
 - Accelerated robustness assessment using FI speed-up techniques: iterative statistical FI, filtering of FPGA essential bits, LUT profiling, multi-level FI, checkpointing, multiprocessing;
 - Parallelized evaluation of PPAD features (Performance, Power consumption, Area and Dependability) of multiple parameterized design alternatives, using multicore / GRID systems, and clusters of FPGA boards;
 - Compatible with different HDL, EDA tools, and technology-specific libraries;
 - Multiplatform (any OS, diverse computing platforms);
 - Compact yet flexible format of experimental datasets, coupled with a lightweight web-based interface for the analysis and visualization of such datasets.

## DAVOS tools:
1. *FPGA-based fault injection tool (DAVOS-FFI)*: automates robustness evaluation of FPGA implementations against SEUs in configuration memory (CM), user memories (BRAM, LUTRAM) and Registers.
   Implements a bit-accurate FFI methodology described in chapter 5 of https://doi.org/10.4995/Thesis/10251/159883. Supports Xilinx 7-series FPGAs and Zynq SoC FPGAs. 
   Implements such speed-up techniques as iterative statistical fault injection, and multiprocessing on the stacks of FPGA evaluation boards.
  Provides a framework for implementation of custom FPGA-based fault injection tools, comprising:
    - C/C++ FFI library for implementing embedded FFI applications, targeting Xilinx Microblaze and Zynq processors used as board-side FFI controllers;
    - Python library for implementing custom bit-accurate FFI tools, that setup, control and monitor an FFI workflow on the host side.
    

2. *Simulation-based fault injection tool (DAVOS-SBFI)*: automates robustness evaluation of HDL models at RTL and gate-level (post-synthesis / post-place-route) 
  after the new SBFI methodolofy described in chapter 4 of https://doi.org/10.4995/Thesis/10251/159883. 
    Preconfigured for Mentor Graphics' ModelSim/QuestaSim simulator.
    Supports custom fault dictionaries for any third-party library of technology-specific macrocells.
    Implements such speed-up techniques as iterative statistical fault injection, checkpointing, multi-level fault injection, multi-core and GRID-based multiprocessing.
    
  
3. *Implementation support tool*: automates translation of RTL designs into the target implementation technology (e.g. FPGA bitstream) by running any custom implementation flow defined by the designer.
  For each obtained implementation it retrieves the performance, power consumption, and area/utilization (PPA) features.


4. *PPAD evaluation engine*: automates evaluation of PPA and dependability features of multiple parameterized HW design alternatives.
  Provides customizable PPAD evalution pipeline, based on DAVOS-FFI, DAVOS-SBFI and implementation support tools.
  Multiple designs are evaluated in parallel using multicore/GRID systems, and clusters of FPGA evaluation boards.

  
5. *Decision support tool*: automates dependability-driven processes that evaluate multiple design alternatives, such as 
dependability benchmarking and dependability-driven design space exploration (DSE). 
  Implements new DSE approaches describes in chapter 7 of https://doi.org/10.4995/Thesis/10251/159883, that include:
    - DSE based on genetic algorithms (GA/NSGA), accelerated by means of iterative dependability-driven selection;
    - DSE based on the design of experiments (DoE), accelerated by means of iterative refinement of D-optimal designs.

    
6. *Data Controller*: manages internal data model of the DAVOS toolkit, being in charge of:
    - Synchronizing the dataflow between DAVOS modules;
    - Collecting experimental results; 
    - performing object-relational mapping (ORM) between the internal data model and an SQLite datasets; 
    - Providing an interface for querying experimental results from the datasets attending to a set of filters.


7.  *DAVOS Web-interface*: it is a collection of HTML5 and Javascript files (front-end) as well as python scripts (at the back-end). 
    It implements an interactive user interface for:
    - monitoring the status of each task executed by DAVOS, 
    - querying the results from the dataset, collected by DAVOS during SBFI/FFI experiments, attending to a set of filters configured by user;
    - visualizing obtained SBFI/FFI results within interactive web-based widgets that:
      - highight the distribution of failure modes along the design tree;
      - indicate the weak points of the design (from the robustness viewpoint);
      - visualize the detailed FI traces, allowing to analyze the fault propagation path in the design.  

## Compatibility and System Requirements
DAVOS has been verified to work properly under the Linux and Windows OS.

All DAVOS tools require basic python 2.x distribution. Note: DAVOS is currently not compatible with python 3.x. 

Depending on use case following third-party tools are required:
- Simulation-based fault injection tool requires ModelSim/Questa simulator;
- Bit-accurate FPGA-based fault injection tool requires Xilinx Vivado suite; 
- Design Space Exploration based on statistical techniques (DoE) requires a Matlab statistical toolkit;
- Scenarios involving automated design implementation require corresponding EDA tools (e.g. Xilinx Vivado, ISE, etc);
- FPGA-based fault injection tool has been verified to work properly on a wide range of Xilinx 7-series FPGAs and Zynq SoC FPGAs;   

## Installation
Clone DAVOS repository to the working directory.
Interactive web-based DAVOS reports require to configure a web-server (Apache preferred). 
Ensure that Web-server is configured to execute CGI scripts, particularly python-scripts. In the 'httpd.conf' file (XAMMP control panel – button config in front of apache module):

– search for line Options Indexes FollowSymLinks and add ExecCGI, so the resulting line looks like this: *Options Indexes FollowSymLinks ExecCGI*

– search for #AddHandler cgi-script .cgi, uncomment (remove #), and append “.py” to this line, so the results looks like: *AddHandler cgi-script .cgi .pl .asp .py*

For more details refer to the user manual.
>User manual will be published soon

## Copyright
Copyright (c) 2018 Universitat Politècnica de València

Author / Developer: Ilya Tuzov (Universitat Politècnica de València)

DAVOS is released under the "MIT license agreement". 
Please check the LICENSE.txt file (that is included as a part of this package) for the license details.



## References

1. A PhD thesis describing the new fault injection methods used in the DAVOS toolkit, as well as the toolkit itself: https://doi.org/10.4995/Thesis/10251/159883

2. A tool description paper presented at the 48th Annual IEEE/IFIP International Conference on Dependable Systems and Networks (DSN'2018): https://doi.org/10.1109/DSN.2018.00042

3. A dataset illustrating the basic DAVOS use cases:   https://doi.org/10.5281/zenodo.891316


## Acknowledgement

- This work has been carried-out under the support of the "Programa de Ayudas de Investigación y Desarrollo" (PAID) de la Universitat Politècnica de València.
- Adaptation to the NOEL-V RISCV platform is currently supported by the:
  * SELENE project (www.selene-project.eu) funded by the European Unions Horizon 2020 research and innovation programme under grant agreement No. 871467, and
  * FRACTAL project (https://fractal-project.eu/) funded by the ECSEL Joint Undertaking (JU) under grant agreement No. 877056
    
