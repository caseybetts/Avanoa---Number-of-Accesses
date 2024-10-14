# Author: Casey Betts, 2024
# This script outputs data on how many accesses the given orders have on a given day
# Requirements: all onv layers and active ufp layer in the table of contents with the correct names

import arcpy

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

# Create feature class of available orders
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

    return active_orders



def run_workflow():
    """ This function calls all functions in the needed order to produce final output """

    scids = ['wv01', 'wv02'] #, 'wv03', 'ge01', 'lg01', 'lg02', 'lg03', 'lg04']
    
    # Get the active map document and data frame
    m = arcpy.mp.ArcGISProject("CURRENT").activeMap

    # Create temp layers of available orders for each spacecraft and add the order list to a dictionary
    order_lists = dict()
    for scid in scids:
        order_lists[scid] = create_available_orders_featuer_class(scid, m)
        arcpy.AddMessage("Number of available orders on " + scid + ": " + str(len(order_lists)))

        


    # Create a set of all unique order ids
    # Create a columnn in a the output shapefile for number of accesses
        # Column calculation is the number of lists the order id is found in
    # Output shapefile 
