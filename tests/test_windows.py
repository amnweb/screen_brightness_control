import ctypes
import screen_brightness_control as sbc
from typing import Type
from unittest.mock import Mock
import pytest
from pytest_mock import MockerFixture
from unittest.mock import call

from .helpers import BrightnessMethodTest
from screen_brightness_control.helpers import BrightnessMethod
from .mocks.windows_mock import mock_enum_display_devices, mock_wmi_init, FakeWinDLL


@pytest.fixture
def patch_global_get_display_info(mocker: MockerFixture):
    '''Mock everything needed to get `sbc.windows.get_display_info` to run'''
    mocker.patch.object(sbc.windows, 'enum_display_devices', mock_enum_display_devices)
    mocker.patch.object(sbc.windows, '_wmi_init', mock_wmi_init)


class TestWMI(BrightnessMethodTest):
    @pytest.fixture
    def patch_get_display_info(self, patch_global_get_display_info):
        '''Mock everything needed to get `WMI.get_display_info` to run'''
        pass

    @pytest.fixture
    def patch_get_brightness(self, mocker: MockerFixture, patch_get_display_info):
        pass

    @pytest.fixture
    def patch_set_brightness(self, mocker: MockerFixture, patch_get_display_info):
        pass

    @pytest.fixture
    def method(self) -> Type[BrightnessMethod]:
        return sbc.windows.WMI

    class TestGetBrightness(BrightnessMethodTest.TestGetBrightness):
        class TestDisplayKwarg(BrightnessMethodTest.TestGetBrightness.TestDisplayKwarg):
            # skip these because WMI doesn't really make display specific calls when getting brightness
            # and perf is negligible anyway
            @pytest.mark.skip('skip TestGetBrightness.TestDisplayKwarg perf tests for WMI')
            def test_with(self):
                pass

            @pytest.mark.skip('skip TestGetBrightness.TestDisplayKwarg perf tests for WMI')
            def test_without(self):
                pass

    class TestSetBrightness(BrightnessMethodTest.TestSetBrightness):
        class TestDisplayKwarg(BrightnessMethodTest.TestSetBrightness.TestDisplayKwarg):
            def test_with(self, mocker: MockerFixture, freeze_display_info, method):
                wmi = sbc.windows._wmi_init()
                mocker.patch.object(sbc.windows, '_wmi_init', Mock(return_value=wmi, spec=True))
                brightness_method = wmi.WmiMonitorBrightnessMethods()[0]
                mocker.patch.object(wmi, 'WmiMonitorBrightnessMethods', lambda: [brightness_method] * 3)
                spy = mocker.spy(brightness_method, 'WmiSetBrightness')
                for index, display in enumerate(freeze_display_info):
                    method.set_brightness(100, display=index)
                    spy.assert_called_once_with(100, 0)
                    spy.reset_mock()

            def test_without(self, mocker: MockerFixture, freeze_display_info, method):
                wmi = sbc.windows._wmi_init()
                mocker.patch.object(sbc.windows, '_wmi_init', Mock(return_value=wmi, spec=True))
                brightness_method = wmi.WmiMonitorBrightnessMethods()[0]
                mocker.patch.object(wmi, 'WmiMonitorBrightnessMethods', lambda: [brightness_method] * 3)
                spy = mocker.spy(brightness_method, 'WmiSetBrightness')

                method.set_brightness(100)
                spy.assert_has_calls([call(100, 0)] * 3)
                spy.reset_mock()


class TestVCP(BrightnessMethodTest):
    @pytest.fixture
    def patch_get_display_info(self, patch_global_get_display_info, mocker: MockerFixture, method):
        '''Mock everything needed to get `VCP.get_display_info` to run'''

        def mock_iter_physical_monitors(start=0):
            displays = method.get_display_info()
            for display in displays[start:]:
                yield displays.index(display)
                # call cleanup function for testing convenience
                ctypes.windll.dxva2.DestroyPhysicalMonitor(0)

        mocker.patch.object(ctypes, 'windll', FakeWinDLL, create=True)
        # also patch locally imported version
        mocker.patch.object(sbc.windows, 'windll', FakeWinDLL)

        sbc.windows.__cache__.enabled = False

        return mocker.patch.object(
            sbc.windows.VCP, 'iter_physical_monitors',
            Mock(side_effect=mock_iter_physical_monitors, spec=True),
            create=True
        )

    @pytest.fixture
    def patch_get_brightness(self, mocker: MockerFixture, patch_get_display_info):
        pass

    @pytest.fixture
    def patch_set_brightness(self, mocker: MockerFixture, patch_get_display_info):
        pass

    @pytest.fixture
    def method(self) -> Type[BrightnessMethod]:
        return sbc.windows.VCP

    class TestGetBrightness(BrightnessMethodTest.TestGetBrightness):
        @pytest.mark.parametrize('display_kw', [None, 0, 1, 2])
        def test_handles_are_cleaned_up(self, mocker: MockerFixture, method, display_kw):
            '''
            DestroyPhysicalMonitor should be called ONCE for each monitor iterated over.
            When using the `display` kwarg, only one monitor should be iterated over and therefore only one
            handle should be destroyed
            '''
            num_displays = 1 if display_kw is not None else len(method.get_display_info())
            spy = mocker.spy(ctypes.windll.dxva2, 'DestroyPhysicalMonitor')
            method.get_brightness(display=display_kw)
            assert spy.call_count == num_displays

        class TestDisplayKwarg(BrightnessMethodTest.TestGetBrightness.TestDisplayKwarg):
            def test_with(self, mocker: MockerFixture, freeze_display_info, method, subtests):
                spy = mocker.spy(ctypes.windll.dxva2, 'GetVCPFeatureAndVCPFeatureReply')
                handles = tuple(sbc.windows.VCP.iter_physical_monitors())
                for index, display in enumerate(freeze_display_info):
                    with subtests.test(index=index):
                        method.get_brightness(display=index)
                        spy.assert_called_once()
                        assert spy.mock_calls[0].args[0] == handles[index]
                        spy.reset_mock()

            def test_without(self, mocker: MockerFixture, method, subtests):
                spy = mocker.spy(ctypes.windll.dxva2, 'GetVCPFeatureAndVCPFeatureReply')
                handles = tuple(sbc.windows.VCP.iter_physical_monitors())
                method.get_brightness()
                spy.assert_called()
                for index, handle in enumerate(handles):
                    with subtests.test(index=index):
                        assert spy.mock_calls[index].args[0] == handle

    class TestSetBrightness(BrightnessMethodTest.TestSetBrightness):
        @pytest.mark.parametrize('display_kw', [None, 0, 1, 2])
        def test_handles_are_cleaned_up(self, mocker: MockerFixture, method, display_kw):
            '''See equivalent test in `TestGetBrightness`'''
            num_displays = 1 if display_kw is not None else len(method.get_display_info())
            spy = mocker.spy(ctypes.windll.dxva2, 'DestroyPhysicalMonitor')
            method.set_brightness(100, display=display_kw)
            assert spy.call_count == num_displays

        class TestDisplayKwarg(BrightnessMethodTest.TestSetBrightness.TestDisplayKwarg):
            def test_with(self, mocker: MockerFixture, freeze_display_info, method, subtests):
                spy = mocker.spy(ctypes.windll.dxva2, 'SetVCPFeature')
                handles = tuple(sbc.windows.VCP.iter_physical_monitors())
                for index, display in enumerate(freeze_display_info):
                    with subtests.test(index=index):
                        method.set_brightness(100, display=index)
                        spy.assert_called_once()
                        assert spy.mock_calls[0].args[0] == handles[index]
                        spy.reset_mock()

            def test_without(self, mocker: MockerFixture, method, subtests):
                spy = mocker.spy(ctypes.windll.dxva2, 'SetVCPFeature')
                handles = tuple(sbc.windows.VCP.iter_physical_monitors())
                method.set_brightness(100)
                spy.assert_called()
                for index, handle in enumerate(handles):
                    with subtests.test(index=index):
                        assert spy.mock_calls[index].args[0] == handle
