


use std.textio.all;
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;
use IEEE.numeric_std.all;
use IEEE.math_real.all; -- for UNIFORM, TRUNC


	
	

entity testbench is
end entity testbench;

architecture arch of testbench is

--#Signals

-- Clock period definitions
   constant clock_period : time := 5.0 ns;
	
begin
--#Instance
			
	proc_clock : process 
	begin
--#Clock
	end process proc_clock;

	proc_reset : process 
	begin
--#Reset
	end process proc_reset;

	process		
--#Random_vector
		variable int_rand: integer;
		variable seed1, seed2: positive;
		variable rand: real;	
		variable pm: integer;
		
		procedure set_random_value(variable vect: inout std_logic_vector) is
			variable a: integer;
		begin
			pm := 2**16 - 1;
			a := vect'LENGTH / 16;
			if((vect'LENGTH mod 16) > 0) then
				a := a + 1;
			end if;
			for i in 1 to a loop
				UNIFORM(seed1, seed2, rand);
				int_rand := INTEGER(TRUNC(rand*real(pm)));		
				vect := std_logic_vector(unsigned(vect) sll 16);
				vect(15 downto 0) := std_logic_vector(to_unsigned(int_rand,16));
				end loop;
		end procedure set_random_value;	
	
	begin
		loop
--#Process
			
		end loop;
	end process;

end;
