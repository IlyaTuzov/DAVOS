`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 31.10.2019 11:58:27
// Design Name: 
// Module Name: StartupCtrl
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////


module StartupCtrl(
    input plrest
    );
    
STARTUPE2  #(
    .PROG_USR("FALSE") // Activate program event security feature. Requires encrypted bitstreams.
)
STARTUPE2_inst
(
    .CFGCLK(), // 1-bit output: Configuration main clock output
    .CFGMCLK(), // 1-bit output: Configuration internal oscillator clock output
    .EOS(), // 1-bit output: Active high output signal indicating the End Of Startup.
    .PREQ(), // 1-bit output: PROGRAM request to fabric output
    .CLK(0), // 1-bit input: User start-up clock input
    .GSR(plrest), // 1-bit input: Global Set/Reset input (GSR cannot be used for the port name)
    .GTS(0), // 1-bit input: Global 3-state input (GTS cannot be used for the port name)
    .KEYCLEARB(1), // 1-bit input: Clear AES Decrypter Key input from Battery-Backed RAM (BBRAM)
    .PACK(1), // 1-bit input: PROGRAM acknowledge input
    .USRCCLKO(0), // 1-bit input: User CCLK input
    .USRCCLKTS(0), // 1-bit input: User CCLK 3-state enable input
    .USRDONEO(1), // 1-bit input: User DONE pin output control
    .USRDONETS(1) // 1-bit input: User DONE 3-state enable outpu
);    
    
    
endmodule
