#!/usr/bin/python -tt
##-*- coding: UTF-8 -*-

'''
******************   ABOUT   ***********************************************************

This is Azimuth-Width script. It is designed to compute minimum or maximum width
of the given polygon(s) in the given direction. Corresponding QGIS plugin coming soon...

########################################################################################

******************   USAGE   ***********************************************************

Prereqirements:
                1. You have to have QGIS installed on your machine.
                2. QGIS have to be in PYTHONPATH. See: http://qgis.org/pyqgis-cookbook/intro.html
                3. Ensure that command "QgsApplication.setPrefixPath("/usr", True)" at line 323
                    of this file have valid path ("/usr" - in this case) to QGIS installation.

General usage: copy script to directory with a shh-file containing polygons.
Using console navigate to the directory. In console type:
  python ./width.py [file to analyse] [field to store values] [azimuth] [mode] [algorithm] [step]
  E.G.:~> python ./width.py poly.shp width 285.9 max Mix 1.3
Where: ./width.py - name of this script file
      [file to analyse] - polygonal shp-file
      [field to store values] - if it does not exist it will be created
      [azimuth] - a direction for width calculation. Take decimal values from 0 to 360
      [mode] - type of width to calculate. Currently 'min' (returns minimum width value
               in given direction) and 'max' (returns maximum value in given direction)
               modes are available.
      [algorithm] - algorithm that will be used: 'byStep', 'byVertex', 'Mix'.
                    "byStep" algorithm will take provided step (shp-file CRS units)
                      and swipe the polygons with it by line. Precision depends on the step.
                      Speed and precision depends on step - lower step mean more
                      precise result but computation will take more time.
                    "byVertex" will intersect polygon with the line only in vertexes
                      of the given polygon. For convex polygons this algorithm
                      will be faster and more precise using 'max' mode then "byStep"
                      algorithm. But this algorithm is not suitable for 'min' mode.
                    "Mix" algorithm will use both "byVertex" and "byStep" algorithm
                      so it will be most precise but will consume more time.
      [step] - step for "byStep" and "Mix" algorithm. Takes decimal values in
               shp-file CRS units. Lower step means more precision but more
               computation time.

########################################################################################

******************   TIPS AND TRICKS   *************************************************

1. Use Equal Area projections.
2. If you have a large variety in polygons area e.g. a continent and an island
   to save computation time you may define big step (like 1000 m or so) to swipe
   through continent faster. It will save computation time and a width for the small
   island will be calculated even if step is grater then any side of island's' Bounding
   Box: step for the island in this case will be 1/100 of the shortest side of it's Bounding
   Box.

########################################################################################

******************   COPYRIGHT  ********************************************************

copyright:  © 2012 Yury V. Ryabov
e-mail:    riabovvv@gmail.com
web-page:  http://ssrebelious.blogspot.com/2012/09/azimuth-width-script.html

########################################################################################

******************   LICENSE   *********************************************************

    'Azimuth-Width' is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    'Azimuth-Width' is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    Text of the GNU General Public License available at <http://www.gnu.org/licenses/>.

########################################################################################
'''

import sys
from qgis.core import *
import math
from PyQt4.QtCore import *



def azimuthWidth(filename, field_name, azimuth, algorithm, step, mode):
  '''
  Returns columnl with polygons weights
  '''
  layer = QgsVectorLayer(filename, "plygons", "ogr")
  if not layer.isValid():
    print "Layer failed to load!"
    QgsApplication.exitQgis()
    sys.exit(1)
  else:
    print "layer loaded!"

  # feature extraction
  provider = layer.dataProvider()
  feat = QgsFeature()

  # check if field_name exist
  columns = provider.fields()
  ci = columns.items()
  field_name_exist = 0
  key_list = []
  for key, value in ci:
    key_list.append(key)
    if str(value.name()) == field_name:
      field_name_exist = 1
      field_id = key # will be used to write width
      print 'column found'
    else:
      pass

  # creating column for result writing
  layer.startEditing()
  cap = layer.dataProvider().capabilities()
  if field_name_exist == 0:
    print 'column not found'
    field_id = max(key_list) + 1 # will be used to write width
    if cap & QgsVectorDataProvider.AddAttributes:
      res = layer.dataProvider().addAttributes( [ QgsField(field_name, QVariant.Double) ] )
      print 'column created'
  else:
    print 'column creation skipped'

  # looping through polygons and writing max width values to field_name
  while provider.nextFeature(feat):
    BBox = feat.geometry().boundingBox()
    polygon = feat.geometry()
    f_id = feat.id()
    fin_width = CalcWidth(BBox, polygon, azimuth, algorithm, step, mode)

    # writing maximum width
    if cap & QgsVectorDataProvider.ChangeAttributeValues:
      attrs = { field_id : QVariant(fin_width) }
      layer.dataProvider().changeAttributeValues({ f_id : attrs })
    print 'geometry ID: %s | %s width: %s  \n' % (f_id, mode, fin_width)

  layer.commitChanges()



#function that will actually calculate width of polygon for given azimuth
def CalcWidth(BBox, polygon, azimuth, algorithm, step, mode):
  '''
  Returns width of the given polygon
  '''
  X1 = BBox.xMinimum()
  Y1 = BBox.yMinimum()
  X2 = BBox.xMaximum()
  Y2 = BBox.yMaximum()

  # handling azimuth
  if azimuth > 180:
    az = azimuth - 180
  else:
    az = azimuth
  if az >= 90:
   az1 = 180 - az # az will be utilised again later
   az1 = math.radians(az1)
  else:
    az1 = math.radians(az)

  # maximum possible width calculation
  dX = X2 - X1
  dY = Y2 - Y1
  L = math.hypot(dX, dY)

  # adjusting "step" for polygons that are too small to be measured correctly using given step
  if algorithm in ['byStep', 'Mix']:
    treshhold = min(dX,dY)/100
    if step > treshhold:
      step = treshhold
    else:
      step = step

  # calculation of values for x_init and y_init change
  dx = L*math.sin(az1)
  dy = L*math.cos(az1)

  # extracting vertexes from polygon
  geometry_collection = polygon.asGeometryCollection() # in case there are multypolygons - I don't want to treat them separately
  vertex_list = []
  for items in geometry_collection:
    i = items.asPolygon()
    for lists in i:
      for point in lists:
        vertex_list.append(point)

  # default width
  if mode == 'max':
    width = 0
  elif mode == 'min':
    width = L

  # creating a dump for widths
  width_list = []

  # if 'byVertex' or 'Mix' algorithm is chosen
  if algorithm in ['byVertex', 'Mix']:
    # calculating lengths for vertexes
    while vertex_list:
      point = vertex_list.pop(0)
      x_raw = point[0]
      y_raw = point[1]

      if az >= 90:
        x_init = x_raw - dx
        y_init = y_raw + dy
        x_new = x_raw + dx
        y_new = y_raw - dy
      elif az < 90:
        x_init = x_raw - dx
        y_init = y_raw - dy
        x_new = x_raw + dx
        y_new = y_raw + dy

      current_width = intersecLength(L, x_init, y_init, x_new, y_new, polygon, mode) # see definition below
      width_list.append(current_width)
      w = width_list.pop(0) # a workaround caused by issues in comparing "current_width" and "width" directly: I don't want to store list of all widths in RAM
      if mode == 'max':
        if w > width:
          width = w
        else:
          pass
      elif mode == 'min':
        if w < width and w != 0:
          width = w
        else:
          pass

  # if 'byStep' or 'Mix' algorithm is chosen
  if algorithm in ['byStep', 'Mix']:
    # defining starting point for looping, redundant parameters are needed for easier code understanding
    if az >= 90:
      x_init = X1
      y_init = Y1
      x_fin = X2
      y_fin = Y2
      dy = -dy
      step_x = step
      step_y = step
    elif az < 90:
      x_init = X1
      y_init = Y2
      x_fin = X2
      y_fin = Y1
      step_x = step
      step_y = -step

    while x_init <= x_fin:
      x_new = x_init + dx
      y_new = y_init + dy
      current_width = intersecLength(L, x_init, y_init, x_new, y_new, polygon, mode) # see definition below
      width_list.append(current_width)
      w = width_list.pop(0) # a workaround caused by issues in comparing "current_width" and "width" directly: I don't want to store list of all widths in RAM
      if mode == 'max':
        if w > width:
          width = w
        else:
          pass
      elif mode == 'min':
        if w < width and w != 0:
          width = w
        else:
          pass
      if az >= 90 and y_init <= y_fin:
        y_init = y_init + step_y
      elif az < 90 and y_init >= y_fin:
        y_init = y_init + step_y
      elif x_init <= x_fin:
        x_init = x_init + step_x

  return width

def intersecLength(L, x_init, y_init, x_new, y_new, polygon, mode):
  '''
  Returns width of the polygon at given point
  '''
  A = QgsPoint(x_init, y_init)
  B = QgsPoint(x_new, y_new)
  m_line = QgsGeometry.fromPolyline( [ A, B ] ) # measurement line
  #intersec = m_line.intersection(polygon).asGeometryCollection() # SEE COMMENT BELOW
  intersec = m_line.intersection(polygon)
  length = intersec.lengths()

  # THIS PART IS FOR THE TIME WHEN THE ISSUE WITH REDUNDANT MULTIGEOMETRY WILL BE SOLVED
  # SEE http://gis-lab.info/forum/viewtopic.php?f=35&t=11606&st=0&sk=t&sd=a&start=10000#p72057
  #if mode == 'max':
    #geom_list = [-1]
  #elif mode == 'min':
    #geom_list = [L]
  #for item in intersec:
    #l = item.length()
    #if l != 0:
      #geom_list.append(l)

  #if mode == "max":
    #length = max(geom_list)
    #if length is None:
      #length = 0
  #elif mode == "min":
    #length = min(geom_list)

  return length


def main():
  '''
  Returns input file with a specified column containing polygons widths
  according to the input parameters: azimuth, mode, algorithm.
  '''
  if len(sys.argv) not in [6, 7, 8]:
    print 'USAGE: ./width.py [file to analyse] [field to store values (will be created if not exist)] [azimuth] [mode] [algorithm] [step]\ne.g.: .python ./width.py poly.shp width 285 max Mix 1'
    sys.exit(1)

  QgsApplication.setPrefixPath("/usr", True) # QGIS initialisation
  QgsApplication.initQgis()

  filename = sys.argv[1] # file to analyse

  field_name = sys.argv[2] # field to write width values

  azimuth = float(sys.argv[3]) # direction for the width calculation
  if azimuth > 360 or azimuth < 0:
    print "Invalid azimuth! Only decimal degrees between 0 and 360 are accepted!"
    QgsApplication.exitQgis()
    sys.exit(1)

  mode = sys.argv[4] # mode defines returned pattern of width
  if mode not in ['min', 'max']:
    print "Invalid mode! Only 'min' and 'max' are accepted!"
    QgsApplication.exitQgis()
    sys.exit(1)

  algorithm = sys.argv[5] # algorithm defines how width will be calculated
  if algorithm not in ['byVertex', 'byStep', 'Mix']:
    print "Invalid algorithm! Must be 'byVertex', 'byStep' or 'Mix'!"
    QgsApplication.exitQgis()
    sys.exit(1)

  if algorithm == 'byVertex' and mode == 'min':
    print "Caution! Mode 'min' in 'byVertex' will not provide actual minimum width value! For much more precise result use 'byStep' or 'Mix' instead."

  if algorithm in ['byStep', 'Mix']: # step is only needed by 'byStep' algorithm
    step = float(sys.argv[6])
    if step <= 0 or step is None:
      print "Invalid step! Step must be greater then 0!"
      QgsApplication.exitQgis()
      sys.exit(1)
  elif algorithm == 'byVertex':
    step = ""

  azimuthWidth(filename, field_name, azimuth, algorithm, step, mode)
  QgsApplication.exitQgis()

  sys.exit(1)

if __name__ == '__main__':
  main()
