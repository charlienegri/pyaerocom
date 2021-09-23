#!/usr/bin/env python3
# -*- coding: utf-8 -*-
########################################################################
#
# This python module is part of the pyaerocom software
#
# License: GNU General Public License v3.0
# More information: https://github.com/metno/pyaerocom
# Documentation: https://pyaerocom.readthedocs.io/en/latest/
# Copyright (C) 2017 met.no
# Contact information: Norwegian Meteorological Institute (MET Norway)
#
########################################################################

import os
import logging
from pathlib import Path
from pyaerocom.combine_vardata_ungridded import combine_vardata_ungridded
from pyaerocom.exceptions import (DataRetrievalError,
                                  NetworkNotImplemented, NetworkNotSupported)

from pyaerocom.io.read_aeronet_sdav2 import ReadAeronetSdaV2
from pyaerocom.io.read_aeronet_sdav3 import ReadAeronetSdaV3
from pyaerocom.io.read_aeronet_invv2 import ReadAeronetInvV2
from pyaerocom.io.read_aeronet_invv3 import ReadAeronetInvV3
from pyaerocom.io.read_aeronet_sunv2 import ReadAeronetSunV2
from pyaerocom.io.read_aeronet_sunv3 import ReadAeronetSunV3
from pyaerocom.io.read_earlinet import ReadEarlinet
from pyaerocom.io.read_ebas import ReadEbas
from pyaerocom.io.read_aasetal import ReadAasEtal
from pyaerocom.io.read_gaw import ReadGAW
from pyaerocom.io.read_ghost import ReadGhost
from pyaerocom.io.read_eea_aqerep import ReadEEAAQEREP
from pyaerocom.io.read_eea_aqerep_v2 import ReadEEAAQEREP_V2
from pyaerocom.io.read_airnow import ReadAirNow
from pyaerocom.io.read_marcopolo import ReadMarcoPolo

from pyaerocom.io.cachehandler_ungridded import CacheHandlerUngridded
from pyaerocom.ungriddeddata import UngriddedData
from pyaerocom.helpers import varlist_aerocom

from pyaerocom import const, print_log, logger

class ReadUngridded(object):
    """Factory class for reading of ungridded data based on obsnetwork ID

    This class also features reading functionality that goes beyond reading
    of inidividual observation datasets; including, reading of multiple
    datasets and post computation of new variables based on datasets that can
    be read.

    Parameters
    ----------
    COMING SOON

    """
    SUPPORTED_READERS = [ReadAeronetInvV3,
                         ReadAeronetInvV2,
                         ReadAeronetSdaV2,
                         ReadAeronetSdaV3,
                         ReadAeronetSunV2,
                         ReadAeronetSunV3,
                         ReadEarlinet,
                         ReadEbas,
                         ReadGAW,
                         ReadAasEtal,
                         ReadGhost,
                         ReadAirNow,
                         ReadMarcoPolo,
                         ReadEEAAQEREP,
                         ReadEEAAQEREP_V2]

    DONOTCACHE_NAME = 'DONOTCACHE'
    def __init__(self, data_ids=None, vars_to_retrieve=None,
                 ignore_cache=False, data_dirs=None):

        #will be assigned in setter method of data_ids
        self._data_ids = []
        self._vars_to_retrieve = None
        self._data_dirs = {}

        #: dictionary containing reading classes for each dataset to read (will
        #: be accessed via get_reader)
        self._readers = {}

        if data_ids is not None:
            self.data_ids = data_ids

        if vars_to_retrieve is not None:
            self.vars_to_retrieve = vars_to_retrieve

        if data_dirs is not None:
            self.data_dirs = data_dirs

        if vars_to_retrieve is not None:
            self.vars_to_retrieve = vars_to_retrieve

        if ignore_cache:
            logger.info('Deactivating caching')
            const.CACHING = False

    @property
    def data_id(self):
        """
        Helper that returns obs data ID in case only 1 data ID is assigned

        Note
        ----
        This is, for instance, used in :class:`Colocator` which allows only
        1 dataset to be processed at a time. Indeed, only in rare use cases
        one would load multiple ungridded datasets at a time.

        Raises
        ------
        AttributeError
            if :attr:`data_ids` does not contain exactly 1 item.

        Returns
        -------
        str
            data ID
        """
        ids = self.data_ids
        if len(ids) != 1:
            raise AttributeError('None or more than one data ID are assigned')
        return ids[0]

    @property
    def data_dirs(self):
        """
        dict: Data directory(ies) for dataset(s) to read (keys are data IDs)
        """
        return self._data_dirs

    @data_dirs.setter
    def data_dirs(self, val):
        if isinstance(val, Path):
            val = str(val)
        dsr = self.data_ids
        if len(dsr) < 2 and isinstance(val, str):
            val = {dsr[0] : val}
        elif not isinstance(val, dict):
            raise ValueError(
                'Invalid input for data_dirs ({val}); needs to be a '
                'dictionary.'
                )
        for data_dir in val.values():
            assert os.path.exists(data_dir), f'{data_dir} does not exist'
        self._data_dirs = val

    @property
    def vars_to_retrieve(self):
        """Variables to retrieve (list or dict)

        Dictionary can be used in case different variables from multiple
        datasets are supposed to be read.
        """
        return self._vars_to_retrieve

    @vars_to_retrieve.setter
    def vars_to_retrieve(self, val):
        if isinstance(val, str):
            val = [val]
        elif not isinstance(val, (list, dict)):
            raise ValueError('Invalid input for vars_to_retrieve ({}). '
                             'Need either str, list or dict')
        self._vars_to_retrieve = val

    @property
    def post_compute(self):
        """Information about datasets that can be computed in post"""
        return const.OBS_UNGRIDDED_POST

    @property
    def SUPPORTED_DATASETS(self):
        """
        Returns list of strings containing all supported dataset names
        """
        lst = []
        for reader in self.SUPPORTED_READERS:
            lst.extend(reader.SUPPORTED_DATASETS)
        lst.extend(self.post_compute)
        return lst

    @property
    def supported_datasets(self):
        """
        Wrapper for :attr:`SUPPORTED_DATASETS`
        """
        return self.SUPPORTED_DATASETS

    def _check_donotcachefile(self):
        """Check if donotcache file exists

        Returns
        -------
        bool
            True if file exists, else False
        """
        try:
            if os.path.exists(os.path.join(const.cache_basedir,
                                           self.DONOTCACHE_NAME)):
                return True
        except:
            pass
        return False

    @property
    def ignore_cache(self):
        """Boolean specifying whether caching is active or not"""
        if self._check_donotcachefile() or not const.CACHING:
            return True
        return False

    @property
    def data_ids(self):
        """List of datasets supposed to be read"""
        return self._data_ids

    @data_ids.setter
    def data_ids(self, val):
        if isinstance(val, str):
            val = [val]
        elif not isinstance(val, (tuple, list)):
            raise IOError('Invalid input for parameter data_ids')
        self._data_ids = val

    @property
    def data_id(self):
        """
        ID of dataset

        Note
        -----
        Only works if exactly one dataset is assigned to the reader, that is,
        length of :attr:`data_ids` is 1.

        Raises
        ------
        AttributeError
            if number of items in :attr:`data_ids` is unequal one.

        Returns
        -------
        str
            data ID

        """
        nids = len(self.data_ids)
        if nids== 0:
            raise AttributeError('No data_id assigned')
        elif nids > 1:
            raise AttributeError('Multiple data_ids assigned')
        return self.data_ids[0]

    def dataset_provides_variables(self, data_id=None):
        """List of variables provided by a certain dataset"""
        if data_id is None:
            data_id = self.data_id
        if not data_id in self._readers:
            reader = self.get_lowlevel_reader(data_id)
        else:
            reader = self._readers[data_id]
        return reader.PROVIDES_VARIABLES

    def get_reader(self, data_id):
        const.print_log.warning(DeprecationWarning(
            'this method was renamed to get_lowlevel_reader, please use the '
            'new name'
            ))
        return self.get_lowlevel_reader(data_id)

    def get_lowlevel_reader(self, data_id=None):
        """Helper method that returns initiated reader class for input ID

        Parameters
        -----------
        data_id : str
            Name of dataset

        Returns
        -------
        ReadUngriddedBase
            instance of reading class (needs to be implementation of base
            class :class:`ReadUngriddedBase`).
        """
        if data_id is None:
            if len(self.data_ids) != 1:
                raise ValueError('Please specify dataset')
        if not data_id in self.supported_datasets:
            raise NetworkNotSupported(f'Could not fetch reader class: Input '
                                      f'network {data_id} is not supported by '
                                      f'ReadUngridded')
        elif not data_id in self.data_ids:
            self.data_ids.append(data_id)

        if not data_id in self._readers:
            _cls = self._find_read_class(data_id)
            reader = self._init_lowlevel_reader(_cls, data_id)
            self._readers[data_id] = reader
        return self._readers[data_id]

    def _find_read_class(self, data_id):
        """Find reading class for dataset name

        Loops over all reading classes available in :attr:`SUPPORTED_READERS`
        and finds the first one that matches the input dataset name, by
        checking the attribute :attr:`SUPPORTED_DATASETS` in each respective
        reading class.

        Parameters
        -----------
        data_id : str
            Name of dataset

        Returns
        -------
        ReadUngriddedBase
            instance of reading class (needs to be implementation of base
            class :class:`ReadUngriddedBase`)

        Raises
        ------
        NetworkNotImplemented
            if network is supported but no reading routine is implemented yet

        """
        for _cls in self.SUPPORTED_READERS:
            if data_id in _cls.SUPPORTED_DATASETS:
                return _cls
        raise NetworkNotImplemented(f'Could not find reading class for dataset '
                                    f'{data_id}')

    def _init_lowlevel_reader(self, reader, data_id):
        """
        Initiate lowlevel reader for input data ID

        Parameters
        ----------
        reader
            reader class (not instantiated)
        data_id : str
            ID of dataset to be isntantiated with input reader

        Returns
        -------
        ReadUngriddedBase
            instantiated reader class for input ID.

        """
        if data_id in self.data_dirs:
            ddir = self.data_dirs[data_id]
            const.print_log.info(
                f'Reading {data_id} from specified data loaction: {ddir}'
            )
        else:
            ddir = None
        return reader(data_id=data_id, data_dir=ddir)

    def _get_vars_to_retrieve(self, data_id):
        """Helper to retrieve variables to be read for a given dataset

        Parameters
        ----------
        data_id : str
            ID of dataset to be imported

        Raises
        ------
        DataRetrievalError
            if :attr:`vars_to_retrieve` is a dictionary (i.e., dataset
            specific) and the input data ID is not specified therein.

        Returns
        -------
        list
            list of variable to be retrieved
        """
        vtr = self.vars_to_retrieve
        if isinstance(vtr, list):
            return vtr
        #vars_to_retrieve is a dict (dataset specific)
        if not data_id in vtr:
            raise DataRetrievalError(
                f'Missing specification of vars_to_retrieve for {data_id}'
                )
        return vtr[data_id]

    def read_dataset(self, data_id, vars_to_retrieve=None,
                     only_cached=False, filter_post=None, **kwargs):
        """Read dataset into an instance of :class:`ReadUngridded`

        Parameters
        ----------
        data_id : str
            name of dataset
        vars_to_retrieve : str or list
            variable or list of variables to be imported
        only_cached : bool
            if True, then nothing is reloaded but only data is loaded that is
            available as cached objects (not recommended to use but may be
            used if working offline without connection to database)
        filter_post : dict, optional
            filters applied to `UngriddedData` object AFTER it is read into
            memory, via :func:`UngriddedData.apply_filters`. This option was
            introduced in pyaerocom version 0.10.0 and should be used
            preferably over **kwargs. There is a certain flexibility with
            respect to how these filters can be defined, for instance, sub
            dicts for each `data_id`. The most common way would be
            to provide directly the input needed for
            `UngriddedData.apply_filters`. If you want to read multiple variables
            from one or more datasets, and if you want to apply variable
            specific filters, it is recommended to read the data individually
            for each variable and corresponding set of filters and then
            merge the individual filtered `UngriddedData` objects afterwards,
            e.g. using `data_var1 & data_var2`.
        **kwargs
            Additional input options for reading of data, which are applied
            WHILE the data is read. If any such additional options are
            provided that are applied during the reading, then automatic
            caching of the output `UngriddedData` object will be deactivated.
            Thus, it is recommended to handle data filtering via `filter_post`
            argument whenever possible, which will result in better performance
            as the unconstrained original data is read in and cached, and then
            the filtering is applied.

        Returns
        --------
        UngriddedData
            data object
        """
        _caching = None
        if len(kwargs) > 0:
            _caching = const.CACHING
            const.CACHING = False

            print_log.info('Received additional reading constraints, '
                           'ignoring caching')

        reader = self.get_lowlevel_reader(data_id)

        if vars_to_retrieve is not None:
            # Note: self.vars_to_retrieve may be None as well, then
            # default variables of each network are read
            self.vars_to_retrieve = vars_to_retrieve

        if self.vars_to_retrieve is None:
            self.vars_to_retrieve = reader.PROVIDES_VARIABLES

        vars_to_retrieve = varlist_aerocom(self.vars_to_retrieve)

        # Since this interface enables to load multiple datasets, each of
        # which support a number of variables, here, only the variables are
        # considered that are supported by the dataset
        vars_available = [var for var in vars_to_retrieve if
                          reader.var_supported(var)]
        if len(vars_available) == 0:
            raise DataRetrievalError('None of the input variables ({}) is '
                                     'supported by {} interface'
                                     .format(vars_to_retrieve, data_id))
        cache = CacheHandlerUngridded(reader)
        if not self.ignore_cache:
            # initate cache handler
            for var in vars_available:
                try:
                    cache.check_and_load(var,
                                         force_use_outdated=only_cached)
                except Exception:
                    logger.exception('Fatal: compatibility error between '
                                          'old cache file {} and current version '
                                          'of code ')

        if not only_cached:
            vars_to_read = [v for v in vars_available if not v in cache.loaded_data]
        else:
            vars_to_read = []

        data_read = None
        if len(vars_to_read) > 0:

            _loglevel = print_log.level
            print_log.setLevel(logging.INFO)
            data_read = reader.read(vars_to_read, **kwargs)
            print_log.setLevel(_loglevel)

            for var in vars_to_read:
                # write the cache file
                if not self.ignore_cache:
                    try:
                        cache.write(data_read, var)
                    except Exception as e:
                        _caching = False
                        print_log.warning('Failed to write to cache directory. '
                                          'Error: {}. Deactivating caching in '
                                          'pyaerocom'.format(repr(e)))

        if len(vars_to_read) == len(vars_available):
            data_out = data_read
        else:
            data_out = UngriddedData()
            for var in vars_available:
                if var in cache.loaded_data:
                    data_out.append(cache.loaded_data[var])
            if data_read is not None:
                data_out.append(data_read)

        if _caching is not None:
            const.CACHING = _caching

        if filter_post:
            filters = self._eval_filter_post(filter_post,
                                             data_id,
                                             vars_available)
            data_out = data_out.apply_filters(**filters)
        return data_out

    def _eval_filter_post(self, filter_post, data_id, vars_available):
        filters = {}
        if not isinstance(filter_post, dict):
            raise ValueError(f'input filter_post must be dict, got '
                             f'{type(filter_post)}')
        elif len(filter_post) == 0:
            return filters

        if data_id in filter_post:
            # filters are specified specifically for that dataset
            subset = filter_post[data_id]
            return self._eval_filter_post(subset,
                                          data_id,
                                          vars_available)

        for key, val in filter_post.items():
            if key == 'ignore_station_names': # for backwards compatibility
                if isinstance(val, (str, list)):
                    filters['station_name'] = val
                    if not 'negate' in filters:
                        filters['negate'] = []
                    filters['negate'].append('station_name')

                elif isinstance(val, dict): #variable specific station filtering
                    if len(vars_available) > 1:
                        raise NotImplementedError(
                            f'Cannot filter different sites for multivariable '
                            f'UngriddedData objects (i.e. apply filter '
                            f'ignore_station_names={val} for UngriddedData '
                            f'object containing {vars_available}')
                    else:
                        # the variable that is available in the UngriddedData
                        # object
                        var = vars_available[0]
                        try:
                            filters['station_name'] = val[var]
                            if not 'negate' in filters:
                                filters['negate'] = []
                            filters['negate'].append('station_name')
                        except KeyError:
                            continue
                else:
                    raise ValueError(f'Invalid input for ignore_station_names: {val}')
            else:
                filters[key] = val
        return filters

    def read_dataset_post(self, data_id, vars_to_retrieve,
                          only_cached=False, filter_post=None, **kwargs):
        """Read dataset into an instance of :class:`ReadUngridded`

        Parameters
        ----------
        data_id : str
            name of dataset
        vars_to_retrieve : list
            variable or list of variables to be imported
        only_cached : bool
            if True, then nothing is reloaded but only data is loaded that is
            available as cached objects (not recommended to use but may be
            used if working offline without connection to database)
        filter_post : dict, optional
            filters applied to `UngriddedData` object AFTER it is read into
            memory, via :func:`UngriddedData.apply_filters`. This option was
            introduced in pyaerocom version 0.10.0 and should be used
            preferably over **kwargs. There is a certain flexibility with
            respect to how these filters can be defined, for instance, sub
            dicts for each `data_id`. The most common way would be
            to provide directly the input needed for
            `UngriddedData.apply_filters`. If you want to read multiple variables
            from one or more datasets, and if you want to apply variable
            specific filters, it is recommended to read the data individually
            for each variable and corresponding set of filters and then
            merge the individual filtered `UngriddedData` objects afterwards,
            e.g. using `data_var1 & data_var2`.
        **kwargs
            Additional input options for reading of data, which are applied
            WHILE the data is read. If any such additional options are
            provided that are applied during the reading, then automatic
            caching of the output `UngriddedData` object will be deactivated.
            Thus, it is recommended to handle data filtering via `filter_post`
            argument whenever possible, which will result in better performance
            as the unconstrained original data is read in and cached, and then
            the filtering is applied.

        Returns
        --------
        UngriddedData
            data object
        """
        aux_info = self.post_compute[data_id]
        loaded = []
        for var in vars_to_retrieve:
            input_data_ids_vars = []
            aux_info_var = aux_info['aux_requires'][var]
            for aux_id, aux_vars in aux_info_var.items():
                if aux_id in self.post_compute:
                    aux_data = self.read_dataset_post(
                                    data_id=aux_id,
                                    vars_to_retrieve=aux_vars,
                                    only_cached=only_cached,
                                    **kwargs)
                    for aux_var in aux_vars:
                        input_data_ids_vars.append((aux_data, aux_id, aux_var))
                else:

                    # read variables individually, so filter_post is more
                    # flexible if some post filters are specified for
                    # individual variables...
                    for aux_var in aux_vars:
                        _data = self.read_dataset(
                            aux_id,
                            aux_var,
                            only_cached=only_cached,
                            filter_post=filter_post,
                            **kwargs)
                        input_data_ids_vars.append((_data, aux_id, aux_var))


            aux_merge_how = aux_info['aux_merge_how'][var]

            if var in aux_info['aux_units']:
                var_unit_out = aux_info['aux_units'][var]
            else:
                var_unit_out = None

            if aux_merge_how == 'eval':
                # function MUST be defined
                aux_fun = aux_info['aux_funs'][var]
            else:
                aux_fun = None

            merged_stats = combine_vardata_ungridded(
                data_ids_and_vars=input_data_ids_vars,
                merge_eval_fun=aux_fun,
                merge_how=aux_merge_how,
                var_name_out=var,
                var_unit_out=var_unit_out,
                data_id_out=aux_info['data_id'])
            loaded.append(UngriddedData.from_station_data(merged_stats))
        first = loaded[0]
        if len(loaded) == 1:
            return first
        for data in loaded[1:]:
            first.append(data)
        return first

    def read(self, data_ids=None, vars_to_retrieve=None,
             only_cached=False, filter_post=None, **kwargs):
        """Read observations

        Iter over all datasets in :attr:`data_ids`, call
        :func:`read_dataset` and append to data object

        Parameters
        ----------
        data_ids : str or list
            data ID or list of all datasets to be imported
        vars_to_retrieve : str or list
            variable or list of variables to be imported
        only_cached : bool
            if True, then nothing is reloaded but only data is loaded that is
            available as cached objects (not recommended to use but may be
            used if working offline without connection to database)
        filter_post : dict, optional
            filters applied to `UngriddedData` object AFTER it is read into
            memory, via :func:`UngriddedData.apply_filters`. This option was
            introduced in pyaerocom version 0.10.0 and should be used
            preferably over **kwargs. There is a certain flexibility with
            respect to how these filters can be defined, for instance, sub
            dicts for each `data_id`. The most common way would be
            to provide directly the input needed for
            `UngriddedData.apply_filters`. If you want to read multiple variables
            from one or more datasets, and if you want to apply variable
            specific filters, it is recommended to read the data individually
            for each variable and corresponding set of filters and then
            merge the individual filtered `UngriddedData` objects afterwards,
            e.g. using `data_var1 & data_var2`.
        **kwargs
            Additional input options for reading of data, which are applied
            WHILE the data is read. If any such additional options are
            provided that are applied during the reading, then automatic
            caching of the output `UngriddedData` object will be deactivated.
            Thus, it is recommended to handle data filtering via `filter_post`
            argument whenever possible, which will result in better performance
            as the unconstrained original data is read in and cached, and then
            the filtering is applied.

        Example
        -------
        >>> import pyaerocom.io.readungridded as pio
        >>> from pyaerocom import const
        >>> obj = pio.ReadUngridded(data_id=const.AERONET_SUN_V3L15_AOD_ALL_POINTS_NAME)
        >>> obj.read()
        >>> print(obj)
        >>> print(obj.metadata[0.]['latitude'])

        """
        if data_ids is not None:
            self.data_ids = data_ids
        if vars_to_retrieve is not None:
            self.vars_to_retrieve = vars_to_retrieve

        data = UngriddedData()
        for ds in self.data_ids:
            read_vars = self._get_vars_to_retrieve(ds)
            logger.info(f'Reading {ds} data, variables: {read_vars}')
            if ds in self.post_compute:
                data.append(self.read_dataset_post(ds, read_vars,
                                                   only_cached=only_cached,
                                                   filter_post=filter_post,
                                                   **kwargs))
            else:
                data.append(self.read_dataset(ds, read_vars,
                                              only_cached=only_cached,
                                              filter_post=filter_post,
                                              **kwargs))

            logger.info('Successfully imported {} data'.format(ds))
        return data

    def get_vars_supported(self, obs_id, vars_desired):
        """
        Filter input list of variables by supported ones for a certain data ID

        Parameters
        ----------
        obs_id : str
            ID of observation network
        vars_desired : list
            List of variables that are desired

        Returns
        -------
        list
            list of variables that can be read through the input network

        """
        obs_vars = []
        if isinstance(vars_desired, str):
            vars_desired = [vars_desired]
        if obs_id in self.post_compute:
            # check if all required are accessible
            postinfo = self.post_compute[obs_id]
            for var in varlist_aerocom(vars_desired):
                if not var in postinfo['vars_supported']:
                    continue
                requires = postinfo['aux_requires'][var]
                all_good = True
                for ds, vars_required in requires.items():
                    if isinstance(vars_required,str):
                        vars_required = [vars_required]
                    vars_avail = self.get_vars_supported(ds, vars_required)
                    if not len(vars_required) == len(vars_avail):
                        all_good = False
                        break
                if all_good:
                    obs_vars.append(var)

        else:
            # check if variable can be read from a dataset on disk
            _oreader = self.get_lowlevel_reader(obs_id)
            for var in varlist_aerocom(vars_desired):
                if _oreader.var_supported(var):
                    obs_vars.append(var)
        return obs_vars

    def __str__(self):
        s=''
        for ds in self.data_ids:
            s += '\n{}'.format(self.get_lowlevel_reader(ds))
        return s

if __name__=="__main__":
    import pyaerocom as pya
    ebas_local = os.path.join(pya.const.OUTPUTDIR, 'data/obsdata/EBASMultiColumn/data')
    reader = ReadUngridded(['blaaaa'],
                           data_dirs={'EBASMC' : ebas_local}
                           )

    data = reader.read('EBASMC', 'ac550aer')