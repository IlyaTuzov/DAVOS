----------------------------------------------------------------------------------
-- Company: 
-- Engineer: 
-- 
-- Create Date: 01.07.2019 12:57:25
-- Design Name: 
-- Module Name: top - Behavioral
-- Project Name: 
-- Target Devices: 
-- Tool Versions: 
-- Description: 
-- 
-- Dependencies: 
-- 
-- Revision:
-- Revision 0.01 - File Created
-- Additional Comments:
-- 
----------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx leaf cells in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity top is
    Port ( XIN : in STD_LOGIC_VECTOR (5 downto 0);
           XO : out STD_LOGIC);
end top;

architecture Behavioral of top is

component LUT6
  generic (
     INIT : bit_vector := X"0000000000000000"
  );
  port (
     O : out std_ulogic;
     I0 : in std_ulogic;
     I1 : in std_ulogic;
     I2 : in std_ulogic;
     I3 : in std_ulogic;
     I4 : in std_ulogic;
     I5 : in std_ulogic
  );
end component;

begin

iLUT: LUT6
    generic map(
      INIT => X"fffffffffffffffe"
    )
        port map (
      I0 => XIN(0),
      I1 => XIN(1),
      I2 => XIN(2),
      I3 => XIN(3),
      I4 => XIN(4),
      I5 => XIN(5),
      O => XO
    );

end Behavioral;
