## Created by: Stats Wong
## Modified by: Kevin Chen
## In order to run this script as QGIS processing fuction save this
## python file in the following directory and restart QGIS
## C:\Users\Kevin\AppData\Roaming\QGIS\QGIS3\profiles\default\processing\scripts

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProject,
                       QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsCoordinateReferenceSystem,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource)
from qgis import processing
from PyQt5 import QtGui

import requests, sys, os, time, traceback, fnmatch, json
server="https://api.cloudrf.com/area"

class CreateUpdateRFNetworkAlgorithm(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):

        # We add the input vector features source. It can have any kind of geometry.
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.INPUT,self.tr('Input Towers Layer'),[QgsProcessing.TypeVectorPoint], defaultValue = '')
        )

    def processAlgorithm(self, parameters, context, model_feedback):

        source = self.parameterAsSource(parameters,self.INPUT,context)
        results = {}
        try:
            # Compute the number of steps to display within the progress bar and
            # get features from source
            total_source_features = source.featureCount() # number of features
            total_steps = total_source_features
            current_step = 0
            feedback = QgsProcessingMultiStepFeedback(total_steps, model_feedback)

            field_names = [field.name() for field in source.fields()] # Store all field names in a list

            for element in source.getFeatures():
                start_time = time.time()
                dict_value = dict(zip(field_names, element.attributes())) # Create dictionary fields and attributes

                # Reformat to make it compatible with API2.0
                dict_value['transmitter'] = {'lat': dict_value['tlat'], 'lon': dict_value['tlon'], 'alt': dict_value['talt'], 'frq': dict_value['frq'], 'txw': dict_value['txw'], 'bwi': dict_value['bwi']}
                dict_value['receiver'] = {'lat': dict_value['rlat'], 'lon': dict_value['rlon'], 'alt': dict_value['ralt'], 'rxg': dict_value['rxg'], 'rxs': dict_value['rxs'], 'bwi': dict_value['bwi']}
                dict_value['antenna'] = {'txg': dict_value['txg'], 'txl': dict_value['txl'], 'ant': dict_value['ant'], 'azi': dict_value['azi'], 'tlt': dict_value['tlt'], 'hbw': dict_value['hbw'], 'vbw': dict_value['vbw'], 'pol': dict_value['pol']}
                dict_value['model'] = {'pm': dict_value['pm'], 'pe': dict_value['pe'], 'cli': dict_value['cli'], 'ked': dict_value['ked'], 'rel': dict_value['rel'], 'ter': dict_value['ter']}
                dict_value['environment'] = {'clm': dict_value['clm'], 'cll': dict_value['cll'], 'mat': dict_value['mat']}
                dict_value['output'] = {'units': dict_value['units'], 'col': dict_value['col'], 'out': dict_value['out'], 'ber': dict_value['ber'], 'mod': dict_value['mod'], 'nf': dict_value['nf'], 'res': dict_value['res'], 'rad': dict_value['rad']}

                newDict = {'site': dict_value['site'], 'network': dict_value['network'], 'transmitter': dict_value['transmitter'],'receiver': dict_value['receiver'],'antenna': dict_value['antenna'],'model': dict_value['model'],'environment': dict_value['environment'],'output': dict_value['output']}
                finalDict = json.dumps(newDict)

                feedback.pushInfo('Tower generation time may take up to 90 seconds or more for the request to be completed\nMaking CloudRF API request to generate {} tower...\n'.format(dict_value['site']))

                headers = {
                  'key': '20935-c3f9cd7df51700a2677bf6d42c84bcb0f3372d82'
                }
                api_response = requests.request("POST", server, headers=headers, data=finalDict) # change to API 2.0
                api_data = json.loads(api_response.text)

                feedback.pushInfo('Area: {}\nCoverage: {}\n'.format(api_data['area'],api_data['coverage']))

                elapsed = round(time.time() - start_time,1)
                feedback.pushInfo('Elapsed: {} seconds\n'.format(elapsed))

                current_step += 1
                feedback.setCurrentStep(current_step)
                if feedback.isCanceled():
                    return {}
                time.sleep(2)

            feedback.pushInfo('\n\nNOTE:Check the your CloudRF network to verify towers have been created\n\n')

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
        return CreateUpdateRFNetworkAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm.
        Names should containlowercase alphanumeric characters only and
        no spaces or other formatting characters.
        """
        return 'create_rf_tower_network'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Create/Update CloudRF Tower Network API 2.0')

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
    # instructions
    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr("This algorithm uses the attribute fields of the input layer to make CloudRF API request to generate towers under the specified network field 'network' from the layer attribute field.\n\
        It was modified to make it compatible with API2.0 to use the high-resolution DSM.\n\
        TO CREATE a new network: Select the corresponding tower layer and click Run.\n\
        TO UPDATE an existing network:\n\
        Step 1: Go to your cloudrf.com account and delete the towers to be updated from the corresponding network, otherwise the old towers will still exist in that network when performing other analysis that uses that network.\n\
        Step 2: IF tower locations were EDITED/MOVED, the corresponding coordinate data in the attribute fields are NOT dynamically updated and NEED to be updated. Use the field calculator from the attribute table to 'Update existing field' for the 'tlat' and 'tlon' field with '$y' and '$x' respectively.\n\
        Step 3: ENSURE that the exact towers to be updated are selected in the layer and check off the 'Selected features only' checkbox, otherwise the algorithm will create all towers in the selected layer. (If checkbox is greyed out, no features have been selected for the layer)\n\
        DOCUMENTATION:\n https://cloud-rf.github.io/documentation/developer/swagger-ui/\n\
        Created by: Stats Wong\n\
        Updated by: Kevin Chen")
