function b = excludeitems(S)
    filename = #INPFILENAME;
    b=[];
    if exist(filename, 'file') == 2
        Excl = table2array(readtable(filename));   
		Excl = bsxfun(@plus, Excl, 1); 
        [x1, x2] = size(Excl);
        [z1, z2] = size(S);
        for row = 1:z1
            for i = 1:x1
                if S(row,:)== Excl(i,:)
                    b = [b row];
                    break
                end                
            end
        end
    end    
        
        
