################################################################
# read_aeronet_earlinet.py
#
# read Aeronet direct sun V2 data
#
# this file is part of the pyaerocom package
#
#################################################################
# Created 20171026 by Jan Griesfeller for Met Norway
#
# Last changed: See git log
#################################################################

# Copyright (C) 2017 met.no
# Contact information:
# Norwegian Meteorological Institute
# Box 43 Blindern
# 0313 OSLO
# NORWAY
# E-mail: jan.griesfeller@met.no
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA
import os, fnmatch, re
from collections import OrderedDict as od
import numpy as np
import xarray
from pyaerocom import const
from pyaerocom.helpers import unit_conversion_fac
from pyaerocom.exceptions import DataUnitError
from pyaerocom.io.readungriddedbase import ReadUngriddedBase
from pyaerocom import StationData, VerticalProfile, Variable
from pyaerocom import UngriddedData
        
# TODO: Check station names -> they are NOT UNIQUE (e.g. Potenza...) -> maybe
# use station_id instead... would require more flexible iterator in 
# UngriddedData
class ReadEarlinet(ReadUngriddedBase):
    """Interface for reading of EARLINET data"""
    #: Mask for identifying datafiles 
    _FILEMASK = '*.*'
    
    #: version log of this class (for caching)
    __version__ = "0.12_" + ReadUngriddedBase.__baseversion__
    
    #: Name of dataset (OBS_ID)
    DATA_ID = const.EARLINET_NAME
    
    #: List of all datasets supported by this interface
    SUPPORTED_DATASETS = [const.EARLINET_NAME]
    
    #: default variables for read method
    DEFAULT_VARS = ['ec532aer']
    
    #: all data values that exceed this number will be set to NaN on read. This
    #: is because iris, xarray, etc. assign a FILL VALUE of the order of e36 
    #: to missing data in the netcdf files
    _MAX_VAL_NAN = 1e6
    
    #: variable name of altitude in files
    ALTITUDE_ID = 'Altitude'
    
    #: temporal resolution
    TS_TYPE = 'undefined'
    
    #: dictionary specifying the file search patterns for each variable
    VAR_PATTERNS_FILE = {'ec532aer'     : '*/*.e532', 
                         'ec355aer'     : '*/*.e355',
                         'bscatc532aer' : '*/*.b532',
                         'bscatc355aer' : '*/*.b355',
                         'bscatc1064aer': '*/*.b1064',
                         'zdust'        : '*/*.e*'}
    
    
    #: dictionary specifying the file column names (values) for each Aerocom 
    #: variable (keys)
    VAR_NAMES_FILE = {'ec532aer'        : 'Extinction', 
                      'ec355aer'        : 'Extinction', 
                      'ec1064aer'       : 'Extinction',
                      'bscatc532aer'    : 'Backscatter',
                      'bscatc355aer'    : 'Backscatter',
                      'bscatc1064aer'   : 'Backscatter',
                      'zdust'           : 'DustLayerHeight'}
        
    #: metadata names that are supposed to be imported
    META_NAMES_FILE = od(location           = 'Location',
                         start_date         = 'StartDate',
                         start_utc          = 'StartTime_UT',
                         stop_utc           = 'StopTime_UT',
                         longitude          = 'Longitude_degrees_east',
                         latitude           = 'Latitude_degrees_north',
                         wavelength_emis    = 'EmissionWavelength_nm',
                         wavelength_det     = 'DetectionWavelength_nm',
                         res_raw_m          = 'ResolutionRaw_meter',
                         zenith_ang_deg     = 'ZenithAngle_degrees',
                         instrument_name    = 'System',
                         comments           = 'Comments',
                         shots_avg          = 'ShotsAveraged',
                         detection_mode     = 'DetectionMode',
                         res_eval           = 'ResolutionEvaluated',
                         input_params       = 'InputParameters',
                         altitude           = 'Altitude_meter_asl',
                         eval_method        = 'EvaluationMethod')
    
    #: Metadata keys from :attr:`META_NAMES_FILE` that are additional to 
    #: standard keys defined in :class:`StationMetaData` and that are supposed 
    #: to be inserted into :class:`UngriddedData` object created in :func:`read`
    KEEP_ADD_META = ['location', 'wavelength_emis', 'wavelength_det', 
                     'res_raw_m', 'zenith_ang_deg', 'comments', 'shots_avg', 
                     'detection_mode', 'res_eval', 'input_params', 
                     'eval_method']
    
    #: Attribute access names for unit reading of variable data
    VAR_UNIT_NAMES = od(Extinction    = ['ExtinctionUnits', 'units'],
                        Backscatter   = ['BackscatterUnits', 'units'],
                        Altitude      = 'units')
    #: Variable names of uncertainty data
    ERR_VARNAMES = od(  ec532aer = 'ErrorExtinction',
                        ec355aer = 'ErrorExtinction')
    
    #: If true, the uncertainties are also read (where available, cf. ERR_VARNAMES)
    READ_ERR = True
    
    PROVIDES_VARIABLES = list(VAR_PATTERNS_FILE)
    
    EXCLUDE_FILES = ['cirrus.txt', 
                     'etna.txt', 
                     'forest_fires.txt', 
                     'saharan_dust.txt']
    EXCLUDE_CASES = ['cirrus.txt']
    
    def __init__(self, dataset_to_read=None):
        # initiate base class
        super(ReadEarlinet, self).__init__(dataset_to_read)
        # make sure everything is properly set up
        if not all([x in self.VAR_PATTERNS_FILE for x in self.PROVIDES_VARIABLES]):
            raise AttributeError("Please specify file search masks in "
                                 "header dict VAR_PATTERNS_FILE for each "
                                 "variable defined in PROVIDES_VARIABLES")
        elif not all([x in self.VAR_NAMES_FILE for x in self.PROVIDES_VARIABLES]):
            raise AttributeError("Please specify file search masks in "
                                 "header dict VAR_NAMES_FILE for each "
                                 "variable defined in PROVIDES_VARIABLES")
        #: private dictionary containing loaded Variable instances, 
        self._var_info = {}
        
        #: files that are supposed to be excluded from reading
        self.exclude_files = []
        
        #: files that were actually excluded from reading
        self.excluded_files = []
    
    def read_file(self, filename, vars_to_retrieve=None, read_errs=None):
        """Read EARLINET file and return it as instance of :class:`StationData`
        
        Parameters
        ----------
        filename : str
            absolute path to filename to read
        vars_to_retrieve : :obj:`list`, optional
            list of str with variable names to read. If None, use
            :attr:`DEFAULT_VARS`
        read_errs : bool
            if True, uncertainty data is also read (where available).
    
        Returns
        -------
        StationData 
            dict-like object containing results
        """
        if read_errs is None: #use default setting
            read_errs = self.READ_ERR
            
        # implemented in base class
        vars_to_read, vars_to_compute = self.check_vars_to_retrieve(vars_to_retrieve)
        
        if len(vars_to_compute) > 0:
            raise NotImplementedError("This feature has not yet implemented, as "
                                      "it was not required so far. The "
                                      "implementation requires handling of "
                                      "profile data as well")
        #create empty data object (is dictionary with extended functionality)
        data_out = StationData()
        data_out['station_id'] = filename.split('/')[-2]
        data_out['data_id'] = self.DATA_ID
        #data_out['ts_type'] = self.TS_TYPE
           
        # create empty arrays for all variables that are supposed to be read
        # from file
        for var in vars_to_read:
            if not var in self._var_info:
                self._var_info[var] = Variable(var)
        var_info = self._var_info
            
        
        # Iterate over the lines of the file
        self.logger.debug("Reading file {}".format(filename))
        
        data_in = xarray.open_dataset(filename)
        
        for k, v in self.META_NAMES_FILE.items():
            
            data_out[k] = data_in.attrs[v]
        
        data_out['station_name'] = re.split('\s|,', data_out['location'])[0].strip()
# =============================================================================
#         except:
#             self.logger.warning('Unusual location string detected. Earlinet '
#                                 'location string expected to be comma separated '
#                                 'city, country information, got: '
#                                 '{}'.format(data_out['location']))
# =============================================================================
        
        str_dummy = str(data_in.StartDate)
        year, month, day = str_dummy[0:4], str_dummy[4:6], str_dummy[6:8]

        str_dummy = str(data_in.StartTime_UT).zfill(6)
        hours, minutes, seconds = str_dummy[0:2], str_dummy[2:4], str_dummy[4:6]
        
        datestring = '-'.join([year, month, day])
        startstring = 'T'.join([datestring, ':'.join([hours, minutes, seconds])])
         
        dtime = np.datetime64(startstring)
        
        str_dummy = str(data_in.StopTime_UT).zfill(6)
        hours, minutes, seconds = str_dummy[0:2], str_dummy[2:4], str_dummy[4:6]
        
        stopstring = 'T'.join([datestring, ':'.join([hours, minutes, seconds])])
        
        stop = np.datetime64(stopstring)
        
        if stop < dtime:
            raise Exception('Fatal: stop time is earlier than start time. '
                            'Developers: check if data has StopDate or similar')
        data_out['dtime'] = [dtime]
        data_out['stopdtime'] = [stop]
        data_out['has_zdust'] = False
        contains_vars = []
        for var in vars_to_read:
            netcdf_var_name = self.VAR_NAMES_FILE[var]
            # check if the desired variable is in the file
            if netcdf_var_name not in data_in.variables:
                self.logger.warning("Variable {} not found in file {}".format(var, filename))
                continue
            
            info = var_info[var]
            # xarray.DataArray
            arr = data_in.variables[netcdf_var_name]
            # the actual data as numpy array (or float if 0-D data, e.g. zdust)
            val = np.float64(arr)
            unit = None
            unames = self.VAR_UNIT_NAMES[netcdf_var_name]
            for u in unames:
                if u in arr.attrs:
                    unit = arr.attrs[u]
            if unit is None:
                raise DataUnitError('Unit of {} could not be accessed in file '
                                    '{}'.format(var, filename))
            unit_fac = None
            try:
                to_unit = self._var_info[var].unit
                unit_fac = unit_conversion_fac(unit, to_unit)
                val *= unit_fac
                unit = to_unit
            except Exception as e:
                self.logger.warn('Failed to convert unit: {}'.format(repr(e)))
            # 1D variable
            if var == 'zdust':
                if not val.ndim == 0:
                    raise ValueError('Fatal: dust layer height data must be '
                                     'single value')
                if np.isnan(val) or not info.minimum <= val <= info.maximum:
                    self.logger.warning("Invalid value of variable zdust "
                                        "in file {}. Skipping...!".format(filename))
                    continue
               
                data_out['has_zdust'] = True
                data_out[var] = float(val)
                

            #elif var.startswith('ec'):
            else:
                if not val.ndim == 1:
                    raise ValueError('Extinction data must be one dimensional')
                val[val > self._MAX_VAL_NAN] = np.nan
                wvlg = var_info[var].wavelength_nm
                wvlg_str = self.META_NAMES_FILE['wavelength_emis']
                
                if not wvlg == data_in.attrs[wvlg_str]:
                    self.logger.info('No wavelength match')
                    continue
                
                # create instance of ProfileData
                profile = VerticalProfile(var_name=var)
                
                alt_id = self.ALTITUDE_ID
                alt_data = data_in.variables[alt_id]
                
                alt_vals = np.float64(alt_data)
                alt_unit = alt_data.attrs[self.VAR_UNIT_NAMES[alt_id]]
                to_alt_unit = const.VAR_PARAM['alt'].unit
                if not alt_unit == to_alt_unit:
                    try:
                        alt_unit_fac = unit_conversion_fac(alt_unit, 
                                                           to_alt_unit)
                        alt_vals *= alt_unit_fac
                        alt_unit = to_alt_unit
                    except Exception as e:
                        self.logger.warn('Failed to convert unit: {}'.format(repr(e)))
                profile.altitude = alt_vals
                
                profile.var_info['altitude'] = od()
                profile.var_info['altitude']['unit'] = alt_unit
                profile.data  = val
                profile.dtime = dtime
                profile.var_info[var] = od()
                profile.var_info[var]['unit'] = unit
                
                if read_errs and var in self.ERR_VARNAMES:
                    err_name = self.ERR_VARNAMES[var]
                    if err_name in data_in.variables:
                        errs = np.float64(data_in.variables[err_name])
                        errs[errs > self._MAX_VAL_NAN] = np.nan
                        if unit_fac is not None:
                            errs *= unit_fac
                        profile.data_err = errs
                
                data_out[var] = profile

            contains_vars.append(var)
            
        data_out['contains_vars'] = contains_vars
        return (data_out)
    
    def read(self, vars_to_retrieve=None, files=None, first_file=None, 
             last_file=None, read_errs=None):
        """Method that reads list of files as instance of :class:`UngriddedData`
        
        Parameters
        ----------
        vars_to_retrieve : :obj:`list` or similar, optional,
            list containing variable IDs that are supposed to be read. If None, 
            all variables in :attr:`PROVIDES_VARIABLES` are loaded
        files : :obj:`list`, optional
            list of files to be read. If None, then the file list is used that
            is returned on :func:`get_file_list`.
        first_file : :obj:`int`, optional
            index of first file in file list to read. If None, the very first
            file in the list is used
        last_file : :obj:`int`, optional
            index of last file in list to read. If None, the very last file 
            in the list is used
        read_errs : bool
            if True, uncertainty data is also read (where available). If 
            unspecified (None), then the default is used (cf. :att:`READ_ERR`)
            
        Returns
        -------
        UngriddedData
            data object
        """
        if vars_to_retrieve is None:
            vars_to_retrieve = self.DEFAULT_VARS
        elif isinstance(vars_to_retrieve, str):
            vars_to_retrieve = [vars_to_retrieve]
        if read_errs is None:
            read_errs = self.READ_ERR
            
        if files is None:
            if len(self.files) == 0:
                self.get_file_list()
            files = self.files
    
        if first_file is None:
            first_file = 0
        if last_file is None:
            last_file = len(files)
        
        files = files[first_file:last_file]
        
        self.read_failed = []
        
        data_obj = UngriddedData()
        col_idx = data_obj.index
        meta_key = -1.0
        idx = 0
        
        #assign metadata object
        metadata = data_obj.metadata
        meta_idx = data_obj.meta_idx
        
        #last_station_id = ''
        num_files = len(files)
        
        disp_each = int(num_files*0.1)
        if disp_each < 1:
            disp_each = 1
            
        for i, _file in enumerate(files):
            if i%disp_each == 0:
                print("Reading file {} of {} ({})".format(i+1, 
                                 num_files, type(self).__name__))
            try:
                stat = self.read_file(_file, vars_to_retrieve=
                                              vars_to_retrieve,
                                              read_errs=read_errs)
                if not any([var in stat.contains_vars for var in 
                            vars_to_retrieve]):
                    self.logger.info("Station {} contains none of the desired "
                                     "variables. Skipping station..."
                                     .format(stat.station_name))
                    continue
                #if last_station_id != station_id:
                meta_key += 1
                # Fill the metatdata dict
                # the location in the data set is time step dependant!
                # use the lat location here since we have to choose one location
                # in the time series plot
                metadata[meta_key] = od()
                metadata[meta_key].update(stat.get_meta())
                for add_meta in self.KEEP_ADD_META:
                    if add_meta in stat:
                        metadata[meta_key][add_meta] = stat[add_meta]
                #metadata[meta_key]['station_id'] = station_id
                #metadata[meta_key]['data_id'] = self.DATA_ID
                metadata[meta_key]['variables'] = []
                metadata[meta_key]['var_info'] = od()
                # this is a list with indices of this station for each variable
                # not sure yet, if we really need that or if it speeds up things
                meta_idx[meta_key] = od()
                    #last_station_id = station_id
                
                # Is floating point single value
                time = stat.dtime[0]
                for var_idx, var in enumerate(stat.contains_vars):
                    val = stat[var]
                    metadata[meta_key]['var_info'][var] = vi = od()
                    if isinstance(val, VerticalProfile):
                        altitude = val.altitude
                        data = val.data
                        add = len(data)
                        err = val.data_err
                        metadata[meta_key]['var_info']['altitude'] = via =od()
                        
                        vi['unit'] = val.var_info[var]['unit']
                        via['unit'] = val.var_info['altitude']['unit']
                    else:
                        add = 1
                        altitude = np.nan
                        data = val
                        if var in stat.data_err:
                            err = stat.errs[var]
                        else:
                            err = np.nan
                        
                    stop = idx + add
                    #check if size of data object needs to be extended
                    if stop >= data_obj._ROWNO:
                        #if totnum < data_obj._CHUNKSIZE, then the latter is used
                        data_obj.add_chunk(add)
                    
                    #write common meta info for this station
                    data_obj._data[idx:stop, 
                                   col_idx['latitude']] = stat['latitude']
                    data_obj._data[idx:stop, 
                                   col_idx['longitude']] = stat['longitude']
                    data_obj._data[idx:stop, 
                                   col_idx['altitude']] = stat['altitude']
                    data_obj._data[idx:stop, 
                                   col_idx['metadata']] = meta_key
                                   
                    # write data to data object
                    data_obj._data[idx:stop, col_idx['time']] = time
                    data_obj._data[idx:stop, col_idx['stoptime']] = stat.stopdtime[0]
                    data_obj._data[idx:stop, col_idx['data']] = data
                    data_obj._data[idx:stop, col_idx['dataaltitude']] = altitude
                    data_obj._data[idx:stop, col_idx['varidx']] = var_idx
                    
                    if read_errs:
                        data_obj._data[idx:stop, col_idx['dataerr']] = err
                    
                    if not var in meta_idx[meta_key]:
                        meta_idx[meta_key][var] = []
                    meta_idx[meta_key][var].extend(list(range(idx, stop)))
                    
                    if not var in metadata[meta_key]['variables']:
                        metadata[meta_key]['variables'].append(var)
                    if not var in data_obj.var_idx:
                        data_obj.var_idx[var] = var_idx
                    idx += add
            except Exception as e:
                self.read_failed.append(_file)
                self.logger.exception('Failed to read file {} (ERR: {})'
                                      .format(os.path.basename(_file),
                                              repr(e)))
                
        # shorten data_obj._data to the right number of points
        data_obj._data = data_obj._data[:idx]
        data_obj.data_revision[self.DATA_ID] = self.data_revision
        self.data = data_obj
        return data_obj
        
    def _get_exclude_filelist(self):
        """Get list of filenames that are supposed to be ignored"""
        exclude = []
        import glob
        files = glob.glob('{}/EXCLUDE/*.txt'.format(self.DATASET_PATH))
        for i, file in enumerate(files):
            if not os.path.basename(file) in self.EXCLUDE_CASES:
                continue
            count = 0
            num = None
            indata = False
            with open(file) as f:
                for line in f:
                    if indata:
                        exclude.append(line.strip())
                        count += 1
                    elif 'Number of' in line:
                        num = int(line.split(':')[1].strip())
                        indata = True
                    
            if not count == num:
                raise Exception
        self.exclude_files = list(dict.fromkeys(exclude))
        return self.exclude_files
        
    def get_file_list(self, vars_to_retrieve=None):
        """Perform recusive file search for all input variables
        
        Note
        ----
        Overloaded implementation of base class, since for Earlinet, the 
        paths are variable dependent
        
        Parameters
        ----------
        vars_to_retrieve : list
            list of variables to retrieve
        
        Returns
        -------
        list
            list containing file paths
        """
        if vars_to_retrieve is None:
            vars_to_retrieve = self.DEFAULT_VARS
        elif isinstance(vars_to_retrieve, str):
            vars_to_retrieve = [vars_to_retrieve]
        exclude = self._get_exclude_filelist()
        self.logger.info('Fetching data files. This might take a while...')
        patterns = [self.VAR_PATTERNS_FILE[var] for var in vars_to_retrieve]
        matches = []
        for root, dirnames, files in os.walk(self.DATASET_PATH):
            for pattern in patterns:
                paths = [os.path.join(root, f) for f in files]
                for path in fnmatch.filter(paths, pattern):
                    if  os.path.basename(path) in exclude:
                        self.excluded_files.append(path)
                    else:
                        matches.append(path)
        self.files = files = list(dict.fromkeys(matches))
        return files
    
    def copy(self):
        """Make and return a deepcopy of this object"""
        from copy import deepcopy
        return deepcopy(self)
    
if __name__=="__main__":
    import matplotlib.pyplot as plt
    plt.close('all')
    read = ReadEarlinet()
    read.verbosity_level = 'warning'
    
    #lst = read.get_file_list('ec532aer')
    
    # to accelerate things for testing (first 20 files)
    lst = ['/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1008192050.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1009162031.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1012131839.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1011221924.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1105122027.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1507232059.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1107072042.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1109192000.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1001251402.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1001211841.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1005272143.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev0911091200.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1109222000.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1103242017.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1109052000.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1109152000.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1109082000.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1006212036.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1008022112.e532',
             '/lustre/storeA/project/aerocom/aerocom1/AEROCOM_OBSDATA/Export/Earlinet/CAMS/data/ev/ev1508272229.e532']
    
    read.files = lst
    
    stat = read.read_file(lst[0], 'ec532aer')
    
    ax = stat.ec532aer.plot()
    
    
    data = read.read('ec532aer', last_file=20)
    print(data)
    
    stat = data.to_station_data('Evora')
    
