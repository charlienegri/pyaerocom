import pytest
import os
from pyaerocom.conftest import lustre_unavail, testdata_unavail
from pyaerocom.io.read_emep import ReadEMEP, ts_type_from_filename
from pyaerocom.griddeddata import GriddedData
from pyaerocom.colocation import colocate_gridded_gridded
from pyaerocom.colocation import ColocatedData


def test_read_emep():
    r = ReadEMEP()
    assert r.data_id == None
    assert r.vars_provided == []
    assert r.filepath == None
    assert r.years_avail == []
    with pytest.raises(FileNotFoundError):
        ReadEMEP(data_dir='/invalid')
    with pytest.raises(FileNotFoundError):
        ReadEMEP(filepath='/invalid/test.nc')


@testdata_unavail
def test_read_emep_read_var(path_emep):
    with pytest.raises(ValueError):
        r = ReadEMEP()
        r.read_var('od550aer')
    with pytest.raises(ValueError):
        r = ReadEMEP()
        r.read_var('od550aer')
    data_dir = path_emep['data_dir']
    with pytest.raises(FileNotFoundError):
        r = ReadEMEP(data_dir=data_dir)
        r.read_var('od550aer')

@testdata_unavail
def test_read_emep_data(path_emep):
    path = path_emep['daily']
    r = ReadEMEP(filepath=path)

    vars_provided = r.vars_provided
    assert isinstance(vars_provided, list)
    assert 'vmro3' in vars_provided

    data = r.read_var('vmro3', ts_type='daily')
    assert isinstance(data, GriddedData)
    assert data.time.long_name == 'time'
    assert data.time.standard_name == 'time'

@testdata_unavail
def test_read_emep_directory(path_emep):
    data_dir = path_emep['data_dir']
    r = ReadEMEP(data_dir=data_dir)
    assert r.data_dir == data_dir
    vars_provided = r.vars_provided
    assert 'vmro3' in vars_provided
    assert 'concpm10' in vars_provided
    assert 'concno2' in vars_provided
    paths = r._get_paths()
    assert len(paths) == 3

@pytest.mark.parametrize('files, ts_types', [
    (['Base_hour.nc','test.nc','Base_month.nc', 'Base_day.nc', 'Base_fullrun.nc'], ['hourly','monthly','daily','yearly'])
])
def test_read_emep_ts_types(files, ts_types, tmpdir):
    for filename in files:
        open(os.path.join(tmpdir, filename), 'a').close()
    r = ReadEMEP(data_dir=tmpdir)
    assert sorted(r.ts_types) == sorted(ts_types)

@pytest.mark.parametrize('filename,ts_type', [
    ('Base_hour.nc', 'hourly'),
    ('Base_month.nc', 'monthly'),
    ('Base_day.nc', 'daily'),
    ('Base_fullrun', 'yearly')
    ])
def test_ts_type_from_filename(filename, ts_type):
    assert ts_type_from_filename(filename) == ts_type

def test_read_emep_years_avail(path_emep):
    data_dir = path_emep['data_dir']
    r = ReadEMEP(data_dir=data_dir)
    assert r.years_avail == [2017]

def test_preprocess_units():
    units = ''
    prefix = 'AOD'
    assert ReadEMEP().preprocess_units(units, prefix) == '1'

    units = 'mgS/m2'
    with pytest.raises(NotImplementedError):
        ReadEMEP().preprocess_units(units)

if __name__ == '__main__':
    import sys
    pytest.main(sys.argv)
