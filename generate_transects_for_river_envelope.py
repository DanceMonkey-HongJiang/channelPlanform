# -*- coding: utf-8 -*-
"""
Created on Wed Sep 27 20:45:09 2023

@author: Hong
"""
import arcpy
import numpy as np

if __name__ == '__main__':
    envelope = arcpy.GetParameterAsText(0)
    startPoint = arcpy.GetParameterAsText(1)
    Out_Space = arcpy.GetParameterAsText(2)

     
    arcpy.env.workspace = Out_Space
    arcpy.env.overwriteOutput = True
    arcpy.env.extent = arcpy.Describe(envelope).Extent
    arcpy.env.outputCoordinateSystem = arcpy.Describe(envelope).spatialReference  
    arcpy.env.overwriteOutput = True
    
    # Create empty list for interim datasets to be deleted at end of function
    dsets = []
    
    #### Centreline extraction and transects generalization
    arcpy.AddMessage("Generating transects")
    centerLine = "centerLine"
    arcpy.topographic.PolygonToCenterline(
        in_features = envelope, 
        out_feature_class = centerLine)
       
    centerLineSmooth = "centerLineSmooth"
    arcpy.cartography.SmoothLine(
        in_features = centerLine, 
        out_feature_class = centerLineSmooth, 
        algorithm = "PAEK", 
        tolerance = "500 Meters")
    
    transects = "transects_2"
    transects = arcpy.management.GenerateTransectsAlongLines(
        in_features = centerLineSmooth, 
        out_feature_class = transects, 
        interval = "1000 Meters", 
        transect_length = "2000 Meters")
    
    arcpy.management.AddField(transects, "Transect_Id","LONG", 9,"","","Transect_Id","NULLABLE")
    arcpy.management.CalculateField(transects, field="Transect_Id", expression="!OBJECTID!")
    arcpy.management.AddField(transects, "Distance","LONG", 9,"","","Distance","NULLABLE")
    arcpy.management.AddField(transects, "Distance_Max","LONG", 9,"","","Distance_Max","NULLABLE")
    
    centerLineEnds = arcpy.management.FeatureVerticesToPoints(
        in_features = centerLine, 
        point_location="BOTH_ENDS")
    
    arcpy.management.AddField(centerLineEnds, "End_Id","LONG", 9,"","","End_Id","NULLABLE")
    arcpy.management.CalculateField(centerLineEnds, field="End_Id", expression="!OBJECTID!")
    
    centerLineEnds = arcpy.analysis.Near(
        in_features = centerLineEnds, 
        near_features = [startPoint], 
        distance_unit = "Kilometers")
    
    fields = ('End_Id','NEAR_DIST')
    ends_tb = arcpy.da.TableToNumPyArray(centerLineEnds,fields)
    ends = np.sort(ends_tb, order = ['End_Id'])
    
    fields = ("Transect_Id")
    crosses_tb = arcpy.da.TableToNumPyArray(transects,fields)
    crosses = np.sort(crosses_tb, order = ['Transect_Id'])
       
    d = max(crosses['Transect_Id'][1:len(crosses)].tolist())
    arcpy.management.CalculateField(transects,"Distance_Max", d, "PYTHON")
    
    if ends[0][1] > ends[1][1]:
       arcpy.management.CalculateField(transects, field="Distance", expression="!Distance_Max!-!Transect_Id!+1") 
    else:
        arcpy.management.CalculateField(transects, field="Distance", expression="!Transect_Id!")
        
    arcpy.management.DeleteField(transects, drop_field=["Distance_Max"])
    
    dsets.extend((centerLine,centerLineSmooth,centerLineEnds))
    for dset in dsets:
        arcpy.management.Delete(dset)
 
