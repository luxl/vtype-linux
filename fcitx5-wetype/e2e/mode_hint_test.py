"""在私有 D-Bus 会话验证 Shift 切换提示、自动隐藏和组词保护。"""
import os
from pathlib import Path

from dbus_test_client import Client, controller, paused_engine, pump

SHIFT_L = 0xFFE1
SHIFT_R = 0xFFE2


def configure_hint(enabled=True):
    # 路径由隔离运行器提供，只修改临时配置。
    Path(os.environ['WETYPE_PAGETEST_CONFIG']).write_text(
        '[Behavior]\nCompactInputMethodInformation=True\n'
        'ShowInputMethodInformation=%s\n' % ('True' if enabled else 'False'))
    controller.ReloadConfig()
    pump()


class HintClient(Client):
    def __init__(self):
        super().__init__('wetype-mode-hint')
        self.hint = ''
        self.panel_preedit = ''

    def _ui(self, *args):
        super()._ui(*args)
        self.panel_preedit = ''.join(str(part[0]) for part in args[0])
        self.hint = ''.join(str(part[0]) for part in args[2])

    def tap_shift(self, key=SHIFT_L):
        self.press(key)
        self.press(key, states=1, release=True)


configure_hint()
c = HintClient()
c.focus()
pump(1.1)
assert c.hint == '', c.hint

for key in (SHIFT_L, SHIFT_R):
    c.tap_shift(key)
    assert c.hint == '英', repr(c.hint)
    assert not c.commits and not c.candidates and not c.panel_preedit
    assert str(controller.CurrentInputMethod()) == 'wetype-im'
    assert not c.press('a'), '英文模式应将字母交给应用'
    c.tap_shift(key)
    assert c.hint == '中', repr(c.hint)
    assert not c.commits and not c.candidates and not c.panel_preedit
    assert str(controller.CurrentInputMethod()) == 'wetype-im'
print('PASS 左右 Shift 均显示中/英，不上屏提示文字、不切换输入法')

pump(1.1)
assert c.hint == '', '提示应自动隐藏'
c.tap_shift()
c.tap_shift()
assert c.hint == '中', repr(c.hint)
c.type('nihao')
assert c.hint == '' and c.candidates, '继续输入应恢复正常候选'
c.press('space')
assert c.commits == ['你好'], c.commits
c.commits.clear()
print('PASS 自动隐藏、快速往返切换和继续中文输入')

c.type('nihao')
c.tap_shift()
assert c.commits == ['nihao'] and c.hint == '英', (c.commits, c.hint)
assert not c.candidates and not c.panel_preedit
c.commits.clear()
c.tap_shift()
print('PASS 组词中切换保留原始拼音并显示新模式')

with paused_engine():
    c.type('nihao', wait=False)
    c.press('space', delay=0)
    c.type('zhongguo', wait=False)
    c.tap_shift()
    assert ''.join(c.commits) == 'nihao zhongguo', c.commits
    assert c.hint == '英', repr(c.hint)
pump(.3)
assert ''.join(c.commits) == 'nihao zhongguo' and not c.candidates
assert c.hint == '英', '迟到引擎响应不应覆盖模式提示'
c.commits.clear()
c.tap_shift()
pump(1.1)
print('PASS 等待候选时切换保留所有按键，迟到响应不覆盖提示')

c.press(SHIFT_L)
c.press('A', states=1)
c.press(SHIFT_L, states=1, release=True)
assert not c.hint, 'Shift 组合键不应触发模式提示'
c.press('enter')
assert c.commits == ['A'], c.commits
c.commits.clear()
c.type('nihao')
c.press('space')
assert c.commits == ['你好'], c.commits
c.commits.clear()
print('PASS Shift 组合键保持原有输入行为')

configure_hint(False)
c.tap_shift()
assert not c.hint and not c.press('a')
c.tap_shift()
assert not c.hint
c.type('nihao')
c.press('space')
assert c.commits == ['你好'], c.commits
print('PASS 遵循 Fcitx 全局提示开关，关闭提示仍能正常切换')
