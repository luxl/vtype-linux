#!/usr/bin/env python3
"""测试双拼引擎和配置界面；仅使用临时词库与私有 D-Bus 会话。"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def test_engine(args):
    test_engine_scheme(args, "小鹤", "3", "nihc", [
        ("vsgo", "中国"), ("vswf", "中文"), ("uijp", "世界"),
        ("bwjk", "北京"), ("aigo", "爱国"), ("ah", "昂")])
    test_engine_scheme(args, "微软", "2", "nihk", [
        ("vsgo", "中国"), ("bzj;", "北京"), ("njj;", "南京"),
        ("ol", "爱"), ("oj", "安")])


def test_engine_scheme(args, name, solution, hello, phrases):
    sys.path.insert(0, str(args.source / "scripts"))
    from test_bionic_daemon import Engine

    os.environ["WETYPE_DOUBLE_PIN"] = solution
    with tempfile.TemporaryDirectory(prefix="vtype-double-pin.") as directory:
        work = Path(directory) / "dict"
        (work / "userdict/v5").mkdir(parents=True)
        (work / "userdict/user_hot_word").mkdir(parents=True)
        with (Path(directory) / "engine.log").open("wb") as log:
            def start():
                engine = Engine(args.engine_dir, work, False, None, log,
                                harness=args.harness)
                engine.command("OPT spans", "OK")
                return engine

            engine = start()
            try:
                for key in hello:
                    words = engine.candidates(key)
                assert words[0] == (4, "你好"), words[:5]
                for code, expected in phrases:
                    engine.command("C", "OK")
                    assert engine.candidates(code)[0] == (len(code), expected)
                print(f"PASS {name}逐键、整句与零声母输入", flush=True)

                engine.command("C", "OK")
                tail, expected = ("bzj;", "北京") if solution == "2" else ("vsgo", "中国")
                words = engine.candidates(hello + tail)
                partial = words.index((4, "你好"))
                remaining = engine.command(f"S {partial}", "CAND")
                assert f"4:{expected}" in remaining.split("\t")[1:], remaining
                engine.command("S 0", "OK")
                print(f"PASS {name}部分选词与剩余编码长度", flush=True)

                engine.command("C", "OK")
                words = engine.candidates(hello)
                before = words.index((4, "拟好"))
                engine.command(f"S {before}", "OK")
                time.sleep(0.5)
                engine.command("C", "OK")
                time.sleep(0.5)
                learned = engine.candidates(hello).index((4, "拟好"))
                assert learned < before
                engine.command("SAVE", "OK")
            finally:
                engine.close()

            engine = start()
            try:
                assert engine.candidates(hello).index((4, "拟好")) <= learned
            finally:
                engine.close()
            print(f"PASS {name}词条学习及重启持久化", flush=True)

        config = Path(directory) / "config/fcitx5/conf"
        config.mkdir(parents=True)
        (config / "wetype.conf").write_text(f"PinyinScheme={name}双拼\n")
        env = dict(os.environ, XDG_CONFIG_HOME=str(config.parents[1]),
                   WETYPE_ENGINE_DIR=str(args.engine_dir), WETYPE_HARNESS=str(args.harness),
                   WETYPE_WORK_DIR=str(work))
        env.pop("WETYPE_DOUBLE_PIN", None)
        demo = subprocess.run(["bash", str(args.source / "src/wetype-ime-demo.sh"), hello],
                              env=env, capture_output=True, text=True, check=True)
        assert "你好" in demo.stdout.splitlines()[-1], demo.stdout
        print(f"PASS {name}命令行演示跟随配置", flush=True)


def test_fcitx(args):
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop

    DBusGMainLoop(set_as_default=True)

    with tempfile.TemporaryDirectory(prefix="vtype-fcitx-double-pin.") as directory:
        root = Path(directory)
        config = root / "config/fcitx5"
        config.mkdir(parents=True)
        (config / "conf").mkdir()
        (config / "conf/wetype.conf").write_text("PinyinScheme=微软双拼\n")
        (config / "profile").write_text(
            "[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=wetype-im\n"
            "[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n"
            "[Groups/0/Items/1]\nName=wetype-im\nLayout=\n"
            "[GroupOrder]\n0=Default\n")
        os.environ.update(
            XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(root / "data"),
            XDG_STATE_HOME=str(root / "state"), XDG_CACHE_HOME=str(root / "cache"),
            XDG_DATA_DIRS=str(args.addon_prefix / "share"),
            WETYPE_ENGINE_DIR=str(args.engine_dir), WETYPE_WORK_DIR=str(root / "dict"),
            WETYPE_HARNESS_LOG=str(root / "harness.log"),
            WETYPE_PAGETEST_LOG=str(root / "fcitx.log"))
        for key in ["DISPLAY", "WAYLAND_DISPLAY", "WETYPE_CLOUD_CONFIG"]:
            os.environ.pop(key, None)
        if args.cloud_launcher:
            # 只验证云代理启动分支；关闭联网，不加载实际账户或云配置。
            cloud_config = root / "cloud.json"
            cloud_config.write_text('{"enabled": false}')
            os.environ["WETYPE_CLOUD_CONFIG"] = str(cloud_config)
        (root / "dict/userdict/v5").mkdir(parents=True)
        (root / "dict/userdict/user_hot_word").mkdir(parents=True)
        registry = dbus.SessionBus()
        with (root / "fcitx.log").open("wb") as log:
            process = subprocess.Popen(
                ["fcitx5", "--disable=classicui,xim,waylandim,wayland,xcb"],
                stdout=log, stderr=subprocess.STDOUT)
            try:
                os.environ["WETYPE_E2E_FCITX_PID"] = str(process.pid)
                for _ in range(100):
                    # 不用 fcitx5-remote 轮询：它会触发 D-Bus 自动启动另一个实例。
                    if registry.name_has_owner("org.fcitx.Fcitx5"):
                        break
                    assert process.poll() is None, "私有 Fcitx 启动失败"
                    time.sleep(0.05)
                else:
                    raise AssertionError("私有 Fcitx D-Bus 未就绪")

                sys.path.insert(0, str(args.source / "fcitx5-wetype/e2e"))
                from dbus_test_client import Client, bus, controller, pump

                client = Client("vtype-double-pinyin-test")
                client.focus()
                time.sleep(2)
                pump()
                url = "fcitx://config/inputmethod/wetype-im"
                raw, description = controller.GetConfig(url)
                assert str(raw["PinyinScheme"]) == "微软双拼", raw
                assert description, "输入法没有导出图形配置描述"
                assert "微软双拼" in str(description), description
                preedits = []
                bus.add_signal_receiver(
                    lambda *values: preedits.append("".join(str(part[0]) for part in values[0])),
                    dbus_interface="org.fcitx.Fcitx.InputContext1",
                    signal_name="UpdateClientSideUI", path=client.path)

                def scheme(value):
                    raw["PinyinScheme"] = dbus.String(value, variant_level=1)
                    controller.SetConfig(url, raw)
                    pump(2)
                    current, _ = controller.GetConfig(url)
                    assert str(current["PinyinScheme"]) == value

                def commit(code, expected):
                    before = len(client.commits)
                    client.type(code)
                    client.press("space", delay=0.5)
                    assert client.commits[before:] == [expected], client.commits

                commit("nihk", "你好")
                assert "ni hk" in preedits, preedits
                commit("bzj;", "北京")
                assert "bz j;" in preedits, preedits
                commit("ol", "爱")
                commit("oj", "安")
                print("PASS 微软配置启动、分号韵母、零声母与两键分段", flush=True)

                client.type("bzj;")
                before = len(client.commits)
                client.press("backspace", delay=0.2)
                client.press(";", delay=0.5)
                client.synchronize_ui()
                client.press("space", delay=0.5)
                assert client.commits[before:] == ["北京"], client.commits

                # 快速输入后立刻空格，分号也必须经过候选等待和回放路径。
                before = len(client.commits)
                client.type("njj;", wait=False)
                client.press("space", delay=0)
                for _ in range(100):
                    pump(0.1)
                    if len(client.commits) > before:
                        break
                assert client.commits[before:] == ["南京"], client.commits
                print("PASS 微软分号退格重输与快速空格上屏", flush=True)

                before = len(client.commits)
                client.press(";")
                assert client.commits[before:] == ["；"], client.commits
                client.type("nihk")
                client.press(";")
                assert client.commits[-1] == "你好；", client.commits
                client.type("ABC")
                client.press(";")
                assert client.commits[-1] == "ABC；", client.commits
                client.type("bzj")
                client.press(":", states=1)
                assert client.commits[-1].endswith("："), client.commits

                raw["AlwaysEnglishPunctuation"] = dbus.String("True", variant_level=1)
                scheme("微软双拼")
                commit("bzj;", "北京")
                client.type("nihk")
                client.press(";")
                assert client.commits[-1] == "你好;", client.commits
                raw["AlwaysEnglishPunctuation"] = dbus.String("False", variant_level=1)
                print("PASS 分号标点、大写英文、冒号和英文标点设置", flush=True)

                next_page = raw["NextPage"]
                raw["NextPage"] = dbus.Dictionary(
                    {"0": dbus.String("semicolon", variant_level=1)}, signature="sv", variant_level=1)
                scheme("微软双拼")
                commit("bzj;", "北京")
                client.type("nihk")
                before = len(client.commits)
                client.press(";")
                assert len(client.commits) == before, client.commits
                client.press("esc")
                raw["NextPage"] = next_page
                print("PASS 分号韵母与自定义翻页键的优先级", flush=True)

                scheme("小鹤双拼")
                client.type("nihc")
                assert any("你好" in text for _, text in client.candidates), client.candidates
                assert "ni hc" in preedits, preedits
                client.press("space", delay=0.5)
                assert client.commits[-1] == "你好", client.commits
                print("PASS 图形配置、小鹤候选、两键分段与上屏", flush=True)

                client.type("nihx")
                client.press("backspace", delay=0.2)
                client.press("c", delay=0.5)
                client.synchronize_ui()
                client.press("space", delay=0.5)
                assert client.commits[-1] == "你好", client.commits
                print("PASS 双拼退格和重输", flush=True)

                client.type("bwj")
                client.press(";")
                assert client.commits[-1].endswith("；"), client.commits

                scheme("全拼")
                client.type("nihao")
                client.press("space", delay=0.5)
                assert client.commits[-1] == "你好", client.commits
                client.type("bei")
                client.press(";")
                assert client.commits[-1].endswith("；"), client.commits
                scheme("微软双拼")
                commit("bzj;", "北京")
                assert "PinyinScheme=微软双拼" in (config / "conf/wetype.conf").read_text()
                print("PASS 全拼和小鹤标点回归、热切换及配置保存", flush=True)
            except BaseException:
                print("\n".join((root / "fcitx.log").read_text(errors="replace").splitlines()[-35:]))
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--harness", type=Path, help="已编译的 Android 宿主程序")
    parser.add_argument("--addon-prefix", type=Path, help="包含 share/fcitx5 的插件安装前缀")
    parser.add_argument("--engine-dir", type=Path,
                        default=Path.home() / ".local/lib/wetype-ime/arm64")
    parser.add_argument("--mode", choices=["engine", "fcitx", "private-fcitx"], default="engine")
    parser.add_argument("--cloud-launcher", action="store_true",
                        help="用关闭联网的临时云配置验证引擎启动分支")
    args = parser.parse_args()
    args.source = args.source.resolve()
    args.engine_dir = args.engine_dir.resolve()
    args.harness = (args.harness or args.engine_dir / "wetype-harness").resolve()
    if args.addon_prefix:
        args.addon_prefix = args.addon_prefix.resolve()
    elif args.mode != "engine":
        parser.error("Fcitx 检查需要 --addon-prefix")
    if args.mode == "engine":
        test_engine(args)
    elif args.mode == "private-fcitx":
        assert os.environ.get("VTYPE_PRIVATE_DBUS") == "1", "请使用 --mode fcitx"
        test_fcitx(args)
    else:
        env = os.environ.copy()
        env["VTYPE_PRIVATE_DBUS"] = "1"
        subprocess.run(["dbus-run-session", "--", sys.executable, __file__,
                        "--source", str(args.source), "--harness", str(args.harness),
                        "--addon-prefix", str(args.addon_prefix),
                        "--engine-dir", str(args.engine_dir), "--mode", "private-fcitx",
                        *(["--cloud-launcher"] if args.cloud_launcher else [])],
                       env=env, check=True)


if __name__ == "__main__":
    main()
