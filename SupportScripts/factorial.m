%matlab.exe -nosplash -nodesktop -minimize -r "cd C:\Users\ILYA\Documents\testmactlab; run ('factorial.m'); quit"
factors =  #FACTORS;
aliases = #ALIASES;
Resolution = #RESOLUTION;
filename = #FILENAME;

Ntrials = 3;
while 1 == 1
    try
        disp(['Trying ', num2str(Ntrials), ' items for resolution ', num2str(Resolution)]);
        generators = fracfactgen(factors, Ntrials, Resolution);
        break;
    catch Err
        Ntrials = Ntrials + 1;
    end  
end
generators = fracfactgen(factors, Ntrials+1, Resolution);
[dff, confounding] = fracfact(generators);
writetable(cell2table(num2cell(dff), 'VariableNames', aliases), filename, 'WriteRowNames', true);
fullsize = size(aliases);
fullsize = fullsize(2);
fractionsize = size(dff);
fractionsize = fullsize - log2(fractionsize(1));
disp(['resulting design: 2^(', num2str(fullsize), '-', num2str(fractionsize), ')_', num2str(Resolution)]);
