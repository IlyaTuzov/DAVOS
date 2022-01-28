# DAVOS - a toolkit for Dependability assessment, verification, optimization and selection of hardware models. #

## Branches
- "master" branch contains the latest version that integrates all recently added features;
- "DSE" branch contains the stable version of the toolkit as presented in the thesis https://doi.org/10.4995/Thesis/10251/159883. 

## Overview 

DAVOS toolkit automates different dependability-driven processes of the semicustom design flow, that are based on the fault injection testing.
Supports following use cases:
- *Robustness evaluation of HDL models* at any representation level (RTL, gate-level, implementation-level) by means of simulation-based fault injection. This scenario is managed by Fault injection module. VHDL, Verilog, SystemVerilog are supported. Injection procedures take into account the requirement of each representation level. Customizable fault dictionary by-default includes most common fault models (bit-flips, stuck-at, delays, etc.) for RTL models, and Xilinx's simprim macrocells (VITAL-compliant). 
-  *Dependabilty Benchmarking* used for selection of alternative IP cores, EDA tools, and implementation technologies. Selection is based on MCDM techniques: Pareto-optimization, and/or ranking by means of weighted sum models. Score may take into account any properties stored into the project database for each model. Custom metrics can be defined in configuration file.
- *Dependability-aware design space exploration (DSE)* used to optimally configure the parameters of HDL model and/or EDA tools, thus to obtain the most robust implementation. Two DSE approaches are currently implemented: i) statistical method relying on design of experiments (fractional factorial designs), and ii) method based on genetic algorithms. 

 **Main features:** 
 - Simulation-based fault injection at implementation-level (technology-specific post-place-route netlsits),
 - Bit-accurate FPGA-based fault injection for Xilinx 7-series FPGAs,
 - Implements multiple SBFI/FFI speed-up techniques for accelerated robustness assessment: iterative statitical injeciton, filtering of FPGA essential bits, LUT profiling, multi-level fault injection, checkpointing, multiprocessing;
 - PPAD evaluation engine for parallelized evaluation of multiple design alternatives, using multicore / GRID systems, and stacks of FPGA boards;
 - Provides a python-based framework for the definition of custom fault injectors,
 - Compatible with different HDL, EDA tools, and technology-specific libraries;
 - Multiplatform (any OS, diverse computing platforms);
 - Compact yet flexible format of experimental datasets, coupled with a lightweight web-based interface for the analysis and visualization of such datasets.


**Basic workflow:**
1. Define custom project configuration (or customize one of provided templates)
    *config.xml*, include several sections (none of them is mandatory) to configure the corresponding DAVOS proceses:
        - *Implementation flow* describes how off-the-shelf EDA tools are configured and launched at each phase of custom implementation chain, so as to obtain the implementation (and estimate it's static properties) with respect to any configuration of design/EDA parameters. 
        - *Factorial Design* defines the factors in the design space under study with the EDA/dsign parameters and their selected treatment levels;
        - *Design Under Study* defines all the required parameters of HDL model to be implemented, assessed, and optimized
        - *SBFI* defines parameters of simulation-based fault injection experiments, including fault models, fault targets, observation traces, etc.
        - *FFI* defines parameters of FPGA-based fault injection experiments, including voard-side injection controller, injection modes, fault models, fault targets, etc.         
    >Refer to application scenarios for detailed information.
    
2. Invoke the selected DAVOS tool, supplying this configuration file as input argument.


## Requirements
DAVOS itself can be launched on PC and SGE (Grid) platforms under any OS, supporting python. Currently only python version 2 is supported. No third-party python modules are required. Depending on use case following tools are required:
- Robustness assessement requires a ModelSim/ simulator;
- Design Space Exploration based on statistical techniques (DoE) requires Matlab statistical toolkit.
- Scenarios involving automated design implementation require corresponding EDA tools (e.g. Xilinx Vivado, ISE, etc).

## Installation
Clone DAVOS to the working directory.
For interactive web-based reports configure the web-server (Apache preferred). Ensure that Web-server is configured to execute CGI scripts, particularly python-scripts. In the 'httpd.conf' file (XAMMP control panel – button config in front of apache module):
– search for line Options Indexes FollowSymLinks and add ExecCGI, so the resulting line looks like this: 
*Options Indexes FollowSymLinks ExecCGI*
– search for #AddHandler cgi-script .cgi, uncomment (remove #), and append “.py” to this line, so the results looks like: *AddHandler cgi-script .cgi .pl .asp .py*

For more details refer to user manual.
>User manual will be published soon


## References
Dataset illustrating the basic application scenarios:   https://doi.org/10.5281/zenodo.891316


## Acknowledgement

This work has been performed under the support of the "Programa de Ayudas de Investigación y Desarrollo" (PAID) de la Universitat Politécnica de Valéncia.
Adaptation to the NOEL-V RISCV platform is currently supported by the H2020 SELENE project (www.selene-project.eu). 
