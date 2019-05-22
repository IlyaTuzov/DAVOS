factors = #FACTORS;
categorical = #CATEGORICAL_INDEXES;
levels = #LEVELS;
inpfile = #INPFILENAME;
resfile = #RESFILENAME;
targetsize = #TARGETDESIGNSIZE;


rng(1);
Tdata = readtable(inpfile);
dCE=table2array(Tdata(:,horzcat(factors)));
dCE = bsxfun(@plus, dCE, 1);
[z1,z2] = size(dCE);
dCE_new = daugment(dCE, targetsize-z1, 'linear','categorical',categorical,'levels',levels, 'excludefun', @excludeitems);
dCE_norm = bsxfun(@plus, dCE_new, -1);
writetable(cell2table(num2cell(dCE_norm), 'VariableNames', factors), resfile, 'WriteRowNames', true);
