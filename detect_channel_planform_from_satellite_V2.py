# -*- coding: utf-8 -*-
"""
Created on Wed Sep 27 11:45:15 2023

@author: Hong
"""

import arcpy
import os

if __name__ == '__main__':
    
    image = arcpy.GetParameterAsText(0)
    envelope = arcpy.GetParameterAsText(1)
    transects = arcpy.GetParameterAsText(2)
    Out_Space = arcpy.GetParameterAsText(3)

    arcpy.env.workspace = Out_Space
    arcpy.env.overwriteOutput = True
    arcpy.env.extent = arcpy.Describe(envelope).Extent
    arcpy.env.outputCoordinateSystem = arcpy.Describe(envelope).spatialReference  
    arcpy.env.overwriteOutput = True
    
    # Create empty list for interim datasets to be deleted at end of function
    dsets = []
    
    #### Land cover classification, 0: water; 1: sand; 2: vegetation
    arcpy.AddMessage("Classifying land cover")
    year = os.path.splitext(os.path.basename(image))[0][3:7]
    ndvi = arcpy.sa.NDVI(image,4,3)
    mndwi = arcpy.sa.NDWI(image,5,2)
    reclassNdvi = arcpy.sa.Reclassify(ndvi, "VALUE", "-1 0.040000 1;0.040000 1 2", "NODATA")
    reclassMndwi = arcpy.sa.Reclassify(mndwi, "VALUE", "-1 0 1;0 1 0", "NODATA")
    landCover = reclassNdvi * reclassMndwi
    landClassRas = arcpy.sa.ExtractByMask(
        landCover, 
        envelope, 
        "INSIDE", 
        "")
    landClassFea = "LandClassFea" +  "_" + year 
    arcpy.conversion.RasterToPolygon(
        in_raster = landClassRas, 
        out_polygon_features = landClassFea, 
        create_multipart_features="SINGLE_OUTER_PART")
    arcpy.management.AlterField(landClassFea,"gridcode", "Class", "Class")
    
    fieldsList = []
    keep = ["Class","Shape_Area"]
    fieldObjList = arcpy.ListFields(landClassFea)
    for field in fieldObjList:
        if (not field.name in keep) and (not field.required):
            fieldsList.append(field.name)
    arcpy.management.DeleteField(landClassFea, fieldsList)
    
    
    #### Wet channel boundary extraction 
    arcpy.AddMessage("Extracting wet channel")
    water = "water"
    water = arcpy.analysis.Select(
        in_features = landClassFea, 
        out_feature_class= water, 
        where_clause="Class = 0")
    
    waterBuffer = "waterBuffer"
    waterBuffer = arcpy.analysis.Buffer(
        in_features = water, 
        out_feature_class = waterBuffer, 
        buffer_distance_or_field = "20 Meters", 
        line_end_type ="FLAT", 
        dissolve_option="NONE", 
        method="GEODESIC")
    
    waterBufferDissolve = "waterBufferDissolve" 
    waterBufferDissolve = arcpy.gapro.DissolveBoundaries(
        input_layer = waterBuffer, 
        out_feature_class = waterBufferDissolve)

    waterContinue = "waterContinue"
    waterContinue  = arcpy.analysis.Select(
        in_features = waterBufferDissolve , 
        out_feature_class= water, 
        where_clause="Shape_Area >= 1000000")
    
    waterContinueBuffer = "waterContinueBuffer"
    waterContinueBuffer = arcpy.analysis.Buffer(
        in_features = waterContinue, 
        out_feature_class = waterContinueBuffer, 
        buffer_distance_or_field = "20 Meters", 
        line_end_type ="FLAT", 
        dissolve_option="ALL", 
        method="GEODESIC")
    
    waterContinueFilled = "waterContinueFilled"
    waterContinueFilled  = arcpy.management.EliminatePolygonPart(
        in_features = waterContinueBuffer, 
        out_feature_class = waterContinue, 
        condition = "PERCENT", 
        part_area_percent = 99, 
        part_option = "CONTAINED_ONLY")

    wetChannel = "wetChannel" +  "_" + year
    wetChannel  = arcpy.analysis.Buffer(
        in_features = waterContinueFilled , 
        out_feature_class = wetChannel , 
        buffer_distance_or_field = "-40 Meters", 
        line_end_type ="FLAT", 
        dissolve_option ="ALL", 
        method="GEODESIC")
    
    dsets.extend((water,waterBuffer, waterBufferDissolve,waterContinue,
                  waterContinueBuffer,waterContinueFilled))
    # Delete interim datasets in workspace  
    for dset in dsets:
        arcpy.management.Delete(dset)
     
    #### Geomorphic unit extraction and classification
    arcpy.AddMessage("Extracting land outside out wet channel")
    land = "land"
    land = arcpy.analysis.Select(
        in_features = landClassFea, 
        out_feature_class = land, 
        where_clause="Class <> 0")
    
    landOutWater = "landOutWater"
    arcpy.analysis.Erase(
        in_features=land, 
        erase_features=wetChannel, 
        out_feature_class=landOutWater)

    sandOutWater = "sandOutWater"
    arcpy.analysis.Select(
        in_features = landOutWater, 
        out_feature_class = sandOutWater, 
        where_clause = "Class = 1")

    sandBarOutWater = "sandBarOutWater"
    arcpy.gapro.DissolveBoundaries(
        input_layer = sandOutWater, 
        out_feature_class = sandBarOutWater)
    
    arcpy.AddMessage("Combining side bar with wet channel")
    activeChannelPotential = "activeChannelPotential "
    activeChannelPotential = arcpy.management.Merge(
        inputs = [sandBarOutWater, wetChannel], 
        output = activeChannelPotential,
        field_mappings = "")

    activeChannelPotentialDissolve = "activeChannelPotentialDissolve"
    activeChannelPotentialDissolve = arcpy.gapro.DissolveBoundaries(
        input_layer = activeChannelPotential, 
        out_feature_class = activeChannelPotentialDissolve)

    activeChannelPotentialArea = "activeChannelPotentialArea"
    activeChannelPotentialArea = arcpy.analysis.Select(
        in_features = activeChannelPotentialDissolve, 
        out_feature_class = activeChannelPotentialArea, 
        where_clause="Shape_area >= 1000000")

    activeChannelPotentialAreaBuffer = "activeChannelPotentialAreaBuffer"
    activeChannelPotentialAreaBuffer = arcpy.analysis.Buffer(
        in_features = activeChannelPotentialArea, 
        out_feature_class = activeChannelPotentialAreaBuffer,
        buffer_distance_or_field="30 Meters", 
        line_end_type="FLAT", 
        dissolve_option="ALL", 
        method="GEODESIC")

    activeChannelFilled = "activeChannelFilled "
    activeChannelFilled = arcpy.management.EliminatePolygonPart(
        in_features = activeChannelPotentialAreaBuffer, 
        out_feature_class = activeChannelFilled, 
        condition = "PERCENT", 
        part_area_percent = 99, 
        part_option = "CONTAINED_ONLY")

    activeChannel = "activeChannel" +  "_" + year
    activeChannel = arcpy.analysis.Buffer(
        in_features = activeChannelFilled , 
        out_feature_class = activeChannel, 
        buffer_distance_or_field ="-30 Meters", 
        line_end_type = "FLAT", 
        method = "GEODESIC")
   
    arcpy.AddMessage("Extracting land within water")
    landInWater = "landInWater"
    landInWater = arcpy.analysis.Clip(
        in_features = land, 
        clip_features = wetChannel, 
        out_feature_class = landInWater)

    featureInWater = "featureInWater "
    featureInWater = arcpy.gapro.DissolveBoundaries(
        input_layer = landInWater, 
        out_feature_class = featureInWater)

    featureInWaterFilled = "featureInWaterFilled"
    featureInWaterFilled = arcpy.management.EliminatePolygonPart(
        in_features= featureInWater, 
        out_feature_class = featureInWaterFilled , 
        condition="PERCENT", 
        part_area_percent = 99)

    midChannelFeature = "midChannelFeature"+ "_" + year
    midChannelFeature = arcpy.analysis.Select(
        in_features = featureInWaterFilled, 
        out_feature_class = midChannelFeature, 
        where_clause="SHAPE_Area >= 10000")
    
    arcpy.management.AddField(midChannelFeature, "Feature_Id","LONG", 9,"","","Feature_Id","NULLABLE")
    arcpy.management.CalculateField(midChannelFeature, field="Feature_Id", expression="!OBJECTID!")
    arcpy.management.AddField(midChannelFeature, "Feature_Area","DOUBLE", 9,"","","Feature_Area","NULLABLE")
    arcpy.management.CalculateField(midChannelFeature, field="Feature_Area", expression="!Shape_Area!")

    midChannelFeatureCover = "midChannelFeatureCover"
    midChannelFeatureCover = arcpy.analysis.Intersect(
        in_features = [[landClassFea, ""], [midChannelFeature, ""]], 
        out_feature_class = midChannelFeatureCover, 
        join_attributes = "ALL", 
        output_type = "INPUT")
    
    summTableCover = arcpy.analysis.Statistics(
        in_table = midChannelFeatureCover, 
        statistics_fields= [["Shape_Area", "SUM"]], 
        case_field=["Feature_Id", "Class"])
    
    summTableVeg = "summTableVeg"
    summTableVeg = arcpy.analysis.TableSelect(
        in_table = summTableCover, 
        out_table = summTableVeg, 
        where_clause="Class = 1")
    
    arcpy.management.AlterField(summTableVeg, field="SUM_Shape_Area", new_field_name="Veg_Area",new_field_alias="Veg_Area")
    arcpy.management.JoinField(
        in_data = midChannelFeature, 
        in_field = "Feature_Id", 
        join_table = summTableVeg, 
        join_field = "Feature_Id", 
        fields = ["Veg_Area"])
    arcpy.management.CalculateField(midChannelFeature, "Veg_Area", "!Veg_Area! if !Veg_Area! is not None else 0", "PYTHON")    
    arcpy.management.AddField(midChannelFeature, "Veg_Ratio","DOUBLE", 9,"","","Veg_Ratio","NULLABLE")
    arcpy.management.CalculateField(midChannelFeature, field="Veg_Ratio", expression="!Veg_Area!/!Feature_Area!")
    arcpy.management.AddField(midChannelFeature, "Feature_Type","Text", 50,"","","Feature_Type","NULLABLE")
    code = """def type(veg):
        if veg <= 0.75:
            return \"MB\"
        else:
            return \"IS\" """
    arcpy.management.CalculateField(
        in_table=midChannelFeature, 
        field="Feature_Type", 
        expression="type(!Veg_Ratio!)", 
        code_block=code)   
    
    fieldsList = []
    keep = ["Feature_Id","Feature_Area","Feature_Type","Veg_Area","Veg_Ratio"]
    fieldObjList = arcpy.ListFields(midChannelFeature)
    for field in fieldObjList:
        if (not field.name in keep) and (not field.required):
            fieldsList.append(field.name)
    arcpy.management.DeleteField(midChannelFeature, fieldsList)


    dsets.extend((land,landOutWater,sandOutWater,sandBarOutWater,
                  activeChannelPotential,activeChannelPotentialArea,
                  activeChannelPotentialAreaBuffer,activeChannelPotentialDissolve,
                  activeChannelFilled,landInWater,featureInWater,
                  featureInWaterFilled,midChannelFeatureCover,
                  summTableCover,summTableVeg))
    
    for dset in dsets:
        arcpy.management.Delete(dset)
    
    #### Planform metrics extraction 
    
    wetChannelTransects = "wetChannelTransect"
    wetChannelTransects =  arcpy.analysis.PairwiseIntersect(
        in_features=[transects, wetChannel], 
        out_feature_class=wetChannelTransects)
    fieldname = "Wet_Width" +  "_" + year
    arcpy.management.AddField(wetChannelTransects, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    #arcpy.management.CalculateField(wetChannelTransects, field= fieldname, expression="!Shape_Length!")
    arcpy.management.CalculateGeometryAttributes(wetChannelTransects, [[fieldname, "LENGTH"]], "METERS")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field= "Distance", 
        join_table = wetChannelTransects, 
        join_field="Distance", 
        fields= [fieldname])
    
    activeChannelTransects = "activeChannelTransect"
    arcpy.analysis.PairwiseIntersect(in_features=[transects, activeChannel], 
                                     out_feature_class=activeChannelTransects)
    fieldname = "Active_Width" +  "_" + year
    arcpy.management.AddField(activeChannelTransects,fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    #arcpy.management.CalculateField(activeChannelTransects, field=fieldname, expression="!Shape_Length!")
    arcpy.management.CalculateGeometryAttributes(activeChannelTransects, [[fieldname, "LENGTH"]], "METERS")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field = "Distance", 
        join_table = activeChannelTransects, 
        join_field = "Distance", 
        fields = [fieldname])
    
    midChannelFeatureTransect = "midChannelFeatureTransect"
    midChannelFeatureTransect = arcpy.analysis.SpatialJoin(
        target_features = transects, 
        join_features = midChannelFeature, 
        out_feature_class = midChannelFeatureTransect, 
        join_operation ="JOIN_ONE_TO_MANY", 
        field_mapping = "", 
        search_radius = "0.01 Meters")
    
    summTableMidChannel = "summTableMidChannel"
    summTableMidChannel = arcpy.analysis.Statistics(
        in_table = midChannelFeatureTransect, 
        out_table = summTableMidChannel, 
        statistics_fields = [["Feature_Type", "COUNT"]], 
        case_field = ["Distance", "Feature_Type"])


    summTable_BI_All = "summTable_BI_All"
    summTable_BI_All = arcpy.analysis.Statistics(
        in_table = summTableMidChannel, 
        out_table = summTable_BI_All, 
        statistics_fields = [["COUNT_Feature_Type", "SUM"]], case_field=["Distance"])
    
    fieldname = "BI_ALL" + "_" + year
    arcpy.management.AddField(summTable_BI_All, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    arcpy.management.CalculateField(summTable_BI_All, field=fieldname, expression="!SUM_COUNT_Feature_Type!+1")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field= "Distance", 
        join_table = summTable_BI_All, 
        join_field="Distance", 
        fields= [fieldname])
    arcpy.management.CalculateField(midChannelFeature, fieldname, "!Veg_Area! if !Veg_Area! is not None else 0", "PYTHON")
    
    summTable_BI_Active = "summTable_BI_Active"
    summTable_BI_Active = arcpy.analysis.TableSelect(
        in_table = summTableMidChannel , 
        out_table = summTable_BI_Active, 
        where_clause = "Feature_Type IN ('MB')")
    
    fieldname = "BI_Active"+ "_" + year
    arcpy.management.AddField(summTable_BI_Active, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    arcpy.management.CalculateField(summTable_BI_Active, field=fieldname, expression="!COUNT_Feature_Type!+1")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field= "Distance", 
        join_table = summTable_BI_Active, 
        join_field = "Distance", 
        fields = [fieldname])
    
    dsets.extend((wetChannelTransects,activeChannelTransects,
                  midChannelFeatureTransect, summTableMidChannel,
                  summTable_BI_All, summTable_BI_Active))
    for dset in dsets:
        arcpy.management.Delete(dset)
    


