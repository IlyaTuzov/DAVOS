`timescale 1ns / 1ps

module StartupCtrl(
    input CLK_I,
    input RST_AXI,
    input START,
    input [31:0] INIT_I,
    output PLREST_O
    );

// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// Internal wires and REGs
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    //Count down reg 
    reg [31:0] CNT_down = 31'h0;
    //Signal to activate global set reset GSR
    wire  plrest;
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
       

// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// Finate state machine - BEGIN
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----

    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // State Encoding
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----   
    localparam [2:0]
        state_idle      = 3'b001,
        state_init      = 3'b010,
        state_counting  = 3'b100;
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- 
    
            
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // State REG Declarations
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----          
    reg[2:0] state_reg, state_next;
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----   
    
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // Synchronous State - Transition always@ ( posedge Clock ) async RST block
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    always @(posedge CLK_I, negedge RST_AXI)
    begin
        if(~RST_AXI)
            state_reg <= state_idle;
        else
            state_reg <= state_next;
    end
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // Conditional State - Transition always@ ( * ) block
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    always @*
    begin : FSM
        state_next = state_reg;
        
        case(state_reg)
            state_idle:
            begin
                if(START)begin
                    state_next = state_init; end
            end
            state_init:
            begin
                if(~START)begin
                    state_next = state_counting; end
            end
            state_counting:
            begin
                if(CNT_down == 1)begin
                    state_next = state_idle; end
            end
            default:
            begin
                
            end
        endcase               
    end
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // FSM Outputs
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    wire CNT, INIT, IDLE;
    
    assign IDLE = (state_reg == state_idle);
    assign INIT = (state_reg == state_init);
    assign CNT = (state_reg == state_counting) && (CNT_down > 0);
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// FSM - END
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----  


// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// Down counters
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- 
    //Down counter for BUFGCE Enable CLK
    always @(posedge CLK_I)
    begin
        if (INIT)
            CNT_down <= INIT_I;
        else if (CNT)
            CNT_down <= CNT_down - 1;
        else if (IDLE)
            CNT_down <= 32'h0;
        else
            CNT_down <= CNT_down;
    end
    
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- 
    
    
    //plrest high when down count over 0 and not inicialising 
    assign plrest = CNT;
    
    //Flag for plrest
    assign PLREST_O = plrest;
    

//Instanciation of clock buffer element    
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
