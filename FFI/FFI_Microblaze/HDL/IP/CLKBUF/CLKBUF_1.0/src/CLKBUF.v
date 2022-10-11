`timescale 1ns / 1ps

module CLK_buf(
    input CLK_I,
    input RST_AXI,
    input START,
    input Free_CLK_I,
    input [31:0] CLK_CTRL,
    input [7:0] RST_CTRL,
    output CE_O,
    output CLK_O,
    output RST_O
    );
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// Internal wires and REGs
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    //BUFGCE Enable    
    wire CE;
    //Active type for RST_O
    wire RST_active_low;
    //Count down reg for CLK 
    reg [31:0] CNT_down = 31'h0;
    //Count down reg for RST 
    reg [6:0] RST_down = 6'h0;
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
    wire CNT_CLK, CNT_RST, INIT_CLK, INIT_RST, IDLE;
    
    assign IDLE = (state_reg == state_idle);
    assign INIT_CLK = (state_reg == state_init);
    assign INIT_RST = (state_reg == state_init);
    assign CNT_CLK = (state_reg == state_counting);
    assign CNT_RST = (state_reg == state_counting) & (RST_down > 0);
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
        if (INIT_CLK)
            CNT_down <= CLK_CTRL;
        else if (CNT_CLK)
            CNT_down <= CNT_down - 1;
        else if (IDLE)
            CNT_down <= 32'h0;
        else
            CNT_down <= CNT_down;
    end
    
    //Down counter for RST_O
    always @(posedge CLK_I) begin
        if(INIT_RST) 
            RST_down <= RST_CTRL[6:0];  
        else if (CNT_RST)
            RST_down <= RST_down -1;
        else if (IDLE)
            RST_down <= 6'h0;
        else
            RST_down <= RST_down;
    end
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- 
    
    
    //CE high when down count over 0 and not inicialising 
    assign CE = (CNT_down > 0) && !START;
    
    //RST_O high when down count over 0 and active high  
    assign RST_active_low = RST_CTRL[7];
    assign RST_O = (RST_down > 0) ^ RST_active_low;
    
    //Flag
    assign CE_O = CE;

    //Instanciation of clock buffer element
    BUFGCE clkbuf(
    .CE(CE | Free_CLK_I),
    .I(CLK_I),
    .O(CLK_O)
    );
        
endmodule


    
//    //Domain crossing register at input
//    always @(posedge CLK_I)
//        begin
//        RST <= RST_I;
//        Free_CLK <= Free_CLK_I;
//    end
    
