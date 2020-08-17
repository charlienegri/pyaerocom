#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  9 14:14:29 2018
"""

# TODO: Docstrings
import pytest
import numpy.testing as npt
from pandas import DataFrame
from pyaerocom.conftest import TEST_RTOL, lustre_unavail, testdata_unavail
from pyaerocom.io.readgridded import ReadGridded

START = "1-1-2003"
STOP = "31-12-2007"

def init_reader():
    return ReadGridded(data_id="ECMWF_CAMS_REAN")

@pytest.fixture(scope='session')
def reader_reanalysis():
    return init_reader()

@pytest.fixture(scope='module')
def reader_tm5():
    return ReadGridded('TM5-met2010_CTRL-TEST')


@pytest.mark.parametrize('input_args,mean_val', [
    (dict(var_name='od550aer', ts_type='monthly'), 0.1186),
    (dict(var_name='od550aer', ts_type='monthly', constraints={
                                  'var_name'   : 'od550aer',
                                  'operator'   : '>',
                                  'filter_val' : 1000
                                  }), 0.1186),
    (dict(var_name='od550aer', ts_type='monthly', constraints={
                                  'var_name'   : 'od550aer',
                                  'operator'   : '<',
                                  'filter_val' : 0.1
                                  }), 0.2062),
    (dict(var_name='od550aer', ts_type='monthly', constraints=[
        {'var_name'   : 'od550aer',
         'operator'   : '<',
         'filter_val' : 0.1},
        {'var_name'   : 'od550aer',
         'operator'   : '>',
         'filter_val' : 0.11}
        ]), 0.1047)
    ])
def test_read_var(reader_tm5, input_args, mean_val):
    data = reader_tm5.read_var(**input_args)
    npt.assert_allclose(data.mean(), mean_val, rtol=1e-3)

def test_ReadGridded_class_empty():
    r = ReadGridded()
    assert r.data_id == None
    assert r.data_dir == None
    from pyaerocom.io.aerocom_browser import AerocomBrowser
    assert isinstance(r.browser, AerocomBrowser)

    failed = False
    try:
        r.years_avail
    except AttributeError:
        failed = True
    assert failed
    assert r.vars_filename == []

@lustre_unavail
def test_file_info(reader_reanalysis):
    assert isinstance(reader_reanalysis.file_info, DataFrame)
    assert len(reader_reanalysis.file_info.columns) == 12, 'Mismatch colnum file_info (df)'

@lustre_unavail
def test_years_available(reader_reanalysis):
    years = list(range(2003, 2020)) + [9999]
    npt.assert_array_equal(reader_reanalysis.years_avail, years)

@lustre_unavail
def test_data_dir(reader_reanalysis):
    assert reader_reanalysis.data_dir.endswith('aerocom/aerocom-users-database/ECMWF/ECMWF_CAMS_REAN/renamed')

@lustre_unavail
def test_read_var_lustre(reader_reanalysis):
    from numpy import datetime64
    d = reader_reanalysis.read_var(var_name="od550aer", ts_type="daily",
                         start=START, stop=STOP)

    from pyaerocom import GriddedData
    assert isinstance(d, GriddedData)
    npt.assert_array_equal([d.var_name, sum(d.shape), d.start, d.stop],
                           ["od550aer", 1826 + 161 + 320,
                            datetime64('2003-01-01T00:00:00.000000'),
                            datetime64('2007-12-31T23:59:59.999999')])
    vals = [d.longitude.points[0],
            d.longitude.points[-1],
            d.latitude.points[0],
            d.latitude.points[-1]]
    nominal = [-180.0, 178.875, 90.0, -90.0]
    npt.assert_allclose(actual=vals, desired=nominal, rtol=TEST_RTOL)
    return d

@lustre_unavail
def test_prefer_longer(reader_reanalysis):
    daily = reader_reanalysis.read_var('od550aer', ts_type='monthly',
                             flex_ts_type=True,
                             prefer_longer=True)
    assert daily.ts_type == 'daily'

@lustre_unavail
def test_read_vars(reader_reanalysis):
    data = reader_reanalysis.read(['od440aer', 'od550aer', 'od865aer'],
                        ts_type="daily", start=START, stop=STOP)
    vals = [len(data),
            sum(data[0].shape),
            sum(data[1].shape),
            sum(data[2].shape)]
    nominal = [3, 2307, 2307, 2307]
    npt.assert_array_equal(vals, nominal)

if __name__=="__main__":
    import sys
    pytest.main(sys.argv)
