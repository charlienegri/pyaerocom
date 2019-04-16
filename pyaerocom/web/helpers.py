#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 15 14:00:44 2019

@author: jonasg
"""
from pyaerocom._lowlevel_helpers import BrowseDict

class ObsConfigEval(BrowseDict):
    """Observation configuration for evaluation (dictionary)
    
    Note
    ----
    Only :attr:`obs_id` and `obs_vars` are mandatory, the rest is optional.
    
    Attributes
    ----------
    obs_id : str
        ID of observation network in AeroCom database 
        (e.g. 'AeronetSunV3Lev2.daily')
    obs_vars : list
        list of pyaerocom variable names that are supposed to be analysed
        (e.g. ['od550aer', 'ang4487aer'])
    obs_ts_type_read : :obj:`str` or :obj:`dict`, optional
        may be specified to explicitly define the reading frequency of the 
        observation data (so far, this does only apply to gridded obsdata such
        as satellites). For ungridded reading, the frequency may be specified
        via :attr:`obs_id`, where applicable (e.g. AeronetSunV3Lev2.daily).
        Can be specified variable specific in form of dictionary.
    obs_vert_type : :obj:`str` or :obj:`dict`, optional
        Aerocom vertical code encoded in the model filenames (only AeroCom 3 
        and later). Specifies which model file should be read in case there are
        multiple options (e.g. surface level data can be read from a 
        *Surface*.nc file as well as from a *ModelLevel*.nc file). If input is 
        string (e.g. 'Surface'), then the corresponding vertical type code is 
        used for reading of all variables that are colocated (i.e. that are 
        specified in :attr:`obs_vars`). Else (if input is dictionary, e.g. 
        `obs_vert_type=dict(od550aer='Column', ec550aer='ModelLevel')`), 
        information is extracted variable specific, for those who are defined
        in the dictionary, for all others, `None` is used.
    read_opts_ungridded : :obj:`dict`, optional
        dictionary that specifies reading constraints for ungridded reading
        (c.g. :class:`pyaerocom.io.ReadUngridded`).
    """
    SUPPORTED_VERT_CODES = ['Column', 'ModelLevel', 'Surface']
    def __init__(self, **kwargs):
        
        self.obs_id = None
        self.obs_vars = None
        self.obs_ts_type_read = None
        self.obs_vert_type = None
        
        self.read_opts_ungridded = None
        
        self.update(**kwargs)
        self.check_cfg()
    
    def check_cfg(self):
        """Check that minimum required attributes are set and okay"""
        if not isinstance(self.obs_id, str):
            raise ValueError('Invalid value for obs_id: {}. Need str.'
                             .format(self.obs_id))
        if isinstance(self.obs_vars, str):
            self.obs_vars = [self.obs_vars]
        elif not isinstance(self.obs_vars, list):
            raise ValueError('Invalid input for obs_vars. Need list or str, '
                             'got: {}'.format(self.obs_vars))
        if self.obs_vert_type is None:
            raise ValueError('obs_vert_type is not defined. Please specify '
                             'using either of the available codes: {}. '
                             'It may be specified for all variables (as string) '
                             'or per variable using a dict'
                             .format(self.SUPPORTED_VERT_CODES))
            if (isinstance(self.obs_vert_type, str) and 
                not self.obs_vert_type in self.SUPPORTED_VERT_CODES):
                    raise ValueError('Invalid value for obs_vert_type: {}. '
                                     'Supported codes are {}.'
                                     .format(self.obs_vert_type,
                                             self.SUPPORTED_VERT_CODES))
            elif isinstance(self.obs_vert_type, dict):
                for var_name, val in self.obs_vert_type.items():
                    if not val in self.SUPPORTED_VERT_CODES:
                        raise ValueError('Invalid value for obs_vert_type: {} '
                                         '(variable {}). Supported codes are {}.'
                                         .format(self.obs_vert_type,
                                                 var_name,
                                                 self.SUPPORTED_VERT_CODES))
                        
                
        
class ModelConfigEval(BrowseDict):
    """Modeln configuration for evaluation (dictionary)
    
    Note
    ----
    Only :attr:`model_id` is mandatory, the rest is optional.
    
    Attributes
    ----------
    model_id : str
        ID of model run in AeroCom database (e.g. 'ECMWF_CAMS_REAN')
    model_ts_type_read : :obj:`str` or :obj:`dict`, optional
        may be specified to explicitly define the reading frequency of the 
        model data. Not to be confused with :attr:`ts_type`, which specifies 
        the frequency used for colocation. Can be specified variable specific 
        by providing a dictionary.
    model_use_vars : :obj:`dict`, optional
        dictionary that specifies mapping of model variables. Keys are 
        observation variables, values are the corresponding model variables 
        (e.g. model_use_vars=dict(od550aer='od550csaer'))
    model_read_aux : :obj:`dict`, optional
        may be used to specify additional computation methods of variables from
        models. Keys are obs variables, values are dictionaries with keys 
        `vars_required` (list of required variables for computation of var 
        and `fun` (method that takes list of read data objects and computes
        and returns var)    
    """
    def __init__(self, model_id, **kwargs):
        self.model_id = model_id
        self.model_ts_type_read = None
        self.model_use_vars = None
        self.model_read_aux = None
        
        self.update(**kwargs)
        self.check_cfg()
    
    def check_cfg(self):
        """Check that minimum required attributes are set and okay"""
        if not isinstance(self.model_id, str):
            raise ValueError('Invalid input for model_id {}. Need str.'
                             .format(self.model_id))