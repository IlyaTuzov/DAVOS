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
            f.write(struct.pack(specificator, self.BitstreamId))
            f.write(struct.pack(specificator, self.SyncTag))
            f.write(struct.pack(specificator, self.BitstreamAddr))
            f.write(struct.pack(specificator, self.BitstreamSize))
            f.write(struct.pack(specificator, self.BitmaskAddr))
            f.write(struct.pack(specificator, self.BitmaskSize))
            f.write(struct.pack(specificator, self.FaultListAdr))
            f.write(struct.pack(specificator, self.FaultListSize))
            f.write(struct.pack(specificator, self.UpdateBitstream))
            f.write(struct.pack(specificator, self.Mode))
            f.write(struct.pack(specificator, self.Blocktype))
            f.write(struct.pack(specificator, self.Celltype))
            f.write(struct.pack(specificator, self.Essential_bits))
            f.write(struct.pack(specificator, self.CheckRecovery))
            f.write(struct.pack(specificator, self.LogTimeout))
            f.write(struct.pack(specificator, self.StartIndex))
            f.write(struct.pack(specificator, self.ExperimentsCompleted))
            f.write(struct.pack(specificator, self.Failures))
            f.write(struct.pack(specificator, self.Signaled))
            f.write(struct.pack(specificator, self.Masked))
            f.write(struct.pack(specificator, self.Latent))
            f.write(struct.pack(specificator, self.SDC))
            f.write(struct.pack(specificator, self.sample_size_goal))
            f.write(struct.pack('<f', self.error_margin_goal))
            f.write(struct.pack(specificator, self.FaultMultiplicity))
            f.write(struct.pack(specificator, self.FilterFrames))
            f.write(struct.pack('<f', self.PopulationSize))
            f.write(struct.pack(specificator, self.WorkloadDuration))
            f.write(struct.pack(specificator, self.SamplingWithouRepetition))
            f.write(struct.pack(specificator, self.DetailedLog))
            f.write(struct.pack(specificator, self.DetectLatentErrors))
            f.write(struct.pack(specificator, self.InjectionTime))



