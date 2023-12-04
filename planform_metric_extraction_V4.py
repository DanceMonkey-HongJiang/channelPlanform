# -*- coding: utf-8 -*-
"""
Created on Fri Dec  1 12:48:21 2023

@author: Hong
"""


import arcpy  
import numpy as np
import pandas as pd
from rpy2.robjects.packages import importr

if __name__ == '__main__': 
    
    envelope = arcpy.GetParameterAsText(0)
    transects = arcpy.GetParameterAsText(1)
    input_space = arcpy.GetParameterAsText(2)
    
    arcpy.env.workspace = input_space
    arcpy.env.overwriteOutput = True
    arcpy.env.extent = arcpy.Describe(envelope).Extent
    arcpy.env.outputCoordinateSystem = arcpy.Describe(envelope).spatialReference  
    arcpy.env.overwriteOutput = True
    
    # Create empty list for interim datasets to be deleted at end of function
    dsets = []
    
    years = ['1987','1989','1992','1994','1996','1999','2002','2005','2009','2013','2014','2016','2018']
    
    for year in years:
    
        wetChannelBoundary = input_space + "/wetChannelBoundary_" + year
        activeChannel = input_space + "/activeChannel_" + year
        channelUnit = input_space + "/channelUnit_" + year
        
        planMetric = "planMetric" + "_" + year
        
        planMetric = arcpy.management.CopyFeatures(transects, planMetric)
        
        wetChannelTransects =  "wetChannelTransect"
        wetChannelTransects =  arcpy.analysis.PairwiseIntersect(
            in_features=[planMetric, wetChannelBoundary], 
            out_feature_class=wetChannelTransects)
        fieldname = "Ww" 
        arcpy.management.AddField(wetChannelTransects, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
        #arcpy.management.CalculateField(wetChannelTransects, field= fieldname, expression="!Shape_Length!")
        arcpy.management.CalculateGeometryAttributes(wetChannelTransects, [[fieldname, "LENGTH"]], "METERS")
        
        planMetric= arcpy.management.JoinField(
            in_data = planMetric, 
            in_field= "Distance", 
            join_table = wetChannelTransects, 
            join_field="Distance", 
            fields= [fieldname])
        
        activeChannelTransects = "activeChannelTransect"
        arcpy.analysis.PairwiseIntersect(in_features=[planMetric, activeChannel], 
                                         out_feature_class=activeChannelTransects)
        fieldname = "Aw" 
        arcpy.management.AddField(activeChannelTransects,fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
        #arcpy.management.CalculateField(activeChannelTransects, field=fieldname, expression="!Shape_Length!")
        arcpy.management.CalculateGeometryAttributes(activeChannelTransects, [[fieldname, "LENGTH"]], "METERS")
        
        planMetric = arcpy.management.JoinField(
            in_data = planMetric, 
            in_field = "Distance", 
            join_table = activeChannelTransects, 
            join_field = "Distance", 
            fields = [fieldname])
        
        channelUnitTransect = "channelUnitTransect"
        channelUnitTransect = arcpy.analysis.SpatialJoin(
            target_features = planMetric, 
            join_features = channelUnit, 
            out_feature_class = channelUnitTransect, 
            join_operation ="JOIN_ONE_TO_MANY", 
            field_mapping = "", 
            search_radius = "0.01 Meters")
        
        summTableUnit = "summTableUnit"
        summTableUnit = arcpy.analysis.Statistics(
            in_table = channelUnitTransect, 
            out_table = summTableUnit, 
            statistics_fields = [["Unit_Type", "COUNT"]], 
            case_field = ["Distance", "Unit_Type"])
    
        summTable_BI_Active = "summTable_BI_Active"
        summTable_BI_Active = arcpy.analysis.TableSelect(
            in_table = summTableUnit , 
            out_table = summTable_BI_Active, 
            where_clause = "Unit_Type IN ('MB')")
        
        planMetric = arcpy.management.JoinField(
            in_data = planMetric, 
            in_field= "Distance", 
            join_table = summTable_BI_Active, 
            join_field = "Distance", 
            fields = ["COUNT_Unit_Type"])
        
        fieldname = "Bi" 
        arcpy.management.AddField(planMetric, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
        arcpy.management.CalculateField(planMetric, field=fieldname, 
                                        expression="!COUNT_Unit_Type!+1 if !COUNT_Unit_Type! is not None else 1")
        arcpy.management.DeleteField(planMetric, ["COUNT_Unit_Type"])
        
        summTable_AI = "summTable_AI"
        summTable_AI = arcpy.analysis.TableSelect(
            in_table = summTableUnit, 
            out_table = summTable_AI, 
            where_clause = "Unit_Type IN ('IS')")
        
        planMetric= arcpy.management.JoinField(
            in_data = planMetric, 
            in_field= "Distance", 
            join_table = summTable_AI, 
            join_field = "Distance", 
            fields = ["COUNT_Unit_Type"])
        
        fieldname = "Ai"
        arcpy.management.AddField(planMetric, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
        arcpy.management.CalculateField(planMetric, field=fieldname, 
                                        expression="!COUNT_Unit_Type!+1 if !COUNT_Unit_Type! is not None else 1")
        arcpy.management.DeleteField(planMetric, ["COUNT_Unit_Type"])
        
        dsets.extend((wetChannelTransects, activeChannelTransects,channelUnitTransect, 
                      summTableUnit, summTable_BI_Active,summTable_AI))
        for dset in dsets:
            arcpy.management.Delete(dset)
        
        arcpy.management.AddField(planMetric, "Break", "LONG", 9,"","","Break","NULLABLE")
        arcpy.management.AddField(planMetric, "Label", "LONG", 9,"","","Label","NULLABLE")
        arcpy.management.AddField(planMetric, "Reach", "LONG", 9,"","","Reach","NULLABLE")
        # Set the default value of "Breaking" as 0, indicating all are not breaking points
        arcpy.management.CalculateField(planMetric, "Break", "0")
        arcpy.management.CalculateField(planMetric, "Label", "0")
        arcpy.management.CalculateField(planMetric, "Reach", "0")
            
        fields = ('Distance','Aw','Ww','Bi','Ai','Break','Reach','Label')
        plan_arr = arcpy.da.TableToNumPyArray(planMetric, fields)
        plan_st_arr = np.sort(plan_arr, order = ['Distance'])
        plan_df = pd.DataFrame(plan_st_arr)
        plan_df['AW'] = plan_df['Aw'].rolling(11, center = True).mean()
        plan_df['WW'] = plan_df['Ww'].rolling(11, center = True).mean()
        plan_df['BI'] = plan_df['Bi'].rolling(11, center = True).mean()
        plan_df['AI'] = plan_df['Ai'].rolling(11, center = True).mean()
        
        plan_seg = plan_df[['Ai','Bi','AW','WW']].dropna().astype(np.float64)
        
        for column in plan_seg.columns: 
            plan_seg[column] = (plan_seg[column] - plan_seg[column].min()) / (plan_seg[column].max() - plan_seg[column].min())     
    
        plan_seg_m = np.asmatrix(plan_seg)
     
        ecp = importr('ecp')
        seg = ecp.e_divisive(X=plan_seg_m, sig_lvl=0.01,R=599,min_size=11,alpha=1)
        
        seg_id = (seg.rx('estimates')[0].astype(int)+4).tolist()[1:-1]
        
        label_id = (seg.rx('estimates')[0].astype(int)+6).tolist()[1:-1]
        
        for i in seg_id:
           plan_st_arr[i][5] = 1
        
        plan_st_arr[2][7] = 1  
        
        for l in label_id:
           plan_st_arr[l][7] = 1    
           
        reach_id = np.concatenate((np.repeat(np.array([1]), 5),seg.rx('cluster')[0].astype(int),np.repeat(seg.rx('k.hat')[0].astype(int),5)))
        
        j = 0
        while j < len(reach_id):
            plan_st_arr[j][6] = reach_id[j]
            j = j+1
       
        arcpy.da.ExtendTable(planMetric, "Distance",plan_st_arr,"Distance", append_only = False)
    
        planMetric_break = "planMetric_break"
        planMetric_break = arcpy.analysis.Select(
            in_features = planMetric, 
            out_feature_class = planMetric_break, 
            where_clause = "Break = 1")
    
        envelope_reach = "envelope_reach "
        envelope_reach  = arcpy.management.FeatureToPolygon(
            in_features = [planMetric_break, envelope], 
            out_feature_class = envelope_reach)
    
        planMetric_label = "planMetric_label"
        planMetric_label = arcpy.analysis.Select(
            in_features = planMetric, 
            out_feature_class = planMetric_label, 
            where_clause = "Label = 1")
        
        envelope_reach_label = "envelope_reach_label" + "_" +year
        envelope_reach_label = arcpy.analysis.SpatialJoin(
            target_features = envelope_reach, 
            join_features = planMetric_label, 
            out_feature_class = envelope_reach_label, 
            field_mapping="")
    
        channelUnitReach = "channelUnitReach" + "_" +year
        channelUnitReach = arcpy.analysis.Intersect(
            in_features =[[envelope_reach_label, ""], [channelUnit, ""]], 
            out_feature_class = channelUnitReach)
        
        dsets.extend((planMetric_break, envelope_reach, planMetric_label))
        for dset in dsets:
            arcpy.management.Delete(dset)