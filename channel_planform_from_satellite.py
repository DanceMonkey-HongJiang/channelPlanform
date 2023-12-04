# -*- coding: utf-8 -*-
"""
This tool is designed for extracting basic information and metrics of river planform from multi-spectral satellite image

It takes the a multi-spectral image as major input and generates two group of outputs:

1) Basic channel features as polygons:
    Land cover()
    Active channel
    Wet channel boundary
    Wet channels
    Geomorphic Unit
    Transects along the river
2) Planform metrics along the river:
    Active channel width
    Wet channel width (of wet channel boundary)
    Braiding index
    Anabranching index

Addtional inputs include the river envelope polygon and the start point of the river

There are three sub-tools to generate the final outputs:
    1) Classify the multi-spectral image into water,vegetation, and bare land
    3) Extract basic channel features 
    3) Generate transects along the axis(centreline) of the river envelope
    4) Extract planform metrics at each trasect

@author: Hong
"""

import arcpy
import numpy as np

if __name__ == '__main__':
    
    # Get input datasets from script tool interface:
    image = arcpy.GetParameterAsText(0)
    envelope = arcpy.GetParameterAsText(1)
    startPoint = arcpy.GetParameterAsText(2)
    Out_Space = arcpy.GetParameterAsText(3)

    arcpy.env.workspace = Out_Space
    arcpy.env.overwriteOutput = True
    arcpy.env.extent = arcpy.Describe(envelope).Extent
    arcpy.env.outputCoordinateSystem = arcpy.Describe(envelope).spatialReference  
    arcpy.env.overwriteOutput = True
    
    # Get input thresholds for model running from script tool interface:
    green_band = arcpy.GetParameterAsText(4)
    red_band = arcpy.GetParameterAsText(5)
    nir_band = arcpy.GetParameterAsText(6)
    swir_band = arcpy.GetParameterAsText(7)
    ndvi_threshold = arcpy.GetParameterAsText(8)
    mndwi_threshold = arcpy.GetParameterAsText(9)
    waterArea_threshold = arcpy.GetParameterAsText(10)
    barArea_threshold = arcpy.GetParameterAsText(11)
    smooth_tolerance = arcpy.GetParameterAsText(12)
    spacing_length = arcpy.GetParameterAsText(13)
    cross_length = arcpy.GetParameterAsText(14)
    # Create empty list for interim datasets to be deleted at end of function
    dsets = []
    
#### Sub-tool-1 Land cover classification, 0: water; 1: sand; 2: vegetation
    arcpy.AddMessage("Classifying land cover")
    ndvi = arcpy.sa.NDVI(image,int(nir_band),int(red_band))
    mndwi = arcpy.sa.NDWI(image,int(swir_band),int(green_band))
    ndvi_reclassifier = arcpy.sa.RemapRange([[-1,float(ndvi_threshold), 1], [float(ndvi_threshold), 1, 2]])
    mndwi_reclassifier = arcpy.sa.RemapRange([[-1,float(mndwi_threshold), 1], [float(mndwi_threshold), 1, 0]])
    reclassNdvi = arcpy.sa.Reclassify(ndvi, "VALUE", ndvi_reclassifier, "NODATA")
    reclassMndwi = arcpy.sa.Reclassify(mndwi, "VALUE", mndwi_reclassifier, "NODATA")
    landCover = reclassNdvi * reclassMndwi
    landClassRas = arcpy.sa.ExtractByMask(
        landCover, 
        envelope, 
        "INSIDE", 
        "")
    landClass = "landClass" 
    arcpy.conversion.RasterToPolygon(
        in_raster = landClassRas, 
        out_polygon_features = landClass, 
        create_multipart_features="SINGLE_OUTER_PART")
    arcpy.management.AlterField(landClass,"gridcode", "Class", "Class")
    
    fieldsList = []
    keep = ["Class","Shape_Area"]
    fieldObjList = arcpy.ListFields(landClass)
    for field in fieldObjList:
        if (not field.name in keep) and (not field.required):
            fieldsList.append(field.name)
    arcpy.management.DeleteField(landClass, fieldsList)
    

#### Sub-tool-2 Channel feature extraction
   
    #### Wet channel boundary extraction 
    arcpy.AddMessage("Extracting wet channel")
    water = "water"
    water = arcpy.analysis.Select(
        in_features = landClass, 
        out_feature_class= water, 
        where_clause="Class = 0")
    
    waterBuffer = "waterBuffer"
    waterBuffer = arcpy.analysis.Buffer(
        in_features = water, 
        out_feature_class = waterBuffer, 
        buffer_distance_or_field = "15 Meters", 
        line_end_type ="FLAT", 
        dissolve_option="NONE", 
        method="GEODESIC")
    
    waterBufferDissolve = "waterBufferDissolve" 
    waterBufferDissolve = arcpy.gapro.DissolveBoundaries(
        input_layer = waterBuffer, 
        out_feature_class = waterBufferDissolve)
    
    water_selection = "Shape_Area >= " + str(waterArea_threshold)
    
    wetChannels = "wetChannels"
    wetChannels  = arcpy.analysis.Select(
        in_features = waterBufferDissolve, 
        out_feature_class = wetChannels, 
        where_clause = water_selection)
    
    waterContinueBuffer = "waterContinueBuffer"
    waterContinueBuffer = arcpy.analysis.Buffer(
        in_features = wetChannels, 
        out_feature_class = waterContinueBuffer, 
        buffer_distance_or_field = "15 Meters", 
        line_end_type ="FLAT", 
        dissolve_option="ALL", 
        method="GEODESIC")
    
    waterContinueFilled = "waterContinueFilled"
    waterContinueFilled  = arcpy.management.EliminatePolygonPart(
        in_features = waterContinueBuffer, 
        out_feature_class = waterContinueFilled, 
        condition = "PERCENT", 
        part_area_percent = 99, 
        part_option = "CONTAINED_ONLY")
   
    waterFilled = "waterFilled" 
    waterFilled = arcpy.analysis.Buffer(
        in_features = waterContinueFilled , 
        out_feature_class = waterFilled , 
        buffer_distance_or_field = "-30 Meters", 
        line_end_type ="FLAT", 
        dissolve_option ="ALL", 
        method="GEODESIC")
    
    waterFilledParts = "waterFilledParts"
    waterFilledParts = arcpy.management.MultipartToSinglepart(
        in_features = waterFilled, 
        out_feature_class = waterFilledParts)
      
    wetChannelBoundary = "wetChannelBoundary"
    wetChannel = arcpy.analysis.Select(
        in_features = waterFilledParts, 
        out_feature_class = wetChannelBoundary , 
        where_clause = water_selection)

    # Delete interim datasets in workspace  
    dsets.extend((water,waterBuffer, waterBufferDissolve,
                  waterContinueBuffer,waterContinueFilled,
                  waterFilled,waterFilledParts))
   
    for dset in dsets:
        arcpy.management.Delete(dset)
     
    #### Geomorphic unit extraction and classification
    arcpy.AddMessage("Extracting land outside out wet channel")
    land = "land"
    land = arcpy.analysis.Select(
        in_features = landClass, 
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
        where_clause = water_selection)

    activeChannelPotentialAreaBuffer = "activeChannelPotentialAreaBuffer"
    activeChannelPotentialAreaBuffer = arcpy.analysis.Buffer(
        in_features = activeChannelPotentialArea, 
        out_feature_class = activeChannelPotentialAreaBuffer,
        buffer_distance_or_field = "30 Meters", 
        line_end_type = "FLAT", 
        dissolve_option = "ALL", 
        method = "GEODESIC")

    activeChannelFilled = "activeChannelFilled "
    activeChannelFilled = arcpy.management.EliminatePolygonPart(
        in_features = activeChannelPotentialAreaBuffer, 
        out_feature_class = activeChannelFilled, 
        condition = "PERCENT", 
        part_area_percent = 99, 
        part_option = "CONTAINED_ONLY")

    activeChannel = "activeChannel"
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
    
    arcpy.management.AddField(featureInWaterFilled , "Unit_Area","DOUBLE", 9,"","","Unit_Area","NULLABLE")
    arcpy.management.CalculateField(featureInWaterFilled , field="Unit_Area", expression="!SHAPE.AREA@SQUAREMETERS!")

    gu_selection = "Unit_Area >= " + str(barArea_threshold)

    midUnit = "midUnit"
    midUnit = arcpy.analysis.Select(
        in_features = featureInWaterFilled, 
        out_feature_class = midUnit, 
        where_clause = gu_selection)
    
    arcpy.management.AddField(midUnit, "Feature_Id","LONG", 9,"","","Feature_Id","NULLABLE")
    arcpy.management.CalculateField(midUnit, field="Feature_Id", expression="!OBJECTID!")


    midUnitClass = "midUnitClass"
    midUnitClass = arcpy.analysis.Intersect(
        in_features = [[landClass, ""], [midUnit, ""]], 
        out_feature_class = midUnitClass , 
        join_attributes = "ALL", 
        output_type = "INPUT")
    
    arcpy.management.AddField(midUnitClass, "Class_Area","DOUBLE", 9,"","","Class_Area","NULLABLE")
    arcpy.management.CalculateField(midUnitClass, field="Class_Area", expression="!SHAPE.AREA@SQUAREMETERS!")
    
    summTableCover = arcpy.analysis.Statistics(
        in_table = midUnitClass, 
        statistics_fields= [["Class_Area", "SUM"]], 
        case_field=["Feature_Id", "Class"])
    
    summTableVeg = "summTableVeg"
    summTableVeg = arcpy.analysis.TableSelect(
        in_table = summTableCover, 
        out_table = summTableVeg, 
        where_clause="Class = 2")
    
    arcpy.management.JoinField(
        in_data = midUnit, 
        in_field = "Feature_Id", 
        join_table = summTableVeg, 
        join_field = "Feature_Id", 
        fields = ["SUM_CLass_Area"])
    arcpy.management.AddField(midUnit, "Veg_Area","DOUBLE", 9,"","","Veg_Area","NULLABLE")
    arcpy.management.CalculateField(midUnit, "Veg_Area", "!SUM_Class_Area! if !SUM_Class_Area! is not None else 0", "PYTHON")       
    arcpy.management.AddField(midUnit, "Veg_Ratio","DOUBLE", 9,"","","Veg_Ratio","NULLABLE")
    arcpy.management.CalculateField(midUnit, field="Veg_Ratio", expression="!Veg_Area!/!Unit_Area!")
    arcpy.management.AddField(midUnit, "Unit_Type","Text", 50,"","","Unit_Type","NULLABLE")
    code = """def type(veg):
        if veg <= 0.75:
            return \"MB\"
        else:
            return \"IS\" """
    arcpy.management.CalculateField(
        in_table = midUnit, 
        field="Unit_Type", 
        expression="type(!Veg_Ratio!)", 
        code_block=code)   
    
    fieldsList = []
    keep = ["Feature_Id","Unit_Area","Unit_Type","Veg_Area","Veg_Ratio"]
    fieldObjList = arcpy.ListFields(midUnit)
    for field in fieldObjList:
        if (not field.name in keep) and (not field.required):
            fieldsList.append(field.name)
    arcpy.management.DeleteField(midUnit, fieldsList)
    
    ## Extract side bars and its vegetation cover ratio
    sideFeature = "sideFeature"
    sideFeature = arcpy.analysis.PairwiseErase(
        in_features= activeChannel, 
        erase_features= wetChannelBoundary, 
        out_feature_class = sideFeature)

    sideFeatures = "sideFeatures"
    sideFeatures = arcpy.management.MultipartToSinglepart(
        in_features = sideFeature, 
        out_feature_class = sideFeatures)
    
    arcpy.management.AddField(sideFeatures, "Unit_Area","DOUBLE", 9,"","","Unit_Area","NULLABLE")
    arcpy.management.CalculateField(sideFeatures, field="Unit_Area", expression="!SHAPE.AREA@SQUAREMETERS!")
    
    feature_selection = "Unit_Area >=" + str(barArea_threshold)
    
    sideUnit = "sideUnit"
    arcpy.analysis.Select(
        in_features = sideFeatures, 
        out_feature_class = sideUnit, 
        where_clause = feature_selection)

    arcpy.management.AddField(sideUnit, "Feature_Id","LONG", 9,"","","Feature_Id","NULLABLE")
    arcpy.management.CalculateField(sideUnit, field="Feature_Id", expression="!OBJECTID!")    
    
    sideUnitClass = "sideUnitClass"
    sideUnitClass = arcpy.analysis.Intersect(
        in_features=[[landClass, ""], [sideUnit, ""]], 
        out_feature_class = sideUnitClass)
    
    arcpy.management.AddField(sideUnitClass, "Class_Area","DOUBLE", 9,"","","Class_Area","NULLABLE")
    arcpy.management.CalculateField(sideUnitClass, field="Class_Area", expression="!SHAPE.AREA@SQUAREMETERS!")
    
    summTableCover = arcpy.analysis.Statistics(
        in_table = sideUnitClass, 
        statistics_fields= [["Class_Area", "SUM"]], 
        case_field=["Feature_Id", "Class"])
    
    summTableVeg = "summTableVeg"
    summTableVeg = arcpy.analysis.TableSelect(
        in_table = summTableCover, 
        out_table = summTableVeg, 
        where_clause="Class = 2")

    arcpy.management.JoinField(
        in_data = sideUnit, 
        in_field = "Feature_Id", 
        join_table = summTableVeg, 
        join_field = "Feature_Id", 
        fields = ["SUM_Class_Area"])
    
    arcpy.management.AddField(sideUnit, "Veg_Area","DOUBLE", 9,"","","Veg_Area","NULLABLE")
    arcpy.management.CalculateField(sideUnit, "Veg_Area", "!SUM_Class_Area! if !SUM_Class_Area! is not None else 0", "PYTHON")    
    arcpy.management.AddField(sideUnit, "Veg_Ratio","DOUBLE", 9,"","","Veg_Ratio","NULLABLE")
    arcpy.management.CalculateField(sideUnit, field="Veg_Ratio", expression="!Veg_Area!/!Unit_Area!")
    arcpy.management.AddField(sideUnit, "Unit_Type","Text", 50,"","","Unit_Type","NULLABLE")
    arcpy.management.CalculateField(sideUnit,field="Unit_Type",expression="\"SB\"")   
    
    fieldsList = []
    keep = ["Feature_Id","Unit_Area","Unit_Type","Veg_Area","Veg_Ratio"]
    fieldObjList = arcpy.ListFields(sideUnit)
    for field in fieldObjList:
        if (not field.name in keep) and (not field.required):
            fieldsList.append(field.name)
    arcpy.management.DeleteField(sideUnit, fieldsList)
        
    channelUnit = "channelUnit" 
    arcpy.management.Merge(
        inputs = [sideUnit, midUnit], 
        output = channelUnit, 
        field_mappings = "")
    
    arcpy.management.AddField(channelUnit, "Unit_Id","LONG", 9,"","","Unit_Id","NULLABLE")
    arcpy.management.CalculateField(channelUnit, field="Unit_Id", expression="!OBJECTID!")
    arcpy.management.DeleteField(channelUnit, ["Feature_Id"])

    dsets.extend((land,landOutWater,sandOutWater,sandBarOutWater,
                  activeChannelPotential,activeChannelPotentialArea,
                  activeChannelPotentialAreaBuffer,activeChannelPotentialDissolve,
                  activeChannelFilled,landInWater,featureInWater,
                  featureInWaterFilled,midUnitClass,sideFeature,sideFeatures,
                  sideUnitClass,sideUnit,summTableCover,summTableVeg))
    
    for dset in dsets:
        arcpy.management.Delete(dset)

#### Sub-tool-3 generate transects along the river 

    #### Centreline extraction and transects generalization
    arcpy.AddMessage("Generating transects")
    centerLine = "centerLine"
    arcpy.topographic.PolygonToCenterline(
        in_features = envelope, 
        out_feature_class = centerLine)
    
    centreline_smooth_tolerance = str(smooth_tolerance) + " Meters"
    centerLineSmooth = "centerLineSmooth"
    arcpy.cartography.SmoothLine(
        in_features = centerLine, 
        out_feature_class = centerLineSmooth, 
        algorithm = "PAEK", 
        tolerance = centreline_smooth_tolerance)
    
    transect_length_spacing = str(spacing_length) + " Meters"
    transect_length_cross = str(cross_length) + " Meters"
    
    transects = "transects"
    transects = arcpy.management.GenerateTransectsAlongLines(
        in_features = centerLineSmooth, 
        out_feature_class = transects, 
        interval = transect_length_spacing, 
        transect_length = transect_length_cross)
    
    arcpy.management.AddField(transects, "Transect_Id","LONG", 9,"","","Transect_Id","NULLABLE")
    arcpy.management.CalculateField(transects, field="Transect_Id", expression="!OBJECTID!")
    arcpy.management.AddField(transects, "Distance","LONG", 9,"","","Distance","NULLABLE")
    arcpy.management.AddField(transects, "Distance_Max","LONG", 9,"","","Distance_Max","NULLABLE")
    arcpy.management.AddField(transects, "Distance_Spacing", "FLOAT", 9,"","", "Distance_Spacing","NULLABLE")
    arcpy.management.CalculateField(transects, "Distance_Spacing", spacing_length, "PYTHON")
    
    centerLineEnds = arcpy.management.FeatureVerticesToPoints(
        in_features = centerLine, 
        point_location="BOTH_ENDS")
    
    arcpy.management.AddField(centerLineEnds, "End_Id","LONG", 9,"","","End_Id","NULLABLE")
    arcpy.management.CalculateField(centerLineEnds, field="End_Id", expression="!OBJECTID!")
    
    centerLineEnds = arcpy.analysis.Near(
        in_features = centerLineEnds, 
        near_features = [startPoint], 
        distance_unit = "Meters")
    
    fields = ('End_Id','NEAR_DIST')
    ends_tb = arcpy.da.TableToNumPyArray(centerLineEnds,fields)
    ends = np.sort(ends_tb, order = ['End_Id'])
    
    fields = ("Transect_Id")
    crosses_tb = arcpy.da.TableToNumPyArray(transects,fields)
    crosses = np.sort(crosses_tb, order = ['Transect_Id'])
       
    d = max(crosses['Transect_Id'][1:len(crosses)].tolist())
    arcpy.management.CalculateField(transects,"Distance_Max", d, "PYTHON")
    
    if ends[0][1] > ends[1][1]:
       arcpy.management.CalculateField(transects, field="Distance", expression="(!Distance_Max!-!Transect_Id!+1)*!Distance_Spacing!") 
    else:
        arcpy.management.CalculateField(transects, field="Distance", expression="!Transect_Id!*!Distance_Spacing!")
        
    arcpy.management.DeleteField(transects, drop_field=["Distance_Max"])
    
    dsets.extend((centerLine,centerLineSmooth,centerLineEnds))
    for dset in dsets:
        arcpy.management.Delete(dset)
 
    
#### Sub-tool-4 Planform metrics extraction 
  
    wetChannelTransect = "wetChannelTransect"
    wetChannelTransect =  arcpy.analysis.PairwiseIntersect(
        in_features=[transects, wetChannelBoundary], 
        out_feature_class = wetChannelTransect)
    fieldname = "Wet_Width"
    arcpy.management.AddField(wetChannelTransect, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    arcpy.management.CalculateGeometryAttributes(wetChannelTransect, [[fieldname, "LENGTH"]], "METERS")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field= "Distance", 
        join_table = wetChannelTransect, 
        join_field="Distance", 
        fields= [fieldname])
    
    activeChannelTransect = "activeChannelTransect"
    activeChannelTransect = arcpy.analysis.PairwiseIntersect(in_features=[transects, activeChannel], 
                                     out_feature_class=activeChannelTransect)
    fieldname = "Active_Width" 
    arcpy.management.AddField(activeChannelTransect,fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    arcpy.management.CalculateGeometryAttributes(activeChannelTransect, [[fieldname, "LENGTH"]], "METERS")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field = "Distance", 
        join_table = activeChannelTransect, 
        join_field = "Distance", 
        fields = [fieldname])
    
    midUnitTransect = "midUnitTransect"
    midUnitTransect  = arcpy.analysis.SpatialJoin(
        target_features = transects, 
        join_features = midUnit, 
        out_feature_class = midUnitTransect, 
        join_operation ="JOIN_ONE_TO_MANY", 
        field_mapping = "", 
        search_radius = "0.01 Meters")
    
    summTableMidChannel = "summTableMidChannel"
    summTableMidChannel = arcpy.analysis.Statistics(
        in_table = midUnitTransect, 
        out_table = summTableMidChannel, 
        statistics_fields = [["Unit_Type", "COUNT"]], 
        case_field = ["Distance", "Unit_Type"])


    summTable_BI_All = "summTable_BI_All"
    summTable_BI_All = arcpy.analysis.Statistics(
        in_table = summTableMidChannel, 
        out_table = summTable_BI_All, 
        statistics_fields = [["COUNT_Unit_Type", "SUM"]], case_field=["Distance"])
    
    fieldname = "BI_ALL" 
    arcpy.management.AddField(summTable_BI_All, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    arcpy.management.CalculateField(summTable_BI_All, field=fieldname, expression="!SUM_COUNT_Unit_Type!+1")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field= "Distance", 
        join_table = summTable_BI_All, 
        join_field="Distance", 
        fields= [fieldname])
    
    summTable_BI_Active = "summTable_BI_Active"
    summTable_BI_Active = arcpy.analysis.TableSelect(
        in_table = summTableMidChannel , 
        out_table = summTable_BI_Active, 
        where_clause = "Unit_Type IN ('MB')")
    
    fieldname = "BI_Active"
    arcpy.management.AddField(summTable_BI_Active, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    arcpy.management.CalculateField(summTable_BI_Active, field=fieldname, expression="!COUNT_Unit_Type!+1")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field= "Distance", 
        join_table = summTable_BI_Active, 
        join_field = "Distance", 
        fields = [fieldname])
    
    summTable_AI = "summTable_AI"
    summTable_AI = arcpy.analysis.TableSelect(
        in_table = summTableMidChannel , 
        out_table = summTable_AI, 
        where_clause = "Unit_Type IN ('IS')")
    
    fieldname = "AI"
    arcpy.management.AddField(summTable_AI, fieldname,"DOUBLE", 9,"","",fieldname,"NULLABLE")
    arcpy.management.CalculateField(summTable_AI, field=fieldname, expression="!COUNT_Unit_Type!+1")
    
    transects = arcpy.management.JoinField(
        in_data = transects, 
        in_field= "Distance", 
        join_table = summTable_AI, 
        join_field = "Distance", 
        fields = [fieldname])
    
    
    dsets.extend((wetChannelTransect,activeChannelTransect,
                  midUnitTransect, summTableMidChannel,
                  summTable_BI_All, summTable_BI_Active,midUnit,
                  summTable_AI))
    
    for dset in dsets:
        arcpy.management.Delete(dset)
        
