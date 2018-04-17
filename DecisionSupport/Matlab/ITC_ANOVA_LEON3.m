clear;
set(0,'DefaultFigureVisible','off');
%specify the type of generalized model: linear, interactions, quadratic, etc.
model_type = 'interactions';
%specify input data tables and output folder
inpfiles = {'LEON3_31_24_IV.csv'};
root_folder = 'C:\\LEON3_Interactions\\';
%adjust the set of factors and responce variables (in accordance with csv)
FullFactorSet = {'X01','X02','X03','X04','X05','X06','X07','X08','X09','X10','X11','X12','X13','X14','X15','X16','X17','X18','X19','X20','X21','X23','X24','X25','X27','X28','X29','X30','X31','X32','X33'};
ResponseVariableArray={'MAX_FREQUENCY','POWER_DYNAMIC','UTIL_FF','UTIL_LUT','UTIL_SLICE','UTIL_RAMB','UTIL_DSP'};
%define distribution type for each variable: continuous or discrete
ResponceVarTyte = {'continuous','continuous','discrete','discrete','discrete','discrete','discrete'};
DistributionContinuous = {'normal', 'gamma', 'inverse gaussian'};
DistributionDiscrete = {'poisson'};
%significance theshold for ANOVA
treshold = double(0.05);
%Rsquared treshold for fitglm, if not met - stepwiseglm is executed
rsquared_treshold = double(0.9);



[buf, num_dist_cont] = size(DistributionContinuous);
[buf, num_dist_disc] = size(DistributionDiscrete);
[buf, FileSetSize] = size(inpfiles);
[buf, Fnum] = size(ResponseVariableArray);
mkdir(root_folder);
for file_index = 1:FileSetSize
    current_fname =  inpfiles{1,file_index};
    resfolder = strcat(root_folder, strrep(current_fname, '.', '_'),'\\');
    mkdir(resfolder);
   
    Tdata = readtable(current_fname);
    data = Tdata(:,horzcat(FullFactorSet, ResponseVariableArray));
    mkdir(strcat(resfolder,'ANOVA\'));
    data_desc = '';
    summary = '<Summary>';
    Models = {};
    for x = 1:Fnum
        T=Tdata(:,horzcat(FullFactorSet,ResponseVariableArray{x}));
        disp(ResponseVariableArray{x});
        [a1,a2,a3,a4]= anovan(T.(32),{T.X01,T.X02,T.X03,T.X04,T.X05,T.X06,T.X07,T.X08,T.X09,T.X10,T.X11,T.X12,T.X13,T.X14,T.X15,T.X16,T.X17,T.X18,T.X19,T.X20,T.X21,T.X23,T.X24,T.X25,T.X27,T.X28,T.X29,T.X30,T.X31,T.X32,T.X33},'model','linear','varnames',FullFactorSet);
        writetable(cell2table(a2),strcat(resfolder,'ANOVA\\ANOVA_',ResponseVariableArray{x},'.csv'),'WriteRowNames',true);
        Factors = {};
        z_vect = {};
        c = 1;
        for i = 2:32 
            if( double(a2{i,7}) < treshold)
                s = char(a2{i,1});
                Factors{c} = s;
                c = c+1;
            end
        end
        disp( Factors );
        z_vect = Factors;
        [buf, FactNum] = size(Factors);
        z_vect{c} = ResponseVariableArray{x};
        z_data = Tdata(:,z_vect);

        if strcmp(ResponceVarTyte{x}, 'continuous')
            for ds = 1:num_dist_cont
                Models{x} = fitglm(z_data,model_type,'ResponseVar',ResponseVariableArray{x},'CategoricalVars',Factors,'Distribution',DistributionContinuous{ds});
    %            if(Models{x}.Rsquared.Adjusted < rsquared_treshold)
    %                Models{x} = stepwiseglm(z_data,'interactions','ResponseVar',ResponseVariableArray{x},'CategoricalVars',Factors,'Distribution',DistributionContinuous{ds});                
    %            end
                ident = strcat(ResponseVariableArray{x},'_',DistributionContinuous{ds});
                resfile = strcat(resfolder,ident,'.csv');
                writetable(Models{x}.Coefficients,resfile,'WriteRowNames',true);
                data_desc = strcat(data_desc, '\n\t\t<responce_variable name = "', ident,'"\t\tdistribution="',DistributionContinuous{ds},'"\t\tfile="',ident,'.csv','"\t\tvalue_treshold = "0.00000001" />' ); 
                summary = strcat(summary, '\n\n\t<Model \n\t\tVariable="', Models{x}.ResponseName,'"\n\t\tDistribution="', DistributionContinuous{ds},'"\n\t\tSignificant_Factors="');
                for j=1:FactNum
                    summary = [summary, Factors{j},' '];
                end
                summary = strcat(summary, '"\n\t\tDeviance="', num2str(Models{x}.Deviance),'"\n\t\tRsquared_Ordinary="', num2str(Models{x}.Rsquared.Ordinary),'"\n\t\tRsquared_Adjusted="',num2str(Models{x}.Rsquared.Adjusted),'"\n\t\tRsquared_LLR="',num2str(Models{x}.Rsquared.LLR), '"\n\t\tRsquared_Deviance="', num2str(Models{x}.Rsquared.Deviance),'"\n\t/>');
            end        
        else
            for ds = 1:num_dist_disc
                Models{x} = fitglm(z_data,model_type,'ResponseVar',ResponseVariableArray{x},'CategoricalVars',Factors,'Distribution',DistributionDiscrete{ds});
    %            if(Models{x}.Rsquared.Adjusted < rsquared_treshold)
    %                    Models{x} = stepwiseglm(z_data,'interactions','ResponseVar',ResponseVariableArray{x},'CategoricalVars',Factors,'Distribution',DistributionDiscrete{ds});
    %            end            
                ident = strcat(ResponseVariableArray{x},'_',DistributionDiscrete{ds});
                resfile = strcat(resfolder,ident,'.csv');
                writetable(Models{x}.Coefficients,resfile,'WriteRowNames',true);
                data_desc = strcat(data_desc, '\n\t\t<responce_variable name = "', ident,'"\t\tdistribution="',DistributionDiscrete{ds},'"\t\tfile="',ident,'.csv','"\t\tvalue_treshold = "0.00000001" />' );            
                summary = strcat(summary, '\n\n\t<Model \n\t\tVariable="', Models{x}.ResponseName,'"\n\t\tDistribution="', DistributionDiscrete{ds},'"\n\t\tSignificant_Factors="');
                for j=1:FactNum
                    summary = [summary, Factors{j},' '];
                end
                summary = strcat(summary, '"\n\t\tDeviance="', num2str(Models{x}.Deviance),'"\n\t\tRsquared_Ordinary="', num2str(Models{x}.Rsquared.Ordinary),'"\n\t\tRsquared_Adjusted="',num2str(Models{x}.Rsquared.Adjusted),'"\n\t\tRsquared_LLR="',num2str(Models{x}.Rsquared.LLR), '"\n\t\tRsquared_Deviance="', num2str(Models{x}.Rsquared.Deviance),'"\n\t/>');
            end        
        end

    end
    fdesc = fopen(strcat(resfolder, 'itc_config.xml'),'wt');
    fprintf(fdesc, strcat('<data>\n\t<models path="',resfolder,'" >',data_desc,'\n\t</models>\n\t<FactorialDesign FullFactorSet=" '));
    [buf, Fsize] = size(FullFactorSet);
    for j=1:Fsize
        fprintf(fdesc, FullFactorSet{j});
        if j<Fsize
            fprintf(fdesc, ',');
        end
    end
    fprintf(fdesc, '"/>\n</data>');
    fclose(fdesc);

    fdesc = fopen(strcat(resfolder, 'MatlabSummary.xml'),'wt');
    summary = strcat(summary, '\n\n</Summary>');
    fprintf(fdesc, summary);
    fclose(fdesc);

end
set(0,'DefaultFigureVisible','on');

