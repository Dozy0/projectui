## Created by: Stats Wong
## In order to run this script as QGIS processing fuction save this
## python file in the following directory and restart QGIS
## C:\Users\[your usesrname]\AppData\Roaming\QGIS\QGIS3\profiles\default\processing\scripts

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsSymbol,
                       QgsProject,
                       QgsProcessing,
                       QgsRendererRange,
                       QgsProcessingUtils,
                       QgsPalLayerSettings,
                       QgsTextBufferSettings,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsSvgMarkerSymbolLayer,
                       QgsGraduatedSymbolRenderer,
                       QgsProcessingParameterField,
                       QgsProcessingParameterString,
                       QgsCoordinateReferenceSystem,
                       QgsVectorLayerSimpleLabeling,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource)
from qgis import processing
from PyQt5 import QtGui
from pathlib import Path

import requests, csv, sys, os, time, json, glob, traceback, fnmatch, shutil

# server="https://cloudrf.com"
# strictSSL=True

class BestSignalProcessingAlgorithm(QgsProcessingAlgorithm):

    INPUT_CIVICS = 'input_civics'
    CIVIC_FIELD = 'civic_field'
    NETWORK = 'network'
    T_DBM = 't_dbm'
    UID = 'uid'
    KEY = 'key'
    RXH = 'rxh'
    RXG = 'rxg'
    ANT = 'ant'
    RES = 'res'
    OUTPUT_CIVICS = 'output_civics'
    OUTPUT_TOWERS = 'output_towers'
    OUTPUT_SPOKES = 'output_spokes'


    # Remove Default values for INPUT, API Key, UID, ANT, OUTPUT
    def initAlgorithm(self, config=None):
        # We add the input vector point features source.
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.INPUT_CIVICS, self.tr('Input civic point layer'),[QgsProcessing.TypeVectorPoint],defaultValue='')
        )
        self.addParameter(
            QgsProcessingParameterField(self.CIVIC_FIELD,'Unique Civic Identifier','OBJECTID',self.INPUT_CIVICS)
        )
        self.addParameter(
            QgsProcessingParameterString(self.NETWORK,'Network name from CloudRF to test for coverage with (i.e. LTE_Pictou)')
        )

        adv_param = QgsProcessingParameterString(self.T_DBM,'Threshold signal strength in dBm (i.e. -65)','-65')
        adv_param.setFlags(adv_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(adv_param)

        adv_param = QgsProcessingParameterString(self.UID,'CloudRF UserID','20935')
        adv_param.setFlags(adv_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(adv_param)

        adv_param = QgsProcessingParameterString(self.KEY,'CloudRF API Key','c3f9cd7df51700a2677bf6d42c84bcb0f3372d82')
        adv_param.setFlags(adv_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(adv_param)

        # adv_param = QgsProcessingParameterString(self.RXH,'Receiver height in metres above ground level','8')
        # adv_param.setFlags(adv_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        # self.addParameter(adv_param)

        # adv_param = QgsProcessingParameterString(self.RXG,'Receiver gain in dBi','8')
        # adv_param.setFlags(adv_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        # self.addParameter(adv_param)

        # adv_param = QgsProcessingParameterString(self.ANT,'Antenna ID for antenna model mounted on tower','26395')
        # adv_param.setFlags(adv_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        # self.addParameter(adv_param)

        adv_param = QgsProcessingParameterString(self.RES,'Raster resolution of the area on interest in meters','30')
        adv_param.setFlags(adv_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(adv_param)

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_CIVICS,self.tr('Civics with signal strength data'), type=QgsProcessing.TypeVectorAnyGeometry, defaultValue="")
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_TOWERS, 'Radio network tower locations', type=QgsProcessing.TypeVectorAnyGeometry, defaultValue="")
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_SPOKES, 'Spokes from each civic to best tower location', type=QgsProcessing.TypeVectorAnyGeometry, defaultValue="")
        )

    def processAlgorithm(self, parameters, context, model_feedback):

        source_civic = self.parameterAsSource(parameters,self.INPUT_CIVICS,context)
        network = self.parameterAsString(parameters,self.NETWORK,context)
        t_dbm = self.parameterAsString(parameters,self.T_DBM,context)
        uid = self.parameterAsString(parameters,self.UID,context)
        key = self.parameterAsString(parameters,self.KEY,context)
        rxh = self.parameterAsString(parameters,self.RXH,context)
        rxg = self.parameterAsString(parameters,self.RXG,context)
        ant = self.parameterAsString(parameters,self.ANT,context)
        res = self.parameterAsString(parameters,self.RES,context)

        outputs = {}
        results = {}

        try:
            # Compute the number of steps to display within the progress bar and
            # get features from source
            total_source_features = source_civic.featureCount()
            total_steps = 9 + total_source_features + (total_source_features//10)
            current_step = 0
            feedback = QgsProcessingMultiStepFeedback(total_steps, model_feedback)

            source_path = self.parameterDefinition(self.INPUT_CIVICS).valueAsPythonString(parameters[self.INPUT_CIVICS], context).strip("'")
            out_civic_path = self.parameterDefinition(self.OUTPUT_CIVICS).valueAsPythonString(parameters[self.OUTPUT_CIVICS], context).strip("'")
            out_tower_path = self.parameterDefinition(self.OUTPUT_TOWERS).valueAsPythonString(parameters[self.OUTPUT_TOWERS], context).strip("'")
            out_spoke_path = self.parameterDefinition(self.OUTPUT_SPOKES).valueAsPythonString(parameters[self.OUTPUT_SPOKES], context).strip("'")

            directory = os.path.dirname(out_civic_path)
            feedback.pushInfo(directory)

            civic_basename = os.path.splitext(os.path.basename(out_civic_path))[0]
            tower_basename = os.path.splitext(os.path.basename(out_tower_path))[0]
            spoke_basename = os.path.splitext(os.path.basename(out_spoke_path))[0]

            # Creating data folder to store resquested API data
            feedback.pushInfo('Creating {} data folder...'.format(spoke_basename))
            data_folder = '{}{}{}_data'.format(directory,os.sep,spoke_basename)
            if not os.path.exists(data_folder):
            		os.makedirs(data_folder)

            current_step += 1
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            time.sleep(.25)

            # check if the name of output layer exsist in the current project if so remove it
            project = QgsProject.instance()
            output_files = [out_civic_path,out_tower_path,out_spoke_path]
            layer_list = [civic_basename,tower_basename,spoke_basename]
            if project.mapLayersByName(civic_basename) or project.mapLayersByName(tower_basename) or project.mapLayersByName(spoke_basename):
                for index in range(len(layer_list)):
                    if project.mapLayersByName(layer_list[index]):
                        feedback.pushInfo('Removing {} layer from project to prevent file lock...'.format(layer_list[index]))
                        project.removeMapLayer(project.mapLayersByName(layer_list[index])[0].id())
                # wait time for remove to finish or else file will be locked
                time.sleep(1)

            current_step += 1
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            time.sleep(.25)

            # Reproject input civics layer to WGS84 for lat lon coordinates
            feedback.pushInfo('Reprojecting input layer to CRS:WGS84...')
            alg_params = {
                'INPUT' : parameters[self.INPUT_CIVICS],
                'TARGET_CRS' : 'EPSG:4326',
                'OUTPUT' : QgsProcessing.TEMPORARY_OUTPUT
            }

            outputs['Reproject'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback,is_child_algorithm=False)

            current_step += 1
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            time.sleep(.25)

            # Iterate through the reprojected civics to write a CSV to be passed to
            # CloudRF best server API requests
            feedback.pushInfo('Generating CSV for CloudRF Best Server API request...')
            features = outputs['Reproject']['OUTPUT'].getFeatures()
            csv_path = '{}{}{}_civics.csv'.format(data_folder,os.sep,civic_basename)

            list_of_fields = outputs['Reproject']['OUTPUT'].fields().names()

            with open(csv_path,'w') as output_csv:
                line = 'civic,uid,key,rxh,rxg,net,lat,lon\n'
                output_csv.write(line)
                for feat in features:
                    if isinstance(feat[parameters[self.CIVIC_FIELD]], str):
                        civic_ID = feat[parameters[self.CIVIC_FIELD]].replace('(','').replace(')','').replace('"','')
                    else:
                        civic_ID = feat[parameters[self.CIVIC_FIELD]]
                    if feat.geometry().isMultipart():
                        ptWGS = feat.geometry().asMultiPoint()[0]
                    else:
                        ptWGS = feat.geometry().asPoint()
                    line = '{},{},{},{},{},{},{},{}'.format(civic_ID,uid,key,rxh,rxg,network, ptWGS.y(),ptWGS.x())
                    line += '\n'
                    output_csv.write(line)

            current_step += 1
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            time.sleep(.25)

            # Creating subfolder to store all JSON data for each civic API request
            csvfile = csv.DictReader(open(csv_path))
            interestedrow = [row for idx, row in enumerate(csvfile) if idx >= 0]
            network_name = interestedrow[0]['net']
            feedback.pushInfo('Creating {} folder to store civic JSON files...'.format(network_name))
            best_path = "{}{}{}_best_signal".format(data_folder,os.sep,network_name)
            if not os.path.exists(best_path):
            		os.makedirs(best_path)

            current_step += 1
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            time.sleep(.25)

            # Iterating through the civic CSV to make CloudRF best server request
            opened_csv = open(csv_path)
            try:
                csvfile = csv.DictReader(opened_csv)
                n = 0
                for row in csvfile:
                    n += 1
                    global server
                    json_path = best_path+os.sep+row.get('civic')+'.json'
                    try:
                        if os.path.exists(json_path) and os.stat(json_path).st_size > 500:
                            feedback.pushInfo('JSON file exists for Property ID: {} ({}/{})'.format(row['civic'],n,total_source_features))
                        else:
                            feedback.pushInfo('Requesting best signal for Property ID: {} ({}/{})'.format(row['civic'],n,total_source_features))
                            filename = open(json_path,"wb")
                            req = requests.post(server+"/API/network/index.php", data=row,verify=strictSSL)
                            time.sleep(.25)
                            filename.write(req.content)
                            filename.close()

                        current_step += 1
                        feedback.setCurrentStep(current_step)
                        if feedback.isCanceled():
                            return {}
                        # feedback.pushInfo(req.content)
                    except Exception:
                        tb = sys.exc_info()[2]
                        tbinfo = traceback.format_tb(tb)[0]
                        # information concerning the error
                        pymsg = "PYTHON ERRORS:\nTraceback info:\n{}\nError Info:\n{}".format(tbinfo, str(sys.exc_info()[1]))
                        # AddMessage Python error messages for use in QGIS
                        feedback.pushInfo('{}'.format(pymsg))
                        continue
            finally:
                opened_csv.close()

            # Generating CSV file of unique towers and civics with signal strength
            # from the 5 best nearby towers
            os.chdir(best_path)
            unique_towers = {}

            unique_tower_csv = data_folder+os.sep+network_name+'_towers.csv'
            unique_tower_csvt = data_folder+os.sep+network_name+'_towers.csvt'
            net_str_csv = data_folder+os.sep+network_name+'_civics_signal_strength.csv'
            net_str_csv_format = data_folder+os.sep+network_name+'_civics_signal_strength.csvt'

            # Create a .csvt file to allow QGIS to associate field types with coresponding
            # csv file to enable joining with (shape)files with matching field types
            feedback.pushInfo('Creating a CSV of civics with the best associated signal strength...')
            civic_field_type = source_civic.fields().field(parameters[self.CIVIC_FIELD]).typeName()
            with open(net_str_csv_format,'w') as format_csv:
                line = '"{}","Real","Real","Real","String","Real","String","String","Real","Real","Real","String","Real","String","String","Real","Real","Real"'.format(civic_field_type)
                format_csv.write(line)
            with open(unique_tower_csvt,'w') as format_csv:
                line = '"String","Real","Real","Real","Integer","Real","Integer","Real","Integer","Real","Integer"'
                format_csv.write(line)

            # Truncates the first 4 characters of the network name to use as prefixes for attribute field names
            if len(network.split('_')[0])>5:
                net_prefix = network.split('_')[0][0:4]
            else:
                net_prefix = network.split('_')[0]

            file_count = len(glob.glob('*.json'))

            with open(net_str_csv,'w') as network_file:
                line = 'civic,civic_lat,civic_lon,target,{0}_T1,{0}_S1,{0}S1_QoC,{0}S1_url,{0}s1_dis,{0}S1_azi,{0}S1_tlt,{0}_T2,{0}_S2,{0}S2_QoC,{0}S2_url,{0}S2_dis,{0}S2_azi,{0}S2_tlt\n'.format(net_prefix)
                network_file.write(line)
                # Iterates through the current directory for .json files and parse the data
                # to a CSV file to be joined to the exisiting civic layer
                h_interval = 0
                interval = 0
                count = 0
                for file in glob.glob('*.json'):
                    civic = os.path.splitext(file)[0]
                    count += 1
                    with open(file) as json_file:
                        try:
                            data = json.load(json_file)
                            try:
                                dict = {}
                                for field in data:
                                    data_list = []
                                    tower_field = field.get('Server name')
                                    tower_name = tower_field.split('{}_'.format(network))[1].replace('_',' ').strip()
                                    signal_str = field['Transmitters'][0]['Signal power at receiver dBm']
                                    data_list.append(signal_str)

                                    if signal_str >= float(t_dbm):
                                        connection_quality = 'Good'
                                    elif signal_str >= float(t_dbm)-10:
                                        connection_quality = 'Marginal'
                                    else:
                                        connection_quality = 'Bad'
                                    data_list.append(connection_quality)

                                    url = field['Chart image']
                                    rlat = field['Receiver'][0]['Latitude']
                                    rlon = field['Receiver'][0]['Longitude']
                                    dis = field['Transmitters'][0]['Distance to receiver km']
                                    azi = field['Transmitters'][0]['Azimuth to receiver deg']
                                    tilt = field['Transmitters'][0]['Downtilt angle deg']

                                    if azi <= 180:
                                        azi = azi + 180
                                        print(azi)
                                    else:
                                        azi = azi - 180
                                        print(azi)

                                    tilt = -tilt

                                    data_list.append(url)
                                    data_list.append(dis)
                                    data_list.append(azi)
                                    data_list.append(tilt)

                                    # Adds tower coordinates to dictionary of towers if not already in
                                    if tower_name not in unique_towers:
                                        lat = field['Transmitters'][0]['Latitude']
                                        long = field['Transmitters'][0]['Longitude']
                                        height = field['Transmitters'][0]['Antenna height m']
                                        coordinate = [long,lat,height]
                                        unique_towers[tower_name] = coordinate
                                    dict[tower_name] = data_list
                                # Sorts dictionary of towers from best to weakest signal
                                sorted_dict = sorted(dict.items(),key=lambda item:item[1][0],reverse=True)[:2]
                                line = '{},{},{},{}'.format(civic,rlat,rlon,t_dbm)
                                for i in sorted_dict:
                                    line += ',{},{},{},{},{},{},{}'.format(i[0],i[1][0],i[1][1],i[1][2],i[1][3],i[1][4],i[1][5])
                                line += '\n'
                                network_file.write(line)
                            except Exception:
                                tb = sys.exc_info()[2]
                                tbinfo = traceback.format_tb(tb)[0]
                                # information concerning the error
                                pymsg = "PYTHON ERRORS:\nTraceback info:\n{}\nError Info:\n{}".format(tbinfo, str(sys.exc_info()[1]))
                                # AddMessage Python error messages for use in QGIS
                                feedback.pushInfo('{}'.format(pymsg))
                                error = data.get('error')
                                line = '{},{},-999\n'.format(civic,error)
                                network_file.write(line)
                                continue
                        except Exception:
                            tb = sys.exc_info()[2]
                            tbinfo = traceback.format_tb(tb)[0]
                            # information concerning the error
                            pymsg = "PYTHON ERRORS:\nTraceback info:\n{}\nError Info:\n Civic JSON file: {}.json\n{}".format(tbinfo,civic,str(sys.exc_info()[1]))
                            # AddMessage Python error messages for use in QGIS
                            feedback.pushInfo('{}'.format(pymsg))

                    if h_interval != count//10:
                        h_interval += 1
                        if file_count < 20:
                            feedback.pushInfo('Parsing json data...')
                            current_step += 1
                            feedback.setCurrentStep(current_step)
                            if feedback.isCanceled():
                                return {}
                        else:
                            five_percent = count//(file_count//20)
                            if interval != five_percent:
                                interval = five_percent
                                feedback.pushInfo('Parsing json data at {}%...'.format(interval*5))
                            current_step += 1
                            feedback.setCurrentStep(current_step)
                            if feedback.isCanceled():
                                return {}


            # Iterate through network file to calculate coverage statistics
            stat_file = csv.DictReader(open(net_str_csv))
            total_good_signals = 0
            total_marginal_signals = 0
            total_bad_signals = 0
            total_connections = 0
            for row in stat_file:
                good_signals = 0
                marginal_signals = 0
                bad_signals = 0
                total_connections += 1
                tower_name = row.get('{}_T1'.format(net_prefix))
                sig_str = float(row.get('{}_S1'.format(net_prefix)))
                if sig_str >= float(t_dbm):
                    total_good_signals += 1
                    good_signals += 1
                elif sig_str >= float(t_dbm)-10:
                    total_marginal_signals += 1
                    marginal_signals += 1
                else:
                    total_bad_signals += 1
                    bad_signals += 1

                tower_att = unique_towers[tower_name]
                if len(tower_att) == 3:
                    tower_att.extend([good_signals, round(good_signals/1,4), marginal_signals, round(marginal_signals/1,4), bad_signals, round(bad_signals/1,4), 1])
                else:
                    tower_att[9] += 1
                    tower_att[3] += good_signals
                    tower_att[4] = round(tower_att[3]/tower_att[9],4)
                    tower_att[5] += marginal_signals
                    tower_att[6] = round(tower_att[5]/tower_att[9],4)
                    tower_att[7] += bad_signals
                    tower_att[8] = round(tower_att[7]/tower_att[9],4)

            # Generates a CSV list of unique towers with assiciated coordinates
            feedback.pushInfo('Creating a CSV of all unique towers...')
            with open(unique_tower_csv,'w') as unique_tower_file:
                line = 'Tower,X,Y,Z,Good_Con,Good_Pct,Margin_Con,Margin_Pct,Bad_Con,Bad_Pct,Total_Con\n'
                unique_tower_file.write(line)
                for item in unique_towers:
                    if len(unique_towers[item]) == 3:
                        line = '{},{},{},{}\n'.format(item.replace('_',' '), *unique_towers[item])
                    else:
                        line = '{},{},{},{},{},{},{},{},{},{},{}\n'.format(item.replace('_',' '), *unique_towers[item])
                    unique_tower_file.write(line)

            # Join the returned civic signal strength CSV to civic shapefile layer
            feedback.pushInfo('Creating civic signal strength {} shapefile...'.format(civic_basename))
            alg_params = {
                # 'INPUT' : parameters[self.INPUT_CIVICS],
                'INPUT' : outputs['Reproject']['OUTPUT'],
                'FIELD' : parameters[self.CIVIC_FIELD],
                'INPUT_2' : net_str_csv,
                'FIELD_2' : 'civic',
                'OUTPUT' : parameters[self.OUTPUT_CIVICS]
            }
            outputs['JoinCivicFields'] = processing.run('qgis:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results[self.OUTPUT_CIVICS] = outputs['JoinCivicFields']['OUTPUT']

            current_step += 1
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            time.sleep(.25)

            # Convert Tower table to a Point Layer
            feedback.pushInfo('Creating tower {} shapefile...'.format(tower_basename))
            alg_params = {
                'INPUT' : unique_tower_csv,
                'XFIELD' : 'X',
                'YFIELD' : 'Y',
                'ZFIELD' : 'Z',
                'TARGET_CRS' : QgsCoordinateReferenceSystem('EPSG:4326'),
                'OUTPUT' : parameters[self.OUTPUT_TOWERS]
            }
            outputs['TowerTableToPoints'] = processing.run('qgis:createpointslayerfromtable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results[self.OUTPUT_TOWERS] = outputs['TowerTableToPoints']['OUTPUT']

            current_step += 1
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            time.sleep(.25)

            # Generate Hublines from Civics and Towers
            feedback.pushInfo('Creating civic signal strenth spokes {} shapefile...'.format(spoke_basename))
            alg_params = {
                'HUBS': outputs['TowerTableToPoints']['OUTPUT'],
                'HUB_FIELD': 'Tower',
                'SPOKES': outputs['JoinCivicFields']['OUTPUT'],
                'SPOKE_FIELD': '{}_T1'.format(net_prefix),
                'GEODESIC': False,
                'GEODESIC_DISTANCE': 1000,
                'ANTIMERIDIAN_SPLIT': False,
                'OUTPUT': parameters[self.OUTPUT_SPOKES]
            }
            outputs['CivicTowerSpokes'] = processing.run('qgis:hublines', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            results[self.OUTPUT_SPOKES] = outputs['CivicTowerSpokes']['OUTPUT']

            current_step += 1
            feedback.setCurrentStep(current_step)
            if feedback.isCanceled():
                return {}
            time.sleep(.25)

            # Defining field name for column to be analyzed and color ranges for signal strenth thresholds
            myColumn = '{}_S1'.format(net_prefix)
            ranges = []

            myMin1 = float(t_dbm)
            myMax1 = 0
            myLabel1 = 'Signals stronger than {} dBm ({}/{}) {}%'.format(t_dbm, total_good_signals, total_source_features, round((total_good_signals/total_source_features)*100,2))
            myColor1 = QtGui.QColor('#0772f5')
            ranges.append((myMin1, myMax1, myLabel1, myColor1))

            myMin2 = float(t_dbm)-10
            myMax2 = float(t_dbm)-0.001
            myLabel2 = 'Marginal signals between {} to {} dBm ({}/{}) {}%'.format(myMax2, myMin2, total_marginal_signals, total_source_features, round((total_marginal_signals/total_source_features)*100,2))
            myColor2 = QtGui.QColor('#7e7e7e')
            ranges.append((myMin2, myMax2, myLabel2, myColor2))

            myMin3 = -1000
            myMax3 = float(t_dbm)-10.000000000000001
            myLabel3 = 'Signals weaker than {} dBm ({}/{}) {}%'.format(myMax3,total_bad_signals,total_source_features,round((total_bad_signals/total_source_features)*100,2))
            myColor3 = QtGui.QColor('#f58a07')
            ranges.append((myMin3, myMax3, myLabel3, myColor3))

            # Style Spokes layer to meet threshold of signal strength
            spokes_layer = QgsProcessingUtils.mapLayerFromString(outputs['CivicTowerSpokes']['OUTPUT'], context)
            myRangeList = []

            for myMin, myMax, myLabel, myColor in ranges:
              mySymbol = QgsSymbol.defaultSymbol(spokes_layer.geometryType())
              mySymbol.setColor(myColor)
              mySymbol.setWidth(.5)
              myRange = QgsRendererRange(myMin, myMax, mySymbol, myLabel)
              myRangeList.append(myRange)

            myRenderer = QgsGraduatedSymbolRenderer('', myRangeList)
            myRenderer.setClassAttribute(myColumn)
            spokes_layer.setRenderer(myRenderer)
            spokes_layer.triggerRepaint()

            # Create map tip to display Path Profile chart from cloudRF
            expression = """<img src = "[% "{}S1_url" %]" width="600" />""".format(net_prefix)
            spokes_layer.setMapTipTemplate(expression)

            # Style Civics layer to meet threshold of signal strength
            civics_layer = QgsProcessingUtils.mapLayerFromString(outputs['JoinCivicFields']['OUTPUT'], context)

            myRangeList = []

            for myMin, myMax, myLabel, myColor in ranges:
              mySymbol = QgsSymbol.defaultSymbol(civics_layer.geometryType())
              mySymbol.setColor(myColor)
              myRange = QgsRendererRange(myMin, myMax, mySymbol, myLabel)
              myRangeList.append(myRange)

            myRenderer = QgsGraduatedSymbolRenderer('', myRangeList)
            myRenderer.setClassAttribute(myColumn)
            civics_layer.setRenderer(myRenderer)
            civics_layer.triggerRepaint()

            # Create map tip to display Path Profile chart from cloudRF
            civics_layer.setMapTipTemplate(expression)

            # Setting labels for Wireless Towers
            towers_layer = QgsProcessingUtils.mapLayerFromString(outputs['TowerTableToPoints']['OUTPUT'], context)

            layer_settings  = QgsPalLayerSettings()
            layer_settings.fieldName = "Tower"
            layer_settings.enabled = True
            layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)

            buffer_settings = QgsTextBufferSettings()
            buffer_settings.setEnabled(True)
            buffer_settings.setSize(1)
            buffer_settings.setColor(QtGui.QColor('white'))

            tower_symbol = QgsSvgMarkerSymbolLayer('https://upload.wikimedia.org/wikipedia/commons/d/db/Octicons-radio-tower.svg')
            towers_layer.renderer().symbol().changeSymbolLayer(0, tower_symbol)
            towers_layer.renderer().symbol().setSize(6)
            towers_layer.setLabelsEnabled(True)
            towers_layer.setLabeling(layer_settings)
            towers_layer.triggerRepaint()

            # Save layer styles for auto styling upon being loaded
            spokes_style = out_spoke_path.rsplit('.',1)[0] + '.qml'
            spokes_layer.saveNamedStyle(spokes_style)
            civics_style = out_civic_path.rsplit('.',1)[0] + '.qml'
            civics_layer.saveNamedStyle(civics_style)
            towers_style = out_tower_path.rsplit('.',1)[0] + '.qml'
            towers_layer.saveNamedStyle(towers_style)

            if os.path.exists(best_path) and os.path.isdir(best_path):
                feedback.pushInfo('Deleting interim data folder: {}'.format(best_path))
                os.chdir(directory)
                #shutil.rmtree(best_path)

            return results

        #get traceback object
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
        return BestSignalProcessingAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm.
        Names should contain lowercase alphanumeric characters only and no spaces
        or other formatting characters.
        """
        return 'best_signal_analysis'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Best RF Signal Analysis')

    def group(self):
        return ''

    def groupId(self):
        return ''

    def shortHelpString(self):
        return self.tr("This algorithm calculates the best tower for optimal signal strength for each of the features in an input layer and generates a hub and spokes diagram by showcasing the signal strength of a tower connection to civic based from the identified existing Tower network on CloudRF.\n\
        Determination of which tower connects to each civic is based on the best signal strength (calculated by CloudRF) that civic can receive from the 5 closest towers.\n\
        The resulting layers will contain tower features points, output civic points and spoke line connections showcasing the level of connectivity threshold for civics to their best servicing tower.\n\
        Unique Civic Identifier: The unique identifier for each of the features in the input civics layer such as Civic ID.\n\
        Network name: The network name of towers as created in CloudRF that is intended to be servicing the input civics layer.\n\
        NOTE: The FIRST FOUR characters of the network name will be used to identify which network the returned data is associated with.\n\
        Threshold: The lowest acceptable signal strength to be received at the location of the civic from any given tower. An addition lower 10 dBm range will be included as marginal signal strength data for reference.\n\
        Receiver height: Height of the receiver at each civic location.\n\
        Antenna ID: Antenna code for tower mounted antenna model. (See cloudrf.com/api/antennas)\n\
        Raster resolution: Default is 30 meters, finer resolution is available from CloudRF depending on area of interest or can be provided to CloudRF for more refined calculations.\n\
        NOTE: A folder of calculation data will be generated in the same directory as your 'Civics with signal strength data'. This folder of interim data is generate in the case that the processing algorithm may possibly crash for unexpected reasons as to not need to remake requests for data that has been acquired prior to a crash.\n\
        UPDATE: August 16th, 2021: Add distance, azimuth, and downtilt between towers and civics.\n\
        For additional documentation:\n https://api.cloudrf.com\n https://github.com/Cloud-RF/CloudRF-API-clients\n\
        Created by: Stats Wong\n\
        Updated by: Kevin Chen")
