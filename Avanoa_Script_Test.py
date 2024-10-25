# Author: Casey Betts, 2024
# This script outputs data on how many accesses the given orders have on a given day
# Requirements: all onv layers and active ufp layer in the table of contents with the correct names

import arcpy
from functools import reduce
import os
import shutil

def get_layer_by_name(layer_name, map):
    """
    Returns the first layer in the TOC of the given name

    :param layer_name: String, the name of the layer to be returned
    :param map: Map Object, the map containing the layer
    """

    # Find the layer
    for layer in map.listLayers():
        if layer.name == layer_name:
            return layer
    else:
        raise Exception(f"Source layer '{layer_name}' not found in the TOC.")

# Select the available orders on a given layer
def select_available_orders(orders_layer, onv_layer, scid):
    """ Select orders accessable on a given rev based on the order's max ONA vlaue """

    arcpy.AddMessage(f"Running available_orders for {scid}.....")

    # Definition query values
    ona_values = [35, 30, 25, 20, 15]
    
    # Select orders intersecting the 45deg segments of the rev (max selection)
    arcpy.management.SelectLayerByLocation(orders_layer, "INTERSECT", onv_layer, None, "NEW_SELECTION")

    # Select only the orders that are avaialble based on their max ONA value    
    for ona in ona_values:

        # Deselect orders with ONA under current value
        arcpy.management.SelectLayerByAttribute(orders_layer, "REMOVE_FROM_SELECTION", "max_ona < " + str(ona + 1), None)

        # Create an onv feature
        feature_layer = arcpy.management.MakeFeatureLayer(onv_layer, "FeatureLayer", f"ona = {ona}")

        # Select orders intersecting the current onv feature layer
        arcpy.management.SelectLayerByLocation(orders_layer, "INTERSECT", feature_layer, None, "ADD_TO_SELECTION")

    # Deselect orders that do not use the spacecraft consitant with the onv
    arcpy.management.SelectLayerByAttribute(orders_layer, "REMOVE_FROM_SELECTION", scid + " = 0", None)

    arcpy.AddMessage("Done")

def create_available_orders_featuer_class(scid, m):
    """ Create a feature class of all available orders on a given spacecraft and return the list of order ids"""

    # get the onv and orders layers
    onv_layer = get_layer_by_name('onv_'+scid+'_Avanoa', m)
    orders_layer = get_layer_by_name('active_orders_ufp_Avanoa', m)

    # Select the available orders on the orders layer
    select_available_orders(orders_layer, onv_layer, scid)

    # Export the selection to the defalut GDB
    temp_layer = arcpy.env.workspace + "\\" + 'available_' + scid + '_temp'
    arcpy.conversion.ExportFeatures(orders_layer, temp_layer)

    # Create a list of order ids
    with arcpy.da.SearchCursor(temp_layer, ["external_id"]) as cursor:
        active_orders = [row[0] for row in cursor]

    arcpy.AddMessage(scid + " :" + str(active_orders[:10]))

    return active_orders

def find_layer_by_source(map, source_path, query_req):
    """ Returns a layer of the given source and name"""

    # Loop through layers looking for matching source and base
    for layer in map.listLayers():
        try:
            desc = arcpy.Describe(layer)
            query = layer.listDefinitionQueries()[0]
            if desc.catalogPath == source_path and query_req in query['sql']:
                return layer

        except:
            continue

    return None

def change_def_query(layer, query):
    """ Change the definition query of the given layer to the given string """

    layer.definitionQuery = query



def get_selected(layer, field):
    """ Returns a list of order ids from the given layer that are currently selected """

    desc = arcpy.Describe(layer)
    oid_field = desc.OIDFieldName 

    # Create a list of selected rows
    with arcpy.da.SearchCursor(layer, [oid_field]) as cursor:
        selected_ids = [str(row[0]) for row in cursor]

    selected_field = []
    # Create a list of values from the given field
    with arcpy.da.SearchCursor(layer, [oid_field, field]) as cursor:
        for row in cursor:
            selected_field.append(row[1])

    return selected_field

def delete_files(folder):
    """ 
    Deletes out the files in the given folder
    """

    for file in os.listdir(folder):
        file_path = os.path.join(folder,  file)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                arcpy.AddMessage(f"Deleted: {file}")
            except:
                arcpy.AddMessage(f"Could not delete: {file}")
                continue

def move_files(source_folder, target_folder):
    """ 
    Moves all files in a given folder to the given output folder    
    """

    for file in os.listdir(source_folder):
        source_path = os.path.join(source_folder, file)
        dest_path = os.path.join(target_folder, file)
        shutil.move(source_path, dest_path)

def run_workflow(path, days):
    """ This function calls all functions in the needed order to produce final output """

    scids = ['wv02']#, 'wv02', 'wv03', 'ge01', 'lg01', 'lg02', 'lg03', 'lg04']
    staging_loc = os.path.join(path, "Staging")
    output_loc = os.path.join(path, "Output")
    output_feature = os.path.join(staging_loc, "Avanoa_test")
    
    # Get the active map document and data frame
    m = arcpy.mp.ArcGISProject("CURRENT").activeMap

    # Get the orders layer
    orders_layer = get_layer_by_name('active_orders_ufp_Avanoa', m)

    # Create lists of available orders for each spacecraft and add the order lists to a dictionary
    order_lists = dict()
    for scid in scids:

        for day in range(1, days+1):

            onv_source = f"https://geoserver-gds-prod-rehearsal.app.maxaranalytics.com/geoserver/ows?\onv_{scid}"

            # get the onv layer
            onv_layer = find_layer_by_source(m, onv_source, f'days = {day}')

            # get the original definition query
            original_query = onv_layer.definitionQuery
            onv_layer.definitionQuery = f"days = {day} And ona IN (15, 25, 20, 30, 35, 45)"
            
            # Select available orders for scid and put order ids in a list
            if onv_layer != None:
                select_available_orders(orders_layer, onv_layer, scid)
                order_lists[scid + "_" + str(day)] = get_selected(orders_layer, 'external_id')
            else:
                arcpy.AddMessage("onv layer is none")

            onv_layer.definitionQuery = original_query

            arcpy.AddMessage(f"Number of available orders in {day} days with {scid}: " + str(len(order_lists[scid + "_" + str(day)])))

    # Create a list of unique availabe order ids
    unique_ids = list(reduce(lambda x, y: set(x) | set(y), list(order_lists.values())))

    # Create the new order layer
    arcpy.SelectLayerByAttribute_management(orders_layer, "CLEAR_SELECTION")
    arcpy.conversion.ExportFeatures(orders_layer, output_feature)

    # Create column specific vars
    field_name = "Accesses"
    expression = "Get_Number_of_Accesses(!external_i!)"
    field_type = "Short"
    code_block = "order_lists = " + str(order_lists) + """
def Get_Number_of_Accesses(order_id):
    count = 0
    for scid in order_lists:
        if order_id in order_lists[scid]: count+=1
    return count
            
    """

    # Create a columnn in a the output shapefile for number of accesses
    arcpy.management.CalculateField(output_feature, field_name, expression, "PYTHON3", code_block, field_type)

    # Delete existing shapefiles
    delete_files(output_loc)

    # Move new shapefiles to output location
    move_files(staging_loc, output_loc)