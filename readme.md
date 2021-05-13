# DAVOS - a toolkit for Dependability assessment, verification, optimization and selection of hardware models. #

## Overview 

DAVOS provides the support for dependability-driven processes along the semicustom design flow. It comprises a set of independent modules implemented in python, which support the customizable data model (ORM managed by custom data manager), and can be launched on PC and/or Grid (SGE) under any OS supporting python.  It's basic use cases (application scenarios) include:
- *Robustness evaluation of HDL models* at any representation level (RTL, gate-level, implementation-level) by means of simulation-based fault injection. This scenario is managed by Fault injection module. VHDL, Verilog, SystemVerilog are supported. Injection procedures take into account the requirement of each representation level. Customizable fault dictionary by-default includes most common fault models (bit-flips, stuck-at, delays, etc.) for RTL models, and Xilinx's simprim macrocells (VITAL-compliant). 
-  *Dependabilty Benchmarking* used for selection of alternative IP cores, EDA tools, and implementation technologies. Selection is based on MCDM techniques: Pareto-optimization, and/or ranking by means of weighted sum models. Score may take into account any properties stored into the project database for each model. Custom metrics can be defined in configuration file.
- *Design space exploration* used to optimally configure the parameters of HDL model and/or EDA tools, thus to obtain the best possible implementation. Two DSE approaches are currently implemented: i) statistical method relying on design of experiments (fractional factorial designs), and ii) method based on genetic algorithms. 

 **Main features:** 
 - Seamlessly integrates into any semisuctom design flow (define your custom implementation process);
 - Compatible with different HDL, EDA tools and implementation technologies;
 - Multiplatform (any OS, diverse computing platforms);
 - Web-based interactive reporting and analysis interface;
 - Self-contained format for interchange of experimental datasets, with lightweight web-based interface attached, to effectively share the experimental results;
 - ...

**Basic workflow:**
1. Define custom project configuration (or customize one of provided templates)
    *config.xml*, including following sections (none of them is mandatory):
        - *Implementation flow* describes how off-the-shelf EDA tools are configured and launched at each phase of custom implementation chain, so as to obtain the implementation (and estimate it's static properties) with respect to any configuration of design/EDA parameters. 
        - *Factorial Design* defines the factors in the design space under study with the EDA/dsign parameters and their selected treatment levels;
        - *Design Under Study* defines all the required parameters of HDL model to be implemented, assessed, and optimized
        - *Robustness Assessement* defines the parameters of fault injection experiments such as fault models, targeted macrocells, injection modes, distributions, etc.
        - *Project Configuration* defines the project's parameters: operating and reporting directories, database formats, etc.        
    >Refer to application scenarios for detailed information.
    
2. Invoke the required DAVOS tools with this file on the input


## Requirements
DAVOS itself can be launched on PC and SGE (Grid) platforms under any OS, supporting python. Both versions 2.x and  3.x are supported. Current implementation can be run on standard python distribution (no dependencies on third-partly modules). Additionally depending on use case are required following tools:
- Robustness assessement requires a ModelSim-like simulator;
- Design Space Exploration based on statistical techniques, requires Matlab (statistical toolkit), while for GA-based DSE Matlab is not required.
- Scenarios involving implementation process require EDA tools of custom selection (e.g. Xilinx Vivado Suite).

## Installation
Unpack the contents of DAVOS package to any directory. 
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
