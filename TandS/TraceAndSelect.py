import os
import vtk, qt, ctk, slicer
import EditorLib
from EditorLib.EditOptions import HelpButton
from EditorLib.EditOptions import EditOptions
from EditorLib import EditUtil
from EditorLib import LabelEffect

#
# The Editor Extension itself.
#
# This needs to define the hooks to become an editor effect.
#

#
# TraceAndSelectOptions - see LabelEffect, EditOptions and Effect for superclasses
#

class TraceAndSelectOptions(EditorLib.LabelEffectOptions):
  """ TraceAndSelect-specfic gui
  """

  def __init__(self, parent=0):
    super(TraceAndSelectOptions,self).__init__(parent)

    # self.attributes should be tuple of options:
    # 'MouseTool' - grabs the cursor
    # 'Nonmodal' - can be applied while another is active
    # 'Disabled' - not available
    self.attributes = ('MouseTool')
    self.displayName = 'TraceAndSelect Effect'

  def __del__(self):
    super(TraceAndSelectOptions,self).__del__()

  def create(self):
    super(TraceAndSelectOptions,self).create()

    self.toleranceFrame = qt.QFrame(self.frame)
    self.toleranceFrame.setLayout(qt.QHBoxLayout())
    self.frame.layout().addWidget(self.toleranceFrame)
    self.widgets.append(self.toleranceFrame)
    self.toleranceLabel = qt.QLabel("Tolerance:", self.toleranceFrame)
    self.toleranceLabel.setToolTip("Set the tolerance of the wand in terms of background pixel values")
    self.toleranceFrame.layout().addWidget(self.toleranceLabel)
    self.widgets.append(self.toleranceLabel)
    self.toleranceSpinBox = qt.QDoubleSpinBox(self.toleranceFrame)
    self.toleranceSpinBox.setToolTip("Set the tolerance of the wand in terms of background pixel values")
    self.toleranceSpinBox.minimum = 0
    self.toleranceSpinBox.maximum = 10000
    self.toleranceSpinBox.suffix = ""
    self.toleranceFrame.layout().addWidget(self.toleranceSpinBox)
    self.widgets.append(self.toleranceSpinBox)

    self.maxPixelsFrame = qt.QFrame(self.frame)
    self.maxPixelsFrame.setLayout(qt.QHBoxLayout())
    self.frame.layout().addWidget(self.maxPixelsFrame)
    self.widgets.append(self.maxPixelsFrame)
    self.maxPixelsLabel = qt.QLabel("Max Pixels per click:", self.maxPixelsFrame)
    self.maxPixelsLabel.setToolTip("Set the maxPixels for each click")
    self.maxPixelsFrame.layout().addWidget(self.maxPixelsLabel)
    self.widgets.append(self.maxPixelsLabel)
    self.maxPixelsSpinBox = qt.QDoubleSpinBox(self.maxPixelsFrame)
    self.maxPixelsSpinBox.setToolTip("Set the maxPixels for each click")
    self.maxPixelsSpinBox.minimum = 1
    self.maxPixelsSpinBox.maximum = 100000
    self.maxPixelsSpinBox.suffix = ""
    self.maxPixelsFrame.layout().addWidget(self.maxPixelsSpinBox)
    self.widgets.append(self.maxPixelsSpinBox)

    HelpButton(self.frame, "Use this tool to label all voxels that are within a tolerance of where you click")

    # don't connect the signals and slots directly - instead, add these
    # to the list of connections so that gui callbacks can be cleanly 
    # disabled while the gui is being updated.  This allows several gui
    # elements to be interlinked with signal/slots but still get updated
    # as a unit to the new value of the mrml node.
    self.connections.append( 
        (self.toleranceSpinBox, 'valueChanged(double)', self.onToleranceSpinBoxChanged) )
    self.connections.append( 
        (self.maxPixelsSpinBox, 'valueChanged(double)', self.onMaxPixelsSpinBoxChanged) )
    

    # Add vertical spacer
    self.frame.layout().addStretch(1)

  def destroy(self):
    super(TraceAndSelectOptions,self).destroy()

  # note: this method needs to be implemented exactly as-is
  # in each leaf subclass so that "self" in the observer
  # is of the correct type 
  def updateParameterNode(self, caller, event):
    node = EditUtil.EditUtil().getParameterNode()
    if node != self.parameterNode:
      if self.parameterNode:
        node.RemoveObserver(self.parameterNodeTag)
      self.parameterNode = node
      self.parameterNodeTag = node.AddObserver("ModifiedEvent", self.updateGUIFromMRML)

  def setMRMLDefaults(self):
    super(TraceAndSelectOptions,self).setMRMLDefaults()
    disableState = self.parameterNode.GetDisableModifiedEvent()
    self.parameterNode.SetDisableModifiedEvent(1)
    defaults = (
      ("tolerance", "500"),
      ("maxPixels", "1000"),
      ("paintThreshold", "1"),
      ("paintThresholdMin", "250"),
      ("paintThresholdMax", "2799"),
    )
    for d in defaults:
      param = "TraceAndSelect,"+d[0]
      pvalue = self.parameterNode.GetParameter(param)
      if pvalue == '':
        self.parameterNode.SetParameter(param, d[1])
    self.parameterNode.SetDisableModifiedEvent(disableState)

  def updateGUIFromMRML(self,caller,event):
    params = ("tolerance", "maxPixels",)
    for p in params:
      if self.parameterNode.GetParameter("TraceAndSelect,"+p) == '':
        # don't update if the parameter node has not got all values yet
        return
    super(TraceAndSelectOptions,self).updateGUIFromMRML(caller,event)
    self.disconnectWidgets()
    self.toleranceSpinBox.setValue( float(self.parameterNode.GetParameter("TraceAndSelect,tolerance")) )
    self.maxPixelsSpinBox.setValue( float(self.parameterNode.GetParameter("TraceAndSelect,maxPixels")) )
    self.toleranceFrame.setHidden( self.thresholdPaint.checked )
    self.connectWidgets()

  def onToleranceSpinBoxChanged(self,value):
    if self.updatingGUI:
      return
    self.updateMRMLFromGUI()

  def onMaxPixelsSpinBoxChanged(self,value):
    if self.updatingGUI:
      return
    self.updateMRMLFromGUI()

  def updateMRMLFromGUI(self):
    disableState = self.parameterNode.GetDisableModifiedEvent()
    self.parameterNode.SetDisableModifiedEvent(1)
    super(TraceAndSelectOptions,self).updateMRMLFromGUI()
    self.parameterNode.SetParameter( "TraceAndSelect,tolerance", str(self.toleranceSpinBox.value) )
    self.parameterNode.SetParameter( "TraceAndSelect,maxPixels", str(self.maxPixelsSpinBox.value) )
    self.parameterNode.SetDisableModifiedEvent(disableState)
    if not disableState:
      self.parameterNode.InvokePendingModifiedEvent()


#
# TraceAndSelectTool
#

class TraceAndSelectTool(LabelEffect.LabelEffectTool):
  """
  One instance of this will be created per-view when the effect
  is selected.  It is responsible for implementing feedback and
  label map changes in response to user input.
  This class observes the editor parameter node to configure itself
  and queries the current view for background and label volume
  nodes to operate on.
  """

  def __init__(self, sliceWidget):
    super(TraceAndSelectTool,self).__init__(sliceWidget)
    # create a logic instance to do the non-gui work
    self.logic = TraceAndSelectLogic(self.sliceWidget.sliceLogic())

  def cleanup(self):
    super(TraceAndSelectTool,self).cleanup()

  def processEvent(self, caller=None, event=None):
    """
    handle events from the render window interactor
    """

    # let the superclass deal with the event if it wants to
    if super(TraceAndSelectTool,self).processEvent(caller,event):
      return

    if event == "LeftButtonPressEvent":
      xy = self.interactor.GetEventPosition()
      sliceLogic = self.sliceWidget.sliceLogic()
      logic = TraceAndSelectLogic(sliceLogic)
      logic.undoRedo = self.undoRedo
      logic.apply(xy)
      print("Got a %s at %s in %s" % (event,str(xy),self.sliceWidget.sliceLogic().GetSliceNode().GetName()))
      self.abortEvent(event)
    else:
      pass

    # events from the slice node
    if caller and caller.IsA('vtkMRMLSliceNode'):
      # here you can respond to pan/zoom or other changes
      # to the view
      pass


#
# TraceAndSelectLogic
#

class TraceAndSelectLogic(LabelEffect.LabelEffectLogic):
  """
  This class contains helper methods for a given effect
  type.  It can be instanced as needed by an TraceAndSelectTool
  or TraceAndSelectOptions instance in order to compute intermediate
  results (say, for user feedback) or to implement the final
  segmentation editing operation.  This class is split
  from the TraceAndSelectTool so that the operations can be used
  by other code without the need for a view context.
  """

  def __init__(self,sliceLogic):
    self.sliceLogic = sliceLogic
    self.fillMode = 'Plane'

  def apply(self,xy):
    #
    # get the parameters from MRML
    #
    node = EditUtil.EditUtil().getParameterNode()
    print("@@@Tolerance:%s" % node.GetParameter("TraceAndSelect,tolerance"))
    tolerance = float(node.GetParameter("TraceAndSelect,tolerance"))
    print("@@@MaxPixels:%s" % node.GetParameter("TraceAndSelect,maxPixels"))
    maxPixels = float(node.GetParameter("TraceAndSelect,maxPixels"))
    print("@@@PaintOver:%s" % node.GetParameter("TraceAndSelect,paintOver"))
    print("@@@Theshold:%s" % node.GetParameter("LabelEffect,paintThreshold"))
    paintThreshold = int(node.GetParameter("LabelEffect,paintThreshold"))
    print("@@@Theshold Min:%s" % node.GetParameter("LabelEffect,paintThresholdMin"))
    thresholdMin = float(node.GetParameter("LabelEffect,paintThresholdMin"))
    print("@@@Theshold Max:%s" % node.GetParameter("LabelEffect,paintThresholdMax"))
    thresholdMax = float(node.GetParameter("LabelEffect,paintThresholdMax"))

    paintOver = 0

    #
    # get the label and background volume nodes
    #
    labelLogic = self.sliceLogic.GetLabelLayer()
    labelNode = labelLogic.GetVolumeNode()
    backgroundLogic = self.sliceLogic.GetBackgroundLayer()
    backgroundNode = backgroundLogic.GetVolumeNode()

    #
    # get the ijk location of the clicked point
    # by projecting through patient space back into index
    # space of the volume.  Result is sub-pixel, so round it
    # (note: bg and lb will be the same for volumes created
    # by the editor, but can be different if the use selected
    # different bg nodes, but that is not handled here).
    #
    xyToIJK = labelLogic.GetXYToIJKTransform()
    ijkFloat = xyToIJK.TransformDoublePoint(xy+(0,))
    ijk = []
    for element in ijkFloat:
      try:
        intElement = int(round(element))
      except ValueError:
        intElement = 0
      ijk.append(intElement)
    ijk.reverse()
    ijk = tuple(ijk)

    #
    # Get the numpy array for the bg and label
    #
    import vtk.util.numpy_support, numpy
    backgroundImage = backgroundNode.GetImageData()
    labelImage = labelNode.GetImageData()
    shape = list(backgroundImage.GetDimensions())
    shape.reverse()
    backgroundArray = vtk.util.numpy_support.vtk_to_numpy(backgroundImage.GetPointData().GetScalars()).reshape(shape)
    labelArray = vtk.util.numpy_support.vtk_to_numpy(labelImage.GetPointData().GetScalars()).reshape(shape)

    if self.fillMode == 'Plane':
      # select the plane corresponding to current slice orientation
      # for the input volume
      ijkPlane = self.sliceIJKPlane()
      i,j,k = ijk
      if ijkPlane == 'JK':
        backgroundDrawArray = backgroundArray[:,:,k]
        labelDrawArray = labelArray[:,:,k]
        ijk = (i, j)
      if ijkPlane == 'IK':
        backgroundDrawArray = backgroundArray[:,j,:]
        labelDrawArray = labelArray[:,j,:]
        ijk = (i, k)
      if ijkPlane == 'IJ':
        backgroundDrawArray = backgroundArray[i,:,:]
        labelDrawArray = labelArray[i,:,:]
        ijk = (j, k)
    elif self.fillMode == 'Volume':
      backgroundDrawArray = backgroundArray
      labelDrawArray = labelArray


    value = backgroundDrawArray[ijk]
    
    print("@@@location=", ijk)
    print("@@@value=", value)
    if tolerance == 0:
        # DEBUG purposes, testing coordinates etc.
        return
    
    self.undoRedo.saveState()
    label = EditUtil.EditUtil().getLabel()
    if paintThreshold:
      lo = thresholdMin
      hi = thresholdMax
    else:
      lo = value - tolerance
      hi = value + tolerance
    pixelsSet = 0
    
    location = ijk
    offsets = [
        (0, 1),
        (1, 1),
        (1, 0),
        (1, -1),
        (0, -1),
        (-1, -1),
        (-1, 0),
        (-1, 1)
    ]
    #
    # Find edge pixels
    #
    seeds = [None,None,None,None]
    dist = 0
    location = ijk
    labelDrawArray[location] = label
    while None in seeds:
        dist += 1
        for i in range(0, 8, 2):
            if seeds[i/2] is not None:
                # Edge was already found in this direction
                continue
            tmp = (location[0] + dist * offsets[i][0], location[1] + dist * offsets[i][1])
            labelDrawArray[tmp] = label + 1
            # Check if edge
            if is_edge(tmp, hi, lo, backgroundDrawArray):
                labelDrawArray[tmp] = label + 2
                seeds[i/2] = tmp


    #
    # Build path
    #
    print(seeds)
    paths = []
    for seed in seeds:
        repeat = False
        for path in paths:
            if seed in path:
                repeat = True
                break
        if repeat:
            continue
        paths.append(recursive_path_helper(seed, seed, seed, hi, lo, backgroundDrawArray, labelDrawArray, label + 2))
        print(paths[-1])
    """
    # Check if original coordinate is in the enclosed path
    fill_point = ijk
    if not is_inside_path(fill_point, path):
        fill_point = get_point_inside_path(path)
    
    # Fill the path using a recursive search
    toVisit = [fill_point,]
    # Create a map that contains the location of the pixels
    # that have been already visited (added or considered to be added).
    # This is required if paintOver is enabled because then we reconsider
    # all pixels (not just the ones that have not labelled yet).
    if paintOver:
      labelDrawVisitedArray = numpy.zeros(labelDrawArray.shape,dtype='bool')

    while toVisit != []:
      location = toVisit.pop(0)
      try:
        l = labelDrawArray[location]
        b = backgroundDrawArray[location]
      except IndexError:
        continue
      if (not paintOver and l != 0):
        # label filled already and not painting over, leave it alone
        continue
      if (paintOver and l == label):
        # label is the current one, but maybe it was filled with another high/low value,
        # so we have to visit it once (and only once) in this session, too
        if  labelDrawVisitedArray[location]:
          # visited already, so don't try to fill it again
          continue
        else:
          # we'll visit this pixel now, so mark it as visited
          labelDrawVisitedArray[location] = True
      if location in path:
        continue
      labelDrawArray[location] = label
      if l != label:
        # only count those pixels that were changed (to allow step-by-step growing by multiple mouse clicks)
        pixelsSet += 1
      #if pixelsSet > maxPixels:
      #  toVisit = []
      else:
        if self.fillMode == 'Plane':
          # add the 4 neighbors to the stack
          toVisit.append((location[0] - 1, location[1]     ))
          toVisit.append((location[0] + 1, location[1]     ))
          toVisit.append((location[0]    , location[1] - 1 ))
          toVisit.append((location[0]    , location[1] + 1 ))
        elif self.fillMode == 'Volume':
          # add the 6 neighbors to the stack
          toVisit.append((location[0] - 1, location[1]    , location[2]    ))
          toVisit.append((location[0] + 1, location[1]    , location[2]    ))
          toVisit.append((location[0]    , location[1] - 1, location[2]    ))
          toVisit.append((location[0]    , location[1] + 1, location[2]    ))
          toVisit.append((location[0]    , location[1]    , location[2] - 1))
          toVisit.append((location[0]    , location[1]    , location[2] + 1))

    # signal to slicer that the label needs to be updated
    """
    EditUtil.EditUtil().markVolumeNodeAsModified(labelNode)  


def recursive_path_helper(start, prev, location, hi, lo, bgArray, lArray, label):
    """Recursively finds and builds a path that reaches start without revisiting previous pixels."""
    # TODO: Implement a visited array, just in case an edge branches and re-converges with another.
    # Will also want to implement tail recursion or a stack as necessary later on, if still
    # hitting max recursion depth.
    neighbors = []
    offsets = [
        (0, 1),
        (1, 1),
        (1, 0),
        (1, -1),
        (0, -1),
        (-1, -1),
        (-1, 0),
        (-1, 1)
    ]
    for offset in offsets:
        neighbor = (location[0] + offset[0], location[1] + offset[1])
        if neighbor != prev and is_edge(neighbor, hi, lo, bgArray):
            neighbors.append(neighbor)
    if start in neighbors:
        return [location,]
    if len(neighbors) == 0:
        return None
    for neighbor in neighbors:
        lArray[neighbor] = label
        tmp = recursive_path_helper(start, location, neighbor, hi, lo, bgArray, lArray, label)
        if tmp is not None:
            tmp.append(location)
            return tmp
    print("WHAT THE FUCK HAPPENED HERE")
    return []


def is_edge(location, hi, lo, bgArray):
    """Return true is location is an edge pixel."""
    offsets = [
        (0,1),
        (1,0),
        (0,-1),
        (-1,0)
    ]
    # Check that location is within threshold first
    try:
        b = bgArray[location]
    except IndexError:
        return False
    if b < lo or b > hi:
        return False
    
    # Check if its neighbors are outside the threshold
    for offset in offsets:
        tmp = (location[0] + offset[0], location[1] + offset[1])
        try:
            b = bgArray[tmp]
        except IndexError:
            return True
        if b < lo or b > hi:
            return True
    return False

def is_inside_path(location, path):
    """Return true if location is inside path."""
    # Check that location is not in path
    if location in path:
        return False
    intersections = sum(x[0] == location[0] and x[1] < location[1] for x in path)
    return intersections % 2


def get_point_inside_path(path):
    """Return a point inside the path."""
    point = path[0]
    offsets = [
        (0,1),
        (1,0),
        (0,-1),
        (-1,0)
    ]
    for offset in offsets:
        tmp = (point[0] + offset[0], point[1] + offset[1])
        if is_inside_path(tmp, path):
            return tmp

#
# The TraceAndSelect class definition
#

class TraceAndSelectExtension(LabelEffect.LabelEffect):
  """Organizes the Options, Tool, and Logic classes into a single instance
  that can be managed by the EditBox
  """

  def __init__(self):
    # name is used to define the name of the icon image resource (e.g. TraceAndSelect.png)
    self.name = "TraceAndSelect"
    # tool tip is displayed on mouse hover
    self.toolTip = "Paint: circular paint brush for label map editing"

    self.options = TraceAndSelectOptions
    self.tool = TraceAndSelectTool
    self.logic = TraceAndSelectLogic

""" Test:

sw = slicer.app.layoutManager().sliceWidget('Red')
import EditorLib
pet = EditorLib.TraceAndSelectTool(sw)

"""

#
# TraceAndSelect
#

class TraceAndSelect:
  """
  This class is the 'hook' for slicer to detect and recognize the extension
  as a loadable scripted module
  """
  def __init__(self, parent):
    parent.title = "Editor TraceAndSelect Effect"
    parent.categories = ["Developer Tools.Editor Extensions"]
    parent.contributors = ["Steve Pieper (Isomics)"] # insert your name in the list
    parent.helpText = """
    Example of an editor extension.  No module interface here, only in the Editor module
    """
    parent.acknowledgementText = """
    This editor extension was developed by
    stfried, pshultz, gieseker, mthol
    based on work by:
    Steve Pieper, Isomics, Inc.
    based on work by:
    Jean-Christophe Fillion-Robin, Kitware Inc.
    and was partially funded by NIH grant 3P41RR013218.
    """

    # TODO:
    # don't show this module - it only appears in the Editor module
    #parent.hidden = True

    # Add this extension to the editor's list for discovery when the module
    # is created.  Since this module may be discovered before the Editor itself,
    # create the list if it doesn't already exist.
    try:
      slicer.modules.editorExtensions
    except AttributeError:
      slicer.modules.editorExtensions = {}
    slicer.modules.editorExtensions['TraceAndSelect'] = TraceAndSelectExtension

#
# TraceAndSelectWidget
#

class TraceAndSelectWidget:
  def __init__(self, parent = None):
    self.parent = parent

  def setup(self):
    # don't display anything for this widget - it will be hidden anyway
    pass

  def enter(self):
    pass

  def exit(self):
    pass

# Steven wuz here
