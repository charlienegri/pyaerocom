import os
import pytest
import json

import numpy as np
from pandas import DataFrame
from pyaerocom import const
from pyaerocom.colocation_auto import ColocationSetup, Colocator
from pyaerocom.colocateddata import ColocatedData
from pyaerocom.griddeddata import GriddedData
from pyaerocom.ungriddeddata import UngriddedData

from pyaerocom.conftest import tda, does_not_raise_exception
from pyaerocom.aeroval import AerocomEvaluation
from pyaerocom.io.aux_read_cubes import add_cubes

PROJ_ID = 'project'
EXP_ID = 'exp'

OBS_ID = 'AeronetSunV3L2Subset.daily'
OBS_NAME = 'AeronetSun'
OBS_VARS = 'od550aer'
OBS_VERT_TYPE = 'Column'

MODEL_NAME = 'TM5'
MODEL_ID = 'TM5-met2010_CTRL-TEST'
TS_TYPE = 'monthly'
START = 2010


CONFIG = tda.testdatadir.joinpath(tda.ADD_PATHS['CONFIG'])
METHODS_FILE = CONFIG.joinpath('cube_read_methods.py')

@pytest.fixture(scope='function')
def model_config():
    config = {MODEL_NAME : dict(model_id=MODEL_ID,
                                model_ts_type_read=TS_TYPE,
                                vert_which=OBS_VERT_TYPE
                                )}
    return config

@pytest.fixture(scope='function')
def obs_config():
    config = {OBS_NAME : dict(obs_id=OBS_ID,
                              obs_vars=OBS_VARS,
                              obs_vert_type=OBS_VERT_TYPE)}
    return config

@pytest.fixture(scope='function')
def model_config_aux(model_config):
    config = model_config.copy()
    config[MODEL_NAME]['model_read_aux'] = {'od550aer' : dict(
        vars_required=['od550aer', 'od550aer'],
        fun='add_cubes')}
    return config

@pytest.fixture(scope='function')
def stp(model_config, obs_config,tmpdir):
    return AerocomEvaluation(proj_id=PROJ_ID, exp_id=EXP_ID,
                             model_config=model_config,
                             obs_config=obs_config, start=START,
                             ts_type=TS_TYPE,
                             raise_exceptions=True,
                             reanalyse_existing=True,
                             out_basedir=str(tmpdir))

@pytest.fixture(scope='function')
def stp_min(tmpdir):
    return AerocomEvaluation(proj_id=PROJ_ID, exp_id=EXP_ID,
                             reanalyse_existing=True,
                             raise_exceptions=True,
                             out_basedir=str(tmpdir))

def test_AerocomEvaluation_type(stp_min):
    assert isinstance(stp_min, AerocomEvaluation)


@pytest.mark.parametrize('args,raises,chk_attrs', [
    ({},pytest.raises(TypeError),{}),
    ({'proj_id':'bla'}, pytest.raises(TypeError),{}),
    ({'proj_id':'bla', 'exp_id' : 'blub'},
     does_not_raise_exception(),{}),
    ({'proj_id' : 'bla', 'exp_id' : 'blub',
      'init_output_dirs' : False}, does_not_raise_exception(),{}),
    ({'proj_id' : 'bla', 'exp_id' : 'blub',
      'basedir_coldata' : '/home'}, pytest.raises(AttributeError),{}),
    ({'proj_id' : 'bla', 'exp_id' : 'blub',
      'basedir_coldata' : '/home'}, pytest.raises(AttributeError),{}),
    ])
def test_AerocomEvaluation___init__(args,raises,chk_attrs):
    with raises:
        stp = AerocomEvaluation(**args)
        assert isinstance(stp, AerocomEvaluation)
        for key, val in chk_attrs.items():
            _val = getattr(stp, key)
            assert _val == val

def test_AerocomEvaluation_autoset_pi():
    stp = AerocomEvaluation('bla', 'blub')
    from getpass import getuser
    pi = getuser()
    assert stp.pi == pi

def test_AerocomEvaluation_DEFAULT_STATISTICS_FREQS(stp_min):
    assert stp_min.DEFAULT_STATISTICS_FREQS == ['daily', 'monthly', 'yearly']

def test_AerocomEvaluation_statistics_freqs(stp_min):
    assert stp_min.statistics_freqs == stp_min.DEFAULT_STATISTICS_FREQS

def test_AerocomEvaluation_start_stop_colocation(stp):
    assert stp.start_stop_colocation == (START, None)

def test_AerocomEvaluation__heatmap_files(tmpdir):
    stp = AerocomEvaluation('bla', 'blub', out_basedir=tmpdir)
    hm_files = stp._heatmap_files
    assert len(hm_files) == len(stp.statistics_freqs)
    for freq, fp in hm_files.items():
        assert freq in stp.statistics_freqs
        assert os.path.basename(fp) == f'glob_stats_{freq}.json'

def test_AerocomEvaluation__get_web_iface_name():
    stp = AerocomEvaluation('bla', 'blub',
                            obs_config={
                                'obs1' : dict(obs_id='obs_id1',
                                              obs_vars='var1',
                                              obs_vert_type='Column',
                                              web_interface_name='bla'),
                                'obs2' : dict(obs_id='obs_id1',
                                              obs_vars='var1',
                                              obs_vert_type='Column')
                                }
                            )
    assert stp._get_web_iface_name('obs1') == 'bla'
    assert stp._get_web_iface_name('obs2') == 'obs2'


def test_AerocomEvaluation_init_json_output_dirs_default():
    stp = AerocomEvaluation('bla','blub')
    stp.init_json_output_dirs()
    bdir = stp.out_basedir
    dirs_keys = ['map', 'ts', 'ts/dw', 'scat', 'hm', 'profiles', 'contour']
    assert os.path.exists(bdir)
    default_out = os.path.join(const.OUTPUTDIR, 'aeroval')
    assert os.path.samefile(default_out, bdir)
    dirs = stp.out_dirs
    assert isinstance(dirs, dict)
    for key, val in dirs.items():
        assert key in dirs_keys
        assert os.path.exists(val)


def test_AerocomEvaluation_run_colocation(stp):

    mid = 'TM5-met2010_CTRL-TEST'
    var_name = 'od550aer'
    col = stp.run_colocation(model_name='TM5',
                             obs_name='AeronetSun',
                             var_name=var_name)


    assert isinstance(col, Colocator)
    assert mid in col.data
    assert var_name in col.data[mid]
    coldata = col.data[mid][var_name]
    assert isinstance(coldata, ColocatedData)
    assert coldata.shape == (2, 12, 8)

def test_AerocomEvaluation_run_evaluation(stp):
    col_paths = stp.run_evaluation(update_interface=False,
                                   reanalyse_existing=False) #reuse model colocated data from prev. test
    assert len(col_paths) == 1
    assert os.path.isfile(col_paths[0])

def test_AerocomEvaluation_get_web_overview_table(stp, tmpdir):
    stp.update()
    stp.run_evaluation(update_interface=False)
    table = stp.get_web_overview_table()
    assert isinstance(table, DataFrame)
    assert len(table) > 0

def test_AerocomEvaluation_get_custom_read_method_model_file(stp,
                                                              model_config_aux):
    stp.add_methods_file = METHODS_FILE
    stp.model_config = model_config_aux
    fun = stp.get_custom_read_method_model('add_cubes')
    assert fun == add_cubes

def test_AerocomEvaluation_get_custom_read_method_model_parameter(stp,
                                                                   model_config_aux):
    stp.add_methods={'add_cubes':add_cubes}
    fun = stp.get_custom_read_method_model('add_cubes')
    assert fun == add_cubes

def test_AerocomEvaluation_all_obs_vars(stp):
    assert stp.all_obs_vars == [OBS_VARS]

def test_AerocomEvaluation_get_model_name(stp):
    assert stp.get_model_name(MODEL_ID) == MODEL_NAME

def test_AerocomEvaluation___str__(stp):
    assert isinstance(str(stp), str)

def test_AerocomEvaluation_output_files(stp, tmpdir):
    stp.out_basedir = tmpdir
    stp.run_evaluation(update_interface=False)

    # Check that folders were created
    for dir in stp.OUT_DIR_NAMES:
        path = os.path.join(stp.exp_dir, dir)
        assert os.path.isdir(path)

    # Check values of one timeseries json file
    json_path = os.path.join(stp.exp_dir, 'ts/EUROPE_OBS-AeronetSun:od550aer_Column.json')
    with open(json_path) as f:
        data = json.load(f)

    data = data['TM5']
    values = []
    should_be = [0.12592844665050507, 0.1256496376978308, 0.16510479006400725,
                 0.18525996804237366, ]
    stats = ['monthly_mod', 'monthly_obs', 'yearly_obs', 'yearly_mod']
    for stat in stats:
        values.append(data[stat][0])
    np.allclose(values, should_be, rtol=1e-8)
    assert data['daily_obs'] == []
    assert data['daily_mod'] == []

def test_AerocomEvaluation_to_from_json(stp, tmpdir):
    stp.to_json(tmpdir)
    config_filename = 'cfg_{}_{}.json'.format(PROJ_ID, EXP_ID)

    cfg_fp = os.path.join(tmpdir, config_filename)
    assert os.path.exists(cfg_fp)
    stp_new = AerocomEvaluation(PROJ_ID, EXP_ID, config_dir=tmpdir,
                                try_load_json=True)
    assert stp.colocation_settings == stp_new.colocation_settings
    assert stp.obs_config == stp_new.obs_config
    assert stp.model_config == stp_new.model_config

def test_AerocomEvaluation_read_model_data(stp):
    data = stp.read_model_data(MODEL_NAME, OBS_VARS)
    assert isinstance(data, GriddedData)
    with pytest.raises(ValueError):
        stp.read_model_data('model_name', 'od550aer')

def test_AerocomEvaluation_read_ungridded_obsdata(stp):
    data = stp.read_ungridded_obsdata(OBS_NAME, vars_to_read=[OBS_VARS])
    assert isinstance(data, UngriddedData)

@pytest.mark.parametrize('search,expected,fun_name',[
    ('TM*', [MODEL_NAME], 'find_model_matches'),
    ('Aero*', [OBS_NAME], 'find_obs_matches'),
])
def test_AerocomEvaluation_find_matches(stp, search, expected, fun_name):
    search_fun = getattr(AerocomEvaluation, fun_name)
    assert search_fun(stp, search) == expected

# @ejgal: keep these tests until deciding if test_AerocomEvaluation_find_matches is ok
# def test_AerocomEvaluation_find_model_matches(stp):
#     matches = stp.find_model_matches('TM*')
#     assert matches == [MODEL_NAME]
#
# def test_AerocomEvaluation_find_obs_matches(stp):
#     matches = stp.find_obs_matches('Aero*')
#     assert matches == [OBS_NAME]

@pytest.mark.parametrize('expected,property',[
    ([MODEL_NAME], 'all_model_names'),
    ([OBS_NAME], 'all_obs_names'),
])
def test_AerocomEvaluation_all_names(stp, expected, property):
    assert getattr(stp, property) == expected

# @ejgal: keep these tests until deciding if test_AerocomEvaluation_all_names is ok.
# def test_AerocomEvaluation_all_model_names(stp):
#     assert stp.all_model_names == [MODEL_NAME]
#
# def test_AerocomEvaluation_all_obs_names(stp):
#     assert stp.all_obs_names == [OBS_NAME]

def test_AerocomEvaluation_find_obs_name(stp):
    obs_name = stp.find_obs_name(OBS_ID, OBS_VARS)
    assert obs_name == OBS_NAME

def test_AerocomEvaluation_find_model_name(stp):
    model_name = stp.find_model_name(MODEL_ID)
    assert model_name == MODEL_NAME

@pytest.mark.parametrize('key,val,expected',[
    ('proj_id', ['project'], AttributeError),
    ('exp_id', ['exp'], AttributeError)
])
def test_AerocomEvaluation_check_config(stp_min, key, val, expected):
    stp_min[key] = val
    with pytest.raises(expected):
        stp_min.check_config()

@pytest.mark.parametrize('config_name,name,id',[
    ('model_config', MODEL_NAME, 'model_id'),
    ('obs_config', OBS_NAME, 'obs_id')
])
def test_AerocomEvaluation_check_config_model_obs(stp, config_name, name, id):
    del stp[config_name][name][id]
    with pytest.raises(KeyError):
        stp.check_config()

if __name__ == '__main__':
    import sys
    pytest.main(sys.argv)