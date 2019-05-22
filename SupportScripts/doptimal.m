factors = #FACTORS;
categorical = #CATEGORICAL_INDEXES;
levels = #LEVELS;
filename = #FILENAME;

rng(1);
[buf, nfactors] = size(factors);
nruns = 100;
while 1 == 1
    try
        dCE = cordexch(nfactors,nruns,'linear','categorical',categorical,'levels',levels);
        break;
    catch Err
        nruns = nruns + 1;
    end
end

%dCE_norm = dCE;
for i = 1:size(dCE,1)
    for j=1:size(dCE,2)
        dCE_norm(i,j)=dCE(i,j)-1;
    end
end

writetable(cell2table(num2cell(dCE_norm), 'VariableNames', factors), filename, 'WriteRowNames', true);
