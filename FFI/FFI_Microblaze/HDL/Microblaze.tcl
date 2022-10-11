#export LANG=en_US.UTF-8
#vivado -mode batch -source BuildVivado.tcl -tclargs "/home2/tuil/FFI/MICTEST" "MicroblazeFFI"
#set SELENE_HARDWARE $env(GRLIB)/../

set TOP_PATH [pwd]
set projpath [get_property DIRECTORY [current_project]] 
set projname [get_property NAME      [current_project]] 
set SELENE_HARDWARE $projpath/../../../../
cd $projpath
puts "Integrating Microblaze into the project: $projname in $projpath"


#update_compile_order -fileset sources_1



set_property IP_REPO_PATHS $SELENE_HARDWARE/FFI/IP [current_fileset]
update_ip_catalog

# Proc to create BD FFICTR
proc cr_bd_FFICTR { parentCell } {

  # CHANGE DESIGN NAME HERE
  set design_name FFICTR

  common::send_gid_msg -ssname BD::TCL -id 2010 -severity "INFO" "Currently there is no design <$design_name> in project, so creating one..."

  create_bd_design $design_name

  set bCheckIPsPassed 1
  ##################################################################
  # CHECK IPs
  ##################################################################
  set bCheckIPs 1
  if { $bCheckIPs == 1 } {
     set list_check_ips "\ 
  user.org:user:CLKBUF:1.0\
  user.org:user:StartupCtrl:1.0\
  xilinx.com:ip:axi_gpio:2.0\
  xilinx.com:ip:axi_hwicap:3.0\
  xilinx.com:ip:axi_timer:2.0\
  xilinx.com:ip:clk_wiz:6.0\
  xilinx.com:ip:mdm:3.2\
  xilinx.com:ip:microblaze:11.0\
  xilinx.com:ip:axi_intc:4.1\
  xilinx.com:ip:xlconcat:2.1\
  xilinx.com:ip:proc_sys_reset:5.0\
  xilinx.com:ip:lmb_bram_if_cntlr:4.0\
  xilinx.com:ip:lmb_v10:3.0\
  xilinx.com:ip:blk_mem_gen:8.4\
  "

   set list_ips_missing ""
   common::send_gid_msg -ssname BD::TCL -id 2011 -severity "INFO" "Checking if the following IPs exist in the project's IP catalog: $list_check_ips ."

   foreach ip_vlnv $list_check_ips {
      set ip_obj [get_ipdefs -all $ip_vlnv]
      if { $ip_obj eq "" } {
         lappend list_ips_missing $ip_vlnv
      }
   }

   if { $list_ips_missing ne "" } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2012 -severity "ERROR" "The following IPs are not found in the IP Catalog:\n  $list_ips_missing\n\nResolution: Please add the repository containing the IP(s) to the project." }
      set bCheckIPsPassed 0
   }

  }

  if { $bCheckIPsPassed != 1 } {
    common::send_gid_msg -ssname BD::TCL -id 2023 -severity "WARNING" "Will not continue with creation of design due to the error(s) above."
    return 3
  }

  
# Hierarchical cell: microblaze_0_local_memory
proc create_hier_cell_microblaze_0_local_memory { parentCell nameHier } {

  variable script_folder

  if { $parentCell eq "" || $nameHier eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2092 -severity "ERROR" "create_hier_cell_microblaze_0_local_memory() - Empty argument(s)!"}
     return
  }

  # Get object for parentCell
  set parentObj [get_bd_cells $parentCell]
  if { $parentObj == "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2090 -severity "ERROR" "Unable to find parent cell <$parentCell>!"}
     return
  }

  # Make sure parentObj is hier blk
  set parentType [get_property TYPE $parentObj]
  if { $parentType ne "hier" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2091 -severity "ERROR" "Parent <$parentObj> has TYPE = <$parentType>. Expected to be <hier>."}
     return
  }

  # Save current instance; Restore later
  set oldCurInst [current_bd_instance .]

  # Set parent object as current
  current_bd_instance $parentObj

  # Create cell and set as current instance
  set hier_obj [create_bd_cell -type hier $nameHier]
  current_bd_instance $hier_obj

  # Create interface pins
  create_bd_intf_pin -mode MirroredMaster -vlnv xilinx.com:interface:lmb_rtl:1.0 DLMB

  create_bd_intf_pin -mode MirroredMaster -vlnv xilinx.com:interface:lmb_rtl:1.0 ILMB


  # Create pins
  create_bd_pin -dir I -type clk LMB_Clk
  create_bd_pin -dir I -type rst SYS_Rst

  # Create instance: dlmb_bram_if_cntlr, and set properties
  set dlmb_bram_if_cntlr [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_bram_if_cntlr:4.0 dlmb_bram_if_cntlr ]
  set_property -dict [ list \
   CONFIG.C_ECC {0} \
 ] $dlmb_bram_if_cntlr

  # Create instance: dlmb_v10, and set properties
  set dlmb_v10 [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_v10:3.0 dlmb_v10 ]

  # Create instance: ilmb_bram_if_cntlr, and set properties
  set ilmb_bram_if_cntlr [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_bram_if_cntlr:4.0 ilmb_bram_if_cntlr ]
  set_property -dict [ list \
   CONFIG.C_ECC {0} \
 ] $ilmb_bram_if_cntlr

  # Create instance: ilmb_v10, and set properties
  set ilmb_v10 [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_v10:3.0 ilmb_v10 ]

  # Create instance: lmb_bram, and set properties
  set lmb_bram [ create_bd_cell -type ip -vlnv xilinx.com:ip:blk_mem_gen:8.4 lmb_bram ]
  set_property -dict [ list \
   CONFIG.Memory_Type {True_Dual_Port_RAM} \
   CONFIG.use_bram_block {BRAM_Controller} \
 ] $lmb_bram

  # Create interface connections
  connect_bd_intf_net -intf_net microblaze_0_dlmb [get_bd_intf_pins DLMB] [get_bd_intf_pins dlmb_v10/LMB_M]
  connect_bd_intf_net -intf_net microblaze_0_dlmb_bus [get_bd_intf_pins dlmb_bram_if_cntlr/SLMB] [get_bd_intf_pins dlmb_v10/LMB_Sl_0]
  connect_bd_intf_net -intf_net microblaze_0_dlmb_cntlr [get_bd_intf_pins dlmb_bram_if_cntlr/BRAM_PORT] [get_bd_intf_pins lmb_bram/BRAM_PORTA]
  connect_bd_intf_net -intf_net microblaze_0_ilmb [get_bd_intf_pins ILMB] [get_bd_intf_pins ilmb_v10/LMB_M]
  connect_bd_intf_net -intf_net microblaze_0_ilmb_bus [get_bd_intf_pins ilmb_bram_if_cntlr/SLMB] [get_bd_intf_pins ilmb_v10/LMB_Sl_0]
  connect_bd_intf_net -intf_net microblaze_0_ilmb_cntlr [get_bd_intf_pins ilmb_bram_if_cntlr/BRAM_PORT] [get_bd_intf_pins lmb_bram/BRAM_PORTB]

  # Create port connections
  connect_bd_net -net SYS_Rst_1 [get_bd_pins SYS_Rst] [get_bd_pins dlmb_bram_if_cntlr/LMB_Rst] [get_bd_pins dlmb_v10/SYS_Rst] [get_bd_pins ilmb_bram_if_cntlr/LMB_Rst] [get_bd_pins ilmb_v10/SYS_Rst]
  connect_bd_net -net microblaze_0_Clk [get_bd_pins LMB_Clk] [get_bd_pins dlmb_bram_if_cntlr/LMB_Clk] [get_bd_pins dlmb_v10/LMB_Clk] [get_bd_pins ilmb_bram_if_cntlr/LMB_Clk] [get_bd_pins ilmb_v10/LMB_Clk]

  # Restore current instance
  current_bd_instance $oldCurInst
}
  variable script_folder

  if { $parentCell eq "" } {
     set parentCell [get_bd_cells /]
  }

  # Get object for parentCell
  set parentObj [get_bd_cells $parentCell]
  if { $parentObj == "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2090 -severity "ERROR" "Unable to find parent cell <$parentCell>!"}
     return
  }

  # Make sure parentObj is hier blk
  set parentType [get_property TYPE $parentObj]
  if { $parentType ne "hier" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2091 -severity "ERROR" "Parent <$parentObj> has TYPE = <$parentType>. Expected to be <hier>."}
     return
  }

  # Save current instance; Restore later
  set oldCurInst [current_bd_instance .]

  # Set parent object as current
  current_bd_instance $parentObj


  # Create interface ports

  # Create ports
  set CLK_O_0 [ create_bd_port -dir O -type clk CLK_O_0 ]
  set GPIO_EXT [ create_bd_port -dir I -from 31 -to 0 GPIO_EXT ]
  set RST_O_0 [ create_bd_port -dir O -type rst RST_O_0 ]
  set clk_in [ create_bd_port -dir I -type clk -freq_hz 100000000 clk_in ]
  set reset [ create_bd_port -dir I reset ]

  # Create instance: CLKBUF_0, and set properties
  set CLKBUF_0 [ create_bd_cell -type ip -vlnv user.org:user:CLKBUF:1.0 CLKBUF_0 ]

  # Create instance: StartupCtrl_0, and set properties
  set StartupCtrl_0 [ create_bd_cell -type ip -vlnv user.org:user:StartupCtrl:1.0 StartupCtrl_0 ]

  # Create instance: axi_gpio_0, and set properties
  set axi_gpio_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 axi_gpio_0 ]
  set_property -dict [ list \
   CONFIG.C_ALL_INPUTS {1} \
 ] $axi_gpio_0

  # Create instance: axi_hwicap_0, and set properties
  set axi_hwicap_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_hwicap:3.0 axi_hwicap_0 ]
  set_property -dict [ list \
   CONFIG.C_INCLUDE_STARTUP {1} \
   CONFIG.C_WRITE_FIFO_DEPTH {128} \
 ] $axi_hwicap_0

  # Create instance: axi_timer_0, and set properties
  set axi_timer_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_timer:2.0 axi_timer_0 ]

  # Create instance: clk_wiz_1, and set properties
  set clk_wiz_1 [ create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clk_wiz_1 ]
  set_property -dict [ list \
   CONFIG.CLKIN1_JITTER_PS {100.0} \
   CONFIG.CLKOUT1_JITTER {115.831} \
   CONFIG.CLKOUT1_PHASE_ERROR {87.180} \
   CONFIG.CLKOUT2_JITTER {115.831} \
   CONFIG.CLKOUT2_PHASE_ERROR {87.180} \
   CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {100.000} \
   CONFIG.CLKOUT2_USED {true} \
   CONFIG.CLK_IN1_BOARD_INTERFACE {Custom} \
   CONFIG.MMCM_CLKFBOUT_MULT_F {12.000} \
   CONFIG.MMCM_CLKIN1_PERIOD {10.000} \
   CONFIG.MMCM_CLKIN2_PERIOD {10.000} \
   CONFIG.MMCM_CLKOUT1_DIVIDE {12} \
   CONFIG.NUM_OUT_CLKS {2} \
   CONFIG.PRIM_IN_FREQ {100.000} \
   CONFIG.PRIM_SOURCE {Single_ended_clock_capable_pin} \
   CONFIG.RESET_BOARD_INTERFACE {reset} \
   CONFIG.USE_BOARD_FLOW {true} \
 ] $clk_wiz_1

  # Create instance: mdm_1, and set properties
  set mdm_1 [ create_bd_cell -type ip -vlnv xilinx.com:ip:mdm:3.2 mdm_1 ]
  set_property -dict [ list \
   CONFIG.C_ADDR_SIZE {32} \
   CONFIG.C_M_AXI_ADDR_WIDTH {32} \
   CONFIG.C_USE_UART {1} \
 ] $mdm_1

  # Create instance: microblaze_0, and set properties
  set microblaze_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:microblaze:11.0 microblaze_0 ]
  set_property -dict [ list \
   CONFIG.C_ADDR_TAG_BITS {0} \
   CONFIG.C_CACHE_BYTE_SIZE {8192} \
   CONFIG.C_DCACHE_ADDR_TAG {0} \
   CONFIG.C_DCACHE_BYTE_SIZE {8192} \
   CONFIG.C_DEBUG_ENABLED {1} \
   CONFIG.C_D_AXI {1} \
   CONFIG.C_D_LMB {1} \
   CONFIG.C_I_AXI {0} \
   CONFIG.C_I_LMB {1} \
   CONFIG.C_USE_DCACHE {0} \
   CONFIG.C_USE_ICACHE {0} \
 ] $microblaze_0

  # Create instance: microblaze_0_axi_intc, and set properties
  set microblaze_0_axi_intc [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_intc:4.1 microblaze_0_axi_intc ]
  set_property -dict [ list \
   CONFIG.C_HAS_FAST {1} \
 ] $microblaze_0_axi_intc

  # Create instance: microblaze_0_axi_periph, and set properties
  set microblaze_0_axi_periph [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 microblaze_0_axi_periph ]
  set_property -dict [ list \
   CONFIG.NUM_MI {7} \
   CONFIG.NUM_SI {3} \
 ] $microblaze_0_axi_periph

  # Create instance: microblaze_0_local_memory
  create_hier_cell_microblaze_0_local_memory [current_bd_instance .] microblaze_0_local_memory

  # Create instance: microblaze_0_xlconcat, and set properties
  set microblaze_0_xlconcat [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 microblaze_0_xlconcat ]

  # Create instance: rst_clk_wiz_1_100M, and set properties
  set rst_clk_wiz_1_100M [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_clk_wiz_1_100M ]
  set_property -dict [ list \
   CONFIG.RESET_BOARD_INTERFACE {reset} \
   CONFIG.USE_BOARD_FLOW {true} \
 ] $rst_clk_wiz_1_100M

  # Create interface connections
  connect_bd_intf_net -intf_net microblaze_0_axi_dp [get_bd_intf_pins microblaze_0/M_AXI_DP] [get_bd_intf_pins microblaze_0_axi_periph/S00_AXI]
  connect_bd_intf_net -intf_net microblaze_0_axi_periph_M01_AXI [get_bd_intf_pins mdm_1/S_AXI] [get_bd_intf_pins microblaze_0_axi_periph/M01_AXI]
  connect_bd_intf_net -intf_net microblaze_0_axi_periph_M02_AXI [get_bd_intf_pins axi_hwicap_0/S_AXI_LITE] [get_bd_intf_pins microblaze_0_axi_periph/M02_AXI]
  connect_bd_intf_net -intf_net microblaze_0_axi_periph_M03_AXI [get_bd_intf_pins axi_timer_0/S_AXI] [get_bd_intf_pins microblaze_0_axi_periph/M03_AXI]
  connect_bd_intf_net -intf_net microblaze_0_axi_periph_M04_AXI [get_bd_intf_pins CLKBUF_0/S00_AXI] [get_bd_intf_pins microblaze_0_axi_periph/M04_AXI]
  connect_bd_intf_net -intf_net microblaze_0_axi_periph_M05_AXI [get_bd_intf_pins axi_gpio_0/S_AXI] [get_bd_intf_pins microblaze_0_axi_periph/M05_AXI]
  connect_bd_intf_net -intf_net microblaze_0_axi_periph_M06_AXI [get_bd_intf_pins StartupCtrl_0/S00_AXI] [get_bd_intf_pins microblaze_0_axi_periph/M06_AXI]
  connect_bd_intf_net -intf_net microblaze_0_debug [get_bd_intf_pins mdm_1/MBDEBUG_0] [get_bd_intf_pins microblaze_0/DEBUG]
  connect_bd_intf_net -intf_net microblaze_0_dlmb_1 [get_bd_intf_pins microblaze_0/DLMB] [get_bd_intf_pins microblaze_0_local_memory/DLMB]
  connect_bd_intf_net -intf_net microblaze_0_ilmb_1 [get_bd_intf_pins microblaze_0/ILMB] [get_bd_intf_pins microblaze_0_local_memory/ILMB]
  connect_bd_intf_net -intf_net microblaze_0_intc_axi [get_bd_intf_pins microblaze_0_axi_intc/s_axi] [get_bd_intf_pins microblaze_0_axi_periph/M00_AXI]
  connect_bd_intf_net -intf_net microblaze_0_interrupt [get_bd_intf_pins microblaze_0/INTERRUPT] [get_bd_intf_pins microblaze_0_axi_intc/interrupt]

  # Create port connections
  connect_bd_net -net CLKBUF_0_CLK_O [get_bd_ports CLK_O_0] [get_bd_pins CLKBUF_0/CLK_O]
  connect_bd_net -net CLKBUF_0_RST_O [get_bd_ports RST_O_0] [get_bd_pins CLKBUF_0/RST_O]
  connect_bd_net -net GPIO_EXT_1 [get_bd_ports GPIO_EXT] [get_bd_pins axi_gpio_0/gpio_io_i]
  connect_bd_net -net axi_hwicap_0_ip2intc_irpt [get_bd_pins axi_hwicap_0/ip2intc_irpt] [get_bd_pins microblaze_0_xlconcat/In1]
  connect_bd_net -net axi_timer_0_pwm0 [get_bd_pins axi_timer_0/pwm0] [get_bd_pins microblaze_0_xlconcat/In0]
  connect_bd_net -net clk_in_1 [get_bd_ports clk_in] [get_bd_pins clk_wiz_1/clk_in1]
  connect_bd_net -net clk_wiz_1_clk_out2 [get_bd_pins CLKBUF_0/CLK_I] [get_bd_pins clk_wiz_1/clk_out2]
  connect_bd_net -net clk_wiz_1_locked [get_bd_pins clk_wiz_1/locked] [get_bd_pins rst_clk_wiz_1_100M/dcm_locked]
  connect_bd_net -net mdm_1_debug_sys_rst [get_bd_pins mdm_1/Debug_SYS_Rst] [get_bd_pins rst_clk_wiz_1_100M/mb_debug_sys_rst]
  connect_bd_net -net microblaze_0_Clk [get_bd_pins CLKBUF_0/s00_axi_aclk] [get_bd_pins StartupCtrl_0/s00_axi_aclk] [get_bd_pins axi_gpio_0/s_axi_aclk] [get_bd_pins axi_hwicap_0/icap_clk] [get_bd_pins axi_hwicap_0/s_axi_aclk] [get_bd_pins axi_timer_0/s_axi_aclk] [get_bd_pins clk_wiz_1/clk_out1] [get_bd_pins mdm_1/S_AXI_ACLK] [get_bd_pins microblaze_0/Clk] [get_bd_pins microblaze_0_axi_intc/processor_clk] [get_bd_pins microblaze_0_axi_intc/s_axi_aclk] [get_bd_pins microblaze_0_axi_periph/ACLK] [get_bd_pins microblaze_0_axi_periph/M00_ACLK] [get_bd_pins microblaze_0_axi_periph/M01_ACLK] [get_bd_pins microblaze_0_axi_periph/M02_ACLK] [get_bd_pins microblaze_0_axi_periph/M03_ACLK] [get_bd_pins microblaze_0_axi_periph/M04_ACLK] [get_bd_pins microblaze_0_axi_periph/M05_ACLK] [get_bd_pins microblaze_0_axi_periph/M06_ACLK] [get_bd_pins microblaze_0_axi_periph/S00_ACLK] [get_bd_pins microblaze_0_axi_periph/S01_ACLK] [get_bd_pins microblaze_0_axi_periph/S02_ACLK] [get_bd_pins microblaze_0_local_memory/LMB_Clk] [get_bd_pins rst_clk_wiz_1_100M/slowest_sync_clk]
  connect_bd_net -net microblaze_0_intr [get_bd_pins microblaze_0_axi_intc/intr] [get_bd_pins microblaze_0_xlconcat/dout]
  connect_bd_net -net reset_1 [get_bd_ports reset] [get_bd_pins clk_wiz_1/reset] [get_bd_pins rst_clk_wiz_1_100M/ext_reset_in]
  connect_bd_net -net rst_clk_wiz_1_100M_bus_struct_reset [get_bd_pins microblaze_0_local_memory/SYS_Rst] [get_bd_pins rst_clk_wiz_1_100M/bus_struct_reset]
  connect_bd_net -net rst_clk_wiz_1_100M_mb_reset [get_bd_pins microblaze_0/Reset] [get_bd_pins microblaze_0_axi_intc/processor_rst] [get_bd_pins rst_clk_wiz_1_100M/mb_reset]
  connect_bd_net -net rst_clk_wiz_1_100M_peripheral_aresetn [get_bd_pins CLKBUF_0/s00_axi_aresetn] [get_bd_pins StartupCtrl_0/s00_axi_aresetn] [get_bd_pins axi_gpio_0/s_axi_aresetn] [get_bd_pins axi_hwicap_0/s_axi_aresetn] [get_bd_pins axi_timer_0/s_axi_aresetn] [get_bd_pins mdm_1/S_AXI_ARESETN] [get_bd_pins microblaze_0_axi_intc/s_axi_aresetn] [get_bd_pins microblaze_0_axi_periph/ARESETN] [get_bd_pins microblaze_0_axi_periph/M00_ARESETN] [get_bd_pins microblaze_0_axi_periph/M01_ARESETN] [get_bd_pins microblaze_0_axi_periph/M02_ARESETN] [get_bd_pins microblaze_0_axi_periph/M03_ARESETN] [get_bd_pins microblaze_0_axi_periph/M04_ARESETN] [get_bd_pins microblaze_0_axi_periph/M05_ARESETN] [get_bd_pins microblaze_0_axi_periph/M06_ARESETN] [get_bd_pins microblaze_0_axi_periph/S00_ARESETN] [get_bd_pins microblaze_0_axi_periph/S01_ARESETN] [get_bd_pins microblaze_0_axi_periph/S02_ARESETN] [get_bd_pins rst_clk_wiz_1_100M/peripheral_aresetn]

  # Create address segments
  assign_bd_address -offset 0x44A00000 -range 0x00000100 -target_address_space [get_bd_addr_spaces microblaze_0/Data] [get_bd_addr_segs CLKBUF_0/S00_AXI/S00_AXI_reg] -force
  assign_bd_address -offset 0x44A10000 -range 0x00000100 -target_address_space [get_bd_addr_spaces microblaze_0/Data] [get_bd_addr_segs StartupCtrl_0/S00_AXI/S00_AXI_reg] -force
  assign_bd_address -offset 0x40000000 -range 0x00010000 -target_address_space [get_bd_addr_spaces microblaze_0/Data] [get_bd_addr_segs axi_gpio_0/S_AXI/Reg] -force
  assign_bd_address -offset 0x40200000 -range 0x00010000 -target_address_space [get_bd_addr_spaces microblaze_0/Data] [get_bd_addr_segs axi_hwicap_0/S_AXI_LITE/Reg] -force
  assign_bd_address -offset 0x41C00000 -range 0x00010000 -target_address_space [get_bd_addr_spaces microblaze_0/Data] [get_bd_addr_segs axi_timer_0/S_AXI/Reg] -force
  assign_bd_address -offset 0x00000000 -range 0x00040000 -target_address_space [get_bd_addr_spaces microblaze_0/Data] [get_bd_addr_segs microblaze_0_local_memory/dlmb_bram_if_cntlr/SLMB/Mem] -force
  assign_bd_address -offset 0x00000000 -range 0x00040000 -target_address_space [get_bd_addr_spaces microblaze_0/Instruction] [get_bd_addr_segs microblaze_0_local_memory/ilmb_bram_if_cntlr/SLMB/Mem] -force
  assign_bd_address -offset 0x41400000 -range 0x00001000 -target_address_space [get_bd_addr_spaces microblaze_0/Data] [get_bd_addr_segs mdm_1/S_AXI/Reg] -force
  assign_bd_address -offset 0x41200000 -range 0x00010000 -target_address_space [get_bd_addr_spaces microblaze_0/Data] [get_bd_addr_segs microblaze_0_axi_intc/S_AXI/Reg] -force

  # Perform GUI Layout
  regenerate_bd_layout -layout_string {
   "ActiveEmotionalView":"Default View",
   "Default View_ScaleFactor":"0.397452",
   "Default View_TopLeft":"-330,-20",
   "ExpandedHierarchyInLayout":"",
   "guistr":"# # String gsaved with Nlview 7.0r4  2019-12-20 bk=1.5203 VDI=41 GEI=36 GUI=JA:10.0 TLS
#  -string -flagsOSRD
preplace port CLK_O_0 -pg 1 -lvl 7 -x 2300 -y 1000 -defaultsOSRD
preplace port RST_O_0 -pg 1 -lvl 7 -x 2300 -y 1020 -defaultsOSRD
preplace port clk_in -pg 1 -lvl 0 -x -80 -y 1230 -defaultsOSRD
preplace port reset -pg 1 -lvl 0 -x -80 -y 1080 -defaultsOSRD
preplace portBus GPIO_EXT -pg 1 -lvl 0 -x -80 -y 1350 -defaultsOSRD
preplace inst StartupCtrl_0 -pg 1 -lvl 5 -x 1780 -y 1240 -defaultsOSRD
preplace inst axi_gpio_0 -pg 1 -lvl 1 -x 130 -y 1470 -defaultsOSRD
preplace inst axi_hwicap_0 -pg 1 -lvl 6 -x 2140 -y 520 -defaultsOSRD
preplace inst axi_timer_0 -pg 1 -lvl 6 -x 2140 -y 110 -defaultsOSRD
preplace inst clk_wiz_1 -pg 1 -lvl 1 -x 130 -y 1220 -defaultsOSRD
preplace inst mdm_1 -pg 1 -lvl 3 -x 890 -y 1070 -defaultsOSRD
preplace inst microblaze_0 -pg 1 -lvl 4 -x 1320 -y 840 -defaultsOSRD
preplace inst microblaze_0_axi_intc -pg 1 -lvl 3 -x 890 -y 870 -defaultsOSRD
preplace inst microblaze_0_axi_periph -pg 1 -lvl 5 -x 1780 -y 420 -defaultsOSRD
preplace inst microblaze_0_local_memory -pg 1 -lvl 5 -x 1780 -y 790 -defaultsOSRD
preplace inst microblaze_0_xlconcat -pg 1 -lvl 2 -x 500 -y 690 -defaultsOSRD
preplace inst rst_clk_wiz_1_100M -pg 1 -lvl 2 -x 500 -y 1160 -defaultsOSRD
preplace inst CLKBUF_0 -pg 1 -lvl 5 -x 1780 -y 1010 -defaultsOSRD
preplace netloc CLKBUF_0_CLK_O 1 5 2 N 1000 N
preplace netloc CLKBUF_0_RST_O 1 5 2 N 1020 N
preplace netloc GPIO_EXT_1 1 0 2 NJ 1350 300
preplace netloc axi_hwicap_0_ip2intc_irpt 1 1 6 280 -10 NJ -10 NJ -10 NJ -10 NJ -10 2280
preplace netloc axi_timer_0_pwm0 1 1 6 290 0 NJ 0 NJ 0 NJ 0 NJ 0 2270
preplace netloc clk_in_1 1 0 1 N 1230
preplace netloc clk_wiz_1_clk_out2 1 1 4 300 1060 680 1150 1070 1000 N
preplace netloc clk_wiz_1_locked 1 1 1 310 1200n
preplace netloc mdm_1_debug_sys_rst 1 1 3 320 1260 NJ 1260 1050
preplace netloc microblaze_0_Clk 1 0 6 -30 1140 280 1050 720 980 1050 930 1580 70 2010
preplace netloc microblaze_0_intr 1 2 1 700 690n
preplace netloc reset_1 1 0 2 -60 1130 290J
preplace netloc rst_clk_wiz_1_100M_bus_struct_reset 1 2 3 690J 750 NJ 750 1570
preplace netloc rst_clk_wiz_1_100M_mb_reset 1 2 2 700 990 1070
preplace netloc rst_clk_wiz_1_100M_peripheral_aresetn 1 0 6 -50 1040 N 1040 710 1160 NJ 1160 1590 80 1980
preplace netloc microblaze_0_axi_periph_M04_AXI 1 4 2 1620 110 1940
preplace netloc microblaze_0_axi_periph_M05_AXI 1 0 6 -40 90 NJ 90 NJ 90 NJ 90 NJ 90 1970
preplace netloc microblaze_0_axi_periph_M06_AXI 1 4 2 1630 120 1950
preplace netloc microblaze_0_debug 1 3 1 1060 830n
preplace netloc microblaze_0_dlmb_1 1 4 1 1560 760n
preplace netloc microblaze_0_ilmb_1 1 4 1 1610 780n
preplace netloc microblaze_0_intc_axi 1 2 4 740 100 NJ 100 NJ 100 1930
preplace netloc microblaze_0_interrupt 1 3 1 1040 810n
preplace netloc microblaze_0_axi_dp 1 4 1 1600 180n
preplace netloc microblaze_0_axi_periph_M01_AXI 1 2 4 730 60 NJ 60 NJ 60 1960
preplace netloc microblaze_0_axi_periph_M02_AXI 1 5 1 1990 400n
preplace netloc microblaze_0_axi_periph_M03_AXI 1 5 1 2000 60n
levelinfo -pg 1 -80 130 500 890 1320 1780 2140 2300
pagesize -pg 1 -db -bbox -sgen -250 -20 2420 1700
"
}

  # Restore current instance
  current_bd_instance $oldCurInst

  validate_bd_design
  save_bd_design
  close_bd_design $design_name 
}
# End of cr_bd_FFICTR()


cr_bd_FFICTR ""
set_property REGISTERED_WITH_MANAGER "1" [get_files FFICTR.bd ] 
set_property SYNTH_CHECKPOINT_MODE "Hierarchical" [get_files FFICTR.bd ] 

#read_xdc $SELENE_HARDWARE/FFI/floorplan.xdc
#set_property used_in_synthesis true [get_files $SELENE_HARDWARE/FFI/floorplan.xdc]
#set_property used_in_implementation true [get_files $SELENE_HARDWARE/FFI/floorplan.xdc]

cd $TOP_PATH
