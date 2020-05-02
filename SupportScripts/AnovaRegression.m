clear;
set(0,'DefaultFigureVisible','off');
%specify the type of generalized model: linear, interactions, quadratic, etc.
model_type = 'linear';
%model_type = 'interactions';
%specify input data tables and output folder
inpfile = #INPFILE;
resfolder = #RESFOLDER;
%adjust the set of factors and responce variables (in accordance with csv)
FullFactorSet = #FACTORLABELS;
ResponseVariableArray= #RESPONSEVARIABLELABELS;
%define distribution type for each variable: continuous or discrete
ResponceVarType = #RESPONSEVARIABLETYPES;
DistributionContinuous = {'normal', 'gamma'};
%DistributionContinuous = {'gamma'};
DistributionDiscrete = {'poisson'};
%significance theshold for ANOVA
treshold = double(1.0);
%Rsquared treshold for fitglm, if not met - stepwiseglm is executed
rsquared_treshold = double(0.9);



[buf, num_dist_cont] = size(DistributionContinuous);
[buf, num_dist_disc] = size(DistributionDiscrete);
[buf, Fnum] = size(ResponseVariableArray);
[buf, Xnum] = size(FullFactorSet);

    mkdir(resfolder);
   
    Tdata = readtable(inpfile);
    data = Tdata(:,horzcat(FullFactorSet, ResponseVariableArray));
    mkdir(strcat(resfolder,'ANOVA\'));
    data_desc = '';
    summary = '<Summary>';
    Models = {};
    for x = 1:Fnum
        T=Tdata(:,horzcat(FullFactorSet,ResponseVariableArray{x}));
        disp(ResponseVariableArray{x});
        XVectArr = {};
        for i = 1:Xnum
            XVectArr = [XVectArr, T.(i)];
        end
        [a1,a2,a3,a4]= anovan(T.(Xnum+1),XVectArr,'model','linear','varnames',FullFactorSet);
        writetable(cell2table(a2),strcat(resfolder,'ANOVA\\ANOVA_',ResponseVariableArray{x},'.csv'),'WriteRowNames',true);
        Factors = {};
        c = 1;
        for i = 2:(Xnum+1)
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

        if strcmp(ResponceVarType{x}, 'continuous')
            indx=1;
            for ds = 1:num_dist_cont                
				Mod = stepwiseglm(z_data,'constant','upper','linear','ResponseVar',ResponseVariableArray{x},'CategoricalVars',Factors,'Distribution',DistributionContinuous{ds}, 'PEnter',0.09999);
                if(ds == 1)
                    Models{x} = Mod;
                elseif(ds>1)
                   if(Mod.Rsquared.Ordinary >  Models{x}.Rsquared.Ordinary)
                       Models{x} = Mod;
                       indx = ds;
                   end
                end                    
            end        
            dist_lbl = strrep(DistributionContinuous{indx}, ' ', '');
            ident = strcat(ResponseVariableArray{x},'_',dist_lbl);
            fname = strcat('RegressionModel=(',ResponseVariableArray{x},')(',dist_lbl,').csv');
            resfile = strcat(resfolder,fname);
            writetable(Models{x}.Coefficients,resfile,'WriteRowNames',true);
            data_desc = strcat(data_desc, '\n\t\t<responce_variable name = "', ident,'"\t\tdistribution="',dist_lbl,'"\t\tfile="',resfile,'"\t\tvalue_treshold = "0.00000001" />' ); 
            summary = strcat(summary, '\n\n\t<Model \n\t\tVariable="', Models{x}.ResponseName,'"\n\t\tDistribution="', dist_lbl,'"\n\t\tSignificant_Factors="');
            for j=1:FactNum
                summary = [summary, Factors{j},' '];
            end
            summary = strcat(summary, '"\n\t\tDeviance="', num2str(Models{x}.Deviance),'"\n\t\tRsquared_Ordinary="', num2str(Models{x}.Rsquared.Ordinary),'"\n\t\tRsquared_Adjusted="',num2str(Models{x}.Rsquared.Adjusted),'"\n\t\tRsquared_LLR="',num2str(Models{x}.Rsquared.LLR), '"\n\t\tRsquared_Deviance="', num2str(Models{x}.Rsquared.Deviance),'"\n\t/>');            
        else
            indx=1;
            for ds = 1:num_dist_disc                
				Mod = stepwiseglm(z_data,'constant','upper','linear','ResponseVar',ResponseVariableArray{x},'CategoricalVars',Factors,'Distribution',DistributionDiscrete{ds}, 'PEnter',0.09999);
                if(ds == 1)
                    Models{x} = Mod;
                elseif(ds>1)
                   if(Mod.Rsquared.Ordinary >  Models{x}.Rsquared.Ordinary)
                       Models{x} = Mod;
                       indx = ds;
                   end
                end                    
            end        
            dist_lbl = strrep(DistributionDiscrete{indx}, ' ', '');
            ident = strcat(ResponseVariableArray{x},'_',dist_lbl);
            fname = strcat('RegressionModel=(',ResponseVariableArray{x},')(',dist_lbl,').csv');
            resfile = strcat(resfolder,fname);
            writetable(Models{x}.Coefficients,resfile,'WriteRowNames',true);
            data_desc = strcat(data_desc, '\n\t\t<responce_variable name = "', ident,'"\t\tdistribution="',dist_lbl,'"\t\tfile="',resfile,'"\t\tvalue_treshold = "0.00000001" />' ); 
            summary = strcat(summary, '\n\n\t<Model \n\t\tVariable="', Models{x}.ResponseName,'"\n\t\tDistribution="', dist_lbl,'"\n\t\tSignificant_Factors="');
            for j=1:FactNum
                summary = [summary, Factors{j},' '];
            end
            summary = strcat(summary, '"\n\t\tDeviance="', num2str(Models{x}.Deviance),'"\n\t\tRsquared_Ordinary="', num2str(Models{x}.Rsquared.Ordinary),'"\n\t\tRsquared_Adjusted="',num2str(Models{x}.Rsquared.Adjusted),'"\n\t\tRsquared_LLR="',num2str(Models{x}.Rsquared.LLR), '"\n\t\tRsquared_Deviance="', num2str(Models{x}.Rsquared.Deviance),'"\n\t/>');            
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

    fdesc = fopen(strcat(resfolder, 'Summary.xml'),'wt');
    summary = strcat(summary, '\n\n</Summary>');
    fprintf(fdesc, summary);
    fclose(fdesc);

set(0,'DefaultFigureVisible','on');

