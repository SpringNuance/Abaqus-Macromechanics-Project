import pandas as pd
import numpy as np
import subprocess
import os
import matplotlib.pyplot as mp
from modules.hardeningLaws import *
from modules.helper import *
import sys
import shutil
import random
import time

class MOO_SIM():
    def __init__(self, info):
        self.info = info
   
    def latin_hypercube_sampling(self):
        paramConfig = self.info["paramConfig"]
        numberOfInitialSims = self.info["numberOfInitialSims"]
        linspaceValues = {}
        for param in paramConfig:
            linspaceValues[param] = np.linspace(
                start=paramConfig[param]["lowerBound"] * paramConfig[param]["exponent"], 
                stop=paramConfig[param]["upperBound"] * paramConfig[param]["exponent"], 
                num = self.info["initialSimsSpacing"])
            linspaceValues[param] = linspaceValues[param].tolist()   
        points = []
        for _ in range(numberOfInitialSims):
            while True:
                candidateParam = {}
                for param in linspaceValues:
                    random.shuffle(linspaceValues[param])
                    candidateParam[param] = linspaceValues[param].pop()
                if candidateParam not in points:
                    break
            points.append(candidateParam)

        return points

    def run_initial_simulations(self, parameters):
        indexParamsDict = self.preprocess_simulations_initial(parameters)
        self.write_paths_initial()
        self.submit_array_jobs_initial()
        self.postprocess_results_initial(indexParamsDict)

    def preprocess_simulations_initial(self, initial_params):
        resultPath = self.info['resultPath']
        simPath = self.info['simPath']
        templatePath = self.info['templatePath'] 
        hardeningLaw = self.info['hardeningLaw']
        numberOfInitialSims = self.info['numberOfInitialSims']
        truePlasticStrain = self.info['truePlasticStrain']
        maxTargetDisplacement = self.info['maxTargetDisplacement']

        # initial_params = self.latin_hypercube_sampling()
        # #print(initial_params)
        # np.save(f"{resultPath}/initial/common/parameters.npy", initial_params)
        # initial_params = np.load(f"{resultPath}/initial/common/parameters.npy", allow_pickle=True).tolist()
        # Initializing the flow curves and force-displacement curves
        # The structure of flow curve: dict of (hardening law params typle) -> {stress: stressArray , strain: strainArray}
        
        flowCurves = {}
        
        for paramDict in initial_params:
            paramsTuple = tuple(paramDict.items())
            trueStress = calculate_flowCurve(paramDict, hardeningLaw, truePlasticStrain)
            flowCurves[paramsTuple] = {}
            flowCurves[paramsTuple]['strain'] = truePlasticStrain
            flowCurves[paramsTuple]['stress'] = trueStress
        np.save(f"{resultPath}/initial/common/flowCurves.npy", flowCurves)
        #print(flowCurves)

        indexParamsDict = {} # Map simulation folder index to the corresponding hardening law parameters
        for index, paramDict in enumerate(initial_params):
            indexParamsDict[str(index+1)] = tuple(paramDict.items())
        
        #print(simulationDict)
        # Copying the template folder to the simulation folder for the number of simulations
        print(f"Number of initial simulations: {numberOfInitialSims}")
        for index in range(1, numberOfInitialSims + 1):
            # Create the simulation folder if not exists, else delete the folder and create a new one
            if os.path.exists(f"{simPath}/initial/{index}"):
                shutil.rmtree(f"{simPath}/initial/{index}")
            shutil.copytree(templatePath, f"{simPath}/initial/{index}")
            paramsTuple = indexParamsDict[str(index)]
            truePlasticStrain = flowCurves[paramsTuple]['strain']
            trueStress = flowCurves[paramsTuple]['stress']
            replace_flowCurve_material_inp(f"{simPath}/initial/{index}/material.inp", truePlasticStrain, trueStress)
            replace_maxDisp_geometry_inp(f"{simPath}/initial/{index}/geometry.inp", maxTargetDisplacement)
            replace_materialName_geometry_inp(f"{simPath}/initial/{index}/geometry.inp", "material.inp")
            create_parameter_file(f"{simPath}/initial/{index}", dict(paramsTuple))
            create_flowCurve_file(f"{simPath}/initial/{index}", truePlasticStrain, trueStress)
        return indexParamsDict

    def write_paths_initial(self):
        numberOfInitialSims = self.info['numberOfInitialSims']
        projectPath = self.info['projectPath']
        simPath = self.info['simPath']
        with open("linux_slurm/array_file.txt", 'w') as filename:
            for index in range(1, numberOfInitialSims + 1):
                filename.write(f"{projectPath}/{simPath}/initial/{index}\n")
    
    def submit_array_jobs_initial(self):
        logPath = self.info['logPath']        
        numberOfInitialSims = self.info['numberOfInitialSims']
        printLog("Initial simulation preprocessing stage starts", logPath)
        printLog(f"Number of jobs required: {numberOfInitialSims}", logPath)
        subprocess.run(f"sbatch --wait --array=1-{numberOfInitialSims} linux_slurm/puhti_abaqus_array_small.sh", shell=True)
        printLog("Initial simulation postprocessing stage finished", logPath)
    
    def postprocess_results_initial(self, indexParamsDict):
        numberOfInitialSims = self.info['numberOfInitialSims']
        simPath = self.info['simPath']
        resultPath = self.info['resultPath']
        logPath = self.info['logPath']
        
        # The structure of force-displacement curve: dict of (hardening law params typle) -> {force: forceArray , displacement: displacementArray}

        FD_Curves = {}
        for index in range(1, numberOfInitialSims + 1):
            if not os.path.exists(f"{resultPath}/initial/data/{index}"):
                os.mkdir(f"{resultPath}/initial/data/{index}")
            shutil.copy(f"{simPath}/initial/{index}/FD_Curve.txt", f"{resultPath}/initial/data/{index}")
            shutil.copy(f"{simPath}/initial/{index}/FD_Curve_Plot.tif", f"{resultPath}/initial/data/{index}")
            shutil.copy(f"{simPath}/initial/{index}/Deformed_Specimen.tif", f"{resultPath}/initial/data/{index}")
            shutil.copy(f"{simPath}/initial/{index}/parameters.xlsx", f"{resultPath}/initial/data/{index}")
            shutil.copy(f"{simPath}/initial/{index}/parameters.csv", f"{resultPath}/initial/data/{index}")
            shutil.copy(f"{simPath}/initial/{index}/flowCurve.xlsx", f"{resultPath}/initial/data/{index}")
            shutil.copy(f"{simPath}/initial/{index}/flowCurve.csv", f"{resultPath}/initial/data/{index}")
                        
            paramsTuple = indexParamsDict[str(index)]
            displacement, force = read_FD_Curve(f"{simPath}/initial/{index}/FD_Curve.txt")
            FD_Curves[paramsTuple] = {}
            FD_Curves[paramsTuple]['displacement'] = displacement
            FD_Curves[paramsTuple]['force'] = force
            create_FD_Curve_file(f"{resultPath}/initial/data/{index}", displacement, force)
            
        # Returning force-displacement curve data
        np.save(f"{resultPath}/initial/common/FD_Curves_unsmooth.npy", FD_Curves)
        printLog("Starting to apply Savgol smoothing filter on the FD curves", logPath)
        smoothing_force(force, startIndex=20, endIndex=90, iter=10000)

        FD_Curves_smooth = {}

        for param in FD_Curves:
            force = FD_Curves[param]['force']
            smooth_force = smoothing_force(force, 40, 90, 10000)
            displacement = FD_Curves[param]['displacement']
            FD_Curves_smooth[param] = {}
            FD_Curves_smooth[param]['force'] = smooth_force
            FD_Curves_smooth[param]['displacement'] = displacement

        np.save(f"{resultPath}/initial/common/FD_Curves_smooth.npy", FD_Curves_smooth)
        printLog("Savgol smoothing of FD curves has finished", logPath)
        printLog("Saving successfully all simulation results", logPath)

    def run_iteration_simulations(self, paramsDict, iterationIndex):
        geom_to_params_flowCurves = self.preprocess_simulations_iteration(paramsDict, iterationIndex)
        self.write_paths_iteration(iterationIndex)
        #time.sleep(180)
        self.submit_array_jobs_iteration()
        geom_to_params_FD_Curves = self.postprocess_results_iteration(paramsDict, iterationIndex)
        return geom_to_params_FD_Curves, geom_to_params_flowCurves
    
    def preprocess_simulations_iteration(self, paramsDict, iterationIndex):
        resultPath = self.info['resultPath']
        simPath = self.info['simPath']
        geometries = self.info['geometries']
        templatePath = self.info['templatePath'] 
        hardeningLaw = self.info['hardeningLaw']
        numberOfInitialSims = self.info['numberOfInitialSims']
        truePlasticStrain = self.info['truePlasticStrain']
        maxTargetDisplacements = self.info['maxTargetDisplacements']
        
        paramsTuple = tuple(paramsDict.items())
        trueStress = calculate_flowCurve(paramsDict, hardeningLaw, truePlasticStrain)
        geom_to_params_flowCurves = {}

        for geometry in geometries:
            geom_to_params_flowCurves[geometry] = {}
            geom_to_params_flowCurves[geometry][paramsTuple] = {}
            geom_to_params_flowCurves[geometry][paramsTuple]['strain'] = truePlasticStrain
            geom_to_params_flowCurves[geometry][paramsTuple]['stress'] = trueStress
        
        # Create the simulation folder if not exists, else delete the folder and create a new one
        for geometry in geometries:
            if os.path.exists(f"{simPath}/{geometry}/iteration/{iterationIndex}"):
                shutil.rmtree(f"{simPath}/{geometry}/iteration/{iterationIndex}")
            shutil.copytree(f"{templatePath}/{geometry}", f"{simPath}/{geometry}/iteration/{iterationIndex}")
            truePlasticStrain = geom_to_params_flowCurves[geometry][paramsTuple]['strain']
            trueStress = geom_to_params_flowCurves[geometry][paramsTuple]['stress']
            replace_flowCurve_material_inp(f"{simPath}/{geometry}/iteration/{iterationIndex}/material.inp", truePlasticStrain, trueStress)
            replace_maxDisp_geometry_inp(f"{simPath}/{geometry}/iteration/{iterationIndex}/geometry.inp", maxTargetDisplacements[geometry])
            replace_materialName_geometry_inp(f"{simPath}/{geometry}/iteration/{iterationIndex}/geometry.inp", "material.inp")
            create_parameter_file(f"{simPath}/{geometry}/iteration/{iterationIndex}", dict(paramsTuple))
            create_flowCurve_file(f"{simPath}/{geometry}/iteration/{iterationIndex}", truePlasticStrain, trueStress)
        
        return geom_to_params_flowCurves

    def write_paths_iteration(self, iterationIndex):
        projectPath = self.info['projectPath']
        simPath = self.info['simPath']
        geometries = self.info['geometries']
        with open("linux_slurm/array_file.txt", 'w') as filename:
            for geometry in geometries:
                filename.write(f"{projectPath}/{simPath}/{geometry}/iteration/{iterationIndex}\n")

    def submit_array_jobs_iteration(self):
        logPath = self.info['logPath']       

        geometries = self.info['geometries']
        printLog("Iteration simulation preprocessing stage starts", logPath)
        printLog(f"Number of jobs required: {len(geometries)}", logPath)
        subprocess.run(f"sbatch --wait --array=1-{len(geometries)} linux_slurm/puhti_abaqus_array_small.sh", shell=True)
        printLog("Iteration simulation postprocessing stage finished", logPath)

    def postprocess_results_iteration(self, paramsDict, iterationIndex):
        simPath = self.info['simPath']
        resultPath = self.info['resultPath']
        logPath = self.info['logPath']
        geometries = self.info['geometries']

        paramsTuple = tuple(paramsDict.items())
        geom_to_params_FD_Curves = {}
        
        
        for geometry in geometries:
            if not os.path.exists(f"{resultPath}/{geometry}/iteration/data/{iterationIndex}"):
                os.mkdir(f"{resultPath}/{geometry}/iteration/data/{iterationIndex}")
            shutil.copy(f"{simPath}/{geometry}/iteration/{iterationIndex}/FD_Curve.txt", f"{resultPath}/{geometry}/iteration/data/{iterationIndex}")
            shutil.copy(f"{simPath}/{geometry}/iteration/{iterationIndex}/FD_Curve_Plot.tif", f"{resultPath}/{geometry}/iteration/data/{iterationIndex}")
            shutil.copy(f"{simPath}/{geometry}/iteration/{iterationIndex}/Deformed_Specimen.tif", f"{resultPath}/{geometry}/iteration/data/{iterationIndex}")
            shutil.copy(f"{simPath}/{geometry}/iteration/{iterationIndex}/parameters.xlsx", f"{resultPath}/{geometry}/iteration/data/{iterationIndex}")
            shutil.copy(f"{simPath}/{geometry}/iteration/{iterationIndex}/parameters.csv", f"{resultPath}/{geometry}/iteration/data/{iterationIndex}")
            shutil.copy(f"{simPath}/{geometry}/iteration/{iterationIndex}/flowCurve.xlsx", f"{resultPath}/{geometry}/iteration/data/{iterationIndex}")
            shutil.copy(f"{simPath}/{geometry}/iteration/{iterationIndex}/flowCurve.csv", f"{resultPath}/{geometry}/iteration/data/{iterationIndex}")
                        
            displacement, force = read_FD_Curve(f"{simPath}/{geometry}/iteration/{iterationIndex}/FD_Curve.txt")
            
            geom_to_params_FD_Curves[geometry] = {}
            geom_to_params_FD_Curves[geometry][paramsTuple] = {}
            geom_to_params_FD_Curves[geometry][paramsTuple]['displacement'] = displacement
            geom_to_params_FD_Curves[geometry][paramsTuple]['force'] = force
            create_FD_Curve_file(f"{resultPath}/{geometry}/iteration/data/{iterationIndex}", displacement, force)
        printLog("Saving successfully iteration simulation results", logPath)
        return geom_to_params_FD_Curves
