`timescale 1ns / 1ps

module CLK_buf(
    input CLK_I,
    input RST_AXI,
    input Free_CLK_I,
    input [31:0] CLK_CTRL,
    input [7:0] RST_CTRL,
    input CLK_SEL,
    input RST_SEL,
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
    reg [31:0] CLK_down = 31'h0;
    //Count down reg for RST 
    reg [6:0] RST_down = 6'h0;
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
       

// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// Finate state machine CLK - BEGIN
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----

    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // State Encoding
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----   
    localparam [2:0]
        state_idle_clk      = 3'b001,
        state_init_clk      = 3'b010,
        state_counting_clk  = 3'b100;
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- 
    
            
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // State REG Declarations
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----          
    reg[2:0] state_reg_clk, state_next_clk;
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----   
    
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // Synchronous State - Transition always@ ( posedge Clock ) async RST block
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    always @(posedge CLK_I, negedge RST_AXI)
    begin
        if(~RST_AXI)
            state_reg_clk <= state_idle_clk;
        else
            state_reg_clk <= state_next_clk;
    end
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // Conditional State - Transition always@ ( * ) block
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    always @*
    begin : FSM_clk
        state_next_clk = state_reg_clk;
        
        case(state_reg_clk)
            state_idle_clk:
            begin
                if(CLK_SEL)begin
                    state_next_clk = state_init_clk; end
            end
            state_init_clk:
            begin
                if(~CLK_SEL)begin
                    state_next_clk = state_counting_clk; end
            end
            state_counting_clk:
            begin
                if(CLK_down == 1)begin
                    state_next_clk = state_idle_clk; end
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
    wire CNT_CLK, INIT_CLK, IDLE_CLK;
    
    assign IDLE_CLK = (state_reg_clk == state_idle_clk);
    assign INIT_CLK = (state_reg_clk == state_init_clk);
    assign CNT_CLK = (state_reg_clk == state_counting_clk);
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// FSM CLK- END
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----  

// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// Finate state machine RST - BEGIN
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----

    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // State Encoding
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----   
    localparam [2:0]
        state_idle_rst      = 3'b001,
        state_init_rst      = 3'b010,
        state_counting_rst  = 3'b100;
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- 
    
            
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // State REG Declarations
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----          
    reg[2:0] state_reg_rst, state_next_rst;
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----   
    
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // Synchronous State - Transition always@ ( posedge Clock ) async RST block
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    always @(posedge CLK_I, negedge RST_AXI)
    begin
        if(~RST_AXI)
            state_reg_rst <= state_idle_rst;
        else
            state_reg_rst <= state_next_rst;
    end
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    // Conditional State - Transition always@ ( * ) block
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    always @*
    begin : FSM_RST
        state_next_rst = state_reg_rst;
        
        case(state_reg_rst)
            state_idle_rst:
            begin
                if(RST_SEL)begin
                    state_next_rst = state_init_rst; end
            end
            state_init_rst:
            begin
                if(~RST_SEL)begin
                    state_next_rst = state_counting_rst; end
            end
            state_counting_rst:
            begin
                if(RST_down == 1)begin
                    state_next_rst = state_idle_rst; end
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
    wire CNT_RST, INIT_RST, IDLE_RST;
    
    assign IDLE_RST = (state_reg_rst == state_idle_rst);
    assign INIT_RST = (state_reg_rst == state_init_rst);
    assign CNT_RST = (state_reg_rst == state_counting_rst) & (RST_down > 0);
    // --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
    
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// FSM RST- END
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----  


// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- -----
// Down counters
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- 
    //Down counter for BUFGCE Enable CLK
    always @(posedge CLK_I)
    begin
        if (INIT_CLK)
            CLK_down <= CLK_CTRL;
        else if (CNT_CLK)
            CLK_down <= CLK_down - 1;
        else if (IDLE_CLK)
            CLK_down <= 32'h0;
        else
            CLK_down <= CLK_down;
    end
    
    //Down counter for RST_O
    always @(posedge CLK_I) begin
        if(INIT_RST) 
            RST_down <= RST_CTRL[6:0];  
        else if (CNT_RST)
            RST_down <= RST_down -1;
        else if (IDLE_RST)
            RST_down <= 6'h0;
        else
            RST_down <= RST_down;
    end
// --- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- ---- ---- ----- 
    
    
    //CE high when down count over 0 and not inicialising 
    assign CE = (CLK_down > 0) && !CLK_SEL;
    
    //RST_O high when down count over 0 and active high  
    assign RST_active_low = RST_CTRL[7];
    assign RST_O = (RST_down > 0) ^ RST_active_low && !RST_SEL;
    
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
    
