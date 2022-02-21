# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Base library for the definition of the host-side of FPGA-based fault injectors,
#       whose workflow is controlled from the FPGA (evaluation board)
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

from FFI_Host_Base import *


class JobDescriptor:
    def __init__(self, BitstreamId):
        self.BitstreamId = BitstreamId
        self.SyncTag = 0  # this is to handshake with the device and filter messages on serial port
        self.BitstreamAddr = 0
        self.BitstreamSize = 0
        self.BitmaskAddr = 0
        self.BitmaskSize = 0
        self.FaultListAdr = 0
        self.FaultListSize = 0
        self.UpdateBitstream = 0
        self.Mode = 0  # 0 - exhaustive, 1 - sampling
        self.Blocktype = 0  # 0 - CLB , 1 - BRAM, >=2 both
        self.Celltype = 0  # 0 - ANY, 1-FF, 2-LUT, 3-BRAM, 4-Type0
        self.Essential_bits = 0  # 0 - target all bits, 1 - only masked bits
        self.LogTimeout = 1000  # report intermediate results each 1000 experiments
        self.CheckRecovery = 0
        self.EssentialBitsCount = 0
        self.StartIndex = 0
        self.ExperimentsCompleted = 0
        self.Failures = 0
        self.Signaled = 0
        self.Masked = 0
        self.Latent = 0
        self.SDC = 0
        self.sample_size_goal = 0
        self.error_margin_goal = float(0.0)
        self.FaultMultiplicity = 1
        self.FilterFrames = 0
        self.PopulationSize = 0.0
        self.WorkloadDuration = 0
        self.SamplingWithouRepetition = 0
        self.DetailedLog = 1
        self.DetectLatentErrors = 1
        self.InjectionTime = 0  # 0-random, > 0 - inject before clock cycle 'InjectionTime', e.g. InjectionTime==1 - inject at the workload start
        # these fields are not exported to device (for internal use)
        self.failure_rate = float(0.0)
        self.failure_error = float(50.0)
        self.masked_rate = float(0.0)
        self.masked_error = float(50.0)
        self.latent_rate = float(0.0)
        self.latent_error = float(0.0)
        self.InjectorError = False
        self.Time = None
        self.InjectorError = False
        self.VerificationSuccess = True

    def ExportToFile(self, fname):
        specificator = '<L'  # Little Endian
        with open(fname, 'wb') as f:
            f.write(struct.pack(specificator, 0xAABBCCDD))  # Start Sequence
            for i in [ self.BitstreamId, self.SyncTag, self.BitstreamAddr, self.BitstreamSize,
                       self.BitmaskAddr, self.BitmaskSize, self.FaultListAdr, self.FaultListSize,
                       self.UpdateBitstream, self.Mode, self.Blocktype, self.Celltype, self.Essential_bits,
                       self.CheckRecovery, self.LogTimeout, self.StartIndex, self.ExperimentsCompleted,
                       self.Failures, self.Signaled, self.Masked, self.Latent, self.SDC, self.sample_size_goal]:
                f.write(struct.pack(specificator, i))
            f.write(struct.pack('<f', self.PopulationSize))
            f.write(struct.pack('<f', self.error_margin_goal))
            for i in [ self.FaultMultiplicity, self.FilterFrames, self.WorkloadDuration, self.SamplingWithouRepetition,
                       self.DetailedLog, self.DetectLatentErrors, self.InjectionTime]:
                f.write(struct.pack(specificator, i))








class FFIHostMonitored(FFIHostBase):
    def __init__(self, targetDir, DevicePart, modelId):
        super(FFIHostMonitored, self).__init__(targetDir, DevicePart)
        self.modelId = modelId
