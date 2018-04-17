clear;
%specify the data table and output folder
%inpfiles = {'B_01_Join.csv', 'B_02_Join.csv','B_03_Join.csv', 'B_04_Join.csv', 'B_05_Join.csv', 'B_06_Join.csv', 'B_07_Join.csv', 'B_08_Join.csv', 'B_09_Join.csv', 'B_10_Join.csv', 'B_11_Join.csv', 'B_12_Join.csv', 'B_13_Join.csv', 'B_14_Join.csv', 'B_15_Join.csv', 'B_17_Join.csv', 'B_20_Join.csv', 'B_21_Join.csv', 'B_22_Join.csv'};
inpfiles = {'TMR_MC8051_31_24_IV.csv'};
resfolder = 'C:\\Models\\ESTIMATORS\\';
mkdir(resfolder);
[buf, NFiles] = size(inpfiles);

for M = 1:NFiles;
    Tdata = readtable(inpfiles{1,M});
    %adjust the set of factors and responce variables (in accordance with csv)
    %FullFactorSet = {'X01','X02','X03','X04','X05','X06','X07','X08','X09','X10','X11','X12','X13','X14','X15','X16','X17','X18','X19','X20','X21','X22','X23','X24','X25','X26','X27','X28','X29','X30','X31','X32','X33'};
    FullFactorSet = {'X01','X02','X03','X04','X05','X06','X07','X08','X09','X10','X11','X12','X13','X14','X15','X16','X17','X18','X19','X20','X21','X23','X24','X25','X27','X28','X29','X30','X31','X32','X33'};
    ResponseVariableArray={'MAX_FREQUENCY','POWER_DYNAMIC','UTIL_FF','UTIL_LUT','UTIL_SLICE','UTIL_RAMB','UTIL_DSP'};
    data = Tdata(:,horzcat(FullFactorSet, ResponseVariableArray));
    [Nconfig,buf] = size(data); %#ok<*ASGLU>
    [buf,Nfactors] = size(FullFactorSet);
    [buf, NVar] = size(ResponseVariableArray);
    ResCell = {Nfactors, NVar};
    for i=1:Nfactors
       for j=1:NVar
          res = double(0);
          for c=1:Nconfig
             if(data{c,i} == 1)
                 res = res + data{c,j+Nfactors}/(Nconfig/2);
             elseif(data{c,i} == 0)
                 res = res - data{c,j+Nfactors}/(Nconfig/2);
             end
          end
          ResCell{i,j} = res;
       end
    end
    ResTable = cell2table(ResCell, 'VariableNames', ResponseVariableArray, 'RowNames',FullFactorSet);
    disp(ResTable);
    writetable(ResTable, strcat(resfolder,'Estimators_',inpfiles{1,M}), 'WriteRowNames',true);
end
