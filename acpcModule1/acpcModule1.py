# Align an image to ACPC coordinates
# David Brandman, July 2021

# This code is heavily based on the script found here:
# https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html
# And from the default script provided in some online tutorials.

# The code works as follows:
# 1. User supplies a Markup with 3 points, in the following order:
#     1) AC
#     2) PC
#     3) A point in the midline
# 2. The user opens the acpcModule, and then selects this Markup and the T1 volume. The volume is then
# aligned such that the MCP is the (0,0,0) coordinate. 

import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np

def getMatrixToACPC(ac, pc, ih):

  # Anteroposterior axis
  pcAc = ac - pc # Vector of acpc direction
  yAxis = pcAc / np.linalg.norm(pcAc) # Unit vector of pcAc

  # Lateral axis
  acIhDir = ih - ac #  Vector in direction of ac ih
  xAxis = np.cross(yAxis, acIhDir) # cross product, so it's x axis
  xAxis /= np.linalg.norm(xAxis) # norm of x axis

  # Rostrocaudal axis
  zAxis = np.cross(xAxis, yAxis) #why? Because acIhDir isn't exactly z axis only

  # Rotation matrix
  rotation = np.vstack([xAxis, yAxis, zAxis])
  # AC in rotated space

  # This code is changed from the script repository. The default code moves it to AC, whereas
  # we want the origin to be at MCP. As such we need to offset it by half the pcAc distance
  translation = -np.dot(rotation, ac - (np.dot(yAxis, 0.5*np.linalg.norm(pcAc))))

  # This is the original code
  # translation = -np.dot(rotation, ac) 

  # Build homogeneous matrix
  matrix = np.eye(4)
  matrix[:3, :3] = rotation
  matrix[:3, 3] = translation
  return matrix



#
# acpcModule1
#

class acpcModule1(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ACPC Alignment" # TODO make this more human readable by adding spaces
    self.parent.categories = ["ACPC Alignment"]
    self.parent.dependencies = []
    self.parent.contributors = ["David Brandman"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
Align the brain to ACPC space, where the MCP is the origin. The specified Markups data requires the points in the following order: (1) AC, (2) PC, (3) A point in the midline. 
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
    Based on the code provided in the script_repository (https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html)
""" 

#
# acpcModule1Widget
#

class acpcModule1Widget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #### Choose Fiducial - Section
    #### Select box ComboBox -
    self.acpcSelector = slicer.qMRMLNodeComboBox()
    self.acpcSelector.nodeTypes = ["vtkMRMLMarkupsFiducialNode"]
    self.acpcSelector.selectNodeUponCreation = True
    self.acpcSelector.addEnabled = False
    self.acpcSelector.removeEnabled = False
    self.acpcSelector.noneEnabled = False
    self.acpcSelector.showHidden = False
    self.acpcSelector.showChildNodeTypes = False
    self.acpcSelector.setMRMLScene( slicer.mrmlScene )
    self.acpcSelector.setToolTip( "Pick a markup to use" )
    parametersFormLayout.addRow("ACPC coordinates:", self.acpcSelector)

    #
    # input volume selector
    #
    self.volumeSelector = slicer.qMRMLNodeComboBox()
    self.volumeSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    self.volumeSelector.selectNodeUponCreation = True
    self.volumeSelector.addEnabled = False
    self.volumeSelector.removeEnabled = False
    self.volumeSelector.noneEnabled = False
    self.volumeSelector.showHidden = False
    self.volumeSelector.showChildNodeTypes = False
    self.volumeSelector.setMRMLScene( slicer.mrmlScene )
    self.volumeSelector.setToolTip( "Pick the input to the algorithm." )
    parametersFormLayout.addRow("Input Volume: ", self.volumeSelector)

    #
    # output volume selector
    #
    self.outputSelector = slicer.qMRMLNodeComboBox()
    self.outputSelector.nodeTypes = ["vtkMRMLTransformNode"]
    self.outputSelector.selectNodeUponCreation = True
    self.outputSelector.addEnabled = True
    self.outputSelector.removeEnabled = True
    self.outputSelector.noneEnabled = False
    self.outputSelector.renameEnabled = True
    self.outputSelector.showHidden = False
    self.outputSelector.showChildNodeTypes = False
    self.outputSelector.setMRMLScene( slicer.mrmlScene )
    self.outputSelector.setToolTip( "Pick the output Transform" )
    parametersFormLayout.addRow("Output Transform: ", self.outputSelector)

    #
    # check box to automatically harden transforms
    #
    self.enableAutoHarden = qt.QCheckBox()
    self.enableAutoHarden.checked = 1
    self.enableAutoHarden.setToolTip("If checked, then automatically harden transform")
    parametersFormLayout.addRow("Automatically harden transforms", self.enableAutoHarden)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = True
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.volumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.acpcSelector.currentNode() and self.volumeSelector.currentNode()

  def onApplyButton(self):
    logic = myLogic()
    logic.run(acpcFid = self.acpcSelector.currentNode(), volumeNode=self.volumeSelector.currentNode(), transformNode = self.outputSelector.currentNode(), autoHarden = self.enableAutoHarden.checked)

class myLogic(ScriptedLoadableModuleLogic):

  def run(self, acpcFid, volumeNode, transformNode, autoHarden=False):

    # This is incredibly annoying and I don't know why it needs to be done this way but it does
    # I tried running this using a loop, but I couldn't get it to work. 
    for i in range(acpcFid.GetNumberOfFiducials()):
      ras = [0,0,0]
      acpcFid.GetNthFiducialPosition(i,ras)
      if i == 0:
        ac = np.array(ras)
      if i == 1:
        pc = np.array(ras)
      if i == 2:
        ih = np.array(ras)

    # Translate the matrix to vtkMatrix
    matrix = getMatrixToACPC(ac, pc, ih)
    vtkMatrix = vtk.vtkMatrix4x4()
    for row in range(4):
        for col in range(4):
            vtkMatrix.SetElement(row, col, matrix[row, col])

    # Apply transformation
    transformNode.SetAndObserveMatrixTransformToParent(vtkMatrix)
    
    # Apply transform to volume node and markups node
    acpcFid.SetAndObserveTransformNodeID(transformNode.GetID())
    volumeNode.SetAndObserveTransformNodeID(transformNode.GetID())

    if autoHarden:
      logic = slicer.vtkSlicerTransformLogic()
      logic.hardenTransform(acpcFid)
      logic.hardenTransform(volumeNode)






#
# acpcModule1Logic
#

#class acpcModule1Logic(ScriptedLoadableModuleLogic):
#  """This class should implement all the actual
#  computation done by your module.  The interface
#  should be such that other python code can import
#  this class and make use of the functionality without
#  requiring an instance of the Widget.
#  Uses ScriptedLoadableModuleLogic base class, available at:
#  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
#  """

#  def hasImageData(self,volumeNode):
#    """This is an example logic method that
#    returns true if the passed in volume
#    node has valid image data
#    """
#    if not volumeNode:
#      logging.debug('hasImageData failed: no volume node')
#      return False
#    if volumeNode.GetImageData() is None:
#      logging.debug('hasImageData failed: no image data in volume node')
#      return False
#    return True

#  def isValidInputOutputData(self, inputVolumeNode, outputVolumeNode):
#    """Validates if the output is not the same as input
#    """
#    if not inputVolumeNode:
#      logging.debug('isValidInputOutputData failed: no input volume node defined')
#      return False
#    if not outputVolumeNode:
#      logging.debug('isValidInputOutputData failed: no output volume node defined')
#      return False
#    if inputVolumeNode.GetID()==outputVolumeNode.GetID():
#      logging.debug('isValidInputOutputData failed: input and output volume is the same. Create a new volume for output to avoid this error.')
#      return False
#    return True

#  def run(self, inputVolume, outputVolume, imageThreshold, enableScreenshots=0):
#    """
#    Run the actual algorithm
#    """

#    if not self.isValidInputOutputData(inputVolume, outputVolume):
#      slicer.util.errorDisplay('Input volume is the same as output volume. Choose a different output volume.')
#      return False

#    logging.info('Processing started')

#    # Compute the thresholded output volume using the Threshold Scalar Volume CLI module
#    cliParams = {'InputVolume': inputVolume.GetID(), 'OutputVolume': outputVolume.GetID(), 'ThresholdValue' : imageThreshold, 'ThresholdType' : 'Above'}
#    cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True)

#    # Capture screenshot
#    if enableScreenshots:
#      self.takeScreenshot('acpcModule1Test-Start','MyScreenshot',-1)

#    logging.info('Processing completed')

#    return True


#class acpcModule1Test(ScriptedLoadableModuleTest):
#  """
#  This is the test case for your scripted module.
#  Uses ScriptedLoadableModuleTest base class, available at:
#  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
#  """

#  def setUp(self):
#    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
#    """
#    slicer.mrmlScene.Clear(0)

#  def runTest(self):
#    """Run as few or as many tests as needed here.
#    """
#    self.setUp()
#    self.test_acpcModule11()

#  def test_acpcModule11(self):
#    """ Ideally you should have several levels of tests.  At the lowest level
#    tests should exercise the functionality of the logic with different inputs
#    (both valid and invalid).  At higher levels your tests should emulate the
#    way the user would interact with your code and confirm that it still works
#    the way you intended.
#    One of the most important features of the tests is that it should alert other
#    developers when their changes will have an impact on the behavior of your
#    module.  For example, if a developer removes a feature that you depend on,
#    your test should break so they know that the feature is needed.
#    """

#    self.delayDisplay("Starting the test")
#    #
#    # first, get some data
#    #
#    import SampleData
#    SampleData.downloadFromURL(
#      nodeNames='FA',
#      fileNames='FA.nrrd',
#      uris='http://slicer.kitware.com/midas3/download?items=5767')
#    self.delayDisplay('Finished with download and loading')

#    volumeNode = slicer.util.getNode(pattern="FA")
#    logic = acpcModule1Logic()
#    self.assertIsNotNone( logic.hasImageData(volumeNode) )
#    self.delayDisplay('Test passed!')
