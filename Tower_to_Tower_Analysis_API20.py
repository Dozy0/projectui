## Created by: Stats Wong
## Updated by: Kevin Chen
## In order to run this script as QGIS processing fuction save this
## python file in the following directory and restart QGIS
## C:\Users\[your usesrname]\AppData\Roaming\QGIS\QGIS3\profiles\default\processing\scripts

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsSymbol,
                       QgsProject,
                       QgsProcessing,
                       QgsVectorLayer,
                       QgsRendererRange,
                       QgsProcessingUtils,
                       QgsPalLayerSettings,
                       QgsTextBufferSettings,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsSvgMarkerSymbolLayer,
                       QgsGraduatedSymbolRenderer,
                       QgsCoordinateReferenceSystem,
                       QgsVectorLayerSimpleLabeling,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource)
from qgis import processing
from PyQt5 import QtGui
from math import factorial


import requests, sys, os, time, traceback, fnmatch, json, itertools, re
server="https://api.cloudrf.com/path"


class CreateTower2TowerNetworkAlgorithm(QgsProcessingAlgorithm):

    INPUT_T2T = 'input_t2t'
    OUTPUT_T2T = 'output_t2t'

    def initAlgorithm(self, config=None):

        # Add the input vector features source.
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.INPUT_T2T,self.tr('Input Towers Layer'),[QgsProcessing.TypeVectorPoint], defaultValue = '')
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_T2T,self.tr('Output Tower-to-Tower singal strength network (Save to disk)'), type=QgsProcessing.TypeVectorAnyGeometry, defaultValue="output.shp")
        )

    def processAlgorithm(self, parameters, context, model_feedback):

        source_t2t = self.parameterAsSource(parameters,self.INPUT_T2T,context)

        outputs = {}
        results = {}
        headers = {
          'key': '20935-c3f9cd7df51700a2677bf6d42c84bcb0f3372d82'
        }


        try:
            # Compute the number of steps to display within the progress bar and
            # get features from source
            total_steps = source_t2t.featureCount()
            no_of_permutations = int(factorial(total_steps)/factorial(total_steps-2))
            current_step = 0
            feedback = QgsProcessingMultiStepFeedback(no_of_permutations, model_feedback)

            # Identifying the directory of the input source (get the input path)
            source_path = self.parameterDefinition(self.INPUT_T2T).valueAsPythonString(parameters[self.INPUT_T2T], context)
            in_file_path = source_path.split("'")[1]
            feedback.pushInfo("{}\n".format(in_file_path))

            # Identifying the directory of the output source
            out_spoke_path = self.parameterDefinition(self.OUTPUT_T2T).valueAsPythonString(parameters[self.OUTPUT_T2T], context).strip("'")
            output_csv_path = "{}/T2T_pathprofile.csv".format(os.path.dirname(in_file_path))
            feedback.pushInfo("{}\n".format(out_spoke_path))


            # Generate a dictionary for each row of data and a list of all data entries, (see Stats Create Tower Network)
            field_names = [field.name() for field in source_t2t.fields()] # Store the INPUT_T2T field names
            attribute_list = []
            for element in source_t2t.getFeatures():
                dict_value = dict(zip(field_names, element.attributes()))  # Create dictionary which has INPUT_T2T's fields and attributes
                attribute_list.append(dict_value) # save to a attribute_list

            # calculates the permutations pairs from the list of all data entries
            # coresponding dictionary for each permutation is generated
            # and used to make CloudRF API requests and outputs a csv of the requested data
            with open(output_csv_path, 'w') as output_csv: # create a csv with the 6 fields
                line = 'UID,Order,lat,lon,signal_str,png\n'
                output_csv.write(line)
                for per in itertools.permutations(attribute_list,2): #"""each pair has the data dictionary"""
                    current_step += 1
                    start_time = time.time()

                    OBJECTID = per[0]['site'] + " - " + per[1]['site']
                    feedback.pushInfo('Processing {}/{} permutations: {}'.format(current_step,no_of_permutations,OBJECTID))

                    # Transmitter Dict
                    dict_value = per[0]

                    # Receiver Dict
                    dict_Para = per[1]

                    # Reformat to make it compatible with API2.0
                    dict_value['transmitter'] = {'lat': dict_value['tlat'], 'lon': dict_value['tlon'], 'alt': dict_value['talt'], 'frq': dict_value['frq'], 'txw': dict_value['txw'], 'bwi': dict_value['bwi']}
                    dict_Para['receiver'] = {'lat': dict_Para['tlat'], 'lon': dict_Para['tlon'], 'alt': dict_Para['talt'], 'rxg': dict_Para['rxg'], 'rxs': dict_Para['rxs']}
                    dict_value['antenna'] = {'txg': dict_value['txg'], 'txl': dict_value['txl'], 'ant': dict_value['ant'], 'azi': dict_value['azi'], 'tlt': dict_value['tlt'], 'hbw': dict_value['hbw'], 'vbw': dict_value['vbw'], 'pol': dict_value['pol']}
                    dict_value['model'] = {'pm': dict_value['pm'], 'pe': dict_value['pe'], 'cli': dict_value['cli'], 'ked': dict_value['ked'], 'rel': dict_value['rel'], 'ter': dict_value['ter']}
                    dict_value['environment'] = {'clm': dict_value['clm'], 'cll': dict_value['cll'], 'mat': dict_value['mat']}
                    dict_value['output'] = {'units': dict_value['units'], 'col': dict_value['col'], 'out': dict_value['out'], 'ber': dict_value['ber'], 'mod': dict_value['mod'], 'nf': dict_value['nf'], 'res': dict_value['res'], 'rad': dict_value['rad']}

                    newDict = {'site': dict_value['site'], 'network': dict_value['network'], 'transmitter': dict_value['transmitter'], 'antenna': dict_value['antenna'], 'receiver': dict_Para['receiver'],'model': dict_value['model'],'environment': dict_value['environment'],'output': dict_value['output']}
                    finalDict = json.dumps(newDict)

                    api_response = requests.request("POST", server, headers=headers, data=finalDict)
                    api_data = json.loads(api_response.text)
                    error = api_data.get('error')

                    # add a condition to request lower resolution result if there is an error
                    if error is None:
                      feedback.pushInfo("Requesting 2 metres resolution results")
                    else:
                      feedback.pushInfo("Requesting 30 metres resolution results")
                      dict_value['output'] = {'units': dict_value['units'], 'col': dict_value['col'], 'out': dict_value['out'], 'ber': dict_value['ber'], 'mod': dict_value['mod'], 'nf': dict_value['nf'], 'res': 30, 'rad': 30}
                      lowDict = {'site': dict_value['site'], 'network': dict_value['network'], 'transmitter': dict_value['transmitter'], 'antenna': dict_value['antenna'], 'receiver': dict_Para['receiver'],'model': dict_value['model'],'environment': dict_value['environment'],'output': dict_value['output']}
                      SecDict = json.dumps(lowDict)
                      api_response_low = requests.request("POST", server, headers=headers, data=SecDict)
                      api_data = json.loads(api_response_low.text)


                    png = api_data.get('Chart image')
                    sig_str = api_data.get('Transmitters')[0].get('Signal power at receiver dBm')

                    line = '{},0,{},{},{},{}\n{},1,{},{},{},{}\n'.format(OBJECTID, per[0]['tlat'], per[0]['tlon'], sig_str, png, OBJECTID, per[1]['tlat'], per[1]['tlon'], sig_str, png)
                    output_csv.write(line)

                    elapsed = round(time.time() - start_time,1)
                    feedback.pushInfo('Elapsed: {} seconds\n'.format(elapsed))
                    feedback.setCurrentStep(current_step)
                    if feedback.isCanceled():
                        return {}
                    time.sleep(1)

            # load in csv as a point layer file in QGIS
            uri = r"file:///{}?delimiter=,&crs=epsg:4326&xField=lon&yField=lat".format(output_csv_path)
            P2P_csv_layer = QgsVectorLayer(uri,"T2T_csv_layer", "delimitedtext")

            # Converts points coordinate to lines based on order and groupings
            alg_params = {
                'INPUT': P2P_csv_layer,
                'CLOSE_PATH':False,
                'ORDER_EXPRESSION':'\"Order\"',
                'NATURAL_SORT':False,
                'GROUP_EXPRESSION':'\"UID\"',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }

            outputs['PointstoPath'] = processing.run("native:pointstopath", alg_params, context=context, feedback = feedback, is_child_algorithm=False)

            # Join the output lines with the corresponding data entries in the csv layer
            alg_params = {
                'INPUT' : outputs['PointstoPath']['OUTPUT'],
                'FIELD' : 'UID',
                'INPUT_2' : P2P_csv_layer,
                'FIELD_2' : 'UID',
                'FIELDS_TO_COPY':['signal_str','png'],
                'OUTPUT' : parameters[self.OUTPUT_T2T]
            }
            outputs['JoinT2TFields'] = processing.run('qgis:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            results[self.OUTPUT_T2T] = outputs['JoinT2TFields']['OUTPUT']

            # Defining field name for column to be analyzed and color ranges for signal strenth thresholds
            ranges = []
            t_dBm = -80

            myMin1 = float(t_dBm)
            myMax1 = 0
            myLabel1 = 'Signals stronger than {} dBm'.format(t_dBm)
            myColor1 = QtGui.QColor('#803d91')
            ranges.append((myMin1, myMax1, myLabel1, myColor1))

            myMin2 = float(t_dBm)-20
            myMax2 = float(t_dBm)-0.001
            myLabel2 = 'Marginal signals between {} to {} dBm'.format(myMax2, myMin2)
            myColor2 = QtGui.QColor('#d0bcdb')
            ranges.append((myMin2, myMax2, myLabel2, myColor2))

            myMin3 = -1000
            myMax3 = float(t_dBm)-20.000000000000001
            myLabel3 = 'Signals weaker than {} dBm'.format(myMax3)
            myColor3 = QtGui.QColor('#f7fbff')
            ranges.append((myMin3, myMax3, myLabel3, myColor3))

            # Style Spokes layer to meet threshold of signal strength
            spokes_layer = QgsProcessingUtils.mapLayerFromString(outputs['JoinT2TFields']['OUTPUT'], context)
            myRangeList = []

            for myMin, myMax, myLabel, myColor in ranges:
              mySymbol = QgsSymbol.defaultSymbol(spokes_layer.geometryType())
              mySymbol.setColor(myColor)
              mySymbol.setWidth(.5)
              myRange = QgsRendererRange(myMin, myMax, mySymbol, myLabel)
              myRangeList.append(myRange)

            myRenderer = QgsGraduatedSymbolRenderer('', myRangeList)
            myRenderer.setClassAttribute("signal_str")
            spokes_layer.setRenderer(myRenderer)
            spokes_layer.triggerRepaint()

            # Create map tip to display Path Profile chart from cloudRF
            expression = """<img src = "[% "png" %]" width="600" />"""
            spokes_layer.setMapTipTemplate(expression)

            # Setting labels for Signal Strength

            layer_settings  = QgsPalLayerSettings()
            layer_settings.fieldName = "signal_str"
            layer_settings.enabled = True
            layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)

            buffer_settings = QgsTextBufferSettings()
            buffer_settings.setEnabled(True)
            buffer_settings.setSize(1)
            buffer_settings.setColor(QtGui.QColor('white'))

            spokes_layer.setLabelsEnabled(True)
            spokes_layer.setLabeling(layer_settings)
            spokes_layer.triggerRepaint()

            # Save layer styles for auto styling upon being loaded
            spokes_style = out_spoke_path.rsplit('.',1)[0] + '.qml'
            spokes_layer.saveNamedStyle(spokes_style)

            return results

        except:
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            # information concerning the error
            pymsg = "PYTHON ERRORS:\nTraceback info:\n{}\nError Info:\n{}".format(tbinfo, str(sys.exc_info()[1]))
            # AddMessage Python error messages for use in QGIS
            feedback.pushInfo('{}'.format(pymsg))


    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CreateTower2TowerNetworkAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm.
        Names should containlowercase alphanumeric characters only and
        no spaces or other formatting characters.
        """
        return 'tower_to_tower_analysis'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Tower to Tower Connectivity Analysis API 2.0')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr('')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. Group id
        should contain lowercase alphanumeric characters only and no spaces or
        other formatting characters.
        """
        return ''

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr("This algorithm calculates the number of permutations of Tower-to-Tower connections within a network and generates all the signal strength permutations by making Path Profile API requests to CloudRF. \n\
        NOTE: This algorithm takes in a tower layer that contains all the necessary parameters as identfied by the Path Profile API docs found on:\n\
        https://api.cloudrf.com\n\
        It was modified to make it compatible with API2.0 to use the high-resolution DSM. CloudRF only supports 1m or 2m resolution up to a limited radius. This script adds a condition that will automatically change to 30m resolution if a huge radius is requested.\n\
        Created by: Stats Wong\n\
        Updated by: Kevin Chen")
