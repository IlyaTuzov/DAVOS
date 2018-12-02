#!/bin/sh
#$ -N IMPL_MC8051_ISE_001
#$ -l h_rt=20:00:00,h_vmem=4g
#$ -S /bin/sh
#$ -o C:\GitHub\DAVOS\GridLogs/out_IMPL_MC8051_ISE_001.txt
#$ -e C:\GitHub\DAVOS\GridLogs/err_IMPL_MC8051_ISE_001.txt
echo $PATH
cd C:\GitHub\DAVOS
python ImplementationTool.py ./testconfig/MC8051_IMPL_normalized.xml C:\Projects\Controllers\MC8051_Test\MC8051_ISE_001.XML