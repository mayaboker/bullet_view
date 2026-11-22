from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6 import QtCore, QtWidgets
from pymavlink.dialects.v20 import common as wire
from bullet_view.parameter_protocol import (BY_PATH, CATALOG, CATALOG_ID, CATALOG_VERSION,
    REVISION_ID, PARAMETER_IDS, INT64, profile_values, encode_value)
from bullet_view.parameters import ParameterClient, ParameterSnapshot, yaml_export
from bullet_view.parameter_view import ParameterPanel
from bullet_view.model import TelemetrySnapshot
NavigatorConfig = pytest.importorskip('los_tracking', reason='legacy parameter panel is disabled').NavigatorConfig

PROFILE=Path(__file__).resolve().parents[3]/'config/betaflight_los_heavy_quad.yaml'


class Mav:
    def __init__(self):self.calls=[]
    def __getattr__(self,name):return lambda *args:self.calls.append((name,args))


def message(id,value, *, revision=0, ack=None, source=(1,1)):
    p=next((p for p in CATALOG if p.id==id),None)
    type=p.wire_type if p else INT64
    raw=encode_value(value,type)
    m=(wire.MAVLink_param_ext_value_message(id.encode(),raw,type,len(PARAMETER_IDS),PARAMETER_IDS.index(id)) if ack is None
       else wire.MAVLink_param_ext_ack_message(id.encode(),raw,type,ack))
    return wire.MAVLink(None).parse_char(m.pack(wire.MAVLink(None,srcSystem=source[0],srcComponent=source[1])))


def loaded():
    values={CATALOG_ID:CATALOG_VERSION,REVISION_ID:0,**profile_values(asdict(NavigatorConfig.from_yaml(PROFILE)))}
    return ParameterSnapshot(tuple(values.items()),complete=True,online=True,target=(1,1))


def test_yaml_export_is_complete_reloadable_and_degree_based(tmp_path):
    snapshot=loaded()
    destination=tmp_path/'profile.yaml'
    destination.write_text(yaml_export(snapshot))
    assert NavigatorConfig.from_yaml(destination)==NavigatorConfig.from_yaml(PROFILE)
    assert 'approach_pitch_deg:' in destination.read_text()
    assert 'camera_to_body_xyzw:' in destination.read_text()
    with pytest.raises(ValueError):yaml_export(replace(snapshot,pending=True))


def test_download_retries_missing_parameters_and_checks_revision():
    client=ParameterClient();mav=Mav()
    client.target=(1,1);client.online=True;client.last_heartbeat=0.
    client.refresh(mav,0.)
    client.handle(message(REVISION_ID,0),.1,mav)
    values=dict(loaded().values)
    missing='LOS_AZ_KP'
    for id,value in reversed(list(values.items())):
        if id!=missing:client.handle(message(id,value),.2,mav)
    client.poll(mav,1.3)
    assert mav.calls[-1][0]=='param_ext_request_read_send'
    assert mav.calls[-1][1][2]==missing.encode()
    client.handle(message(missing,2.2),1.4,mav)
    client.handle(message(REVISION_ID,1),1.5,mav)
    assert not client.complete and client.phase=='head'
    assert client.restarts==1


def test_write_retries_then_readback_and_stale_protection():
    client=ParameterClient();mav=Mav()
    client.target=(1,1);client.online=True;client.complete=True;client.phase='ready';client.last_heartbeat=0.
    client.values=dict(loaded().values)
    client.set(mav,'LOS_AZ_KP',1.5,0.)
    for now in [1.,2.,3.]:
        client.last_heartbeat=now
        client.poll(mav,now)
    assert [name for name,_ in mav.calls].count('param_ext_set_send')==3
    assert mav.calls[-1][0]=='param_ext_request_read_send'
    client.handle(message('LOS_AZ_KP',1.5),3.1,mav)
    assert client.pending is None and client.statuses['LOS_AZ_KP']=='Confirmed by readback'
    client.poll(mav,7.)
    assert not client.online and not client.complete


def test_wrong_source_and_catalog_do_not_confirm_write():
    client=ParameterClient();mav=Mav()
    client.target=(1,1);client.online=True;client.complete=True;client.phase='ready'
    client.set(mav,'LOS_AZ_KP',1.5,0.)
    client.handle(message('LOS_AZ_KP',1.5,ack=0,source=(2,1)),.1,mav)
    assert client.pending is not None
    client.handle(message('LOS_AZ_KP',2.2,ack=2),.2,mav)
    assert client.statuses['LOS_AZ_KP']=='Rejected'


class Presenter(QtCore.QObject):
    snapshot_changed=QtCore.Signal(object)
    parameters_changed=QtCore.Signal(object)
    def __init__(self):super().__init__();self.applied=[]
    def apply_parameter(self,*args):self.applied.append(args)
    def refresh_parameters(self):pass


def test_parameter_panel_search_filters_favorites_and_apply(tmp_path):
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    presenter=Presenter()
    settings=QtCore.QSettings(str(tmp_path/'favorites.ini'),QtCore.QSettings.Format.IniFormat)
    panel=ParameterPanel(presenter,settings=settings)
    presenter.parameters_changed.emit(loaded())
    panel.search.setText('AZIMUTH_KP')
    row,edit,apply=panel.rows['LOS_AZ_KP']
    assert not panel.table.isRowHidden(row)
    assert all(panel.table.isRowHidden(i) for i in range(len(CATALOG)) if i!=row)
    edit.setText('1.5');edit.textEdited.emit('1.5')
    apply.click()
    assert presenter.applied==[('LOS_AZ_KP',1.5)]
    panel.table.item(row,0).setCheckState(QtCore.Qt.CheckState.Checked)
    panel.favorites_only.setChecked(True)
    panel.category.setCurrentText('Yaw')
    assert panel.table.isRowHidden(row)
    panel.category.setCurrentText('LOS Lateral')
    assert not panel.table.isRowHidden(row)
    other=ParameterPanel(presenter,settings=settings)
    assert 'LOS_AZ_KP' in other.favorites
    presenter.parameters_changed.emit(replace(loaded(),pending=True))
    assert not panel.export.isEnabled() and not apply.isEnabled()
    panel.close();other.close()


def test_old_success_does_not_reject_a_new_write_and_unconfirmed_can_refresh(tmp_path):
    client=ParameterClient();mav=Mav()
    client.target=(1,1);client.online=True;client.complete=True;client.phase='ready'
    client.set(mav,'LOS_AZ_KP',1.5,0.)
    client.handle(message('LOS_AZ_KP',2.2,ack=0),.1,mav)
    assert client.pending is not None
    client.statuses['LOS_AZ_KP']='Unconfirmed';client.pending=None
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    presenter=Presenter()
    settings=QtCore.QSettings(str(tmp_path/'settings.ini'),QtCore.QSettings.Format.IniFormat)
    panel=ParameterPanel(presenter,settings=settings)
    presenter.parameters_changed.emit(client.snapshot())
    assert panel.refresh.isEnabled() and not panel.export.isEnabled()
    panel.close()


def test_catalog_mismatch_disables_edits_and_download_timeout_is_bounded():
    client=ParameterClient();mav=Mav()
    client.target=(1,1);client.online=True;client.last_heartbeat=0.
    client.refresh(mav,0.)
    client.handle(message(REVISION_ID,0),.1,mav)
    values=dict(loaded().values);values[CATALOG_ID]=999
    for id,value in values.items():client.handle(message(id,value),.2,mav)
    client.handle(message(REVISION_ID,0),.3,mav)
    assert not client.complete and client.phase=='failed'
    client.refresh(mav,1.)
    for t in [2.,3.,4.,5.]:
        client.last_heartbeat=t
        client.poll(mav,t)
    assert client.phase=='failed' and 'incomplete' in client.progress


def test_presenter_refreshes_remote_profile_before_export(tmp_path):
    from bullet_view.presenter import Presenter as RealPresenter
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    presenter=RealPresenter('test')
    snapshot=loaded()
    presenter._on_parameters(snapshot)
    path=tmp_path/'fresh.yaml'
    presenter.export_parameters(path)
    assert not path.exists()
    # A queued old ready snapshot must not trigger export.
    presenter._on_parameters(snapshot)
    assert not path.exists()
    presenter._on_parameters(replace(snapshot,complete=False))
    values=dict(snapshot.values);values['LOS_AZ_KP']=1.25;values[REVISION_ID]=1
    presenter._on_parameters(replace(snapshot,values=tuple(values.items())))
    assert NavigatorConfig.from_yaml(path).tuning.azimuth_kp==1.25
    presenter.stop()


def test_failed_export_refresh_preserves_existing_file(tmp_path):
    from bullet_view.presenter import Presenter as RealPresenter
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    presenter=RealPresenter('test')
    snapshot=loaded()
    presenter._on_parameters(snapshot)
    path=tmp_path/'existing.yaml';path.write_text('original')
    presenter.export_parameters(path)
    presenter._on_parameters(replace(snapshot,complete=False,failed=True))
    assert path.read_text()=='original'
    assert presenter._export_destination is None
    presenter.stop()
